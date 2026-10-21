"""Real indexed reads and scripted inference; no model quality assertion."""
import json
from unittest.mock import Mock

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.selected_document_qa import answer_selected_document, MAX_READ_CHARS
from rat.timetable.compositor import TimetableCompositor


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'selected.txt'
    path.write_text('Mã xác nhận: LOTUS-7319.\nPhòng: B203.')
    db = Database(str(tmp_path / 'index.db'))
    db.upsert_document({'file_path': str(path), 'file_name': path.name, 'file_ext': '.txt',
        'file_size': path.stat().st_size, 'created_at': 1, 'modified_at': 1, 'indexed_at': 1,
        'content_text': path.read_text()})
    client = Mock()
    client.chat_with_meta.return_value = {'message': {'role': 'assistant', 'content': 'LOTUS-7319'},
        'prompt_tokens': 100, 'completion_tokens': 8, 'done_reason': 'stop', 'error': None}
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    yield runtime, path, client
    db.get_connection().close()


def test_one_call_after_real_read_preserves_source_artifact_and_receipt(env):
    runtime, path, client = env
    response = answer_selected_document(runtime, 'Mã xác nhận là gì?', str(path), model_client=client)
    assert response.error is None and response.answer == 'LOTUS-7319'
    assert client.chat_with_meta.call_count == 1 and response.tool_call_count == 1
    messages, tools = client.chat_with_meta.call_args.args
    assert tools == [] and messages[-1]['content'] == 'Mã xác nhận là gì?'
    assert path.read_text() in json.loads(messages[1]['content'].split(': ', 1)[1])['text']
    assert response.sources[0]['path'] == str(path) and response.sources[0]['read']
    assert response.artifacts[0].kind == 'document_content'
    receipts = response.execution_journal.receipts
    assert any(r.operation_name == 'read_document' and r.committed for r in receipts)
    assert response.total_tokens == 108


@pytest.mark.parametrize('state', ['missing', 'unindexed', 'empty'])
def test_no_call_when_selected_file_cannot_supply_text(env, state):
    runtime, path, client = env
    if state == 'missing':
        path.unlink()
    elif state == 'unindexed':
        path = path.with_name('not-indexed.txt')
        path.write_text('Unindexed content.')
    else:
        path.write_text('')
    response = answer_selected_document(runtime, 'Mã?', str(path), model_client=client)
    assert response.error in {'selected_document_read_failed', 'selected_document_no_text'}
    assert not response.answer
    client.chat_with_meta.assert_not_called()


def test_partial_read_is_explicit_in_prompt_and_source(env):
    runtime, path, client = env
    path.write_text('x' * 6000)
    response = answer_selected_document(runtime, 'Nội dung?', str(path), model_client=client)
    assert response.error is None
    data = json.loads(client.chat_with_meta.call_args.args[0][1]['content'].split(': ', 1)[1])
    assert data['truncated'] and len(data['text']) == MAX_READ_CHARS and data['total_chars'] == 6000
    assert response.sources[0]['truncated'] and response.sources[0]['read_chars'] == MAX_READ_CHARS


@pytest.mark.parametrize('failure', ['tool', 'truncated', 'timeout'])
def test_failures_never_execute_model_tools_or_trigger_another_generation(env, failure):
    runtime, path, client = env
    meta = client.chat_with_meta.return_value
    if failure == 'tool':
        meta['message'] = {'tool_calls': [{'function': {'name': 'open_document', 'arguments': {'file_path': str(path)}}}]}
    elif failure == 'truncated':
        meta['done_reason'] = 'length'
    else:
        meta['error'] = 'fixture timeout'
    response = answer_selected_document(runtime, 'Mã?', str(path), model_client=client)
    assert response.error and not response.answer
    assert client.chat_with_meta.call_count == 1
    assert [s.tool_name for s in response.steps if s.tool_name] == ['read_document']


def test_cancellation_during_inference_discards_late_answer(env):
    runtime, path, client = env
    cancelled = [False]
    def finish(*args, **kwargs):
        cancelled[0] = True
        return {'message': {'content': 'Late answer'}, 'prompt_tokens': 10, 'completion_tokens': 3}
    client.chat_with_meta.side_effect = finish
    response = answer_selected_document(runtime, 'Mã?', str(path), model_client=client,
                                        should_cancel=lambda: cancelled[0])
    assert response.error == 'cancelled' and not response.answer
    assert client.chat_with_meta.call_count == 1


def test_disabled_runtime_does_not_instantiate_a_live_client(env):
    runtime, path, _ = env
    runtime.use_live_model = False
    with pytest.raises(ValueError, match='live_model_disabled'):
        answer_selected_document(runtime, 'Mã?', str(path))
