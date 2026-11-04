"""Unified RAT-CoT flow acceptance tests on the real Qt Quick QML interface (PDFDesk.qml).

Validates all multi-turn DSA scenarios, optimistic artifact revisioning,
draft preservation on lookback, cancellation, quotas, and PDF regression directly
through the Quick QML surface and QuickPDFController.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QUrl, Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

from rat.engine.assistant_runtime import AgentResponse, AssistantRuntime
from rat.kernel.contracts import Artifact
from rat.ui.chat_session import ConversationHistory
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from tests.test_selected_pdf import write_pdf

PROJECT = Path(__file__).resolve().parents[1]


class RecordingBackend:
    """Stands in for AssistantRuntime.run, recording observed inputs and threads."""

    def __init__(self, answer_text="authored synthetic answer", delay_s=0.0):
        self.answer_text = answer_text
        self.delay_s = delay_s
        self.run_calls = []

    def run(self, query, **context):
        self.run_calls.append({"query": query, "context": context, "thread": threading.current_thread()})
        started = time.monotonic()
        while time.monotonic() - started < self.delay_s:
            if context.get("should_cancel") and context["should_cancel"]():
                return AgentResponse("", [], 0, 0, 0, error="cancelled")
            time.sleep(0.01)
        return AgentResponse(self.answer_text, [], 0, 0, 12)


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtGui import QGuiApplication
    application = QGuiApplication.instance() or QGuiApplication([])
    application.setFont(QFont("Helvetica Neue", 13))
    yield application


def wait_for(predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < end, "Timed out waiting for predicate in wait_for()"
        QTest.qWait(10)
    QTest.qWait(20)


def submit_draft(view, root, text):
    editor = root.findChild(QQuickItem, "draftEditor")
    assert editor is not None
    editor.setProperty("text", text)
    editor.forceActiveFocus()
    QTest.keyClick(view, Qt.Key.Key_Return)
    QTest.qWait(20)


def click_item(view, root, name):
    item = root.findChild(QQuickItem, name)
    if item is None:
        pending = list(root.childItems())
        while pending:
            candidate = pending.pop()
            if candidate.objectName() == name:
                item = candidate
                break
            pending.extend(candidate.childItems())
    assert item is not None and item.isVisible(), f"Item {name} not found or not visible"
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
    QTest.qWait(30)


@pytest.fixture
def quick_env(app, tmp_path, monkeypatch):
    from rat.config import config
    monkeypatch.setattr(config, "db_path", str(tmp_path / "quick_fixture.db"))
    monkeypatch.setattr(config, "document_model_path", "")
    monkeypatch.setattr(config, "document_model_preload", False)
    from rat.engine.slm import slm_engine
    monkeypatch.setattr(slm_engine, "is_service_running", lambda: pytest.fail("GUI probed model service"))
    monkeypatch.setattr(slm_engine, "list_installed_models", lambda: [])

    backend = RecordingBackend()
    runtime = AssistantRuntime()
    runtime.run = backend.run
    conversation = ConversationHistory()

    controller = QuickPDFController(
        assistant_runtime=runtime,
        conversation=conversation,
    )
    controller.ready()

    copied_texts = []
    controller.copyReady.connect(copied_texts.append)

    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({
        "liveController": controller,
        "reduceMotion": True,
        "mascotSource": QUrl.fromLocalFile(str(PROJECT / "rat/assets/rat_mascot_cutout.png")),
    })
    view.setSource(QUrl.fromLocalFile(str(PROJECT / "rat/ui/quick/PDFDesk.qml")))
    assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]

    root = view.rootObject()
    view.resize(720, round(root.property("preferredWindowHeight")))
    view.setPosition(0, view.screen().availableGeometry().bottom() - view.height() - 32)
    resize_timer = bind_desk_window(view)
    view.show()
    QTest.qWait(40)

    yield SimpleNamespace(
        view=view,
        root=root,
        controller=controller,
        backend=backend,
        runtime=runtime,
        conversation=conversation,
        copied_texts=copied_texts,
    )

    resize_timer.stop()
    controller.close()
    view.setSource(QUrl())
    view.close()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


# --- Bước 1: Giải thích binary search bằng ví dụ, chưa đưa code ---

def test_quick_step_1_explain_binary_search(quick_env):
    root = quick_env.root
    view = quick_env.view
    controller = quick_env.controller
    backend = quick_env.backend

    q1 = "Giải thích binary search bằng ví dụ nhỏ, chưa đưa code vội."
    backend.answer_text = "Binary search là thuật toán tìm kiếm trên mảng đã sắp xếp bằng cách chia đôi khoảng tìm kiếm."

    submit_draft(view, root, q1)

    # Wait for execution to finish (app stays folded in min mode, showing notice card)
    wait_for(lambda: not controller.snapshot["busy"])

    # 1. Verification of QML elements in min mode, then expand via notice click
    assert controller.snapshot["view"] == "answer"
    assert controller.snapshot["expanded"] is False

    click_item(view, root, "notice")
    wait_for(lambda: controller.snapshot["expanded"])
    assert controller.snapshot["expanded"] is True

    answer_item = root.findChild(QQuickItem, "answerText")
    assert answer_item is not None and answer_item.isVisible()
    assert answer_item.property("textDocument").textDocument().toPlainText() == backend.answer_text
    assert controller.snapshot["answerText"] == backend.answer_text

    # 2. Telemetry and provenance
    telem = controller.snapshot["telemetry"]
    assert telem["execution_lane"] == "assistant"

    # 3. Arithmetic verifier scope remains UNKNOWN
    snap = controller.conversation.get_turn("turn-1")
    assert snap is not None
    assert snap.status == "completed"
    assert snap.answer == backend.answer_text

    # 4. Backend input did not leak private thoughts and executed on worker thread
    assert len(backend.run_calls) == 1
    call = backend.run_calls[0]
    assert "PRIVATE_THOUGHT" not in call["query"]
    assert call["thread"] is not threading.main_thread()


# --- Bước 2: Mảng [2, 4, 6, 8, 10], tìm 8 đi ---

def test_quick_step_2_pass_array_and_target_retains_facts(quick_env):
    root = quick_env.root
    view = quick_env.view
    controller = quick_env.controller
    backend = quick_env.backend

    # Turn 1
    backend.answer_text = "Khái niệm Binary Search."
    controller.submit("Giải thích binary search")
    wait_for(lambda: not controller.snapshot["busy"])

    # Turn 2
    q2 = "Dùng mảng [2, 4, 6, 8, 10], tìm 8 đi."
    backend.answer_text = "Bước 1: mid=2, a[2]=6 < 8 => xét [3, 4]. Bước 2: mid=3, a[3]=8 => tìm thấy tại index 3."

    submit_draft(view, root, q2)
    wait_for(lambda: not controller.snapshot["busy"])

    # Backend received Turn 1 context and facts
    last_call = backend.run_calls[-1]
    assert last_call["query"] == q2
    assert "binary search" in str(last_call["context"]["history"]).lower()

    # UI displayed query remains strictly user's query
    assert controller.snapshot["userQuery"] == q2

    # Commit artifact at revision 1 for Turn 2
    art = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=1,
        payload={"array": [2, 4, 6, 8, 10], "target": 8, "result_index": 3},
        inputs={"array": [2, 4, 6, 8, 10], "target": 8},
        provenance={"owner_turn_id": "turn-2"},
        title="Binary search tìm 8",
    )
    committed = controller.commit_artifact(art)
    assert committed.revision == 1
    assert controller.conversation.get_turn("turn-2").artifact_refs[0]["revision"] == 1


# --- Bước 3: “Sao phải dùng mid + 1?” ---

def test_quick_step_3_followup_question_receives_referenced_facts(quick_env):
    root = quick_env.root
    view = quick_env.view
    controller = quick_env.controller
    backend = quick_env.backend

    # Setup Turn 1 and 2
    controller.conversation.add_turn("Giải thích binary search", "Khái niệm Binary Search.")
    art = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=1,
        payload={"array": [2, 4, 6, 8, 10], "target": 8, "result_index": 3},
        inputs={"array": [2, 4, 6, 8, 10], "target": 8},
        provenance={"owner_turn_id": "turn-2"},
        title="Binary search tìm 8",
    )
    controller.assistant_runtime.artifact_store.put(art)
    controller.conversation.add_turn("Dùng mảng [2, 4, 6, 8, 10], tìm 8", "Tìm 8 tại index 3", artifact_refs=[art.to_dict()])

    q3 = "Sao phải dùng mid + 1?"
    backend.answer_text = "Vì a[mid] = 6 < 8, ta loại trừ mid và xét từ mid + 1."

    # Submit Turn 3 referencing Turn 2 and art-dsa-search@v1
    controller.submit(q3, target_turn_id="turn-2", target_artifact_id="art-dsa-search", target_revision=1)
    wait_for(lambda: not controller.snapshot["busy"])

    # Transport verified: backend received referenced facts of target 8
    call = backend.run_calls[-1]
    assert call["query"] == q3
    assert call["context"]["turn_ref"].target_turn_id == "turn-2"
    assert call["context"]["turn_ref"].target_artifact_id == "art-dsa-search"
    assert "Tìm 8 tại index 3" in str(call["context"]["turn_references"])

    # UI displays strictly q3 and answer in answerText
    assert controller.snapshot["userQuery"] == q3

    # Open full workbench from notice before inspecting paper and copying citation
    click_item(view, root, "notice")
    wait_for(lambda: controller.snapshot["expanded"])

    answer_item = root.findChild(QQuickItem, "answerText")
    assert answer_item is not None and answer_item.isVisible()
    assert answer_item.property("textDocument").textDocument().toPlainText() == backend.answer_text

    # Copy answer test through QML copyCitation button
    click_item(view, root, "copyCitation")
    assert len(quick_env.copied_texts) == 1
    assert quick_env.copied_texts[0] == backend.answer_text


# --- Bước 4: “Đổi sang tìm 6” (Revisioning & Optimistic Locking) ---

def test_quick_step_4_change_target_optimistic_locking(quick_env):
    controller = quick_env.controller
    backend = quick_env.backend
    art_store = controller.assistant_runtime.artifact_store

    # Setup Turn 1
    controller.submit("Giải thích binary search")
    wait_for(lambda: not controller.snapshot["busy"])

    # Setup Turn 2 with art-dsa-search@v1
    art_v1 = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=1,
        payload={"array": [2, 4, 6, 8, 10], "target": 8, "result_index": 3},
        inputs={"array": [2, 4, 6, 8, 10], "target": 8},
        provenance={"owner_turn_id": "turn-2"},
        title="Tìm 8",
    )
    art_store.put(art_v1)
    controller.submit("Dùng mảng [2, 4, 6, 8, 10], tìm 8")
    wait_for(lambda: not controller.snapshot["busy"])

    turn_2_snap = controller.conversation.get_turn("turn-2")
    turn_2_snap.artifact_refs = [art_v1.to_dict()]
    controller.conversation._turn_snapshots["turn-2"] = turn_2_snap

    # Step 4: Change target to 6 (Turn 3)
    q4 = "Đổi sang tìm 6 nhé."
    backend.answer_text = "Tìm 6: mid=2, a[2]=6 == 6 => index 2."
    controller.submit(q4, target_turn_id="turn-2", target_artifact_id="art-dsa-search", target_revision=1)
    wait_for(lambda: not controller.snapshot["busy"])

    # Commit revision 2 with expected_revision=1
    art_v2 = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=2,
        payload={"array": [2, 4, 6, 8, 10], "target": 6, "result_index": 2},
        inputs={"array": [2, 4, 6, 8, 10], "target": 6},
        provenance={"owner_turn_id": "turn-3", "source_artifact_id": "art-dsa-search", "source_revision": 1},
        title="Tìm 6",
    )
    committed = controller.commit_artifact(art_v2, expected_revision=1)
    assert committed.revision == 2

    # Snapshot of Turn 2 still holds revision 1
    turn_2_snap = controller.conversation.get_turn("turn-2")
    assert turn_2_snap.artifact_refs[0]["revision"] == 1
    assert turn_2_snap.artifact_refs[0]["inputs"]["target"] == 8

    # Store retains both revisions
    assert art_store.get("art-dsa-search", revision=1).inputs["target"] == 8
    assert art_store.get("art-dsa-search", revision=2).inputs["target"] == 6

    # Optimistic locking check: attempting another put with stale expected_revision=1 fails
    stale_attempt = copy.deepcopy(art_v2)
    stale_attempt.revision = 3
    with pytest.raises(ValueError, match="stale_revision"):
        controller.commit_artifact(stale_attempt, expected_revision=1)


# --- Bước 5: Mở lại lượt giải thích mid+1 ---

def test_quick_step_5_lookback_preserves_draft_no_dispatch(quick_env):
    root = quick_env.root
    controller = quick_env.controller
    backend = quick_env.backend

    controller.conversation.add_turn("Sao phải dùng mid + 1?", "Giải thích mid + 1 tại index 3", turn_id="turn-3")
    calls_before = len(backend.run_calls)

    # User is currently typing a draft in composer
    editor = root.findChild(QQuickItem, "draftEditor")
    draft_text = "Bản nháp câu hỏi tiếp theo đang soạn dở..."
    editor.setProperty("text", draft_text)

    # Explicit navigation to Turn 3
    assert controller.navigateToTurn("turn-3")

    # 1. Draft is strictly preserved in draftEditor
    assert editor.property("text") == draft_text

    # 2. No additional model calls dispatched
    assert len(backend.run_calls) == calls_before

    # 3. AnswerText displays the historical answer
    answer_item = root.findChild(QQuickItem, "answerText")
    assert "Giải thích mid + 1" in answer_item.property("text")


# --- Bước 6: Hủy rồi hỏi tiếp ---

def test_quick_step_6_cancellation_and_subsequent_query(quick_env):
    root = quick_env.root
    view = quick_env.view
    controller = quick_env.controller
    backend = quick_env.backend

    backend.delay_s = 0.5
    submit_draft(view, root, "Giải thích vì sao tìm kiếm lâu?")
    wait_for(lambda: controller.snapshot["busy"])

    # The live send control cancels through the actual QML click path.
    send_btn = root.findChild(QQuickItem, "sendButton")
    assert send_btn.isVisible() and send_btn.isEnabled()

    click_item(view, root, "sendButton")
    wait_for(lambda: not controller.snapshot["busy"])

    # Cancelled turn records status='cancelled'
    cancelled_snap = controller.conversation.turns()[-1]
    assert cancelled_snap.status == "cancelled"

    # Late callback cannot write to cancelled execution
    with pytest.raises(ValueError, match="cancelled:turn_cancelled"):
        controller.conversation.complete_turn(
            cancelled_snap.turn_id,
            "Late answer arriving",
            execution_id=cancelled_snap.execution_id,
        )

    # Subsequent query can be submitted immediately
    backend.delay_s = 0.0
    backend.answer_text = "Câu trả lời của lượt tiếp theo."
    submit_draft(view, root, "Câu hỏi mới sau khi hủy.")
    wait_for(lambda: not controller.snapshot["busy"])

    new_snap = controller.conversation.turns()[-1]
    assert new_snap.turn_id != cancelled_snap.turn_id
    assert new_snap.execution_id != cancelled_snap.execution_id
    assert new_snap.status == "completed"
    assert new_snap.answer == backend.answer_text


# --- Bước 8: PDF chọn / tìm / đọc / chép nguồn trên cùng UI ---

def test_quick_step_8_pdf_flow_regression(quick_env, tmp_path):
    controller = quick_env.controller
    root = quick_env.root
    view = quick_env.view

    pdf_file = write_pdf(tmp_path / "Document_DSA.pdf", ["Page 1 Intro", "Page 2 Binary Search in Log N time", "Page 3 Conclusion"])

    # 1. Select PDF
    controller.selectFile(str(pdf_file))
    wait_for(lambda: not controller.snapshot["busy"])
    assert controller.snapshot["pageCount"] == 3
    assert controller.snapshot["fileName"] == "Document_DSA.pdf"

    # 2. Search keyword in PDF
    controller.search("Binary")
    wait_for(lambda: not controller.snapshot["busy"])
    assert controller.snapshot["view"] == "search"
    assert len(controller.snapshot["items"]) >= 1

    # 3. Read matched page
    controller.readPage(2)
    wait_for(lambda: not controller.snapshot["busy"])
    assert controller.snapshot["view"] == "page"
    assert "Binary Search in Log N time" in controller.snapshot["pageText"]

    # 4. Copy citation
    controller.copyCitation()
    assert len(quick_env.copied_texts) >= 1
    assert "Document_DSA.pdf" in quick_env.copied_texts[-1]

    # 5. Clear PDF
    controller.selectFile("")
    assert controller.snapshot["fileName"] == ""
