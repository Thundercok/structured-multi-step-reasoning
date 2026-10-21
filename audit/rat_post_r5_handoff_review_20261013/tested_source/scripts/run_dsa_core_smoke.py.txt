"""Reproducible headless smoke runner for the RAT shared conversation core (DSA 6-turn + follow-up flow).

Addresses Codex review items:
- R5 fix: collects `history.messages_with_turn_ids()` and `history.turn_references()` BEFORE `history.begin_turn(q)`
  without slicing `[:-1]`, preserving the previous assistant reply in model context.
- Execution identity: passes `execution_id=snap.execution_id` and `conversation_id=history.conversation_id` to `runtime.run(...)`.
- Provenance: records SHA-256 hashes of core files, runtime config (`plan_tasks`, `max_steps`, `model`, `timeout`),
  and full raw model requests/responses per call.
- Honest token accounting: records `null` (`None`) for token counts when a model call times out or errors without
  returning Ollama eval counts, never conflating timeout with 0 tokens.
- Turn 6 requests cancellation while a local HTTP call is waiting, then checks late writes.
  The probe uses a short timeout; it does not verify native interruption or backend cancellation.
- Honest content/action evaluation: separates core lifecycle/context contract checks from live SLM tool-use and
  algorithmic accuracy checks (specifically checking whether Turn 4 stops at `mid=2` where `a[2]=6`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rat.config import config
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import SLMEngine
from rat.timetable.compositor import TimetableCompositor
from rat.ui.chat_session import ConversationHistory


TRACKED_SOURCE_FILES = [
    "rat/engine/work_notes.py",
    "rat/ui/chat_session.py",
    "rat/engine/assistant_runtime.py",
    "rat/kernel/dispatcher.py",
    "rat/kernel/contracts.py",
    "rat/ui/omnibar.py",
    "tests/test_work_context.py",
    "tests/test_rat_conversation_lifecycle.py",
    "scripts/run_dsa_core_smoke.py",
    "rat/engine/slm.py",
    "rat/engine/persona.py",
    "rat/engine/task_state.py",
    "rat/engine/verification.py",
    "rat/kernel/registry.py",
    "rat/kernel/capabilities/__init__.py",
    "rat/config.py",
]

SCENARIOS = {
    "dsa": [
        ("turn_1_explain", "Giải thích binary search bằng ví dụ nhỏ"),
        ("turn_2_trace_8", "Dùng mảng [2, 4, 6, 8, 10], tìm 8 từng bước"),
        ("turn_3_followup_mid_plus_1", "Vì sao bước đó dùng mid + 1 mà không giữ mid?"),
        ("turn_4_change_target_6", "Đổi thành tìm 6 thì các bước đổi thế nào?"),
        ("turn_5_lookback_summary", "Quay lại câu hỏi mid + 1 ở ví dụ trước, viết gọn thành 3 ý để tôi chép bài"),
        ("turn_6_in_flight_cancel", "Viết bảng trace đầy đủ cho mọi trường hợp"),
        ("turn_7_post_cancel_followup", "Tiếp tục với tìm 6 ở trên, chỉ số kết quả là mấy?"),
    ],
    # Development evaluation inputs only; the app has no scenario/keyword policy.
    "calculation": [
        ("turn_1_calculate", "Tính 18 * 7"),
        ("turn_2_record", "Ghi lại kết quả này."),
        ("turn_3_change_and_record", "Thay 7 bằng 9 và sửa ghi chú đó."),
        ("turn_4_compare", "Chênh với kết quả trước bao nhiêu?"),
        ("turn_5_lookback", "Kết quả đầu tiên là bao nhiêu? Giữ ghi chú hiện tại."),
        ("turn_6_in_flight_cancel", "Tính gấp đôi kết quả hiện tại rồi ghi lại."),
        ("turn_7_resume_and_record", "Tiếp tục việc bị dừng, ghi lại kết quả gấp đôi."),
    ],
}


def compute_source_hashes(repo_root: Path) -> Dict[str, Optional[str]]:
    hashes: Dict[str, Optional[str]] = {}
    for rel_path in TRACKED_SOURCE_FILES:
        p = repo_root / rel_path
        if p.exists() and p.is_file():
            hashes[rel_path] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            hashes[rel_path] = None
    return hashes


class InstrumentedSLMEngine(SLMEngine):
    """Capture HTTP observations and cancellation flags without claiming server abort."""

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        default_timeout: float = 90.0,
    ) -> None:
        super().__init__(ollama_url=ollama_url, model=model)
        self.default_timeout = default_timeout
        self.call_Records: List[Dict[str, Any]] = []
        self.record_path: Optional[Path] = None
        self._in_flight_cancel_config: Optional[Dict[str, Any]] = None

    def _record_call(self, record):
        self.call_Records.append(record)
        if self.record_path is not None:
            try:
                with self.record_path.open('a', encoding='utf-8') as journal:
                    journal.write(json.dumps(record, ensure_ascii=False) + '\n')
                    journal.flush()
            except OSError as exc:
                record['journal_error'] = str(exc)

    def arm_in_flight_cancel(
        self,
        cancel_event: threading.Event,
        delay_ms: float = 250.0,
        request_timeout_s: float = 0.6,
    ) -> Dict[str, Any]:
        state = {
            "armed": True,
            "was_cancelled_before_start": cancel_event.is_set(),
            "request_attempted": False,
            "request_active": False,
            "cancel_requested_while_waiting": False,
            "server_received_request": None,
            "transport_abort_verified": False,
            "server_cancellation_verified": False,
            "timeout_override_s": request_timeout_s,
            "delay_ms": delay_ms,
            "request_started_perf": None,
            "cancel_triggered_perf": None,
            "elapsed_before_cancel_ms": None,
        }
        self._in_flight_cancel_config = {
            "event": cancel_event,
            "delay_ms": delay_ms,
            "request_timeout_s": request_timeout_s,
            "state": state,
        }
        return state

    def disarm_in_flight_cancel(self) -> None:
        self._in_flight_cancel_config = None

    def chat_with_meta(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        timeout: float = 90.0,
        max_tokens: int = 640,
        thinking: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        effective_timeout = self.default_timeout if timeout == 90.0 else timeout
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": thinking,
            "options": {"temperature": 0.1, "num_predict": max_tokens, "num_ctx": 8192},
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["format"] = response_format

        req = urllib.request.Request(
            self.ollama_url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        cancel_cfg = self._in_flight_cancel_config
        timer: Optional[threading.Timer] = None
        tick = time.perf_counter()

        if cancel_cfg is not None and cancel_cfg["state"]["armed"]:
            state = cancel_cfg["state"]
            state["request_attempted"] = True
            state["request_active"] = True
            state["request_started_perf"] = tick
            effective_timeout = min(effective_timeout, float(cancel_cfg["request_timeout_s"]))

            def _trigger_cancel() -> None:
                if not state["request_active"]:
                    return
                now_p = time.perf_counter()
                state["cancel_requested_while_waiting"] = True
                state["cancel_triggered_perf"] = now_p
                state["elapsed_before_cancel_ms"] = round((now_p - tick) * 1000.0, 2)
                cancel_cfg["event"].set()

            timer = threading.Timer(float(cancel_cfg["delay_ms"]) / 1000.0, _trigger_cancel)
            timer.daemon = True
            timer.start()

        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as reply:
                raw_bytes = reply.read()
                if cancel_cfg is not None:
                    cancel_cfg["state"]["request_active"] = False
                data = json.loads(raw_bytes.decode("utf-8"))
            duration_ms = (time.perf_counter() - tick) * 1000.0
            if timer is not None:
                timer.cancel()
            has_eval_counts = all(type(data.get(field)) is int and data[field] >= 0
                                  for field in ("prompt_eval_count", "eval_count"))
            prompt_toks = int(data.get("prompt_eval_count") or 0)
            completion_toks = int(data.get("eval_count") or 0)
            err = data.get("error") or (None if data.get("done") is True else "incomplete_chat_response")
            record = {
                "call_index": len(self.call_Records) + 1,
                "duration_ms": round(duration_ms, 2),
                "timeout_s": effective_timeout,
                "request": payload,
                "raw_response": data,
                "token_usage_known": bool(has_eval_counts and err is None),
                "prompt_tokens": prompt_toks if (has_eval_counts and err is None) else None,
                "completion_tokens": completion_toks if (has_eval_counts and err is None) else None,
                "total_tokens": (prompt_toks + completion_toks) if (has_eval_counts and err is None) else None,
                "done_reason": data.get("done_reason"),
                "error": err,
            }
            self._record_call(record)
            return {
                "message": data.get("message", {}),
                "prompt_tokens": prompt_toks,
                "completion_tokens": completion_toks,
                "done_reason": data.get("done_reason"),
                "error": err,
                "request": payload,
                "raw_response": data,
                "token_usage_known": record["token_usage_known"],
                "duration_ms": duration_ms,
            }
        except Exception as exc:
            if cancel_cfg is not None:
                cancel_cfg["state"]["request_active"] = False
            duration_ms = (time.perf_counter() - tick) * 1000.0
            if timer is not None:
                timer.cancel()
            record = {
                "call_index": len(self.call_Records) + 1,
                "duration_ms": round(duration_ms, 2),
                "timeout_s": effective_timeout,
                "request": payload,
                "raw_response": None,
                "token_usage_known": False,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "done_reason": None,
                "error": str(exc),
            }
            self._record_call(record)
            return {
                "message": {},
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "request": payload,
                "raw_response": None,
                "token_usage_known": False,
                "error": str(exc),
                "duration_ms": duration_ms,
            }
        finally:
            if cancel_cfg is not None:
                cancel_cfg["state"]["request_active"] = False
            if timer is not None:
                timer.cancel()


def evaluate_turn4_binary_search(answer: str) -> Dict[str, Any]:
    """Keyword triage only; prose requires human semantic review."""
    text = (answer or "").lower()
    if not text.strip():
        return {
            "has_answer": False,
            "mentions_mid_2": False,
            "claims_6_gt_6_or_continues_search": False,
            "heuristic_match": False,
            "semantic_correctness_verified": False,
            "verdict": "missing_answer",
            "explanation": "Turn 4 produced no final answer.",
        }

    mentions_mid_2 = any(
        pat in text
        for pat in ("mid = 2", "mid=2", "chỉ số 2", "index 2", "vị trí 2", "a[2]", "arr[2]")
    )
    false_inequality_or_extra_step = any(
        pat in text
        for pat in (
            "6 > 6",
            "6 < 6",
            "mid = 3",
            "mid=3",
            "low = 3",
            "low=3",
            "left = 3",
            "left=3",
            "high = 1",
            "high=1",
            "right = 1",
            "right=1",
        )
    )
    stops_at_match = mentions_mid_2 and not false_inequality_or_extra_step
    return {
        "has_answer": True,
        "mentions_mid_2": mentions_mid_2,
        "claims_6_gt_6_or_continues_search": false_inequality_or_extra_step,
        "heuristic_match": stops_at_match,
        "semantic_correctness_verified": False,
        "verdict": "candidate_requires_review" if stops_at_match else "flagged_requires_review",
        "explanation": (
            "Text contains a mid/index-2 marker without the selected contradiction markers; semantic review is required."
            if stops_at_match
            else "Text lacks the selected mid/index-2 markers or contains a contradiction marker; semantic review is required."
        ),
    }


def run_smoke_suite(
    *,
    model_name: str,
    plan_tasks: bool,
    max_steps: int,
    timeout_s: float,
    scenario: str = "dsa",
    call_log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    source_start = compute_source_hashes(REPO_ROOT)
    history = ConversationHistory()
    client = InstrumentedSLMEngine(model=model_name, default_timeout=timeout_s)
    if call_log_path is not None:
        with call_log_path.open('x', encoding='utf-8'):
            pass
        client.record_path = call_log_path
    runtime = AssistantRuntime(
        db=MagicMock(),
        compositor=TimetableCompositor([]),
        use_live_model=True,
        plan_tasks=plan_tasks,
        model_client=client,
    )

    prompts = SCENARIOS[scenario]

    turn_logs: List[Dict[str, Any]] = []
    active_task_state: Dict[str, Any] = {}
    previous_turn_id: Optional[str] = None

    for idx, (label, q) in enumerate(prompts, start=1):
        if call_log_path is not None:
            print(json.dumps({'scenario': scenario, 'turn': idx, 'phase': 'started'}), flush=True)
        # R5 FIX: Capture prior_messages and prior_refs BEFORE history.begin_turn(q)
        prior_messages = history.messages_with_turn_ids()
        prior_refs = history.turn_references()
        snap = history.begin_turn(q)

        # Verify R5 context integrity before execution
        prev_assistant_present = True
        prev_assistant_entry = None
        if previous_turn_id is not None:
            prev_assistant_entry = prior_messages[-1] if prior_messages else None
            prev_assistant_present = bool(
                prev_assistant_entry
                and prev_assistant_entry.get("role") == "assistant"
                and prev_assistant_entry.get("turn_id") == previous_turn_id
                and bool(prev_assistant_entry.get("content"))
            )

        context_check = {
            "prior_messages_count": len(prior_messages),
            "prior_turn_references_count": len(prior_refs),
            "current_turn_leaked_into_prior_messages": any(
                m.get("turn_id") == snap.turn_id for m in prior_messages
            ),
            "current_turn_leaked_into_prior_refs": any(
                r.get("turn_id") == snap.turn_id for r in prior_refs
            ),
            "expected_previous_turn_id": previous_turn_id,
            "previous_turn_assistant_present": prev_assistant_present,
            "last_prior_message": prev_assistant_entry,
        }

        call_cursor_start = len(client.call_Records)

        if label == "turn_6_in_flight_cancel":
            cancel_event = threading.Event()
            cancel_state = client.arm_in_flight_cancel(
                cancel_event,
                delay_ms=250.0,
                request_timeout_s=0.6,
            )
            res = runtime.run(
                q,
                max_steps=max_steps,
                history=prior_messages,
                turn_ref=snap.to_turn_ref(history.conversation_id),
                execution_id=snap.execution_id,
                conversation_id=history.conversation_id,
                turn_references=prior_refs,
                task_state=dict(active_task_state),
                should_cancel=cancel_event.is_set,
            )
            client.disarm_in_flight_cancel()
            cancelled_ctx = runtime.notebook.current_context()

            # Probe late note write & late dispatcher operation with cancelled execution_id
            late_note_rejected = False
            late_note_error = None
            try:
                runtime.notebook.record(
                    "Ghi chú trễ sau khi hủy",
                    "Ghi chú trễ",
                    context=cancelled_ctx,
                )
            except ValueError as exc:
                late_note_rejected = "cancelled" in str(exc)
                late_note_error = str(exc)

            late_dispatch = runtime.dispatcher.execute_operation(
                "record_work_note",
                {"text": "Ghi chú trễ qua dispatcher", "source_quote": "Ghi chú trễ"},
                context={"execution_id": res.execution_id, "note_context": cancelled_ctx},
            )
            late_dispatch_rejected = (
                late_dispatch.status in ("cancelled", "error")
                and "cancelled" in (late_dispatch.error or "")
            )
            in_flight_cancel_proof = {
                **cancel_state,
                "cancel_event_set_after_run": cancel_event.is_set(),
                "late_note_write_rejected": late_note_rejected,
                "late_note_error": late_note_error,
                "late_dispatch_rejected": late_dispatch_rejected,
                "late_dispatch_status": late_dispatch.status,
                "late_dispatch_error": late_dispatch.error,
            }
        else:
            in_flight_cancel_proof = None
            res = runtime.run(
                q,
                max_steps=max_steps,
                history=prior_messages,
                turn_ref=snap.to_turn_ref(history.conversation_id),
                execution_id=snap.execution_id,
                conversation_id=history.conversation_id,
                turn_references=prior_refs,
                task_state=dict(active_task_state),
            )
        if not res.error and res.task_state_updated and res.task_state:
            active_task_state = dict(res.task_state)
        metadata = dict(execution_id=res.execution_id,
                        artifact_refs=[{"artifact_id": a.id, "revision": a.revision} for a in res.artifacts],
                        note_ids=[n["id"] for n in runtime.notebook.notes_for_turn(snap.turn_id)],
                        note_event_ids=[event["event_id"] for event in res.note_events],
                        task_state=dict(active_task_state))
        if res.error == "cancelled":
            history.cancel_turn(snap.turn_id, **metadata)
        elif res.error:
            history.fail_turn(snap.turn_id, "failed", error=res.error, **metadata)
        elif res.pending_input_request:
            history.fail_turn(snap.turn_id, "needs_input", **metadata)
        else:
            history.complete_turn(snap.turn_id, res.answer, **metadata)

        turn_calls = client.call_Records[call_cursor_start:]
        all_tokens_known = bool(turn_calls) and all(c["token_usage_known"] for c in turn_calls)
        known_prompt_tokens = (
            sum(c["prompt_tokens"] for c in turn_calls if c["prompt_tokens"] is not None)
            if all_tokens_known
            else None
        )
        known_completion_tokens = (
            sum(c["completion_tokens"] for c in turn_calls if c["completion_tokens"] is not None)
            if all_tokens_known
            else None
        )
        known_total_tokens = (
            (known_prompt_tokens + known_completion_tokens)
            if (known_prompt_tokens is not None and known_completion_tokens is not None)
            else None
        )

        turn_logs.append({
            "turn_index": idx,
            "label": label,
            "turn_id": snap.turn_id,
            "snap_execution_id": snap.execution_id,
            "response_execution_id": res.execution_id,
            "execution_id_matched": snap.execution_id == res.execution_id,
            "query": q,
            "answer": res.answer,
            "error": res.error,
            "total_time_ms": round(res.total_time_ms, 2),
            "model_time_ms": round(res.model_time_ms, 2),
            "tool_time_ms": round(res.tool_time_ms, 2),
            "tool_call_count": res.tool_call_count,
            "completion_status": res.completion_status,
            "answer_verification_status": res.answer_verification_status,
            "verification_reports": res.verification_reports,
            "controller_decisions": res.controller_decisions,
            "verification_time_ms": res.verification_time_ms,
            "artifacts": [artifact.to_dict() for artifact in res.artifacts],
            "token_accounting": {
                "token_usage_known": all_tokens_known,
                "prompt_tokens": known_prompt_tokens,
                "completion_tokens": known_completion_tokens,
                "total_tokens": known_total_tokens,
                "runtime_reported_prompt_tokens": res.prompt_tokens,
                "runtime_reported_completion_tokens": res.completion_tokens,
            },
            "context_integrity_check": context_check,
            "in_flight_cancel_proof": in_flight_cancel_proof,
            "PriorMessagesSent": prior_messages,
            "PriorTurnReferencesSent": prior_refs,
            "steps": [
                {
                    "step_number": s.step_number,
                    "thought": s.thought,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args,
                    "tool_result": s.tool_result,
                    "duration_ms": round(s.duration_ms, 2),
                    "model_duration_ms": round(s.model_duration_ms, 2),
                    "tool_duration_ms": round(s.tool_duration_ms, 2),
                    "prompt_tokens": s.prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "raw_completion": s.raw_completion,
                    "model_input": s.model_input,
                    "error": s.error,
                    "turn_id": s.turn_id,
                    "execution_id": s.execution_id,
                    "note_events": s.note_events,
                    "verification": s.verification,
                }
                for s in res.steps
            ],
            "raw_model_calls": turn_calls,
            "note_events": res.note_events,
            "active_notes_snapshot": runtime.notebook.snapshot(),
            "historical_notes_snapshot": runtime.notebook.historical_context(),
            "turn_reference": res.turn_reference,
        })

        previous_turn_id = snap.turn_id
        if call_log_path is not None:
            print(json.dumps({'turn': idx, 'error': res.error, 'note_events': len(res.note_events),
                              'seconds': round(res.total_time_ms / 1000, 2)}), flush=True)

    turn4_entry = next((t for t in turn_logs if t["label"] == "turn_4_change_target_6"), None)
    turn6_entry = next((t for t in turn_logs if t["label"] == "turn_6_in_flight_cancel"), None)
    turn4_eval = evaluate_turn4_binary_search(turn4_entry["answer"]) if turn4_entry else None

    non_cancel_turns = [t for t in turn_logs if t["label"] != "turn_6_in_flight_cancel"]
    completed_non_cancel = [t for t in non_cancel_turns if t["error"] is None and t["answer"].strip()]
    errored_non_cancel = [t for t in non_cancel_turns if t["error"] is not None]
    initial_plan_steps = sum(
        1
        for t in turn_logs
        for s in t["steps"]
        if isinstance(s.get("tool_result"), dict) and s["tool_result"].get("phase") == "initial_plan"
    )
    model_invoked_tool_calls = sum(
        1
        for t in turn_logs
        for s in t["steps"]
        if s["tool_name"] is not None
        and s["tool_result"] is not None
        and not (isinstance(s.get("tool_result"), dict) and s["tool_result"].get("phase") == "initial_plan")
        and not (isinstance(s.get("tool_result"), dict) and s["tool_result"].get("error") == "paired_stop")
    )
    record_note_calls = sum(
        1
        for t in turn_logs
        for s in t["steps"]
        if s["tool_name"] == "record_work_note"
    )
    total_note_events = sum(len(t["note_events"]) for t in turn_logs)

    evaluation = {
        "lifecycle_and_context_contracts": {
            "all_execution_ids_matched": all(t["execution_id_matched"] for t in turn_logs),
            "all_prior_assistant_messages_preserved_r5": all(
                t["context_integrity_check"]["previous_turn_assistant_present"]
                for t in turn_logs
            ),
            "no_current_turn_leaked_into_prior_messages": all(
                not t["context_integrity_check"]["current_turn_leaked_into_prior_messages"]
                for t in turn_logs
            ),
            "no_current_turn_leaked_into_prior_refs": all(
                not t["context_integrity_check"]["current_turn_leaked_into_prior_refs"]
                for t in turn_logs
            ),
            "turn_6_cancel_flag_and_late_write_guards": bool(
                turn6_entry
                and turn6_entry["error"] == "cancelled"
                and turn6_entry["in_flight_cancel_proof"]
                and not turn6_entry["in_flight_cancel_proof"]["was_cancelled_before_start"]
                and turn6_entry["in_flight_cancel_proof"]["request_attempted"]
                and turn6_entry["in_flight_cancel_proof"]["cancel_requested_while_waiting"]
                and turn6_entry["in_flight_cancel_proof"]["late_note_write_rejected"]
                and turn6_entry["in_flight_cancel_proof"]["late_dispatch_rejected"]
            ),
            "native_cancellation_verified": False,
            "backend_cancellation_verified": False,
        },
        "model_behavior_and_content_quality": {
            "non_cancel_turns_total": len(non_cancel_turns),
            "non_cancel_turns_completed_without_runtime_error": len(completed_non_cancel),
            "non_cancel_turns_with_runtime_or_timeout_error": [
                {"turn_id": t["turn_id"], "label": t["label"], "error": t["error"]}
                for t in errored_non_cancel
            ],
            "runtime_reported_tool_call_count_total": sum(t["tool_call_count"] for t in turn_logs),
            "initial_plan_steps_count": initial_plan_steps,
            "model_invoked_tool_calls_count": model_invoked_tool_calls,
            "model_proposed_tool_calls_count": sum(
                len((call.get("raw_response") or {}).get("message", {}).get("tool_calls", []))
                for turn in turn_logs for call in turn["raw_model_calls"]
            ),
            "record_work_note_calls_count": record_note_calls,
            "note_events_count": total_note_events,
            "model_issued_note_calls": record_note_calls > 0,
            "turn_4_binary_search_evaluation": turn4_eval,
            "explicit_note_requests": [
                {"turn_id": turn["turn_id"], "query": turn["query"],
                 "note_events_count": len(turn["note_events"]),
                 "observed_result_note_committed": any(
                     event["snapshot"].get("source") == "artifact_result" and event["snapshot"].get("confirmed")
                     for event in turn["note_events"])}
                for turn in turn_logs
                if turn["label"] in ("turn_2_record", "turn_3_change_and_record", "turn_7_resume_and_record")
            ],
        },
    }

    source_end = compute_source_hashes(REPO_ROOT)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "script": "scripts/run_dsa_core_smoke.py",
            "scenario": scenario,
            "evidence_scope": "exposed_development_smoke_not_research_benchmark",
            "model": client.model,
            "ollama_url": client.ollama_url,
            "plan_tasks": plan_tasks,
            "max_steps": max_steps,
            "timeout_s": timeout_s,
            "matches_omnibar_planner_and_step_settings": bool(plan_tasks is True and max_steps == 8),
            "native_equivalence_verified": False,
            "model_revision_verified": False,
            "timing_scope": "client wall time; excludes native GUI; cancel probe timeout overridden to 0.6s",
            "token_scope": "prompt and completion counts; unknown on missing counts or failed responses",
            "source_sha256": source_start,
            "source_sha256_end": source_end,
            "source_changed_during_run": [name for name in source_start if source_start[name] != source_end[name]],
            "call_journal": str(call_log_path) if call_log_path else None,
            "journal_errors": [record['journal_error'] for record in client.call_Records if record.get('journal_error')],
        },
        "conversation_id": history.conversation_id,
        "evaluation": evaluation,
        "turns": turn_logs,
        "final_history_turns": [t.to_dict() for t in history.turns()],
        "final_turn_references": history.turn_references(),
        "final_messages_with_turn_ids": history.messages_with_turn_ids(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible RAT shared conversation core DSA smoke.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write raw JSON smoke artifacts into.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=config.assistant_model or config.ollama_model or "qwen2.5:1.5b",
        help="Ollama model name.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Max ReAct steps per turn (Omnibar AssistantWorker uses 8).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Per-call HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--mode",
        choices=["omnibar", "no_plan", "both"],
        default="both",
        help="Run 'omnibar' (plan_tasks=True), 'no_plan' (plan_tasks=False), or 'both'.",
    )
    parser.add_argument("--scenario", choices=list(SCENARIOS), default="dsa",
                        help="Development conversation inputs; does not change app routing.")
    args = parser.parse_args()
    if not 1 <= args.max_steps <= 20 or not 0 < args.timeout < float('inf'):
        parser.error("max-steps must be 1..20 and timeout must be positive and finite")

    out_dir: Path = args.output_dir.resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("output-dir already exists; choose a new directory to preserve run evidence")

    summary_index: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "scenario": args.scenario,
        "source_sha256": compute_source_hashes(REPO_ROOT),
        "runs": {},
    }

    if args.mode in ("omnibar", "both"):
        omnibar_report = run_smoke_suite(
            model_name=args.model,
            plan_tasks=True,
            max_steps=args.max_steps,
            timeout_s=args.timeout,
            scenario=args.scenario,
            call_log_path=out_dir / 'raw_calls_plan_tasks_true.jsonl',
        )
        omnibar_path = out_dir / f"live_{args.scenario}_smoke_plan_tasks_true.json"
        omnibar_path.write_text(json.dumps(omnibar_report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_index["runs"]["plan_tasks_true"] = {
            "artifact": str(omnibar_path),
            "evaluation": omnibar_report["evaluation"],
        }

    if args.mode in ("no_plan", "both"):
        no_plan_report = run_smoke_suite(
            model_name=args.model,
            plan_tasks=False,
            max_steps=args.max_steps,
            timeout_s=args.timeout,
            scenario=args.scenario,
            call_log_path=out_dir / 'raw_calls_plan_tasks_false.jsonl',
        )
        no_plan_path = out_dir / f"live_{args.scenario}_smoke_plan_tasks_false.json"
        no_plan_path.write_text(json.dumps(no_plan_report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_index["runs"]["plan_tasks_false"] = {
            "artifact": str(no_plan_path),
            "evaluation": no_plan_report["evaluation"],
        }

    summary_path = out_dir / "smoke_summary.json"
    summary_path.write_text(json.dumps(summary_index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary_index, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
