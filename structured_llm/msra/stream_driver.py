"""Interactive Streaming Runtime Driver for MSRA.

Connects the language model generation stream with CapabilityRouter and EpistemicVerifier,
orchestrating decision gates, isolated helper invocations, and verification checks during inference.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from .router import CapabilityRouter
from .trace_parser import (
    extract_final_answer,
    parse_step,
    parse_var_dict,
)
from .types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    VerificationStatus,
)


class GeneratorBackend(Protocol):
    """Protocol for token generation backends (Mock, MLX, etc.)."""
    def generate_until(self, prompt: str, stop_sequences: List[str], max_new_tokens: int = 512) -> str:
        ...


class MockGeneratorBackend:
    """Mock generator for deterministic testing and validation."""
    def __init__(self, script: Dict[str, str]):
        self.script = script
        self.history: List[str] = []

    def generate_until(self, prompt: str, stop_sequences: List[str], max_new_tokens: int = 512) -> str:
        self.history.append(prompt)
        best_pos = -1
        best_response = None
        for pattern, response in self.script.items():
            pos = prompt.rfind(pattern)
            if pos > best_pos:
                best_pos = pos
                best_response = response

        if best_response is not None:
            # Find earliest stop sequence if present in canned response
            for stop in stop_sequences:
                if stop in best_response:
                    idx = best_response.index(stop) + len(stop)
                    return best_response[:idx]
            return best_response

        # Default fallback
        return "<final_answer>0</final_answer>"



class MSRAStepDriver:
    """Drives step-by-step reasoning with interactive help-seeking and verification."""

    def __init__(self, backend: GeneratorBackend, router: CapabilityRouter):
        self.backend = backend
        self.router = router

    def solve(
        self,
        problem: str,
        initial_budget: float = 2.0,
        max_steps: int = 8,
        system_instruction: str = "",
    ) -> Dict[str, Any]:
        """Execute the interactive metacognitive reasoning process on a problem."""
        is_mock = isinstance(self.backend, MockGeneratorBackend)
        if is_mock:
            context = f"{system_instruction}\n" if system_instruction else ""
            context += f"<problem>{problem}</problem>\n\n"
        else:
            user_content = f"{system_instruction}\n{problem}" if system_instruction else problem
            context = f"<|im_start|>user\n{user_content}<|im_end|>\n<|im_start|>assistant\n<think>\n"

        nodes: List[ReasoningNode] = []
        committed_vars: Dict[str, str] = {}
        total_cost = 0.0
        remaining_budget = initial_budget

        for step_idx in range(1, max_steps + 1):
            remaining_budget = max(0.0, initial_budget - total_cost)
            if is_mock or step_idx == 1:
                step_header = f'<step id="{step_idx}" budget_remaining="{remaining_budget:.2f}">\n'
            else:
                step_header = ""
            current_step_text = step_header

            # 1. Generate subgoal, capability, and decision (or closing think/final_answer)
            chunk_decision = self.backend.generate_until(
                context + current_step_text,
                stop_sequences=["</decision>", "<final_answer>", "</think>"],
                max_new_tokens=256,
            )

            if "</think>" in chunk_decision:
                context += current_step_text + chunk_decision
                ans_rest = self.backend.generate_until(
                    context,
                    stop_sequences=["<|im_end|>", "</final_answer>"],
                    max_new_tokens=64,
                )
                context += ans_rest
                break

            if "<final_answer>" in chunk_decision:
                context += current_step_text + chunk_decision
                if "</final_answer>" not in chunk_decision:
                    ans_rest = self.backend.generate_until(
                        context,
                        stop_sequences=["</final_answer>"],
                        max_new_tokens=64,
                    )
                    context += ans_rest
                    if "</final_answer>" not in context:
                        context += "</final_answer>"
                break

            current_step_text += chunk_decision

            # Parse capability and decision
            cap_m = re.search(r"<capability>(.*?)</capability>", chunk_decision, re.DOTALL)
            dec_m = re.search(r"<decision>(.*?)</decision>", chunk_decision, re.DOTALL)
            cap_str = cap_m.group(1).strip() if cap_m else "CAP:DECOMPOSE"
            dec_str = dec_m.group(1).strip() if dec_m else "SOLVE_LOCAL"

            try:
                capability = CapabilityTag(cap_str)
            except ValueError:
                capability = CapabilityTag.DECOMPOSE

            is_ask_help = "ASK_HELP" in dec_str

            # 2. If ASK_HELP, elicit query_payload and dispatch to CapabilityRouter
            if is_ask_help:
                if "</query_payload>" not in current_step_text:
                    chunk_query = self.backend.generate_until(
                        context + current_step_text,
                        stop_sequences=["</query_payload>"],
                        max_new_tokens=256,
                    )
                    current_step_text += chunk_query

                q_m = re.search(r"<query_payload>(.*?)</query_payload>", current_step_text, re.DOTALL)
                query_payload = q_m.group(1).strip() if q_m else ""

                # Dispatch isolated query to helper
                helper_out, cost, helper_source = self.router.dispatch(capability, query_payload, remaining_budget)
                total_cost += cost
                remaining_budget = max(0.0, initial_budget - total_cost)

                current_step_text += f'\n  <helper_response source="{helper_source}">{helper_out}</helper_response>\n'

            # 3. Generate verification and output_var to close step
            chunk_closing = self.backend.generate_until(
                context + current_step_text,
                stop_sequences=["</step>"],
                max_new_tokens=256,
            )
            current_step_text += chunk_closing
            if not current_step_text.endswith("</step>"):
                current_step_text += "\n</step>"

            context += current_step_text + "\n\n"

            # Extract step body if step_header was generated inside current_step_text
            m_step_body = re.search(r"<step[^>]*>(.*?)</step>", current_step_text, re.DOTALL)
            body_for_parse = m_step_body.group(1) if m_step_body else current_step_text
            node, errs = parse_step(str(step_idx), body_for_parse, str(remaining_budget))
            if node:
                nodes.append(node)
                if node.verification_status == VerificationStatus.COMMIT:
                    for k, v in node.output_var.items():
                        committed_vars[k] = v

            if "<final_answer>" in context or "</think>" in context:
                break

        # If final answer not yet emitted, request final answer
        if "<final_answer>" not in context and "Answer:" not in context:
            if is_mock:
                final_chunk = self.backend.generate_until(
                    context + "<final_answer>",
                    stop_sequences=["</final_answer>"],
                    max_new_tokens=64,
                )
                if "</final_answer>" not in final_chunk:
                    final_chunk += "</final_answer>"
                context += "<final_answer>" + final_chunk
            else:
                if "</think>" not in context:
                    context += "</think>\n\nAnswer: "
                else:
                    context += "\n\nAnswer: "
                final_chunk = self.backend.generate_until(
                    context,
                    stop_sequences=["<|im_end|>", "\n"],
                    max_new_tokens=64,
                )
                context += final_chunk

        final_ans = extract_final_answer(context)

        return {
            "trace": context,
            "nodes": nodes,
            "committed_vars": committed_vars,
            "total_cost": total_cost,
            "budget_remaining": max(0.0, initial_budget - total_cost),
            "final_answer": final_ans,
        }
