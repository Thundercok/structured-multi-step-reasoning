"""Native transport contract; no real model or quality assertions."""
from io import BytesIO
import json
from unittest.mock import patch

from rat.engine.slm import SLMEngine


def test_native_chat_payload_and_reported_usage():
    payload = {'message': {'role': 'assistant', 'tool_calls': []}, 'done': True,
               'prompt_eval_count': 31, 'eval_count': 7, 'done_reason': 'stop',
               'load_duration': 100, 'prompt_eval_duration': 200, 'eval_duration': 300}
    messages = [{'role': 'user', 'content': 'hello'}]
    tool = {'type': 'function', 'function': {'name': 'calculate', 'parameters': {'type': 'object'}}}
    with patch('urllib.request.urlopen', return_value=BytesIO(json.dumps(payload).encode())) as urlopen:
        result = SLMEngine(model='fixture').chat_with_meta(messages, [tool])
    request = urlopen.call_args.args[0]
    body = json.loads(request.data)
    assert request.full_url.endswith('/api/chat')
    assert body['messages'] == messages and body['tools'] == [tool]
    assert body['stream'] is False
    assert result['prompt_tokens'] == 31 and result['completion_tokens'] == 7
    assert result['message'] == payload['message']
    assert result['token_usage_known'] is True
    assert result['raw_response'] == payload


def test_chat_transport_failure_is_returned_without_any_fallback():
    with patch('urllib.request.urlopen', side_effect=TimeoutError('fixture timeout')) as request:
        result = SLMEngine().chat_with_meta([], [])
    assert request.call_count == 1
    assert 'timeout' in result['error'] and result['message'] == {}
    assert result['token_usage_known'] is False and result['raw_response'] is None


def test_incomplete_chat_does_not_become_a_successful_answer():
    payload = {'message': {'role': 'assistant', 'content': 'Partial'}, 'done': False,
               'prompt_eval_count': 31, 'eval_count': 7}
    with patch('urllib.request.urlopen', return_value=BytesIO(json.dumps(payload).encode())):
        result = SLMEngine().chat_with_meta([], [])
    assert result['error'] == 'incomplete_chat_response'
    assert result['prompt_tokens'] == 31 and result['completion_tokens'] == 7
    assert result['token_usage_known'] is False


def test_absent_usage_is_distinguished_from_reported_zero_tokens():
    for counts, known in (({}, False), ({'prompt_eval_count': 0, 'eval_count': 0}, True)):
        payload = {'message': {'role': 'assistant', 'content': 'hello'}, 'done': True, **counts}
        with patch('urllib.request.urlopen', return_value=BytesIO(json.dumps(payload).encode())):
            result = SLMEngine().chat_with_meta([], [])
        assert result['token_usage_known'] is known
        assert result['raw_response'] == payload
