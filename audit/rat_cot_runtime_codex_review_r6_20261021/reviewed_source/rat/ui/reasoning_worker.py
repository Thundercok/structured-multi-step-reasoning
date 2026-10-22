"""
rat.ui.reasoning_worker — Off-thread worker for MetaReasonerEngine execution.

Runs OnlineReasoningController off the Qt main thread. Binds callbacks to
execution ID and query generation, tracks multi-call budgets, supports
cooperative cancellation and deadline timeout, and preserves explicit boundaries
between strategy LLMBackend and selected-document QA sessions.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from rat.engine.meta_reasoner import MetaReasonerEngine, MetaReasoningResult

logger = logging.getLogger("rat.ui.reasoning_worker")


class OnlineReasoningWorker(QThread):
    """QThread worker executing MetaReasonerEngine off the main GUI thread."""

    progress_changed = pyqtSignal(str)
    step_completed = pyqtSignal(object)
    response_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str)  # "working", "done", "wait", "error", "cancel"

    def __init__(
        self,
        engine: MetaReasonerEngine,
        query: str,
        *,
        execution_id: Optional[str] = None,
        query_generation: Optional[int] = None,
        timeout_s: Optional[float] = None,
        document_path: Optional[str] = None,
        max_strategy_invocations: Optional[int] = None,
        max_underlying_requests: Optional[int] = None,
        max_generated_tokens: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.query = query
        self.execution_id = execution_id
        self.query_generation = query_generation
        self.timeout_s = timeout_s
        self.document_path = document_path
        self.max_strategy_invocations = max_strategy_invocations
        self.max_underlying_requests = max_underlying_requests
        self.max_generated_tokens = max_generated_tokens

    def run(self) -> None:
        started_t = time.monotonic()
        deadline = started_t + self.timeout_s if self.timeout_s is not None else None

        self.status_changed.emit("working")
        self.progress_changed.emit("Đang khởi tạo suy luận có kiểm soát...")

        initial_doc_hash = None
        initial_doc_mtime = None
        initial_doc_size = None

        # Guard: check if selected document was requested
        if self.document_path:
            # Explicit boundary verification: verify document existence and source
            p = Path(self.document_path)
            if not p.is_file():
                res = MetaReasoningResult(
                    query=self.query,
                    strategy="DOCUMENT_QA",
                    badge="Tài liệu",
                    answer="Tài liệu được chọn không tồn tại hoặc đã bị di chuyển.",
                    steps=["Tệp tài liệu không tồn tại trên máy."],
                    confidence=0.0,
                    tokens=0,
                    latency_ms=(time.monotonic() - started_t) * 1000,
                    escalated=False,
                    verification_status="unverified",
                    execution_mode="selected_document_qa",
                    strategy_path=[],
                    policy_source=None,
                    confidence_kind="not_estimated",
                    status="unresolved",
                    execution_id=self.execution_id,
                    query_generation=self.query_generation,
                )
                self.status_changed.emit("error")
                self.response_ready.emit(res)
                return
            try:
                st = p.stat()
                initial_doc_mtime = st.st_mtime_ns
                initial_doc_size = st.st_size
                initial_doc_hash = hashlib.sha256(p.read_bytes()).hexdigest()
                doc_text = p.read_text(encoding="utf-8", errors="replace")
                query_to_solve = f"{self.query}\n\n[Document Context: {p.name}]\n{doc_text}"
            except Exception as e:
                logger.warning(f"Failed to snapshot or read selected document: {e}")
                res = MetaReasoningResult(
                    query=self.query,
                    strategy="DOCUMENT_QA",
                    badge="Tài liệu",
                    answer=f"Không thể đọc tài liệu được chọn: {e}",
                    steps=["Lỗi khi truy cập nội dung tệp tài liệu."],
                    confidence=0.0,
                    tokens=0,
                    latency_ms=(time.monotonic() - started_t) * 1000,
                    escalated=False,
                    verification_status="unverified",
                    execution_mode="selected_document_qa",
                    strategy_path=[],
                    policy_source=None,
                    confidence_kind="not_estimated",
                    status="unresolved",
                    execution_id=self.execution_id,
                    query_generation=self.query_generation,
                )
                self.status_changed.emit("wait")
                self.response_ready.emit(res)
                return
        else:
            query_to_solve = self.query

        # Check early cancellation
        if self.isInterruptionRequested():
            self.status_changed.emit("cancel")
            res = MetaReasoningResult(
                query=self.query,
                strategy="NONE",
                badge="Cancelled",
                answer="",
                steps=["Hủy bỏ bởi người dùng trước khi thực thi."],
                confidence=0.0,
                tokens=0,
                latency_ms=(time.monotonic() - started_t) * 1000,
                escalated=False,
                verification_status="unverified",
                execution_mode="online_policy",
                strategy_path=[],
                policy_source=getattr(self.engine._controller, "policy_source", None),
                confidence_kind="not_estimated",
                status="cancelled",
                execution_id=self.execution_id,
                query_generation=self.query_generation,
            )
            self.response_ready.emit(res)
            return

        try:
            res = self.engine.solve(
                query_to_solve,
                execution_id=self.execution_id,
                query_generation=self.query_generation,
                deadline_monotonic=deadline,
                is_cancelled=self.isInterruptionRequested,
                max_strategy_invocations=self.max_strategy_invocations,
                max_underlying_requests=self.max_underlying_requests,
                max_generated_tokens=self.max_generated_tokens,
                on_step=self.step_completed.emit,
            )

            # Recheck document integrity after execution (unconditional content hash check)
            if self.document_path:
                p = Path(self.document_path)
                doc_changed = False
                if not p.is_file():
                    doc_changed = True
                else:
                    try:
                        current_hash = hashlib.sha256(p.read_bytes()).hexdigest()
                        if current_hash != initial_doc_hash:
                            doc_changed = True
                    except Exception:
                        doc_changed = True
                if doc_changed:
                    res.status = "unresolved"
                    res.confidence = 0.0
                    res.confidence_kind = "not_estimated"
                    res.verification_status = "unverified"
                    res.answer = "Tài liệu bị thay đổi trong quá trình xử lý; không thể đảm bảo tính nhất quán."
                    res.steps.append("Document changed during reasoning execution; marked unresolved.")

            if self.isInterruptionRequested() or res.status == "cancelled":
                self.status_changed.emit("cancel")
            elif res.status in ("timeout", "failed", "budget_exceeded"):
                self.status_changed.emit("error" if res.status == "failed" else "wait")
            elif res.status == "unresolved":
                self.status_changed.emit("wait")
            else:
                self.status_changed.emit("done")

            self.response_ready.emit(res)

        except Exception as exc:
            logger.warning(f"OnlineReasoningWorker exception: {exc}")
            cost_ledger = getattr(exc, "cost_ledger", None)

            if self.isInterruptionRequested() or (cost_ledger is not None and cost_ledger.status == "cancelled") or "cancel" in str(exc).lower():
                final_status = "cancelled"
                status_signal = "cancel"
                strategy_name = "CANCELLED"
                badge = "Đã hủy"
            elif isinstance(exc, TimeoutError) or (cost_ledger is not None and cost_ledger.status == "timeout") or "deadline" in str(exc).lower() or "timeout" in str(exc).lower():
                final_status = "timeout"
                status_signal = "wait"
                strategy_name = "TIMEOUT"
                badge = "Quá hạn"
            else:
                final_status = "error"
                status_signal = "error"
                strategy_name = "ERROR"
                badge = "Lỗi"

            self.status_changed.emit(status_signal)
            ledger_dict = (
                {
                    "strategy_invocations": cost_ledger.strategy_invocations,
                    "underlying_requests_dispatched": cost_ledger.underlying_requests_dispatched,
                    "underlying_requests_succeeded": cost_ledger.underlying_requests_succeeded,
                    "underlying_requests_failed": cost_ledger.underlying_requests_failed,
                    "generated_tokens": cost_ledger.generated_tokens,
                    "prompt_tokens": cost_ledger.prompt_tokens,
                    "status": cost_ledger.status,
                }
                if cost_ledger is not None
                else None
            )
            failed_res = MetaReasoningResult(
                query=self.query,
                strategy=strategy_name,
                badge=badge,
                answer="",
                steps=[f"Execution {final_status}: {exc}"],
                confidence=0.0,
                tokens=cost_ledger.generated_tokens if cost_ledger is not None else 0,
                latency_ms=(time.monotonic() - started_t) * 1000,
                escalated=False,
                verification_status="unverified",
                execution_mode="online_policy",
                strategy_path=[],
                policy_source=getattr(exc, "policy_source", getattr(self.engine._controller, "policy_source", None)),
                confidence_kind="not_estimated",
                status=final_status,
                execution_id=self.execution_id,
                query_generation=self.query_generation,
                bundle_id=getattr(exc, "bundle_id", getattr(self.engine._controller, "bundle_id", None)),
                cost_ledger=ledger_dict,
            )
            self.response_ready.emit(failed_res)
