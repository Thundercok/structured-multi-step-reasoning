"""Headless progressive finder: independent lexical and optional semantic lanes.

Query snapshots are transient search projections, not a second artifact/task
store. No application launch, file extraction, model or embedding import occurs
here. Semantic retrieval is an explicitly injected provider of indexed paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import logging
from pathlib import Path
import threading
import time

from rat.crawler.db import Database
from rat.engine.app_resolver import ApplicationCatalog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchFilters:
    extensions: tuple[str, ...] = ()
    excluded_extensions: tuple[str, ...] = ()
    date_min: float | None = None
    date_max: float | None = None

    def __post_init__(self):
        for name in ('extensions', 'excluded_extensions'):
            values = tuple(value.lower() for value in getattr(self, name))
            object.__setattr__(self, name, values)

    def accepts(self, row):
        ext = row.get('file_ext', '').lower()
        return (not self.extensions or ext in self.extensions) and ext not in self.excluded_extensions \
            and (self.date_min is None or row.get('modified_at', 0) >= self.date_min) \
            and (self.date_max is None or row.get('modified_at', 0) <= self.date_max)


@dataclass(frozen=True)
class SearchHit:
    resource_id: str
    kind: str
    title: str
    path: str
    origin: str
    snippet: str = ''
    bundle_id: str | None = None
    read: bool = False


@dataclass(frozen=True)
class SearchRequest:
    query_id: int
    query: str
    limit: int = 15
    filters: SearchFilters = SearchFilters()
    selected_id: str | None = None
    started: float = field(default_factory=time.perf_counter)
    cancelled: threading.Event = field(default_factory=threading.Event, compare=False)


@dataclass(frozen=True)
class SearchSnapshot:
    query_id: int
    query: str
    phase: str
    hits: tuple[SearchHit, ...]
    selected_id: str | None
    complete: bool
    elapsed_ms: float
    errors: tuple[str, ...] = ()


class ProgressiveSearch:
    def __init__(self, db_path, *, catalog=None, semantic=None):
        self.db = Database(str(db_path), read_only=True)
        self.catalog = catalog if catalog is not None else ApplicationCatalog()
        self.semantic = semantic

    @staticmethod
    def _file_hit(row, origin):
        path = row['file_path']
        if not Path(path).is_absolute() or not Path(path).is_file():
            return None
        return SearchHit('file:' + hashlib.sha256(path.encode()).hexdigest()[:24],
            'file', row['file_name'], path, origin, (row.get('summary') or '')[:200])

    def _snapshot(self, request, phase, hits, *, complete, errors=()):
        selected = request.selected_id if any(h.resource_id == request.selected_id for h in hits) else None
        return SearchSnapshot(request.query_id, request.query, phase, tuple(hits), selected,
                              complete, (time.perf_counter() - request.started) * 1000, tuple(errors))

    def initial(self, request):
        if type(request.limit) is not int or not 1 <= request.limit <= 100 or len(request.query) > 2000:
            raise ValueError('invalid_finder_request')
        if request.cancelled.is_set():
            raise InterruptedError('finder_cancelled')
        hits, errors = [], []
        if not request.filters.extensions and request.filters.date_min is None and request.filters.date_max is None:
            hits.extend(SearchHit(a.resource_id, 'application', a.name, a.path, 'application_catalog',
                                  bundle_id=a.bundle_id) for a in
                        self.catalog.search(request.query, limit=request.limit))
        try:
            rows = self.db.search_metadata(request.query, extensions=request.filters.extensions,
                excluded_extensions=request.filters.excluded_extensions,
                date_min=request.filters.date_min, date_max=request.filters.date_max,
                limit=min(100, request.limit * 3), should_cancel=request.cancelled.is_set)
            for row in rows:
                hit = self._file_hit(row, 'lexical_index')
                if hit and len(hits) < request.limit:
                    hits.append(hit)
        except InterruptedError:
            raise
        except Exception:
            errors.append('file_index_unavailable')
        if request.cancelled.is_set():
            raise InterruptedError('finder_cancelled')
        return self._snapshot(request, 'lexical', hits,
            complete=self.semantic is None or not request.query.strip() or len(hits) >= request.limit, errors=errors)

    def refine(self, request, initial):
        """Append grounded semantic hits; keep existing identities and selection."""
        hits, errors = list(initial.hits), list(initial.errors)
        seen = {h.resource_id for h in hits}
        try:
            for index, path in enumerate(self.semantic(request)):
                if request.cancelled.is_set():
                    raise InterruptedError('finder_cancelled')
                if index >= 100 or len(hits) >= request.limit:
                    break
                connection = self.db.get_connection()
                connection.execute('PRAGMA busy_timeout=50')
                row = connection.execute(
                    'SELECT file_path, file_name, file_ext, modified_at, '
                    "substr(coalesce(summary, ''), 1, 200) AS summary FROM documents WHERE file_path = ?",
                    (str(path),)).fetchone()
                row = dict(row) if row is not None else None
                if not row or not request.filters.accepts(row):
                    continue
                hit = self._file_hit(row, 'semantic_index')
                if hit and hit.resource_id not in seen:
                    hits.append(hit)
                    seen.add(hit.resource_id)
        except InterruptedError:
            raise
        except Exception:
            errors.append('semantic_unavailable')
        return self._snapshot(request, 'semantic', hits, complete=True, errors=errors)

    def snapshots(self, request):
        initial = self.initial(request)
        yield initial
        if not initial.complete and not request.cancelled.is_set():
            yield self.refine(request, initial)

    def close_connection(self):
        conn = getattr(self.db._local, 'conn', None)
        if conn is not None:
            conn.close()
            self.db._local.conn = None


class _LatestWorker:
    """One running job and one replaceable pending job; no unbounded FIFO."""
    def __init__(self, name, cleanup):
        self._condition = threading.Condition()
        self._pending = None
        self._closed = False
        self._cleanup = cleanup
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(self, job):
        with self._condition:
            if not self._closed:
                self._pending = job
                self._condition.notify()

    def _run(self):
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._closed or self._pending is not None)
                    if self._closed:
                        return
                    job, self._pending = self._pending, None
                try:
                    job()
                except Exception:
                    logger.exception('Finder job failed')
        finally:
            self._cleanup()

    def close(self, timeout):
        with self._condition:
            self._closed, self._pending = True, None
            self._condition.notify()
        if threading.current_thread() is self._thread:
            return False
        self._thread.join(timeout)
        return not self._thread.is_alive()


class SearchCoordinator:
    """Callbacks run on workers; UI must also check query_id at event delivery."""
    def __init__(self, search, on_update):
        self.search, self.on_update = search, on_update
        self._lock = threading.Lock()
        self._current = None
        self._counter = 0
        self._closed = False
        self._fast = _LatestWorker('rat-finder-fast', search.close_connection)
        self._semantic = _LatestWorker('rat-finder-semantic', search.close_connection) if search.semantic else None

    def is_current(self, query_id):
        with self._lock:
            return not self._closed and self._current is not None \
                and self._current.query_id == query_id and not self._current.cancelled.is_set()

    def submit(self, query, *, limit=15, filters=SearchFilters(), selected_id=None):
        if type(limit) is not int or not 1 <= limit <= 100 or not isinstance(query, str) or len(query) > 2000:
            raise ValueError('invalid_finder_request')
        with self._lock:
            if self._closed:
                raise RuntimeError('finder_closed')
            if self._current is not None:
                self._current.cancelled.set()
            self._counter += 1
            request = SearchRequest(self._counter, query, limit, filters, selected_id)
            self._current = request
            self._fast.submit(lambda: self._initial(request))
        return request.query_id

    def _publish(self, request, snapshot):
        if self.is_current(request.query_id):
            self.on_update(snapshot)

    def _initial(self, request):
        if not self.is_current(request.query_id):
            return
        try:
            initial = self.search.initial(request)
            self._publish(request, initial)
            with self._lock:
                if not initial.complete and not self._closed and self._current is request \
                        and not request.cancelled.is_set():
                    self._semantic.submit(lambda: self._refine(request, initial))
        except InterruptedError:
            pass

    def _refine(self, request, initial):
        if not self.is_current(request.query_id):
            return
        try:
            self._publish(request, self.search.refine(request, initial))
        except InterruptedError:
            pass

    def cancel(self):
        with self._lock:
            if self._current is not None:
                self._current.cancelled.set()

    def close(self, timeout=2):
        with self._lock:
            self._closed = True
            if self._current is not None:
                self._current.cancelled.set()
        fast = self._fast.close(timeout)
        semantic = self._semantic.close(timeout) if self._semantic else True
        return fast and semantic
