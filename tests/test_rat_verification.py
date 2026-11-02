"""Execution and rejection/repair contracts; scripted outputs are not model evidence."""
import json
from fractions import Fraction
from unittest.mock import MagicMock

import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.verification import (CalculationVerifier, ExecutionEvidence,
    VerificationReport, VerificationSession, VerificationStatus, evaluate_expression)
from rat.engine.work_trace import summarize_step
from rat.kernel.registry import OperationDefinition
from rat.timetable.compositor import TimetableCompositor


@pytest.fixture
def runtime():
    return AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)


def scripted(runtime, *decisions):
    sequence = iter(decisions)
    runtime.model_callable = lambda goal, steps: next(sequence)


def final(value, tokens=0):
    return ModelDecision('', final_answer=value, prompt_tokens=tokens, completion_tokens=2)


def test_wrong_final_is_rejected_and_a_new_model_turn_repairs_it(runtime):
    scripted(runtime, final('999', 10), final('**4**', 20))
    observed, progress = [], []
    result = runtime.run('2 + 2', on_step=observed.append, on_progress=progress.append)
    assert result.answer == '**4**' and result.error is None
    assert result.total_tokens == 34 and result.tool_call_count == 0
    assert result.answer_verification_status == 'PASS'
    assert [r['status'] for r in result.verification_reports] == ['FAIL', 'PASS']
    assert observed[0].tool_result['candidate_answer'] == '999'
    assert [d['intervention'] for d in result.controller_decisions] == ['REPAIR', 'ACCEPT']
    assert any('điều chỉnh' in message for message in progress)
    trace = summarize_step(observed[0])
    assert trace.title == 'Đối chiếu kết luận' and trace.status == 'error'
    assert '999' in trace.detail and '4' in trace.detail


def test_native_model_gets_real_failure_feedback_and_usage_is_preserved(runtime):
    class Client:
        requests = []
        formats = []
        def chat_with_meta(self, messages, tools, **kwargs):
            self.requests.append(messages)
            self.formats.append(kwargs.get('response_format'))
            content = '5' if len(self.requests) == 1 else '{"answer":"4"}'
            return {'message': {'content': content}, 'prompt_tokens': 11, 'completion_tokens': 3}
    client = Client()
    runtime.model_client, runtime.use_live_model = client, True
    result = runtime.run('Calculate 2 + 2')
    assert not result.error and result.answer == '4'
    assert result.is_live_model and result.total_tokens == 28
    assert client.requests[1][-3] == {'role': 'assistant', 'content': '5'}
    feedback = json.loads(client.requests[1][-2]['content'].split(': ', 1)[1])
    assert feedback[0]['status'] == 'FAIL'
    assert '2 + 2' in feedback[0]['reason']
    assert client.formats[0] is None and client.formats[1]['required'] == ['answer']
    assert client.formats[1]['properties']['answer']['enum'] == ['4']


@pytest.mark.parametrize('settings', [{'max_steps': 1}, {'max_verification_repairs': 0}, {'max_tokens': 12}])
def test_failed_candidate_never_becomes_answer_when_budget_ends(runtime, settings):
    scripted(runtime, final('999', 10))
    result = runtime.run('2 + 2', **settings)
    assert result.answer == '' and result.error == 'verification_failed'
    assert result.answer_verification_status == 'FAIL' and result.total_tokens == 12


def test_repair_attempts_are_bounded(runtime):
    scripted(runtime, final('5'), final('6'), final('7'))
    result = runtime.run('2 + 2', max_steps=10, max_verification_repairs=2)
    assert result.error == 'verification_failed' and len(result.steps) == 3
    assert result.controller_decisions[-1]['intervention'] == 'REJECT'


def test_unknown_format_is_not_a_pass_and_contradictory_prose_is_not_extracted(runtime):
    scripted(runtime, final('2 + 2 = 4, but the answer is 999.'))
    result = runtime.run('2 + 2', max_verification_repairs=0)
    assert result.error == 'verification_unresolved' and not result.answer
    assert result.answer_verification_status == 'UNKNOWN'


def test_equation_must_be_bound_to_the_actual_requested_expression(runtime):
    scripted(runtime, final('2 + 3 = 5'))
    result = runtime.run('2 + 2', max_verification_repairs=0)
    assert result.error == 'verification_failed'
    assert 'biểu thức khác' in result.verification_reports[-1]['reason']


def test_word_problem_interpretation_is_not_promoted_to_verified(runtime):
    scripted(runtime, ModelDecision('', tool_name='calculate', tool_args={'expression': '3 * 3'}), final('9'))
    result = runtime.run('Three notebooks cost 45000. What do seven cost?')
    assert not result.error
    report = result.verification_reports[-1]
    assert report['status'] == 'PASS' and report['scope'] == 'calculation_answer_only'
    assert 'diễn giải đề bài chưa được kiểm chứng' in report['reason']
    assert result.completion_status == 'unchecked'


def test_previous_request_evidence_is_not_reused(runtime):
    scripted(runtime, ModelDecision('', tool_name='calculate', tool_args={'expression': '3 * 3'}), final('9'))
    first = runtime.run('Compute a quantity')
    assert first.verification_reports
    scripted(runtime, final('9'))
    second = runtime.run('What is the number in my document?')
    assert second.answer_verification_status == 'UNKNOWN' and not second.verification_reports


def test_corrupt_tool_result_is_detected_independently(runtime, monkeypatch):
    monkeypatch.setattr(runtime, 'tool_calculate', lambda expression: '999')
    scripted(runtime, ModelDecision('', tool_name='calculate', tool_args={'expression': '2 + 2'}), final('4'))
    # The utility handler calls the class calculator; inject at the registered handler boundary.
    runtime.registry.get_operation('calculate').handler = lambda args, **ctx: {'expression': args['expression'], 'result': '999'}
    result = runtime.run('2 + 2')
    assert result.verification_reports[0]['status'] == 'FAIL'
    assert result.verification_reports[-1]['status'] == 'PASS'
    assert result.answer == '4' and result.tool_call_count == 1


def test_custom_registered_checker_uses_same_runtime_and_feedback(runtime):
    class CountChecker:
        def check_execution(self, evidence):
            return VerificationReport(VerificationStatus.PASS, 'count_result', 'Observed count.', (evidence.id,))
        def check_answer(self, goal, answer, evidence):
            if not evidence:
                return None
            expected = str(evidence[-1].result['count'])
            return VerificationReport(VerificationStatus.PASS if answer == expected else VerificationStatus.FAIL,
                                      'count_answer', f'Expected observed count {expected}.', (evidence[-1].id,), retryable=True)
    runtime.registry.register_operation(OperationDefinition('read_count', 'Read count',
        {'type': 'object', 'properties': {}}, lambda args, **ctx: {'count': 7}, verifier=CountChecker()))
    scripted(runtime, ModelDecision('', tool_name='read_count', tool_args={}), final('8'), final('7'))
    result = runtime.run('Read the count')
    assert not result.error and result.answer == '7'
    assert [r['status'] for r in result.verification_reports] == ['PASS', 'FAIL', 'PASS']
    assert result.verification_reports[-1]['evidence_ids'][0].startswith('request:')


def test_checker_crash_remains_unknown_and_cannot_silently_pass(runtime):
    class BrokenChecker:
        def check_execution(self, evidence):
            raise RuntimeError('broken')
        def check_answer(self, goal, answer, evidence):
            raise RuntimeError('broken')
    runtime.registry.get_operation('calculate').verifier = BrokenChecker()
    scripted(runtime, final('4'))
    result = runtime.run('2 + 2', max_verification_repairs=0)
    assert result.error == 'verification_unresolved'
    assert result.answer_verification_status == 'UNKNOWN'


def test_cancel_after_check_does_not_publish_the_candidate(runtime):
    scripted(runtime, final('4'))
    observed = []
    result = runtime.run('2 + 2', on_step=observed.append, should_cancel=lambda: bool(observed))
    assert result.error == 'cancelled' and not result.answer


def test_evidence_snapshot_is_immutable_to_later_handler_mutation(runtime):
    session = VerificationSession(runtime.registry, '2 + 2', 'example')
    payload = {'expression': '2 + 2', 'result': '4'}
    session.observe('calculate', {'expression': '2 + 2'}, payload, 1)
    payload['result'] = '999'
    reports = session.check_answer('4')
    assert reports[0]['status'] == 'PASS'
    snapshot = next(iter(session.evidence.values()))[0]
    assert snapshot.result['result'] == '4' and len(snapshot.sha256) == 64


@pytest.mark.parametrize('expression,expected', [('0.1 + 0.2', Fraction(3, 10)),
    ('(12 - 2) / 5', Fraction(2)), ('7 // 2', Fraction(3)), ('7 % 2', Fraction(1)), ('2 ** -3', Fraction(1, 8))])
def test_independent_arithmetic(expression, expected):
    assert evaluate_expression(expression) == expected


@pytest.mark.parametrize('expression', ['2 ** 10000000', '1e999999 + 2', '__import__("os")',
    'True + 1', '1 / 0', '2 ** 0.5'])
def test_checker_has_bounded_syntax_and_no_code_execution(expression):
    with pytest.raises((ValueError, ZeroDivisionError)):
        evaluate_expression(expression)


def test_large_integer_error_is_not_hidden_by_relative_tolerance(runtime):
    scripted(runtime, final('1000000000001'))
    result = runtime.run('1000000000000 + 0', max_verification_repairs=0)
    assert result.error == 'verification_failed'


def test_invalid_checker_status_is_not_accepted_as_a_pass(runtime):
    class InvalidChecker:
        def check_answer(self, *args):
            return VerificationReport('PASS', 'bad_contract', 'Not a typed status')
    runtime.registry.get_operation('calculate').verifier = InvalidChecker()
    scripted(runtime, final('4'))
    result = runtime.run('2 + 2', max_verification_repairs=0)
    assert result.error == 'verification_unresolved'
    assert result.answer_verification_status == 'UNKNOWN'


@pytest.mark.parametrize('content', ['4', '{"answer":"4","contradiction":"999"}', '{"answer":4}'])
def test_malformed_repair_envelope_is_a_recorded_failure(runtime, content):
    class Client:
        count = 0
        def chat_with_meta(self, messages, tools, **kwargs):
            self.count += 1
            return {'message': {'content': '999' if self.count == 1 else content}, 'completion_tokens': 4}
    runtime.model_client, runtime.use_live_model = Client(), True
    result = runtime.run('2 + 2')
    assert result.error == 'invalid_verified_answer_format' and not result.answer
    assert result.total_tokens == 8
    assert json.loads(result.steps[-1].raw_completion)['content'] == content


def test_correct_schema_with_wrong_value_still_fails_the_checker(runtime):
    class Client:
        count = 0
        def chat_with_meta(self, messages, tools, **kwargs):
            self.count += 1
            return {'message': {'content': '999' if self.count == 1 else '{"answer":"5"}'}}
    runtime.model_client, runtime.use_live_model = Client(), True
    result = runtime.run('2 + 2', max_verification_repairs=1)
    assert result.error == 'verification_failed' and not result.answer


def test_repair_schema_cannot_be_bypassed_with_an_unrequested_tool(runtime):
    class Client:
        count = 0
        def chat_with_meta(self, messages, tools, **kwargs):
            self.count += 1
            return {'message': {'content': '999'} if self.count == 1 else {'tool_calls': [
                {'function': {'name': 'get_schedule', 'arguments': {'target_date': 'today'}}}]}}
    runtime.model_client, runtime.use_live_model = Client(), True
    result = runtime.run('2 + 2')
    assert result.error == 'invalid_verified_answer_format' and result.tool_call_count == 0


def test_output_constraint_is_computed_from_request_not_a_canned_answer(runtime):
    scripted(runtime, final('999'), final('3901'))
    result = runtime.run('47 * 83')
    first = result.verification_reports[0]
    assert first['answer_schema']['properties']['answer']['enum'] == ['3901']
    assert result.answer == '3901' and result.answer_verification_status == 'PASS'


def test_identical_operations_in_separate_requests_have_distinct_evidence_ids(runtime):
    ids = []
    for _ in range(2):
        scripted(runtime, ModelDecision('', tool_name='calculate', tool_args={'expression': '2 + 2'}), final('4'))
        response = runtime.run('2 + 2')
        ids.append(response.verification_reports[0]['evidence_ids'][0])
    assert ids[0] != ids[1]
