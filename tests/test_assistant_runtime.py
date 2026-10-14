"""Offline execution-contract checks. Scripted decisions are fixture evidence only."""
import json
from datetime import datetime
from unittest.mock import patch

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AgentStep, AssistantRuntime, ModelDecision, observed_sources
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.model import ClassSession, MemberSchedule


@pytest.fixture
def runtime(tmp_path):
    db = Database(str(tmp_path / 'index.db'))
    file = tmp_path / 'networks.txt'
    file.write_text('TCP retransmits missing segments. Exercise: explain timeout backoff.')
    db.get_connection().execute('''INSERT INTO documents
        (file_path,file_name,file_ext,file_size,created_at,modified_at,content_text,summary,normalized_text,indexed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (str(file), file.name, '.txt', 80, 1, 1, file.read_text(), 'Networks TCP', 'networks tcp', 1))
    db.get_connection().commit()
    member = MemberSchedule(id='student', name='Student', schedule={
        'T2': [ClassSession(1, 3, 'Networks', 'B203', course_code='NET101')],
        'T4': [ClassSession(4, 6, 'Networks', 'B203', course_code='NET101')],
    })
    r = AssistantRuntime(db=db, compositor=TimetableCompositor([member]), use_live_model=False)
    yield r
    db.get_connection().close()


def scripted(*decisions):
    it = iter(decisions)
    return lambda goal, steps: next(it)


def test_tools_and_active_member(runtime):
    assert runtime.tool_get_schedule('Monday', 'student')[0]['room'] == 'B203'
    with pytest.raises(ValueError):
        runtime.tool_get_schedule('T2', 'missing-member')
    with pytest.raises(ValueError):
        runtime.tool_get_schedule('made up date')
    assert runtime.tool_get_schedule('next', now_dt=datetime(2026, 10, 12, 23))[0]['day_code'] == 'T4'
    assert runtime.tool_get_schedule('2026-10-14')[0]['course_code'] == 'NET101'


def test_observed_sources_and_token_accounting(runtime):
    path = runtime.tool_search_documents('Networks')[0]['path']
    runtime.model_callable = scripted(
        ModelDecision('', tool_name='search_documents', tool_args={'query': 'Networks'}, prompt_tokens=100, completion_tokens=10),
        ModelDecision('', tool_name='read_document', tool_args={'file_path': path}, prompt_tokens=150, completion_tokens=15),
        ModelDecision('', final_answer='TCP retransmits missing segments.', prompt_tokens=180, completion_tokens=20),
    )
    progress = []
    result = runtime.run('Explain the file', on_progress=progress.append)
    assert result.answer == 'TCP retransmits missing segments.'
    assert result.total_tokens == 475
    assert result.tool_call_count == 2
    assert result.sources[0]['read'] is True
    assert result.sources[0]['path'] == path
    assert not result.is_live_model
    assert 'Đang đọc tài liệu…' in progress


def test_disabled_model_does_not_emulate_intelligence(runtime):
    result = runtime.run('Prepare for my class')
    assert result.error == 'live_model_disabled'
    assert not result.answer and not result.sources


@pytest.mark.parametrize('name,args', [
    ('invented', {}), ('search_documents', {}), ('search_documents', {'query': 'x', 'limit': -1}),
    ('search_documents', {'query': 'x', 'limit': True}), ('read_document', {'file_path': 'x', 'max_chars': 999999}),
])
def test_bad_tool_calls_are_failures(runtime, name, args):
    runtime.model_callable = scripted(ModelDecision('', tool_name=name, tool_args=args))
    result = runtime.run('Anything')
    assert result.error and result.tool_call_count == 0
    assert not result.answer


def test_context_includes_followup_and_selected_member(runtime):
    messages = runtime._native_messages('Tóm tắt cái đó', [],
        history=[{'role': 'assistant', 'content': 'Found Networks notes'}],
        previous_sources=[{'path': '/notes/networks.txt'}], member_id='student',
        now_dt=datetime(2026, 10, 11, 14))
    assert messages[-1]['content'] == 'Tóm tắt cái đó'
    assert messages[1]['content'] == 'Found Networks notes'
    assert '/notes/networks.txt' in messages[2]['content']
    runtime_context = next(message for message in messages if message['content'].startswith('Runtime context:'))
    assert runtime_context['role'] == 'system' and 'student' in runtime_context['content']
    assert '2026-10-11' in runtime_context['content']


def test_duplicate_action_requests_model_finish_without_canned_plan(runtime):
    call = ModelDecision('', tool_name='get_schedule', tool_args={'target_date': 'T2'})
    runtime.model_callable = scripted(call, call, ModelDecision('', final_answer='Only this model-authored answer.'))
    result = runtime.run('Check schedule')
    assert result.tool_call_count == 1
    assert result.answer == 'Only this model-authored answer.'
    assert result.sources[0]['type'] == 'schedule'


def test_learned_stop_retains_sources_and_uses_model_synthesis(runtime):
    from rat.engine.controller import ControllerDecision, ControllerIntervention
    class StopAfterSchedule:
        def evaluate_step(self, state, action, args, goal):
            return ControllerDecision(ControllerIntervention.FORCE_STOP if state.has_schedule else ControllerIntervention.ALLOW, 'fixture')
    runtime.controller = StopAfterSchedule()
    runtime.model_callable = scripted(
        ModelDecision('', tool_name='get_schedule', tool_args={'target_date': 'T2'}),
        ModelDecision('', tool_name='search_documents', tool_args={'query': 'Networks'}),
        ModelDecision('', final_answer='I only have the schedule.'),
    )
    result = runtime.run('Check classes')
    assert result.answer == 'I only have the schedule.'
    assert result.tool_call_count == 1 and result.sources
    assert result.controller_decisions[-1]['intervention'] == 'FORCE_STOP'


def test_live_failure_keeps_raw_completion_and_usage(runtime):
    runtime.use_live_model = True
    with patch('rat.engine.slm.slm_engine.chat_with_meta', return_value={
        'message': {'role': 'assistant', 'tool_calls': [{'function': {'name': 'read_document', 'arguments': []}}]}, 'prompt_tokens': 50, 'completion_tokens': 7, 'done_reason': 'stop',
    }):
        result = runtime.run('Help')
    assert result.error == 'invalid_model_output'
    assert result.total_tokens == 57
    assert json.loads(result.steps[0].raw_completion)['tool_calls'][0]['function']['arguments'] == []
    assert result.is_live_model


def test_cancel_before_inference_and_budget_exhaustion(runtime):
    assert runtime.run('Help', should_cancel=lambda: True).error == 'cancelled'
    runtime.model_callable = scripted(ModelDecision('', tool_name='get_schedule', tool_args={'target_date': 'T2'}))
    result = runtime.run('Help', max_steps=1)
    assert result.error == 'step_budget_exhausted' and not result.answer


def native_call(name, args):
    return {'function': {'name': name, 'arguments': args}}


def test_native_parallel_calls_return_all_observations_once(runtime):
    runtime.use_live_model = True
    calls = [native_call('get_schedule', {'target_date': 'T2'}), native_call('search_documents', {'query': 'Networks'})]
    replies = [
        {'message': {'role': 'assistant', 'content': '', 'tool_calls': calls}, 'prompt_tokens': 100, 'completion_tokens': 30},
        {'message': {'role': 'assistant', 'content': 'Model-authored result.'}, 'prompt_tokens': 200, 'completion_tokens': 20},
    ]
    with patch('rat.engine.slm.slm_engine.chat_with_meta', side_effect=replies) as chat:
        result = runtime.run('Use my data', member_id='student')
    assert result.answer == 'Model-authored result.'
    assert result.tool_call_count == 2 and result.total_tokens == 350
    messages = chat.call_args_list[-1].args[0]
    tool_messages = [m for m in messages if m['role'] == 'tool']
    assert [m['tool_name'] for m in tool_messages] == ['get_schedule', 'search_documents']
    assert json.loads(tool_messages[0]['content'])[0]['room'] == 'B203'
    assert json.loads(tool_messages[1]['content'])[0]['filename'] == 'networks.txt'


def test_duplicate_in_parallel_batch_skips_remaining_tools_and_asks_model_to_finish(runtime):
    runtime.use_live_model = True
    repeated = native_call('get_schedule', {'target_date': 'T2'})
    replies = [
        {'message': {'role': 'assistant', 'tool_calls': [repeated]}},
        {'message': {'role': 'assistant', 'tool_calls': [repeated, native_call('search_documents', {'query': 'Networks'})]}},
        {'message': {'role': 'assistant', 'content': 'Schedule-only answer.'}},
    ]
    with patch('rat.engine.slm.slm_engine.chat_with_meta', side_effect=replies) as chat:
        result = runtime.run('Help')
    assert result.tool_call_count == 1 and result.answer == 'Schedule-only answer.'
    assert chat.call_args.args[1] == []
    messages = chat.call_args.args[0]
    assert 'not_executed' in messages[-2]['content']


@pytest.mark.parametrize('message', [None, [], {}, {'content': ''},
    {'tool_calls': [{'function': {'name': 'get_schedule', 'arguments': []}}]},
    {'tool_calls': [42]}, {'tool_calls': [{'function': None}]}])
def test_malformed_native_messages_are_recorded_failures(runtime, message):
    runtime.use_live_model = True
    with patch('rat.engine.slm.slm_engine.chat_with_meta', return_value={'message': message}):
        result = runtime.run('Help')
    assert result.error == 'invalid_model_output' and not result.answer


def test_partial_sources_survive_cancel_after_read(runtime):
    path = runtime.tool_search_documents('Networks')[0]['path']
    runtime.model_callable = scripted(ModelDecision('', tool_name='read_document', tool_args={'file_path': path}))
    steps = []
    result = runtime.run('Read', on_step=steps.append, should_cancel=lambda: bool(steps))
    assert result.error == 'cancelled'
    assert result.sources[0]['path'] == path and result.sources[0]['read'] is True


def test_reserved_final_turn_uses_no_tools_and_exposes_budget(runtime):
    runtime.use_live_model = True
    replies = [
        {'message': {'role': 'assistant', 'tool_calls': [native_call('get_schedule', {'target_date': 'T2'})]}},
        {'message': {'role': 'assistant', 'content': 'Only the schedule is available.'}},
    ]
    with patch('rat.engine.slm.slm_engine.chat_with_meta', side_effect=replies) as chat:
        result = runtime.run('Prepare', max_steps=2)
    assert result.answer == 'Only the schedule is available.'
    assert chat.call_args.args[1] == []
    assert 'budget' in chat.call_args.args[0][-1]['content']


def test_calculator_evaluates_arithmetic_without_unbounded_powers_or_code(runtime):
    assert runtime.tool_calculate('47 * 83') == '3901'
    assert runtime.tool_calculate('(12 - 2) / 5') == '2.0'
    for expression in ['2 ** (2 ** 100)', '2 ** 100000000', '__import__("os")', '1 / 0', '1e999']:
        with pytest.raises((ValueError, ZeroDivisionError)):
            runtime.tool_calculate(expression)


def test_birth_place_lookup_keeps_candidates_and_calculated_chart_source(runtime):
    pytest.importorskip('swisseph')
    from rat.astrology.places import Place
    places = (Place('HCM', 10.8231, 106.6297, 'Asia/Ho_Chi_Minh'), Place('Other', 21, 105, 'Asia/Ho_Chi_Minh'))
    with patch('rat.astrology.places.search_places', return_value=places) as lookup:
        result = runtime.execute_tool('search_birth_places', {'query': 'Ho Chi Minh City'})
    lookup.assert_called_once_with('Ho Chi Minh City')
    assert len(result) == 2 and result[0]['timezone'] == places[0].timezone
    calculated = runtime.execute_tool('create_natal_chart', {
        'date': '2000-06-15', 'time': '09:30', 'place': result[0]['name'],
        'latitude': result[0]['latitude'], 'longitude': result[0]['longitude'], 'timezone': result[0]['timezone']})
    step = AgentStep(1, '', tool_name='create_natal_chart', tool_result=calculated)
    sources = observed_sources(step)
    messages = runtime._native_messages('Explain these observations', [step], previous_sources=sources)
    observation = json.loads(messages[-1]['content'])['observation']['chart']
    points = [dict(zip(observation['points']['columns'], row)) for row in observation['points']['rows']]
    assert points[0]['longitude'] == calculated['chart']['positions'][0]['longitude']
    assert len(points) == 14 and len(observation['house_cusps']) == 12
    assert 'distance_au' in sources[0]['chart']['positions'][0]
    assert 'distance_au' not in points[0]  # Export-only fields stay out of the inference context.
