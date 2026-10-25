"""
rat.engine.execution_service — Headless unified execution coordinator for all RAT capabilities.

Implements the single agentic execution entry point according to the immutable rule:
"TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC."

Manages the 6 lifecycle phases:
    accepted -> planning -> dispatching -> observing -> checking -> deciding
Enforces pre-checks (resource bindings, budget, idempotency, stale context)
and dispatches through ActionDispatcher / AssistantRuntime without creating
competing agent loops or domain UI bypasses.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from rat.engine.assistant_runtime import AgentResponse, AgentStep, AssistantRuntime
from rat.engine.execution import ExecutionRequest, execution_response
from rat.engine.verification import ExecutionEvidence
from rat.kernel.contracts import ExecutionEvent


class AgentExecutionService:
    """Headless service coordinating execution for chat, UI actions, and CLI."""

    def __init__(
        self,
        runtime: AssistantRuntime,
        *,
        reasoning_engine: Optional[Any] = None,
        allow_synthetic_policy: bool = False,
    ):
        self.runtime = runtime
        self.reasoning_engine = reasoning_engine
        self.allow_synthetic_policy = allow_synthetic_policy
        self._idempotency_cache: Dict[str, AgentResponse] = {}
        self._lock = threading.Lock()

    def execute(
        self,
        request: ExecutionRequest,
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        on_event: Optional[Callable[[ExecutionEvent], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_text: Optional[Callable[[str], None]] = None,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> AgentResponse:
        """Execute a business request through the unified agentic lifecycle."""
        seq = 0
        events_emitted: List[ExecutionEvent] = []

        def emit(
            event_type: str,
            *,
            payload: Any = None,
            operation_name: Optional[str] = None,
            artifact_id: Optional[str] = None,
            error: Optional[str] = None,
            artifact_refs: Optional[List[str]] = None,
        ) -> ExecutionEvent:
            nonlocal seq
            seq += 1
            event = ExecutionEvent(
                type=event_type,
                operation_name=operation_name,
                artifact_id=artifact_id,
                payload=payload,
                error=error,
                turn_id=request.turn_id,
                execution_id=request.execution_id,
                generation=request.generation,
                sequence=seq,
                artifact_refs=artifact_refs or [],
            )
            events_emitted.append(event)
            if callable(on_event):
                try:
                    on_event(event)
                except Exception:
                    pass
            return event

        def check_cancelled() -> bool:
            return bool(should_cancel and should_cancel())

        # -----------------------------------------------------------------
        # Phase 1: ACCEPTED
        # -----------------------------------------------------------------
        emit("accepted", payload={"origin": request.origin, "goal": request.goal})

        if check_cancelled():
            emit("cancelling")
            emit("turn_failed", error="cancelled")
            return AgentResponse("", [], 0, 0, 0, error="cancelled",
                                 execution_id=request.execution_id, turn_id=request.turn_id)

        # Idempotency check
        if request.idempotency_key:
            with self._lock:
                if request.idempotency_key in self._idempotency_cache:
                    cached = copy.deepcopy(self._idempotency_cache[request.idempotency_key])
                    emit("turn_completed", payload={"idempotent_replay": True})
                    return cached

        # Pre-check: Budget validation
        budget = request.budget or {}
        deadline_s = budget.get("deadline_s") if "deadline_s" in budget else request.timeout_s
        max_tokens = budget.get("max_generated_tokens") if "max_generated_tokens" in budget else request.max_generated_tokens
        if (deadline_s is not None and deadline_s <= 0) or (max_tokens is not None and max_tokens <= 0):
            emit("turn_failed", error="budget_exhausted")
            return AgentResponse("", [], 0, 0, 0, error="budget_exhausted",
                                 execution_id=request.execution_id, turn_id=request.turn_id)

        # Pre-check: Resource bindings validation (reject stale resources when pinned by hash)
        for binding in request.resource_bindings:
            expected_sha = binding.get("sha256")
            if expected_sha:
                path_str = binding.get("path") or binding.get("file_path")
                if path_str:
                    p = Path(path_str).resolve()
                    if not p.is_file():
                        err = f"stale_resource_binding: Tệp không tồn tại hoặc đã bị xóa ({path_str})"
                        emit("turn_failed", error=err)
                        return AgentResponse("", [], 0, 0, 0, error="stale_resource_binding",
                                             execution_id=request.execution_id, turn_id=request.turn_id)
                    actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
                    if actual_sha != expected_sha:
                        err = f"stale_resource_binding: Nội dung tệp đã thay đổi ({path_str})"
                        emit("turn_failed", error=err)
                        return AgentResponse("", [], 0, 0, 0, error="stale_resource_binding",
                                             execution_id=request.execution_id, turn_id=request.turn_id)

        # Pre-check: Continuation validation
        if request.continuation:
            target_aid = request.continuation.get("artifact_id") or request.continuation.get("target_artifact_id")
            target_rev = request.continuation.get("revision") or request.continuation.get("target_revision")
            if target_aid:
                art = self.runtime.artifact_store.get(target_aid)
                if not art or (target_rev is not None and art.revision != target_rev):
                    err = f"stale_continuation: Artifact {target_aid} không tồn tại hoặc revision đã đổi"
                    emit("turn_failed", error=err)
                    return AgentResponse("", [], 0, 0, 0, error="stale_continuation",
                                         execution_id=request.execution_id, turn_id=request.turn_id)

        # -----------------------------------------------------------------
        # Phase 2: PLANNING
        # -----------------------------------------------------------------
        plan_desc = f"Action: {request.requested_action.get('name')}" if request.requested_action else f"Goal: {request.goal}"
        emit("planning", payload={"plan": plan_desc})

        if check_cancelled():
            emit("cancelling")
            emit("turn_failed", error="cancelled")
            return AgentResponse("", [], 0, 0, 0, error="cancelled",
                                 execution_id=request.execution_id, turn_id=request.turn_id)

        # -----------------------------------------------------------------
        # Phase 3 & 4: DISPATCHING & OBSERVING
        # -----------------------------------------------------------------
        # Case A: Explicit single action requested by user (direct action contract)
        if request.requested_action:
            action_name = request.requested_action.get("name") or request.requested_action.get("operation_name")
            action_args = request.requested_action.get("args") or request.requested_action.get("arguments") or {}
            emit("dispatching", operation_name=action_name, payload=action_args)

            if callable(on_progress):
                on_progress(f"Đang thực hiện thao tác {action_name}…")

            ctx = {
                **request.context,
                **request.assistant_context(),
                "should_cancel": should_cancel,
                "runtime": self.runtime,
                "artifact_store": getattr(self.runtime, "artifact_store", None),
                "model_client": getattr(self.runtime, 'document_model_client', None) or getattr(self.runtime, 'model_client', None),
            }
            dispatch_res = self.runtime.dispatcher.execute_operation(action_name, action_args, context=ctx)

            art_id = dispatch_res.artifact.id if dispatch_res.artifact else None
            emit("observing", operation_name=action_name, artifact_id=art_id, payload=dispatch_res.result)

            # Phase 5: CHECKING
            emit("checking", operation_name=action_name)
            v_status = "UNKNOWN"
            v_reports = []
            op_def = self.runtime.registry.get_operation(action_name)
            if op_def and op_def.verifier:
                evidence = ExecutionEvidence(
                    id=f"{request.execution_id}:op:{action_name}",
                    operation=action_name,
                    args=action_args,
                    result=dispatch_res.result,
                    sha256="",
                )
                v_rep = op_def.verifier.check_execution(evidence)
                if v_rep:
                    v_status = v_rep.status.value
                    v_reports.append(v_rep.to_dict())

            # Phase 6: DECIDING
            emit("deciding", payload={"verification": v_status, "dispatch_status": dispatch_res.status})
            success = dispatch_res.status == "success" and v_status != "FAIL"
            err = (dispatch_res.error or "verification_failed") if not success else None

            step = AgentStep(
                step_number=1,
                thought=f"Đã thực thi {action_name}",
                tool_name=action_name,
                tool_args=action_args,
                tool_result=dispatch_res.result,
                error=err,
                verification=v_reports,
            )
            if callable(on_step):
                try:
                    on_step(step)
                except Exception:
                    pass

            if success:
                if isinstance(dispatch_res.result, dict) and "result" in dispatch_res.result:
                    ans_text = str(dispatch_res.result["result"])
                else:
                    ans_text = str(dispatch_res.result)
            else:
                ans_text = ""

            resp = AgentResponse(
                answer=ans_text,
                steps=[step],
                total_time_ms=0,
                tool_call_count=1,
                token_estimate=0,
                error=err,
                execution_id=request.execution_id,
                turn_id=request.turn_id,
                artifacts=[dispatch_res.artifact] if dispatch_res.artifact else [],
                answer_verification_status=v_status,
                verification_reports=v_reports,
            )

            if success:
                emit("turn_completed", payload={"status": "completed"})
                if request.idempotency_key:
                    with self._lock:
                        self._idempotency_cache[request.idempotency_key] = resp
            else:
                emit("turn_failed", error=err)
            return resp

        # Case B: Document QA (selected document path or bound document)
        doc_path = request.document_path
        if not doc_path and request.resource_bindings:
            bound_doc = next((b for b in request.resource_bindings if b.get("kind") == "document"), None)
            if bound_doc:
                doc_path = bound_doc.get("path") or bound_doc.get("file_path")

        if doc_path:
            emit("dispatching", operation_name="read_document", payload={"file_path": doc_path})
            from rat.engine.selected_document_qa import answer_selected_document

            ctx = request.assistant_context()
            ctx["selected_document_path"] = doc_path
            resp = answer_selected_document(
                self.runtime,
                request.query,
                doc_path,
                **ctx,
                on_progress=on_progress,
                on_text=on_text,
                on_step=on_step,
                should_cancel=should_cancel,
            )

            emit("observing", payload={"sources_count": len(resp.sources)})
            emit("checking", payload={"answer_verification": resp.answer_verification_status})
            emit("deciding", payload={"has_answer": bool(resp.answer), "error": resp.error})

            if not resp.error:
                emit("turn_completed", payload={"sources": resp.sources})
                if request.idempotency_key:
                    with self._lock:
                        self._idempotency_cache[request.idempotency_key] = resp
            else:
                emit("turn_failed", error=resp.error)
            return resp

        # Case C: Reasoning Engine strategy lane
        if request.lane == "reasoning" and self.reasoning_engine is not None:
            emit("dispatching", payload={"lane": "reasoning"})
            res = self.reasoning_engine.run(request.query, **request.assistant_context())
            resp = execution_response(request, res)
            emit("observing")
            emit("checking")
            emit("deciding")
            if not resp.error:
                emit("turn_completed")
                if request.idempotency_key:
                    with self._lock:
                        self._idempotency_cache[request.idempotency_key] = resp
            else:
                emit("turn_failed", error=resp.error)
            return resp

        # Case D: General multi-step structured reasoning loop
        emit("dispatching", payload={"lane": "assistant"})
        run_ctx = request.assistant_context()
        resp = self.runtime.run(
            request.query,
            max_steps=8,
            should_cancel=should_cancel,
            on_progress=on_progress,
            on_step=on_step,
            **run_ctx,
        )

        emit("observing", payload={"steps_count": len(resp.steps)})
        emit("checking", payload={"answer_verification": resp.answer_verification_status})
        emit("deciding", payload={"completion_status": resp.completion_status})

        if not resp.error:
            emit("turn_completed", payload={"status": "completed"})
            if request.idempotency_key:
                with self._lock:
                    self._idempotency_cache[request.idempotency_key] = resp
        else:
            emit("turn_failed", error=resp.error)
        return resp
