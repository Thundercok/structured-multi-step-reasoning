import os
import sys
import time
import shutil
from pathlib import Path
from PIL import Image
import numpy as np

os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import SLMEngine

pdf_path = Path("work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf").resolve()
assert pdf_path.exists(), f"Missing PDF at {pdf_path}"

app = QGuiApplication.instance() or QGuiApplication([])

slm_engine = SLMEngine(model="qwen3:4b-instruct", ollama_url="http://localhost:11434")
runtime = AssistantRuntime(model_client=slm_engine, use_live_model=True)
controller = QuickPDFController(assistant_runtime=runtime, auto_init_finder=False)
controller.ready()

# Select authentic PDF
controller.selectFile(str(pdf_path))

view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.setInitialProperties({"liveController": controller, "reduceMotion": True})
view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
root = view.rootObject()
view.resize(520, round(root.property("preferredWindowHeight")))
timer = bind_desk_window(view)
view.show()
QTest.qWait(300)

def wait_for_idle(timeout_ms=30000):
    elapsed = 0
    while elapsed < timeout_ms:
        QTest.qWait(100)
        elapsed += 100
        if not controller.snapshot.get("busy"):
            return
    raise TimeoutError(f"Timed out waiting for controller idle, snapshot={controller.snapshot}")

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

def click_item(item):
    assert item is not None, "Cannot click None item"
    scene_pos = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, scene_pos)
    QTest.qWait(100)

wait_for_idle()

# 1. Verify initial document selection state
assert controller.snapshot.get("fileName") == "arxiv_2506.22716_original.pdf"
doc_chip = find_item(root, "documentMenu")
assert doc_chip.property("text") == "arxiv_2506.22716_original.pdf"

# 2. Enter genuine question into composer
user_query = "Tóm tắt chi phí triển khai LLM và phương pháp Model Cascade trong bài báo này"
editor = find_item(root, "draftEditor")
assert editor is not None
editor.forceActiveFocus()
editor.setProperty("text", user_query)
QTest.qWait(50)
assert editor.property("text") == user_query

# 3. Submit question to live model (Budget: exactly 1 request)
print(f"Submitting live query: {user_query!r}")
start_time = time.perf_counter()
controller.submitQuery(user_query)
wait_for_idle(timeout_ms=60000)
elapsed_s = time.perf_counter() - start_time
print(f"Live model response received in {elapsed_s:.2f}s")

# 4. Verify Answer Presentation & Source Label
assert controller.snapshot.get("view") == "answer", f"Expected answer view, got {controller.snapshot.get('view')}"
answer_text = controller.snapshot.get("answerText")
print("\n--- ACTUAL LIVE MODEL RESPONSE ---")
print(answer_text)
print("----------------------------------\n")
assert answer_text and len(answer_text.strip()) > 20, "Expected non-empty live answer from model"

# Verify Minor UI Build .17: answerDocumentLabel displays the genuine source document name
doc_label = find_item(root, "answerDocumentLabel")
assert doc_label is not None and doc_label.isVisible(), "answerDocumentLabel must be visible in answer view"
doc_label_text = doc_label.property("text")
print(f"answerDocumentLabel text: {doc_label_text!r}")
assert doc_label_text == "arxiv_2506.22716_original.pdf", f"Expected filename in answerDocumentLabel, got {doc_label_text!r}"

qa_telem = controller.snapshot.get("telemetry", {})
print(f"Telemetry: {qa_telem}")

# 5. Open cited source page and return back to Answer
answer_sources = controller.snapshot.get("answerSources") or []
print(f"Answer sources count: {len(answer_sources)}")
if answer_sources:
    first_src = answer_sources[0]
    target_page = first_src.get("page", 1)
    print(f"Opening cited source on page {target_page}")
    toggle_btn = find_item(root, "answerSourcesToggle")
    if toggle_btn and toggle_btn.isVisible():
        click_item(toggle_btn)
        QTest.qWait(100)
    
    open_src_btn = find_item(root, "openAnswerSource_0")
    if open_src_btn and open_src_btn.isVisible() and open_src_btn.property("enabled"):
        click_item(open_src_btn)
        wait_for_idle()
        assert controller.snapshot.get("view") == "page", f"Expected page view after opening source, got {controller.snapshot.get('view')}"
        assert controller.snapshot.get("canBackToAnswer") is True
        print(f"Successfully navigated to cited source page {controller.snapshot.get('pageNumber')}")
        
        # Return back to answer
        back_answer_btn = find_item(root, "backToAnswer")
        assert back_answer_btn is not None and back_answer_btn.isVisible(), "backToAnswer must be visible on page view"
        click_item(back_answer_btn)
        wait_for_idle()
        assert controller.snapshot.get("view") == "answer", "Expected return to answer view"
        assert controller.snapshot.get("answerText") == answer_text, "Answer text must remain intact"
        print("Successfully returned to Answer view via backToAnswer")

# 6. Compose new follow-up draft in composer and verify context preservation
followup_draft = "Phương pháp K-Means clustering hoạt động như thế nào?"
editor.forceActiveFocus()
editor.setProperty("text", followup_draft)
QTest.qWait(50)
assert editor.property("text") == followup_draft
assert controller.snapshot.get("view") == "answer", "Composer typing must not dismiss answer view"

# Test Min Mode
click_item(find_item(root, "liveFoldButton"))
assert not root.property("expanded"), "Workbench must be folded in min mode"
assert editor.property("text") == followup_draft, "Draft must be preserved in min mode"
notice_card = find_item(root, "notice")
assert notice_card is not None and notice_card.isVisible(), "notice card must be visible in min mode"

# Test Full Mode
click_item(notice_card)
assert root.property("expanded"), "Workbench must be expanded in full mode"
assert editor.property("text") == followup_draft, "Draft must be preserved in full mode"
assert controller.snapshot.get("view") == "answer", "Answer view must remain active after expanding"
assert controller.snapshot.get("answerText") == answer_text, "Answer text must remain preserved"
print("Follow-up draft and answer context perfectly preserved across min/full modes.")

# 7. Capture screenshots at 520px and 700px production dimensions
os.makedirs("work/turn5_evidence", exist_ok=True)
artifact_dir = Path("/Users/thundercock2/.gemini/antigravity/brain/c521fb94-cdbc-4b76-8354-89e731c844c7")

img_520_path = "work/turn5_evidence/turn5_live_conversation_520px.png"
view.grabWindow().save(img_520_path)
shutil.copy2(img_520_path, str(artifact_dir / "turn5_live_conversation_520px.png"))
print(f"Saved and copied to artifact: {img_520_path} (520px)")

view.resize(700, round(root.property("preferredWindowHeight")))
QTest.qWait(350)
img_700_path = "work/turn5_evidence/turn5_live_conversation_700px.png"
view.grabWindow().save(img_700_path)
shutil.copy2(img_700_path, str(artifact_dir / "turn5_live_conversation_700px.png"))
print(f"Saved and copied to artifact: {img_700_path} (700px)")

# Verify non-transparency
for p in [img_520_path, img_700_path]:
    im = Image.open(p)
    arr = np.array(im)
    assert arr.shape[0] > 100 and arr.shape[1] > 100, f"Image {p} too small"
    non_transparent = np.count_nonzero(arr[:, :, 3] > 10)
    ratio = non_transparent / (arr.shape[0] * arr.shape[1])
    print(f"Image {p}: size={im.size}, non-transparent ratio={ratio:.2%}")
    assert ratio > 0.40, f"Image {p} is too transparent: ratio={ratio:.2%}"

print("\n--- ALL BUILD 2026.10.25.17 LIVE CONVERSATION VERIFICATIONS PASSED SUCCESSFULLY ---")

timer.stop()
view.close()
controller.close()
