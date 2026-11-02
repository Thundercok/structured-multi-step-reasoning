"""Invalid equation syntax must not bypass a known literal-arithmetic obligation."""
import json
from unittest.mock import MagicMock

import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.timetable.compositor import TimetableCompositor


@pytest.mark.parametrize('candidate', ['Tính 2 + 2 = 999', 'unparseable expression = 999'])
def test_unparseable_answer_expression_is_rejected_for_a_literal_request(candidate):
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False,
                               model_callable=lambda goal, steps: ModelDecision('', final_answer=candidate))
    result = runtime.run('Tính 2 + 2', max_verification_repairs=0)
    assert result.error == 'verification_unresolved' and result.answer == ''
    assert result.answer_verification_status == 'UNKNOWN'


def test_literal_format_failure_reaches_native_feedback_and_bounded_repair():
    client = MagicMock()
    client.chat_with_meta.side_effect = [
        {'message': {'content': 'Tính 2 + 2 = 999'}, 'prompt_tokens': 10, 'completion_tokens': 4},
        {'message': {'content': json.dumps({'answer': '4'})}, 'prompt_tokens': 11, 'completion_tokens': 5},
    ]
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                               use_live_model=True, model_client=client)
    result = runtime.run('Tính 2 + 2')
    assert not result.error and result.answer == '4'
    assert [report['status'] for report in result.verification_reports] == ['UNKNOWN', 'PASS']
    assert [item['intervention'] for item in result.controller_decisions] == ['REPAIR', 'ACCEPT']
    schema = client.chat_with_meta.call_args_list[1].kwargs['response_format']
    assert schema['properties']['answer']['enum'] == ['4']
    assert result.total_tokens == 30
