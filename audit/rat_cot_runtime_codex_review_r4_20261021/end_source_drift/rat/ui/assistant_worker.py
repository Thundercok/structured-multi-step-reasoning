"""Run the RAT assistant outside the GUI thread; emit only observed progress."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from rat.engine.assistant_runtime import AgentResponse, AssistantRuntime
from rat.engine.execution import ExecutionRequest
from rat.ui.reasoning_worker import OnlineReasoningWorker


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
        self.startup_error = startup_error

    def run(self):
        try:
            if self.startup_error:
                response = AgentResponse(answer="", steps=[], total_time_ms=0,
                    tool_call_count=0, token_estimate=0, error=self.startup_error)
            elif self.isInterruptionRequested():
                response = AgentResponse(answer="", steps=[], total_time_ms=0,
                    tool_call_count=0, token_estimate=0, error="cancelled")
            elif self.document_path:
                from rat.engine.selected_document_qa import answer_selected_document
                response = answer_selected_document(self.runtime, self.query, self.document_path,
                    **self.context, on_progress=self.progress_changed.emit,
                    on_step=self.step_completed.emit, on_text=self.text_streamed.emit,
                    should_cancel=self.isInterruptionRequested)
            else:
                response = self.runtime.run(
                    self.query, max_steps=8, **self.context,
                    on_progress=self.progress_changed.emit, on_step=self.step_completed.emit,
                    should_cancel=self.isInterruptionRequested,
                )
        except Exception as exc:
            response = AgentResponse(answer="", steps=[], total_time_ms=0, tool_call_count=0,
                                     token_estimate=0, error=str(exc))
        response.execution_id = self.execution_request.execution_id or response.execution_id
        response.turn_id = getattr(self.execution_request.turn_ref, "turn_id", None) or response.turn_id
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

    def __init__(self, callback, parent=None, *, request=None):
        super().__init__(parent)
        self.callback = callback
        self.execution_request = request

    def run(self):
        from rat.kernel.contracts import DispatchResult
        try:
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
        return ArtifactWorker(operation, parent=parent, request=request)
    wants_reasoning = not request.document_path and (
        request.lane == "reasoning" or
        (request.lane == "auto" and reasoning_engine is not None
         and reasoning_engine.is_reasoning_query(request.query))
    )
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
        worker = OnlineReasoningWorker(
            reasoning_engine, request.query, execution_id=request.execution_id,
            query_generation=request.generation, timeout_s=request.timeout_s,
            max_strategy_invocations=request.max_strategy_invocations,
            max_underlying_requests=request.max_underlying_requests,
            max_generated_tokens=request.max_generated_tokens, parent=parent,
        )
        worker.execution_request = request
        return worker
    if request.lane == "document" and not request.document_path:
        return AssistantWorker(runtime, request.query, request=request,
                               startup_error="missing_selected_document", parent=parent)
    return AssistantWorker(runtime, request.query, request=request, parent=parent)
