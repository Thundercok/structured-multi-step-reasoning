"""Finder contracts on synthetic app/index fixtures; no Qt, model or live launch."""
from pathlib import Path
import plistlib
import shutil
import threading

import pytest

from rat.crawler.db import Database
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator, SearchFilters, SearchRequest


def app_bundle(root, name, bundle_id='com.example.league', *, executable=True):
    path = root / (name + '.app')
    (path / 'Contents' / 'MacOS').mkdir(parents=True)
    (path / 'Contents' / 'Info.plist').write_bytes(plistlib.dumps(dict(
        CFBundleIdentifier=bundle_id, CFBundleName=name, CFBundleExecutable='fixture-bin')))
    if executable:
        (path / 'Contents' / 'MacOS' / 'fixture-bin').write_text('synthetic, never executed')
    return path


@pytest.fixture
def finder(tmp_path):
    app = app_bundle(tmp_path / 'Apps', 'League of Legends')
    catalog = ApplicationCatalog.scan([app.parent])
    db = Database(str(tmp_path / 'fixture.db'))

    def add(name, content='', *, modified=10, exists=True):
        path = tmp_path / name
        if exists:
            path.write_text(content)
        db.upsert_document(dict(file_path=str(path), file_name=name, file_ext=path.suffix,
            file_size=len(content), created_at=1, modified_at=modified, indexed_at=1,
            content_text=content, summary='Synthetic index summary'))
        return path

    first = add('Liên Minh ghi chú.txt', 'workshop TCP deadline', modified=20)
    second = add('Second.pdf', 'workshop TCP deadline', modified=30)
    stale = add('gone.txt', 'workshop TCP deadline', exists=False)
    engine = ProgressiveSearch(db.db_path, catalog=catalog)
    try:
        yield engine, add, first, second, app
    finally:
        engine.close_connection()
        db.get_connection().close()


def test_verified_app_aliases_separate_installations_and_missing_targets(tmp_path):
    a = app_bundle(tmp_path / 'A', 'League of Legends')
    b = app_bundle(tmp_path / 'B', 'League of Legends')
    app_bundle(tmp_path / 'A', 'Riot Client', 'com.example.riot')
    app_bundle(tmp_path / 'A', 'Broken', executable=False)
    catalog = ApplicationCatalog.scan([a.parent, b.parent])
    for query in ('Liên Minh Huyền Thoại', 'lien minh', 'LoL', 'league of leg'):
        hits = catalog.search(query)
        assert {h.path for h in hits} == {str(a.resolve()), str(b.resolve())}
        assert len({h.resource_id for h in hits}) == 2
        assert all(h.name != 'Riot Client' for h in hits)
    shutil.rmtree(a)
    assert [h.path for h in catalog.search('lol')] == [str(b.resolve())]
    assert 'invalid_application_bundle' in catalog.issues
    assert not catalog.search('nothing installed')


def test_catalog_scan_budget_and_symlink_dedup(tmp_path):
    app = app_bundle(tmp_path, 'Example')
    (tmp_path / 'Alias.app').symlink_to(app, target_is_directory=True)
    catalog = ApplicationCatalog.scan([tmp_path])
    assert len(catalog.applications) == 1
    limited = ApplicationCatalog.scan([tmp_path], max_entries=1)
    assert 'application_catalog_scan_limit' in limited.issues


def test_app_and_file_results_are_real_references_not_read_receipts(finder):
    engine, _, first, _, app = finder
    snapshot = engine.initial(SearchRequest(1, 'Liên Minh'))
    assert snapshot.complete and snapshot.phase == 'lexical'
    assert snapshot.hits[0].kind == 'application' and snapshot.hits[0].path == str(app.resolve())
    assert any(h.path == str(first) for h in snapshot.hits)
    assert all(not h.read for h in snapshot.hits)
    assert len({h.resource_id for h in snapshot.hits}) == len(snapshot.hits)


def test_fts_filters_and_small_projection_without_reading_file_contents(finder, monkeypatch):
    engine, _, first, second, _ = finder
    monkeypatch.setattr(Path, 'read_text', lambda *a, **k: pytest.fail('Search must not extract files'))
    result = engine.initial(SearchRequest(1, 'workshop TCP', filters=SearchFilters(extensions=('.pdf',), date_min=25)))
    assert [h.path for h in result.hits] == [str(second)]
    result = engine.initial(SearchRequest(2, 'workshop TCP', filters=SearchFilters(excluded_extensions=('.pdf',))))
    assert [h.path for h in result.hits] == [str(first)]
    rows = engine.db.search_metadata('workshop TCP')
    assert rows and all('content_text' not in row and 'normalized_text' not in row for row in rows)
    assert all(len(row['summary']) <= 200 for row in rows)
    assert not engine.initial(SearchRequest(3, '%"')).hits


def test_initial_result_precedes_semantic_and_augmentation_preserves_selection(finder):
    engine, add, first, second, _ = finder
    selected = engine.initial(SearchRequest(1, 'Liên Minh')).hits[0].resource_id
    unindexed = Path(first).with_name('unindexed.txt')
    unindexed.write_text('outside index')
    called = []
    def semantic(request):
        called.append(request.query)
        return [first, second, unindexed, second]
    engine.semantic = semantic
    request = SearchRequest(2, 'Liên Minh', selected_id=selected)
    snapshots = engine.snapshots(request)
    initial = next(snapshots)
    assert not called and not initial.complete
    final = next(snapshots)
    assert called == ['Liên Minh'] and final.complete
    assert final.hits[:len(initial.hits)] == initial.hits
    assert final.selected_id == initial.selected_id == selected
    assert len({h.resource_id for h in final.hits}) == len(final.hits)
    assert not any(h.path == str(unindexed) for h in final.hits)


def test_semantic_failure_preserves_lexical_results_and_read_filters(finder):
    engine, _, first, second, _ = finder
    def unavailable(request):
        raise RuntimeError('private provider details')
    engine.semantic = unavailable
    initial, final = list(engine.snapshots(SearchRequest(1, 'workshop')))
    assert final.hits == initial.hits and final.errors == ('semantic_unavailable',)
    engine.semantic = lambda request: [first, second]
    request = SearchRequest(2, 'unmatched', filters=SearchFilters(extensions=('.pdf',)))
    final = list(engine.snapshots(request))[-1]
    assert [h.path for h in final.hits] == [str(second)]


def test_missing_index_keeps_valid_app_results(finder, tmp_path):
    existing, _, _, _, _ = finder
    engine = ProgressiveSearch(tmp_path / 'missing.db', catalog=existing.catalog)
    try:
        result = engine.initial(SearchRequest(1, 'lol'))
        assert result.errors == ('file_index_unavailable',)
        assert result.hits and result.hits[0].kind == 'application'
        assert not (tmp_path / 'missing.db').exists()
    finally:
        engine.close_connection()


def test_new_fast_query_is_not_blocked_by_old_semantic_and_stale_results_are_dropped(finder):
    engine, _, first, second, _ = finder
    entered, release, fresh = (threading.Event() for _ in range(3))
    updates = []
    def semantic(request):
        if request.query == 'old':
            entered.set()
            assert release.wait(3)
        return [second]
    engine.semantic = semantic
    def updated(snapshot):
        updates.append(snapshot)
        if snapshot.query == 'Liên Minh' and snapshot.phase == 'lexical':
            fresh.set()
    coordinator = SearchCoordinator(engine, updated)
    try:
        old_id = coordinator.submit('old')
        assert entered.wait(2)
        for i in range(50):
            coordinator.submit('intermediate ' + str(i))
        new_id = coordinator.submit('Liên Minh')
        assert fresh.wait(2), 'New lexical result must arrive while old semantics remain blocked'
        assert not coordinator.is_current(old_id) and coordinator.is_current(new_id)
        release.set()
    finally:
        release.set()
        assert coordinator.close()
    assert not any(s.query_id == old_id and s.phase == 'semantic' for s in updates)
    assert any(s.query_id == new_id and any(h.path == str(first) for h in s.hits) for s in updates)
    with pytest.raises(RuntimeError, match='closed'):
        coordinator.submit('after close')


def test_cancelled_request_and_worker_callback_error_do_not_break_next_query(finder):
    engine, _, _, _, _ = finder
    request = SearchRequest(1, 'lol')
    request.cancelled.set()
    with pytest.raises(InterruptedError):
        engine.initial(request)
    failed, completed = threading.Event(), threading.Event()
    def callback(snapshot):
        if snapshot.query == 'bad callback':
            failed.set()
            raise ValueError('consumer failure')
        completed.set()
    coordinator = SearchCoordinator(engine, callback)
    try:
        coordinator.submit('bad callback')
        assert failed.wait(2)
        coordinator.cancel()
        coordinator.submit('lol')
        assert completed.wait(2)
    finally:
        assert coordinator.close()


def test_pending_fast_jobs_are_coalesced_to_latest_request(finder):
    engine, _, _, _, _ = finder
    entered, release, completed = (threading.Event() for _ in range(3))
    calls = []
    original = engine.initial
    def slow_first(request):
        calls.append(request.query)
        if request.query == 'hold':
            entered.set()
            assert release.wait(3)
        return original(request)
    engine.initial = slow_first
    coordinator = SearchCoordinator(engine, lambda snapshot: completed.set())
    try:
        coordinator.submit('hold')
        assert entered.wait(2)
        for i in range(100):
            coordinator.submit('discard ' + str(i))
        coordinator.submit('final')
        release.set()
        assert completed.wait(2)
    finally:
        release.set()
        assert coordinator.close()
    assert calls == ['hold', 'final']


def test_full_list_skips_unused_semantics_and_filters_are_case_consistent(finder):
    engine, _, _, second, _ = finder
    engine.semantic = lambda request: pytest.fail('No semantic call when the bounded list is full')
    snapshots = list(engine.snapshots(SearchRequest(1, 'workshop', limit=1,
        filters=SearchFilters(extensions=('.PDF',)))))
    assert len(snapshots) == 1 and snapshots[0].complete
    assert snapshots[0].hits[0].path == str(second)


def test_search_needs_no_inference_gui_numpy_network_or_subprocess(finder):
    import json
    import os
    import subprocess
    import sys
    engine, _, _, _, app = finder
    program = r'''
import importlib.abc, json, sys
blocked = ('numpy', 'PyQt6', 'rat.ui', 'mlx', 'mlx_lm', 'torch', 'onnxruntime',
           'fastembed', 'rat.engine.embedder', 'rat.engine.slm', 'rat.engine.hybrid_search')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name+'.') for name in blocked):
            raise AssertionError('Heavy import on initial finder path: '+fullname)
sys.meta_path.insert(0, Guard())
def guard(event, args):
    if event in ('socket.connect', 'subprocess.Popen'):
        raise AssertionError('Finder attempted '+event)
sys.addaudithook(guard)
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import ProgressiveSearch, SearchRequest
catalog = ApplicationCatalog.scan([sys.argv[2]])
engine = ProgressiveSearch(sys.argv[1], catalog=catalog)
try:
    snap = engine.initial(SearchRequest(1, 'Liên Minh'))
    assert any(h.kind == 'application' for h in snap.hits)
    assert any(h.kind == 'file' for h in snap.hits)
    assert not any(n == p or n.startswith(p+'.') for n in sys.modules for p in blocked)
    print(json.dumps({'hits': len(snap.hits), 'errors': snap.errors}))
finally:
    engine.close_connection()
'''
    result = subprocess.run([sys.executable, '-c', program, engine.db.db_path, str(app.parent)],
        capture_output=True, text=True, timeout=15, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['errors'] == []


def test_busy_database_does_not_hold_up_app_results_for_default_sixty_seconds(finder, tmp_path):
    import time
    existing, _, _, _, _ = finder
    database = Database(str(tmp_path / 'locked.db'))
    writer = database.get_connection()
    engine = ProgressiveSearch(database.db_path, catalog=existing.catalog)
    try:
        writer.execute('PRAGMA journal_mode=DELETE')
        writer.execute('BEGIN EXCLUSIVE')
        tick = time.perf_counter()
        snapshot = engine.initial(SearchRequest(1, 'lol'))
        assert time.perf_counter() - tick < 1
        assert snapshot.errors == ('file_index_unavailable',)
        assert snapshot.hits and snapshot.hits[0].kind == 'application'
    finally:
        engine.close_connection()
        writer.rollback()
        writer.close()
