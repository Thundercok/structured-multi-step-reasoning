"""Software contracts on synthetic inputs; no live UI/model acceptance claims."""
import json
import subprocess
import sys

import pytest

from rat.engine.reading_session import load_natal_profile, parse_cards


def test_reading_projection_import_does_not_initialize_qt():
    probe = '''
import importlib.abc
import sys
class NoQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('PyQt6'):
            raise AssertionError('presentation import initialized Qt')
sys.meta_path.insert(0, NoQt())
from rat.ui.reading_presentation import reading_profile_view
assert callable(reading_profile_view)
assert 'rat.ui.quick_pdf_controller' not in sys.modules
assert 'rat.ui.quick_app' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', probe], capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_jumper_does_not_shift_position_and_reversed_is_preserved():
    cards = parse_cards('rơi: 9 pent; 4 wands rev, 5 cups, queen cups ngược')
    assert [c['position'] for c in cards] == [0, 1, 2, 3]
    assert [c['reversed'] for c in cards] == [False, True, False, True]
    assert cards[0]['jumper'] and cards[-1]['title'] == 'Queen of Cups'
    assert parse_cards('The World')[0]['suit'] == 'Major'


def test_invalid_or_duplicate_entries_are_not_silently_dropped():
    for text in ('4 pent, unknown', '4 pent, 4 pent rev', ','.join(['world'] * 13)):
        with pytest.raises(ValueError):
            parse_cards(text)
    assert parse_cards('') == []


def test_profile_recalculates_and_ignores_injected_positions(tmp_path):
    pytest.importorskip('swisseph')
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps({'schema': 'rat-natal-v1', 'birth': {
        'name': 'Software test', 'date': '2000-06-15', 'time': '09:30', 'place': 'Test reference',
        'latitude': 10.8231, 'longitude': 106.6297, 'timezone': 'Asia/Ho_Chi_Minh',
    }, 'positions': [{'name': 'invented', 'longitude': 0}]}))
    result = load_natal_profile(path)
    assert result['name'] == 'Software test'
    assert len(result['positions']) == 5 and 'invented' not in str(result['positions'])
    assert result['chart']['positions']
    from rat.ui.reading_presentation import reading_profile_view
    assert reading_profile_view(result)['wheel'].startswith('data:image/svg+xml;')


def test_profile_rejects_unsupported_large_and_missing_files(tmp_path):
    path = tmp_path / 'profile.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='rat-natal-v1'):
        load_natal_profile(path)
    path.write_text(' ' * 20_001)
    with pytest.raises(ValueError, match='20 KB'):
        load_natal_profile(path)
    with pytest.raises(ValueError):
        load_natal_profile(tmp_path / 'missing.json')


def test_reading_tools_share_dispatch_contract_and_reject_unselected_profiles(tmp_path):
    from rat.kernel.capabilities.reading import create_reading_capability
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.dispatcher import ActionDispatcher
    from rat.kernel.registry import CapabilityRegistry
    registry = CapabilityRegistry()
    registry.register_capability(create_reading_capability())
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)
    assert {t.name for t in registry.to_tool_definitions()} == {'prepare_reading_spread', 'load_reading_profile', 'synthesize_reading_draft'}
    result = dispatcher.execute_operation('prepare_reading_spread', {'text': '4 pent, world rev'})
    assert result.status == 'success' and result.artifact.kind == 'reading_spread'
    assert result.artifact.payload['cards'][1]['reversed']
    assert any(e.operation_name == 'prepare_reading_spread' and e.type == 'operation_completed'
               for e in dispatcher.state.events)
    failed = dispatcher.execute_operation('load_reading_profile', {'file_path': str(tmp_path / 'unselected.json')})
    assert failed.status == 'error' and 'chọn' in failed.error
    assert store.get(result.artifact.id) is not None


@pytest.mark.parametrize('query', ['công việc', 'mối quan hệ'])
def test_unavailable_synthesis_returns_error_without_draft(query):
    from rat.kernel.capabilities.reading import create_reading_capability
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.dispatcher import ActionDispatcher
    from rat.kernel.registry import CapabilityRegistry
    from rat.engine.reading_session import parse_cards
    registry = CapabilityRegistry()
    registry.register_capability(create_reading_capability())
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    cards = parse_cards('4 pent, 8 cups rev')
    res = dispatcher.execute_operation('synthesize_reading_draft', {
        'query': query,
    }, context={'reading_cards': cards})
    assert res.status == 'error' and 'model_unavailable' in res.error
    assert res.artifact is None


def test_quick_pdf_controller_reading_draft_flow(tmp_path):
    from rat.ui.quick_pdf_controller import QuickPDFController
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        controller.openReadingDesk()
        assert controller.snapshot['view'] == 'reading'
        assert controller.setReadingCards('roi: 9 pent; 4 wands rev, 5 cups, queen cups rev')
        assert not controller.synthesizeReadingDraft('câu hỏi kết nối')
        snap = controller.snapshot['readingSession']
        assert not snap['draft'] and not snap['cotSteps']
        assert 'model_unavailable' in snap['error']
        assert not controller.saveReadingDraft('Không có draft để lưu.')
    finally:
        controller.close()
