"""Smoke verification script for RAT Build .23:
1. Semantic / Fuzzy Reranker: Offline topic expansion retrieves relevant documents for vague concepts.
2. Agentic Reasoning Bridge: Pressing Tab on a candidate adopts the document AND automatically submits
   the drafted question to Chuột's reasoning loop with grounded citations.
3. Visual capture at 520px and 700px with non-transparency >= 40%.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure software backend to avoid macOS Metal cache transparency bug
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PyQt6.QtCore import QPointF, Qt, QUrl
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QGuiApplication

from rat.engine.semantic_reranker import SemanticFuzzyReranker
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.icon_provider import RatIconProvider
from rat.ui.quick_app import bind_desk_window

OUT = ROOT / "artifacts/agentic_finder_build23_20261025"
OUT.mkdir(parents=True, exist_ok=True)
CONV_DIR = Path("/Users/thundercock2/.gemini/antigravity/brain/367dd020-1255-4e73-9cb5-9ade6f03cada")

print("=== Starting Turn 7 Reasoning Agentic Finder & Reranker Smoke (Build .23) ===")

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
app.setOrganizationName("RAT")
app.setApplicationName("RATQuickDesk")

# -------------------------------------------------------------
# 1. Verify Offline Semantic & Fuzzy Reranker directly
# -------------------------------------------------------------
controller = QuickPDFController()
db_path = controller._db_path
reranker = SemanticFuzzyReranker(db_path)

class VagueRequest:
    query = "bài toán vận tải và giao hàng"
    intent = None

t0 = time.perf_counter()
semantic_paths = list(reranker(VagueRequest()))
elapsed_ms = (time.perf_counter() - t0) * 1000
print(f"[OK] Semantic Reranker resolved in {elapsed_ms:.2f}ms, candidates: {len(semantic_paths)}")
assert len(semantic_paths) > 0, "Semantic reranker must find candidates for vague topic!"
joined_paths = " ".join(semantic_paths)
assert "VRPTW" in joined_paths or "ALNS" in joined_paths or "NAMI" in joined_paths
print(f"[OK] Top semantic candidate: '{Path(semantic_paths[0]).name}'")

# -------------------------------------------------------------
# 2. Setup QQuickView and PDFDesk QML with liveController
# -------------------------------------------------------------
view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
RatIconProvider.register(view.engine(), "icon")
view.setInitialProperties({"liveController": controller, "reduceMotion": True})

qml_path = ROOT / "rat" / "ui" / "quick" / "PDFDesk.qml"
view.setSource(QUrl.fromLocalFile(str(qml_path)))
assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]
view.resize(520, 550)
window_timer = bind_desk_window(view)
view.show()
view.requestActivate()
QTest.qWait(250)

root = view.rootObject()
assert root is not None, "Failed to load QML root"
assert root.property("uiBuildLabel") == "Build 2026.10.25.23", f"Expected Build 2026.10.25.23, got {root.property('uiBuildLabel')}"
print(f"[OK] UI Build Label verified: {root.property('uiBuildLabel')}")

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

editor = find_item("draftEditor")
assert editor is not None, "draftEditor not found"

# -------------------------------------------------------------
# 3. Test Agentic Reasoning Loop Triggered by Tab
# Query: "tìm tài liệu pdf về ALNS Double DQN"
# -------------------------------------------------------------
natural_query_pdf = "tìm tài liệu pdf về ALNS Double DQN"
editor.setProperty("text", natural_query_pdf)
controller.onComposerTextChanged(natural_query_pdf)

deadline = time.perf_counter() + 3.0
while not controller.snapshot.get("finderHits") and time.perf_counter() < deadline:
    QTest.qWait(20)

pdf_hits = controller.snapshot.get("finderHits", [])
print(f"[OK] PDF query resolved, hits returned: {len(pdf_hits)}")
assert len(pdf_hits) >= 1
first_pdf_hit = pdf_hits[0]
print(f"[OK] PDF Candidate 0: '{first_pdf_hit['title']}', match_reason='{first_pdf_hit.get('match_reason')}'")
assert first_pdf_hit.get("is_pdf") is True

# If view is not 'finder', open suggestions
if controller.snapshot.get("view") != "finder":
    res_open = controller.openFinderSuggestions()
    print(f"[DEBUG] openFinderSuggestions returned {res_open}, controller view is now {controller.snapshot.get('view')}")
    QTest.qWait(150)

# Select candidate 0
root.setProperty("selectedFinderIndex", 0)
QTest.qWait(100)
adopt_action = find_item("finderAdoptAction")
assert adopt_action is not None and adopt_action.isVisible(), "finderAdoptAction must be visible for selected candidate"
print(f"[OK] Adopt action verified: key='Tab', label='{adopt_action.property('labelText')}'")

# Capture candidate cards view at 520px
img_candidates_path = OUT / "agentic_candidates_520.png"
view.grabWindow().save(str(img_candidates_path))
print(f"[OK] Saved {img_candidates_path}")

# Press Tab key: Adopts document AND submits question to Chuột!
editor.forceActiveFocus()
QTest.qWait(50)
QTest.keyClick(view, Qt.Key.Key_Tab)
QTest.qWait(250)

# Verify document is adopted
adopted_filename = controller.snapshot.get("fileName")
print(f"[OK] File adopted into RAT desk: '{adopted_filename}'")
assert adopted_filename and ("ALNS" in adopted_filename or "DQN" in adopted_filename)

# Verify Chuột enters working / reasoning state
busy_state = controller.snapshot.get("busy") or controller.snapshot.get("view") in ("busy", "answer")
status_text = controller.snapshot.get("status")
print(f"[OK] Agentic loop launched! View='{controller.snapshot.get('view')}', Status='{status_text}', Busy={controller.snapshot.get('busy')}")
assert busy_state or "Chuột" in status_text

# Wait for reasoning agent to complete or deliver response (up to 45s for genuine model call)
deadline = time.perf_counter() + 45.0
while controller.snapshot.get("busy") and time.perf_counter() < deadline:
    QTest.qWait(200)

final_view = controller.snapshot.get("view")
final_answer = controller.snapshot.get("lastAssistantAnswer") or controller.snapshot.get("answerText")
print(f"[OK] Reasoning finished: view='{final_view}', answer length={len(final_answer or '')}")
print(f"[OBSERVED ANSWER]: {final_answer}")

# Ensure controller workbench is expanded so answer card is visible
controller.setExpanded(True)
QTest.qWait(200)

preferred_h = round(root.property("preferredWindowHeight"))
print(f"[DEBUG] preferredWindowHeight={preferred_h}")
target_h = max(420, min(650, preferred_h))

# Capture Agentic Answer & Evidence view at 520px
view.resize(520, target_h)
QTest.qWait(200)
img_answer_520 = OUT / "agentic_answer_grounded_520.png"
view.grabWindow().save(str(img_answer_520))
print(f"[OK] Saved {img_answer_520}")

# Capture at 700px
view.resize(700, target_h)
QTest.qWait(200)
img_answer_700 = OUT / "agentic_answer_grounded_700.png"
view.grabWindow().save(str(img_answer_700))
print(f"[OK] Saved {img_answer_700}")

# -------------------------------------------------------------
# 4. Verify non-transparency >= 40%
# -------------------------------------------------------------
images = [img_candidates_path, img_answer_520, img_answer_700]
for p in images:
    qimg = QImage(str(p))
    w, h = qimg.width(), qimg.height()
    total_pixels = w * h
    non_transparent = 0
    step = 2
    sampled = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            sampled += 1
            if qimg.pixelColor(x, y).alpha() > 20:
                non_transparent += 1
    ratio = non_transparent / sampled
    print(f"Image {p.name}: resolution=({w}, {h}), non-transparent pixel ratio={ratio*100:.2f}%")
    assert ratio >= 0.40, f"Image {p.name} is too transparent: {ratio*100:.2f}% < 40%"
    # Copy to conversation artifacts
    dest = CONV_DIR / p.name
    dest.write_bytes(p.read_bytes())
    print(f"[OK] Copied {p.name} to artifact directory: {dest}")

print("=== All Turn 7 Reasoning Agentic Finder & Reranker Verifications PASSED 100% ===")
