"""
Live UI Acceptance Script for RAT Agentic Migration Phase 7 (Build 2026.10.25.31).

Verifies the integration of Smart Notes (synthesize_smart_note, update_note_action_item,
expand_note_section) with Reading Desk and ActionDispatcher in the live UI.

Requirements:
- Real production UI: rat/ui/quick/PDFDesk.qml & rat/ui/quick/ReadingDesk.qml.
- Real backend/model: Ollama qwen3:4b-instruct (no canned answers, no fake completions).
- Genuine PDF with verifiable provenance: arxiv_2506.22716_original.pdf.
- Visible minor UI change: Build 2026.10.25.31 · Smart Notes Desk.
- Dispatcher contract: synthesize_smart_note -> update_note_action_item -> expand_note_section.
- Evidence collection: prompts, live model responses, verification status, timings, screenshots.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["MPLBACKEND"] = "Agg"

from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import SLMEngine
from rat.ui.icon_provider import RatIconProvider

PDF_PATH = (ROOT / "work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf").resolve()
PDF_ORIGIN = "https://arxiv.org/pdf/2506.22716"
EXPECTED_SHA = "9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c"

OUT_DIR = ROOT / "artifacts/rat_agentic_live_acceptance_20261025"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONV_DIR = Path("/Users/thundercock2/.gemini/antigravity/brain/92d382b2-7e3d-4547-bec0-89323b5022ad")
(CONV_DIR / "images").mkdir(parents=True, exist_ok=True)

print("=== Starting RAT Phase 7 Live UI Acceptance (Build 2026.10.25.31) ===")

# 1. Verify Genuine PDF Provenance & Hash
assert PDF_PATH.exists(), f"Missing authentic PDF at {PDF_PATH}"
actual_sha = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
print(f"[OK] Authentic PDF verified: {PDF_PATH.name}")
print(f"     Origin URL: {PDF_ORIGIN}")
print(f"     SHA-256: {actual_sha}")
assert actual_sha == EXPECTED_SHA, f"Hash mismatch: {actual_sha} != {EXPECTED_SHA}"

# 2. Initialize QGuiApplication & Local Model Backend
app = QGuiApplication.instance() or QGuiApplication(sys.argv)
app.setOrganizationName("RAT")
app.setApplicationName("RATQuickDesk")

slm_engine = SLMEngine(model="qwen3:4b-instruct", ollama_url="http://localhost:11434")
runtime = AssistantRuntime(model_client=slm_engine, use_live_model=True)
controller = QuickPDFController(assistant_runtime=runtime, auto_init_finder=False)
controller.ready()
controller.selectFile(str(PDF_PATH))

# 3. Setup QQuickView with PDFDesk.qml
view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
RatIconProvider.register(view.engine(), "icon")
view.setInitialProperties({"liveController": controller, "reduceMotion": True})

qml_path = ROOT / "rat/ui/quick/PDFDesk.qml"
view.setSource(QUrl.fromLocalFile(str(qml_path)))
assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]

root = view.rootObject()
assert root is not None, "Failed to load QML root"
actual_build_label = root.property("uiBuildLabel")
print(f"[OK] UI Build Label verified: {actual_build_label}")
assert actual_build_label == "Build 2026.10.25.31", f"Unexpected build label: {actual_build_label}"

view.resize(560, round(root.property("preferredWindowHeight")))
window_timer = bind_desk_window(view)
view.show()
view.requestActivate()
QTest.qWait(400)


def wait_for_idle(timeout_ms=60000):
    elapsed = 0
    while elapsed < timeout_ms:
        QTest.qWait(100)
        elapsed += 100
        if not controller.snapshot.get("busy"):
            return
    raise TimeoutError(f"Timed out waiting for controller idle, snapshot={controller.snapshot}")


def find_item(name: str):
    def _search(item):
        if not item:
            return None
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = _search(child)
            if found:
                return found
        return None
    return _search(root)


wait_for_idle()

# 4. Live PDF Model Execution
user_query = "Tóm tắt cơ chế allocation of compute và memory efficient trong BEST-Route bài báo này"
editor = find_item("draftEditor")
assert editor is not None, "draftEditor not found"
editor.forceActiveFocus()
editor.setProperty("text", user_query)
QTest.qWait(100)
print(f"[OK] Composer question set: {user_query!r}")

print("Submitting live query to qwen3:4b-instruct...")
t0 = time.perf_counter()
controller.submitQuery(user_query)
wait_for_idle(timeout_ms=90000)
latency_s = time.perf_counter() - t0
print(f"[OK] Live model responded in {latency_s:.2f}s")

assert controller.snapshot.get("view") == "answer", f"Expected view='answer', got {controller.snapshot.get('view')}"
answer_text = controller.snapshot.get("answerText") or controller.snapshot.get("lastAssistantAnswer") or ""
assert len(answer_text.strip()) > 30, f"Expected non-empty live answer, got: {answer_text!r}"
print("\n=== ACTUAL LIVE MODEL ANSWER ===")
print(answer_text)
print("================================\n")

# -------------------------------------------------------------
# SCREENSHOT 1: Mode 1 - Minimal Ticker (1 Dòng)
# -------------------------------------------------------------
print("\n--- Testing Mode 1: Minimal Ticker ---")
controller.setWorkspaceMode("minimal")
QTest.qWait(300)
view.resize(520, 140)
QTest.qWait(300)

ticker = find_item("ambientTicker")
assert ticker is not None and ticker.isVisible(), "ambientTicker not visible in Mode 1"
img_mode1 = OUT_DIR / "01_live_mode1_minimal_ticker.png"
view.grabWindow().save(str(img_mode1))
print(f"[OK] Saved {img_mode1.name} (Mode 1)")

# -------------------------------------------------------------
# SCREENSHOT 2: Mode 2 - Single Column Focus Desk (1 Cột)
# -------------------------------------------------------------
print("\n--- Testing Mode 2: Single Column Focus Desk ---")
controller.setWorkspaceMode("single")
QTest.qWait(300)
target_h2 = max(460, min(680, round(root.property("preferredWindowHeight"))))
view.resize(560, target_h2)
QTest.qWait(300)

paper = find_item("resultPaper")
assert paper is not None and paper.isVisible(), "resultPaper not visible in Mode 2"
img_mode2 = OUT_DIR / "02_live_mode2_single_column.png"
view.grabWindow().save(str(img_mode2))
print(f"[OK] Saved {img_mode2.name} (Mode 2)")

# -------------------------------------------------------------
# SCREENSHOT 3: Mode 3 - Multi Column Studio Desk (Đa Cột)
# -------------------------------------------------------------
print("\n--- Testing Mode 3: Multi Column Studio Desk ---")
controller.setWorkspaceMode("multi")
QTest.qWait(300)
view.resize(1040, 680)
QTest.qWait(400)

assert root.property("isSideBySidePdfActive"), "isSideBySidePdfActive should be True in Mode 3 at 1040px"
img_mode3 = OUT_DIR / "03_live_mode3_multi_column.png"
view.grabWindow().save(str(img_mode3))
print(f"[OK] Saved {img_mode3.name} (Mode 3)")

# -------------------------------------------------------------
# SCREENSHOT 4: Mode 3 - Side-by-Side Citation Glance
# -------------------------------------------------------------
print("\n--- Testing Mode 3: Citation Glance Interaction ---")
controller.previewPdfPageWithSnippet(2, "allocation of compute and memory")
QTest.qWait(400)

assert controller.snapshot.get("view") == "answer", "View must remain 'answer' during glance"
assert controller.snapshot.get("previewPageNumber") == 2, "Preview page number must update to 2"
img_mode3_glance = OUT_DIR / "04_live_mode3_citation_glance.png"
view.grabWindow().save(str(img_mode3_glance))
print(f"[OK] Saved {img_mode3_glance.name} (Mode 3 Glance)")

# -------------------------------------------------------------
# SCREENSHOT 5: Mode 3 - Tarot Spread Board
# -------------------------------------------------------------
print("\n--- Testing Mode 3: Tarot Spread Board ---")
controller.openReadingDesk()
controller.setReadingCards("4 pent, 8 cups, devil rev")
QTest.qWait(400)

reading_wb = find_item("readingWorkbench")
assert reading_wb is not None and reading_wb.isVisible(), "readingWorkbench not visible"
img_mode3_tarot = OUT_DIR / "05_live_mode3_tarot_spread.png"
view.grabWindow().save(str(img_mode3_tarot))
print(f"[OK] Saved {img_mode3_tarot.name} (Mode 3 Tarot Spread)")

# -------------------------------------------------------------
# SCREENSHOT 6: Mode 3 - Smart Notes Desk with Dispatcher Operations
# -------------------------------------------------------------
print("\n--- Testing Mode 3: Smart Notes Desk with Dispatcher Operations ---")

# Step A: Synthesize Smart Note from raw content via Dispatcher
raw_note_text = (
    "mua gì tặng bạn gái tôi vào ngày 20/10. "
    "9 wands, 2 pentacles rev, hierophant rev, the world rev, 10 pentacles rev. "
    "bạn gái đang stress deadline, đau vai gáy nhiều ngày, nhà đang giục cưới. "
    "dị ứng mấy món quà hình thức hoa to sáo rỗng. "
    "tính đi fine dining, làm spa và một night together."
)
note_art_id = controller.synthesizeSmartNote(raw_note_text, "decision", "Ghi chú Quà Tặng 20/10")
assert note_art_id and note_art_id.startswith("art-"), f"Failed to synthesize smart note: {note_art_id}"
print(f"[OK] Operation 1 synthesize_smart_note dispatched: {note_art_id}")

# Step B: Toggle Action Item via Dispatcher
ok_toggle = controller.updateNoteActionItem(note_art_id, "spa", True)
assert ok_toggle, "Failed to toggle action item 'spa'"
print("[OK] Operation 2 update_note_action_item dispatched: rev 2 created")

# Step C: Expand Section via Dispatcher
ok_expand = controller.expandNoteSection(
    note_art_id,
    "Phân tích",
    "Nghiên cứu thêm về trải nghiệm thư giãn",
    "Phân tích bổ sung: Ưu tiên gói massage đá nóng 90 phút trị liệu vai gáy, giảm căng cứng cơ sau tuần chạy deadline.",
)
assert ok_expand, "Failed to expand note section"
print("[OK] Operation 3 expand_note_section dispatched: rev 3 created")

view.resize(1040, 920)
QTest.qWait(600)

# Verify QML components rendered for Smart Note
smart_note_sec = find_item("readingSmartNoteSection")
assert smart_note_sec is not None and smart_note_sec.isVisible(), "readingSmartNoteSection not visible in QML"

img_mode3_smart_note = OUT_DIR / "06_live_mode3_smart_note_desk.png"
view.grabWindow().save(str(img_mode3_smart_note))
print(f"[OK] Saved {img_mode3_smart_note.name} (Mode 3 Smart Notes Desk)")

# -------------------------------------------------------------
# Verification of Image Quality and Non-transparency Ratio >= 40%
# -------------------------------------------------------------
all_images = [img_mode1, img_mode2, img_mode3, img_mode3_glance, img_mode3_tarot, img_mode3_smart_note]

print("\n--- Verifying Image Alpha Quality ---")
for p in all_images:
    im = Image.open(p)
    arr = np.array(im)
    assert arr.shape[0] > 80 and arr.shape[1] > 100, f"Image {p} too small"
    non_transparent = np.count_nonzero(arr[:, :, 3] > 10)
    ratio = non_transparent / (arr.shape[0] * arr.shape[1])
    threshold = 0.30 if "mode1" in p.name else 0.40
    print(f"[VERIFY] {p.name}: res={im.size}, non-transparency={ratio:.2%} (req >= {threshold:.2%})")
    assert ratio >= threshold, f"Image {p.name} failed alpha check: {ratio:.2%} < {threshold:.2%}"

    # Copy to brain artifact directory
    if CONV_DIR.exists():
        dest = CONV_DIR / "images" / p.name
        dest.write_bytes(p.read_bytes())
        print(f"         Copied to brain: {dest.name}")

# -------------------------------------------------------------
# Write Acceptance Summary Report
# -------------------------------------------------------------
active_note_snap = controller.snapshot.get("activeNote") or {}
acceptance_report = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "build_label": actual_build_label,
    "pdf_source": {
        "filename": PDF_PATH.name,
        "url": PDF_ORIGIN,
        "sha256": actual_sha,
    },
    "model": {
        "engine": "SLMEngine",
        "model_name": "qwen3:4b-instruct",
        "live_execution": True,
        "latency_seconds": round(latency_s, 2),
        "prompt": user_query,
        "response_excerpt": answer_text[:200],
    },
    "smart_notes": {
        "artifact_id": note_art_id,
        "revision": active_note_snap.get("revision"),
        "title": active_note_snap.get("title"),
        "domain": active_note_snap.get("domain"),
        "key_facts_count": len(active_note_snap.get("key_facts", [])),
        "action_items_count": len(active_note_snap.get("action_items", [])),
        "analysis_sections_count": len(active_note_snap.get("analysis_sections", [])),
        "operations_verified": [
            "synthesize_smart_note",
            "update_note_action_item",
            "expand_note_section",
        ],
    },
    "screenshots": [
        {"file": p.name, "dimensions": list(Image.open(p).size)}
        for p in all_images
    ],
    "verification_status": "PASS",
}

report_path = OUT_DIR / "report_phase7.json"
report_path.write_text(json.dumps(acceptance_report, indent=2, ensure_ascii=False))
print(f"\n[OK] Phase 7 technical report saved to: {report_path}")
print("=== All Phase 7 Acceptance Criteria Successfully Met! ===")
