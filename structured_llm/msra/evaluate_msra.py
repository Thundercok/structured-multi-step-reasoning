"""Evaluation harness for MSRA Structured Reasoning Agent.

Evaluates trained models and prompt baselines on MSRA XML DAG traces,
measuring XML validity, DAG dependency compliance, tool dispatch efficacy,
budget consumption, and final answer correctness.

Run:
    python -m structured_llm.msra.evaluate_msra --data data/structured_msra_coldstart_v1/valid.jsonl --limit 20
"""

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .router import CapabilityRouter
from .sandbox import SymPySandbox
from .stream_driver import GeneratorBackend, MockGeneratorBackend, MSRAStepDriver
from .trace_parser import (
    extract_final_answer,
    parse_step,
    parse_trace,
)
from .types import CapabilityTag, Decision, ReasoningNode, VerificationStatus

EXEMPLAR_PROMPT = """Solve the following problem step by step inside <think></think> using MSRA XML DAG format with explicit subgoals, dependency variables, capability tags, and verification. Then give the final answer.

Question: Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
<think>
<step id="1" budget_remaining="2.00">
  <subgoal>Calculate clips sold in May</subgoal>
  <deps>None</deps>
  <capability>CAP:SYMBOLIC_CALC</capability>
  <decision>SOLVE_LOCAL</decision>
  <execution>48 / 2 = 24</execution>
  <verification status="COMMIT">Verified exact half</verification>
  <output_var>v1 = 24</output_var>
</step>

<step id="2" budget_remaining="2.00">
  <subgoal>Calculate total clips sold altogether</subgoal>
  <deps>v1 = 24</deps>
  <capability>CAP:SYMBOLIC_CALC</capability>
  <decision>SOLVE_LOCAL</decision>
  <execution>48 + 24 = 72</execution>
  <verification status="COMMIT">Verified exact sum</verification>
  <output_var>v2 = 72</output_var>
</step>
</think>

<final_answer>72</final_answer>

Question: """


def wilson_interval(successes: int, total: int, z: float = 1.95996) -> Tuple[float, float]:
    """Compute 95% Wilson score confidence interval."""
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + (z**2) / total
    centre = (p + (z**2) / (2 * total)) / denom
    spread = (z * math.sqrt((p * (1 - p) + (z**2) / (4 * total)) / total)) / denom
    return round(max(0.0, centre - spread) * 100, 1), round(min(1.0, centre + spread) * 100, 1)


def score_trace(output_text: str, gold_answer: str) -> Dict[str, Any]:
    """Score a generated MSRA trace for formatting, DAG invariants, and correctness."""
    parsed = parse_trace(output_text)
    final_ans = extract_final_answer(output_text)

    # Basic numeric/string matching
    is_correct = False
    if final_ans is not None and gold_answer is not None:
        try:
            val_found = float(final_ans.replace(",", ""))
            val_gold = float(gold_answer.replace(",", ""))
            is_correct = abs(val_found - val_gold) < 1e-6
        except ValueError:
            is_correct = final_ans.strip().lower() == gold_answer.strip().lower()

    # Calculate dependency metrics
    total_steps = len(parsed.nodes)
    deps_counts = [len(n.deps) for n in parsed.nodes]
    mean_deps = sum(deps_counts) / max(1, total_steps)

    has_help = any(n.decision == Decision.ASK_HELP for n in parsed.nodes)

    return {
        "xml_valid": parsed.is_valid,
        "dag_valid": parsed.is_valid and len(parsed.errors) == 0,
        "errors": parsed.errors,
        "num_steps": total_steps,
        "mean_deps": round(mean_deps, 2),
        "has_help": has_help,
        "final_answer": final_ans,
        "gold_answer": gold_answer,
        "correct": is_correct,
    }


def evaluate_records(
    records: List[Dict[str, Any]],
    driver: MSRAStepDriver,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Evaluate a collection of benchmark problems through the MSRA driver."""
    eval_count = len(records) if limit is None else min(len(records), limit)
    results = []

    xml_valid_cnt = 0
    dag_valid_cnt = 0
    correct_cnt = 0
    total_cost = 0.0
    total_steps = 0
    helper_calls = 0

    for idx, row in enumerate(records[:eval_count], start=1):
        # Extract problem text and gold answer from ChatML or fields
        text = row.get("text", "")
        gold_ans = row.get("gold") or row.get("answer")

        m_user = re.search(r"<\|im_start\|>user\n(.*?)(?:<\|im_end\|>|$)", text, re.DOTALL)
        problem_prompt = m_user.group(1).strip() if m_user else (row.get("question") or row.get("problem", text))

        if not gold_ans:
            m_ans = re.search(r"(?:Answer:|<final_answer>)\s*([^\s<]+)", text)
            gold_ans = m_ans.group(1).strip() if m_ans else "0"

        # Run driver
        start_t = time.perf_counter()
        solve_res = driver.solve(problem_prompt)
        dur = time.perf_counter() - start_t

        trace_text = solve_res["trace"]
        metrics = score_trace(trace_text, gold_ans)
        metrics["problem_id"] = row.get("id", f"item_{idx}")
        metrics["duration_seconds"] = round(dur, 2)
        metrics["cost"] = solve_res.get("total_cost", 0.0)
        results.append(metrics)

        if metrics["xml_valid"]:
            xml_valid_cnt += 1
        if metrics["dag_valid"]:
            dag_valid_cnt += 1
        if metrics["correct"]:
            correct_cnt += 1
        total_cost += solve_res.get("total_cost", 0.0)
        total_steps += metrics["num_steps"]
        if metrics["has_help"]:
            helper_calls += 1

    n = max(1, len(results))
    acc_ci = wilson_interval(correct_cnt, n)
    xml_ci = wilson_interval(xml_valid_cnt, n)

    summary = {
        "evaluated_problems": len(results),
        "accuracy": round(correct_cnt / n * 100, 2),
        "accuracy_wilson_95": list(acc_ci),
        "xml_valid_rate": round(xml_valid_cnt / n * 100, 2),
        "xml_valid_wilson_95": list(xml_ci),
        "dag_valid_rate": round(dag_valid_cnt / n * 100, 2),
        "mean_steps": round(total_steps / n, 2),
        "mean_cost_per_problem": round(total_cost / n, 3),
        "helper_call_rate": round(helper_calls / n * 100, 2),
        "items": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/structured_msra_coldstart_v1/valid.jsonl", help="Dataset to evaluate")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of evaluation problems")
    parser.add_argument("--adapter", default=None, help="Path to LoRA adapter directory (optional)")
    parser.add_argument("--model", default="mlx-community/Qwen3-8B-4bit", help="Base model identifier")
    parser.add_argument("--out", default=None, help="Path to write evaluation JSON output")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: dataset {data_path} not found.")
        sys.exit(1)

    records = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Setup default router and sandbox
    router = CapabilityRouter()
    sandbox = SymPySandbox()
    router.register_helper(
        CapabilityTag.SYMBOLIC_CALC,
        lambda q: sandbox.execute_algebraic_query(q)["result"],
        cost=0.1,
        source_id="h_sym",
    )

    if args.adapter:
        from .mlx_backend import MLXGeneratorBackend
        backend = MLXGeneratorBackend(model_path=args.model, adapter_path=args.adapter)
    else:
        # Use mock backend for verification/testing if no live adapter specified
        backend = MockGeneratorBackend({
            "<step id=\"1\"": (
                "  <subgoal>Evaluate step 1</subgoal>\n"
                "  <deps>None</deps>\n"
                "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
                "  <decision>SOLVE_LOCAL</decision>\n"
                "  <execution>1 + 1 = 2</execution>\n"
                "  <verification status=\"COMMIT\">Exact</verification>\n"
                "  <output_var>v1 = 2</output_var>\n"
                "</step>"
            ),
            "<step id=\"2\"": "<final_answer>2</final_answer>",
            "<final_answer>": "2</final_answer>",
        })

    driver = MSRAStepDriver(backend=backend, router=router)
    summary = evaluate_records(records, driver, limit=args.limit)

    output_json = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output_json + "\n", encoding="utf-8")
        print(f"Results written to {args.out}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
