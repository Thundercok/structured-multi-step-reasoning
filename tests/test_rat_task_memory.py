"""State and paired collection contract; fixtures do not measure model ability."""
import copy
import json
from unittest.mock import patch
import pytest
from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.paired_continuation import collect_pair
from rat.engine.task_state import validate_task_state
from rat.timetable.compositor import TimetableCompositor

STATE = dict(goal='Explain the exercise', constraints=['20 minutes', 'Skip IP routing'],
             success_criteria=['Read source and explain timeout backoff'], known_facts=[],
             completed=[], remaining=['Read the source'], status='in_progress')


@pytest.fixture
def runtime(tmp_path):
    db = Database(str(tmp_path / 'index.db'))
    result = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=False)
    yield result
    db.get_connection().close()


def test_only_model_authored_updates_change_memory(runtime):
    decisions = iter([ModelDecision('', tool_name='update_task_state', tool_args=copy.deepcopy(STATE)),
                      ModelDecision('', final_answer='I have not read the source yet.')])
    runtime.model_callable = lambda goal, steps: next(decisions)
    response = runtime.run('Please prepare')
    assert response.task_state == STATE and response.task_state_updated
    # Migrated per ADR-003: completion_status is derived solely from TurnReconciliation,
    # separating authoritative execution status from model-reported plan progress (preserved in task_state).
    assert response.completion_status == 'unchecked'
    assert response.task_state['status'] == 'in_progress'
    assert response.reconciliation.intent_coverage == 'unchecked'
    runtime.model_callable = lambda goal, steps: ModelDecision('', final_answer='A follow-up')
    followup = runtime.run('Three points', task_state=response.task_state)
    assert followup.task_state['constraints'] == ['20 minutes', 'Skip IP routing']
    assert not followup.task_state_updated and followup.completion_status == 'unchecked'
    assert 'Skip IP routing' in runtime._native_messages('Three points', [], task_state=STATE)[1]['content']


def test_state_validation_never_invents_missing_constraints():
    with pytest.raises(ValueError, match='remaining'):
        validate_task_state({**STATE, 'status': 'completed'})
    with pytest.raises(ValueError):
        validate_task_state({**STATE, 'constraints': '20 min'})
    assert validate_task_state(STATE) == STATE


def test_paired_cost_counts_shared_selection_and_both_synthesis_calls(runtime):
    calls = iter([ModelDecision('', tool_name='search_documents', tool_args={'query': 'Networks'}, prompt_tokens=100, completion_tokens=20),
                  ModelDecision('', final_answer='No source read.', prompt_tokens=200, completion_tokens=30),
                  ModelDecision('', final_answer='Search was empty.', prompt_tokens=300, completion_tokens=40)])
    runtime.model_callable = lambda goal, steps: next(calls)
    result = collect_pair(runtime, 'Find source', proposal_tool='search_documents')
    pair = result['pair']
    assert result['status'] == 'paired'
    assert pair['stop']['total_tokens'] == 350
    assert pair['continue']['total_tokens'] == 460
    assert pair['collection_tokens'] == 690
    assert pair['quality_gain'] is None and pair['review_status'] == 'pending'
    assert pair['stop']['steps'][0]['tool_result']['error'] == 'paired_stop'
    assert pair['continue']['steps'][0]['tool_result'] == []
    assert len(result['pair_trace_sha256']) == 64


def test_model_skipping_lookup_does_not_get_a_synthetic_pair(runtime):
    runtime.model_callable = lambda goal, steps: ModelDecision('', final_answer='Unhelpful metadata answer')
    result = collect_pair(runtime, 'Read the source')
    assert result['status'] == 'checkpoint_not_reached' and result['pair'] is None


def test_initial_schema_plan_is_a_real_counted_call_even_if_actor_skips_updates(runtime):
    runtime.use_live_model = runtime.plan_tasks = True
    replies = [dict(message={'content': json.dumps(STATE)}, prompt_tokens=100, completion_tokens=20,
                    request={'format': 'fixture_schema'}),
               dict(message={'content': 'I still need to read the source.'}, prompt_tokens=200, completion_tokens=30)]
    with patch('rat.engine.slm.slm_engine.chat_with_meta', side_effect=replies) as calls:
        response = runtime.run('Explain the exercise')
    assert calls.call_count == 2
    assert calls.call_args_list[0].kwargs['response_format']['required']
    assert response.total_tokens == 350 and response.task_state['constraints'] == STATE['constraints']
    assert response.task_state_updated and response.steps[0].tool_result['phase'] == 'initial_plan'
    assert [step.step_number for step in response.steps] == [1, 2]


def test_bad_initial_plan_is_preserved_as_failure_without_rule_fallback(runtime):
    runtime.use_live_model = runtime.plan_tasks = True
    with patch('rat.engine.slm.slm_engine.chat_with_meta', return_value={
        'message': {'content': 'This is not JSON'}, 'prompt_tokens': 50, 'completion_tokens': 7}):
        result = runtime.run('Prepare the next class')
    assert result.error.startswith('task_plan_failed:')
    assert result.total_tokens == 57 and not result.task_state
    assert json.loads(result.steps[0].raw_completion)['content'] == 'This is not JSON'


def test_internal_state_json_is_neither_a_final_answer_nor_an_invented_tool_call(runtime):
    runtime.use_live_model = True
    with patch('rat.engine.slm.slm_engine.chat_with_meta', return_value={
        'message': {'content': json.dumps(STATE)}, 'prompt_tokens': 50, 'completion_tokens': 70}):
        result = runtime.run('Prepare the next class')
    assert result.error == 'internal_task_state_in_final_answer' and not result.answer
    assert not result.task_state_updated and result.tool_call_count == 0
    assert result.total_tokens == 120 and STATE['goal'] in result.steps[0].raw_completion
