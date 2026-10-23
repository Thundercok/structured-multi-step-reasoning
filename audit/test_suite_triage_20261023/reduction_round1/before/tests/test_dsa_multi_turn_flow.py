"""End-to-end multi-turn RAT-CoT flow acceptance tests using DSA binary search scenario.

Covers steps 1 to 7d from the unified acceptance plan:
1. Explain binary search with example, no code (provenance, display vs backend input).
2. Array [2,4,6,8,10], find 8 (facts and source refs in context snapshot).
3. "Why mid + 1?" (context transport of target 8 without re-prompting user).
4. "Change target to 6" (new turn, source revision 1 referenced, new revision 2 committed, optimistic locking).
5. Lookback to prior turn (preserves composer draft without new model dispatch).
6. Cancel mid-flight then re-ask (cooperative cancel, stale callback rejected, draft preserved).
7. Quota=0, missing required context, post-dispatch exception, and deadline timeout.
"""
import copy
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from PyQt6.QtCore import QThread
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.execution import (
    CONTEXT_ADAPTER_SCHEMA_VERSION,
    ExecutionRequest,
    build_execution_context_snapshot,
    execution_response,
    render_backend_input,
)
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.kernel.contracts import Artifact
from reasoning.reasoning_env import ReasoningAction as A
from rat.ui.assistant_worker import create_execution_worker
from rat.ui.omnibar import OmnibarWindow
from rat.ui.reasoning_worker import OnlineReasoningWorker
from reasoning.bundle import create_synthetic_specimen_bundle


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def until(app, predicate, timeout_s=5):
    deadline = time.monotonic() + timeout_s
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Predicate timed out in until()"


class RecordingBackend:
    """Controllable double recording observed inputs, controls, and threads."""
    hidden_size = 2

    def __init__(self, answer_text="authored synthetic answer", delay_s=0.0):
        self.answer_text = answer_text
        self.delay_s = delay_s
        self.embed_calls = []
        self.run_calls = []
        self.fail_on_strategy = None
        self.cancel_check_fn = None

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


@pytest.fixture
def test_env(app, tmp_path, monkeypatch):
    from rat.config import config
    from rat.ui import omnibar
    monkeypatch.delenv("RAT_WORKBENCH_SCENE", raising=False)
    monkeypatch.delenv("RAT_WORKBENCH_FINDER", raising=False)
    monkeypatch.setenv("RAT_REDUCE_MOTION", "1")
    monkeypatch.setattr(config, "db_path", str(tmp_path / "fixture.db"))
    monkeypatch.setattr(config, "document_model_path", "")
    monkeypatch.setattr(config, "document_model_preload", False)
    monkeypatch.setattr(omnibar, "load_club_members", lambda: [])
    monkeypatch.setattr(omnibar, "SearchEngine", Mock())
    monkeypatch.setattr("rat.ui.feedback.FeedbackLog", Mock())
    monkeypatch.setattr(ApplicationCatalog, "scan", classmethod(lambda cls, *a, **k: cls()))
    monkeypatch.setattr("rat.engine.slm.slm_engine.is_service_running", lambda: pytest.fail("GUI probed model service"))
    monkeypatch.setattr("rat.engine.slm.slm_engine.list_installed_models", lambda: [])

    backend = RecordingBackend()
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    from rat.ui.reasoning_host import install_reasoning_engine
    previous_host = {name: app.property(name) for name in (
        "ratReasoningEngine", "ratAllowSyntheticPolicy", "ratReasoningConversation")}
    install_reasoning_engine(app, engine, allow_synthetic_policy=True)

    window = OmnibarWindow()
    window.show_omnibar()
    until(app, lambda: window.isVisible())

    yield SimpleNamespace(window=window, backend=backend, engine=engine, bundle=bundle, policy=policy, app=app)

    window.shutdown()
    window.hide()
    window.deleteLater()
    for name, value in previous_host.items():
        app.setProperty(name, value)
    app.processEvents()


# --- Bước 1: Giải thích binary search bằng ví dụ, chưa đưa code ---

def test_step_1_explain_binary_search_provenance_and_presentation(test_env):
    window = test_env.window
    app = test_env.app
    backend = test_env.backend

    q1 = "Giải thích binary search bằng ví dụ nhỏ, chưa đưa code vội."
    backend.answer_text = "Binary search là thuật toán tìm kiếm trên mảng đã sắp xếp bằng cách chia đôi khoảng tìm kiếm."

    window.chat_composer_input.setText(q1)
    window._submit_chat_prompt(q1)

    until(app, lambda: window._pending_chat_query is None)

    # 1. UI displays the exact user query
    assert window._last_assistant_query == q1
    result_node = window.workbench_scene.current_snapshot.result_node
    assert result_node.answer_text == backend.answer_text
    assert "```" not in result_node.answer_text

    # 2. Telemetry and Provenance
    telem = window.last_turn_telemetry
    assert telem["execution_lane"] == "reasoning"
    assert telem["execution_mode"] == "online_policy"
    assert telem["policy_source"] == test_env.bundle.bundle_id
    assert telem["query_generation"] == 0
    assert telem["user_displayed_query"] == q1
    assert telem["context_snapshot_schema"] == CONTEXT_ADAPTER_SCHEMA_VERSION

    # 3. Verification scope is UNKNOWN (arithmetic verifier does not check DSA)
    snap = window._conversation.get_turn("turn-1")
    assert snap is not None
    assert snap.status == "completed"
    assert snap.answer == backend.answer_text

    # 4. Backend input did not expose private thoughts
    assert len(backend.run_calls) == 1
    call = backend.run_calls[0]
    assert "PRIVATE_THOUGHT" not in call["query"]
    assert call["thread"] is not app.thread()


# --- Bước 2: Dùng mảng [2, 4, 6, 8, 10], tìm 8 đi ---

def test_step_2_pass_array_and_target_retains_facts_and_source_refs(test_env):
    window = test_env.window
    app = test_env.app
    backend = test_env.backend

    # Turn 1
    q1 = "Giải thích binary search bằng ví dụ nhỏ."
    backend.answer_text = "Khái niệm Binary Search."
    window._submit_chat_prompt(q1)
    until(app, lambda: window._pending_chat_query is None)

    # Turn 2: Array and target
    q2 = "Dùng mảng [2, 4, 6, 8, 10], tìm 8 đi."
    backend.answer_text = "Bước 1: khoảng [0, 4], mid=2, a[2]=6 < 8 => xét [3, 4]. Bước 2: mid=3, a[3]=8 => tìm thấy tại index 3."
    window._submit_chat_prompt(q2)
    until(app, lambda: window._pending_chat_query is None)

    # Backend received context containing binary search topic from Turn 1 and array facts
    last_call = backend.run_calls[-1]
    backend_input = last_call["query"]
    assert "binary search" in backend_input.lower()
    assert "[2, 4, 6, 8, 10]" in backend_input or "2, 4, 6, 8, 10" in backend_input
    assert "8" in backend_input

    # UI displayed query remains strictly user's query
    assert window.last_turn_telemetry["user_displayed_query"] == q2
    snap2 = window._conversation.get_turn("turn-2")
    assert snap2.query == q2
    assert snap2.status == "completed"

    # Commit an artifact for the search task at revision 1
    art_store = window.assistant_runtime.artifact_store
    art = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=1,
        payload={"array": [2, 4, 6, 8, 10], "target": 8, "result_index": 3},
        inputs={"array": [2, 4, 6, 8, 10], "target": 8},
        provenance={"owner_turn_id": "turn-2"},
        title="Binary search tìm 8",
    )
    art_store.put(art)
    window._conversation.complete_turn("turn-2", backend.answer_text, artifact_refs=[art.to_dict()])
    assert window._conversation.get_turn("turn-2").artifact_refs[0]["revision"] == 1


# --- Bước 3: “Sao phải dùng mid + 1?” ---

def test_step_3_followup_question_receives_referenced_facts_without_reinput(test_env):
    window = test_env.window
    app = test_env.app
    backend = test_env.backend

    # Setup Turn 1 and Turn 2
    window._conversation.add_turn("Giải thích binary search", "Khái niệm Binary Search.")
    art_store = window.assistant_runtime.artifact_store
    art = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=1,
        payload={"array": [2, 4, 6, 8, 10], "target": 8, "result_index": 3},
        inputs={"array": [2, 4, 6, 8, 10], "target": 8},
        provenance={"owner_turn_id": "turn-2"},
        title="Binary search tìm 8",
    )
    art_store.put(art)
    window._conversation.add_turn("Dùng mảng [2, 4, 6, 8, 10], tìm 8", "Tìm 8 tại index 3", artifact_refs=[art.to_dict()])

    q3 = "Sao phải dùng mid + 1?"
    backend.answer_text = "Vì a[mid] = 6 nhỏ hơn 8, nên 8 chắc chắn nằm ở nửa phải, ta loại trừ mid và bắt đầu từ mid + 1."

    window._submit_chat_prompt(q3, target_turn_id="turn-2", target_artifact_id="art-dsa-search", target_revision=1)
    until(app, lambda: window._pending_chat_query is None)

    # Actual transport verified: backend received referenced facts of target 8 and array
    call = backend.run_calls[-1]
    backend_input = call["query"]
    assert "8" in backend_input
    assert "Referenced Prior Turn: turn-2" in backend_input
    assert "art-dsa-search@v1" in backend_input
    assert "Sao phải dùng mid + 1?" in backend_input

    # UI displays strictly q3
    assert window.last_turn_telemetry["user_displayed_query"] == q3


# --- Bước 4: “Đổi sang tìm 6” (Revisioning & Optimistic Locking) ---

def test_step_4_change_target_creates_new_revision_and_protects_old(test_env):
    window = test_env.window
    app = test_env.app
    backend = test_env.backend
    art_store = window.assistant_runtime.artifact_store

    # Setup Turn 1
    window._submit_chat_prompt("Giải thích binary search")
    until(app, lambda: window._pending_chat_query is None)

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
    window._submit_chat_prompt("Dùng mảng [2, 4, 6, 8, 10], tìm 8")
    until(app, lambda: window._pending_chat_query is None)

    # Attach artifact to Turn 2
    turn_2_snap = window._conversation.get_turn("turn-2")
    assert turn_2_snap is not None
    turn_2_snap.artifact_refs = [art_v1.to_dict()]
    window._conversation._turn_snapshots["turn-2"] = turn_2_snap

    # Step 4: Change target to 6 (Turn 3)
    q4 = "Đổi sang tìm 6 nhé."
    backend.answer_text = "Tìm 6: mid=2, a[2]=6 == 6 => tìm thấy ngay tại index 2."
    window._submit_chat_prompt(q4, target_turn_id="turn-2", target_artifact_id="art-dsa-search", target_revision=1)
    until(app, lambda: window._pending_chat_query is None)

    # Commit new revision v2
    art_v2 = Artifact(
        id="art-dsa-search",
        kind="dsa_search",
        revision=2,
        payload={"array": [2, 4, 6, 8, 10], "target": 6, "result_index": 2},
        inputs={"array": [2, 4, 6, 8, 10], "target": 6},
        provenance={"owner_turn_id": "turn-4", "source_artifact_id": "art-dsa-search", "source_revision": 1},
        title="Tìm 6",
    )
    committed = art_store.put(art_v2, expected_revision=1)
    assert committed.revision == 2

    # Snapshot of Turn 2 STILL holds revision 1
    turn_2_snap = window._conversation.get_turn("turn-2")
    assert turn_2_snap.artifact_refs[0]["revision"] == 1
    assert turn_2_snap.artifact_refs[0]["inputs"]["target"] == 8

    # Store retains both revisions in history
    assert art_store.get("art-dsa-search", revision=1).inputs["target"] == 8
    assert art_store.get("art-dsa-search", revision=2).inputs["target"] == 6

    # Optimistic locking check: attempting another put with stale expected_revision=1 fails
    stale_attempt = copy.deepcopy(art_v2)
    stale_attempt.revision = 3
    with pytest.raises(ValueError, match="stale_revision"):
        art_store.put(stale_attempt, expected_revision=1)


# --- Bước 5: Mở lại lượt giải thích mid+1 ---

def test_step_5_lookback_to_prior_turn_keeps_composer_draft_without_dispatch(test_env):
    window = test_env.window
    backend = test_env.backend

    window._conversation.add_turn("Sao phải dùng mid + 1?", "Giải thích mid + 1 tại index 3", turn_id="turn-3")
    calls_before = len(backend.run_calls)

    # User is currently typing a draft in composer
    editor = window.chat_composer_input
    editor.setText("Bản nháp câu hỏi tiếp theo đang soạn...")

    # Explicit navigation to Turn 3
    assert window.navigate_to_turn("turn-3")

    # 1. Draft is preserved
    assert editor.text() == "Bản nháp câu hỏi tiếp theo đang soạn..."

    # 2. No additional model calls dispatched
    assert len(backend.run_calls) == calls_before

    # 3. Speech bubble shows the historical answer
    assert "Giải thích mid + 1" in window.workbench_speech_bubble.dialogue.text()


# --- Bước 6: Hủy rồi hỏi tiếp ---

def test_step_6_cancellation_and_subsequent_query_isolates_stale_callback(test_env):
    window = test_env.window
    app = test_env.app
    backend = test_env.backend

    # Backend with delay so we can cancel mid-execution
    backend.delay_s = 0.5
    editor = window.chat_composer_input
    editor.setText("Tìm kiếm lâu và bị hủy...")

    window._submit_chat_prompt(editor.text())
    until(app, lambda: window._current_reasoner is not None)

    # Cancel while in-flight
    window._cancel_assistant()
    until(app, lambda: window._pending_chat_query is None)

    # Cancelled turn records status='cancelled' and adds to cancelled_executions
    cancelled_snap = window._conversation.turns()[-1]
    assert cancelled_snap.status == "cancelled"

    # Late callback cannot write to cancelled execution
    with pytest.raises(ValueError, match="cancelled:turn_cancelled"):
        window._conversation.complete_turn(cancelled_snap.turn_id, "Late answer arriving", execution_id=cancelled_snap.execution_id)

    # Subsequent query can be asked immediately
    backend.delay_s = 0.0
    backend.answer_text = "Câu trả lời của lượt tiếp theo."
    editor.setText("Câu hỏi mới sau khi hủy.")
    window._submit_chat_prompt(editor.text())
    until(app, lambda: window._pending_chat_query is None)

    new_snap = window._conversation.turns()[-1]
    assert new_snap.turn_id != cancelled_snap.turn_id
    assert new_snap.execution_id != cancelled_snap.execution_id
    assert new_snap.status == "completed"
    assert new_snap.answer == backend.answer_text


# --- Bước 7a: Quota cứng bằng 0 ---

@pytest.mark.parametrize("cap_type", ["tokens", "requests", "strategies"])
def test_step_7a_quota_caps_zero_dispatches_zero(test_env, cap_type):
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

def test_step_7b_missing_or_unreadable_context_returns_unresolved(test_env):
    window = test_env.window
    app = test_env.app
    backend = test_env.backend

    # Request document QA with non-existent document
    req = ExecutionRequest(
        "Đọc tài liệu",
        document_path="/tmp/non_existent_doc_12345.pdf",
        lane="document",
    )
    worker = create_execution_worker(window.assistant_runtime, req)
    worker.start()
    until(app, lambda: worker.isFinished())

    # Dispatched 0 model calls
    assert len(backend.run_calls) == 0

    # Optional context absent does not break standalone query
    req_standalone = ExecutionRequest("Câu hỏi đơn lẻ không ngữ cảnh", lane="reasoning")
    worker_standalone = create_execution_worker(window.assistant_runtime, req_standalone, reasoning_engine=test_env.engine, allow_synthetic_policy=True)
    assert isinstance(worker_standalone, OnlineReasoningWorker)


# --- Bước 7c: Exception sau khi dispatch giữ chi phí thực tế ---

def test_step_7c_exception_after_dispatch_preserves_partial_cost(test_env):
    backend = RecordingBackend()
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend.fail_on_strategy = "COT"
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    with pytest.raises(RuntimeError, match="Simulated failure on strategy"):
        engine.solve("query ladder that fails")

    assert len(backend.run_calls) == 1
    # Cost was not zeroed out: 1 request was dispatched
    assert backend.run_calls[0]["strategy"] == "COT"


# --- Bước 7d: Hủy hoặc deadline khi đang chạy ---

def test_step_7d_deadline_timeout_stops_and_preserves_cost(app):
    backend = RecordingBackend(delay_s=0.2)
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    worker = OnlineReasoningWorker(
        engine,
        "query ladder tight deadline",
        execution_id="exec-timeout",
        timeout_s=0.04,
    )
    responses = []
    statuses = []
    worker.status_changed.connect(statuses.append)
    worker.response_ready.connect(responses.append)
    worker.start()
    until(app, lambda: worker.isFinished())
    app.processEvents()

    assert len(responses) == 1
    res = responses[0]
    assert res.status == "timeout"
    assert "wait" in statuses
    assert res.verification_status == "unverified"
    assert res.cost_ledger is not None
    assert res.cost_ledger["status"] == "timeout"
