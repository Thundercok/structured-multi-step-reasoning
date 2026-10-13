"""Independent headless review probes. No live model, Qt, or personal indexing.

These assertions encode the intended lifecycle contract, not the current code.
Run explicitly with pytest; failures are retained as review evidence.
"""
from unittest.mock import MagicMock

import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.timetable.compositor import TimetableCompositor
from rat.engine.work_notes import TurnRef, WorkNotebook
from rat.kernel.contracts import Artifact, ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.registry import CapabilityRegistry, OperationDefinition
from rat.ui.chat_session import ConversationHistory


def test_reset_rejects_completion_from_previous_conversation_execution():
    history = ConversationHistory()
    old = history.begin_turn('Old conversation request')
    history.clear()
    current = history.begin_turn('New conversation request')
    assert old.turn_id == current.turn_id  # IDs are reused across conversation namespaces.
    with pytest.raises(ValueError):
        history.complete_turn(old.turn_id, 'Late old answer', execution_id=old.execution_id)
    assert history.get_turn(current.turn_id).answer == ''


def test_repeated_completion_is_idempotent():
    history = ConversationHistory()
    turn = history.begin_turn('One request')
    history.complete_turn(turn.turn_id, 'One answer', execution_id=turn.execution_id)
    try:
        history.complete_turn(turn.turn_id, 'One answer', execution_id=turn.execution_id)
    except ValueError:
        pass  # Explicit rejection also prevents duplicate context.
    assert len(history.context_messages()) == 2


def test_late_failure_does_not_reopen_cancelled_turn():
    history = ConversationHistory()
    turn = history.begin_turn('Request to stop')
    history.cancel_turn(turn.turn_id, execution_id=turn.execution_id)
    try:
        history.fail_turn(turn.turn_id, 'failed', execution_id=turn.execution_id)
    except ValueError:
        pass
    assert history.get_turn(turn.turn_id).status == 'cancelled'


def ambiguity_fixture():
    registry, store = CapabilityRegistry(), ArtifactStore()
    registry.register_operation(OperationDefinition(
        'update_sample', 'Update a sample result',
        {'type': 'object', 'properties': {}, 'additionalProperties': False},
        lambda args, **ctx: {'value': 'updated'},
        artifact_kind='sample', target_kind='sample', updates_target=True,
    ))
    store.put(Artifact('sample-a', 'sample', 1, {'value': 'a'}))
    store.put(Artifact('sample-b', 'sample', 1, {'value': 'b'}))
    return ActionDispatcher(registry, store), store


def test_cancelled_ambiguous_operation_does_not_create_pending_input():
    dispatcher, store = ambiguity_fixture()
    dispatcher.cancel_execution('exec-stopped')
    result = dispatcher.execute_operation('update_sample', {}, context={
        'turn_id': 'turn-stopped', 'execution_id': 'exec-stopped',
    })
    assert result.status == 'cancelled'
    assert dispatcher.state.pending_input_request is None
    assert len(store.list()) == 2


def test_ambiguity_request_and_event_preserve_owner_identity():
    dispatcher, _ = ambiguity_fixture()
    result = dispatcher.execute_operation('update_sample', {}, context={
        'turn_id': 'turn-active', 'execution_id': 'exec-active',
    })
    assert result.status == 'needs_input'
    assert result.artifact.provenance.get('owner_turn_id') == 'turn-active'
    event = dispatcher.state.events[-1]
    assert event.turn_id == 'turn-active' and event.execution_id == 'exec-active'


def test_runtime_does_not_commit_artifact_when_cancel_requested_during_tool():
    cancelled = {'value': False}

    def handler(args, **context):
        # Deterministically model a stop request arriving while the handler runs.
        cancelled['value'] = True
        return {'value': 'late result'}

    registry = CapabilityRegistry()
    registry.register_operation(OperationDefinition(
        'produce_sample', 'Produce a result',
        {'type': 'object', 'properties': {}, 'additionalProperties': False},
        handler, artifact_kind='sample',
    ))
    runtime = AssistantRuntime(
        db=MagicMock(), compositor=TimetableCompositor([]), registry=registry,
        use_live_model=False, plan_tasks=False,
        model_callable=lambda goal, steps: ModelDecision('', tool_name='produce_sample', tool_args={}),
    )
    response = runtime.run('Produce a result', max_steps=2, should_cancel=lambda: cancelled['value'])
    assert response.error == 'cancelled'
    assert runtime.artifact_store.list() == []


def test_historical_context_matches_latest_snapshot_owned_by_old_turn():
    notes = WorkNotebook(conversation_id='conv-review')
    notes.begin_request('Có 20 phút', turn_ref=TurnRef('conv-review', 'turn-1'))
    first = notes.record('Có 20 phút', 'Có 20 phút')
    edit_ctx = notes.make_interaction_context(target_turn_id='turn-1')
    edited = notes.user_edit(first['id'], first['revision'], 'Có 30 phút', context=edit_ctx)
    notes.begin_request('Có 40 phút', turn_ref=TurnRef('conv-review', 'turn-2'))
    notes.record('Có 40 phút', 'Có 40 phút', replace_id=first['id'], revision=edited['revision'])
    old_display = notes.notes_for_turn('turn-1')[0]
    old_context = notes.historical_context()[0]
    assert old_display['text'] == 'Có 30 phút'
    assert old_context['revision'] == old_display['revision']
    assert old_context['text'] == old_display['text']
