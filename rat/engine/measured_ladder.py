"""Run the policy fitted in the GSM8K development study, step by step, for the demo.

The rule and thresholds below come from
runs/gsm8k-qwen3-8b-full-policy-reviewed93-palfix-20261101/policy_fit.json, fitted
on 45 train questions. This is development evidence, not a held-out result.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Callable, Optional

from reasoning.reasoning_env import ReasoningAction as A
from research_scoring import parse_typed_answer, repair_float_artifact

ENTRY_CUTOFF_WORDS = 80
TAU_DIRECT = 0.9962735591063407
TAU_COT = 0.9794315415816602

MODE_POLICY = "policy"
MODE_LADDER = "ladder"
MODE_COMPARE = "compare"
MODES = (MODE_POLICY, MODE_LADDER, MODE_COMPARE)

STRATEGY_LABELS = {"DIRECT": "Trả lời thẳng", "COT": "Suy luận từng bước", "PAL": "Viết code để tính"}


@dataclass
class LabStep:
    strategy: str
    answer: str
    confidence: float
    tokens: int
    prompt_tokens: int
    seconds: float
    text: str = ""
    code: str = ""
    tool_output: str = ""
    tool_ok: Optional[bool] = None
    decision: str = ""


@dataclass
class LabRun:
    question: str
    mode: str
    reason: str = ""
    steps: list[LabStep] = field(default_factory=list)
    final_strategy: str = ""
    final_answer: str = ""
    status: str = "completed"
    seconds: float = 0.0

    @property
    def path(self) -> list[str]:
        return [step.strategy for step in self.steps]

    @property
    def tokens(self) -> int:
        return sum(step.tokens for step in self.steps)

    @property
    def prompt_tokens(self) -> int:
        return sum(step.prompt_tokens for step in self.steps)


def entry_reason(question: str) -> tuple[str, str]:
    """Return the first strategy and the measured rule that picked it."""
    words = len(question.split())
    if words <= ENTRY_CUTOFF_WORDS:
        return "PAL", f"Đề có {words} từ, không quá {ENTRY_CUTOFF_WORDS} từ, nên đi thẳng tới viết code."
    return "DIRECT", f"Đề có {words} từ, dài hơn {ENTRY_CUTOFF_WORDS} từ, nên bắt đầu bằng trả lời thẳng."


def _run_step(backend: Any, strategy: str, question: str, should_cancel) -> LabStep:
    started = time.monotonic()
    answer, confidence, tokens = backend.run(A[strategy], question, should_cancel=should_cancel)
    trace = getattr(backend, "last_trace", None) or {}
    generations = trace.get("generations") or [{}]
    tools = trace.get("tools") or []
    step = LabStep(strategy=strategy, answer=answer, confidence=float(confidence), tokens=int(tokens),
                   prompt_tokens=sum(int(row.get("prompt_tokens") or 0) for row in generations),
                   seconds=time.monotonic() - started, text=str(generations[-1].get("output") or ""))
    if tools:
        tool = tools[-1]
        step.code = str(tool.get("input") or "")
        step.tool_output = str(tool.get("output") or "")
        step.tool_ok = bool(tool.get("ok"))
        if step.tool_ok:
            repaired = repair_float_artifact(step.tool_output)
            step.answer = parse_typed_answer(f"Answer: {repaired}", "number")[0]
    return step


def _stop_decision(step: LabStep, tau: float) -> bool:
    stop = step.confidence >= tau
    verb = "dừng ở đây" if stop else "chạy thêm"
    sign = "≥" if stop else "<"
    step.decision = f"Độ tin cậy {step.confidence:.4f} {sign} ngưỡng {tau:.4f} nên {verb}."
    return stop


def solve(backend: Any, question: str, mode: str = MODE_POLICY, *,
          on_step: Optional[Callable[[LabRun], None]] = None,
          on_start: Optional[Callable[[str], None]] = None,
          should_cancel: Optional[Callable[[], bool]] = None) -> LabRun:
    """Execute one mode for real. A cancelled or failed run keeps its finished steps."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode: {mode}")
    question = question.strip()
    if not question:
        raise ValueError("A nonempty question is required")
    run = LabRun(question=question, mode=mode)
    started = time.monotonic()

    def execute(strategy: str) -> LabStep:
        if on_start:
            on_start(strategy)
        step = _run_step(backend, strategy, question, should_cancel)
        run.steps.append(step)
        return step

    try:
        if mode == MODE_COMPARE:
            run.reason = "Chạy cả ba cách trên cùng câu hỏi để so sánh. Không chọn cách nào."
            for strategy in ("DIRECT", "COT", "PAL"):
                execute(strategy)
                if on_step:
                    on_step(run)
        else:
            first = "DIRECT"
            if mode == MODE_LADDER:
                run.reason = "Luôn bắt đầu từ cách rẻ nhất, chỉ chạy thêm khi độ tin cậy dưới ngưỡng."
            else:
                first, run.reason = entry_reason(question)
            if first == "PAL":
                execute("PAL").decision = "Viết code là bậc cuối, không chạy thêm."
            else:
                for strategy, tau in (("DIRECT", TAU_DIRECT), ("COT", TAU_COT), ("PAL", None)):
                    step = execute(strategy)
                    stopped = tau is None or _stop_decision(step, tau)
                    if tau is None:
                        step.decision = "Viết code là bậc cuối, không chạy thêm."
                    if on_step:
                        on_step(run)
                    if stopped:
                        break
            if on_step:
                on_step(run)
    except Exception as exc:
        cancelled = bool(should_cancel and should_cancel()) or "cancel" in str(exc).lower()
        run.status = "cancelled" if cancelled else "failed"
        run.reason = "Đã dừng theo yêu cầu." if cancelled else f"Không chạy xong: {type(exc).__name__}: {exc}"
    if run.steps and mode != MODE_COMPARE:
        run.final_strategy = run.steps[-1].strategy
        run.final_answer = run.steps[-1].answer
    run.seconds = time.monotonic() - started
    return run


def append_log(run: LabRun, path: Path, *, model_id: str = "") -> None:
    """Append one JSON line with the question, every step and its measured cost."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model_id": model_id,
           **asdict(run), "path": run.path, "tokens": run.tokens, "prompt_tokens": run.prompt_tokens}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
