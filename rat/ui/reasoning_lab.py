"""Standalone demo window showing how the measured policy solves one question."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QThread, QUrl, pyqtProperty, pyqtSignal, pyqtSlot, Qt

from rat.config import RAT_DIR
from rat.engine.measured_ladder import (MODE_POLICY, STRATEGY_LABELS, LabRun, append_log, solve)

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
logger = logging.getLogger(__name__)

MODEL_REPO = "mlx-community/Qwen3-8B-4bit"
LOG_PATH = RAT_DIR / "reasoning_lab_runs.jsonl"

EXAMPLES = [
    {"label": "Chia tiền nhóm", "expected": "265000",
     "text": "Nhóm 5 người ăn hết 1250000 đồng, cộng thêm 10% phí phục vụ, sau đó được giảm 50000 đồng. Mỗi người phải trả bao nhiêu đồng?"},
    {"label": "Điểm cuối kỳ", "expected": "8.6",
     "text": "Điểm giữa kỳ 7 chiếm 30%, điểm thực hành 8 chiếm 20%, điểm cuối kỳ chiếm 50%. Cần bao nhiêu điểm cuối kỳ để tổng kết đạt 8?"},
    {"label": "Trả góp laptop", "expected": "1176000",
     "text": "Mua laptop giá 18000000 đồng, trả trước 30%. Phần còn lại trả đều trong 12 tháng, mỗi tháng cộng thêm phí 1% trên số tiền vay ban đầu. Mỗi tháng phải trả bao nhiêu đồng?"},
    {"label": "Câu từng làm mô hình sai", "expected": "16",
     "text": "Ben works 8-hour shifts in a furniture shop.  It takes him 5 hours to build 1 rocking chair.  How many chairs can he build in 10 days?"},
]


def load_real_backend():
    from qwen_mlx_backend import QwenMLXBackend
    backend = QwenMLXBackend(MODEL_REPO, max_tokens=1024, prompt_profile="english-math-v1")
    backend.configure_answer_format("number")
    return backend


def _numbers_match(answer: str, expected: str) -> bool:
    try:
        return abs(float(answer.replace(",", "")) - float(expected)) < 1e-6
    except ValueError:
        return False


def present_run(run: LabRun, expected: str = "") -> dict:
    """Turn a run into plain values for QML, labelling correctness only when known."""
    def verdict(answer: str) -> str:
        if not expected or not answer:
            return ""
        return "correct" if _numbers_match(answer, expected) else "wrong"

    return {
        "question": run.question,
        "mode": run.mode,
        "reason": run.reason,
        "status": run.status,
        "finalLabel": STRATEGY_LABELS.get(run.final_strategy, ""),
        "finalAnswer": run.final_answer,
        "finalVerdict": verdict(run.final_answer),
        "expected": expected,
        "path": [STRATEGY_LABELS[name] for name in run.path],
        "tokens": run.tokens,
        "promptTokens": run.prompt_tokens,
        "calls": len(run.steps),
        "seconds": round(run.seconds, 1),
        "steps": [{
            "strategy": step.strategy,
            "label": STRATEGY_LABELS[step.strategy],
            "answer": step.answer,
            "verdict": verdict(step.answer),
            "confidence": f"{step.confidence:.4f}",
            "tokens": step.tokens,
            "seconds": round(step.seconds, 1),
            "text": step.text,
            "code": step.code,
            "toolOutput": step.tool_output,
            "toolOk": step.tool_ok is not False,
            "decision": step.decision,
        } for step in run.steps],
    }


class LabWorker(QObject):
    """Owns the model on one thread, because MLX streams are bound to their thread."""
    loading = pyqtSignal()
    strategyStarted = pyqtSignal(int, str)
    stepFinished = pyqtSignal(int, object)
    finished = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, backend_factory: Callable[[], Any], log_path: Path):
        super().__init__()
        self.backend_factory = backend_factory
        self.log_path = log_path
        self.backend = None
        self.cancel_generation = 0

    @pyqtSlot(int, str, str)
    def run(self, generation: int, question: str, mode: str):
        cancelled = lambda: self.cancel_generation >= generation
        try:
            if self.backend is None:
                self.loading.emit()
                self.backend = self.backend_factory()
            result = solve(self.backend, question, mode, should_cancel=cancelled,
                           on_start=lambda name: self.strategyStarted.emit(generation, name),
                           on_step=lambda partial: self.stepFinished.emit(generation, partial))
            if result.steps:
                append_log(result, self.log_path, model_id=getattr(self.backend, "model_id", ""))
            self.finished.emit(generation, result)
        except Exception as exc:
            logger.exception("Reasoning lab run failed")
            self.failed.emit(generation, f"{type(exc).__name__}: {exc}")


class ReasoningLabController(QObject):
    changed = pyqtSignal()
    _requestRun = pyqtSignal(int, str, str)

    def __init__(self, backend_factory: Callable[[], Any] = load_real_backend, *, log_path: Path = LOG_PATH):
        super().__init__()
        self.log_path = log_path
        self._generation = 0
        self._busy = False
        self._status = ""
        self._error = ""
        self._expected = ""
        self._question = ""
        self._mode = MODE_POLICY
        self._result: dict = {}
        self._thread = QThread()
        self._worker = LabWorker(backend_factory, log_path)
        self._worker.moveToThread(self._thread)
        self._requestRun.connect(self._worker.run)
        self._worker.loading.connect(self._on_loading)
        self._worker.strategyStarted.connect(self._on_strategy)
        self._worker.stepFinished.connect(self._on_step)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    @pyqtProperty("QVariantMap", notify=changed)
    def snapshot(self):
        return {"busy": self._busy, "status": self._status, "error": self._error, "question": self._question,
                "mode": self._mode, "result": self._result, "examples": EXAMPLES, "logPath": str(self.log_path)}

    @pyqtSlot(int)
    def useExample(self, index: int):
        self._question = EXAMPLES[index]["text"]
        self._expected = EXAMPLES[index]["expected"]
        self.changed.emit()

    @pyqtSlot(str)
    def editQuestion(self, text: str):
        if text != self._question:
            self._question = text
            self._expected = ""
            self.changed.emit()

    @pyqtSlot(str)
    def setMode(self, mode: str):
        self._mode = mode
        self.changed.emit()

    @pyqtSlot()
    def submit(self):
        if self._busy or not self._question.strip():
            return
        self._generation += 1
        self._busy = True
        self._error = ""
        self._result = {}
        self._status = "Đang chuẩn bị…"
        self.changed.emit()
        self._requestRun.emit(self._generation, self._question, self._mode)

    @pyqtSlot()
    def cancel(self):
        if self._busy:
            self._worker.cancel_generation = self._generation
            self._status = "Đang dừng…"
            self.changed.emit()

    def _on_loading(self):
        self._status = "Đang nạp Qwen3-8B vào bộ nhớ, lần đầu mất khoảng một phút…"
        self.changed.emit()

    def _on_strategy(self, generation: int, name: str):
        if generation == self._generation:
            self._status = f"Đang chạy: {STRATEGY_LABELS[name]}…"
            self.changed.emit()

    def _on_step(self, generation: int, partial: LabRun):
        if generation == self._generation:
            self._result = present_run(partial, self._expected)
            self.changed.emit()

    def _on_finished(self, generation: int, result: LabRun):
        if generation != self._generation:
            return
        self._busy = False
        self._status = ""
        self._result = present_run(result, self._expected)
        if result.status == "failed":
            self._error = result.reason
        self.changed.emit()

    def _on_failed(self, generation: int, message: str):
        if generation == self._generation:
            self._busy = False
            self._status = ""
            self._error = message
            self.changed.emit()

    def close(self):
        self._worker.cancel_generation = self._generation
        self._thread.quit()
        self._thread.wait(30000)


def create_view(controller: ReasoningLabController, *, dark_mode: Optional[bool] = None):
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtQuick import QQuickView

    app = QGuiApplication.instance()
    view = QQuickView()
    view.setTitle("RAT · Phòng suy luận")
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setMinimumWidth(720)
    view.setMinimumHeight(560)
    view.resize(980, 780)
    dark = dark_mode if dark_mode is not None else app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    view.setInitialProperties({"controller": controller, "darkMode": dark})
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "quick/ReasoningLab.qml")))
    if view.status() != QQuickView.Status.Ready:
        raise RuntimeError("; ".join(error.toString() for error in view.errors()))
    return view


def main() -> int:
    from PyQt6.QtGui import QFont, QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setApplicationName("RAT")
    if sys.platform == "darwin":
        app.setFont(QFont("Helvetica Neue", 13))
    controller = ReasoningLabController()
    try:
        view = create_view(controller)
        view.show()
        return app.exec()
    finally:
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
