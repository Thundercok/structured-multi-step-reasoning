"""Canonical model-boundary and closed-loop checks; scripted calls are fixtures."""
import json
from unittest.mock import Mock

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.completion import ExecutionJournal, TurnContract
from rat.engine.context_snapshot import validate_context_snapshot
from rat.engine.runtime_context import collect_runtime_context, compact_model_context, ContextBuildError
from rat.kernel.contracts import Artifact
from rat.timetable.compositor import TimetableCompositor


@pytest.fixture
def runtime(tmp_path):
    db = Database(str(tmp_path / 'index.db'))
    obj = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True, structured_context=True)
    yield obj
    db.get_connection().close()


def reply(content=None, calls=None):
    return {'message': {'role': 'assistant', 'content': content or '',
                        **({'tool_calls': calls} if calls else {})}}


def projection(messages):
    for message in messages:
        content = message.get('content', '')
        if content.startswith('Runtime context snapshot'):
            return json.loads(content.split(': ', 1)[1])
    # Planner uses the same compiler in its structured user payload.
    return json.loads(messages[-1]['content'])['context_snapshot']


def state(outcomes):
    return dict(goal='Tính và trả kết quả', constraints=[], success_criteria=['Có kết quả thật'],
                known_facts=[], completed=[], remaining=['Tính'], status='in_progress', outcomes=outcomes)


def test_early_final_continues_missing_work_and_uses_fresh_frozen_contract(runtime):
    outcomes = [dict(outcome_id='calc', kind='registered_effect', effect_type='calculate',
                     expected_args={'expression': '18 * 7'}), dict(outcome_id='answer', kind='response')]
    client = Mock()
    client.chat_with_meta.side_effect = [reply(json.dumps(state(outcomes))),
        reply('Đã tính xong.'), reply(calls=[{'id': 'native-1', 'function': {
            'name': 'calculate', 'arguments': {'expression': '18 * 7'}}}]), reply('126')]
    runtime.model_client = client
    runtime.plan_tasks = True
    response = runtime.run('Chạy phép tính đã khai và trả kết quả.', max_steps=3)
    assert response.error is None and response.answer == '126'
    assert response.reconciliation.declared_scope_completion == 'satisfied'
    assert [r.operation_name for r in response.execution_journal.receipts if r.issuer == 'dispatcher'] == ['calculate']
    snapshots = [projection(c.args[0]) for c in client.chat_with_meta.call_args_list]
    assert [s['view'] for s in snapshots] == ['planner', 'actor', 'actor', 'finish']
    assert snapshots[0]['runtime_obligations']['status'] == 'not_declared'
    assert snapshots[1]['runtime_obligations']['contract']['frozen'] is False
    assert snapshots[-1]['runtime_obligations']['contract']['frozen'] is True
    assert all(validate_context_snapshot(s)[0] for s in snapshots)
    last = client.chat_with_meta.call_args_list[-1].args[0]
    tool = next(m for m in last if m['role'] == 'tool')
    assert tool['tool_call_id'] == 'native-1'
    assert 'observation_in_context' in json.loads(tool['content'])


def test_pending_input_is_a_model_question_then_survives_into_followup(runtime):
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [reply(calls=[{'function': {
        'name': 'create_natal_chart', 'arguments': {}}}]), reply('Bạn sinh ngày nào, lúc mấy giờ và ở đâu?')]
    result = runtime.run('Lập lá số', max_steps=3)
    assert result.answer == 'Bạn sinh ngày nào, lúc mấy giờ và ở đâu?'
    assert result.pending_input_request is not None
    assert result.completion_status == 'needs_input'
    assert result.turn_reference['status'] == 'needs_input'
    pending = projection(runtime.model_client.chat_with_meta.call_args_list[-1].args[0])
    assert pending['view'] == 'finish'
    assert pending['observed_state']['lifecycle']['pending_input']['operation_name'] == 'create_natal_chart'
    runtime.model_client.chat_with_meta.side_effect = [reply('Mình còn cần ngày sinh và nơi sinh.')]
    next_result = runtime.run('9:30', history=[{'role': 'user', 'content': 'Lập lá số'},
        {'role': 'assistant', 'content': result.answer}])
    assert next_result.pending_input_request.id == result.pending_input_request.id
    snapshot = projection(runtime.model_client.chat_with_meta.call_args_list[-1].args[0])
    assert snapshot['boundary']['execution_id'] != pending['boundary']['execution_id']
    assert snapshot['observed_state']['receipts'] == []


def test_missing_work_never_becomes_a_fluent_success_when_budget_ends(runtime):
    outcomes = [dict(outcome_id='save', kind='registered_effect', effect_type='record_work_note')]
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [reply(json.dumps(state(outcomes))), reply('Đã ghi.')]
    runtime.plan_tasks = True
    response = runtime.run('Ghi lại kết quả', max_steps=1)
    assert response.error == 'completion_unresolved' and response.answer == ''
    assert response.reconciliation.unmet_outcomes[0]['outcome_id'] == 'save'
    assert response.steps[-1].tool_result['candidate_answer'] == 'Đã ghi.'


def test_native_planner_selects_operations_without_fabricating_task_state(runtime):
    runtime.planner_operations_only = True
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [
        reply(json.dumps({'operations': [], 'respond': True})), reply('Chào bạn.')]
    runtime.plan_tasks = True
    response = runtime.run('Chào Chuột')
    assert response.answer == 'Chào bạn.' and response.error is None
    assert response.task_state == {} and response.task_state_updated is False
    assert response.reconciliation.declared_scope_completion == 'satisfied'
    schema = runtime.model_client.chat_with_meta.call_args_list[0].kwargs['response_format']
    assert list(schema['properties']) == ['operations', 'respond']
    assert schema['required'] == ['operations', 'respond']
    assert response.turn_contract.proposed_by == 'model_planner_operations'
    assert response.steps[0].tool_name is None
    messages = runtime.model_client.chat_with_meta.call_args_list[0].args[0]
    assert messages[-1] == {'role': 'user', 'content': 'Chào Chuột'}


def test_native_operation_list_maps_only_model_selected_names_to_effects(runtime):
    runtime.planner_operations_only = True
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [reply(json.dumps({'operations': ['calculate'], 'respond': True})),
        reply(calls=[{'function': {'name': 'calculate', 'arguments': {'expression': '18 * 7'}}}]), reply('126')]
    runtime.plan_tasks = True
    result = runtime.run('Làm việc này', max_steps=3)
    assert result.answer == '126' and result.error is None
    assert [(o.outcome_id, o.kind, o.effect_type) for o in result.turn_contract.outcomes] == [
        ('op-1', 'registered_effect', 'calculate'), ('reply', 'response', None)]
    assert result.reconciliation.declared_scope_completion == 'satisfied'


def test_direct_native_loop_reads_and_hands_over_real_file_without_planner(runtime, tmp_path):
    path = tmp_path / 'source.txt'
    path.write_text('An actual source paragraph.', encoding='utf-8')
    runtime.db.upsert_document({'file_path': str(path), 'file_name': path.name, 'file_ext': '.txt',
                               'file_size': path.stat().st_size, 'created_at': 1, 'modified_at': 1,
                               'indexed_at': 1, 'content_text': path.read_text()})
    def call(name, args):
        return reply(calls=[{'function': {'name': name, 'arguments': args}}])
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [
        call('search_documents', {'query': 'source'}),
        call('read_document', {'file_path': str(path)}),
        call('deliver_document', {'file_path': str(path)}), reply('Đây là tệp gốc.')]
    runtime.discover_tools = True
    runtime.plan_tasks = False
    runtime.structured_context = False
    result = runtime.run('Đọc và đưa tệp đó cho tôi.', max_steps=6)
    assert result.error is None and result.answer == 'Đây là tệp gốc.'
    assert [s.tool_name for s in result.steps] == ['search_documents',
                                                'read_document', 'deliver_document', None]
    assert result.steps[0].tool_result[0]['content_status'] == 'search_metadata_only'
    assert result.steps[0].tool_result[0]['read'] is False
    delivered = next(a for a in result.artifacts if a.kind == 'document_file')
    assert delivered.payload['path'] == str(path) and delivered.payload['size_bytes'] == path.stat().st_size
    calls = runtime.model_client.chat_with_meta.call_args_list
    assert not any(c.kwargs.get('response_format') for c in calls)
    assert {t['function']['name'] for t in calls[0].args[1]} == {
        'search_documents', 'read_document', 'search_book_pages', 'read_book_page',
        'deliver_document', 'inspect_artifact', 'request_operation_tools'}
    assert 'calculate' not in {t['function']['name'] for t in calls[1].args[1]}
    # Each native tool exchange extends the same request prefix. Updating the
    # canonical context must not force the backend to reread older exchanges.
    for before, after in zip(calls, calls[1:]):
        prefix = list(before.args[0])
        if prefix[-1]['content'].startswith('Work context '):
            prefix.pop()
        assert after.args[0][:len(prefix)] == prefix
    facts = json.loads(calls[-1].args[0][-1]['content'].split(': ', 1)[1])
    assert [effect['operation'] for effect in facts['current_effects']] == [
        'search_documents', 'read_document', 'deliver_document']
    assert any(ref['id'] == delivered.id and ref['revision'] == delivered.revision
               for ref in facts['results'])
    # Successful file effects do not manufacture coverage of all user intent.
    assert result.reconciliation.intent_coverage == 'unchecked'
    assert result.reconciliation.declared_scope_completion == 'unchecked'
    assert all(step.context_boundary['execution_id'] == result.execution_id for step in result.steps)
    assert not any(m.get('content', '').startswith('Runtime context snapshot') for m in calls[0].args[0])


@pytest.mark.parametrize('operations,respond,expected_error', [
    (['calculate'] * 12, True, 'completion_unresolved'),
    ([], False, 'task_plan_failed:invalid_native_declaration:empty_work'),
])
def test_native_wire_cardinality_preserves_all_operations_and_rejects_empty_work(runtime, operations, respond, expected_error):
    runtime.planner_operations_only = True
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [
        reply(json.dumps({'operations': operations, 'respond': respond})), reply('Chưa làm.')]
    runtime.plan_tasks = True
    result = runtime.run('Làm việc này', max_steps=1)
    assert result.error == expected_error
    if operations:
        assert len(result.turn_contract.outcomes) == 13
        assert [o.effect_type for o in result.turn_contract.outcomes[:-1]] == operations
    else:
        assert result.turn_contract is None and result.execution_journal.receipts == []


def test_native_plan_rejects_response_disguised_as_executed_effect(runtime):
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.return_value = reply(json.dumps({'outcomes': [
        {'outcome_id': 'a', 'kind': 'response', 'effect_type': 'deliver_document'}]}))
    runtime.plan_tasks = True
    result = runtime.run('Gửi tệp')
    assert result.error.startswith('task_plan_failed:invalid_native_declaration:')
    assert result.answer == '' and result.execution_journal.receipts == []


def test_native_tool_catalog_follows_declared_operations_without_domain_keywords(runtime):
    runtime.model_client = Mock()
    runtime.model_client.chat_with_meta.side_effect = [reply(json.dumps({'outcomes': [
        {'outcome_id': 'a', 'kind': 'registered_effect', 'effect_type': 'deliver_document'},
        {'outcome_id': 'reply', 'kind': 'response'}]})), reply('Chưa có tệp.')]
    runtime.plan_tasks = True
    runtime.run('Làm việc này', max_steps=1)
    tools = runtime.model_client.chat_with_meta.call_args_list[1].args[1]
    names = {t['function']['name'] for t in tools}
    assert names == {'deliver_document', 'search_documents', 'inspect_artifact', 'request_operation_tools'}


def test_unexecuted_parallel_call_does_not_consume_completion_feedback(runtime):
    from rat.engine.assistant_runtime import AgentStep
    calls = [{'id': 'a', 'function': {'name': 'get_schedule', 'arguments': {'target_date': 'T2'}}},
             {'id': 'b', 'function': {'name': 'search_documents', 'arguments': {'query': 'x'}}}]
    steps = [AgentStep(1, '', tool_name='get_schedule', tool_args={'target_date': 'T2'}, tool_result=[],
                       raw_completion=json.dumps({'role': 'assistant', 'tool_calls': calls})),
             AgentStep(2, '', tool_result={'candidate_answer': 'Chưa tìm tệp.',
                                          'completion_feedback': {'unmet_outcomes': [{'outcome_id': 'find'}]}})]
    messages = runtime._native_messages('x', steps)
    tools = [m for m in messages if m['role'] == 'tool']
    assert [m['tool_call_id'] for m in tools] == ['a', 'b']
    assert json.loads(tools[1]['content']) == {'error': 'not_executed'}
    assert any(m['role'] == 'assistant' and m.get('content') == 'Chưa tìm tệp.' for m in messages)


def test_snapshot_keeps_required_old_artifact_revision_and_raw_unknown_data(runtime):
    notebook = runtime.notebook
    notebook.begin_request('giữ nguồn', execution_id='exec-x')
    ctx = notebook.current_context()
    art = Artifact('source', 'sample', payload={'result': 'old'})
    runtime.artifact_store.put(art)
    notebook.record_result('old', {'artifact_id': 'source', 'revision': 1, 'field': 'result'}, runtime.artifact_store)
    runtime.artifact_store.put(Artifact('source', 'sample', revision=2, payload={'result': 'new'}))
    notebook.select_results(['source'])
    journal = ExecutionJournal(ctx.turn_ref.conversation_id, ctx.turn_ref.turn_id, ctx.execution_id, notebook.generation)
    raw = {'$value_ref': {'entity_ref': {'kind': 'unknown'}, 'pointer': '/text'}}
    journal.record_operation('unknown_plugin', {}, raw)
    snapshot = collect_runtime_context(view='actor', notebook=notebook, store=runtime.artifact_store,
        dispatcher=runtime.dispatcher, journal=journal, contract=None, task_state={}, query='giữ nguồn')
    assert [p['revision'] for p in snapshot['indexes']['current_results']] == [2]
    assert snapshot['indexes']['selected_results'] == snapshot['indexes']['current_results']
    assert {p['revision'] for p in snapshot['boundary']['artifact_pins']} == {1, 2}
    assert any(e['body'] == raw for e in snapshot['entities'])
    assert validate_context_snapshot(snapshot)[0]


def test_coherence_failure_stops_instead_of_using_mixed_boundary(runtime, monkeypatch):
    runtime.notebook.begin_request('x', execution_id='exec-x')
    ctx = runtime.notebook.current_context()
    journal = ExecutionJournal(ctx.turn_ref.conversation_id, ctx.turn_ref.turn_id, ctx.execution_id, runtime.notebook.generation)
    cursor = iter(range(100))
    monkeypatch.setattr(runtime.notebook, 'event_cursor', lambda: next(cursor))
    with pytest.raises(ContextBuildError, match='concurrent_change'):
        collect_runtime_context(view='actor', notebook=runtime.notebook, store=runtime.artifact_store,
            dispatcher=runtime.dispatcher, journal=journal, contract=None, task_state={}, query='x')


def test_receipt_dedup_uses_exact_artifact_pin_and_keeps_raw_wrappers_literal(runtime):
    from rat.engine.context_snapshot import expand_value_refs, is_value_ref
    runtime.notebook.begin_request('x', execution_id='exec-x')
    ctx = runtime.notebook.current_context()
    raw = {'$value_ref': {'entity_ref': {'kind': 'artifact', 'conversation_id': ctx.turn_ref.conversation_id,
            'artifact_id': 'other', 'revision': 1}, 'pointer': '/payload/text'}}
    runtime.artifact_store.put(Artifact('actual', 'sample', payload=raw))
    runtime.artifact_store.put(Artifact('other', 'sample', payload={'text': 'MUST_NOT_DECODE_RAW'}))
    journal = ExecutionJournal(ctx.turn_ref.conversation_id, ctx.turn_ref.turn_id, ctx.execution_id, runtime.notebook.generation)
    journal.record_operation('plugin', {}, raw, artifact_refs=[{'artifact_id': 'actual', 'revision': 1}])
    journal.record_operation('unbound_plugin', {}, raw)
    snapshot = collect_runtime_context(view='actor', notebook=runtime.notebook, store=runtime.artifact_store,
        dispatcher=runtime.dispatcher, journal=journal, contract=None, task_state={}, query='x')
    receipts = snapshot['observed_state']['receipts']
    assert is_value_ref(receipts[0]['operation_result'])
    assert receipts[0]['operation_result']['$value_ref']['entity_ref']['artifact_id'] == 'actual'
    assert expand_value_refs(receipts[0], snapshot)['operation_result'] == raw
    # The unpinned observation has its own operation identity even if equal.
    assert receipts[1]['operation_result']['$value_ref']['entity_ref']['kind'] == 'operation_result'
    assert expand_value_refs(receipts[1], snapshot)['operation_result'] == raw


def test_compact_facts_omit_empty_defaults_and_preserve_exact_note_source_revision(runtime):
    runtime.notebook.begin_request('giữ nguồn', execution_id='exec-facts')
    ctx = runtime.notebook.current_context()
    journal = ExecutionJournal(ctx.turn_ref.conversation_id, ctx.turn_ref.turn_id, ctx.execution_id, runtime.notebook.generation)
    def collect():
        return collect_runtime_context(view='actor', notebook=runtime.notebook, store=runtime.artifact_store,
            dispatcher=runtime.dispatcher, journal=journal, contract=TurnContract(intent_coverage='unchecked'),
            task_state={}, query='giữ nguồn')
    assert compact_model_context(collect()) == {}
    literal = 'A source value containing $value_ref as plain text.'
    runtime.artifact_store.put(Artifact('source', 'sample', payload={'result': literal}))
    note = runtime.notebook.record_result(literal, {'artifact_id': 'source', 'revision': 1, 'field': 'result'}, runtime.artifact_store)
    runtime.artifact_store.put(Artifact('source', 'sample', revision=2, payload={'result': 'replacement'}))
    facts = compact_model_context(collect())
    actual = next(n for n in facts['active_notes'] if n['id'] == note['id'])
    assert actual['quote'] == literal and actual['text'] == literal
    assert actual['source_ref']['artifact_revision'] == 1
    assert actual['confirmed'] is True
    assert facts['results'][0]['revision'] == 2
    assert 'payload' not in facts['results'][0]


def test_context_preserves_existing_history_and_metadata_windows(runtime):
    history = [{'role': 'user', 'content': str(i)} for i in range(20)]
    runtime.notebook.begin_request('x', history, execution_id='exec-windows')
    ctx = runtime.notebook.current_context()
    journal = ExecutionJournal(ctx.turn_ref.conversation_id, ctx.turn_ref.turn_id, ctx.execution_id, runtime.notebook.generation)
    snapshot = collect_runtime_context(view='actor', notebook=runtime.notebook, store=runtime.artifact_store,
        dispatcher=runtime.dispatcher, journal=journal, contract=None, task_state={}, query='x', history=history,
        turn_references=[{'turn_id': f'turn-{i}'} for i in range(20)],
        previous_sources=[{'label': i} for i in range(20)])
    assert len(snapshot['current_request']['history_message_refs']) == 12
    assert [t['turn_id'] for t in snapshot['continuity']['turn_refs']] == [f'turn-{i}' for i in range(12, 20)]
    assert snapshot['unmodeled_observations'] == [{'label': i} for i in range(12, 20)]
