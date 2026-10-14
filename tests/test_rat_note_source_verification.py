"""Source-statement checks reuse registered verifiers without treating notes as user facts."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from rat.engine.assistant_runtime import AssistantRuntime
from rat.timetable.compositor import TimetableCompositor


def calculated():
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)
    runtime.execute_tool('calculate', {'expression': '18 * 7'}, turn_id='turn-1', execution_id='exec-1')
    artifact = runtime.artifact_store.list('calculation')[0]
    runtime.notebook.begin_request('Ghi lại kết quả.', turn_ref='turn-2')
    return runtime, {'artifact_id': artifact.id, 'revision': 1, 'field': 'result'}


def test_source_equation_is_verified_with_real_artifact_evidence():
    runtime, source = calculated()
    note = runtime.execute_tool('record_work_note', {
        'text': '18 * 7 = 126', 'source_result': source,
    })['note']
    assert note['confirmed'] and note['status'] == 'active'
    assert note['quote'] == '126' and note['source_ref']['artifact_id'] == source['artifact_id']
    proof = note['source_verification']
    assert proof['status'] == 'PASS' and proof['scope'] == 'source_calculation_note'
    assert proof['evidence_ids'][0].startswith(f"artifact:{source['artifact_id']}:revision:1:")
    assert runtime.notebook.model_context()[0]['authority'] == 'observed_result'

    runtime.execute_tool('calculate', {'expression': '18 * 9'}, turn_id='turn-3', execution_id='exec-3')
    newer = runtime.artifact_store.list('calculation')[-1]
    runtime.notebook.begin_request('Sửa ghi chú.', turn_ref='turn-3')
    revision2 = runtime.execute_tool('record_work_note', {
        'text': '18 * 9 = 162', 'replace_note_id': note['id'], 'revision': 1,
        'source_result': {'artifact_id': newer.id, 'revision': 1, 'field': 'result'},
    })['note']
    assert revision2['confirmed'] and revision2['revision'] == 2
    assert runtime.notebook.historical_context()[0]['source_verification'] == proof

    # A user's later edit does not inherit the old arithmetic proof.
    changed = runtime.notebook.user_edit(note['id'], 2, 'Giá trị tôi muốn giữ: 999')
    assert 'source_verification' not in changed
    assert runtime.notebook.version_history(note['id'])[0]['source_verification'] == proof
    assert runtime.notebook.model_context()[0]['authority'] == 'user_supplied'


def test_user_acceptance_of_prose_is_not_promoted_to_an_observed_source_fact():
    runtime, source = calculated()
    proposed = runtime.execute_tool('record_work_note', {
        'text': 'Đây là ví dụ để ôn bài', 'source_result': source,
    })['note']
    accepted = runtime.notebook.confirm(proposed['id'], proposed['revision'])
    assert accepted['source'] == 'user_confirmed'
    assert runtime.notebook.model_context()[0]['authority'] == 'user_supplied'
    assert 'source_verification' not in accepted


def test_wrong_source_result_does_not_commit_a_note():
    runtime, source = calculated()
    with pytest.raises(ValueError, match='126'):
        runtime.execute_tool('record_work_note', {'text': '18 * 7 = 999', 'source_result': source})
    assert runtime.notebook.snapshot() == [] and runtime.notebook.events_since(0) == []


@pytest.mark.parametrize('text', ['Kết quả này chứng minh tôi giỏi DSA', '2 + 2 = 4'])
def test_unsupported_prose_or_unrelated_equation_stays_proposed(text):
    runtime, source = calculated()
    note = runtime.execute_tool('record_work_note', {'text': text, 'source_result': source})['note']
    assert not note['confirmed'] and note['status'] == 'proposed'
    assert runtime.notebook.model_context()[0]['authority'] == 'unconfirmed_model_suggestion'


@pytest.mark.parametrize('invalid_return', [False, True])
def test_broken_source_checker_cannot_promote_a_proposal(invalid_return):
    runtime, source = calculated()
    class BrokenChecker:
        def check_note(self, *args):
            if invalid_return:
                return {'status': 'PASS'}
            raise RuntimeError('fixture broken checker')
    runtime.registry.get_operation('calculate').verifier = BrokenChecker()
    note = runtime.execute_tool('record_work_note', {
        'text': '18 * 7 = 126', 'source_result': source,
    })['note']
    assert not note['confirmed'] and note['source_verification']['status'] == 'UNKNOWN'


def test_clock_and_member_do_not_change_the_static_system_prefix():
    runtime, _ = calculated()
    first = runtime._native_messages('Hỏi tiếp', [], now_dt=datetime(2026, 10, 13, 10), member_id='member-a')
    second = runtime._native_messages('Hỏi tiếp', [], now_dt=datetime(2026, 10, 13, 11), member_id='member-b')
    assert first[0] == second[0]
    assert 'member-a' not in first[0]['content'] and '2026-10-13' not in first[0]['content']
    contexts = [message for message in first if message['content'].startswith('Runtime context:')]
    assert len(contexts) == 1 and contexts[0]['role'] == 'system'
    assert '2026-10-13T10:00:00' in contexts[0]['content'] and 'member-a' in contexts[0]['content']
    assert first[-1] == second[-1] == {'role': 'user', 'content': 'Hỏi tiếp'}
