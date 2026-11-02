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


def test_selected_document_qa_populates_telemetry_streams_progress_and_reconciles_contract(env):
    runtime, path, client = env
    client.chat_with_meta.return_value = {
        'message': {'role': 'assistant', 'content': 'LOTUS-7319'},
        'prompt_tokens': 120,
        'completion_tokens': 6,
        'done_reason': 'stop',
        'error': None,
        'duration_ms': 42.5,
        'phases': {
            'queue_ms': 1.2,
            'load_ms': 0.0,
            'lock_wait_ms': 0.3,
            'tokenize_ms': 2.1,
            'prefill_ms': 0.0,
            'cache_copy_ms': 0.4,
            'generation_ms': 38.5,
            'first_token_ms': 11.0,
            'decode_after_first_token_ms': 27.5,
        },
        'raw_response': {
            'prefix_already_prepared': True,
            'reused_prefix_tokens': 96,
            'newly_submitted_tokens': 24,
        },
    }
    progress_msgs = []
    response = answer_selected_document(
        runtime,
        'Mã xác nhận là gì?',
        str(path),
        model_client=client,
        on_progress=progress_msgs.append,
    )
    assert response.error is None and response.answer == 'LOTUS-7319'
    assert any('Đã đọc trích đoạn selected.txt' in m for m in progress_msgs)
    assert response.turn_contract is not None
    assert response.turn_contract.proposed_by in ('selected_document_qa', 'provided_contract')
    assert [o.outcome_id for o in response.turn_contract.outcomes] == ['read_selected_doc', 'answer_from_excerpt']
    assert response.reconciliation is not None and response.reconciliation.all_satisfied
    assert response.qa_telemetry is not None
    assert response.qa_telemetry['first_token_ms'] == 11.0
    assert response.qa_telemetry['reused_prefix_tokens'] == 96
    assert response.qa_telemetry['newly_submitted_tokens'] == 24
    assert response.qa_telemetry['prefix_already_prepared'] is True
    assert response.qa_telemetry['model_calls'] == 1



@pytest.mark.parametrize('answer', ['WRONG-9999', 'Không đủ dữ kiện để trả lời.'])
def test_read_success_does_not_certify_answer_or_invent_page(env, answer):
    runtime, path, client = env
    client.chat_with_meta.return_value['message']['content'] = answer
    response = answer_selected_document(runtime, 'Mã xác nhận?', str(path), model_client=client)
    assert response.answer == answer
    assert response.answer_verification_status != 'PASS'
    assert not any(r.get('verifier') == 'document_grounding' and r.get('status') == 'PASS'
                   for r in response.verification_reports)
    assert all(not source.get('page') and not source.get('page_num') for source in response.sources)
    assert any(r.operation_name == 'read_document' and r.committed
               for r in response.execution_journal.receipts)


def test_agentic_expand_dispatches_when_initial_excerpt_lacks_terms(env):
    runtime, path, client = env
    # 3500 chars of introductory padding, followed by the target passage
    intro = "Phần mở đầu giới thiệu tổng quan không có thuật ngữ chuyên sâu. " * 50
    target_section = " Cơ chế Pareto Cascade tối ưu hóa chi phí định tuyến thích ứng cho các mô hình ngôn ngữ lớn."
    path.write_text(intro + target_section, encoding="utf-8")

    client.chat_with_meta.return_value['message']['content'] = "Pareto Cascade tối ưu hóa chi phí bằng định tuyến thích ứng."

    response = answer_selected_document(
        runtime,
        "Giải thích cơ chế Pareto Cascade trong văn bản này",
        str(path),
        model_client=client,
    )
    assert response.error is None
    # Verify that expand_document_context was dispatched as an agentic step
    step_tools = [s.tool_name for s in response.steps]
    assert "read_document" in step_tools
    assert "expand_document_context" in step_tools
    # Verify model prompt received the expanded snippet containing the target section
    called_messages = client.chat_with_meta.call_args.args[0]
    doc_msg = next(m['content'] for m in called_messages if 'Document excerpt' in m['content'])
    assert "Pareto Cascade" in doc_msg
