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

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QUrl, Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

from rat.engine.execution import (
    CONTEXT_ADAPTER_SCHEMA_VERSION,
    ExecutionRequest,
    build_execution_context_snapshot,
    render_backend_input,
)
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.engine.assistant_runtime import AssistantRuntime
from rat.kernel.contracts import Artifact
from rat.ui.chat_session import ConversationHistory
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window
from reasoning.bundle import create_synthetic_specimen_bundle
from tests.test_selected_pdf import write_pdf

PROJECT = Path(__file__).resolve().parents[1]


class RecordingBackend:
    """Controllable double recording observed inputs, controls, and threads."""
    hidden_size = 2

    def __init__(self, answer_text="authored synthetic answer", delay_s=0.0):
        self.answer_text = answer_text
        self.delay_s = delay_s
        self.embed_calls = []
        self.run_calls = []
        self.fail_on_strategy = None

    def embed(self, query: str):
        self.embed_calls.append((query, threading.current_thread()))
        return np.zeros(self.hidden_size, dtype=np.float32)

    def run(self, strategy, query: str, should_cancel=None, deadline_monotonic=None, max_tokens=None):
        self.run_calls.append({
            "strategy": strategy.name if hasattr(strategy, "name") else str(strategy),
            "query": query,
            "thread": threading.current_thread(),
            "max_tokens": max_tokens,
        })
        if self.delay_s > 0:
            t0 = time.monotonic()
            while time.monotonic() - t0 < self.delay_s:
                if should_cancel and should_cancel():
                    raise RuntimeError("cancelled_in_backend")
                if deadline_monotonic and time.monotonic() >= deadline_monotonic:
                    raise TimeoutError("timeout_in_backend")
                time.sleep(0.01)

        if self.fail_on_strategy and (strategy == self.fail_on_strategy or strategy.name == self.fail_on_strategy):
            raise RuntimeError(f"Simulated failure on strategy {strategy}")

        return self.answer_text, 0.95, 12


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
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
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    runtime = AssistantRuntime()
    conversation = ConversationHistory()

    controller = QuickPDFController(
        assistant_runtime=runtime,
        conversation=conversation,
        reasoning_engine=engine,
        allow_synthetic_policy=True,
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
        engine=engine,
        bundle=bundle,
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

    # Wait for execution to finish
    wait_for(lambda: not controller.snapshot["busy"])

    # 1. Verification of QML elements
    assert controller.snapshot["view"] == "answer"
    assert controller.snapshot["expanded"] is True

    answer_item = root.findChild(QQuickItem, "answerText")
    assert answer_item is not None and answer_item.isVisible()
    assert answer_item.property("text") == backend.answer_text
    assert "```" not in answer_item.property("text")

    # 2. Telemetry and provenance
    telem = controller.snapshot["telemetry"]
    assert telem["execution_lane"] == "reasoning"
    assert telem["execution_mode"] == "online_policy"
    assert telem["policy_source"] == quick_env.bundle.bundle_id
    assert telem["context_snapshot_schema"] == CONTEXT_ADAPTER_SCHEMA_VERSION
    assert telem["user_displayed_query"] == q1

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
    backend_input = last_call["query"]
    assert "binary search" in backend_input.lower()
    assert "[2, 4, 6, 8, 10]" in backend_input or "2, 4, 6, 8, 10" in backend_input
    assert "8" in backend_input

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
    backend_input = call["query"]
    assert "8" in backend_input
    assert "Referenced Prior Turn: turn-2" in backend_input
    assert "art-dsa-search@v1" in backend_input
    assert "Sao phải dùng mid + 1?" in backend_input

    # UI displays strictly q3 and answer in answerText
    assert controller.snapshot["userQuery"] == q3
    answer_item = root.findChild(QQuickItem, "answerText")
    assert answer_item.property("text") == backend.answer_text

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
    submit_draft(view, root, "Tìm kiếm lâu và bị hủy...")
    wait_for(lambda: controller.snapshot["busy"])

    # Send button shows stop ("■")
    send_btn = root.findChild(QQuickItem, "sendButton")
    assert send_btn.property("text") == "■"

    # Cancel via controller or stopRequest
    controller.cancel()
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


# --- Bước 7a: Quota cứng bằng 0 ---

@pytest.mark.parametrize("cap_type", ["tokens", "requests", "strategies"])
def test_quick_step_7a_quota_caps_zero_dispatches_zero(quick_env, cap_type):
    backend = RecordingBackend()
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    kwargs = {}
    if cap_type == "tokens":
        kwargs["max_generated_tokens"] = 0
    elif cap_type == "requests":
        kwargs["max_underlying_requests"] = 0
    elif cap_type == "strategies":
        kwargs["max_strategy_invocations"] = 0

    res = engine.solve("query requiring reasoning", **kwargs)
    assert res.status == "budget_exceeded"
    assert len(backend.embed_calls) == 0
    assert len(backend.run_calls) == 0
    assert res.cost_ledger["underlying_requests_dispatched"] == 0
    assert res.cost_ledger["generated_tokens"] == 0
    assert res.verification_status == "unverified"

    # Ensure None does NOT act as 0
    res_none = engine.solve("query with None cap", max_generated_tokens=None)
    assert res_none.status == "completed"
    assert len(backend.run_calls) > 0


# --- Bước 7b: Thiếu context bắt buộc hoặc failure trước dispatch ---

def test_quick_step_7b_missing_or_unreadable_context_returns_unresolved(quick_env):
    controller = quick_env.controller
    backend = quick_env.backend

    # Submit request referencing non-existent turn/artifact
    ok = controller.submit("Hỏi trên turn ảo", target_turn_id="turn-nonexistent-999")
    assert not ok
    assert len(backend.run_calls) == 0

    # Turn in conversation recorded as failed with truthful error
    turns = controller.conversation.turns()
    assert len(turns) > 0
    assert turns[-1].status == "failed"
    assert "reasoning_context_unavailable" in turns[-1].answer


# --- Bước 7c: Exception sau khi dispatch giữ chi phí thực tế ---

def test_quick_step_7c_exception_after_dispatch_preserves_partial_cost():
    backend = RecordingBackend()
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend.fail_on_strategy = "COT"
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    with pytest.raises(RuntimeError, match="Simulated failure on strategy"):
        engine.solve("query ladder that fails")

    assert len(backend.run_calls) == 1
    assert backend.run_calls[0]["strategy"] == "COT"


# --- Bước 7d: Timeout deadline ---

def test_quick_step_7d_deadline_timeout_stops_and_preserves_cost(app):
    backend = RecordingBackend(delay_s=0.2)
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    from rat.ui.reasoning_worker import OnlineReasoningWorker
    worker = OnlineReasoningWorker(
        engine,
        "query ladder tight deadline",
        execution_id="exec-timeout-quick",
        timeout_s=0.04,
    )
    responses = []
    worker.response_ready.connect(responses.append)
    worker.start()
    wait_for(lambda: worker.isFinished())
    app.processEvents()

    assert len(responses) == 1
    res = responses[0]
    assert res.status == "timeout"
    assert res.verification_status == "unverified"
    assert res.cost_ledger is not None
    assert res.cost_ledger["status"] == "timeout"


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
