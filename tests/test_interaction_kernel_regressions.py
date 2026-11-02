"""Execution regressions from Codex review; scripted calls are not AI quality evidence."""
from dataclasses import asdict
from threading import Event, Thread
from unittest.mock import patch

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.kernel import Artifact, ArtifactAction, ArtifactStore, ActionDispatcher, CapabilityRegistry, OperationDefinition
from rat.kernel.view_spec import StandardViewProvider, ViewBlock, ViewSpec, validate_view_spec
from rat.timetable.compositor import TimetableCompositor


@pytest.fixture
def runtime(tmp_path):
    db = Database(str(tmp_path / 'index.db'))
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=False)
    yield runtime
    db.get_connection().close()


BIRTH = dict(name='Ví dụ kiểm thử', date='2000-06-15', time='09:30', place='Hồ Chí Minh',
             latitude=10.8231, longitude=106.6297, timezone='Asia/Ho_Chi_Minh')


def chart(runtime):
    pytest.importorskip('swisseph')
    result = runtime.dispatcher.execute_operation('create_natal_chart', BIRTH)
    assert result.status == 'success', result.error
    return result.artifact


def test_partial_native_call_publishes_resumable_input(runtime):
    runtime.model_callable = lambda goal, steps: ModelDecision('', tool_name='create_natal_chart', tool_args={'date': BIRTH['date']})
    response = runtime.run('Lập lá số')
    assert response.error is None
    request = response.pending_input_request
    assert request is not None and request.supplied_inputs['date'] == BIRTH['date']
    assert response.artifacts[0].kind == 'input_request'
    result = runtime.dispatcher.resume_input(request.id, BIRTH)
    assert result.status == 'success'
    assert runtime.artifact_store.get(request.id) is None
    assert runtime.dispatcher.state.pending_input_request is None


def test_native_followup_reuses_target_and_records_actual_revision(runtime):
    before = chart(runtime)
    decisions = iter([ModelDecision('', tool_name='update_birth_data', tool_args={
        'artifact_id': before.id, 'revision': before.revision, 'time': '10:15'}),
        ModelDecision('', final_answer='Đã cập nhật.')])
    runtime.model_callable = lambda goal, steps: next(decisions)
    response = runtime.run('Đổi giờ thành 10:15')
    assert response.error is None
    latest = runtime.artifact_store.get(before.id)
    assert latest.revision == 2 and latest.payload['chart']['birth']['time'] == '10:15'
    assert len(runtime.artifact_store.get_history(before.id)) == 2
    assert [a.id for a in response.artifacts] == [before.id]
    assert before.id in str(runtime._native_messages('Tiếp tục', []))


def test_export_keeps_chart_and_requires_explicit_destination(runtime, tmp_path):
    before = chart(runtime)
    action = next(a for a in runtime.registry.actions_for(before) if a.params.get('format') == 'svg')
    waiting = runtime.dispatcher.dispatch(action)
    assert waiting.status == 'needs_input'
    destination = tmp_path / 'la-so.svg'
    result = runtime.dispatcher.resume_input(waiting.input_request.id, {'output_path': str(destination)})
    assert result.status == 'success', result.error
    assert destination.read_text().startswith('<svg')
    assert result.artifact.kind == 'file_export' and result.artifact.id != before.id
    assert runtime.artifact_store.get(before.id).to_dict() == before.to_dict()


def test_read_action_keeps_search_result_and_creates_content(runtime, tmp_path):
    path = tmp_path / 'network.txt'
    path.write_text('TCP retransmits missing segments.')
    runtime.db.get_connection().execute('''INSERT INTO documents
        (file_path,file_name,file_ext,file_size,created_at,modified_at,content_text,summary,normalized_text,indexed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)''', (str(path), path.name, '.txt', 40, 1, 1, path.read_text(), 'TCP network', 'tcp network', 1))
    runtime.db.get_connection().commit()
    found = runtime.dispatcher.execute_operation('search_documents', {'query': 'TCP'}).artifact
    action = next(a for a in runtime.registry.actions_for(found) if a.operation_name == "read_document")
    read = runtime.dispatcher.dispatch(action)
    assert read.status == 'success', read.error
    assert read.artifact.kind == 'document_content'
    assert read.artifact.payload['found'] is True
    assert runtime.artifact_store.get(found.id).to_dict() == found.to_dict()


def test_ambiguous_native_update_waits_for_real_target(runtime):
    first = chart(runtime)
    second = runtime.dispatcher.execute_operation('create_natal_chart', {**BIRTH, 'name': 'Ví dụ thứ hai'}).artifact
    waiting = runtime.dispatcher.execute_operation('update_birth_data', {'time': '10:15'})
    assert waiting.status == 'needs_input'
    index = next(i for i, c in enumerate(waiting.input_request.candidate_choices) if c['id'] == second.id)
    done = runtime.dispatcher.resume_input(waiting.input_request.id, {'selected_candidate': index})
    assert done.status == 'success', done.error
    assert done.artifact.id == second.id
    assert runtime.artifact_store.get(first.id).revision == 1


@pytest.mark.parametrize('values', [{'time_known': 'false'}, {'latitude': True}, {'max_orb': -1}])
def test_direct_calls_validate_types_before_coercion(runtime, values):
    result = runtime.dispatcher.execute_operation('create_natal_chart', {**BIRTH, **values})
    assert result.status == 'error'
    assert not runtime.artifact_store.list()


def test_view_rejects_prefixed_forged_actions_and_forged_resource_data(runtime):
    artifact = chart(runtime)
    provider = StandardViewProvider(runtime.registry)
    spec = provider.provide_view(artifact)
    assert validate_view_spec(spec, artifact, runtime.registry)[0]
    action_block = next(b for b in spec.blocks if b.type == 'actions')
    action_block.data['actions'][0]['operation_name'] = 'export_invented'
    assert not validate_view_spec(spec, artifact, runtime.registry)[0]
    spec = provider.provide_view(artifact)
    resource = next(b for b in spec.blocks if b.type == 'resource')
    resource.data['value'] = {'birth': BIRTH}
    assert not validate_view_spec(spec, artifact, runtime.registry)[0]
    spec = ViewSpec(1, artifact.id, artifact.revision, blocks=[ViewBlock('summary', {'fields': ['sun']})])
    assert not validate_view_spec(spec, artifact, runtime.registry)[0]  # A substring in the payload is not a field.


def test_ids_do_not_collide_and_revisions_cannot_roll_back(runtime):
    with patch('time.time', return_value=1):
        first = chart(runtime)
        second = chart(runtime)
    assert first.id != second.id
    with pytest.raises(ValueError, match='non_monotonic_revision'):
        runtime.artifact_store.put(first)


def test_reset_rejects_inflight_results():
    registry, store = CapabilityRegistry(), ArtifactStore()
    entered, release = Event(), Event()
    def handler(args, **context):
        entered.set()
        assert release.wait(5)
        return {'value': 1}
    registry.register_operation(OperationDefinition('slow', 'Slow fixture', {'type': 'object', 'properties': {}}, handler, artifact_kind='fixture'))
    dispatcher = ActionDispatcher(registry, store)
    results = []
    worker = Thread(target=lambda: results.append(dispatcher.execute_operation('slow', {})))
    worker.start()
    assert entered.wait(5)
    dispatcher.reset()
    release.set()
    worker.join(5)
    assert not worker.is_alive()
    assert results[0].status == 'cancelled'
    assert store.list() == [] and dispatcher.state.events == []


def test_custom_operation_registers_its_view_and_actions_without_feature_branch(runtime):
    def view(artifact, context):
        return ViewSpec(1, artifact.id, artifact.revision, blocks=[ViewBlock('summary', {'text': str(artifact.payload['value'])})])
    def actions(artifact):
        return [ArtifactAction('refresh-fixture', 'Cập nhật', artifact.id, artifact.revision, 'fixture', {'value': 2})]
    runtime.registry.register_operation(OperationDefinition('fixture', 'Custom fixture',
        {'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'required': ['value']},
        lambda args, **ctx: args, artifact_kind='custom', view_factory=view, available_actions=actions, updates_target=True))
    artifact = runtime.dispatcher.execute_operation('fixture', {'value': 1}).artifact
    spec = StandardViewProvider(runtime.registry).provide_view(artifact)
    assert spec.blocks[0].data['text'] == '1'
    assert validate_view_spec(spec, artifact, runtime.registry)[0]
    action = runtime.registry.actions_for(artifact)[0]
    assert runtime.dispatcher.dispatch(action).artifact.revision == 2


def test_prior_result_can_be_inspected_by_exact_id_and_revision(runtime):
    before = chart(runtime)
    runtime.execute_tool('update_birth_data', {'artifact_id': before.id, 'revision': 1, 'time': '10:15'})
    old = runtime.execute_tool('inspect_artifact', {'artifact_id': before.id, 'revision': 1})
    new = runtime.execute_tool('inspect_artifact', {'artifact_id': before.id})
    assert old['chart']['birth']['time'] == '09:30' and old['revision'] == 1
    assert new['chart']['birth']['time'] == '10:15' and new['revision'] == 2


def test_repeated_birth_hour_requests_a_fold_and_resumes(runtime):
    birth = {**BIRTH, 'date': '2023-11-05', 'time': '01:30', 'place': 'New York',
             'latitude': 40.7128, 'longitude': -74.006, 'timezone': 'America/New_York'}
    result = runtime.dispatcher.execute_operation('create_natal_chart', birth)
    assert result.status == 'needs_input'
    assert result.input_request.missing_fields[0]['name'] == 'fold'
    resumed = runtime.dispatcher.resume_input(result.input_request.id, {'fold': 1})
    assert resumed.status == 'success', resumed.error
    assert resumed.artifact.payload['chart']['utc_datetime'].startswith('2023-11-05T06:30')


def test_failed_geocoding_offers_manual_values_without_guessing(runtime):
    with patch('rat.astrology.places.search_places', return_value=()):
        result = runtime.dispatcher.execute_operation('create_natal_chart',
            {'date': BIRTH['date'], 'time': BIRTH['time'], 'place': 'Lieu chưa tra được'})
    assert result.status == 'needs_input'
    assert {f['name'] for f in result.input_request.missing_fields} == {'latitude', 'longitude', 'timezone'}
    assert 'latitude' not in result.input_request.supplied_inputs
    resumed = runtime.dispatcher.resume_input(result.input_request.id, {k: BIRTH[k] for k in ('latitude', 'longitude', 'timezone')})
    assert resumed.status == 'success', resumed.error


def test_declared_output_contract_rejects_wrong_result_before_publication(runtime):
    runtime.registry.register_operation(OperationDefinition('invalid_fixture', 'Invalid fixture',
        {'type': 'object', 'properties': {}}, lambda args, **ctx: {'value': 'wrong type'},
        result_contract={'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'required': ['value']},
        artifact_kind='fixture'))
    result = runtime.dispatcher.execute_operation('invalid_fixture', {})
    assert result.status == 'error'
    assert runtime.artifact_store.list() == []


def test_serialized_unknown_time_view_binds_real_chart_without_copying_payload(runtime):
    import json
    result = runtime.dispatcher.execute_operation('create_natal_chart', {**BIRTH, 'time_known': False})
    artifact = result.artifact
    assert artifact.payload['chart']['positions'][0]['day_range'] is not None
    spec = StandardViewProvider(runtime.registry).provide_view(artifact)
    restored = ViewSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert validate_view_spec(restored, artifact, runtime.registry)[0]
    resource = next(b for b in restored.blocks if b.type == 'resource')
    assert resource.data == {'resource': 'wheel', 'field': 'chart'}
