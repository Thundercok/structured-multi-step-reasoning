"""Scoped macOS metadata/full-text provider, reusable by any RAT product profile."""
from __future__ import annotations

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from rat.engine.finder_intent import parse_finder_intent, _fold_ascii
from rat.engine.rrf import ReciprocalRankFusion
from rat.os.system_process import system_environment

logger = logging.getLogger(__name__)


class SpotlightFailure(ValueError):
    def __init__(self, code, returncode=None):
        super().__init__(code)
        self.code, self.returncode = code, returncode


def _spotlight_error(payload):
    # Inspect bounded stderr locally; never expose raw paths/query text in logs.
    message = payload.decode('utf-8', errors='replace').casefold()
    if any(word in message for word in ('not permitted', 'permission denied', 'not authorized')):
        return 'spotlight_permission_denied'
    if any(word in message for word in ('invalid query', 'parse error', 'syntax error')):
        return 'spotlight_invalid_query'
    return 'spotlight_unavailable'


class ScopePolicy:
    def __init__(self, roots=()):
        self.lock = threading.RLock()
        self.set_roots(roots)

    def set_roots(self, roots):
        with self.lock:
            self.roots = tuple(dict.fromkeys(Path(p).expanduser().resolve() for p in roots if Path(p).expanduser().is_dir()))
            self.version = hashlib.sha256('\0'.join(map(str, self.roots)).encode()).hexdigest()

    def verify(self, raw_path, expected=None):
        with self.lock:
            p = Path(raw_path).resolve(strict=True)
            if not any(p.is_relative_to(root) for root in self.roots):
                raise ValueError('file_out_of_scope')
            # Readability verified by open, not os.access; reject nonregular targets.
            fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError('not_regular_file')
                identity = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]
                if expected is not None and identity != expected:
                    raise ValueError('stale_resource')
                return p, info, identity
            finally:
                os.close(fd)


def _quoted(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"cd'


def name_key(text):
    return unicodedata.normalize('NFC', text).casefold()


class SpotlightTimeout(TimeoutError):
    """Keep completed output rows even if Spotlight never finishes gathering."""
    def __init__(self, paths):
        super().__init__('spotlight_timeout')
        self.partial_paths = paths


def _spotlight_rows(payload):
    # -0 output can stop in the middle of a path on timeout. Never use that row.
    complete = payload[:payload.rfind(b'\0')+1]
    return [p.decode('utf-8', errors='surrogateescape') for p in complete.split(b'\0') if p][:500]


def spotlight_paths(root, predicate, should_cancel, deadline):
    if should_cancel():
        raise ValueError('cancelled:finder')
    if time.monotonic() >= deadline:
        raise TimeoutError('spotlight_timeout')
    # A file-backed pipe bounds memory even for an unexpectedly broad query.
    # Polling also lets cancel/replacement reap mdfind promptly.
    # Do not open a protected directory as a preflight: TCC/remote volumes can
    # block that call outside the subprocess timeout. Query scoped metadata;
    # real hits still pass ScopePolicy's existence/readability/identity check.
    logger.info('spotlight_scope_start')
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(['/usr/bin/mdfind', '-0', '-onlyin', str(root), predicate],
            stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
            cwd='/', env=system_environment(), close_fds=True, start_new_session=True)
        logger.info('spotlight_scope_spawned')
        try:
            while True:
                if should_cancel():
                    raise ValueError('cancelled:finder')
                if os.fstat(output.fileno()).st_size > 2_000_000:
                    raise ValueError('spotlight_candidate_overflow')
                if os.fstat(errors.fileno()).st_size > 64_000:
                    raise SpotlightFailure('spotlight_diagnostic_overflow')
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('spotlight_timeout')
                try:
                    code = process.wait(timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    pass
            if code:
                errors.seek(0)
                raise SpotlightFailure(_spotlight_error(errors.read(64_000)), code)
            if should_cancel():
                raise ValueError('cancelled:finder')
            output.seek(0)
            payload = output.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError('spotlight_candidate_overflow')
        except TimeoutError as exc:
            if process.poll() is None:
                process.kill()
            process.wait()
            output.seek(0)
            partial = output.read(2_000_001)
            if len(partial) > 2_000_000:
                raise ValueError('spotlight_candidate_overflow') from exc
            if should_cancel():
                raise ValueError('cancelled:finder') from exc
            errors.seek(0)
            diagnostic = errors.read(64_000)
            if diagnostic and _spotlight_error(diagnostic) == 'spotlight_permission_denied':
                raise SpotlightFailure('spotlight_permission_denied') from exc
            raise SpotlightTimeout(_spotlight_rows(partial)) from exc
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    return _spotlight_rows(payload)


def spotlight_scopes(roots, predicate, should_cancel, deadline):
    """Search independent scopes fairly within one bounded request budget."""
    paths, failures, completed = [], [], 0
    # Default Documents/Desktop/Downloads all start together. Custom scopes
    # share at most three processes; errors identify scope indexes, not paths.
    def search_scope(root):
        # A frozen-app query can time out while an immediately repeated query
        # succeeds. Reserve part of the SAME deadline for one retry; never
        # widen scope, retry access errors or run concurrent duplicates.
        first_deadline = min(deadline, time.monotonic()+6)
        try:
            return spotlight_paths(root, predicate, should_cancel, first_deadline)
        except SpotlightTimeout as first:
            if should_cancel() or deadline-time.monotonic() < 0.25:
                raise
            logger.info('spotlight_timeout_retry within_original_budget=true')
            try:
                return list(dict.fromkeys(first.partial_paths + spotlight_paths(root, predicate, should_cancel, deadline)))
            except SpotlightTimeout as second:
                raise SpotlightTimeout(list(dict.fromkeys(first.partial_paths+second.partial_paths))) from second

    with ThreadPoolExecutor(max_workers=min(3, len(roots))) as pool:
        pending = [pool.submit(search_scope, root)
                   for root in roots]
        for index, future in enumerate(pending):
            try:
                paths.extend(future.result())
                completed += 1
            except (OSError, TimeoutError, ValueError) as exc:
                if str(exc).startswith('cancelled:'):
                    for task in pending:
                        task.cancel()
                    raise
                if isinstance(exc, SpotlightTimeout):
                    paths.extend(exc.partial_paths)
                failure = {'provider': 'spotlight', 'code': getattr(exc, 'code', type(exc).__name__), 'scope_index': index}
                if isinstance(exc, SpotlightFailure):
                    failure['returncode'] = exc.returncode
                if isinstance(exc, SpotlightTimeout):
                    failure['partial_candidates'] = len(exc.partial_paths)
                failures.append(failure)
                logger.info('spotlight_scope_failed scope_index=%s code=%s partial_candidates=%s returncode=%s',
                    index, failure['code'], failure.get('partial_candidates', 0), failure.get('returncode'))
    if should_cancel():
        raise ValueError('cancelled:finder')
    return paths, failures, completed


class HybridFinder:
    def __init__(self, scopes, semantic=None):
        self.scopes, self.semantic = scopes, semantic

    def search(self, query, *, filters=None, limit=8, mode='auto', should_cancel=lambda: False):
        started = time.monotonic()
        with self.scopes.lock:
            roots, version = self.scopes.roots, self.scopes.version
        if not roots:
            raise ValueError('no_search_roots')
        plan = parse_finder_intent(query, now=datetime.now().astimezone())
        filters = filters or {}
        extensions = filters.get('extensions') or plan.extensions
        excluded = filters.get('excluded_extensions') or plan.excluded_extensions
        date_field = filters.get('date_field', plan.date_field)
        lower = datetime.fromisoformat(filters['from']).timestamp() if filters.get('from') else plan.date_min
        upper = datetime.fromisoformat(filters['to']).timestamp() if filters.get('to') else plan.date_max_exclusive
        if lower is not None and upper is not None and lower >= upper:
            raise ValueError('invalid_date_range')
        terms = re.findall(r'[\w.-]+', plan.query_terms or '', flags=re.UNICODE)[:12]
        if not terms and not extensions and lower is None and upper is None:
            terms = re.findall(r'[\w.-]+', query)[:12]
        predicates = [f'(kMDItemFSName == {_quoted("*" + term + "*")} || kMDItemTextContent == {_quoted(term)})'
                      for term in terms]
        if extensions:
            predicates.append('(' + ' || '.join(f'kMDItemFSName == {_quoted("*" + e)}' for e in extensions) + ')')
        predicate = ' && '.join(predicates) or 'kMDItemContentTypeTree == "public.item"'
        filename_query = bool(Path(query.strip()).suffix and len(query.split()) == 1)
        if filename_query:
            predicate = 'kMDItemFSName == ' + _quoted(query.strip())
        lexical = []
        deadline = time.monotonic() + 12
        paths, failures, completed_roots = spotlight_scopes(roots, predicate, should_cancel, deadline)

        def accepted(raw):
            try:
                p, info, identity = self.scopes.verify(raw)
                ext = p.suffix.lower()
                timestamp = getattr(info, 'st_birthtime', info.st_ctime) if date_field == 'created' else info.st_mtime
                if extensions and ext not in extensions or ext in excluded:
                    return None
                if lower is not None and timestamp < lower or upper is not None and timestamp >= upper:
                    return None
                return {'file_path': str(p), 'file_name': p.name, 'file_ext': ext,
                        'file_size': info.st_size, 'modified_at': info.st_mtime,
                        'identity': identity, 'created_at': getattr(info, 'st_birthtime', info.st_ctime)}
            except (OSError, ValueError):
                return None

        for raw in dict.fromkeys(paths):
            row = accepted(raw)
            if row:
                lexical.append(row)
        query_key = query.strip()
        folded_phrase = _fold_ascii(plan.query_terms or query_key)
        lexical.sort(key=lambda row: (
            name_key(row['file_name']) != name_key(query_key),
            folded_phrase not in _fold_ascii(row['file_name']) if folded_phrase else True,
            not all(_fold_ascii(term) in _fold_ascii(row['file_name']) for term in terms) if terms else False,
            -float(row.get('modified_at', 0.0))
        ))
        dense = []
        semantic_state = 'disabled'
        if self.semantic is not None and mode != 'metadata':
            semantic_state = 'not_indexed'
            if self.semantic.count():
                try:
                    stale = []
                    for row in self.semantic.search(query, should_cancel):
                        verified = accepted(row['file_path'])
                        if verified and row.get('identity') == verified['identity']:
                            dense.append({**row, **verified})
                        elif not verified:
                            # A filtered-out live file is not stale; only prune missing,
                            # unreadable or changed source identities from the cache.
                            try:
                                self.scopes.verify(row['file_path'], row.get('identity'))
                            except (OSError, ValueError):
                                stale.append(row['file_path'])
                        else:
                            stale.append(row['file_path'])
                    if stale:
                        self.semantic.invalidate_paths(stale)
                    semantic_state = 'queried'
                except Exception as exc:
                    if should_cancel():
                        raise ValueError('cancelled:semantic') from exc
                    semantic_state = 'failed'
                    failures.append({'provider': 'semantic', 'code': type(exc).__name__})
        fused = ReciprocalRankFusion().fuse(lexical, dense, top_k=100)
        if filters.get('sort') == 'newest' or plan.sort == 'modified_desc':
            fused.sort(key=lambda row: row.get('modified_at', 0), reverse=True)
        elif filters.get('sort') == 'oldest':
            fused.sort(key=lambda row: row.get('modified_at', 0))
        hits = []
        for row in fused[:limit]:
            p, info, identity = self.scopes.verify(row['file_path'])
            hits.append({'resource_id': hashlib.sha256(str(p).encode()).hexdigest()[:20],
                         'title': p.name, 'path': str(p), 'identity': identity,
                         'modified_at': info.st_mtime, 'size_bytes': info.st_size,
                         'match_sources': (['spotlight'] if row.get('matched_sparse') else []) +
                                          (['semantic'] if row.get('matched_dense') else []),
                         'snippet': row.get('best_chunk_text', '')[:240],
                         'verification': {'exists': True, 'readable': True, 'in_scope': True}})
        if version != self.scopes.version:
            raise ValueError('scope_revoked')
        diagnostics = {'runtime': 'frozen' if getattr(sys, 'frozen', False) else 'source',
            'elapsed_ms': round((time.monotonic()-started)*1000),
            'transport': 'scoped-mdfind-bounded-retry-v3'}
        logger.info('spotlight_search_finished runtime=%s elapsed_ms=%s roots=%s completed=%s hits=%s',
            diagnostics['runtime'], diagnostics['elapsed_ms'], len(roots), completed_roots, len(hits))
        return {'status': 'partial' if failures or semantic_state in ('failed', 'not_indexed') else 'complete',
                'query': query, 'hits': hits, 'hit_count': len(hits), 'scope_version': version,
                'effective_filters': {'extensions': list(extensions), 'date_field': date_field,
                                      'from_timestamp': lower, 'to_timestamp': upper},
                'interpretation': list(plan.interpretation_chips),
                'coverage': {'roots': len(roots), 'completed_roots': completed_roots,
                             'failed_roots': len(roots)-completed_roots, 'semantic': semantic_state,
                             'exhaustive': False, 'candidate_cap_reached': len(paths) >= 500},
                'provider_errors': failures, 'diagnostics': diagnostics}
