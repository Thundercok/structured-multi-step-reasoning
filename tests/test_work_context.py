"""Work notes/trace contracts; scripted decisions are not model-quality evidence."""
import json
from unittest.mock import MagicMock

import pytest
from rat.engine.assistant_runtime import AgentStep, AssistantRuntime, ModelDecision
from rat.engine.work_notes import WorkNotebook
from rat.engine.work_trace import summarize_step
from rat.timetable.compositor import TimetableCompositor


def test_quotes_have_provenance_and_paraphrases_remain_suggestions():
    notes = WorkNotebook()
    generation = notes.begin_request('Tôi rảnh sau 3 giờ, chỉ ôn TCP.')
    exact = notes.record('chỉ ôn TCP.', 'chỉ ôn TCP.', generation=generation)
    assert exact['confirmed'] and exact['source'] == 'user_quote'
    proposed = notes.record('Không ôn IP routing', 'chỉ ôn TCP.', generation=generation)
    assert not proposed['confirmed']
    assert notes.model_context()[1]['authority'] == 'unconfirmed_model_suggestion'
    with pytest.raises(ValueError):
        notes.record('Đã đọc tài liệu', 'Đã đọc tài liệu', generation=generation)


@pytest.mark.parametrize('completed,expected_error', [([], None), (['Đã ghi chú'], 'task_plan_failed:initial_plan_claimed_execution')])
def test_initial_plan_does_not_write_notes_and_cannot_claim_completed_work(completed, expected_error):
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True,
        plan_tasks=True, model_client=MagicMock())
    state = dict(goal='Ôn TCP', constraints=['Mình chỉ ôn TCP trong lượt này.'],
        success_criteria=['Ghi điều người dùng dặn'], known_facts=[], completed=completed,
        remaining=['Ghi chú'], status='in_progress')
    runtime.model_client.chat_with_meta.side_effect = [
        {'message': {'content': json.dumps(state)}}, {'message': {'content': 'Chưa ghi.'}}]
    response = runtime.run('Ghi lại: Mình chỉ ôn TCP trong lượt này.')
    assert response.error == expected_error
    assert not runtime.notebook.snapshot()
    assert runtime.model_client.chat_with_meta.call_count == (1 if expected_error else 2)


def test_user_edit_updates_context_without_rewriting_source_and_rejects_stale_edits():
    notes = WorkNotebook()
    note = notes.add_user_note('Rảnh sau 3 giờ')
    changed = notes.user_edit(note['id'], note['revision'], 'Rảnh sau 4 giờ')
    assert changed['confirmed'] and changed['revision'] == 2
    assert notes.model_context()[0]['text'] == 'Rảnh sau 4 giờ'
    with pytest.raises(ValueError):
        notes.user_edit(note['id'], 1, 'Giá trị cũ')
    notes.remove(note['id'], 2)
    assert notes.model_context() == []


def test_correction_replaces_one_note_with_new_user_quote_and_revision():
    notes = WorkNotebook()
    notes.begin_request('Tôi có 20 phút để ôn TCP.')
    first = notes.record('Tôi có 20 phút', 'Tôi có 20 phút')
    notes.begin_request('Tôi có 30 phút, sửa lại ghi chú giúp mình.')
    new = notes.record('Tôi có 30 phút', 'Tôi có 30 phút', replace_id=first['id'], revision=1)
    assert len(notes.snapshot()) == 1 and new['revision'] == 2
    assert new['quote'] == 'Tôi có 30 phút' and new['confirmed']
    with pytest.raises(ValueError):
        notes.record('Tôi có 30 phút', 'Tôi có 30 phút', replace_id=first['id'], revision=1)


def test_reset_blocks_late_note_writes_and_result_selection():
    notes = WorkNotebook()
    generation = notes.begin_request('Chỉ ôn phần TCP thôi.')
    notes.select_results(['observed-result'], generation=generation)
    notes.clear()
    with pytest.raises(ValueError, match='cancelled'):
        notes.record('Chỉ ôn phần TCP thôi.', 'Chỉ ôn phần TCP thôi.', generation=generation)
    with pytest.raises(ValueError, match='cancelled'):
        notes.select_results(['late-result'], generation=generation)
    assert not notes.result_ids() and not notes.selection_set


def test_stop_preserves_accepted_notes_but_blocks_late_writes():
    notes = WorkNotebook()
    generation = notes.begin_request('Tôi có 30 phút để ôn TCP.')
    saved = notes.record('Tôi có 30 phút', 'Tôi có 30 phút', generation=generation)
    notes.invalidate_pending()
    with pytest.raises(ValueError, match='cancelled'):
        notes.record('để ôn TCP.', 'để ôn TCP.', generation=generation)
    assert notes.snapshot() == [saved]


def test_direct_input_replaces_previous_value_for_same_result_field():
    notes = WorkNotebook()
    notes.record_input('input:chart:time', 'Giờ sinh: 09:30', source='control:chart')
    notes.record_input('input:chart:time', 'Giờ sinh: 10:00', source='control:chart')
    assert len(notes.snapshot()) == 1
    assert notes.snapshot()[0]['revision'] == 2
    assert notes.snapshot()[0]['text'] == 'Giờ sinh: 10:00'


def test_runtime_notes_reach_followup_as_sourced_context():
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)
    choices = iter([ModelDecision('', tool_name='record_work_note', tool_args={
        'text': 'chỉ ôn TCP.', 'source_quote': 'chỉ ôn TCP.'}), ModelDecision('', final_answer='Đã ghi.')])
    runtime.model_callable = lambda goal, steps: next(choices)
    result = runtime.run('Tôi có 20 phút, chỉ ôn TCP.')
    assert not result.error and result.tool_call_count == 1
    messages = runtime._native_messages('Xếp lại giúp mình', [])
    note_message = next(message for message in messages if 'Session work notes' in message['content'])
    assert 'chỉ ôn TCP.' in note_message['content']
    assert 'user_supplied' in note_message['content']


def test_public_trace_uses_observations_not_private_reasoning_or_raw_completion():
    step = AgentStep(1, 'PRIVATE CHAIN SHOULD NEVER SHOW', 'read_document',
        tool_result={'filename': 'TCP.txt', 'found': True, 'truncated': True},
        raw_completion='PRIVATE RAW COMPLETION')
    trace = summarize_step(step)
    assert trace.title == 'Đọc tài liệu' and 'TCP.txt' in trace.detail
    assert 'PRIVATE' not in trace.detail and 'PRIVATE' not in trace.title
    assert 'phần đầu' in trace.detail


def test_structured_plan_is_a_proposal_not_verified_completion():
    step = AgentStep(1, '', 'update_task_state', tool_result={'task_state': {
        'goal': 'Ôn TCP', 'remaining': ['Đọc tài liệu'], 'completed': ['Đã làm mọi thứ']}})
    trace = summarize_step(step)
    assert trace.status == 'proposed'
    assert 'Đọc tài liệu' in trace.detail and 'Đã làm mọi thứ' not in trace.detail


@pytest.mark.parametrize('result,status', [({'error': 'Read failed'}, 'error'),
    ({'status': 'needs_input', 'prompt': 'Bạn sinh ngày nào?'}, 'waiting'),
    ({'error': 'duplicate_action'}, 'stopped')])
def test_trace_exposes_failures_waiting_and_limits(result, status):
    assert summarize_step(AgentStep(1, '', 'read_document', tool_result=result)).status == status


def test_work_selection_only_accepts_real_results_and_can_clear_the_surface():
    from rat.kernel.contracts import Artifact
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)
    for name, kind in [('schedule', 'schedule'), ('files', 'document_search')]:
        runtime.artifact_store.put(Artifact(name, kind))
    selected = runtime.execute_tool('select_work_results', {'artifact_ids': ['schedule', 'files']})
    assert [ref['artifact_id'] for ref in selected['result_refs']] == ['schedule', 'files']
    with pytest.raises(ValueError):
        runtime.execute_tool('select_work_results', {'artifact_ids': ['invented']})
    assert runtime.notebook.result_ids() == ['schedule', 'files']
    runtime.execute_tool('select_work_results', {'artifact_ids': []})
    assert runtime.notebook.result_ids() == [] and runtime.notebook.selection_set
