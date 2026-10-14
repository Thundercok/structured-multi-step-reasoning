"""Source copying, lineage and revision limits for the RAT-AI-02 table slice."""
import sys
import subprocess

import pytest

from rat.kernel.capabilities import build_default_registry
from rat.kernel.contracts import Artifact, ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.view_spec import StandardViewProvider, validate_view_spec


@pytest.fixture
def env():
    registry, store = build_default_registry(), ArtifactStore()
    store.put(Artifact('book', 'book_page_search', payload={'items': [{'page': 30, 'snippet': 'Binary search'}]}, title='DSA book'))
    store.put(Artifact('schedule', 'schedule', payload={'items': [{'course_name': 'DSA', 'room': 'A101'}]}, title='Lịch học'))
    return registry, store, ActionDispatcher(registry, store)


def ref(artifact_id, field, revision=1):
    return {'artifact_id': artifact_id, 'revision': revision, 'field': field}


def compose(env, rows, headers=None):
    return env[2].execute_operation('compose_result_table', {
        'title': 'Bảng tham chiếu', 'headers': headers or ['Môn', 'Trang'], 'rows': rows})


def test_cross_domain_table_keeps_exact_data_and_per_cell_lineage(env):
    refs = [ref('schedule', 'items.0.course_name'), ref('book', 'items.0.page')]
    result = compose(env, [refs])
    assert result.status == 'success', result.error
    assert result.result['rows'] == [['DSA', 30]]
    assert len(result.result['source_refs']) == 2
    assert [[{k: cell[k] for k in ('artifact_id', 'revision', 'field')} for cell in row]
            for row in result.result['cell_refs']] == [refs]
    provider = StandardViewProvider(env[0])
    view = provider.provide_view(result.artifact)
    assert validate_view_spec(view, result.artifact, env[0]) == (True, None)
    assert next(b for b in view.blocks if b.type == 'table').data['rows'] == [['DSA', 30]]


@pytest.mark.parametrize('rows', [
    [[ref('missing', 'result'), ref('book', 'items.0.page')]],
    [[ref('book', 'items.0.page', 5), ref('book', 'items.0.page')]],
    [[ref('book', 'items.8.page'), ref('book', 'items.0.page')]],
    [[ref('book', 'items.-1.page'), ref('book', 'items.0.page')]],
    [[ref('book', 'items'), ref('book', 'items.0.page')]],
    [[ref('book', 'items.0.page')]],
    [['Invented', '999']],
    [[{'artifact_id': 'book', 'field': 'items.0.page'}, ref('book', 'items.0.page')]],
])
def test_invalid_or_invented_cells_cannot_publish_a_table(env, rows):
    result = compose(env, rows)
    assert result.status == 'error' and result.artifact is None
    assert not env[1].find_by_kind('result_table')


def test_historical_revision_is_explicit_and_snapshots_survive_source_updates(env):
    env[1].put(Artifact('book', 'book_page_search', revision=2, payload={'items': [{'page': 40}]}))
    result = compose(env, [[ref('book', 'items.0.page', 1), ref('book', 'items.0.page', 2)]])
    assert result.result['rows'] == [[30, 40]]
    assert result.result['source_refs'][0]['historical']
    env[1].put(Artifact('book', 'book_page_search', revision=3, payload={'items': [{'page': 50}]}))
    assert env[1].get(result.artifact.id).payload['rows'] == [[30, 40]]


def test_deleted_sources_fail_and_reset_cannot_reuse_refs(env):
    env[1].delete('book')
    result = compose(env, [[ref('book', 'items.0.page'), ref('schedule', 'items.0.room')]])
    assert result.status == 'error'
    env[2].reset()
    result = compose(env, [[ref('schedule', 'items.0.room'), ref('schedule', 'items.0.room')]])
    assert result.status == 'error' and not env[1].list()


@pytest.mark.parametrize('value', ['x' * 2001, float('nan')])
def test_excessive_text_and_non_finite_numbers_fail(env, value):
    env[1].put(Artifact('bad', 'example', payload={'value': value}))
    result = compose(env, [[ref('bad', 'value')]], headers=['Giá trị'])
    assert result.status == 'error' and not env[1].find_by_kind('result_table')


def test_new_operations_do_not_load_qt_pdf_parser_or_docai_at_startup():
    result = subprocess.run([sys.executable, '-c',
        'import sys; from rat.kernel.capabilities import build_default_registry; r = build_default_registry(); '
        'assert r.get_operation("search_book_pages") and r.get_operation("compose_result_table"); '
        'assert not any(n.startswith(("PyQt6", "pypdf", "modules.docai")) for n in sys.modules)'],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
