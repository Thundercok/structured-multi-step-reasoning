import sys
import os
from pathlib import Path
from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PIL import Image
import numpy as np

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window

os.environ["QT_QUICK_BACKEND"] = "software"

app = QApplication.instance() or QApplication(sys.argv)
controller = QuickPDFController(auto_init_finder=False)
controller.ready()

view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.setInitialProperties({"liveController": controller, "reduceMotion": True})
view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
root = view.rootObject()
view.resize(520, 570)
timer = bind_desk_window(view)
view.show()
QTest.qWait(300)

def wait_for_idle(timeout_ms=10000):
    elapsed = 0
    while elapsed < timeout_ms:
        QTest.qWait(50)
        elapsed += 50
        if not controller.snapshot.get("busy"):
            return
    raise TimeoutError(f"Timed out waiting for controller idle, snapshot={controller.snapshot}")

# 1. Type draft in composer
editor = root.findChild(QQuickItem, "draftEditor")
assert editor is not None, "draftEditor must exist"
initial_draft = "Câu hỏi đang soạn dở trong ô chat: chi phí triển khai LLM"
editor.setProperty("text", initial_draft)
assert editor.property("text") == initial_draft

# 2. Select authentic PDF
pdf_path = "work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf"
assert Path(pdf_path).exists(), f"PDF path {pdf_path} must exist"
controller.openPdfDocument(pdf_path)
wait_for_idle()

# 3. Perform search for keyword "routing"
controller.search("routing")
wait_for_idle()
assert controller.snapshot.get("items"), f"Search must return items for 'routing', got: {controller.snapshot}"

# 4. Open page 1 from search hit / readPage
controller.readPage(1)
wait_for_idle()

# Verify view and properties
snap = controller.snapshot
assert snap.get("view") == "page", f"Expected view == 'page', got {snap.get('view')}"
assert snap.get("pageNumber") == 1, f"Expected pageNumber == 1, got {snap.get('pageNumber')}"
assert snap.get("pageCount") == 25, f"Expected pageCount == 25, got {snap.get('pageCount')}"

# Verify UI elements
title_item = root.findChild(QQuickItem, "pageSourceTitle")
assert title_item is not None, "pageSourceTitle must exist"
title_text = title_item.property("text")
print(f"pageSourceTitle text: {title_text!r}")
assert title_text == "Nguồn · Trang 1/25", f"Unexpected title text: {title_text!r}"

meta_item = root.findChild(QQuickItem, "pageMetadataLabel")
assert meta_item is not None, "pageMetadataLabel must exist"
meta_text = meta_item.property("text")
print(f"pageMetadataLabel text: {meta_text!r}")
assert meta_text == "arxiv_2506.22716_original.pdf", f"Unexpected meta text: {meta_text!r}"

composer_status = root.findChild(QQuickItem, "composerDropStatus")
assert composer_status is not None, "composerDropStatus must exist"
status_text = composer_status.property("text")
print(f"composerDropStatus text: {status_text!r}")
assert "Trang" not in status_text, f"Page number should not be in composer footer: {status_text!r}"
assert status_text == "↵ hỏi Chuột · ⌘F tìm chữ trong PDF", f"Unexpected status text: {status_text!r}"

# Verify draft text is untouched
assert editor.property("text") == initial_draft, "Draft in composer was mutated!"

# 5. Capture at 520px and 700px, checking overflow
paper = root.findChild(QQuickItem, "resultPaper")
assert paper is not None, "resultPaper must exist"

results = {}
for w in [520, 700]:
    view.resize(w, round(root.property("preferredWindowHeight")))
    QTest.qWait(350)
    
    paper_right = paper.mapToScene(QPointF(0, 0)).x() + paper.width()
    for obj_name in ("copyCitation", "liveFoldButton"):
        ctrl = root.findChild(QQuickItem, obj_name)
        if ctrl is not None and ctrl.isVisible():
            ctrl_right = ctrl.mapToScene(QPointF(0, 0)).x() + ctrl.width()
            overflow = ctrl_right - paper_right
            print(f"Width {w}px, {obj_name} right: {ctrl_right:.1f}, paper right: {paper_right:.1f}, overflow: {overflow:.1f}px")
            assert overflow <= 0.5, f"{obj_name} overflows paper by {overflow:.1f}px at {w}px width!"
    
    out_file = f"work/turn3_metadata_after_{w}px.png"
    success = view.grabWindow().save(out_file)
    assert success, f"Failed to save {out_file}"
    im = Image.open(out_file)
    arr = np.array(im)
    alpha_mean = float(arr[:, :, 3].mean())
    nonzero = int(np.count_nonzero(arr[:, :, :3]))
    print(f"After {w}px: size={im.size}, alpha_mean={alpha_mean:.1f}, nonzero_rgb={nonzero}")
    assert nonzero > 100_000, f"Image {out_file} has insufficient non-zero pixels ({nonzero})!"
    results[w] = (im.size, alpha_mean, nonzero)

# 6. Test min / full toggle preserves draft and reading state
root.setProperty("expanded", False)
controller.setExpanded(False)
QTest.qWait(250)
assert editor.property("text") == initial_draft, "Draft lost on fold!"

root.setProperty("expanded", True)
controller.setExpanded(True)
QTest.qWait(250)
assert editor.property("text") == initial_draft, "Draft lost on expand!"
assert controller.snapshot.get("pageNumber") == 1, "Page number lost on expand!"

view.close()
print("All verification checks passed successfully!")
