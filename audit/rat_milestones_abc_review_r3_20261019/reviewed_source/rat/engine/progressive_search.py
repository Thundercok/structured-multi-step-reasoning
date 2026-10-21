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
from rat.engine.finder_intent import (
    FinderIntentPlan,
    is_report_row,
    is_slide_row,
    parse_finder_intent,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchFilters:
    extensions: tuple[str, ...] = ()
    excluded_extensions: tuple[str, ...] = ()
    date_min: float | None = None
    date_max: float | None = None
    date_max_exclusive: float | None = None
    date_field: str = 'modified'
    slide_rule: bool = False
    report_rule: bool = False
    sort: str = 'relevance'

    def __post_init__(self):
        for name in ('extensions', 'excluded_extensions'):
            values = tuple(value.lower() for value in getattr(self, name))
            object.__setattr__(self, name, values)

    def accepts(self, row):
        ext = row.get('file_ext', '').lower()
        target_ts = row.get('created_at' if self.date_field == 'created' else 'modified_at', 0)
        return (
            (not self.extensions or ext in self.extensions)
            and ext not in self.excluded_extensions
            and (self.date_min is None or target_ts >= self.date_min)
            and (
                self.date_max_exclusive is not None and target_ts < self.date_max_exclusive
                if self.date_max_exclusive is not None
                else (self.date_max is None or target_ts <= self.date_max)
            )
            and (not self.slide_rule or is_slide_row(row))
            and (not self.report_rule or row.get('_report_rule_matched') or is_report_row(row))
        )


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
    version: str = ''
    modified_at: float | None = None


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
    intent: FinderIntentPlan | None = None


class ProgressiveSearch:
    def __init__(self, db_path, *, catalog=None, semantic=None, now_fn=None):
        self.db = Database(str(db_path), read_only=True)
        self.catalog = catalog if catalog is not None else ApplicationCatalog()
        self.semantic = semantic
        self.now_fn = now_fn

    @staticmethod
    def _file_hit(row, origin):
        path = row['file_path']
        if not Path(path).is_absolute() or not Path(path).is_file():
            return None
        return SearchHit(
            'file:' + hashlib.sha256(path.encode()).hexdigest()[:24],
            'file',
            row['file_name'],
            path,
            origin,
            (row.get('summary') or '')[:200],
            modified_at=row.get('modified_at'),
        )

    def _snapshot(self, request, phase, hits, *, complete, errors=(), intent=None):
        selected = request.selected_id if any(h.resource_id == request.selected_id for h in hits) else None
        return SearchSnapshot(
            request.query_id,
            request.query,
            phase,
            tuple(hits),
            selected,
            complete,
            (time.perf_counter() - request.started) * 1000,
            tuple(errors),
            intent=intent,
        )

    def _resolve_intent_and_filters(self, request: SearchRequest) -> tuple[FinderIntentPlan, SearchFilters]:
        now_val = self.now_fn() if callable(self.now_fn) else None
        intent = parse_finder_intent(request.query, now=now_val, catalog=self.catalog)
        rf = request.filters
        effective = SearchFilters(
            extensions=rf.extensions or intent.extensions,
            excluded_extensions=rf.excluded_extensions or intent.excluded_extensions,
            date_min=rf.date_min if rf.date_min is not None else intent.date_min,
            date_max=rf.date_max if rf.date_max is not None else intent.date_max,
            date_max_exclusive=(
                rf.date_max_exclusive if rf.date_max_exclusive is not None else intent.date_max_exclusive
            ),
            date_field=rf.date_field if rf.date_field != 'modified' else getattr(intent, 'date_field', 'modified'),
            slide_rule=rf.slide_rule or intent.slide_rule,
            report_rule=rf.report_rule or intent.report_rule,
            sort=rf.sort if rf.sort != 'relevance' else intent.sort,
        )
        return intent, effective

    def initial(self, request):
        if type(request.limit) is not int or not 1 <= request.limit <= 100 or len(request.query) > 2000:
            raise ValueError('invalid_finder_request')
        if request.cancelled.is_set():
            raise InterruptedError('finder_cancelled')
        intent, eff_filters = self._resolve_intent_and_filters(request)
        if intent.needs_clarification:
            return self._snapshot(request, 'lexical', (), complete=True, errors=(), intent=intent)
        if intent.action == 'negated_open':
            return self._snapshot(request, 'lexical', (), complete=True, errors=(), intent=intent)
        if intent.action == 'open_app':
            app_matches = self.catalog.search(intent.target_app_query, limit=request.limit)
            hits = [
                SearchHit(
                    a.resource_id,
                    'application',
                    a.name,
                    a.path,
                    'application_catalog',
                    snippet=a.path,
                    bundle_id=a.bundle_id,
                    version=a.version,
                )
                for a in app_matches
            ]
            if len(app_matches) > 1:
                intent = replace(
                    intent,
                    needs_clarification=True,
                    clarification_reason=(
                        f"Có {len(app_matches)} ứng dụng khớp với '{intent.target_app_query}'. "
                        "Hãy chọn đúng bản cài đặt cần mở."
                    ),
                )
            elif len(app_matches) == 0:
                intent = replace(
                    intent,
                    needs_clarification=True,
                    clarification_reason=(
                        f"Không tìm thấy ứng dụng '{intent.target_app_query}' trong danh mục đã xác thực."
                    ),
                )
            return self._snapshot(request, 'lexical', hits, complete=True, errors=(), intent=intent)

        hits, errors = [], []
        has_file_only_filter = bool(
            eff_filters.extensions
            or eff_filters.excluded_extensions
            or eff_filters.date_min is not None
            or eff_filters.date_max is not None
            or eff_filters.date_max_exclusive is not None
            or eff_filters.slide_rule
            or eff_filters.report_rule
            or eff_filters.sort != 'relevance'
        )
        if not has_file_only_filter:
            hits.extend(
                SearchHit(
                    a.resource_id,
                    'application',
                    a.name,
                    a.path,
                    'application_catalog',
                    snippet=a.path,
                    bundle_id=a.bundle_id,
                    version=a.version,
                )
                for a in self.catalog.search(request.query, limit=request.limit)
            )
        fts_query = intent.query_terms if intent.has_structured_constraints else request.query
        try:
            if fts_query.strip() or has_file_only_filter:
                rows = self.db.search_metadata(
                    fts_query,
                    extensions=eff_filters.extensions,
                    excluded_extensions=eff_filters.excluded_extensions,
                    date_min=eff_filters.date_min,
                    date_max=eff_filters.date_max,
                    date_max_exclusive=eff_filters.date_max_exclusive,
                    date_field=eff_filters.date_field,
                    slide_rule=eff_filters.slide_rule,
                    report_rule=eff_filters.report_rule,
                    sort=eff_filters.sort,
                    limit=min(100, request.limit * 3),
                    should_cancel=request.cancelled.is_set,
                )
                for row in rows:
                    if not eff_filters.accepts(row):
                        continue
                    hit = self._file_hit(row, 'lexical_index')
                    if hit and len(hits) < request.limit:
                        hits.append(hit)
        except InterruptedError:
            raise
        except Exception:
            errors.append('file_index_unavailable')
        if request.cancelled.is_set():
            raise InterruptedError('finder_cancelled')
        return self._snapshot(
            request,
            'lexical',
            hits,
            complete=(
                self.semantic is None
                or not request.query.strip()
                or len(hits) >= request.limit
                or eff_filters.sort == 'modified_desc'
            ),
            errors=errors,
            intent=intent,
        )

    def refine(self, request, initial):
        """Append grounded semantic hits; keep existing identities and selection."""
        intent, eff_filters = self._resolve_intent_and_filters(request)
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
                    'SELECT file_path, file_name, file_ext, modified_at, created_at, '
                    "substr(coalesce(summary, ''), 1, 200) AS summary FROM documents WHERE file_path = ?",
                    (str(path),)).fetchone()
                row = dict(row) if row is not None else None
                if not row or not eff_filters.accepts(row):
                    continue
                hit = self._file_hit(row, 'semantic_index')
                if hit and hit.resource_id not in seen:
                    hits.append(hit)
                    seen.add(hit.resource_id)
        except InterruptedError:
            raise
        except Exception:
            errors.append('semantic_unavailable')
        return self._snapshot(request, 'semantic', hits, complete=True, errors=errors, intent=initial.intent or intent)

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
