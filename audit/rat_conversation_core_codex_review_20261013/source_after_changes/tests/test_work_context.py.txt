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


def test_short_quotes_and_ambiguous_multi_turn_quotes():
    notes = WorkNotebook()
    notes.begin_request(
        'Dùng mảng [2, 4, 6, 8, 10], tìm 8',
        history=[{'role': 'user', 'content': 'Ví dụ tìm 8 hoặc 6', 'turn_id': 'turn-1'}],
        turn_ref='turn-2',
    )
    short = notes.record('mid + 1', '[2, 4, 6, 8, 10]')
    assert short['confirmed'] is False
    exact_short = notes.record('8', '8', source_turn_id='turn-2')
    assert exact_short['confirmed'] is True
    assert exact_short['source_ref']['quote_source_turn_id'] == 'turn-2'

    # Quote '8' appears in both turn-1 and turn-2; omitting source_turn_id must fail.
    with pytest.raises(ValueError, match='nhiều lượt'):
        notes.record('Mục tiêu 8', '8')


def test_cross_turn_quote_keeps_distinct_owner_and_source_turn_ids():
    notes = WorkNotebook()
    history = [
        {'role': 'user', 'content': 'Dùng mảng [2, 4, 6, 8, 10], tìm 8 từng bước', 'turn_id': 'turn-1'},
        {'role': 'assistant', 'content': 'Bước 1: mid = 2...'},
        {'role': 'user', 'content': 'Vì sao dùng mid + 1?', 'turn_id': 'turn-2'},
        {'role': 'assistant', 'content': 'Vì phần tử tại mid nhỏ hơn 8.'},
    ]
    notes.begin_request('Ghi lại mảng ở lượt đầu giúp tôi', history=history, turn_ref='turn-3')
    saved = notes.record('[2, 4, 6, 8, 10]', '[2, 4, 6, 8, 10]')
    assert saved['owner_turn_id'] == 'turn-3'
    assert saved['source_ref']['quote_source_turn_id'] == 'turn-1'


def test_two_turns_with_identical_user_text_preserve_separate_turn_ownership():
    notes = WorkNotebook()
    notes.begin_request('tìm 8', history=[], turn_ref='turn-1')
    n1 = notes.record('tìm 8', 'tìm 8')
    assert n1['owner_turn_id'] == 'turn-1'

    notes.begin_request(
        'tìm 8',
        history=[{'role': 'user', 'content': 'tìm 8', 'turn_id': 'turn-1'}],
        turn_ref='turn-2',
    )
    n2 = notes.record('tìm 8', 'tìm 8', source_turn_id='turn-2')
    assert n2['id'] != n1['id']
    assert n2['owner_turn_id'] == 'turn-2'
    assert len(notes.notes_for_turn('turn-1')) == 1
    assert len(notes.notes_for_turn('turn-2')) == 1


def test_remove_creates_tombstone_and_restore_undoes_unless_stale():
    notes = WorkNotebook()
    notes.begin_request('Chỉ số tìm kiếm: mid + 1', turn_ref='turn-1')
    created = notes.record('mid + 1', 'mid + 1')
    removed = notes.remove(created['id'], created['revision'])
    assert removed['status'] == 'removed' and removed['revision'] == 2
    assert notes.snapshot() == []
    assert notes.model_context() == []

    with pytest.raises(ValueError):
        notes.restore(created['id'], expected_revision=1)

    restored = notes.restore(created['id'], expected_revision=2)
    assert restored['status'] == 'active' and restored['revision'] == 3
    assert len(notes.snapshot()) == 1
    assert [v['status'] for v in notes.version_history(created['id'])] == ['active', 'removed', 'active']


def test_direct_input_records_artifact_provenance_and_interaction_turn():
    notes = WorkNotebook()
    ctx = notes.make_interaction_context(
        turn_id='interaction-1',
        target_turn_id='turn-2',
        target_artifact_id='chart-1',
        target_revision=3,
    )
    saved = notes.record_input(
        'input:chart:time',
        'Giờ sinh: 09:30',
        source='control:chart',
        context=ctx,
        field='birth_time',
    )
    assert saved['owner_turn_id'] == 'turn-2'
    assert saved['source_ref']['kind'] == 'artifact_input'
    assert saved['source_ref']['artifact_id'] == 'chart-1'
    assert saved['source_ref']['artifact_revision'] == 3
    assert saved['source_ref']['field'] == 'birth_time'


def test_dsa_six_turn_shared_conversation_core_contract():
    """Fixture contract test for the 6-turn DSA Binary Search flow on the shared core."""
    from rat.ui.chat_session import ConversationHistory

    history = ConversationHistory()
    runtime = AssistantRuntime(
        db=MagicMock(),
        compositor=TimetableCompositor([]),
        use_live_model=False,
    )

    # Turn 1: Explain binary search with a small example
    q1 = 'Giải thích binary search bằng ví dụ nhỏ'
    t1 = history.begin_turn(q1)
    runtime.model_callable = lambda goal, steps: ModelDecision(
        '', final_answer='Binary search chia đôi mảng đã sắp xếp ở chỉ số mid.'
    )
    r1 = runtime.run(
        q1,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t1.to_turn_ref(history.conversation_id),
        execution_id=t1.execution_id,
        turn_references=history.turn_references()[:-1],
    )
    history.complete_turn(t1.turn_id, r1.answer, execution_id=r1.execution_id)
    assert r1.turn_id == 'turn-1' and not r1.error

    # Turn 2: Array [2, 4, 6, 8, 10], find 8 step-by-step (records work note)
    q2 = 'Dùng mảng [2, 4, 6, 8, 10], tìm 8 từng bước'
    t2 = history.begin_turn(q2)
    t2_decisions = iter([
        ModelDecision(
            '',
            tool_name='record_work_note',
            tool_args={'text': 'Mảng [2, 4, 6, 8, 10], tìm 8', 'source_quote': '[2, 4, 6, 8, 10], tìm 8'},
        ),
        ModelDecision(
            '',
            final_answer='Bước 1: low=0, high=4, mid=2 (giá trị 6 < 8) -> low = mid + 1 = 3. Bước 2: mid=3 (giá trị 8).',
        ),
    ])
    runtime.model_callable = lambda goal, steps: next(t2_decisions)
    r2 = runtime.run(
        q2,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t2.to_turn_ref(history.conversation_id),
        execution_id=t2.execution_id,
        turn_references=history.turn_references()[:-1],
    )
    note_v1 = runtime.notebook.snapshot()[0]
    history.complete_turn(
        t2.turn_id,
        r2.answer,
        execution_id=r2.execution_id,
        note_ids=[note_v1['id']],
    )
    assert note_v1['owner_turn_id'] == 'turn-2' and note_v1['revision'] == 1
    assert len(r2.note_events) == 1 and r2.note_events[0]['kind'] == 'create'

    # Turn 3: Follow-up on mid + 1 without repeating the array
    q3 = 'Vì sao bước đó dùng mid + 1 mà không giữ mid?'
    t3 = history.begin_turn(q3)
    runtime.model_callable = lambda goal, steps: ModelDecision(
        '', final_answer='Vì a[mid] = 6 đã nhỏ hơn 8 nên chỉ số mid đã kiểm tra xong, cần xét từ mid + 1.'
    )
    r3 = runtime.run(
        q3,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t3.to_turn_ref(history.conversation_id),
        execution_id=t3.execution_id,
        turn_references=history.turn_references()[:-1],
    )
    history.complete_turn(t3.turn_id, r3.answer, execution_id=r3.execution_id)
    assert r3.turn_id == 'turn-3'

    # Turn 4: Change target from 8 to 6 (replaces note revision 1 -> revision 2)
    q4 = 'Đổi thành tìm 6 thì các bước đổi thế nào?'
    t4 = history.begin_turn(q4)
    t4_decisions = iter([
        ModelDecision(
            '',
            tool_name='record_work_note',
            tool_args={
                'text': 'Mảng [2, 4, 6, 8, 10], tìm 6',
                'source_quote': 'tìm 6',
                'replace_note_id': note_v1['id'],
                'revision': 1,
            },
        ),
        ModelDecision(
            '',
            final_answer='Với tìm 6: Bước 1 có low=0, high=4, mid=2 và a[2]=6 khớp ngay ở bước đầu.',
        ),
    ])
    runtime.model_callable = lambda goal, steps: next(t4_decisions)
    r4 = runtime.run(
        q4,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t4.to_turn_ref(history.conversation_id),
        execution_id=t4.execution_id,
        turn_references=history.turn_references()[:-1],
    )
    note_v2 = runtime.notebook.snapshot()[0]
    history.complete_turn(
        t4.turn_id,
        r4.answer,
        execution_id=r4.execution_id,
        note_ids=[note_v2['id']],
    )
    assert len(runtime.notebook.snapshot()) == 1
    assert note_v2['revision'] == 2 and note_v2['owner_turn_id'] == 'turn-4'
    assert note_v2['replaces_turn_id'] == 'turn-2' and note_v2['replaces_revision'] == 1

    # Turn 2 still retains its replaced note snapshot pointing forward to Turn 4
    t2_notes = runtime.notebook.notes_for_turn('turn-2')
    assert len(t2_notes) == 1
    assert t2_notes[0]['status'] == 'replaced'
    assert t2_notes[0]['replaced_by_turn_id'] == 'turn-4'
    assert t2_notes[0]['replaced_by_revision'] == 2

    # Turn 5: Look back at mid + 1 in the earlier example while keeping Turn 4 as active note
    q5 = 'Quay lại câu hỏi mid + 1 ở ví dụ trước, viết gọn thành 3 ý để tôi chép bài'
    t5 = history.begin_turn(q5)
    t5_messages = runtime._native_messages(
        q5,
        [],
        history=history.messages_with_turn_ids()[:-1],
        turn_references=history.turn_references()[:-1],
    )
    joined_context = '\n'.join(m['content'] for m in t5_messages)
    assert 'Prior replaced note versions' in joined_context
    assert 'Mảng [2, 4, 6, 8, 10], tìm 8' in joined_context
    assert 'Mảng [2, 4, 6, 8, 10], tìm 6' in joined_context
    assert 'Prior turn references' in joined_context

    runtime.model_callable = lambda goal, steps: ModelDecision(
        '', final_answer='1. Đã so sánh a[mid] < target.\n2. Loại bỏ nửa trái.\n3. Tránh lặp vô hạn khi low == mid.'
    )
    r5 = runtime.run(
        q5,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t5.to_turn_ref(history.conversation_id),
        execution_id=t5.execution_id,
        turn_references=history.turn_references()[:-1],
    )
    history.complete_turn(t5.turn_id, r5.answer, execution_id=r5.execution_id)

    # Turn 6: Start long trace request, cancel mid-execution, block late writes, then continue
    q6 = 'Viết bảng trace đầy đủ cho mọi trường hợp'
    t6 = history.begin_turn(q6)
    r6 = runtime.run(
        q6,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t6.to_turn_ref(history.conversation_id),
        execution_id=t6.execution_id,
        turn_references=history.turn_references()[:-1],
        should_cancel=lambda: True,
    )
    cancelled_ctx = runtime.notebook.current_context()
    history.cancel_turn(t6.turn_id, execution_id=r6.execution_id)
    assert r6.error == 'cancelled'

    # Any late note write or dispatcher action from the cancelled execution must be rejected
    with pytest.raises(ValueError, match='cancelled'):
        runtime.notebook.record('Viết bảng trace', 'Viết bảng trace', context=cancelled_ctx)
    late_dispatch = runtime.dispatcher.execute_operation(
        'record_work_note',
        {'text': 'Viết bảng trace', 'source_quote': 'Viết bảng trace'},
        context={'execution_id': r6.execution_id, 'note_context': cancelled_ctx},
    )
    assert late_dispatch.status in ('cancelled', 'error') and 'cancelled' in late_dispatch.error

    # Follow-up Turn 7 continues cleanly with Turn 4's active note preserved
    q7 = 'Tiếp tục với tìm 6 ở trên, chỉ số kết quả là mấy?'
    t7 = history.begin_turn(q7)
    runtime.model_callable = lambda goal, steps: ModelDecision('', final_answer='Chỉ số kết quả là mid = 2.')
    r7 = runtime.run(
        q7,
        history=history.messages_with_turn_ids()[:-1],
        turn_ref=t7.to_turn_ref(history.conversation_id),
        execution_id=t7.execution_id,
        turn_references=history.turn_references()[:-1],
    )
    history.complete_turn(t7.turn_id, r7.answer, execution_id=r7.execution_id)
    assert not r7.error and r7.answer == 'Chỉ số kết quả là mid = 2.'
    assert runtime.notebook.snapshot()[0]['text'] == 'Mảng [2, 4, 6, 8, 10], tìm 6'
