"""Reproducible synthetic-index timing + read-only installed-app catalog smoke.

No personal file index, GUI, model, embedding, network or application launch.
Timings are backend API time; discovery, fixture creation and imports are separate.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.abc
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BLOCKED = ('numpy', 'PyQt6', 'rat.ui', 'mlx', 'mlx_lm', 'torch', 'onnxruntime',
           'fastembed', 'rat.engine.embedder', 'rat.engine.slm', 'rat.engine.hybrid_search')


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in BLOCKED):
            raise AssertionError('Heavy dependency on fast finder path: ' + fullname)


network_attempts = 0


def audit(event, args):
    global network_attempts
    if event == 'socket.connect':
        network_attempts += 1
        raise AssertionError('Network forbidden')
    if event == 'subprocess.Popen':
        raise AssertionError('No application/process launch in finder acceptance')


def main():
    sys.meta_path.insert(0, Guard())
    sys.addaudithook(audit)
    started = time.perf_counter()
    from rat.crawler.db import Database, remove_vietnamese_accents
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.progressive_search import ProgressiveSearch, SearchRequest
    result = dict(started_utc=datetime.now(timezone.utc).isoformat(),
        scope='Backend API on 5,000 authored synthetic files; not UI latency, research data or general performance.',
        python=platform.python_version(), platform=sys.platform + ' ' + platform.release() + ' ' + platform.machine(),
        import_s=time.perf_counter() - started, cases=[], raw=[])
    files = ['rat/crawler/db.py', 'rat/crawler/__init__.py', 'rat/engine/__init__.py',
             'rat/engine/app_resolver.py', 'rat/engine/progressive_search.py',
             'tests/test_progressive_search.py']
    result['source_hashes'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
    tick = time.perf_counter()
    catalog = ApplicationCatalog.scan()
    result['native_catalog'] = dict(scan_s=time.perf_counter() - tick,
        applications=len(catalog.applications), issues=catalog.issues)
    # Persist only public system-app metadata, not an inventory of user applications.
    safari = catalog.search('Safari')
    result['native_catalog']['safari_matches'] = len(safari)
    result['native_catalog']['stable_ids_distinct'] = len({a.resource_id for a in catalog.applications}) == len(catalog.applications)

    with tempfile.TemporaryDirectory(prefix='rat-finder-fixtures-') as temporary:
        folder = Path(temporary)
        db = Database(str(folder / 'fixture.db'))
        conn = db.get_connection()
        tick = time.perf_counter()
        def rows():
            for i in range(5000):
                name = f'Workshop-{i:04d}.txt'
                path = folder / name
                text = f'SYNTHETIC FIXTURE. Workshop confirmation CODE{i:04d}. Campus seminar notes.'
                path.write_text(text)
                yield (str(path), name, '.txt', len(text), 1, float(i + 1), 1, text,
                       remove_vietnamese_accents(name + ' ' + text), 'Synthetic fixture summary')
        conn.executemany('''INSERT INTO documents
            (file_path,file_name,file_ext,file_size,created_at,modified_at,indexed_at,content_text,normalized_text,summary)
            VALUES (?,?,?,?,?,?,?,?,?,?)''', rows())
        conn.commit()
        result['fixture_creation_s'] = time.perf_counter() - tick
        engine = ProgressiveSearch(db.db_path, catalog=catalog)
        queries = [('exact_name', 'Workshop-0042.txt', 'Workshop-0042.txt'),
                   ('indexed_content', 'CODE0731', 'Workshop-0731.txt'),
                   ('broad_term', 'workshop', None), ('no_match', 'absentzyxq', None)]
        qid = 0
        try:
            for name, query, expected in queries:
                times = []
                for repetition in range(31):
                    qid += 1
                    tick = time.perf_counter()
                    snapshot = engine.initial(SearchRequest(qid, query))
                    elapsed = (time.perf_counter() - tick) * 1000
                    times.append(elapsed)
                    if expected:
                        assert any(h.title == expected for h in snapshot.hits)
                    if name == 'no_match':
                        assert not snapshot.hits
                    assert snapshot.complete and not snapshot.errors
                    assert all(not h.read for h in snapshot.hits)
                    result['raw'].append(dict(case=name, repetition=repetition, wall_ms=elapsed,
                                              result_count=len(snapshot.hits)))
                warm = sorted(times[1:])
                result['cases'].append(dict(name=name, query=query, first_call_ms=times[0],
                    warm_repetitions=len(warm), warm_p50_ms=statistics.median(warm),
                    warm_p95_ms=warm[int(0.95 * (len(warm) - 1))], warm_max_ms=max(warm)))
                print(json.dumps(result['cases'][-1]), flush=True)
        finally:
            engine.close_connection()
            conn.close()
    result.update(status='completed', fixture_directory_removed=True, network_attempts=network_attempts,
        blocked_dependencies_imported=[n for n in sys.modules for p in BLOCKED if n == p or n.startswith(p + '.')],
        source_changed=[p for p, h in result['source_hashes'].items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h])
    assert not result['blocked_dependencies_imported'] and not network_attempts and not result['source_changed']
    (OUT / 'probe.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: result[k] for k in ('status', 'import_s', 'native_catalog', 'fixture_creation_s', 'network_attempts')}))


if __name__ == '__main__':
    main()
