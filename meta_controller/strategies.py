"""
meta_controller.strategies — Execution Engines for the 5 Reasoning Strategies.
Includes Chain-of-Thought (CoT), Self-Consistency (SC), Tree-of-Thoughts (ToT),
ReAct (Tool-augmented), and Program-Aided Language (PAL with Python sandbox).
"""

from __future__ import annotations

import io
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from meta_controller.actions import ACTION_BASE_COSTS, ReasoningAction
from meta_controller.backend import BaseReasoningBackend, GenerationResult

logger = logging.getLogger(__name__)


@dataclass
class StrategyExecutionResult:
    action: ReasoningAction
    answer: str
    confidence: float
    entropy: float
    compute_cost: float
    raw_trace: str
    intermediate_steps: List[str]


class StrategyExecutor:
    """Executes the specific reasoning strategy selected by the Meta-Controller."""

    def __init__(self, backend: BaseReasoningBackend, tools: Optional[Dict[str, Callable[[str], str]]] = None) -> None:
        self.backend = backend
        self.tools = tools or self._default_tools()

    def _default_tools(self) -> Dict[str, Callable[[str], str]]:
        def python_eval(expr: str) -> str:
            try:
                # Safe basic arithmetic evaluation
                allowed = set("0123456789+-*/(). %")
                cleaned = "".join(c for c in expr if c in allowed)
                return str(eval(cleaned, {"__builtins__": None}, {}))
            except Exception as e:
                return f"Error: {e}"

        return {"python": python_eval}

    def execute(self, action: ReasoningAction, query: str, context: str = "") -> StrategyExecutionResult:
        if action == ReasoningAction.COT:
            return self._execute_cot(query, context)
        elif action == ReasoningAction.SELF_CONSISTENCY:
            return self._execute_self_consistency(query, context, k=3)
        elif action == ReasoningAction.TOT:
            return self._execute_tot(query, context, branches=3)
        elif action == ReasoningAction.REACT:
            return self._execute_react(query, context)
        elif action == ReasoningAction.PAL:
            return self._execute_pal(query, context)
        elif action == ReasoningAction.ESCALATE:
            # Escalation runs Self-Consistency with broader search
            res = self._execute_self_consistency(query, context, k=5)
            res.action = ReasoningAction.ESCALATE
            res.compute_cost += ACTION_BASE_COSTS[ReasoningAction.ESCALATE]
            return res
        elif action == ReasoningAction.STOP:
            return StrategyExecutionResult(
                action=ReasoningAction.STOP,
                answer=context,
                confidence=1.0,
                entropy=0.0,
                compute_cost=0.0,
                raw_trace="[STOP] Terminated by Meta-Controller.",
                intermediate_steps=[],
            )
        else:
            raise ValueError(f"Unknown reasoning action: {action}")

    # --- 1. Chain of Thought (CoT) ---
    def _execute_cot(self, query: str, context: str) -> StrategyExecutionResult:
        prompt = (
            f"Hãy suy luận từng bước một cách cẩn thận để giải quyết vấn đề sau:\n"
            f"Vấn đề: {query}\n"
            f"Ngữ cảnh hiện tại: {context}\n"
            f"Suy luận từng bước:"
        )
        gen = self.backend.generate(prompt, temperature=0.2, max_tokens=384)
        return StrategyExecutionResult(
            action=ReasoningAction.COT,
            answer=gen.text.strip(),
            confidence=gen.confidence,
            entropy=gen.entropy,
            compute_cost=ACTION_BASE_COSTS[ReasoningAction.COT],
            raw_trace=gen.text,
            intermediate_steps=[gen.text],
        )

    # --- 2. Self-Consistency (SC) ---
    def _execute_self_consistency(self, query: str, context: str, k: int = 3) -> StrategyExecutionResult:
        prompt = (
            f"Giải quyết câu hỏi sau bằng cách suy nghĩ độc lập:\n"
            f"Câu hỏi: {query}\n"
            f"Trả lời:"
        )
        candidates: List[GenerationResult] = []
        for _ in range(k):
            candidates.append(self.backend.generate(prompt, temperature=0.7, max_tokens=256))

        answers = [c.text.strip() for c in candidates]
        # Approximate majority vote or highest confidence
        best_cand = max(candidates, key=lambda c: c.confidence)
        avg_ent = sum(c.entropy for c in candidates) / len(candidates)
        # Agreement bonus to confidence
        agreement_ratio = answers.count(best_cand.text.strip()) / k
        adjusted_conf = min(best_cand.confidence * 0.7 + agreement_ratio * 0.3, 1.0)

        return StrategyExecutionResult(
            action=ReasoningAction.SELF_CONSISTENCY,
            answer=best_cand.text.strip(),
            confidence=adjusted_conf,
            entropy=avg_ent,
            compute_cost=ACTION_BASE_COSTS[ReasoningAction.SELF_CONSISTENCY],
            raw_trace="\n---\n".join(answers),
            intermediate_steps=answers,
        )

    # --- 3. Tree of Thoughts (ToT) ---
    def _execute_tot(self, query: str, context: str, branches: int = 3) -> StrategyExecutionResult:
        # Step 1: Propose candidate thoughts
        prop_prompt = (
            f"Đề xuất {branches} hướng tiếp cận khác nhau để giải quyết câu hỏi:\n"
            f"Câu hỏi: {query}\n"
            f"Các hướng tiếp cận:"
        )
        gen_branches = self.backend.generate(prop_prompt, temperature=0.6, max_tokens=300)

        # Step 2: Evaluate and select best branch
        eval_prompt = (
            f"Đánh giá và chọn ra hướng tiếp cận logic và chính xác nhất cho câu hỏi '{query}':\n"
            f"Các nhánh:\n{gen_branches.text}\n"
            f"Kết luận hướng đi tốt nhất và lời giải hoàn chỉnh:"
        )
        gen_eval = self.backend.generate(eval_prompt, temperature=0.2, max_tokens=400)

        combined_conf = (gen_branches.confidence + gen_eval.confidence) / 2.0
        return StrategyExecutionResult(
            action=ReasoningAction.TOT,
            answer=gen_eval.text.strip(),
            confidence=combined_conf,
            entropy=gen_eval.entropy,
            compute_cost=ACTION_BASE_COSTS[ReasoningAction.TOT],
            raw_trace=f"Branches:\n{gen_branches.text}\n\nEvaluation:\n{gen_eval.text}",
            intermediate_steps=[gen_branches.text, gen_eval.text],
        )

    # --- 4. ReAct (Reason + Act) ---
    def _execute_react(self, query: str, context: str) -> StrategyExecutionResult:
        prompt = (
            f"Sử dụng công cụ phù hợp để tìm câu trả lời.\n"
            f"Câu hỏi: {query}\n"
            f"Thought: Suy nghĩ bước tiếp theo\n"
            f"Action: python(biểu thức toán nếu có)\n"
        )
        gen_thought = self.backend.generate(prompt, temperature=0.3, max_tokens=256)

        # Tool execution check
        match = re.search(r"Action:\s*python\((.*?)\)", gen_thought.text, re.IGNORECASE)
        observation = ""
        if match:
            expr = match.group(1)
            tool_fn = self.tools.get("python")
            if tool_fn:
                observation = tool_fn(expr)

        final_prompt = (
            f"{prompt}\n{gen_thought.text}\n"
            f"Observation: {observation}\n"
            f"Final Answer:"
        )
        gen_final = self.backend.generate(final_prompt, temperature=0.2, max_tokens=256)

        return StrategyExecutionResult(
            action=ReasoningAction.REACT,
            answer=gen_final.text.strip(),
            confidence=max(gen_final.confidence, 0.85 if observation else 0.6),
            entropy=gen_final.entropy,
            compute_cost=ACTION_BASE_COSTS[ReasoningAction.REACT],
            raw_trace=f"{gen_thought.text}\nObs: {observation}\n{gen_final.text}",
            intermediate_steps=[gen_thought.text, f"Obs: {observation}", gen_final.text],
        )

    # --- 5. Program-Aided Language (PAL) ---
    def _execute_pal(self, query: str, context: str) -> StrategyExecutionResult:
        prompt = (
            f"Viết một đoạn code Python ngắn để tính toán và giải quyết chính xác câu hỏi sau.\n"
            f"Định dạng code trong khối ```python ... ``` và gán kết quả cuối cùng vào biến `result` hoặc in ra bằng print().\n"
            f"Câu hỏi: {query}\n"
            f"Code Python:"
        )
        gen = self.backend.generate(prompt, temperature=0.1, max_tokens=300)

        # Extract code block
        code_match = re.search(r"```python(.*?)```", gen.text, re.DOTALL)
        code = code_match.group(1).strip() if code_match else gen.text.strip()

        # Run safely in isolated scope
        captured_output = io.StringIO()
        exec_scope: Dict[str, Any] = {}
        old_stdout = sys.stdout
        exec_success = False

        try:
            sys.stdout = captured_output
            exec(code, {"__builtins__": {"print": print, "range": range, "len": len, "sum": sum, "min": min, "max": max, "abs": abs}}, exec_scope)
            exec_success = True
        except Exception as e:
            exec_output = f"Execution error: {e}"
        finally:
            sys.stdout = old_stdout

        if exec_success:
            val = exec_scope.get("result", captured_output.getvalue().strip())
            exec_output = f"Kết quả từ chương trình: {val}"
            conf = 0.98  # Very high confidence when program successfully runs
            ent = 0.05
        else:
            exec_output = f"Không thể thực thi code: {gen.text[:100]}"
            conf = 0.40
            ent = 1.20

        return StrategyExecutionResult(
            action=ReasoningAction.PAL,
            answer=exec_output,
            confidence=conf,
            entropy=ent,
            compute_cost=ACTION_BASE_COSTS[ReasoningAction.PAL],
            raw_trace=f"Generated Code:\n{code}\nOutput: {exec_output}",
            intermediate_steps=[code, exec_output],
        )
