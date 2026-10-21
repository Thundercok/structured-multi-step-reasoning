"""
rat.engine.reasoning_trace — Structured Chain-of-Thought (CoT) trace model for FR-CoT.
Records the multi-step reasoning progression: Thought -> Action -> Observation -> Evaluation.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReasoningStep:
    """A single atomic reasoning step in the retrieval Chain-of-Thought."""
    step_id: int
    phase: str          # "decompose" | "retrieve" | "evaluate" | "correct" | "rerank" | "synthesize"
    thought: str        # Explanation of reasoning at this step
    action: str         # The concrete operation or query dispatched
    observation: str    # Summary of empirical evidence or candidates found
    evaluation: str     # Assessment of adequacy, confidence, or match quality
    latency_ms: float   # Execution time of this step in milliseconds


@dataclass
class ReasoningTrace:
    """The complete transparent execution trace of an FR-CoT search query."""
    raw_query: str = ""
    steps: List[ReasoningStep] = field(default_factory=list)
    total_latency_ms: float = 0.0
    final_confidence: float = 0.0
    correction_count: int = 0
    is_sufficient: bool = True
    start_time: float = field(default_factory=time.time)

    def add_step(
        self,
        phase: str,
        thought: str,
        action: str,
        observation: str,
        evaluation: str,
        latency_ms: float,
    ) -> ReasoningStep:
        step_id = len(self.steps) + 1
        step = ReasoningStep(
            step_id=step_id,
            phase=phase,
            thought=thought,
            action=action,
            observation=observation,
            evaluation=evaluation,
            latency_ms=round(latency_ms, 2),
        )
        self.steps.append(step)
        return step

    def finalize(self, confidence: float, is_sufficient: bool, correction_count: int = 0) -> None:
        self.final_confidence = round(confidence, 3)
        self.is_sufficient = is_sufficient
        self.correction_count = correction_count
        self.total_latency_ms = round((time.time() - self.start_time) * 1000.0, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "total_latency_ms": self.total_latency_ms,
            "final_confidence": self.final_confidence,
            "is_sufficient": self.is_sufficient,
            "correction_count": self.correction_count,
            "total_steps": len(self.steps),
            "steps": [asdict(s) for s in self.steps],
        }

    def render_markdown(self) -> str:
        """Render readable markdown representation of the reasoning trace."""
        lines = [
            f"### 🧠 FR-CoT Reasoning Trace (`{self.total_latency_ms}ms`, Confidence: `{self.final_confidence*100:.0f}%`)",
            f"**Query**: *\"{self.raw_query}\"* | **Corrections**: `{self.correction_count}` | **Status**: `{'✅ SUFFICIENT' if self.is_sufficient else '⚠️ PARTIAL'}`",
            "",
        ]
        for s in self.steps:
            icon_map = {
                "decompose": "🔍 [Phase 1: Phân Rã Truy Vấn]",
                "retrieve": "⚡ [Phase 2: Truy Xuất Đa Tầng]",
                "evaluate": "🎯 [Phase 3: Đánh Giá Đủ Điều Kiện]",
                "correct": "🛠️ [Phase 4: Tự Động Sửa Lỗi]",
                "rerank": "📊 [Phase 5: Tái Xếp Hạng & Bằng Chứng]",
                "synthesize": "💬 [Phase 6: Tổng Hợp Tri Thức]",
            }
            header = icon_map.get(s.phase, f"🔹 [{s.phase.upper()}]")
            lines.append(f"**Step {s.step_id}**: {header} — *{s.latency_ms}ms*")
            lines.append(f"- **Thought**: {s.thought}")
            lines.append(f"- **Action**: `{s.action}`")
            lines.append(f"- **Observation**: {s.observation}")
            lines.append(f"- **Evaluation**: {s.evaluation}")
            lines.append("")

        return "\n".join(lines)
