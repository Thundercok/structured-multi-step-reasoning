"""Run the RAT assistant outside the GUI thread; emit only observed progress."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from rat.engine.assistant_runtime import AgentResponse, AssistantRuntime


class AssistantWorker(QThread):
    progress_changed = pyqtSignal(str)
    step_completed = pyqtSignal(object)
    response_ready = pyqtSignal(object)

    def __init__(self, runtime: AssistantRuntime, query: str, *, history=None,
                 previous_sources=None, member_id=None, task_state=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.query = query
        self.context = dict(history=history or [], previous_sources=previous_sources or [], member_id=member_id,
                            task_state=task_state or {})

    def run(self):
        try:
            response = self.runtime.run(
                self.query, max_steps=8, **self.context,
                on_progress=self.progress_changed.emit, on_step=self.step_completed.emit,
                should_cancel=self.isInterruptionRequested,
            )
        except Exception as exc:
            response = AgentResponse(answer="", steps=[], total_time_ms=0, tool_call_count=0,
                                     token_estimate=0, error=str(exc))
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

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.callback = callback

    def run(self):
        from rat.kernel.contracts import DispatchResult
        try:
            self.result_ready.emit(self.callback())
        except Exception as exc:
            self.result_ready.emit(DispatchResult("error", error=str(exc)))
