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
from PyQt6.QtCore import QCoreApplication, QUrl, Qt
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.crawler.db import Database
from rat.engine.app_resolver import Application, ApplicationCatalog
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator
from rat.ui.quick_pdf_controller import QuickPDFController
from reasoning.bundle import create_synthetic_specimen_bundle


def _process_events(ms: int = 150):
    deadline = time.perf_counter() + (ms / 1000.0)
    while time.perf_counter() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)


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
    app = QApplication.instance() or QApplication([])
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
    app = QApplication.instance() or QApplication([])

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
    app = QApplication.instance() or QApplication([])
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

    controller.close()


def test_quick_finder_ask_about_file(finder_fixture):
    """Clicking 'Hỏi về tệp' attaches the file context to assistant reasoning."""
    app = QApplication.instance() or QApplication([])

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
    app = QApplication.instance() or QApplication([])

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
    app = QApplication.instance() or QApplication([])
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

    view.close()
    controller.close()


def test_quick_finder_keyboard_navigation_and_actions(finder_fixture):
    """Arrow Up/Down keys cycle through finder hits; Return key opens selected hit."""
    app = QApplication.instance() or QApplication([])
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

    view.close()
    controller.close()


def test_quick_finder_reveal_and_preview_actions(finder_fixture):
    """Verify quicklook preview and reveal in Finder actions work and shorten home path."""
    app = QApplication.instance() or QApplication([])
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
    app = QApplication.instance() or QApplication([])

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

    view.close()
    controller.close()
