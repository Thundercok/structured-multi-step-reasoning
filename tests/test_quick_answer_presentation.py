"""Presentation contracts on authored content; no model or quality evaluation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from html.parser import HTMLParser
from pathlib import Path
import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QPointF, QUrl, Qt
from PyQt6.QtGui import QFont, QGuiApplication, QTextDocument
from PyQt6.QtQuick import QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from rat.ui.answer_presentation import answer_html, source_rows
from rat.ui.chat_session import ConversationHistory
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from rat.engine.assistant_runtime import AgentResponse
from tests.test_quick_pdf import click, wait_for
from tests.test_selected_pdf import write_pdf


_APPLICATION = None


@pytest.fixture(scope='module')
def app():
    # Keep one Qt application alive across the subsequent UI test modules.
    global _APPLICATION
    _APPLICATION = QGuiApplication.instance() or QApplication([])
    return _APPLICATION


def test_answer_formatting_keeps_content_and_never_creates_resource_elements(app):
    raw = '# Tiêu đề\n\n**Ý chính** và `mid + 1`.\n\n3. Bước ba\n9. Bước chín\n\n```python\nif a < b:\n    print("<safe>")\n```\n\n<img src="file:///private/secret">\n![ảnh](https://example.invalid/image.png)'
    rendered = answer_html(raw)
    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []
        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
    tags = Tags()
    tags.feed(rendered)
    assert not {'img', 'a', 'script', 'iframe', 'object'}.intersection(tags.tags)
    doc = QTextDocument()
    body_font = QFont()
    body_font.setPixelSize(14)
    doc.setDefaultFont(body_font)
    doc.setHtml(rendered)
    plain = doc.toPlainText()
    for content in ['Tiêu đề', 'Ý chính', 'mid + 1', '3. Bước ba', '9. Bước chín', 'if a < b:', 'print("<safe>")', '<img src="file:///private/secret">']:
        assert content in plain
    assert '**Ý chính**' not in plain
    assert not doc.find('Tiêu đề').isNull()
    title_font = doc.find('Tiêu đề').charFormat().font().resolve(body_font)
    assert title_font.pixelSize() > body_font.pixelSize()


def test_source_pages_are_explicit_and_scoped_to_the_selected_pdf(tmp_path):
    path = tmp_path / 'source.pdf'
    rows = source_rows([
        {'file_path': str(path), 'file_name': 'Source', 'page': 3},
        {'path': str(path)},
        {'path': str(path), 'page_num': True},
        {'path': str(path), 'page': 99},
        {'path': str(tmp_path / 'other.pdf'), 'page': 2},
        {'path': 'bad\x00path', 'provenance': []},
    ], path, 4)
    assert rows[0]['canOpen'] and rows[0]['page'] == 3
    assert rows[1]['page'] == 0 and not rows[1]['canOpen']
    assert rows[2]['page'] == 0 and not rows[2]['canOpen']
    assert not rows[3]['canOpen'] and not rows[4]['canOpen'] and not rows[5]['canOpen']


def complete_fixture(controller, query, answer, sources, verification='UNKNOWN'):
    turn = controller.conversation.begin_turn(query)
    controller._current_turn_id = turn.turn_id
    controller._current_execution_id = turn.execution_id
    controller._current_worker = object()  # Ownership only; no background/model worker.
    controller._last_user_query = query
    controller._on_execution_response(AgentResponse(
        answer, [], 0, 0, 0, sources=sources, execution_id=turn.execution_id,
        answer_verification_status=verification,
    ))
    return turn.turn_id


def test_source_history_follows_the_displayed_turn_and_rejects_stale_response(app):
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        refs = [{'path': '/tmp/first.pdf', 'page': 3}]
        first = complete_fixture(controller, 'First', 'One', refs, 'FAIL')
        refs[0]['page'] = 99
        second = complete_fixture(controller, 'Second', 'Two', [])
        assert controller.snapshot['answerSources'] == []
        assert controller.navigateToTurn(first)
        assert controller.snapshot['answerSources'][0]['page'] == 3
        assert controller.snapshot['answerVerification'] == 'FAIL'
        assert controller.navigateToTurn(second)
        assert controller.snapshot['answerSources'] == []
        assert controller.snapshot['answerVerification'] == 'UNKNOWN'
        controller._on_execution_response(AgentResponse('late', [], 0, 0, 0, execution_id='stale', sources=refs))
        assert controller.snapshot['answerText'] == 'Two'
    finally:
        controller.close()


@pytest.mark.parametrize('outcome', ['timeout', 'budget_exceeded', 'cancelled', 'unresolved'])
def test_incomplete_answers_have_an_incomplete_history_state(app, outcome):
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        turn = controller.conversation.begin_turn('A request that cannot finish')
        controller._current_turn_id = turn.turn_id
        controller._current_execution_id = turn.execution_id
        controller._current_worker = object()
        controller._on_execution_response(AgentResponse(
            'Partial output', [], 0, 0, 0,
            error=outcome, execution_id=turn.execution_id,
        ))
        recorded = controller.conversation.get_turn(turn.turn_id)
        assert recorded.status == ('cancelled' if outcome == 'cancelled' else 'failed')
        assert recorded.answer == 'Partial output'
        assert controller.snapshot['answerVerification'] == 'UNKNOWN'
        assert not controller.snapshot['busy']
    finally:
        controller.close()


@pytest.mark.parametrize('width,dark', [(520, False), (520, True), (700, False), (700, True)])
def test_answer_copy_and_source_page_journey(app, tmp_path, width, dark):
    path = write_pdf(tmp_path / 'Source.pdf', ['Page one', 'Actual evidence on page two', 'Page three'])
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    controller.selectFile(str(path))
    wait_for(lambda: not controller.snapshot['busy'])
    original = '**Kết quả**\n\n`value = 2`'
    complete_fixture(controller, 'Đọc nguồn', original, [
        {'path': str(path), 'page': 2}, {'path': str(path)},
    ])
    copied = []
    controller.copyReady.connect(copied.append)
    view = QQuickView()
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({'liveController': controller, 'reduceMotion': True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]
    root = view.rootObject()
    view.resize(width, 550)
    timer = bind_desk_window(view)
    view.show()
    try:
        QTest.qWait(60)
        root.setProperty('darkMode', dark)
        QTest.qWait(20)
        answer_item = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'answerText')
        code_format = answer_item.property('textDocument').textDocument().find('value = 2').charFormat()
        assert code_format.background().color().name() == ('#333b2f' if dark else '#eff3e9')
        menu = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'documentMenu')
        composer = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'composer')
        chip = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'contextChip')
        assert menu.isVisible() and menu.width() < chip.width() <= composer.width() - 28
        paper = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'resultPaper')
        assert abs(paper.mapToScene(QPointF(paper.width(), 0)).x() - composer.mapToScene(QPointF(composer.width(), 0)).x()) <= 1
        click(view, root, 'copyCitation')
        assert copied[-1] == original  # Markdown source is copied in full, not normalized HTML.
        click(view, root, 'documentMenu')
        assert controller._page is None  # Merely opening the picker is never a page-1 citation.
        popup = root.findChild(__import__('PyQt6.QtCore', fromlist=['QObject']).QObject, 'documentPopup')
        QMetaObject.invokeMethod(popup, 'close')
        QTest.qWait(20)
        click(view, root, 'answerSourcesToggle')
        assert root.property('answerSourcesOpen')
        editor = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'draftEditor')
        editor.setProperty('text', 'Câu hỏi tiếp theo chưa gửi')
        answer_item.select(0, 3)
        selected = answer_item.property('selectedText')
        anchor = view.y() + composer.mapToScene(QPointF(0, composer.height())).y()
        click(view, root, 'liveFoldButton')
        assert not paper.isVisible() and chip.isVisible() and menu.isVisible()
        assert view.height() < 310
        # PDF controls still work in the mode users spend most of their time in.
        click(view, root, 'documentMenu')
        assert popup.property('visible')
        QTest.keyClick(view, Qt.Key.Key_Escape)
        QTest.qWait(20)
        assert not popup.property('visible')
        click(view, root, 'notice')
        assert paper.isVisible() and root.property('answerSourcesOpen')
        assert answer_item.property('selectedText') == selected
        assert editor.property('text') == 'Câu hỏi tiếp theo chưa gửi'
        assert abs(view.y() + composer.mapToScene(QPointF(0, composer.height())).y() - anchor) <= 1
        assert not controller.openAnswerSource(1)  # Missing page never defaults to 1.
        click(view, root, 'openAnswerSource_0')
        wait_for(lambda: not controller.snapshot['busy'])
        assert controller.snapshot['pageNumber'] == 2
        assert 'Actual evidence' in controller.snapshot['pageText']
        assert warnings == []
    finally:
        timer.stop()
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize('width', [520, 700])
def test_long_answer_question_and_reading_position_survive_fold(app, tmp_path, width):
    from PyQt6.QtQuick import QQuickItem
    path = write_pdf(tmp_path / ('Quy chế học vụ và hướng dẫn đăng ký tín chỉ năm học 2026–2027.pdf'), ['Authored notes'])
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    controller.selectFile(str(path))
    wait_for(lambda: not controller.snapshot['busy'])
    query = 'Giải thích điều kiện áp dụng và đưa ví dụ cụ thể cho các trường hợp dữ liệu có phần tử trùng lặp. ' * 3
    raw = '## Ý chính\n\n' + ('Một đoạn văn tự soạn đủ dài để kiểm tra cuộn và chuyển chế độ.\n\n' * 35)
    complete_fixture(controller, query, raw, [{'path': str(path), 'page': 1}])
    view = QQuickView()
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({'liveController': controller, 'reduceMotion': True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(width, 550)
    timer = bind_desk_window(view)
    view.show()
    try:
        QTest.qWait(80)
        question = root.findChild(QQuickItem, 'answerQuestion')
        short_height = question.height()
        click(view, root, 'answerQuestion')
        assert question.height() > short_height and root.property('answerQuestionOpen')
        assert question.property('contentItem').property('text') == query
        chip = root.findChild(QQuickItem, 'contextChip')
        composer = root.findChild(QQuickItem, 'composer')
        assert chip.width() <= composer.width() - 28
        scroller = root.findChild(QQuickItem, 'resultScroll').property('contentItem')
        assert scroller.property('contentHeight') > scroller.height()
        scroller.setProperty('contentY', 220)
        QTest.qWait(30)
        position = scroller.property('contentY')
        assert position > 0
        click(view, root, 'liveFoldButton')
        click(view, root, 'notice')
        assert abs(scroller.property('contentY') - position) <= 1
        assert root.property('answerQuestionOpen')
        assert controller.snapshot['answerText'] == raw
        assert warnings == []
    finally:
        timer.stop()
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
