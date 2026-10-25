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


def test_connected_model_synthesizes_reading_draft_and_scoped_verifier(tmp_path):
    from rat.kernel.capabilities.reading import create_reading_capability
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.dispatcher import ActionDispatcher
    from rat.kernel.registry import CapabilityRegistry
    from rat.engine.reading_session import parse_cards
    from rat.engine.verification import ExecutionEvidence, ReadingVerifier, VerificationStatus

    dispatched_messages = []

    class StubModel:
        def chat_with_meta(self, messages, tools, **kwargs):
            dispatched_messages.append(messages)
            return {
                "message": {
                    "content": "Bản luận: 4 Pentacles nhắc nhở về sự vững vàng tài chính, trong khi The World ngược cảnh báo về sự trì hoãn."
                },
                "prompt_tokens": 120,
                "completion_tokens": 40,
            }

    registry = CapabilityRegistry()
    registry.register_capability(create_reading_capability())
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    cards = parse_cards("4 pent, world rev")
    chart = {
        "positions": [
            {"name": "Mặt Trời", "position": "15° Bọ Cạp"},
            {"name": "Mặt Trăng", "position": "22° Kim Ngưu"},
        ]
    }
    stub = StubModel()

    res = dispatcher.execute_operation(
        "synthesize_reading_draft",
        {"query": "Định hướng tháng tới"},
        context={"reading_cards": cards, "reading_chart": chart, "model_client": stub},
    )
    assert res.status == "success"
    assert res.artifact is not None
    payload = res.artifact.payload
    assert "4 Pentacles" in payload["draft_markdown"]
    assert payload["verification_status"] == "UNKNOWN"
    assert payload["user_edited"] is False
    assert len(dispatched_messages) == 1
    prompt_text = dispatched_messages[0][1]["content"]
    assert "4 of Pentacles" in prompt_text
    assert "World" in prompt_text
    assert "15° Bọ Cạp" in prompt_text

    # Scoped verification checks
    verifier = ReadingVerifier()
    rep = verifier.check_execution(ExecutionEvidence(
        id="test-synth-ev",
        operation="synthesize_reading_draft",
        args={"query": "Định hướng"},
        result=payload,
        sha256="",
    ))
    assert rep.status == VerificationStatus.UNKNOWN
    assert "chưa xác minh" in rep.reason

    # Prepare spread verification
    rep_spread = verifier.check_execution(ExecutionEvidence(
        id="test-spread-ev",
        operation="prepare_reading_spread",
        args={"text": "4 pent, world rev"},
        result={"cards": cards},
        sha256="",
    ))
    assert rep_spread.status == VerificationStatus.PASS

    # Negative probe: duplicate cards in spread must FAIL
    rep_fail = verifier.check_execution(ExecutionEvidence(
        id="test-fail-ev",
        operation="prepare_reading_spread",
        args={"text": "4 pent, 4 pent"},
        result={"cards": [cards[0], cards[0]]},
        sha256="",
    ))
    assert rep_fail.status == VerificationStatus.FAIL


def test_adaptive_consensus_stopping_in_reading_verifier_and_runtime():
    """Verify Hướng 3: Adaptive Stopping & Consensus Verification logic in RAT agentic loop."""
    from rat.engine.verification import (
        ReadingVerifier,
        VerificationStatus,
        evaluate_consensus_stopping,
    )

    # 1. Direct mathematical verification of consensus stopping
    # Case A: Strong consensus reached early (A=3, B=0)
    v_early = evaluate_consensus_stopping(["A", "A", "A"], threshold=0.85, margin=2)
    assert v_early.stop_early is True
    assert v_early.winner == "A"
    assert v_early.margin == 3
    assert v_early.beta_prob > 0.85

    # Case B: Disagreement, cannot stop early (A=2, B=2)
    v_split = evaluate_consensus_stopping(["A", "B", "A", "B"], threshold=0.85, margin=2)
    assert v_split.stop_early is False
    assert v_split.margin == 0

    # 2. ReadingVerifier.check_consensus integration
    verifier = ReadingVerifier()
    rep_pass = verifier.check_consensus(["A", "A", "A"], threshold=0.85, margin=2)
    assert rep_pass.status == VerificationStatus.PASS
    assert "Đạt ngưỡng đồng thuận" in rep_pass.reason
    assert rep_pass.retryable is False

    rep_unknown = verifier.check_consensus(["A", "B"], threshold=0.85, margin=2)
    assert rep_unknown.status == VerificationStatus.UNKNOWN
    assert "Chưa đạt ngưỡng" in rep_unknown.reason
    assert rep_unknown.retryable is True

    # 3. Multi-sample consensus in synthesize_reading_draft
    from rat.kernel.capabilities.reading import create_reading_capability
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.dispatcher import ActionDispatcher
    from rat.kernel.registry import CapabilityRegistry
    from rat.engine.reading_session import parse_cards

    class StubModel:
        def chat_with_meta(self, messages, tools, **kwargs):
            return {
                "message": {"content": "Bản luận tổng hợp: 4 Pentacles biểu trưng cho sự ổn định."},
                "prompt_tokens": 100,
                "completion_tokens": 30,
            }

    registry = CapabilityRegistry()
    registry.register_capability(create_reading_capability())
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    cards = parse_cards("4 pent, world")
    candidates = [
        "Ổn định tài chính vững chắc",
        "Ổn định tài chính vững chắc",
        "Ổn định tài chính vững chắc",
    ]
    res = dispatcher.execute_operation(
        "synthesize_reading_draft",
        {"query": "Tài chính"},
        context={"reading_cards": cards, "model_client": StubModel(), "candidate_drafts": candidates},
    )
    assert res.status == "success"
    payload = res.artifact.payload
    assert payload["verification_status"] == "PASS"
    assert payload["consensus_metadata"]["stop_early"] is True
    assert "Đạt ngưỡng đồng thuận" in payload["consensus_metadata"]["reason"]


def test_quick_pdf_controller_smart_notes_dispatcher_integration(tmp_path):
    """Verify that Reading Desk and QuickPDFController connect to smart_notes operations via Dispatcher."""
    from rat.ui.quick_pdf_controller import QuickPDFController

    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        controller.openReadingDesk()
        assert controller.snapshot["view"] == "reading"

        # 1. Operation 1: synthesize_smart_note via Dispatcher
        raw_text = (
            "mua gì tặng bạn gái tôi vào ngày 20/10. "
            "9 wands, 2 pentacles rev, hierophant rev, the world rev, 10 pentacles rev. "
            "bạn gái đang stress deadline, đau vai gáy nhiều ngày, nhà đang giục cưới. "
            "dị ứng mấy món quà hình thức hoa to sáo rỗng. "
            "tính đi fine dining, làm spa và một night together."
        )
        note_id = controller.synthesizeSmartNote(raw_text, "decision", "Ghi chú Quà Tặng 20/10")
        assert note_id and note_id.startswith("art-")

        # Snapshot projections
        active_note = controller.snapshot["activeNote"]
        assert active_note is not None
        assert active_note["note_id"] == note_id
        assert active_note["revision"] == 1
        assert active_note["title"] == "Ghi chú Quà Tặng 20/10"
        assert len(active_note["action_items"]) >= 1

        reading_note = controller.snapshot["readingSession"]["activeNote"]
        assert reading_note["note_id"] == note_id

        # Canonical store check
        art_store = controller.assistant_runtime.artifact_store
        stored_art = art_store.get(note_id)
        assert stored_art is not None
        assert stored_art.revision == 1

        # 2. Operation 2: update_note_action_item via Dispatcher
        ok_update = controller.updateNoteActionItem(note_id, "spa", True)
        assert ok_update is True

        updated_note = controller.snapshot["activeNote"]
        assert updated_note["revision"] == 2
        spa_item = next(item for item in updated_note["action_items"] if "spa" in item["task"].lower())
        assert spa_item["done"] is True

        # Canonical store revision check
        stored_art_rev2 = art_store.get(note_id)
        assert stored_art_rev2.revision == 2

        # 3. Operation 3: expand_note_section via Dispatcher
        ok_expand = controller.expandNoteSection(
            note_id,
            "Phân tích",
            "Nghiên cứu thêm về bẫy gò bó của Fine Dining",
            "Phân tích bổ sung: Fine dining gây áp lực ngồi giữ kẽ 2 tiếng, không hợp bạn gái đang mệt mỏi.",
        )
        assert ok_expand is True

        expanded_note = controller.snapshot["activeNote"]
        assert expanded_note["revision"] == 3
        assert "fine dining" in expanded_note["markdown_rendered"].lower()
        stored_art_rev3 = art_store.get(note_id)
        assert stored_art_rev3.revision == 3

        # 4. Synthesize note from reading cards / draft
        controller.setReadingCards("4 pent, world rev")
        draft_note_id = controller.synthesizeNoteFromReadingDraft("decision")
        assert draft_note_id and draft_note_id.startswith("art-")
        assert controller.snapshot["activeNote"]["note_id"] == draft_note_id
        assert "world" in controller.snapshot["activeNote"]["markdown_rendered"].lower() or "pentacles" in controller.snapshot["activeNote"]["markdown_rendered"].lower()

    finally:
        controller.close()


