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
from PyQt6.QtGui import QGuiApplication
from rat.ui.answer_presentation import answer_html, source_rows
from rat.ui.chat_session import ConversationHistory
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from rat.engine.assistant_runtime import AgentResponse
from tests.test_quick_pdf import click, wait_for, find_item
from tests.test_selected_pdf import write_pdf


_APPLICATION = None


@pytest.fixture(scope='module')
def app():
    # Keep one Qt application alive across the subsequent UI test modules.
    global _APPLICATION
    _APPLICATION = QGuiApplication.instance() or QGuiApplication([])
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


def test_answer_html_renders_tables_blockquotes_and_code_cards_without_resource_tags(app):
    raw = (
        "## Bảng tổng hợp\n\n"
        "| Tiêu chí | Học kỳ chính | Học kỳ hè |\n"
        "| :--- | :---: | ---: |\n"
        "| Tín chỉ tối đa | **24** | `12` |\n\n"
        "> Lưu ý *quan trọng*: kiểm tra điều kiện tiên quyết.\n\n"
        "```python\ndef check_limit(credits: int) -> bool:\n    return credits <= 24\n```"
    )
    for dark in (False, True):
        rendered = answer_html(raw, dark=dark)
        assert "<table" in rendered and "<th" in rendered and "<td" in rendered
        assert "PYTHON" in rendered
        for forbidden in ("<img", "<a ", "<script", "<iframe", "<object"):
            assert forbidden not in rendered.lower()
        doc = QTextDocument()
        doc.setHtml(rendered)
        plain = doc.toPlainText()
        for expected in ("Bảng tổng hợp", "Tiêu chí", "Học kỳ chính", "24", "12", "Lưu ý quan trọng", "def check_limit"):
            assert expected in plain


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


def test_pdf_source_reference_labels_with_section_and_missing_pages(tmp_path):
    path = tmp_path / 'Source.pdf'
    rows = source_rows([
        # 1. Page with section metadata
        {'path': str(path), 'page': 3, 'section': '3. Phương pháp nghiên cứu'},
        # 2. Page with section_title in provenance
        {'path': str(path), 'page': 5, 'provenance': {'section_title': 'Kết quả thực nghiệm'}},
        # 3. Page without section metadata -> never defaults to Abstract
        {'path': str(path), 'page': 1},
        # 4. Missing page number -> Chưa xác định trang, never defaults to 1
        {'path': str(path), 'section': 'Tổng quan'},
        {'path': str(path)},
        # 5. Invalid page number (0 or bool)
        {'path': str(path), 'page': 0},
        {'path': str(path), 'page_num': True},
    ], path, 10)

    assert rows[0]['label'] == 'Trang 3 · 3. Phương pháp nghiên cứu'
    assert rows[0]['section'] == '3. Phương pháp nghiên cứu'
    assert rows[0]['canOpen'] is True

    assert rows[1]['label'] == 'Trang 5 · Kết quả thực nghiệm'
    assert rows[1]['section'] == 'Kết quả thực nghiệm'
    assert rows[1]['canOpen'] is True

    assert rows[2]['label'] == 'Trang 1'
    assert rows[2]['section'] == ''
    assert 'Abstract' not in rows[2]['label']
    assert rows[2]['canOpen'] is True

    assert rows[3]['label'] == 'Chưa xác định trang'
    assert rows[3]['page'] == 0
    assert rows[3]['canOpen'] is False

    assert rows[4]['label'] == 'Chưa xác định trang'
    assert rows[4]['page'] == 0
    assert rows[4]['canOpen'] is False

    assert rows[5]['label'] == 'Chưa xác định trang'
    assert rows[5]['page'] == 0
    assert rows[5]['canOpen'] is False

    assert rows[6]['label'] == 'Chưa xác định trang'
    assert rows[6]['page'] == 0
    assert rows[6]['canOpen'] is False


def test_qml_source_reference_button_text_and_disabled_state(app, tmp_path):
    from PyQt6.QtQuick import QQuickItem, QQuickView
    from PyQt6.QtCore import QUrl
    from rat.ui.quick_app import bind_desk_window
    
    path = write_pdf(tmp_path / 'Doc.pdf', ['Page 1', 'Page 2'])
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    controller.selectFile(str(path))
    wait_for(lambda: not controller.snapshot['busy'])
    complete_fixture(controller, 'Hỏi', 'Đáp', [
        {'path': str(path), 'page': 2, 'section': 'Phương pháp'},
        {'path': str(path)},  # missing page
    ])
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({'liveController': controller, 'reduceMotion': True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(600, 550)
    timer = bind_desk_window(view)
    view.show()
    try:
        QTest.qWait(50)
        click(view, root, 'answerSourcesToggle')
        QTest.qWait(50)
        btn0 = find_item(root, 'openAnswerSource_0')
        btn1 = find_item(root, 'openAnswerSource_1')
        assert btn0 is not None and btn0.isVisible()
        assert btn0.property('text') == 'Trang 2 · Phương pháp'
        assert btn0.property('enabled') is True
        
        assert btn1 is not None and btn1.isVisible()
        assert btn1.property('text') == 'Chưa xác định trang'
        assert btn1.property('enabled') is False
        assert not controller.openAnswerSource(1)
    finally:
        timer.stop()
        controller.close()
        view.close()


def complete_fixture(controller, query, answer, sources, verification='UNKNOWN', expanded=True):
    turn = controller.conversation.begin_turn(query)
    controller._current_turn_id = turn.turn_id
    controller._current_execution_id = turn.execution_id
    controller._current_worker = object()  # Ownership only; no background/model worker.
    controller._last_user_query = query
    controller._on_execution_response(AgentResponse(
        answer, [], 0, 0, 0, sources=sources, execution_id=turn.execution_id,
        answer_verification_status=verification,
    ))
    if expanded:
        controller.setExpanded(True)
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
        doc_label = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'answerDocumentLabel')
        assert doc_label is not None and doc_label.isVisible()
        assert doc_label.property('text') == 'Source.pdf'

        # Information Evidence Sheet verification (Build 2026.10.25.18)
        process_card = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'evidenceProcessCard')
        assert process_card is not None and process_card.isVisible()
        source_card = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'evidenceSourceCard')
        assert source_card is not None and source_card.isVisible()
        source_title = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'evidenceSourceTitle')
        assert source_title is not None and 'Source.pdf' in source_title.property('text')
        source_snippet = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'evidenceSourceSnippet')
        assert source_snippet is not None and source_snippet.isVisible()
        copy_btn = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'copyCitationButton')
        assert copy_btn is not None and copy_btn.isVisible()
        open_ext_btn = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'openExternalPdfButton')
        assert open_ext_btn is not None and open_ext_btn.isVisible()
        expand_btn = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'expandContextButton')
        assert expand_btn is not None and expand_btn.isVisible()

        # Toggle expanded context
        assert not root.property('contextExpanded')
        click(view, root, 'expandContextButton')
        assert root.property('contextExpanded')
        click(view, root, 'expandContextButton')
        assert not root.property('contextExpanded')

        # Toggle process details
        assert not root.property('processDetailsOpen')
        click(view, root, 'processDetailsToggle')
        assert root.property('processDetailsOpen')
        details_content = root.findChild(__import__('PyQt6.QtQuick', fromlist=['QQuickItem']).QQuickItem, 'processDetailsContent')
        assert details_content is not None and details_content.isVisible()
        click(view, root, 'processDetailsToggle')
        assert not root.property('processDetailsOpen')

        # Click copy citation button
        click(view, root, 'copyCitationButton')
        assert root.property('sourceCopied') is True

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
        wait_for(lambda: controller.snapshot['view'] == 'page')
        assert controller.snapshot['canBackToAnswer']
        click(view, root, 'backToAnswer')
        assert controller.snapshot['view'] == 'answer'
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
        # PDF controls still work in the mode users spend most of their time in: clicking chip returns to page.
        click(view, root, 'documentMenu')
        wait_for(lambda: controller.snapshot['view'] == 'page')
        assert paper.isVisible()
        click(view, root, 'backToAnswer')
        assert controller.snapshot['view'] == 'answer'
        assert paper.isVisible() and root.property('answerSourcesOpen')
        assert answer_item.property('selectedText') == selected
        assert editor.property('text') == 'Câu hỏi tiếp theo chưa gửi'
        assert abs(view.y() + composer.mapToScene(QPointF(0, composer.height())).y() - anchor) <= 1
        assert not controller.openAnswerSource(1)  # Missing page never defaults to 1.
        click(view, root, 'openAnswerSource_0')
        wait_for(lambda: not controller.snapshot['busy'])
        assert controller.snapshot['pageNumber'] == 2
        assert 'Actual evidence' in controller.snapshot['pageText']
        assert controller.snapshot['canBackToAnswer']
        click(view, root, 'backToAnswer')
        assert controller.snapshot['view'] == 'answer'
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
