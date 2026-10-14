"""Real PDF fixtures and scripted orchestration; no model-quality measurement."""
import pytest
from pypdf import PdfWriter
from pypdf.constants import PageLabelStyle
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.kernel.capabilities import build_default_registry
from rat.kernel.contracts import ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.view_spec import StandardViewProvider, validate_view_spec


def write_pdf(path, texts, password=None):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream.set_data(f'BT /F1 12 Tf 40 750 Td ({escaped}) Tj ET'.encode('latin-1'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    writer.set_page_label(0, len(texts) - 1, style=PageLabelStyle.DECIMAL, prefix='Book-', start=1)
    if password:
        writer.encrypt(password)
    with path.open('wb') as output:
        writer.write(output)


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'DSA book.pdf'
    texts = ['Introduction'] * 30
    texts[0] = ''
    texts[1] = 'Binary-search halves a sorted array.'
    texts[28] = 'Thuat toan tim kiem. Binary search uses a loop.'
    texts[29] = 'Binary search uses log n comparisons. Binary search is fast.'
    write_pdf(path, texts)
    db = Database(str(tmp_path / 'index.db'))
    db.upsert_document({'file_path': str(path), 'file_name': path.name,
                        'file_ext': '.pdf', 'file_size': path.stat().st_size,
                        'created_at': 1, 'modified_at': 1, 'indexed_at': 1,
                        'content_text': 'Only the first indexed pages. DSA book.'})
    registry = build_default_registry(db=db)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)
    yield path, texts, db, registry, store, dispatcher
    db.get_connection().close()


def search(env, **overrides):
    path, _, _, _, _, dispatcher = env
    return dispatcher.execute_operation('search_book_pages',
                                        {'file_path': str(path), 'query': 'binary search', **overrides})


def test_search_finds_actual_late_pages_and_cites_exact_excerpts(env):
    result = search(env)
    assert result.status == 'success', result.error
    payload = result.artifact.payload
    assert [item['page'] for item in payload['items']] == [30, 2, 29]
    assert payload['searched_range'] == [1, 30] and payload['next_start_page'] is None
    assert payload['textless_pages'] == [1] and payload['matched_pages'] == 3
    for item in payload['items']:
        assert item['snippet'].strip() in env[1][item['page'] - 1]
        assert item['page_label'] == f"Book-{item['page']}"
        assert item['path'] == str(env[0]) and item['page_numbering'] == 'pdf_1_based'
    view = StandardViewProvider(env[3]).provide_view(result.artifact)
    assert validate_view_spec(view, result.artifact, env[3]) == (True, None)
    table = next(block for block in view.blocks if block.type == 'table')
    assert table.data['rows'][0][0] == 30


def test_accent_insensitive_words_and_zero_matches(env):
    result = search(env, query='THUẬT TOÁN')
    assert [item['page'] for item in result.result['items']] == [29]
    result = search(env, query='art')  # A substring of "array" must not count as a word.
    assert result.status == 'success' and result.result['items'] == []
    assert result.result['matched_pages'] == 0


def test_bounded_search_reports_unsearched_range_and_result_limit(env):
    first = search(env, max_pages=2)
    assert first.result['searched_range'] == [1, 2] and first.result['next_start_page'] == 3
    action = env[3].actions_for(first.artifact)[-1]
    assert action.operation_name == 'search_book_pages'
    continued = env[5].dispatch(action)
    assert continued.status == 'success' and continued.result['searched_range'] == [3, 4]
    rest = search(env, start_page=3, limit=1)
    assert rest.result['matched_pages'] == 2 and rest.result['results_truncated']
    assert rest.result['items'][0]['page'] == 30 and rest.result['next_start_page'] is None


def test_exact_page_action_reads_a_citable_page_and_preserves_search(env):
    result = search(env)
    registry, store, dispatcher = env[3:]
    actions = registry.actions_for(result.artifact)
    assert actions[0].params == {'file_path': str(env[0]), 'page': 30}
    read = dispatcher.dispatch(actions[0])
    assert read.status == 'success', read.error
    assert read.artifact.kind == 'book_page_content' and read.result['page'] == 30
    assert read.result['content'] == env[1][29]
    assert read.result['citation']['page_label'] == 'Book-30'
    assert store.get(result.artifact.id) == result.artifact
    assert validate_view_spec(StandardViewProvider(registry).provide_view(read.artifact),
                              read.artifact, registry) == (True, None)
    short = dispatcher.execute_operation('read_book_page',
                                        {'file_path': str(env[0]), 'page': 30, 'max_chars': 10})
    assert short.result['truncated'] and short.result['content'] == env[1][29][:10]


@pytest.mark.parametrize('page', [1, 31])
def test_blank_and_out_of_range_pages_fail_without_publishing_content(env, page):
    result = env[5].execute_operation('read_book_page', {'file_path': str(env[0]), 'page': page})
    assert result.status == 'error' and result.artifact is None
    assert not env[4].find_by_kind('book_page_content')


def test_unindexed_and_password_protected_pdf_fail_truthfully(env, tmp_path):
    private = tmp_path / 'private.pdf'
    write_pdf(private, ['Binary search'], password='secret')
    args = {'file_path': str(private), 'query': 'binary'}
    result = env[5].execute_operation('search_book_pages', args)
    assert result.status == 'error' and 'chỉ mục' in result.error
    env[2].upsert_document({'file_path': str(private), 'file_name': private.name, 'file_ext': '.pdf',
                           'file_size': private.stat().st_size, 'created_at': 1, 'modified_at': 1,
                           'indexed_at': 1})
    result = env[5].execute_operation('search_book_pages', args)
    assert result.status == 'error' and 'mật khẩu' in result.error
    assert not env[4].list()


def test_cancel_during_page_search_commits_nothing(env):
    calls = []
    def cancel_after_two_checks():
        calls.append(True)
        return len(calls) > 2
    result = env[5].execute_operation('search_book_pages',
                                     {'file_path': str(env[0]), 'query': 'binary'},
                                     context={'should_cancel': cancel_after_two_checks})
    assert result.status == 'cancelled' and not env[4].list()


def test_malformed_pdf_fails_and_empty_queries_are_rejected(env):
    env[0].write_bytes(b'not a pdf')
    result = search(env)
    assert result.status == 'error' and not env[4].list()
    result = search(env, query='   ')
    assert result.status == 'error'


def test_scripted_search_read_compose_and_note_share_the_runtime(env):
    runtime = AssistantRuntime(db=env[2], registry=env[3], artifact_store=env[4],
                               dispatcher=env[5], use_live_model=False, plan_tasks=False)
    def decide(goal, steps):
        if not steps:
            return ModelDecision('', tool_name='search_book_pages',
                                 tool_args={'file_path': str(env[0]), 'query': 'binary search'})
        if len(steps) == 1:
            return ModelDecision('', tool_name='read_book_page',
                                 tool_args={'file_path': str(env[0]), 'page': 30})
        page = env[4].find_by_kind('book_page_content')[0]
        if len(steps) == 2:
            return ModelDecision('', tool_name='record_work_note', tool_args={
                'text': page.payload['content'], 'source_result': {
                    'artifact_id': page.id, 'revision': 1, 'field': 'content'}})
        if len(steps) == 3:
            found = env[4].find_by_kind('book_page_search')[0]
            def ref(artifact, field):
                return {'artifact_id': artifact.id, 'revision': artifact.revision, 'field': field}
            return ModelDecision('', tool_name='compose_result_table', tool_args={
                'title': 'Các trang về binary search', 'headers': ['Trang PDF', 'Trích đoạn'],
                'rows': [[ref(found, 'items.0.page'), ref(found, 'items.0.snippet')],
                         [ref(page, 'page'), ref(page, 'content')]]})
        return ModelDecision('', final_answer='Đã tìm và đọc trang PDF 30, lưu trích dẫn và ghép bảng.')
    runtime.model_callable = decide
    response = runtime.run('Tìm trang về binary search, đọc trang và ghi trích dẫn rồi so sánh.')
    assert response.error is None
    assert {a.kind for a in response.artifacts} >= {'book_page_search', 'book_page_content', 'result_table'}
    note = runtime.notebook.snapshot()[0]
    assert note['confirmed'] and note['text'] == env[1][29]
    table = env[4].find_by_kind('result_table')[0]
    assert table.payload['rows'][1] == [30, env[1][29]]
