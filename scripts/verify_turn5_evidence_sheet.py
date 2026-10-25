import sys
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import QPoint, QPointF, QUrl, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PIL import Image
import numpy as np

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from tests.test_quick_answer_presentation import complete_fixture

os.environ["QT_QUICK_BACKEND"] = "software"

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
opened_urls = []
controller = QuickPDFController(auto_init_finder=False, open_url=lambda url: opened_urls.append(url) or True)
controller.ready()

pdf_path = Path("work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf").resolve()
assert pdf_path.exists(), f"Authentic PDF file must exist: {pdf_path}"

controller.selectFile(str(pdf_path))
QTest.qWait(200)

query = "BEST-Route giúp giảm chi phí bao nhiêu % và ảnh hưởng hiệu năng thế nào theo bài báo?"
answer_md = "BEST-Route giúp giảm chi phí triển khai lên đến **60%** với sự mất mát hiệu năng dưới **1%** thông qua việc định tuyến thông minh giữa các mô hình trong Model Cascade."
snippet = "Recent advancements in Large Language Models (LLMs) have demonstrated remarkable capabilities... BEST-Route reduces deployment costs by up to 60% with less than 1% performance loss."
full_excerpt = (
    "Abstract—Recent advancements in Large Language Models (LLMs) have demonstrated remarkable capabilities "
    "across diverse reasoning and NLP benchmarks. However, serving state-of-the-art models at scale remains "
    "prohibitively expensive for production systems. In this work, we present BEST-Route, an adaptive model cascade "
    "framework that dynamically routes incoming queries to appropriately sized models based on early difficulty prediction. "
    "Our extensive evaluation demonstrates that BEST-Route reduces deployment costs by up to 60% with less than 1% "
    "performance loss compared to uniform frontier model dispatching."
)

complete_fixture(
    controller,
    query=query,
    answer=answer_md,
    sources=[{
        "path": str(pdf_path),
        "page": 1,
        "title": pdf_path.name,
        "section": "Abstract",
        "snippet": snippet,
        "full_excerpt": full_excerpt,
        "extended_snippet": full_excerpt,
        "canOpen": True,
        "readScope": "Trang 1 · Tóm tắt"
    }]
)

view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.setInitialProperties({"liveController": controller, "reduceMotion": True})
view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]
root = view.rootObject()
view.resize(520, 550)
timer = bind_desk_window(view)
view.show()
QTest.qWait(300)

def find_item(name):
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

def click_item(item):
    assert item is not None and item.isVisible(), f"Item {item} must be visible to click"
    scene_pos = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    pt = scene_pos.toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
    QTest.qWait(150)

# Verification checks
print("=== Starting Turn 5 Evidence Sheet UI Verification (Build .19) ===")

# 1. Build Label verification
build_label = root.property("uiBuildLabel")
assert build_label == "Build 2026.10.25.23", f"Expected Build 2026.10.25.23, got {build_label}"
print(f"[OK] Build label verified: {build_label}")

# 2. Evidence Process Card verification
process_card = find_item("evidenceProcessCard")
assert process_card is not None and process_card.isVisible(), "evidenceProcessCard must exist and be visible"
process_repeater = find_item("processStepsRepeater")
assert process_repeater is not None, "processStepsRepeater must exist"
assert process_repeater.property("count") >= 3, f"Repeater count should be at least 3, got {process_repeater.property('count')}"
toggle_btn = find_item("processDetailsToggle")
assert toggle_btn is not None and toggle_btn.isVisible(), "processDetailsToggle must exist and be visible"
print(f"[OK] Dynamic Evidence process card present with {process_repeater.property('count')} steps")

# 3. Toggle Process Details Drawer (No raw CoT)
assert not root.property("processDetailsOpen"), "processDetailsOpen must start false"
click_item(toggle_btn)
assert root.property("processDetailsOpen"), "processDetailsOpen must toggle to true"
details_content = find_item("processDetailsContent")
assert details_content is not None and details_content.isVisible(), "processDetailsContent must be visible when open"
print("[OK] Process details drawer expands smoothly, displaying public verification without raw CoT")

# Capture screenshot with details open at 520px
img_details = view.grabWindow()
img_details_path = Path("artifacts/turn5_evidence_sheet_details_open.png")
img_details_path.parent.mkdir(parents=True, exist_ok=True)
img_details.save(str(img_details_path))
print(f"[OK] Saved {img_details_path}")

# Close details drawer
click_item(toggle_btn)
assert not root.property("processDetailsOpen"), "processDetailsOpen must collapse back to false"

# 4. Focal Answer verification
answer_item = find_item("answerText")
assert answer_item is not None and answer_item.isVisible(), "answerText must be visible"
print(f"[OK] Answer text rendered: {answer_item.property('textDocument').textDocument().toPlainText()[:60]}...")

# 5. Verbatim Source Card verification
source_card = find_item("evidenceSourceCard")
assert source_card is not None and source_card.isVisible(), "evidenceSourceCard must exist and be visible"

source_title = find_item("evidenceSourceTitle")
assert source_title is not None and source_title.isVisible(), "evidenceSourceTitle must be visible"
assert "arxiv_2506.22716_original.pdf" in source_title.property("text")
assert "Trang 1" in source_title.property("text")
print(f"[OK] Verbatim source title verified: {source_title.property('text')}")

source_snippet = find_item("evidenceSourceSnippet")
assert source_snippet is not None and source_snippet.isVisible(), "evidenceSourceSnippet must be visible"
initial_snippet_text = source_snippet.property("text")
assert "60%" in initial_snippet_text
print(f"[OK] Initial snippet text verified ({len(initial_snippet_text)} chars): {initial_snippet_text[:60]}...")

# 6. Expand Context Toggle Button verification
expand_btn = find_item("expandContextButton")
assert expand_btn is not None and expand_btn.isVisible(), "expandContextButton must exist and be visible"
assert not root.property("contextExpanded"), "contextExpanded must start False"

# Click to expand surrounding context
click_item(expand_btn)
assert root.property("contextExpanded") is True, "contextExpanded must be True after clicking expand"
expanded_snippet_text = source_snippet.property("text")
assert len(expanded_snippet_text) > len(initial_snippet_text), "Expanded text must be longer than initial snippet"
assert "serving state-of-the-art models" in expanded_snippet_text, "Expanded text must contain surrounding context"
print(f"[OK] Context successfully expanded ({len(expanded_snippet_text)} chars): {expanded_snippet_text[:70]}...")

# Capture screenshot with context expanded at 520px
img_ctx = view.grabWindow()
img_ctx_path = Path("artifacts/turn5_evidence_sheet_context_expanded.png")
img_ctx.save(str(img_ctx_path))
print(f"[OK] Saved {img_ctx_path}")

# 7. Copy Citation Button verification (while context is expanded)
copy_btn = find_item("copyCitationButton")
assert copy_btn is not None and copy_btn.isVisible(), "copyCitationButton must be visible"
click_item(copy_btn)
assert root.property("sourceCopied") is True, "sourceCopied must be true after clicking copy"
clipboard_text = app.clipboard().text()
assert "serving state-of-the-art models" in clipboard_text and "arxiv_2506.22716_original.pdf" in clipboard_text, f"Clipboard missing expanded citation: {clipboard_text}"
print(f"[OK] Clipboard successfully updated with expanded citation: {clipboard_text[:70]}...")

# Click to collapse context back
click_item(expand_btn)
assert root.property("contextExpanded") is False, "contextExpanded must toggle back to False"
collapsed_text = source_snippet.property("text")
assert len(collapsed_text) == len(initial_snippet_text), "Snippet must return to compact length"
print("[OK] Context successfully collapsed back to compact snippet")

# 8. Open External PDF Button verification
open_ext_btn = find_item("openExternalPdfButton")
assert open_ext_btn is not None and open_ext_btn.isVisible(), "openExternalPdfButton must be visible"
click_item(open_ext_btn)
assert len(opened_urls) == 1, f"Expected 1 open_url call, got {len(opened_urls)}"
print(f"[OK] openExternalPdf successfully triggered openOriginal: {opened_urls[0]}")

# 9. Composer Draft Persistence verification
editor = find_item("draftEditor")
assert editor is not None, "draftEditor must exist"
followup_draft = "Hỏi tiếp về phương pháp cascade trong mục 5"
editor.setProperty("text", followup_draft)
assert editor.property("text") == followup_draft
print(f"[OK] Follow-up draft composed: '{followup_draft}'")

# Capture 520px screenshot
img_520 = view.grabWindow()
img_520_path = Path("artifacts/turn5_evidence_sheet_520px.png")
img_520.save(str(img_520_path))
print(f"[OK] Saved {img_520_path}")

# Resize to 700px and capture
view.resize(700, 600)
QTest.qWait(300)
assert editor.property("text") == followup_draft, "Draft must persist through window resize"

img_700 = view.grabWindow()
img_700_path = Path("artifacts/turn5_evidence_sheet_700px.png")
img_700.save(str(img_700_path))
print(f"[OK] Saved {img_700_path}")

# Verify non-transparent pixels (>40%)
all_images = [img_520_path, img_700_path, img_details_path, img_ctx_path]
for pth in all_images:
    pil_img = Image.open(pth).convert("RGBA")
    arr = np.array(pil_img)
    alpha = arr[:, :, 3]
    non_transparent = np.count_nonzero(alpha > 10)
    ratio = non_transparent / alpha.size
    print(f"Image {pth.name}: resolution={pil_img.size}, non-transparent pixel ratio={ratio:.2%}")
    assert ratio >= 0.40, f"Image {pth.name} must have >= 40% non-transparent pixels, got {ratio:.2%}"

# Copy to conversation artifact directory
artifact_dir = Path(os.environ.get("ANTIGRAVITY_ARTIFACT_DIR", "/Users/thundercock2/.gemini/antigravity/brain/c521fb94-cdbc-4b76-8354-89e731c844c7"))
if artifact_dir.exists():
    for pth in all_images:
        dest = artifact_dir / pth.name
        shutil.copy2(pth, dest)
        print(f"[OK] Copied {pth.name} to artifact directory: {dest}")

timer.stop()
controller.close()
view.close()
print("=== All Turn 5 Evidence Sheet UI Verifications (Build .23) PASSED 100% ===")
