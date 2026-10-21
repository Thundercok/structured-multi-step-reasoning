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


def test_natural_finder_slide_dsa_last_week_rule_and_timezone_window(tmp_path):
    from datetime import datetime, timedelta, timezone

    tz = timezone(timedelta(hours=7))
    # Saturday 2026-10-17 14:00+07:00 -> this Monday is 2026-10-12 00:00,
    # previous calendar week is [2026-10-05 00:00, 2026-10-12 00:00).
    fixed_now = datetime(2026, 10, 17, 14, 0, tzinfo=tz)
    db = Database(str(tmp_path / 'slides.db'))

    def add_doc(rel_path, content, summary, dt):
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        ts = dt.timestamp()
        db.upsert_document(dict(
            file_path=str(full),
            file_name=full.name,
            file_ext=full.suffix,
            file_size=len(content),
            created_at=ts,
            modified_at=ts,
            indexed_at=ts,
            content_text=content,
            summary=summary,
        ))
        return full

    slide_pptx = add_doc(
        'courses/DSA_Chapter3_Trees.pptx',
        'DSA binary search tree AVL rotations',
        'Slide bài giảng cấu trúc dữ liệu chương 3',
        datetime(2026, 10, 7, 10, 0, tzinfo=tz),
    )
    slide_pdf = add_doc(
        'lectures/DSA_Lecture04_Graph_Slide.pdf',
        'DSA shortest path Dijkstra',
        'Lecture deck for graph algorithms',
        datetime(2026, 10, 9, 15, 30, tzinfo=tz),
    )
    # Arbitrary non-slide PDF mentioning DSA modified last week -> must be excluded by Slide rule
    non_slide_pdf = add_doc(
        'books/DSA_Reference_Manual.pdf',
        'DSA reference manual and syllabus overview',
        'Reference textbook chapter on data structures',
        datetime(2026, 10, 9, 16, 0, tzinfo=tz),
    )
    # Slide modified THIS week -> must be excluded by "tuần trước"
    this_week_pptx = add_doc(
        'courses/DSA_Chapter5_Hashing.pptx',
        'DSA hash tables open addressing',
        'Slide bài giảng chương 5',
        datetime(2026, 10, 14, 9, 0, tzinfo=tz),
    )
    # Slide modified TWO weeks ago -> must be excluded by "tuần trước"
    two_weeks_ago_pptx = add_doc(
        'courses/DSA_Chapter1_Intro.pptx',
        'DSA complexity big-O',
        'Slide mở đầu',
        datetime(2026, 10, 1, 9, 0, tzinfo=tz),
    )

    engine = ProgressiveSearch(
        db.db_path,
        catalog=ApplicationCatalog(()),
        now_fn=lambda: fixed_now,
    )
    try:
        snap = engine.initial(SearchRequest(1, 'Slide DSA sửa tuần trước'))
        assert snap.intent is not None
        assert snap.intent.slide_rule is True
        assert snap.intent.core_query.lower() == 'dsa'
        assert snap.intent.date_min == datetime(2026, 10, 5, 0, 0, tzinfo=tz).timestamp()
        assert snap.intent.date_max_exclusive == datetime(2026, 10, 12, 0, 0, tzinfo=tz).timestamp()
        assert any('Slide' in chip for chip in snap.intent.applied_filters)
        assert any('tuần trước' in chip.lower() for chip in snap.intent.applied_filters)

        hit_paths = {h.path for h in snap.hits}
        assert hit_paths == {str(slide_pptx), str(slide_pdf)}
        assert str(non_slide_pdf) not in hit_paths
        assert str(this_week_pptx) not in hit_paths
        assert str(two_weeks_ago_pptx) not in hit_paths
    finally:
        engine.close_connection()
        db.get_connection().close()


def test_natural_finder_latest_report_orders_by_modified_desc_before_limit(tmp_path):
    db = Database(str(tmp_path / 'reports.db'))
    report_paths = []
    # Insert 22 reports with increasing modified_at so pre-LIMIT ordering is tested
    for idx in range(1, 23):
        name = f'bao_cao_tien_do_{idx:02d}.docx' if idx % 2 == 0 else f'project_report_{idx:02d}.pdf'
        p = tmp_path / name
        content = f'Nội dung báo cáo tiến độ tuần {idx}'
        p.write_text(content)
        mod_ts = float(1000 + idx * 100)
        db.upsert_document(dict(
            file_path=str(p),
            file_name=name,
            file_ext=p.suffix,
            file_size=len(content),
            created_at=100.0,
            modified_at=mod_ts,
            indexed_at=mod_ts,
            content_text=content,
            summary=f'Báo cáo tổng kết tuần {idx}',
        ))
        report_paths.append((mod_ts, str(p)))

    # Non-report file with an even newer timestamp must not appear as a report
    unrelated = tmp_path / 'ghi_chu_nhap.txt'
    unrelated.write_text('ghi chú cá nhân hôm nay')
    db.upsert_document(dict(
        file_path=str(unrelated),
        file_name=unrelated.name,
        file_ext='.txt',
        file_size=20,
        created_at=100.0,
        modified_at=99999.0,
        indexed_at=99999.0,
        content_text='ghi chú cá nhân hôm nay',
        summary='Ghi chú nhanh',
    ))

    engine = ProgressiveSearch(db.db_path, catalog=ApplicationCatalog(()))
    try:
        snap = engine.initial(SearchRequest(1, 'bản báo cáo mới nhất', limit=5))
        assert snap.intent is not None
        assert snap.intent.report_rule is True
        assert snap.intent.sort == 'modified_desc'
        assert 'chỉ mục' in snap.intent.scope_note

        expected_top5 = [path for _, path in sorted(report_paths, reverse=True)[:5]]
        assert [h.path for h in snap.hits] == expected_top5
        assert [h.modified_at for h in snap.hits] == sorted([h.modified_at for h in snap.hits], reverse=True)
    finally:
        engine.close_connection()
        db.get_connection().close()


def test_natural_finder_ambiguity_negation_and_conflict_handling(tmp_path):
    a = app_bundle(tmp_path / 'AppsA', 'League of Legends', 'com.riotgames.leagueoflegends')
    b = app_bundle(tmp_path / 'AppsB', 'League of Legends', 'com.riotgames.leagueoflegends')
    catalog = ApplicationCatalog.scan([a.parent, b.parent])
    db = Database(str(tmp_path / 'intent.db'))
    engine = ProgressiveSearch(db.db_path, catalog=catalog)
    try:
        # 1. Missing target on bare "mở"
        bare = engine.initial(SearchRequest(1, 'mở'))
        assert bare.intent is not None
        assert bare.intent.action == 'open_app'
        assert bare.intent.needs_clarification is True
        assert bare.hits == ()
        assert 'ứng dụng nào' in bare.intent.clarification_prompt

        # 2. Negated open ("đừng mở Liên Minh", "không mở Liên Minh")
        for neg_q in ('đừng mở Liên Minh', 'không mở Liên Minh'):
            neg = engine.initial(SearchRequest(2, neg_q))
            assert neg.intent is not None
            assert neg.intent.action == 'negated_open'
            assert neg.hits == ()
            assert 'không mở' in neg.intent.clarification_prompt.lower()

        # 3. Conflicting time constraints ("slide DSA hôm nay tuần trước")
        conflict = engine.initial(SearchRequest(3, 'slide DSA hôm nay tuần trước'))
        assert conflict.intent is not None
        assert conflict.intent.needs_clarification is True
        assert len(conflict.intent.conflicting_constraints) >= 2
        assert conflict.hits == ()

        # 4. Multiple installations of League of Legends on "mở Liên Minh"
        multi = engine.initial(SearchRequest(4, 'mở Liên Minh'))
        assert multi.intent is not None
        assert multi.intent.action == 'open_app'
        assert multi.intent.needs_clarification is True
        assert {h.path for h in multi.hits} == {str(a.resolve()), str(b.resolve())}
    finally:
        engine.close_connection()
        db.get_connection().close()


def test_open_application_capability_revalidation_disambiguation_and_honest_status(tmp_path, monkeypatch):
    import sys
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.capabilities import build_default_registry
    from rat.kernel.dispatcher import ActionDispatcher

    monkeypatch.setattr(sys, 'platform', 'darwin')

    lol_a = app_bundle(tmp_path / 'A', 'League of Legends', 'com.riotgames.leagueoflegends')
    riot = app_bundle(tmp_path / 'A', 'Riot Client', 'com.riotgames.RiotClient')
    catalog_single = ApplicationCatalog.scan([lol_a.parent])

    launched = []
    def fake_launcher(app):
        launched.append((app.name, app.path, app.bundle_id))
        return True, None

    registry = build_default_registry()
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    # 1. Single verified bundle launch ("mở Liên Minh") -> never launches Riot Client
    res = dispatcher.execute_operation(
        'open_application',
        {'query': 'mở Liên Minh'},
        context={'catalog': catalog_single, 'app_launcher': fake_launcher},
    )
    assert res.status == 'success'
    assert res.artifact is not None
    assert res.artifact.kind == 'application_launch'
    assert launched == [('League of Legends', str(lol_a.resolve()), 'com.riotgames.leagueoflegends')]
    assert res.artifact.payload['os_launch_accepted'] is True
    assert res.artifact.payload['in_game_verified'] is False
    assert 'không đồng nghĩa' in res.artifact.payload['status_note']

    # 2. Multiple installations -> needs_input with candidate metadata, then resume_input launches selected
    launched.clear()
    lol_b = app_bundle(tmp_path / 'B', 'League of Legends', 'com.riotgames.leagueoflegends')
    catalog_multi = ApplicationCatalog.scan([lol_a.parent, lol_b.parent])

    ambig = dispatcher.execute_operation(
        'open_application',
        {'query': 'mở Liên Minh'},
        context={'catalog': catalog_multi, 'app_launcher': fake_launcher},
    )
    assert ambig.status == 'needs_input'
    assert ambig.input_request is not None
    assert not launched
    choices = ambig.input_request.candidate_choices
    assert len(choices) == 2
    assert {c['path'] for c in choices} == {str(lol_a.resolve()), str(lol_b.resolve())}
    assert all(c.get('bundle_id') == 'com.riotgames.leagueoflegends' for c in choices)

    chosen_idx = next(i for i, c in enumerate(choices) if c['path'] == str(lol_b.resolve()))
    resumed = dispatcher.resume_input(
        ambig.input_request.id,
        {'selected_candidate': chosen_idx},
        context={'catalog': catalog_multi, 'app_launcher': fake_launcher},
    )
    assert resumed.status == 'success'
    assert launched == [('League of Legends', str(lol_b.resolve()), 'com.riotgames.leagueoflegends')]

    # 3. Deleted executable after scan -> revalidation fails at launch time
    launched.clear()
    shutil.rmtree(lol_a / 'Contents' / 'MacOS')
    broken = dispatcher.execute_operation(
        'open_application',
        {'query': 'League of Legends', 'path': str(lol_a.resolve())},
        context={'catalog': catalog_single, 'app_launcher': fake_launcher},
    )
    assert broken.status == 'error'
    assert not launched

    # 4. Non-macOS platform refusal
    monkeypatch.setattr(sys, 'platform', 'linux')
    non_mac = dispatcher.execute_operation(
        'open_application',
        {'query': 'mở Liên Minh'},
        context={'catalog': catalog_multi, 'app_launcher': fake_launcher},
    )
    assert non_mac.status == 'error'
    assert 'macOS' in (non_mac.error or '')
    assert not launched

