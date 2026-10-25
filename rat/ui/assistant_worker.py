"""Run the RAT assistant outside the GUI thread; emit only observed progress."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from rat.engine.assistant_runtime import AgentResponse, AssistantRuntime
from rat.engine.execution import ExecutionRequest


class ErrorDocumentModel:
    """Placeholder when a configured native document model path failed to initialize.

    Ensures selected-document Q&A returns the explicit native initialization error
    instead of silently falling back to Ollama or cloud providers.
    """
    supports_document_callbacks = True

    def __init__(self, error_message: str):
        self.error_message = error_message
        self.is_loaded = False
        self.model = "mlx:error"

    def chat_with_meta(self, *args, **kwargs):
        return {
            "error": self.error_message,
            "message": {"content": ""},
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    def preload(self):
        from concurrent.futures import Future
        f = Future()
        f.set_exception(ValueError(self.error_message))
        return f

    def close(self):
        pass


class AssistantWorker(QThread):
    progress_changed = pyqtSignal(str)
    step_completed = pyqtSignal(object)
    response_ready = pyqtSignal(object)
    text_streamed = pyqtSignal(str)

    def __init__(self, runtime: AssistantRuntime, query: str, *, history=None,
                 previous_sources=None, member_id=None, task_state=None,
                 turn_ref=None, execution_id=None, turn_references=None, document_path=None,
                 request=None, startup_error=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.query = query
        self.document_path = document_path
        self.context = dict(
            history=history or [],
            previous_sources=previous_sources or [],
            member_id=member_id,
            task_state=task_state or {},
            turn_ref=turn_ref,
            execution_id=execution_id,
            turn_references=turn_references,
        )
        self.execution_request = request or ExecutionRequest(
            query, execution_id=execution_id, turn_ref=turn_ref,
            document_path=document_path, context=self.context,
        )
        self.query = self.execution_request.query
        self.document_path = self.execution_request.document_path
        self.context = self.execution_request.assistant_context()
        # Evidence/artifact fields remain in the immutable request snapshot.
        # Both assistant and document lanes use Runtime's explicit context API.
        assistant_keys = {"history", "previous_sources", "member_id", "task_state",
                          "turn_ref", "execution_id", "turn_references",
                          "conversation_id", "contract"}
        self.context = {key: value for key, value in self.context.items()
                        if key in assistant_keys}
        if self.document_path:
            # A user-selected file grants a read of this exact path for this
            # execution only; it does not enroll the file in personal indexing.
            self.context["selected_document_path"] = self.document_path
        self.startup_error = startup_error

    def run(self):
        try:
            if self.startup_error:
                response = AgentResponse(answer="", steps=[], total_time_ms=0,
                    tool_call_count=0, token_estimate=0, error=self.startup_error)
            elif self.isInterruptionRequested():
                response = AgentResponse(answer="", steps=[], total_time_ms=0,
                    tool_call_count=0, token_estimate=0, error="cancelled")
            else:
                from rat.engine.execution_service import AgentExecutionService
                service = AgentExecutionService(self.runtime)
                response = service.execute(
                    self.execution_request,
                    should_cancel=self.isInterruptionRequested,
                    on_progress=self.progress_changed.emit,
                    on_step=self.step_completed.emit,
                    on_text=self.text_streamed.emit,
                )
        except Exception as exc:
            response = AgentResponse(answer="", steps=[], total_time_ms=0, tool_call_count=0,
                                     token_estimate=0, error=str(exc))
        response.execution_id = self.execution_request.execution_id or response.execution_id
        response.turn_id = getattr(self.execution_request.turn_ref, "turn_id", None) or response.turn_id
        response.qa_telemetry = {**(response.qa_telemetry or {}),
            "execution_lane": "document" if self.document_path else "assistant",
            "query_generation": self.execution_request.generation}
        self.response_ready.emit(response)
        # SQLite connections are thread-local; release only this worker's handle.
        local = getattr(self.runtime.db, "_local", None)
        connection = getattr(local, "conn", None)
        if connection is not None:
            connection.close()
            local.conn = None


class ArtifactWorker(QThread):
    """Run direct registered actions off the UI thread using the same dispatcher."""
    result_ready = pyqtSignal(object)

    def __init__(self, callback, parent=None, *, request=None, runtime=None):
        super().__init__(parent)
        self.callback = callback
        self.execution_request = request
        self.runtime = runtime

    def run(self):
        from rat.kernel.contracts import DispatchResult
        try:
            if self.runtime is not None and self.execution_request is not None and self.execution_request.requested_action:
                from rat.engine.execution_service import AgentExecutionService
                service = AgentExecutionService(self.runtime)
                resp = service.execute(self.execution_request, should_cancel=self.isInterruptionRequested)
                self.result_ready.emit(resp)
            else:
                self.result_ready.emit(self.callback())
        except Exception as exc:
            self.result_ready.emit(DispatchResult("error", error=str(exc)))


def create_execution_worker(runtime, request: ExecutionRequest, *, reasoning_engine=None,
                            allow_synthetic_policy=False, operation=None, parent=None):
    """One desktop dispatch boundary; reuse existing workers and model owners.

    Policy activation is explicit in the composition host. No model, bundle or
    provider is discovered/loaded here, and selected-document QA takes precedence.
    """
    if request.lane == "operation":
        if operation is None:
            raise ValueError("missing_operation_callback")
        return ArtifactWorker(operation, parent=parent, request=request, runtime=runtime)
    try:
        has_prior_reasoning = False
        t_refs = request.context.get("turn_references") or []
        t_ref = getattr(request, "turn_ref", None)
        target_tid = getattr(t_ref, "target_turn_id", None) if hasattr(t_ref, "target_turn_id") else (t_ref.get("target_turn_id") if isinstance(t_ref, dict) else None)
        if target_tid:
            has_prior_reasoning = True
        elif t_refs and any(r.get("execution_lane") == "reasoning" or r.get("status") == "completed" for r in t_refs[-2:]):
            has_prior_reasoning = True

        wants_reasoning = not request.document_path and (
            request.lane == "reasoning" or
            (request.lane == "auto" and reasoning_engine is not None
             and (reasoning_engine.is_reasoning_query(request.query) or has_prior_reasoning))
        )
    except Exception:
        return AssistantWorker(runtime, request.query, request=request,
            startup_error="reasoning_policy_unavailable:invalid_engine", parent=parent)
    if wants_reasoning:
        try:
            controller = getattr(reasoning_engine, "_controller", None)
            if controller is None or controller.bundle is None:
                raise ValueError("reasoning_policy_unavailable")
            from reasoning.bundle import validate_policy_bundle
            validate_policy_bundle(controller.bundle, controller.policy, controller.backend,
                                   allow_synthetic=allow_synthetic_policy)
        except Exception as exc:
            return AssistantWorker(runtime, request.query, request=request,
                startup_error=f"reasoning_policy_unavailable:{type(exc).__name__}", parent=parent)
        from rat.ui.reasoning_worker import OnlineReasoningWorker
        snapshot = request.context_snapshot() if hasattr(request, "context_snapshot") else None
        try:
            from rat.engine.execution import validate_referenced_context
            validate_referenced_context(snapshot)
        except (TypeError, ValueError, AttributeError):
            return AssistantWorker(runtime, request.query, request=request,
                startup_error="reasoning_context_unavailable", parent=parent)
        worker = OnlineReasoningWorker(
            reasoning_engine, request.query, execution_id=request.execution_id,
            query_generation=request.generation, timeout_s=request.timeout_s,
            max_strategy_invocations=request.max_strategy_invocations,
            max_underlying_requests=request.max_underlying_requests,
            max_generated_tokens=request.max_generated_tokens,
            context_snapshot=snapshot, parent=parent,
        )
        worker.execution_request = request
        return worker
    if request.lane == "document" and not request.document_path:
        return AssistantWorker(runtime, request.query, request=request,
                               startup_error="missing_selected_document", parent=parent)
    if any(value is not None for value in (request.timeout_s, request.max_strategy_invocations,
            request.max_underlying_requests, request.max_generated_tokens)):
        return AssistantWorker(runtime, request.query, request=request,
            startup_error="unsupported_execution_controls", parent=parent)
    return AssistantWorker(runtime, request.query, request=request, parent=parent)
