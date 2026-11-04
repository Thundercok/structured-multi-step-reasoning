"""End-to-end acceptance tests for RAT-FIND-01 progressive finder in Qt Quick Desk."""
from __future__ import annotations

import os
from pathlib import Path
import plistlib
import tempfile
import time
from typing import List

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QPointF, QUrl, Qt
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QGuiApplication

from rat.crawler.db import Database
from rat.engine.app_resolver import Application, ApplicationCatalog
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator
from rat.ui.quick_pdf_controller import QuickPDFController, finder_row_detail, short_folder
from reasoning.bundle import create_synthetic_specimen_bundle


def _process_events(ms: int = 150):
    deadline = time.perf_counter() + (ms / 1000.0)
    while time.perf_counter() < deadline:
        QGuiApplication.processEvents()
        time.sleep(0.005)


def _dispose(view, controller):
    """Destroy now: a view left for the garbage collector crashes Qt's animation timer in the next test."""
    view.close()
    controller.close()
    view.deleteLater()
    controller.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QGuiApplication.processEvents()


class RecordingBackend:
    hidden_size = 2

    def __init__(self, authored_answer="Tệp chứa danh sách sinh viên CNTT 2026."):
        self.authored_answer = authored_answer
        self.dispatches = []

    def embed(self, query: str):
        import numpy as np
        return np.zeros(self.hidden_size, dtype=np.float32)

    def run(self, strategy, query: str, should_cancel=None, deadline_monotonic=None, max_tokens=None):
        self.dispatches.append(query)
        return self.authored_answer, 0.95, 12


@pytest.fixture
def finder_fixture(tmp_path):
    # 1. Synthetic PDF document
    pdf_path = tmp_path / "bao_cao_quy_che.pdf"
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        with open(pdf_path, "wb") as f:
            writer.write(f)
    except Exception:
        pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n190\n%%EOF\n")

    # 2. Synthetic text document
    txt_path = tmp_path / "danh_sach_lop.txt"
    txt_path.write_text("Danh sach sinh vien khoa CNTT 2026")

    # 3. Database
    db_path = tmp_path / "test_finder.db"
    db = Database(str(db_path))
    db.upsert_document({
        "file_path": str(pdf_path),
        "file_name": pdf_path.name,
        "file_ext": ".pdf",
        "file_size": pdf_path.stat().st_size,
        "created_at": 1000.0,
        "modified_at": 1000.0,
        "indexed_at": 1000.0,
        "content_text": "Bao cao quy che dao tao tin chi hoc vu",
        "summary": "Quy chế học vụ tín chỉ",
    })
    db.upsert_document({
        "file_path": str(txt_path),
        "file_name": txt_path.name,
        "file_ext": ".txt",
        "file_size": txt_path.stat().st_size,
        "created_at": 1000.0,
        "modified_at": 1000.0,
        "indexed_at": 1000.0,
        "content_text": "Danh sach sinh vien khoa CNTT 2026",
        "summary": "Danh sách sinh viên",
    })

    # 4. Synthetic application catalog with Info.plist
    app_dir = tmp_path / "Apps"
    app_path = app_dir / "Calculator.app"
    (app_path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    plist = dict(
        CFBundleIdentifier="com.apple.calculator",
        CFBundleExecutable="Calculator",
        CFBundleShortVersionString="1.0",
    )
    with open(app_path / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(plist, f)
    (app_path / "Contents" / "MacOS" / "Calculator").write_text("bin")

    catalog = ApplicationCatalog.scan([app_dir])
    search = ProgressiveSearch(db_path, catalog=catalog)

    yield {
        "db": db,
        "db_path": str(db_path),
        "catalog": catalog,
        "search": search,
        "pdf_path": str(pdf_path),
        "txt_path": str(txt_path),
        "app_path": str(app_path),
    }
    search.close_connection()
    db.get_connection().close()


def test_quick_finder_typing_shows_hits(finder_fixture):
    """Typing an app or file name in composer displays progressive finder hits."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )
    controller.ready()

    # Initially view is "none", no hits
    assert controller.snapshot["view"] == "none"
    assert len(controller.snapshot["finderHits"]) == 0

    # User types "calc" -> matches Calculator app
    controller.onComposerTextChanged("calc")
    _process_events(250)

    snap = controller.snapshot
    assert snap["view"] == "finder"
    assert snap["expanded"] is True
    assert len(snap["finderHits"]) >= 1
    calc_hit = next((h for h in snap["finderHits"] if h["title"] == "Calculator"), None)
    assert calc_hit is not None
    assert calc_hit["kind"] == "application"

    # User types "quy che" -> matches PDF
    controller.onComposerTextChanged("quy che")
    _process_events(250)

    snap2 = controller.snapshot
    assert snap2["view"] == "finder"
    pdf_hit = next((h for h in snap2["finderHits"] if "bao_cao" in h["title"]), None)
    assert pdf_hit is not None
    assert pdf_hit["is_pdf"] is True

    controller.close()


def test_quick_finder_open_pdf_directly(finder_fixture):
    """Clicking 'Đọc trực tiếp' on a PDF hit loads it into the reader."""
    app = QGuiApplication.instance() or QGuiApplication([])

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
    )
    controller.ready()

    controller.onComposerTextChanged("quy che")
    _process_events(250)

    # Click open PDF
    controller.openPdfHit(finder_fixture["pdf_path"])
    _process_events(300)

    snap = controller.snapshot
    assert snap["fileName"] == "bao_cao_quy_che.pdf"
    assert snap["pageCount"] >= 1

    controller.close()


def test_quick_finder_open_app(finder_fixture):
    """Clicking 'Mở ứng dụng' launches the app via open_url."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )
    controller.ready()

    ok = controller.openHit(finder_fixture["app_path"])
    assert ok is True
    assert len(opened_urls) == 1
    assert finder_fixture["app_path"] in opened_urls[0].toLocalFile()
    assert controller.snapshot['launchFeedback'] == 'Chuột đang mở Calculator.'
    assert not controller.snapshot['launchFeedbackError']

    controller.close()


@pytest.mark.parametrize('failure', ['removed', 'executable_removed', 'identity_changed', 'malformed', 'os_refused', 'os_exception'])
def test_app_launch_failure_is_inline_and_keeps_workbench(finder_fixture, failure):
    """Synthetic unit contracts only; not live UI/OS launch acceptance."""
    import shutil
    app = QGuiApplication.instance() or QGuiApplication([])
    opened = []
    def opener(url):
        opened.append(url)
        if failure == 'os_exception':
            raise OSError('private OS details')
        return False
    controller = QuickPDFController(
        finder_catalog=finder_fixture['catalog'], auto_init_finder=False,
        db_path=finder_fixture['db_path'], open_url=opener,
    )
    controller.ready()
    controller.onComposerTextChanged('calc')
    _process_events(200)
    before = controller.snapshot
    path = Path(finder_fixture['app_path'])
    if failure == 'removed':
        shutil.rmtree(path)
    elif failure == 'executable_removed':
        (path / 'Contents/MacOS/Calculator').unlink()
    elif failure == 'identity_changed':
        info = path / 'Contents/Info.plist'
        data = plistlib.loads(info.read_bytes())
        data['CFBundleIdentifier'] = 'com.example.replacement'
        info.write_bytes(plistlib.dumps(data))
    elif failure == 'malformed':
        (path / 'Contents/Info.plist').write_text('not a plist')
    try:
        assert not controller.openSelectedHit(0)
        after = controller.snapshot
        assert after['launchFeedbackError']
        assert 'không mở được' in after['launchFeedback']
        assert 'private OS details' not in after['launchFeedback']
        assert after['view'] == before['view']
        assert after['finderQuery'] == 'calc'
        assert after['finderHits'] == before['finderHits']
        assert len(opened) == (1 if failure.startswith('os_') else 0)
        controller.onComposerTextChanged('safari')
        assert not controller.snapshot['launchFeedback']
    finally:
        controller.close()


def test_new_query_cannot_open_previous_results(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    opened = []
    controller = QuickPDFController(
        finder_catalog=finder_fixture['catalog'], auto_init_finder=False,
        db_path=finder_fixture['db_path'], open_url=lambda url: opened.append(url) or True,
    )
    controller.ready()
    try:
        controller.onComposerTextChanged('calc')
        _process_events(200)
        assert controller.snapshot['finderHits']
        controller.onComposerTextChanged('mo trinh duyet')
        # No event loop yield: latest snapshot has not arrived yet.
        assert not controller.snapshot['finderHits']
        assert not controller.openSelectedHit(0)
        assert not opened
    finally:
        controller.close()


def test_described_file_can_open_outside_and_missing_file_is_inline(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    opened = []
    controller = QuickPDFController(
        finder_catalog=finder_fixture['catalog'], db_path=finder_fixture['db_path'],
        auto_init_finder=False, open_url=lambda url: opened.append(url.toLocalFile()) or True,
    )
    controller.ready()
    try:
        controller.onComposerTextChanged('tim file co noi dung danh sach sinh vien')
        _process_events(250)
        assert [h['path'] for h in controller.snapshot['finderHits']] == [finder_fixture['txt_path']]
        assert controller.openSelectedHit(0)
        assert opened == [finder_fixture['txt_path']]
        assert controller.snapshot['launchFeedback'] == 'Chuột đang mở danh_sach_lop.txt.'
        Path(finder_fixture['txt_path']).unlink()
        assert not controller.openSelectedHit(0)
        assert controller.snapshot['launchFeedbackError']
        assert controller.snapshot['view'] != 'error'
        controller.onComposerTextChanged('tim file co noi dung nonexistenttopic')
        _process_events(250)
        assert not controller.snapshot['finderHits']
        assert 'chưa thấy tệp khớp' in controller.snapshot['finderFeedback']
        assert not controller.snapshot['launchFeedback']
    finally:
        controller.close()


def test_quick_finder_ask_about_file(finder_fixture):
    """Clicking 'Hỏi về tệp' attaches the file context to assistant reasoning."""
    app = QGuiApplication.instance() or QGuiApplication([])

    backend = RecordingBackend()
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        reasoning_engine=engine,
        allow_synthetic_policy=True,
        auto_init_finder=False,
    )
    controller.ready()

    ok = controller.askAboutHit(finder_fixture["txt_path"], "Tóm tắt danh sách lớp")
    assert ok is True
    _process_events(350)

    snap = controller.snapshot
    assert snap["view"] == "answer"
    assert "danh sách sinh viên" in snap["answerText"].lower()

    controller.close()


def test_quick_finder_clear_composer_folds_workbench(finder_fixture):
    """Clearing text in composer folds the finder back to idle state."""
    app = QGuiApplication.instance() or QGuiApplication([])

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
    )
    controller.ready()

    controller.onComposerTextChanged("calc")
    _process_events(250)
    assert controller.snapshot["view"] == "finder"

    # Clear composer text
    controller.onComposerTextChanged("")
    _process_events(100)

    snap = controller.snapshot
    assert snap["view"] == "none"
    assert len(snap["finderHits"]) == 0

    controller.close()


def test_quick_finder_qml_real_surface(finder_fixture):
    """Verify finder results and user actions directly in the real QML interface."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )

    view = QQuickView()
    view.setInitialProperties({
        "liveController": controller,
        "darkMode": False,
        "reduceMotion": True,
    })
    qml_path = Path(__file__).resolve().parents[1] / "rat/ui/quick/PDFDesk.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_path)))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    _process_events(100)

    root = view.rootObject()
    editor = root.findChild(QQuickItem, "draftEditor")
    assert editor is not None

    # Simulate user typing "calc" into the draftEditor
    editor.setProperty("text", "calc")
    _process_events(300)

    snap = controller.snapshot
    assert snap["view"] == "finder"
    assert snap["expanded"] is True

    # Find the finderResults QML item
    finder_results = root.findChild(QQuickItem, "finderResults")
    assert finder_results is not None
    assert finder_results.property("visible") is True

    # Simulate clearing text
    editor.setProperty("text", "")
    _process_events(150)
    assert controller.snapshot["view"] == "none"

    _dispose(view, controller)


def test_quick_finder_keyboard_navigation_and_actions(finder_fixture):
    """Arrow Up/Down keys cycle through finder hits; Return key opens selected hit."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )

    view = QQuickView()
    view.setInitialProperties({
        "liveController": controller,
        "darkMode": False,
        "reduceMotion": True,
    })
    qml_path = Path(__file__).resolve().parents[1] / "rat/ui/quick/PDFDesk.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_path)))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    _process_events(100)

    root = view.rootObject()
    editor = root.findChild(QQuickItem, "draftEditor")
    assert editor is not None
    editor.forceActiveFocus()

    # 1. Type "calc" to get results
    editor.setProperty("text", "calc")
    _process_events(300)
    assert controller.snapshot["view"] == "finder"
    hits = controller.snapshot["finderHits"]
    assert len(hits) >= 1
    assert root.property("selectedFinderIndex") == -1

    # 2. Press Arrow Down -> selects first hit (index 0)
    QTest.keyClick(view, Qt.Key.Key_Down)
    _process_events(50)
    assert root.property("selectedFinderIndex") == 0

    # 3. Press Escape -> clears selection
    QTest.keyClick(view, Qt.Key.Key_Escape)
    _process_events(50)
    assert root.property("selectedFinderIndex") == -1

    # 4. Press Arrow Up -> wraps to last hit
    QTest.keyClick(view, Qt.Key.Key_Up)
    _process_events(50)
    assert root.property("selectedFinderIndex") == len(hits) - 1

    # 5. Cycle back to 0 and press Return to open
    QTest.keyClick(view, Qt.Key.Key_Down)
    _process_events(50)
    assert root.property("selectedFinderIndex") == 0

    QTest.keyClick(view, Qt.Key.Key_Return)
    _process_events(100)
    assert len(opened_urls) == 1
    assert "Calculator.app" in opened_urls[0].toString()

    _dispose(view, controller)


def test_quick_finder_reveal_and_preview_actions(finder_fixture):
    """Verify quicklook preview and reveal in Finder actions work and shorten home path."""
    app = QGuiApplication.instance() or QGuiApplication([])
    revealed = []
    previewed = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        reveal_file=lambda p: revealed.append(p) or True,
        preview_file=lambda p: previewed.append(p) or True,
    )
    controller.ready()

    controller.onComposerTextChanged("calc")
    _process_events(200)

    hits = controller.snapshot["finderHits"]
    assert len(hits) >= 1
    hit = hits[0]

    # Home path is shortened to ~
    assert not hit["display_path"].startswith(str(Path.home())) or "~" in hit["display_path"]

    # Reveal in finder
    assert controller.revealSelectedInFinder(0) is True
    assert len(revealed) == 1
    assert "Calculator.app" in revealed[0]

    # QuickLook preview
    assert controller.previewSelectedHit(0) is True
    assert len(previewed) == 1
    assert "Calculator.app" in previewed[0]

    controller.close()


def test_quick_finder_spotlight_sections_and_action_bar(finder_fixture):
    """Verify section grouping, isQuestionQuery, bottomActionBar, and contextChip in QML."""
    app = QGuiApplication.instance() or QGuiApplication([])

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
    )
    controller.ready()

    # 1. Search for 'c' to get both apps and files
    controller.onComposerTextChanged("c")
    _process_events(200)

    snap = controller.snapshot
    hits = snap["finderHits"]
    assert len(hits) >= 1

    # Verify section header flags
    app_hits = [h for h in hits if h["kind"] == "application"]
    if app_hits:
        assert app_hits[0]["is_first_of_section"] is True
        assert app_hits[0]["section_title"] == "ỨNG DỤNG"

    doc_hits = [h for h in hits if h["kind"] != "application"]
    if doc_hits:
        assert doc_hits[0]["is_first_of_section"] is True
        assert doc_hits[0]["section_title"] == "TÀI LIỆU & TỆP"

    # 2. Test conversational / question query detection
    controller.onComposerTextChanged("sao phải dùng mid + 1?")
    _process_events(100)
    assert controller.snapshot["isQuestionQuery"] is True

    controller.onComposerTextChanged("calculator")
    _process_events(100)
    assert controller.snapshot["isQuestionQuery"] is False

    # 3. Mount in QML to test bottomActionBar and contextChip visibility
    view = QQuickView()
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.show()
    _process_events(50)

    # When search hits exist and selectedFinderIndex >= 0
    controller.onComposerTextChanged("calc")
    _process_events(200)

    bottom_action_bar = root.findChild(QQuickItem, "bottomActionBar")
    assert bottom_action_bar is not None
    # Initially selectedFinderIndex is -1 so bottomActionBar is hidden
    assert not bottom_action_bar.isVisible()

    # Select hit 0 -> bottom action bar becomes visible
    root.setProperty("selectedFinderIndex", 0)
    _process_events(50)
    assert bottom_action_bar.isVisible()

    # Test contextChip appears when activeContext is present
    context_chip = root.findChild(QQuickItem, "contextChip")
    assert context_chip is not None
    assert not context_chip.isVisible()

    from rat.engine.selected_pdf import SelectedPDF
    controller._selection = SelectedPDF(Path("/tmp/quy_che.pdf"), 20, (0, 0, 0, 0))
    controller.changed.emit()
    _process_events(50)

    assert context_chip.isVisible()

    # Clear active context -> chip hides
    controller.clearActiveContext()
    _process_events(50)
    assert not context_chip.isVisible()

    _dispose(view, controller)


def test_app_action_button_keyboard_activation_restores_draft(finder_fixture):
    """The visible toolbar action supports focus/Space and opens its exact target."""
    from PyQt6.QtCore import QEvent
    from rat.ui.icon_provider import RatIconProvider
    from rat.ui.quick_app import bind_desk_window

    application = QGuiApplication.instance() or QGuiApplication([])
    opened = []
    controller = QuickPDFController(
        finder_search=finder_fixture['search'],
        finder_catalog=finder_fixture['catalog'],
        auto_init_finder=False,
        open_url=lambda url: opened.append(url.toLocalFile()) or True,
    )
    controller.ready()
    view = QQuickView()
    RatIconProvider.register(view.engine(), 'icon')
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({'liveController': controller, 'reduceMotion': True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready
    root = view.rootObject()
    view.resize(520, 500)
    timer = bind_desk_window(view)
    view.show()
    try:
        editor = root.findChild(QQuickItem, 'draftEditor')
        draft = 'Bản nháp giữ lại khi mở ứng dụng'
        editor.setProperty('text', draft)
        _process_events(150)
        controller.openAppsView(draft)
        editor.setProperty('text', '')
        _process_events(80)
        pending = [root]
        action = None
        while pending:
            item = pending.pop()
            if item.objectName() == 'appOpenAction':
                action = item
                break
            pending.extend(item.childItems())
        assert action is not None and action.isVisible()
        action.forceActiveFocus()
        assert action.hasActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Space)
        _process_events(100)
        assert opened == [str(Path(finder_fixture['app_path']).resolve())]
        assert controller.snapshot['view'] != 'apps'
        assert editor.property('text') == draft
        assert warnings == []
    finally:
        timer.stop()
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        application.processEvents()


def test_quick_finder_slice_see_more_and_min_mode(tmp_path):
    """Build 2026.10.24.7: max 3 suggestions slice, see-more toggle, collapse selection reset, and min/full draft preservation."""
    from rat.ui.icon_provider import RatIconProvider
    from rat.ui.quick_app import bind_desk_window

    app = QGuiApplication.instance() or QGuiApplication([])

    # Create 5 synthetic documents
    db_path = tmp_path / "test_slice.db"
    db = Database(str(db_path))
    for i in range(1, 6):
        p = tmp_path / f"document_note_{i}.txt"
        p.write_text(f"Content of document {i}")
        db.upsert_document({
            "file_path": str(p),
            "file_name": p.name,
            "file_ext": ".txt",
            "file_size": p.stat().st_size,
            "created_at": 1000.0 + i,
            "modified_at": 1000.0 + i,
            "indexed_at": 1000.0 + i,
            "content_text": f"Document note {i} sample text",
            "summary": f"Summary note {i}",
        })

    search = ProgressiveSearch(db_path, catalog=ApplicationCatalog())
    controller = QuickPDFController(
        finder_search=search,
        auto_init_finder=False,
    )

    view = QQuickView()
    RatIconProvider.register(view.engine(), "icon")
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.resize(520, 500)
    timer = bind_desk_window(view)
    view.show()
    _process_events(100)

    try:
        root = view.rootObject()
        assert root.property("uiBuildLabel").startswith("Build ")

        editor = root.findChild(QQuickItem, "draftEditor")
        assert editor is not None

        # Type 'note' to match 5 documents
        draft = "note"
        editor.setProperty("text", draft)
        _process_events(300)

        snap = controller.snapshot
        assert snap["view"] == "finder"
        hits = snap["finderHits"]
        assert len(hits) == 5

        def to_list(val):
            return val.toVariant() if hasattr(val, "toVariant") else list(val)

        # By default, only max 3 suggestions are visible
        visible_hits = to_list(root.property("visibleFinderHits"))
        assert len(visible_hits) == 3
        assert root.property("remainingFinderHits") == 2
        assert root.property("showAllFinderHits") is False

        # Verify finderResults is visible
        finder_results = root.findChild(QQuickItem, "finderResults")
        assert finder_results is not None
        assert finder_results.isVisible()

        # Verify "see more" button exists and has correct count
        see_more_btn = root.findChild(QQuickItem, "seeMoreFinderHits")
        assert see_more_btn is not None
        assert see_more_btn.isVisible()
        assert "2" in see_more_btn.property("text")

        # Click "see more" -> reveals all 5 suggestions
        see_more_btn.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Space)
        _process_events(100)

        assert root.property("showAllFinderHits") is True
        assert len(to_list(root.property("visibleFinderHits"))) == 5
        assert "Thu gọn" in see_more_btn.property("text")

        # Select index 4 (a hit outside the first 3)
        root.setProperty("selectedFinderIndex", 4)
        assert root.property("selectedFinderIndex") == 4
        bottom_action_bar = root.findChild(QQuickItem, "bottomActionBar")
        assert bottom_action_bar is not None
        assert bottom_action_bar.isVisible()

        # Collapse back to 3 cards
        see_more_btn.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Space)
        _process_events(100)
        assert root.property("showAllFinderHits") is False
        assert len(to_list(root.property("visibleFinderHits"))) == 3
        # Regression check: selectedFinderIndex must be reset/clamped (< 3), never retaining hidden selection
        assert root.property("selectedFinderIndex") < 3, "Collapsed list retains a selected hidden result"
        assert root.property("selectedFinderIndex") == -1
        assert not bottom_action_bar.isVisible()

        # Test min/full mode toggling: draft is preserved
        root.setProperty("expanded", False)
        _process_events(100)
        assert root.property("expanded") is False
        assert root.property("hasFinderPreview") is True

        notice = root.findChild(QQuickItem, "notice")
        assert notice is not None
        assert notice.isVisible()
        min_excerpt = root.findChild(QQuickItem, "minAnswerExcerpt")
        assert min_excerpt is not None
        assert "Gợi ý" in min_excerpt.property("text")
        min_meta = root.findChild(QQuickItem, "minAnswerMetadata")
        assert min_meta is not None
        assert "5 kết quả" in min_meta.property("text")
        assert editor.property("text") == draft

        # Click notice to expand back to full mode
        notice.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Space)
        _process_events(100)
        assert root.property("expanded") is True
        assert editor.property("text") == draft

        # Test "← Bàn làm việc" / backFromFinder button
        back_btn = root.findChild(QQuickItem, "backFromFinder")
        assert back_btn is not None
        assert back_btn.isVisible()
        back_btn.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Space)
        _process_events(100)

        assert controller.snapshot["view"] == "none"
        assert editor.property("text") == draft

        # Type again to bring suggestions back
        editor.setProperty("text", "note 1")
        _process_events(300)
        assert controller.snapshot["view"] == "finder"

        # Test Escape dismisses suggestions while keeping draft
        editor.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Escape)
        _process_events(100)
        assert controller.snapshot["view"] == "none"
        assert editor.property("text") == "note 1"

    finally:
        timer.stop()
        controller.close()
        search.close_connection()
        db.get_connection().close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def test_finder_never_hijacks_active_answer_or_zero_hit_chat_and_exposes_drawer_tab(finder_fixture):
    """Build 2026.10.24.9: 0-hit chat stays folded, active Answer stays visible on follow-up typing, and drawer tab opens/returns cleanly."""
    from PyQt6.QtCore import QPointF
    from rat.engine.assistant_runtime import AgentResponse
    from rat.ui.icon_provider import RatIconProvider
    from rat.ui.quick_app import bind_desk_window

    app = QGuiApplication.instance() or QGuiApplication([])
    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
    )
    view = QQuickView()
    RatIconProvider.register(view.engine(), "icon")
    warnings = []
    view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    root = view.rootObject()
    view.resize(620, round(root.property("preferredWindowHeight")))
    timer = bind_desk_window(view)
    view.show()
    _process_events(80)

    try:
        editor = root.findChild(QQuickItem, "draftEditor")
        drawer_tab = root.findChild(QQuickItem, "finderDrawerTab")
        assert editor is not None and drawer_tab is not None
        assert not drawer_tab.isVisible()

        # 1. Zero-hit normal chat does NOT hijack view or auto-expand window
        editor.setProperty("text", "Xin chào Chuột, giải thích giúp mình quy hoạch động")
        _process_events(250)
        assert controller.snapshot["view"] == "none"
        assert controller.snapshot["expanded"] is False
        assert view.height() < 310
        assert not drawer_tab.isVisible()

        editor.setProperty("text", "")
        _process_events(80)

        # 2. Active Answer view stays on screen while typing follow-up that matches local files/apps
        turn = controller.conversation.begin_turn("So sánh Binary Search và Linear Search kèm điều kiện áp dụng?")
        controller._current_turn_id = turn.turn_id
        controller._current_execution_id = turn.execution_id
        controller._current_worker = object()
        controller._last_user_query = "So sánh Binary Search và Linear Search kèm điều kiện áp dụng?"
        controller._on_execution_response(AgentResponse(
            "| Thuật toán | Thời gian | Điều kiện mảng |\n"
            "| :--- | :---: | :--- |\n"
            "| **Binary Search** | `O(log n)` | Đã sắp xếp tăng dần |\n"
            "| **Linear Search** | `O(n)` | Không cần sắp xếp |\n\n"
            "> Lưu ý *quan trọng*: Dùng `mid = (lo + hi) // 2` tránh tràn chỉ số.\n\n"
            "```python\ndef binary_search(a: list[int], x: int) -> int:\n"
            "    lo, hi = 0, len(a) - 1\n"
            "    return (lo + hi) // 2 if a else -1\n```",
            [],
            0,
            0,
            0,
            execution_id=turn.execution_id,
            answer_verification_status="PASS",
        ))
        controller.setExpanded(True)
        _process_events(120)
        assert controller.snapshot["view"] == "answer"
        q_card = root.findChild(QQuickItem, "answerQuestionCard")
        assert q_card is not None and q_card.isVisible()

        capture_dir = os.environ.get("RAT_QUICK_CAPTURE_DIR")

        # Typing "calc" while reading Answer must NOT overwrite Answer view; drawer tab peeks up instead
        editor.setProperty("text", "calc")
        _process_events(250)
        assert controller.snapshot["view"] == "answer"
        assert controller.snapshot["expanded"] is True
        assert len(controller.snapshot["finderHits"]) >= 1
        assert drawer_tab.isVisible()

        if capture_dir:
            out_p = Path(capture_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            _process_events(80)
            assert view.grabWindow().save(str(out_p / "turn2-answer-sheet-drawer-light.png"))
            root.setProperty("darkMode", True)
            _process_events(80)
            assert view.grabWindow().save(str(out_p / "turn2-answer-sheet-drawer-dark.png"))
            root.setProperty("darkMode", False)
            _process_events(80)

        # 3. Clicking the drawer tab explicitly opens Finder, and "← Câu trả lời" returns to Answer
        pos = drawer_tab.mapToScene(QPointF(drawer_tab.width() / 2, drawer_tab.height() / 2)).toPoint()
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        _process_events(100)
        assert controller.snapshot["view"] == "finder"
        back_btn = root.findChild(QQuickItem, "backFromFinder")
        assert back_btn is not None and back_btn.isVisible()
        assert back_btn.property("text") == "Câu trả lời"

        back_pos = back_btn.mapToScene(QPointF(back_btn.width() / 2, back_btn.height() / 2)).toPoint()
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, back_pos)
        _process_events(100)
        assert controller.snapshot["view"] == "answer"
        assert controller.snapshot["expanded"] is True
        assert editor.property("text") == "calc"
        assert warnings == []
    finally:
        timer.stop()
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def test_dismiss_finder_restores_cancelled_or_empty_answer_state():
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        # Simulate a cancelled turn with empty assistant answer
        turn = controller.conversation.begin_turn("Câu hỏi bị dừng")
        controller._current_turn_id = turn.turn_id
        controller._current_execution_id = turn.execution_id
        controller._last_user_query = "Câu hỏi bị dừng"
        controller._last_assistant_answer = ""
        controller._view = "answer"
        controller._expanded = True
        controller._status = "Chuột dừng rồi. Chữ bạn đang gõ vẫn còn."

        assert controller.snapshot["view"] == "answer"
        assert controller.snapshot["status"] == "Chuột dừng rồi. Chữ bạn đang gõ vẫn còn."

        # Fake finder hits arrived
        controller._finder_hits = [{"kind": "application", "title": "Calculator", "path": "/Applications/Calculator.app"}]
        controller._finder_query = "calc"

        # Explicitly open suggestions
        opened = controller.openFinderSuggestions()
        assert opened is True
        assert controller.snapshot["view"] == "finder"
        assert controller.snapshot["expanded"] is True

        # Dismiss finder: must restore cancelled/empty answer view, expanded mode and original status
        controller.dismissFinder()
        assert controller.snapshot["view"] == "answer"
        assert controller.snapshot["expanded"] is True
        assert controller.snapshot["status"] == "Chuột dừng rồi. Chữ bạn đang gõ vẫn còn."
    finally:
        controller.close()


def test_is_question_query_rules():
    from rat.ui.quick_pdf_controller import is_question_query

    # Ends with ?
    assert is_question_query("file nào?") is True
    assert is_question_query("báo cáo？") is True

    # More than 8 words
    assert is_question_query("đây là một câu hỏi rất dài có hơn tám từ ở đây") is True  # 12 words
    assert is_question_query("quy chế đào tạo đại học năm 2024") is False  # 7 words

    # Starts with question words (EN & VN)
    assert is_question_query("what is the file") is True
    assert is_question_query("how to open") is True
    assert is_question_query("why is it failing") is True
    assert is_question_query("who is author") is True
    assert is_question_query("can you read") is True
    assert is_question_query("is there a file") is True
    assert is_question_query("ai là tác giả") is True
    assert is_question_query("gì đây") is True
    assert is_question_query("nào tốt hơn") is True
    assert is_question_query("sao lại thế") is True
    assert is_question_query("tại sao không chạy") is True
    assert is_question_query("vì sao thế này") is True
    assert is_question_query("thế nào là hợp lệ") is True
    assert is_question_query("làm sao mở tệp") is True
    assert is_question_query("ở đâu có tài liệu") is True
    assert is_question_query("khi nào họp") is True
    assert is_question_query("bao nhiêu trang") is True
    assert is_question_query("có phải đây là file") is True
    assert is_question_query("hãy tóm tắt") is True
    assert is_question_query("hỏi về quy chế") is True

    # Non-question searches
    assert is_question_query("báo cáo tài chính") is False
    assert is_question_query("app chỉnh ảnh") is False
    assert is_question_query("calc") is False
    assert is_question_query("airdrop tệp tin") is False
    assert is_question_query("whatnot document") is False

    # Words that also begin ordinary searches only count in a question shape
    for search in ("AI ethics report", "sao chép file", "do an tot nghiep", "can thiep rq2", "WHO report"):
        assert is_question_query(search) is False, search
    for question in ("do you know this", "sao không chạy", "who wrote this"):
        assert is_question_query(question) is True, question

    # Instructions for the assistant are never treated as searches
    for instruction in ("xin chào", "viết email xin nghỉ", "tính 12*7+3", "12*7+3", "so sánh hai file",
                        "dịch đoạn này", "explain this", "summarize the paper"):
        assert is_question_query(instruction) is True, instruction

    # An explicit find or open wins over the polite prefix and the length rule
    for search in ("hãy tìm file hợp đồng", "hãy mở word", "tìm file hợp đồng thuê nhà mà tôi ký năm ngoái với chủ trọ"):
        assert is_question_query(search) is False, search
    assert is_question_query("Mở đầu bài báo trình bày phương pháp mới cho bài toán dịch máy") is True
    assert is_question_query("tìm file nào?") is True
    assert is_question_query("báo cáo 2024-2025") is False


def test_controller_handle_composer_return_open_hit_vs_question_vs_nohits(tmp_path):
    app = QGuiApplication.instance() or QGuiApplication([])
    opened = []
    submitted = []
    controller = QuickPDFController(
        auto_init_finder=False,
        open_url=lambda url: opened.append(url) or True,
    )
    controller.ready()
    try:
        controller.submit = lambda q, origin="": submitted.append(q) or True

        f1 = tmp_path / "BC_2024.pdf"
        f1.touch()
        f2 = tmp_path / "BC_2023.pdf"
        f2.touch()

        # 1. Non-question with hits -> opens first hit when selected_index = -1
        controller._finder_query = "báo cáo tài chính"
        controller._finder_hits = [
            {"kind": "file", "title": "BC_2024.pdf", "path": str(f1), "is_pdf": False},
            {"kind": "file", "title": "BC_2023.pdf", "path": str(f2), "is_pdf": False},
        ]
        controller._view = "finder"
        res = controller.handleComposerReturn("báo cáo tài chính", selected_index=-1)
        assert res is True
        assert len(opened) == 1
        assert "BC_2024.pdf" in opened[0].toString()
        assert len(submitted) == 0

        # 2. Non-question with hits and specific selection
        res2 = controller.handleComposerReturn("báo cáo tài chính", selected_index=1)
        assert res2 is True
        assert len(opened) == 2
        assert "BC_2023.pdf" in opened[1].toString()

        # 3. Question -> calls submitQuery / submit, does NOT open hit
        res_q = controller.handleComposerReturn("tại sao có hai báo cáo?", selected_index=-1)
        assert res_q is True
        assert len(opened) == 2
        assert len(submitted) == 1
        assert submitted[0] == "tại sao có hai báo cáo?"

        # 4. Non-question with 0 hits -> shows Vietnamese feedback, does NOT submit
        controller._finder_query = "tài liệu không có"
        controller._finder_hits = []
        res_empty = controller.handleComposerReturn("tài liệu không có", selected_index=-1)
        assert res_empty is True
        assert len(opened) == 2
        assert len(submitted) == 1  # Not incremented!
        assert "không tìm ra" in controller.snapshot["status"]
        assert "không tìm ra" in controller.snapshot["finderFeedback"]
    finally:
        controller.close()


def test_controller_handle_composer_return_waits_for_search(tmp_path):
    from PyQt6.QtCore import QTimer
    from rat.engine.progressive_search import SearchHit, SearchSnapshot

    app = QGuiApplication.instance() or QGuiApplication([])
    opened = []
    controller = QuickPDFController(
        auto_init_finder=False,
        open_url=lambda url: opened.append(url) or True,
    )
    controller.ready()
    fake_file = tmp_path / "KetQua.txt"
    fake_file.touch()
    try:
        # Simulate an in-flight search
        controller._finder_in_flight_query = "chờ kết quả"
        controller._finder_query = "chờ kết quả"
        controller._finder_hits = []

        # Deliver snapshot after 80ms via timer
        def deliver():
            hit = SearchHit(
                resource_id="r1",
                kind="file",
                title="KetQua.txt",
                path=str(fake_file),
                origin="test",
            )
            snap = SearchSnapshot(
                query_id=1,
                query="chờ kết quả",
                phase="initial",
                hits=(hit,),
                selected_id=None,
                complete=True,
                elapsed_ms=10.0,
            )
            controller._finder_delivered.emit(snap)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(deliver)
        timer.start(80)

        # Calling handleComposerReturn while search is running must wait and then open the hit
        res = controller.handleComposerReturn("chờ kết quả", selected_index=-1)
        assert res is True
        assert len(opened) == 1
        assert "KetQua.txt" in opened[0].toString()
    finally:
        timer.stop()
        controller.close()


def test_qml_composer_return_key_opens_first_hit_when_unselected(finder_fixture):
    """When hits are showing and text is not a question, Return opens hit 0 even if selectedFinderIndex == -1."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )

    view = QQuickView()
    view.setInitialProperties({
        "liveController": controller,
        "darkMode": False,
        "reduceMotion": True,
    })
    qml_path = Path(__file__).resolve().parents[1] / "rat/ui/quick/PDFDesk.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_path)))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    _process_events(100)

    try:
        root = view.rootObject()
        editor = root.findChild(QQuickItem, "draftEditor")
        assert editor is not None
        editor.forceActiveFocus()

        # Type "calc"
        editor.setProperty("text", "calc")
        _process_events(300)
        assert controller.snapshot["view"] == "finder"
        assert len(controller.snapshot["finderHits"]) >= 1

        # selectedFinderIndex is -1 (user did NOT press Arrow Down)
        assert root.property("selectedFinderIndex") == -1

        # Check hint text for non-question: must show ↵ mở
        hints = {hint["key"]: hint["label"] for hint in root.property("composerKeyHints").toVariant()}
        assert hints["↵"] == "mở"

        # Press Return directly
        QTest.keyClick(view, Qt.Key.Key_Return)
        _process_events(100)

        # Hit 0 (Calculator) must have been opened!
        assert len(opened_urls) == 1
        assert "Calculator.app" in opened_urls[0].toString()
    finally:
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def _titles_for(query, *apps_reasons, intent=None):
    from rat.ui.quick_pdf_controller import order_finder_hits
    raw = [{"kind": "file", "title": "note.pdf", "match_reason": "Khớp chủ đề ngữ nghĩa (Semantic)"}]
    raw += [{"kind": "application", "title": f"app{i}", "match_reason": reason} for i, reason in enumerate(apps_reasons)]
    return [hit["title"] for hit in order_finder_hits(raw, query, intent)]


def test_files_lead_unless_the_query_asks_for_or_names_an_app():
    purpose, name = "Khớp công dụng", "Khớp tên ứng dụng"
    assert _titles_for("chỉnh ảnh", purpose) == ["note.pdf", "app0"]
    assert _titles_for("app chỉnh ảnh", purpose) == ["app0", "note.pdf"]
    assert _titles_for("ứng dụng chỉnh ảnh", purpose) == ["app0", "note.pdf"]
    assert _titles_for("ung dung chinh anh", purpose) == ["app0", "note.pdf"]
    assert _titles_for("photoshop", name) == ["app0", "note.pdf"]
    assert _titles_for("chỉnh ảnh", purpose, name) == ["app0", "app1", "note.pdf"]
    # "application" inside a word is not a request for an app
    assert _titles_for("applications of calculus", purpose) == ["note.pdf", "app0"]


def test_open_intent_puts_apps_first_and_sections_are_marked():
    from types import SimpleNamespace
    from rat.ui.quick_pdf_controller import order_finder_hits
    assert _titles_for("mở word", "Khớp công dụng", intent=SimpleNamespace(resource_kind="application"))[0] == "app0"
    hits = order_finder_hits(
        [{"kind": "application", "title": "a", "match_reason": "Khớp công dụng"},
         {"kind": "file", "title": "f", "match_reason": ""},
         {"kind": "file", "title": "g", "match_reason": ""}], "chỉnh ảnh")
    assert [(h["title"], h["is_first_of_section"], h["section_title"]) for h in hits] == [
        ("f", True, "TÀI LIỆU & TỆP"), ("g", False, "TÀI LIỆU & TỆP"), ("a", True, "ỨNG DỤNG")]


def test_command_number_opens_that_row_and_keeps_the_composer(finder_fixture):
    """⌘1 to ⌘3 work while the composer still holds the query, and each row shows its key."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []
    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )
    view = QQuickView()
    view.setInitialProperties({"liveController": controller, "darkMode": False, "reduceMotion": True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    view.requestActivate()
    _process_events(100)
    command = Qt.KeyboardModifier.ControlModifier

    try:
        root = view.rootObject()
        editor = root.findChild(QQuickItem, "draftEditor")
        editor.forceActiveFocus()

        # No results yet: the key does nothing and types nothing
        QTest.keyClick(view, Qt.Key.Key_1, command)
        _process_events(50)
        assert opened_urls == [] and editor.property("text") == ""

        editor.setProperty("text", "c")
        _process_events(300)
        hits = controller.snapshot["finderHits"]
        openable = [i for i, hit in enumerate(hits[:3]) if not hit["is_pdf"]]
        assert len(hits) >= 2 and openable

        # Repeater rows are visual children only, so findChild cannot reach them
        pending, found = [root], {}
        while pending:
            item = pending.pop()
            found[item.objectName()] = item
            pending.extend(item.childItems())
        for index, hit in enumerate(hits[:3]):
            assert found[f"finderHitKey_{index}"].isVisible(), hit["title"]

        keys = [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3]
        for index in openable:
            opened_urls.clear()
            QTest.keyClick(view, keys[index], command)
            _process_events(50)
            assert [url.toLocalFile() for url in opened_urls] == [hits[index]["path"]]
            assert editor.property("text") == "c"

        # A row that does not exist opens nothing
        if len(hits) < 3:
            opened_urls.clear()
            QTest.keyClick(view, Qt.Key.Key_3, command)
            _process_events(50)
            assert opened_urls == []
    finally:
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def test_qml_composer_return_submits_when_question(finder_fixture):
    """When text is a question, Return asks Chuột instead of opening hits."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []
    submitted = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )
    controller.submit = lambda q, origin="": submitted.append(q) or True

    view = QQuickView()
    view.setInitialProperties({
        "liveController": controller,
        "darkMode": False,
        "reduceMotion": True,
    })
    qml_path = Path(__file__).resolve().parents[1] / "rat/ui/quick/PDFDesk.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_path)))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    _process_events(100)

    try:
        root = view.rootObject()
        editor = root.findChild(QQuickItem, "draftEditor")
        assert editor is not None
        editor.forceActiveFocus()

        # Type a question
        editor.setProperty("text", "làm sao để tính calc?")
        _process_events(300)

        # Press Return
        QTest.keyClick(view, Qt.Key.Key_Return)
        _process_events(100)

        assert len(opened_urls) == 0
        assert len(submitted) == 1
        assert submitted[0] == "làm sao để tính calc?"
    finally:
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def test_qml_composer_return_no_hits_feedback_and_tab_to_ask(finder_fixture):
    """When search finishes with no hits, Return shows feedback; Tab sends query to Chuột."""
    app = QGuiApplication.instance() or QGuiApplication([])
    opened_urls = []
    submitted = []

    controller = QuickPDFController(
        finder_search=finder_fixture["search"],
        finder_catalog=finder_fixture["catalog"],
        auto_init_finder=False,
        open_url=lambda url: opened_urls.append(url) or True,
    )
    controller.submit = lambda q, origin="": submitted.append(q) or True

    view = QQuickView()
    view.setInitialProperties({
        "liveController": controller,
        "darkMode": False,
        "reduceMotion": True,
    })
    qml_path = Path(__file__).resolve().parents[1] / "rat/ui/quick/PDFDesk.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_path)))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    _process_events(100)

    try:
        root = view.rootObject()
        editor = root.findChild(QQuickItem, "draftEditor")
        assert editor is not None
        editor.forceActiveFocus()

        # Type non-existent query
        editor.setProperty("text", "nonexistentquery12345")
        _process_events(300)
        assert len(controller.snapshot["finderHits"]) == 0

        # Press Return -> must not call submit, shows feedback
        QTest.keyClick(view, Qt.Key.Key_Return)
        _process_events(100)

        assert len(opened_urls) == 0
        assert len(submitted) == 0
        status_label = root.findChild(QQuickItem, "composerDropStatus")
        assert status_label is not None
        assert "không tìm ra" in status_label.property("text")
        assert "Tab" in status_label.property("text")

        # Now press Tab -> sends query to Chuột!
        QTest.keyClick(view, Qt.Key.Key_Tab)
        _process_events(100)

        assert len(submitted) == 1
        assert submitted[0] == "nonexistentquery12345"
    finally:
        controller.close()
        view.close()
        view.setSource(QUrl())
        view.deleteLater()
        controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('display_path, folder', [
    ('~/Documents/Hoc ky 2/Bai tap/Tuan 12/a.txt', 'Bai tap › Tuan 12'),
    ('~/Documents/a.pdf', 'Documents'),
    ('~/a.pdf', 'Thư mục nhà'),
    ('/Volumes/USB/a.pdf', 'Volumes › USB'),
])
def test_short_folder_keeps_only_the_last_two_folders(display_path, folder):
    assert short_folder(display_path) == folder


def test_row_detail_speaks_plainly_and_drops_the_app_path():
    assert finder_row_detail('file', 'Khớp chủ đề ngữ nghĩa (Semantic)', '~/Docs/Tuan 12/a.txt') == 'Khớp theo nghĩa · Docs › Tuan 12'
    assert finder_row_detail('file', 'Khớp nội dung: tiền cọc hai tháng', '~/Docs/a.txt') == 'Khớp nội dung · Docs'
    assert finder_row_detail('application', 'Khớp tên ứng dụng', '/Applications/Calculator.app') == 'Khớp tên ứng dụng'


def test_finder_row_shows_short_folder_and_keeps_full_path_in_tooltip(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    controller = QuickPDFController(
        finder_search=finder_fixture['search'], finder_catalog=finder_fixture['catalog'],
        db_path=finder_fixture['db_path'], auto_init_finder=False, open_url=lambda url: True,
    )
    view = QQuickView()
    view.setInitialProperties({'liveController': controller, 'darkMode': False, 'reduceMotion': True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    try:
        view.rootObject().findChild(QQuickItem, 'draftEditor').setProperty('text', 'tim file danh sach sinh vien')
        _process_events(300)
        hit = controller.snapshot['finderHits'][0]
        assert hit['path'] == finder_fixture['txt_path']

        def walk(item):
            yield item
            for child in item.childItems():
                yield from walk(child)
        by_name = {i.objectName(): i for i in walk(view.rootObject()) if i.objectName()}
        detail = by_name['finderMatchReason_0'].property('text')
        assert finder_fixture['txt_path'] not in detail
        assert hit['display_path'] not in detail
        assert short_folder(hit['display_path']) in detail
        assert by_name['finderKind_0'].property('rotation') != 0
        assert by_name['finderContentExcerpt_0'].property('text') != hit['display_path']

        stroke = by_name['finderSelectionStroke_0']
        assert not stroke.property('visible')
        view.rootObject().setProperty('selectedFinderIndex', 0)
        _process_events(100)
        assert stroke.property('visible')
        title = by_name['finderTitle_0']
        card = by_name['finderHit_0']
        title_left = title.mapToItem(card, QPointF(0, 0)).x()
        assert stroke.property('x') + stroke.property('width') <= title_left
        view.rootObject().setProperty('selectedFinderIndex', -1)
        _process_events(50)
        assert not stroke.property('visible')
    finally:
        _dispose(view, controller)


def _paper_desk(finder_fixture, reduce_motion):
    controller = QuickPDFController(
        finder_search=finder_fixture['search'], finder_catalog=finder_fixture['catalog'],
        db_path=finder_fixture['db_path'], auto_init_finder=False, open_url=lambda url: True,
    )
    view = QQuickView()
    view.setInitialProperties({'liveController': controller, 'darkMode': False, 'reduceMotion': reduce_motion})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready
    controller.ready()
    view.show()
    return view, controller


def _type_and_read_nudge(view, text):
    root = view.rootObject()
    root.findChild(QQuickItem, 'draftEditor').setProperty('text', text)
    # Long enough for the initial and refined results, which may each count as new.
    _process_events(800)
    assert root.findChild(QQuickItem, 'resultPaper').property('rotation') == 0
    return root.property('paperNudgeTarget')


def test_paper_shifts_on_new_results_only_and_the_text_sheet_stays_straight(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    view, controller = _paper_desk(finder_fixture, reduce_motion=False)
    try:
        calc = _type_and_read_nudge(view, 'calc')
        assert controller.snapshot['view'] == 'finder'
        assert calc != 0

        assert _type_and_read_nudge(view, 'calc ') == calc

        other = _type_and_read_nudge(view, 'tim file danh sach sinh vien')
        assert other != calc
        assert -0.7 <= other <= 0.6
    finally:
        _dispose(view, controller)


def test_reduced_motion_keeps_the_paper_still(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    view, controller = _paper_desk(finder_fixture, reduce_motion=True)
    try:
        assert _type_and_read_nudge(view, 'calc') == 0
        assert _type_and_read_nudge(view, 'tim file danh sach sinh vien') == 0
    finally:
        _dispose(view, controller)


def test_backing_sheet_follows_the_nudge(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    view, controller = _paper_desk(finder_fixture, reduce_motion=True)
    try:
        root = view.rootObject()
        root.setProperty('paperNudgeTarget', 0.5)
        assert root.findChild(QQuickItem, 'paperBackingSheet').property('rotation') == pytest.approx(-0.4)
    finally:
        _dispose(view, controller)


def test_summon_keycap_replaces_the_build_line_and_still_drags(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    view, controller = _paper_desk(finder_fixture, reduce_motion=True)
    try:
        root = view.rootObject()
        cap_text = root.findChild(QQuickItem, 'summonKeyText')
        assert cap_text.property('text') == 'RAT'
        assert root.findChild(QQuickItem, 'dragHandle') is not None
        assert root.findChild(QQuickItem, 'uiBuildLabel') is None
        assert root.property('uiBuildLabel').startswith('Build ')

        controller.set_shortcut_label('⌃⌥Space')
        _process_events(50)
        assert controller.snapshot['shortcutLabel'] == '⌃⌥Space'
        assert cap_text.property('text') == '⌃⌥Space'
        moves = []
        root.moveRequested.connect(lambda: moves.append(True))
        handle = root.findChild(QQuickItem, 'dragHandle')
        center = handle.mapToScene(QPointF(handle.width() / 2, handle.height() / 2))
        QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center.toPoint())
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center.toPoint())
        assert moves == [True]
    finally:
        _dispose(view, controller)


def _sized_desk(finder_fixture, width):
    controller = QuickPDFController(
        finder_search=finder_fixture['search'], finder_catalog=finder_fixture['catalog'],
        db_path=finder_fixture['db_path'], auto_init_finder=False, open_url=lambda url: True,
    )
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({'liveController': controller, 'darkMode': False, 'reduceMotion': True})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'rat/ui/quick/PDFDesk.qml')))
    assert view.status() == QQuickView.Status.Ready
    view.resize(width, 400)
    controller.ready()
    view.show()
    _process_events(100)
    return view, controller


def _scene_rect(item):
    top_left = item.mapToScene(QPointF(0, 0))
    return top_left.x(), top_left.y(), top_left.x() + item.width(), top_left.y() + item.height()


def test_rat_stands_beside_the_composer_when_there_is_room(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    view, controller = _sized_desk(finder_fixture, 720)
    try:
        root = view.rootObject()
        assert root.property('ratBesideComposer')
        rat = _scene_rect(root.findChild(QQuickItem, 'mascotCrop'))
        composer = _scene_rect(root.findChild(QQuickItem, 'composer'))
        assert rat[0] >= composer[2]
        assert rat[2] <= view.width()
        assert rat[3] == pytest.approx(composer[3])
        assert root.findChild(QQuickItem, 'ratBubbleTail').property('visible')

        root.findChild(QQuickItem, 'draftEditor').setProperty('text', 'calc')
        _process_events(400)
        assert controller.snapshot['view'] == 'finder'
        assert root.findChild(QQuickItem, 'mascotCrop').property('visible')
        paper = _scene_rect(root.findChild(QQuickItem, 'resultPaper'))
        assert paper[0] == pytest.approx(composer[0])
        assert paper[2] <= rat[0]
    finally:
        _dispose(view, controller)


def test_narrow_desk_keeps_the_rat_above_the_composer(finder_fixture):
    app = QGuiApplication.instance() or QGuiApplication([])
    view, controller = _sized_desk(finder_fixture, 520)
    try:
        root = view.rootObject()
        assert not root.property('ratBesideComposer')
        rat = _scene_rect(root.findChild(QQuickItem, 'mascotCrop'))
        composer = _scene_rect(root.findChild(QQuickItem, 'composer'))
        assert rat[3] == pytest.approx(composer[1])
        assert rat[0] >= 0 and rat[2] <= view.width()
        assert not root.findChild(QQuickItem, 'ratBubbleTail').property('visible')
    finally:
        _dispose(view, controller)
