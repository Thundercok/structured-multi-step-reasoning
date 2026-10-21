"""Cache ownership and real indexed-read integration; no MLX/model required."""
from types import SimpleNamespace

import pytest

from rat.engine.mlx_document_session import MLXDocumentSession


class Tokenizer:
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, enable_thinking):
        assert tokenize and enable_thinking is False
        text = ''.join(m['role'] + ':' + m['content'] + '\n' for m in messages)
        return list(text.encode()) + ([255] if add_generation_prompt else [])


class Backend:
    def __init__(self):
        self.loads = self.prefills = self.clears = 0
        self.generations = []
        self.answer = 'LOTUS-7319'
        self.finish = 'stop'

    def load(self, path):
        self.loads += 1
        return object(), Tokenizer()

    def prepare(self, model, tokens, check=None):
        if check:
            check()
        self.prefills += 1
        return {'tokens': list(tokens)}

    def generate(self, model, tokenizer, tokens, cache, max_tokens, check):
        check()
        self.generations.append((list(tokens), list(cache['tokens'])))
        cache['tokens'].append(-1)
        yield SimpleNamespace(text=self.answer, generation_tokens=7, finish_reason=self.finish)

    def clear(self):
        self.clears += 1


@pytest.fixture
def session(tmp_path):
    model = tmp_path / 'model'
    model.mkdir()
    for name in ('config.json', 'tokenizer.json', 'weights.safetensors'):
        (model / name).write_text('{}')
    backend = Backend()
    client = MLXDocumentSession(model, _backend_factory=lambda: backend)
    yield client, backend
    client.close()


def messages(document='document data', question='question'):
    return [{'role': 'system', 'content': 'Use provided text.'},
            {'role': 'user', 'content': document}, {'role': 'user', 'content': question}]


def test_requires_local_files_before_importing_native_runtime(tmp_path):
    with pytest.raises(ValueError, match='complete_local_directory'):
        MLXDocumentSession('mlx-community/not-a-local-directory')
    with pytest.raises(ValueError, match='complete_local_directory'):
        MLXDocumentSession(tmp_path)


def test_load_once_prepare_once_and_copy_prefix_for_each_question(session):
    client, backend = session
    assert client.chat_with_meta(messages(), [])['error'] == 'native_model_not_loaded'
    client.load()
    client.load()
    client.prepare_context(messages()[:-1])
    chunks = []
    first = client.chat_with_meta(messages(), [], on_text=chunks.append)
    second = client.chat_with_meta(messages(question='another question'), [])
    assert first['error'] is second['error'] is None
    assert backend.loads == 1 and backend.prefills == 1 and len(backend.generations) == 2
    assert chunks == ['LOTUS-7319']
    assert backend.generations[0][1] == backend.generations[1][1]
    assert -1 not in backend.generations[1][1]
    assert first['prompt_tokens'] == len(Tokenizer().apply_chat_template(messages(), tokenize=True,
        add_generation_prompt=True, enable_thinking=False))
    assert first['raw_response']['prefix_already_prepared']


def test_changed_document_invalidates_context_and_generates_new_answer(session):
    client, backend = session
    client.load()
    first = client.chat_with_meta(messages(), [])
    backend.answer = 'NEW-ANSWER'
    second = client.chat_with_meta(messages(document='new document'), [])
    assert backend.prefills == 2 and len(backend.generations) == 2
    assert first['message']['content'] == 'LOTUS-7319'
    assert second['message']['content'] == 'NEW-ANSWER'
    assert backend.generations[0][1] != backend.generations[1][1]


@pytest.mark.parametrize('options,error', [
    ({'tools': [{'type': 'function'}]}, 'does_not_support_agent_protocol'),
    ({'thinking': True}, 'does_not_support_agent_protocol'),
    ({'response_format': {'type': 'object'}}, 'does_not_support_agent_protocol'),
    ({'max_tokens': 5000}, 'context_too_large'),
    ({'max_tokens': 0}, 'generation_budget'),
    ({'should_cancel': lambda: True}, 'cancelled'),
])
def test_rejected_request_never_prefills_or_generates(session, options, error):
    client, backend = session
    client.load()
    meta = client.chat_with_meta(messages(), **({'tools': []} | options))
    assert error in meta['error'] and meta['message'] == {}
    assert backend.prefills == 0 and not backend.generations


def test_truncation_is_an_error_and_close_releases_session(session):
    client, backend = session
    client.load()
    backend.finish = 'length'
    meta = client.chat_with_meta(messages(), [])
    assert meta['error'] == 'native_document_output_truncated'
    client.close()
    assert not client.is_loaded and backend.clears == 1


def test_cancelled_answer_cannot_pollute_next_question_cache(session):
    client, backend = session
    client.load()
    cancelled = [False]
    result = client.chat_with_meta(messages(), [], should_cancel=lambda: cancelled[0],
        on_text=lambda _: cancelled.__setitem__(0, True))
    assert result['error'] == 'cancelled' and result['message'] == {}
    next_result = client.chat_with_meta(messages(question='new question'), [])
    assert next_result['error'] is None and backend.prefills == 1
    assert -1 not in backend.generations[-1][1]


def test_failed_new_document_preparation_drops_old_context(session):
    client, backend = session
    client.load()
    assert client.chat_with_meta(messages(), [])['error'] is None
    prepare = backend.prepare
    def fail(*args):
        raise RuntimeError('prefill interrupted')
    backend.prepare = fail
    assert client.chat_with_meta(messages(document='different text'), [])['error'] == 'prefill interrupted'
    backend.prepare = prepare
    assert client.chat_with_meta(messages(), [])['error'] is None
    assert backend.prefills == 2


def test_selected_document_runtime_uses_native_session_after_real_read(session, tmp_path):
    from rat.crawler.db import Database
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.engine.selected_document_qa import answer_selected_document, selected_document_messages, MAX_READ_CHARS
    from rat.timetable.compositor import TimetableCompositor

    client, backend = session
    client.load()
    path = tmp_path / 'selected.txt'
    path.write_text('Mã xác nhận: LOTUS-7319.\n')
    database = Database(str(tmp_path / 'index.db'))
    database.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext='.txt',
        file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
        content_text=path.read_text()))
    try:
        runtime = AssistantRuntime(db=database, compositor=TimetableCompositor([]), use_live_model=True)
        read = runtime.registry.execute('read_document', {'file_path': str(path), 'max_chars': MAX_READ_CHARS})
        assert read['content'] != path.read_text()
        client.prepare_context(selected_document_messages('', read, path.name)[:-1])
        for question in ('Mã xác nhận?', 'Confirmation code?'):
            calls = []
            response = answer_selected_document(runtime, question, str(path), model_client=client,
                                                on_model_call=calls.append)
            assert response.error is None and response.answer == 'LOTUS-7319'
            assert calls[0]['raw_response']['prefix_already_prepared']
            assert any(s.get('path') == str(path) and s.get('read') for s in response.sources)
            assert any(r.operation_name == 'read_document' and r.committed
                       for r in response.execution_journal.receipts)
        assert backend.loads == 1 and backend.prefills == 1 and len(backend.generations) == 2
    finally:
        database.get_connection().close()
