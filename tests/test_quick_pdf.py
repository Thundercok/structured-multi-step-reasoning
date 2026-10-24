"""Qt Quick journeys on authored PDF bytes, not a model or OCR quality study."""
import os
from pathlib import Path
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QUrl, Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from tests.test_selected_pdf import write_pdf

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    application = QGuiApplication.instance() or QGuiApplication([])
    application.setFont(QFont("Helvetica Neue", 13))
    yield application


def wait_for(predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < end, "Timed out waiting for PDF operation"
        QTest.qWait(10)
    QTest.qWait(20)


def find_item(root, name):
    item = root.findChild(QQuickItem, name)
    if item is not None:
        return item
    pending = list(root.childItems())
    while pending:
        candidate = pending.pop()
        if candidate.objectName() == name:
            return candidate
        pending.extend(candidate.childItems())
    return None


def click(view, root, name):
    item = find_item(root, name)
    assert item is not None and item.isVisible(), name
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    assert 0 <= point.x() <= view.width() and 0 <= point.y() <= view.height(), (name, point)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
    QTest.qWait(30)


@pytest.fixture
def controller(app):
    control = QuickPDFController(open_url=lambda url: True)
    control.ready()
    yield control
    control.close()
    control.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_real_qml_search_read_copy_back_error_and_draft(app, controller, tmp_path):
    path = write_pdf(tmp_path / "Tài liệu #1.pdf", [""] + ["Intro"] * 28 + ["Binary search uses log n comparisons. Binary search is fast."])
    copied = []
    controller.copyReady.connect(copied.append)
    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": controller, "reduceMotion": True,
                               "mascotSource": QUrl.fromLocalFile(str(PROJECT / "rat/assets/rat_mascot_cutout.png"))})
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]
    root = view.rootObject()
    view.resize(720, round(root.property("preferredWindowHeight")))
    view.setPosition(0, view.screen().availableGeometry().bottom() - view.height() - 32)
    resize_timer = bind_desk_window(view)
    view.show()
    try:
        QTest.qWait(30)
        composer = root.findChild(QQuickItem, "composer")
        anchor = view.y() + composer.mapToScene(QPointF(0, composer.height())).y()
        assert view.height() < 310
        # The software offscreen grab is RGB32 even for a translucent surface.
        assert root.property("color").alpha() == 0 and view.color().alpha() == 0
        send_text = root.findChild(QQuickItem, "sendButton").property("contentItem")
        assert send_text.property("color").name() == "#fafcf5"
        capture = os.environ.get("RAT_QUICK_CAPTURE_DIR")
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
            assert view.grabWindow().save(str(Path(capture) / "pdf-simple.png"))
        controller.selectFile(QUrl.fromLocalFile(str(path)).toString())
        wait_for(lambda: not controller.snapshot["busy"])
        assert controller.snapshot["pageCount"] == 30 and not controller.snapshot["unread"]
        editor = root.findChild(QQuickItem, "draftEditor")
        editor.setProperty("text", "Câu hỏi đang soạn dở trong chatbox")
        click(view, root, "openPdfSearch")
        pdf_search_field = root.findChild(QQuickItem, "pdfSearchField")
        assert pdf_search_field is not None and pdf_search_field.isVisible()
        pdf_search_field.setProperty("text", "binary search")
        click(view, root, "runPdfSearch")
        wait_for(lambda: not controller.snapshot["busy"])
        assert controller.snapshot["items"][0]["page"] == 30
        assert controller.snapshot["searchQuery"] == "binary search"
        assert root.property("noticeVisible")
        assert view.height() < 310
        if capture:
            assert view.grabWindow().save(str(Path(capture) / "pdf-unread.png"))
        assert editor.property("text") == "Câu hỏi đang soạn dở trong chatbox"
        click(view, root, "notice")
        assert not controller.snapshot["unread"]
        assert abs(view.y() + composer.mapToScene(QPointF(0, composer.height())).y() - anchor) <= 1
        snap_card = find_item(root, "searchSnapshot_30")
        assert snap_card is not None and snap_card.isVisible()
        wait_for(lambda: bool(snap_card.property("snapshotReady")))
        assert snap_card.height() >= 58
        capture = os.environ.get("RAT_QUICK_CAPTURE_DIR")
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
            assert view.grabWindow().save(str(Path(capture) / "pdf-search.png"))
        click(view, root, "searchSnapshot_30")
        wait_for(lambda: controller.snapshot["view"] == "page")
        assert "log n comparisons" in controller.snapshot["pageText"]
        if capture:
            assert view.grabWindow().save(str(Path(capture) / "pdf-page.png"))
        target_item = root.findChild(QQuickItem, "matchedExcerptText")
        if target_item is None or not target_item.isVisible():
            target_item = root.findChild(QQuickItem, "pageText")
        content = controller.snapshot.get("rawMatchedSnippet") or controller.snapshot["pageText"]
        start = content.index("log n")
        target_item.select(start, start + len("log n comparisons"))
        click(view, root, "copyCitation")
        assert copied[-1].startswith("log n comparisons\n\n")
        assert "trang PDF 30" in copied[-1] and "Book-30" in copied[-1]
        assert str(path) in copied[-1]
        selection = (target_item.property("selectionStart"), target_item.property("selectionEnd"))
        click(view, root, "liveFoldButton")
        click(view, root, "notice")
        assert (target_item.property("selectionStart"), target_item.property("selectionEnd")) == selection
        click(view, root, "backToSearch")
        assert controller.snapshot["items"][0]["page"] == 30
        click(view, root, "liveFoldButton")
        assert not root.property("noticeVisible")
        controller.readPage(1)
        wait_for(lambda: not controller.snapshot["busy"])
        assert controller.snapshot["errorCode"] == "no_text_page"
        assert root.property("noticeVisible")
        click(view, root, "notice")
        click(view, root, "liveFoldButton")
        assert not root.property("noticeVisible")
        click(view, root, "documentMenu")
        page_picker = root.findChild(QQuickItem, "pagePicker")
        assert page_picker.isVisible()
        page_picker.setProperty("value", 30)
        if capture:
            assert view.grabWindow().save(str(Path(capture) / "pdf-document-menu.png"))
        click(view, root, "readPage")
        wait_for(lambda: not controller.snapshot["busy"])
        assert controller.snapshot["pageNumber"] == 30
        assert editor.property("text") == "Câu hỏi đang soạn dở trong chatbox"
        editor.setProperty("text", "word\n" * 100)
        QTest.qWait(30)
        assert root.findChild(QQuickItem, "composer").height() <= 150
        editor.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Tab)
        assert root.findChild(QQuickItem, "sendButton").hasActiveFocus()
        long_pdf = write_pdf(tmp_path / "long.pdf", ["Binary search uses log n comparisons. " * 400])
        controller.selectFile(str(long_pdf))
        wait_for(lambda: not controller.snapshot["busy"])
        controller.readPage(1)
        wait_for(lambda: not controller.snapshot["busy"])
        click(view, root, "notice")
        assert controller.snapshot["pageTruncated"] and len(controller.snapshot["pageText"]) == 8000
        click(view, root, "copyCitation")
        assert "long.pdf, trang PDF 1" in copied[-1]
        assert len(copied[-1].split("\n\n— ")[0]) <= 500
        editor.setProperty("text", "binary search")
        view.resize(520, view.height())
        root.setProperty("darkMode", True)
        QTest.qWait(50)
        click(view, root, "copyCitation")
        assert root.findChild(QQuickItem, "resultPaper").width() <= 370
        if capture:
            assert view.grabWindow().save(str(Path(capture) / "pdf-long-page-dark-520.png"))
        assert warnings == []
    finally:
        resize_timer.stop()
        view.setSource(QUrl())
        view.close()
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_compact_surface_startup_busy_and_error(app, tmp_path, monkeypatch):
    from rat.ui import quick_pdf_controller as module
    original = module.select_pdf
    entered, release = threading.Event(), threading.Event()
    path = write_pdf(tmp_path / "Đề cương nghiên cứu dài.pdf", ["Example text."])

    def held(path, **kwargs):
        entered.set()
        release.wait(3)
        return original(path, **kwargs)

    monkeypatch.setattr(module, "select_pdf", held)
    control = QuickPDFController()
    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": control, "reduceMotion": True,
                               "mascotSource": QUrl.fromLocalFile(str(PROJECT / "rat/assets/rat_mascot_cutout.png"))})
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(520, round(root.property("preferredWindowHeight")))
    resize_timer = bind_desk_window(view)
    view.show()
    capture = os.environ.get("RAT_QUICK_CAPTURE_DIR")

    def screenshot(name):
        QTest.qWait(30)
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
            assert view.grabWindow().save(str(Path(capture) / name))

    try:
        assert root.property("phase") == "startup"
        screenshot("pdf-startup-520.png")
        control.ready()
        control.selectFile(str(path))
        wait_for(entered.is_set)
        assert not root.property("noticeVisible")
        assert view.height() < 310
        screenshot("pdf-busy-folded-520.png")
        click(view, root, "notice")
        assert root.property("expanded")
        screenshot("pdf-busy-expanded-520.png")
        release.set()
        wait_for(lambda: not control.snapshot["busy"])
        assert not root.property("noticeVisible")
        control.setExpanded(False)
        control.selectFile("https://example.invalid/remote.pdf")
        assert root.property("noticeVisible")
        click(view, root, "notice")
        assert control.snapshot["errorCode"] == "not_pdf"
        screenshot("pdf-error-520.png")
        QTest.keyClick(view, Qt.Key.Key_Escape)
        QTest.qWait(30)
        assert not root.property("expanded") and not root.property("noticeVisible")
        assert view.height() < 310
        assert warnings == []
    finally:
        release.set()
        resize_timer.stop()
        control.close()
        view.setSource(QUrl())
        view.close()
        view.deleteLater()
        control.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_latest_selection_replaces_pending_and_stale_callbacks_are_ignored(controller, tmp_path, monkeypatch):
    from rat.ui import quick_pdf_controller as module
    original = module.select_pdf
    paths = [write_pdf(tmp_path / f"{name}.pdf", [name]) for name in ("a", "b", "c")]
    entered, release = threading.Event(), threading.Event()
    seen = []
    def select(path, **kwargs):
        seen.append(Path(path).name)
        if Path(path) == paths[0]:
            entered.set()
            release.wait(3)
        return original(path, **kwargs)
    monkeypatch.setattr(module, "select_pdf", select)
    try:
        controller.selectFile(str(paths[0]))
        wait_for(entered.is_set)
        old = controller._request.serial
        controller.selectFile(str(paths[1]))
        controller.selectFile(str(paths[2]))
        release.set()
        wait_for(lambda: not controller.snapshot["busy"])
        assert seen == ["a.pdf", "c.pdf"]
        assert controller.snapshot["fileName"] == "c.pdf"
        controller._delivered.emit(old, "ok", original(paths[0]))
        QTest.qWait(20)
        assert controller.snapshot["fileName"] == "c.pdf"
    finally:
        release.set()


def test_cancel_and_close_withdraw_results_without_claiming_thread_termination(app, tmp_path, monkeypatch):
    from rat.ui import quick_pdf_controller as module
    original = module.select_pdf
    path = write_pdf(tmp_path / "held.pdf", ["Text"])
    entered, release = threading.Event(), threading.Event()
    def held(path, **kwargs):
        entered.set()
        release.wait(3)
        return original(path, **kwargs)
    monkeypatch.setattr(module, "select_pdf", held)
    controller = QuickPDFController()
    controller.ready()
    try:
        controller.selectFile(str(path))
        wait_for(entered.is_set)
        controller.cancel()
        assert not controller.snapshot["busy"] and not controller.snapshot["fileName"]
        assert controller.close() is False
        release.set()
        wait_for(lambda: not controller._worker._thread.is_alive())
        QTest.qWait(20)
        assert not controller.snapshot["fileName"] and not controller.snapshot["unread"]
    finally:
        release.set()
        controller.close()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_bad_remote_selection_cancels_previous_work_and_never_opens_it(controller, tmp_path):
    path = write_pdf(tmp_path / "good.pdf", ["Binary search"])
    controller.selectFile(str(path))
    controller.selectFile("https://example.com/unselected.pdf")
    QTest.qWait(100)
    assert controller.snapshot["errorCode"] == "not_pdf"
    assert not controller.snapshot["fileName"] and not controller.snapshot["busy"]
    assert controller.openOriginal() is False


def test_copy_rechecks_changed_source(controller, tmp_path):
    path = write_pdf(tmp_path / "original.pdf", ["Read this exact source."])
    controller.selectFile(str(path))
    wait_for(lambda: not controller.snapshot["busy"])
    controller.readPage(1)
    wait_for(lambda: not controller.snapshot["busy"])
    copied = []
    controller.copyReady.connect(copied.append)
    path.write_bytes(path.read_bytes() + b"\n% new version\n")
    assert controller.copyCitation("") is False
    assert controller.snapshot["errorCode"] == "pdf_changed"
    assert copied == []


def test_pure_chatbox_enter_asks_pdf_and_renders_citation_snapshot(app, tmp_path):
    """Build 2026.10.24.8: Enter in composer asks Chuột directly even when a PDF is attached."""
    from rat.engine.assistant_runtime import AgentResponse, AssistantRuntime

    dispatched = []

    class StubDocModel:
        def chat_with_meta(self, messages, tools, **kwargs):
            dispatched.append(messages)
            return {
                "message": {"content": "Tài liệu nêu binary search dùng O(log n) phép so sánh."},
                "prompt_tokens": 24,
                "completion_tokens": 12,
            }

        def close(self):
            pass

    pdf_path = write_pdf(tmp_path / "Algo.pdf", ["Intro page", "Binary search uses log n comparisons."])
    stub_model = StubDocModel()
    runtime = AssistantRuntime(model_client=stub_model, discover_tools=True)
    runtime.document_model_client = stub_model
    control = QuickPDFController(assistant_runtime=runtime, auto_init_finder=False)
    control.ready()
    view = QQuickView()
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": control, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(640, 520)
    timer = bind_desk_window(view)
    view.show()
    try:
        control.selectFile(str(pdf_path))
        wait_for(lambda: not control.snapshot["busy"])
        send_btn = root.findChild(QQuickItem, "sendButton")
        assert send_btn.property("iconName") == "arrow-up"

        # 1. Pure chatbox: pressing Enter directly asks Chuột about the selected PDF (no Cmd+Enter needed).
        editor = root.findChild(QQuickItem, "draftEditor")
        editor.setProperty("text", "Binary search tốn bao nhiêu phép so sánh?")
        editor.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Return)
        wait_for(lambda: not control.snapshot["busy"] and control.snapshot["view"] == "answer")
        assert editor.property("text") == ""
        assert len(dispatched) == 1
        assert dispatched[0][-1]["content"] == "Binary search tốn bao nhiêu phép so sánh?"
        assert "O(log n)" in control.snapshot["answerText"]

        # 2. Explicit page citation renders a clickable cropped snapshot card in answerSources.
        turn = control.conversation.begin_turn("Trang nào nêu phép so sánh?")
        control._current_turn_id = turn.turn_id
        control._current_execution_id = turn.execution_id
        control._current_worker = object()
        control._last_user_query = "Trang nào nêu phép so sánh?"
        control._on_execution_response(AgentResponse(
            "Xem chi tiết tại trang 2.",
            [],
            0,
            0,
            0,
            sources=[{
                "path": str(pdf_path),
                "page": 2,
                "excerpt": "Binary search uses log n comparisons.",
            }],
            execution_id=turn.execution_id,
            answer_verification_status="PASS",
        ))
        click(view, root, "notice")
        click(view, root, "answerSourcesToggle")
        src_snap = find_item(root, "sourceSnapshot_0")
        assert src_snap is not None and src_snap.isVisible()
        wait_for(lambda: bool(src_snap.property("snapshotReady")))
        assert src_snap.height() >= 58

        # Security check: pageSnapshot rejects any unselected path
        other_pdf = write_pdf(tmp_path / "Other.pdf", ["Secret"])
        assert control.pageSnapshot(str(other_pdf), 1, "Secret", "Secret") == ""

        # Accent-insensitive recovery check: unaccented query recovers accented span from snippet
        from rat.ui.pdf_snapshot_provider import _candidate_phrases_and_words
        phrases, words = _candidate_phrases_and_words("quy che", "Điều 5: Quy chế học vụ tối đa 24 tín chỉ.")
        assert phrases[0] == "Quy chế"
        assert "Quy" in words and "chế" in words

        click(view, root, "sourceSnapshot_0")
        wait_for(lambda: not control.snapshot["busy"] and control.snapshot["view"] == "page")
        assert control.snapshot["pageNumber"] == 2
        assert control.snapshot["canBackToAnswer"]
        click(view, root, "backToAnswer")
        assert control.snapshot["view"] == "answer"
        assert warnings == []
    finally:
        timer.stop()
        control.close()
        runtime.close()
        view.setSource(QUrl())
        view.close()
        view.deleteLater()
        control.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_build10_seamless_reader_and_navigation_suite(app, controller, tmp_path):
    """Build 2026.10.24.10: Seamless reader navigation, bounds check, full page snapshot, and return to answer."""
    path = write_pdf(tmp_path / "MultiPage.pdf", ["Page 1 content", "Page 2 content", "Page 3 content"])
    controller.openPdfDocument(str(path))
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "page")
    assert controller.snapshot["pageNumber"] == 1
    assert controller.snapshot["pageCount"] == 3
    assert controller.snapshot["expanded"]

    # 1. Bounds check on prevPage (cannot go < 1)
    assert not controller.prevPage()
    assert controller.snapshot["pageNumber"] == 1

    # 2. Next page advances to 2 and 3
    assert controller.nextPage()
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["pageNumber"] == 2)
    assert controller.nextPage()
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["pageNumber"] == 3)

    # 3. Bounds check on nextPage (cannot go > pageCount)
    assert not controller.nextPage()
    assert controller.snapshot["pageNumber"] == 3

    # 4. Prev page returns to 2
    assert controller.prevPage()
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["pageNumber"] == 2)

    # 5. Full page snapshot rendering & LRU cache
    data_url = controller.fullPageSnapshot(str(path), 2, 800)
    assert data_url.startswith("data:image/png;base64,")
    # Security check: rejected for unauthorized path
    other_path = write_pdf(tmp_path / "Unauthorized.pdf", ["Secret"])
    assert controller.fullPageSnapshot(str(other_path), 1, 800) == ""

    # 6. Jump to PDF page from Answer and return to Answer without model call
    controller._last_assistant_answer = "Câu trả lời có sẵn"
    controller._view = "answer"
    controller.jumpToPdfPage(3)
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "page")
    assert controller.snapshot["pageNumber"] == 3
    assert controller.snapshot["canBackToAnswer"]
    controller.backToAnswer()
    assert controller.snapshot["view"] == "answer"
    assert controller.snapshot["answerText"] == "Câu trả lời có sẵn"


def test_header_controls_bounds_and_mode_instructions(app, controller, tmp_path):
    path = write_pdf(tmp_path / "BoundsDoc.pdf", ["Page 1 text", "Page 2 text", "Page 3 binary search log n"])
    controller.selectFile(str(path), auto_read=True)
    wait_for(lambda: not controller.snapshot["busy"])
    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(520, round(root.property("preferredWindowHeight")))
    timer = bind_desk_window(view)
    view.show()
    try:
        # Simulate opening from Answer source reference so canBackToAnswer is True
        controller._last_assistant_answer = "Câu trả lời trước"
        controller._last_answer_sources = [{"path": str(path), "page": 1, "snippet": "Page 1 text"}]
        controller.openAnswerSource(0)
        wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "page")

        # Test bounds at both narrow 520px and wider 700px
        for width in [520, 700]:
            view.resize(width, round(root.property("preferredWindowHeight")))
            QTest.qWait(50)
            paper = root.findChild(QQuickItem, "resultPaper")
            copy = root.findChild(QQuickItem, "copyCitation")
            fold = root.findChild(QQuickItem, "liveFoldButton")
            assert paper is not None and copy is not None and fold is not None
            paper_scene = paper.mapToScene(QPointF(0, 0))
            paper_right = paper_scene.x() + paper.width()
            copy_right = copy.mapToScene(QPointF(0, 0)).x() + copy.width()
            fold_right = fold.mapToScene(QPointF(0, 0)).x() + fold.width()
            assert copy_right <= paper_right + 1.0, f"copyCitation right ({copy_right}) exceeds paper right ({paper_right}) at width {width}"
            assert fold_right <= paper_right + 1.0, f"liveFoldButton right ({fold_right}) exceeds paper right ({paper_right}) at width {width}"
            assert fold_right <= view.width(), f"liveFoldButton exceeds window width at {width}"

        # Test P2: Visual mode must NOT show selection instruction
        root.setProperty("readerDisplayMode", "visual")
        QTest.qWait(30)
        page_instructions = [child for child in root.findChildren(QQuickItem)
                             if hasattr(child, "property") and "Bôi chọn đoạn cần lấy" in str(child.property("text") or "")]
        assert len(page_instructions) == 0, "Visual mode must not show text selection instruction"

        # Switch to text mode: selection instruction is now appropriate
        root.setProperty("readerDisplayMode", "text")
        QTest.qWait(30)
        page_instructions_text = [child for child in root.findChildren(QQuickItem)
                                  if hasattr(child, "property") and "Bôi chọn đoạn cần lấy" in str(child.property("text") or "")]
        assert len(page_instructions_text) > 0, "Text mode should show text selection instruction"
    finally:
        view.close()


def test_source_metadata_title_and_composer_footer_presentation(app, controller, tmp_path):
    """Test Build 2026.10.24.11 source title 'Nguồn · Trang N/M', filename subtitle, and clean composer footer."""
    path = write_pdf(tmp_path / "SourceDoc.pdf", ["Page 1 intro", "Page 2 analysis", "Page 3 conclusion"])
    controller.openPdfDocument(str(path))
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "page")

    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(520, round(root.property("preferredWindowHeight")))
    timer = bind_desk_window(view)
    view.show()
    try:
        QTest.qWait(100)
        title_item = root.findChild(QQuickItem, "pageSourceTitle")
        assert title_item is not None
        assert title_item.property("text") == "Nguồn · Trang 1/3"

        meta_item = root.findChild(QQuickItem, "pageMetadataLabel")
        assert meta_item is not None
        assert meta_item.property("text") == "SourceDoc.pdf"

        composer_status = root.findChild(QQuickItem, "composerDropStatus")
        assert composer_status is not None
        status_text = composer_status.property("text")
        assert "Trang" not in status_text
        assert status_text == "↵ hỏi Chuột · ⌘F tìm chữ trong PDF"
    finally:
        view.close()


def test_search_hit_opens_matched_excerpt_mode_suite(app, controller, tmp_path):
    """Test Build 2026.10.24.12: Search hit opens matched excerpt view, highlights keyword, copies snippet, and toggles visual page."""
    path = write_pdf(tmp_path / "MatchDoc.pdf", [
        "Page 1: Overview of concepts and principles.",
        "Page 2: Deep analysis of routing heuristics for optimization.",
        "Page 3: Evaluation results and benchmarks."
    ])
    controller.selectFile(str(path))
    wait_for(lambda: not controller.snapshot["busy"])
    controller.search("routing")
    wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "search")
    assert len(controller.snapshot["items"]) >= 1

    copied_texts = []
    controller.copyReady.connect(copied_texts.append)

    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(520, round(root.property("preferredWindowHeight")))
    timer = bind_desk_window(view)
    view.show()
    try:
        QTest.qWait(100)
        # Type a draft in composer
        draft_ed = root.findChild(QQuickItem, "draftEditor")
        assert draft_ed is not None
        draft_ed.setProperty("text", "Draft question being composed")

        # Open workbench from min mode notice card
        click(view, root, "notice")
        assert root.property("expanded")

        # 1. Click read hit button on page 2
        click(view, root, "readHit_2")
        wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "page")
        assert controller.snapshot["pageNumber"] == 2
        assert controller.snapshot["hasMatchedSnippet"]
        assert controller.snapshot["sourceKind"] == "search_hit"

        # 2. Check title: 'Nguồn · Trang 2' and filename
        title_item = root.findChild(QQuickItem, "pageSourceTitle")
        assert title_item is not None
        assert title_item.property("text") == "Nguồn · Trang 2"

        meta_item = root.findChild(QQuickItem, "pageMetadataLabel")
        assert meta_item is not None
        assert meta_item.property("text") == "MatchDoc.pdf"

        # 3. Check matched excerpt text contains keyword and highlight
        excerpt_item = root.findChild(QQuickItem, "matchedExcerptText")
        assert excerpt_item is not None and excerpt_item.isVisible()
        excerpt_html = excerpt_item.property("text")
        assert "routing" in excerpt_html.lower()
        assert "background-color" in excerpt_html

        # 4. Assert switcher does NOT exist and openOriginalExternal exists
        assert root.findChild(QQuickItem, "readerModeToggle") is None
        open_ext_btn = root.findChild(QQuickItem, "openOriginalExternal")
        assert open_ext_btn is not None and open_ext_btn.isVisible()

        # 5. Copy button is 'Chép đoạn'
        copy_btn = root.findChild(QQuickItem, "copyCitation")
        assert copy_btn is not None and copy_btn.isVisible()
        assert copy_btn.property("text") == "Chép đoạn"

        # 6. Click copy citation -> verify REAL clipboard contents
        click(view, root, "copyCitation")
        wait_for(lambda: len(copied_texts) == 1)
        assert app.clipboard().text() == copied_texts[0]
        assert "routing" in app.clipboard().text().lower()
        assert "MatchDoc.pdf" in app.clipboard().text()
        assert "trang PDF 2" in app.clipboard().text()
        assert copy_btn.property("text") == "Đã chép"

        # 7. Test partial text selection copying
        excerpt_item.select(0, 13)
        assert excerpt_item.property("selectedText") != ""
        click(view, root, "copyCitation")
        wait_for(lambda: len(copied_texts) == 2)
        assert app.clipboard().text() == copied_texts[1]
        assert excerpt_item.property("selectedText").strip() in app.clipboard().text()

        # 8. Test reading page without matched hit -> shows fallback "Chưa có đoạn trích cho trang này."
        controller.readPage(3)
        wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["pageNumber"] == 3)
        assert not controller.snapshot["hasMatchedSnippet"]
        fallback_btn = root.findChild(QQuickItem, "openOriginalFallback")
        assert fallback_btn is not None and fallback_btn.isVisible()

        # 9. Test backToSearch preserves draft and keyword
        click(view, root, "backToSearch")
        wait_for(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "search")
        assert draft_ed.property("text") == "Draft question being composed"
        assert controller.snapshot["searchQuery"] == "routing"

        # 10. Test openOriginal does not clear draft or disturb flow
        opened_urls = []
        controller._open_url = lambda url: opened_urls.append(url) or True
        assert controller.openOriginal()
        assert len(opened_urls) == 1
        assert "MatchDoc.pdf" in opened_urls[0].toString()
        assert draft_ed.property("text") == "Draft question being composed"
    finally:
        view.close()




