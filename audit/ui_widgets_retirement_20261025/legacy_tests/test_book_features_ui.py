"""Actual Qt rendering/actions for book tools; fixtures do not assess the model."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTextBrowser

from rat.ui.assistant_presenter import source_panel
from tests.test_book_pages import env, search


@pytest.fixture(autouse=True)
def developer_controls(monkeypatch):
    monkeypatch.setenv('RAT_DEBUG_UI', '1')


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


def test_page_result_menu_dispatches_exact_page_in_the_same_panel(app, env):
    result = search(env)
    captured = []
    panel = source_panel([], artifacts=[result.artifact], registry=env[3],
                         on_action=lambda action, inputs: captured.append((action, inputs)))
    assert panel.covers_documents
    renderer = panel.renderers[result.artifact.id]
    menu = next(button.menu() for button in renderer.findChildren(QPushButton) if button.menu())
    menu.actions()[0].trigger()
    action, inputs = captured[0]
    assert action.params == {'file_path': str(env[0]), 'page': 30}
    read = env[5].dispatch(action, inputs)
    assert read.status == 'success'
    panel.update_artifacts([result.artifact, read.artifact])
    assert panel.renderers[result.artifact.id] is renderer
    browsers = panel.renderers[read.artifact.id].findChildren(QTextBrowser)
    assert any(browser.toPlainText() == env[1][29] for browser in browsers)
    panel.close()


def test_table_headers_and_source_text_render_without_html(app, env):
    result = search(env)
    def ref(field):
        return {'artifact_id': result.artifact.id, 'revision': 1, 'field': field}
    table = env[5].execute_operation('compose_result_table', {
        'title': 'Đối chiếu trang sách', 'headers': ['<b>Trang PDF</b>', 'Trích đoạn'],
        'rows': [[ref('items.0.page'), ref('items.0.snippet')]]})
    panel = source_panel([], artifacts=[table.artifact], registry=env[3])
    labels = panel.findChildren(QLabel)
    header = next(label for label in labels if label.text() == '<b>Trang PDF</b>')
    assert header.textFormat() == Qt.TextFormat.PlainText
    assert any(label.text() == '30' for label in labels)
    assert any(result.artifact.title in browser.toPlainText() for browser in panel.findChildren(QTextBrowser))
    panel.close()


def test_compact_full_retains_open_page_content(app, env):
    result = env[5].execute_operation('read_book_page', {'file_path': str(env[0]), 'page': 30})
    panel = source_panel([], artifacts=[result.artifact], registry=env[3])
    renderer = panel.renderers[result.artifact.id]
    disclosure = renderer.disclosures['Nội dung trang']
    disclosure.set_open(True, animate=False)
    renderer.set_compact(False)
    renderer.set_compact(True)
    assert disclosure.opened
    assert any(browser.toPlainText() == env[1][29] for browser in renderer.findChildren(QTextBrowser))
    panel.close()
