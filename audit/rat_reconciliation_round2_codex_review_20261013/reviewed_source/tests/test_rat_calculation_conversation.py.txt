"""Cross-turn core contracts with injected decisions, never model-quality evidence."""
from unittest.mock import MagicMock

import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.kernel.contracts import Artifact
from rat.timetable.compositor import TimetableCompositor
from rat.ui.chat_session import ConversationHistory


def runtime_fixture():
    return AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                            use_live_model=False, plan_tasks=False)


def action(name, **args):
    return ModelDecision('', tool_name=name, tool_args=args)


def answer(text):
    return ModelDecision('', final_answer=text)


def result_note(artifact, text, **replacement):
    return action('record_work_note', text=text, source_result={
        'artifact_id': artifact.id, 'revision': artifact.revision, 'field': 'result',
    }, **replacement)


def run_turn(runtime, history, query, decisions, **options):
    # Pending turns are not part of the prior message context.
    prior_messages, prior_refs = history.messages_with_turn_ids(), history.turn_references()
    snap = history.begin_turn(query)
    choices = iter(decisions)
    runtime.model_callable = lambda goal, steps: next(choices)
    response = runtime.run(query, history=prior_messages, turn_references=prior_refs,
                           turn_ref=snap.turn_ref, execution_id=snap.execution_id,
                           conversation_id=history.conversation_id, **options)
    refs = [{'artifact_id': a.id, 'revision': a.revision} for a in response.artifacts]
    metadata = dict(execution_id=response.execution_id, artifact_refs=refs,
                    note_ids=list(dict.fromkeys(e['note_id'] for e in response.note_events)),
                    note_event_ids=[e['event_id'] for e in response.note_events])
    if response.error == 'cancelled':
        history.cancel_turn(snap.turn_id, reconciliation=response.reconciliation, **metadata)
    elif response.error:
        history.fail_turn(snap.turn_id, error=response.error, reconciliation=response.reconciliation, **metadata)
    else:
        history.complete_turn(snap.turn_id, response.answer, reconciliation=response.reconciliation, **metadata)
    assert response.execution_id == snap.execution_id
    return snap, response


def test_calculate_record_change_compare_cancel_and_continue_share_one_core():
    runtime, history = runtime_fixture(), ConversationHistory()

    first_turn, first = run_turn(runtime, history, 'Tính 18 * 7', [
        action('calculate', expression='18 * 7'), answer('126'),
    ])
    assert not first.error and first.answer_verification_status == 'PASS'
    assert len(first.artifacts) == 1
    original = first.artifacts[0]
    assert original.payload == {'expression': '18 * 7', 'result': '126'}
    assert original.provenance['owner_turn_id'] == first_turn.turn_id
    assert original.provenance['presentation'] == 'trace'

    saved_turn, saved = run_turn(runtime, history, 'Ghi lại kết quả này.', [
        result_note(original, '126'), answer('Đã ghi kết quả.'),
    ])
    assert not saved.error and len(saved.note_events) == 1
    old_note = saved.note_events[0]['snapshot']
    assert old_note['owner_turn_id'] == saved_turn.turn_id
    assert old_note['source_ref']['quote_source_turn_id'] == first_turn.turn_id
    assert old_note['source_ref']['artifact_id'] == original.id
    assert runtime.notebook.model_context()[0]['authority'] == 'observed_result'

    # The fixture chooses its action; the app does not recognize a canned phrase.
    choices = iter([
        action('calculate', expression='18 * 9'),
        lambda: result_note(runtime.artifact_store.list('calculation')[-1], '162',
                            replace_note_id=old_note['id'], revision=1),
        answer('162'),
    ])
    dynamic_decisions = (value() if callable(value) else value for value in choices)
    changed_turn, changed = run_turn(runtime, history, 'Thay 7 bằng 9 và sửa ghi chú đó.', dynamic_decisions)
    assert not changed.error
    current = changed.artifacts[0]
    assert runtime.artifact_store.get(original.id).payload == original.payload
    new_note = runtime.notebook.snapshot()[0]
    assert new_note['revision'] == 2 and new_note['text'] == '162'
    assert new_note['source_ref']['artifact_id'] == current.id
    assert new_note['owner_turn_id'] == changed_turn.turn_id
    old_projection = runtime.notebook.notes_for_turn(saved_turn.turn_id)[0]
    assert old_projection['text'] == '126' and old_projection['status'] == 'replaced'
    assert old_projection['replaced_by_turn_id'] == changed_turn.turn_id
    assert runtime.notebook.version_history(old_note['id'])[0] == old_note

    _, comparison = run_turn(runtime, history, 'Chênh với kết quả trước bao nhiêu?', [
        action('inspect_artifact', artifact_id=original.id, revision=1),
        action('inspect_artifact', artifact_id=current.id, revision=1),
        action('calculate', expression='162 - 126'), answer('36'),
    ])
    assert not comparison.error and comparison.answer == '36'
    assert [s.tool_result['result'] for s in comparison.steps[:2]] == ['126', '162']
    # Arithmetic is checked; the model's natural-language interpretation is not.
    assert comparison.verification_reports[-1]['scope'] == 'calculation_answer_only'
    assert comparison.completion_status == 'unchecked'

    cancelled = {'value': False}
    def stop_after_result(step):
        if step.tool_name == 'calculate':
            cancelled['value'] = True
    stopped_turn, stopped = run_turn(runtime, history, 'Tính gấp đôi rồi ghi lại.', [
        action('calculate', expression='162 * 2'), answer('This must never be committed'),
    ], on_step=stop_after_result, should_cancel=lambda: cancelled['value'])
    assert stopped.error == 'cancelled' and stopped.answer == ''
    assert stopped.note_events == [] and runtime.notebook.snapshot() == [new_note]
    accepted_before_stop = stopped.artifacts[0]
    stopped_context = runtime.notebook.current_context()
    with pytest.raises(ValueError, match='cancelled'):
        runtime.execute_tool('record_work_note', result_note(accepted_before_stop, '324').tool_args,
                             turn_id=stopped_turn.turn_id, execution_id=stopped.execution_id,
                             note_context=stopped_context)
    assert runtime.notebook.snapshot() == [new_note]

    resumed_turn, resumed = run_turn(runtime, history, 'Tiếp tục, ghi kết quả vừa tính.', [
        action('inspect_artifact', artifact_id=accepted_before_stop.id, revision=1),
        result_note(accepted_before_stop, '324', replace_note_id=old_note['id'], revision=2),
        answer('Đã ghi kết quả vừa tính.'),
    ])
    assert not resumed.error and resumed.execution_id != stopped.execution_id
    assert len(resumed.note_events) == 1
    latest = runtime.notebook.snapshot()[0]
    assert latest['revision'] == 3 and latest['text'] == '324'
    assert latest['owner_turn_id'] == resumed_turn.turn_id
    assert latest['source_ref']['quote_source_turn_id'] == stopped_turn.turn_id
    assert [v['text'] for v in runtime.notebook.version_history(old_note['id'])] == ['126', '162', '324']
    assert history.get_turn(stopped_turn.turn_id).status == 'cancelled'
    with pytest.raises(ValueError, match='phiên bản mới nhất'):
        runtime.execute_tool('record_work_note', result_note(original, '126',
                             replace_note_id=old_note['id'], revision=1).tool_args)
    assert runtime.notebook.snapshot()[0] == latest


@pytest.mark.parametrize('reference', [
    {'artifact_id': 'invented', 'revision': 1, 'field': 'value'},
    {'artifact_id': 'sample', 'revision': 9, 'field': 'value'},
    {'artifact_id': 'sample', 'revision': 1, 'field': 'invented'},
    {'artifact_id': 'sample', 'revision': 1, 'field': 'nested.missing'},
    {'artifact_id': 'sample', 'revision': 1, 'field': 'nested'},
])
def test_invented_or_unsupported_result_sources_do_not_mutate_notes(reference):
    runtime = runtime_fixture()
    runtime.artifact_store.put(Artifact('sample', 'sample', payload={'value': 7, 'nested': {'value': 7}}))
    runtime.notebook.begin_request('Ghi kết quả này.')
    with pytest.raises(ValueError):
        runtime.execute_tool('record_work_note', {'text': '7', 'source_result': reference})
    assert runtime.notebook.snapshot() == [] and runtime.notebook.events_since(0) == []


def test_result_note_uses_exact_historical_revision_without_promoting_paraphrase():
    runtime = runtime_fixture()
    runtime.artifact_store.put(Artifact('sample', 'sample', 1, {'nested': {'value': 7}},
                                         provenance={'owner_turn_id': 'turn-old'}))
    runtime.artifact_store.put(Artifact('sample', 'sample', 2, {'nested': {'value': 9}}))
    runtime.notebook.begin_request('Ghi bản cũ.', turn_ref='turn-new')
    ref = {'artifact_id': 'sample', 'revision': 1, 'field': 'nested.value'}
    exact = runtime.execute_tool('record_work_note', {'text': '7', 'source_result': ref})['note']
    proposed = runtime.execute_tool('record_work_note', {'text': 'Số lượng là 700', 'source_result': ref})['note']
    assert exact['confirmed'] and exact['source_ref']['artifact_revision'] == 1
    assert exact['source_ref']['quote'] == '7' and exact['source_ref']['quote_source_turn_id'] == 'turn-old'
    assert not proposed['confirmed'] and proposed['status'] == 'proposed'
    assert [n['authority'] for n in runtime.notebook.model_context()] == ['observed_result', 'unconfirmed_model_suggestion']
    assert runtime.notebook.historical_context() == []


@pytest.mark.parametrize('extra', [
    {}, {'source_turn_id': 'turn-fake'}, {'source_quote': 'Ghi kết quả này.'},
    {'revision': 1}, {'replace_note_id': 'invented'},
])
def test_source_modes_and_replacement_pair_must_be_explicit(extra):
    runtime = runtime_fixture()
    runtime.artifact_store.put(Artifact('sample', 'sample', payload={'value': 7}))
    runtime.notebook.begin_request('Ghi kết quả này.')
    args = {'text': '7', 'source_result': {'artifact_id': 'sample', 'revision': 1, 'field': 'value'}, **extra}
    if not extra:
        args.pop('source_result')
    with pytest.raises(ValueError):
        runtime.execute_tool('record_work_note', args)
    assert runtime.notebook.snapshot() == []


def test_saying_saved_without_execution_remains_unchecked():
    runtime, history = runtime_fixture(), ConversationHistory()
    _, response = run_turn(runtime, history, 'Ghi kết quả giúp tôi.', [answer('Đã ghi.')])
    assert response.note_events == [] and runtime.notebook.snapshot() == []
    assert response.completion_status == 'unchecked'
    assert response.answer_verification_status == 'UNKNOWN'


def test_missing_result_owner_is_not_invented_from_note_writing_turn():
    runtime = runtime_fixture()
    runtime.artifact_store.put(Artifact('sample', 'sample', payload={'value': 7}))
    runtime.notebook.begin_request('Ghi kết quả này.', turn_ref='turn-new')
    result = runtime.execute_tool('record_work_note', {
        'text': '7', 'source_result': {'artifact_id': 'sample', 'revision': 1, 'field': 'value'},
    })
    assert result['note']['owner_turn_id'] == 'turn-new'
    assert result['note']['source_ref']['quote_source_turn_id'] is None
    assert result['note_event']['source_turn_id'] is None


@pytest.mark.parametrize('field,value', [('value', float('inf')), ('value', 'x' * 501)])
def test_unrepresentable_source_values_do_not_commit(field, value):
    runtime = runtime_fixture()
    runtime.artifact_store.put(Artifact('sample', 'sample', payload={field: value}))
    runtime.notebook.begin_request('Ghi kết quả này.')
    with pytest.raises(ValueError):
        runtime.execute_tool('record_work_note', {
            'text': '7', 'source_result': {'artifact_id': 'sample', 'revision': 1, 'field': field},
        })
    assert runtime.notebook.events_since(0) == []
