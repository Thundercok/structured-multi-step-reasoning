"""Deterministic contract regressions; scripted decisions are not UI/model acceptance."""
import copy

import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.note_requirements import derive_note_requirements, NoteRequirementError
from rat.kernel.capabilities.smart_notes import deterministic_note_synthesizer

TASK = 'Đọc Section 3 của bài BEST-Route'
GOAL = f'Tạo và lưu Smart Note từ câu trả lời BEST-Route vừa rồi. Thêm việc cần làm: {TASK}. Dùng công cụ ghi chú và báo ID sau khi lưu.'


def runtime(decisions=()):
    calls = []
    def model(goal, trajectory, **context):
        calls.append(context)
        return decisions[len(calls)-1]
    rt = AssistantRuntime(model_callable=model, use_live_model=False)
    return rt, calls


def create(rt, raw=TASK):
    result = rt.execute_tool('synthesize_smart_note', {'raw_content': raw})
    return rt.artifact_store.get(result['artifact_id'])


def proposal(items):
    note = deterministic_note_synthesizer('BEST-Route là bài nghiên cứu.')
    return {key: copy.deepcopy(items if key == 'action_items' else note[key]) for key in
            ('title', 'domain', 'summary', 'key_facts', 'analysis_sections', 'risks_and_constraints', 'action_items')}


def synth(items):
    return ModelDecision(thought='Kiểm tra hợp đồng', tool_name='synthesize_smart_note', tool_args={
        'raw_content': 'BEST-Route là bài nghiên cứu.', 'structured_note': proposal(items)})


def test_missing_requested_task_rejected_then_repaired():
    rt, calls = runtime([synth([]), synth([{'task': TASK, 'done': False}]),
                         ModelDecision(thought='Kiểm tra hợp đồng', final_answer='Đã lưu ghi chú.')])
    response = rt.run(GOAL, max_steps=4)
    assert response.error is None
    assert len(calls) == 3  # No extra planning/model verifier call.
    notes = rt.artifact_store.find_by_kind('structured_note')
    assert len(notes) == 1
    assert notes[0].payload['action_items'] == [{'task': TASK, 'done': False}]
    assert 'invalid_note' in str(response.steps[0].tool_result)
    assert response.completion_status == 'satisfied'


def test_final_without_receipt_cannot_erase_required_effect():
    rt, calls = runtime([ModelDecision(thought='Kiểm tra hợp đồng', final_answer='Đã lưu.', outcomes=[]) for _ in range(2)])
    response = rt.run(GOAL, max_steps=2)
    assert response.error
    assert response.completion_status != 'satisfied'
    assert not rt.artifact_store.find_by_kind('structured_note')


def test_latest_note_wrong_operation_and_target_repair():
    rt, _ = runtime()
    create(rt, 'Đọc bài cũ')
    target = create(rt)
    goal = f'Đánh dấu {TASK} đã xong trong note mới nhất'
    decisions = [ModelDecision(thought='Kiểm tra hợp đồng', tool_name='synthesize_smart_note', tool_args={'raw_content': TASK}),
                 ModelDecision(thought='Kiểm tra hợp đồng', tool_name='update_note_action_item', tool_args={
                     'artifact_id': 'art-guessed', 'revision': 1, 'item_index': 1, 'done': True}),
                 ModelDecision(thought='Kiểm tra hợp đồng', tool_name='update_note_action_item', tool_args={
                     'artifact_id': target.id, 'revision': 1, 'item_index': 1, 'done': True}),
                 ModelDecision(thought='Kiểm tra hợp đồng', final_answer='Đã đánh dấu.')]
    rt.model_callable = lambda goal, trajectory, **ctx: decisions[len(trajectory)]
    response = rt.run(goal, max_steps=5)
    assert response.error is None
    assert len(rt.artifact_store.find_by_kind('structured_note')) == 2
    assert rt.artifact_store.get(target.id).revision == 2
    assert rt.artifact_store.get(target.id).payload['action_items'][0]['done'] is True
    assert 'note_operation_mismatch' in str(response.steps[0].tool_result)
    assert 'note_target_mismatch' in str(response.steps[1].tool_result)


def test_stale_target_no_inference_or_write():
    rt, calls = runtime()
    target = create(rt)
    response = rt.run(f'Đánh dấu {TASK} đã xong trong note {target.id} revision 2')
    assert response.error == 'stale_note_target'
    assert not calls
    assert rt.artifact_store.get(target.id).revision == 1


def test_expansion_heading_and_id_preserved():
    rt, _ = runtime()
    target = create(rt)
    goal = f'Bổ sung mục Giới hạn: phân tích thêm trong note {target.id}'
    args = {'artifact_id': target.id, 'revision': 1, 'section_heading': 'Sai mục',
            'expansion_query': 'phân tích thêm', 'expansion_content': 'Cần kiểm chứng trên dữ liệu thật.'}
    decisions = [ModelDecision(thought='Kiểm tra hợp đồng', tool_name='expand_note_section', tool_args=args),
                 ModelDecision(thought='Kiểm tra hợp đồng', tool_name='expand_note_section', tool_args={**args, 'section_heading': 'Giới hạn'}),
                 ModelDecision(thought='Kiểm tra hợp đồng', final_answer='Đã bổ sung.')]
    rt.model_callable = lambda goal, trajectory, **ctx: decisions[len(trajectory)]
    response = rt.run(goal, max_steps=4)
    assert response.error is None
    assert 'note_heading_mismatch' in str(response.steps[0].tool_result)
    updated = rt.artifact_store.get(target.id)
    assert updated.revision == 2
    assert updated.payload['action_items'] == target.payload['action_items']
    assert len(rt.artifact_store.find_by_kind('structured_note')) == 1


def test_unknown_and_conflicting_targets_do_not_default_latest():
    rt, _ = runtime()
    first, second = create(rt), create(rt)
    stem = f'Đánh dấu {TASK} đã xong trong note mới nhất '
    assert derive_note_requirements(stem + 'art-unknown', rt.artifact_store).error
    assert derive_note_requirements(stem + first.id + ' ' + second.id, rt.artifact_store).error
    assert derive_note_requirements(stem + first.id, rt.artifact_store,
        {'target_artifact_id': second.id, 'target_revision': 1}).error


@pytest.mark.parametrize('goal', ['Không tạo note mới', 'Giải thích cách tạo note', 'Checklist có nghĩa gì?'])
def test_non_commands_are_not_bound(goal):
    rt, _ = runtime()
    assert not derive_note_requirements(goal, rt.artifact_store, 'legacy-turn').operation


def test_direct_dispatcher_rejects_missing_checklist_and_wrong_mutation():
    rt, _ = runtime()
    requirements = derive_note_requirements(GOAL, rt.artifact_store)
    result = rt.dispatcher.execute_operation('synthesize_smart_note', {
        'raw_content': 'Nguồn', 'structured_note': proposal([])}, context={
            'artifact_store': rt.artifact_store, 'note_requirements': requirements})
    assert result.status != 'success'
    assert not rt.artifact_store.find_by_kind('structured_note')
    target = create(rt)
    requirements = derive_note_requirements(f'Đánh dấu {TASK} đã xong trong note {target.id}', rt.artifact_store)
    with pytest.raises(NoteRequirementError, match='note_task_mismatch'):
        requirements.check_action('update_note_action_item', {
            'artifact_id': target.id, 'revision': 1, 'task_match': 'khác', 'done': True}, rt.artifact_store)


def test_selected_pdf_note_mutation_uses_agent_lane_without_pdf_read(tmp_path):
    from rat.engine.execution import ExecutionRequest
    from rat.engine.execution_service import AgentExecutionService
    rt, calls = runtime()
    target = create(rt)
    decisions = [ModelDecision(thought='', tool_name='update_note_action_item', tool_args={
        'artifact_id': target.id, 'revision': 1, 'item_index': 1, 'done': True}),
        ModelDecision(thought='', final_answer='Đã đánh dấu.')]
    rt.model_callable = lambda goal, trajectory: decisions[len(trajectory)]
    response = AgentExecutionService(rt).execute(ExecutionRequest(
        query=f'Đánh dấu {TASK} đã xong trong note mới nhất',
        document_path=str(tmp_path / 'must-not-be-read.pdf')))
    assert response.error is None
    assert rt.artifact_store.get(target.id).revision == 2


def test_direct_ui_dispatch_uses_same_checklist_validation():
    from rat.engine.execution import ExecutionRequest
    from rat.engine.execution_service import AgentExecutionService
    rt, calls = runtime()
    response = AgentExecutionService(rt).execute(ExecutionRequest(query=GOAL,
        requested_action={'name': 'synthesize_smart_note', 'args': {
            'raw_content': 'BEST-Route là bài nghiên cứu.', 'structured_note': proposal([])}}))
    assert response.error
    assert not calls
    assert not rt.artifact_store.find_by_kind('structured_note')


def test_bound_requirements_are_visible_in_native_model_prompt():
    rt, _ = runtime()
    target = create(rt)
    req = derive_note_requirements(f'Đánh dấu {TASK} đã xong trong note mới nhất', rt.artifact_store)
    messages = rt._native_messages('test', [], note_requirements=req)
    assert any(target.id in str(message['content']) and 'update_note_action_item' in str(message['content'])
               for message in messages)


def test_unchecked_contract_cannot_bypass_note_receipt():
    rt, _ = runtime([ModelDecision(thought='', final_answer='Đã lưu.')])
    response = rt.run(GOAL, max_steps=1, contract={'outcomes': [], 'intent_coverage': 'unchecked'})
    assert response.error == 'completion_unresolved'
