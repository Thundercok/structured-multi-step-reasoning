"""Counterfactual Intervention Engine for MSRA Graph Reasoning Traces.

Tests causal dependency and epistemic vigilance by perturbing intermediate
output variables and evaluating downstream model behavior:
- follows: downstream steps condition on the perturbed variable.
- reverted: downstream steps ignore the perturbed variable and restore original answer.
- rejected_at_verification: Phase 2 epistemic verifier catches the anomaly and emits REJECT.
- other / no_answer: diverging path or incomplete generation.
"""

import collections
import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from .trace_parser import extract_final_answer, parse_step, parse_trace
from .types import CapabilityTag, Decision, ReasoningNode, VerificationStatus


def find_eligible_intervention_step(nodes: List[ReasoningNode]) -> Optional[Tuple[int, str, float]]:
    """Find the earliest intermediate step whose output_var is consumed by a subsequent step."""
    if len(nodes) < 2:
        return None

    # Check each step t < K
    for t_idx in range(len(nodes) - 1):
        node = nodes[t_idx]
        for var_name, var_val_str in node.output_var.items():
            # Check if var_name is in deps of any subsequent node
            consumed_later = any(
                var_name in later_node.deps
                for later_node in nodes[t_idx + 1 :]
            )
            if consumed_later:
                try:
                    val = float(var_val_str)
                    return (node.step_id, var_name, val)
                except ValueError:
                    continue
    return None


def plan_msra_intervention(
    chatml_or_xml: str,
    key: Any = 0,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Plan an intermediate variable perturbation on an MSRA trace."""
    parsed = parse_trace(chatml_or_xml)
    if not parsed.is_valid or len(parsed.nodes) < 2:
        return None, "invalid_or_insufficient_steps"

    eligible = find_eligible_intervention_step(parsed.nodes)
    if not eligible:
        return None, "no_variable_consumed_later"

    step_id, var_name, orig_val = eligible

    # Generate a deterministic perturbed value
    digest = int(hashlib.sha256(f"{key}_{var_name}_{orig_val}".encode()).hexdigest(), 16)
    delta = (digest % 5 + 1) * (2 if orig_val >= 10 else 1)
    perturbed_val = orig_val + delta

    # Extract original answer
    orig_answer_str = extract_final_answer(chatml_or_xml)
    orig_answer = float(orig_answer_str) if orig_answer_str and re.match(r"^-?\d+(?:\.\d+)?$", orig_answer_str) else None

    # Construct the intervention prefix up to step_id
    # Replace step_id's output_var with perturbed_val
    prefix_nodes: List[ReasoningNode] = []
    for node in parsed.nodes:
        if node.step_id < step_id:
            prefix_nodes.append(node)
        elif node.step_id == step_id:
            # Perturbed node
            new_out = dict(node.output_var)
            new_out[var_name] = str(int(perturbed_val) if perturbed_val.is_integer() else perturbed_val)
            mod_node = ReasoningNode(
                step_id=node.step_id,
                subgoal=node.subgoal,
                capability_tag=node.capability_tag,
                decision=node.decision,
                deps=node.deps,
                query_payload=node.query_payload,
                execution_result=node.execution_result,
                verification_status=node.verification_status,
                critique=node.critique,
                output_var=new_out,
                helper_source=node.helper_source,
                cost=node.cost,
            )
            prefix_nodes.append(mod_node)
            break

    # Build XML prefix string
    xml_steps = []
    for p_node in prefix_nodes:
        deps_str = ", ".join(f"{k} = {v}" for k, v in p_node.deps.items()) if p_node.deps else "None"
        out_str = ", ".join(f"{k} = {v}" for k, v in p_node.output_var.items()) if p_node.output_var else "None"
        xml_steps.append(
            f'<step id="{p_node.step_id}" budget_remaining="2.00">\n'
            f"  <subgoal>{p_node.subgoal}</subgoal>\n"
            f"  <deps>{deps_str}</deps>\n"
            f"  <capability>{p_node.capability_tag.value}</capability>\n"
            f"  <decision>{p_node.decision.value}</decision>\n"
            f"  <execution>{p_node.execution_result}</execution>\n"
            f'  <verification status="{p_node.verification_status.value}">{p_node.critique}</verification>\n'
            f"  <output_var>{out_str}</output_var>\n"
            f"</step>"
        )

    # Prefix cut off ready for step_id + 1
    m_user = re.search(r"<\|im_start\|>user\n(.*?)(?:<\|im_end\|>|$)", chatml_or_xml, re.DOTALL)
    user_header = f"<|im_start|>user\n{m_user.group(1).strip()}<|im_end|>\n" if m_user else ""
    full_prefix = f"{user_header}<|im_start|>assistant\n<think>\n" + "\n\n".join(xml_steps) + "\n\n"

    plan = {
        "step_id": step_id,
        "var_name": var_name,
        "original_value": orig_val,
        "perturbed_value": perturbed_val,
        "original_answer": orig_answer,
        "prefix": full_prefix,
    }
    return plan, None


def classify_msra_outcome(
    continuation_text: str,
    plan: Dict[str, Any],
    tolerance: float = 0.01,
) -> str:
    """Classify the model's response to an intermediate counterfactual perturbation."""
    # Check if the epistemic verifier actively rejected the perturbation
    if 'status="REJECT"' in continuation_text or "<verification status='REJECT'>" in continuation_text:
        return "rejected_at_verification"

    final_ans_str = extract_final_answer(continuation_text)
    if not final_ans_str:
        # Check if Answer: line exists
        m_ans = re.search(r"Answer:\s*(-?\d+(?:\.\d+)?)", continuation_text)
        if m_ans:
            final_ans_str = m_ans.group(1)
        else:
            return "no_answer"

    try:
        final_ans = float(final_ans_str.replace(",", ""))
    except ValueError:
        return "no_answer"

    orig_ans = plan.get("original_answer")
    if orig_ans is not None and abs(final_ans - orig_ans) <= tolerance:
        return "reverted"

    # If the answer changed away from original answer
    return "follows"


def run_msra_interventions(
    records: List[Dict[str, Any]],
    backend: Any,
    limit: Optional[int] = None,
    max_new_tokens: int = 512,
) -> Dict[str, Any]:
    """Run counterfactual interventions across a collection of MSRA traces."""
    eval_count = len(records) if limit is None else min(len(records), limit)
    results = []
    skipped = collections.Counter()
    outcomes = collections.Counter()

    for idx, row in enumerate(records[:eval_count], start=1):
        text = row.get("text", "")
        plan, reason = plan_msra_intervention(text, key=row.get("id", idx))
        if plan is None:
            skipped[reason] += 1
            continue

        prompt = plan["prefix"]
        continuation = backend.generate_until(
            prompt=prompt,
            stop_sequences=["<|im_end|>", "</final_answer>"],
            max_new_tokens=max_new_tokens,
        )

        outcome = classify_msra_outcome(continuation, plan)
        outcomes[outcome] += 1

        results.append({
            "problem_id": row.get("id", f"item_{idx}"),
            "step_id": plan["step_id"],
            "var_name": plan["var_name"],
            "original_value": plan["original_value"],
            "perturbed_value": plan["perturbed_value"],
            "original_answer": plan["original_answer"],
            "prefix": prompt,
            "continuation": continuation,
            "outcome": outcome,
        })

    n_eligible = len(results)
    total_items = n_eligible + sum(skipped.values())
    eligibility_rate = round(n_eligible / max(1, total_items), 3)

    return {
        "total_records": total_items,
        "eligible_count": n_eligible,
        "eligibility_rate": eligibility_rate,
        "skipped": dict(skipped),
        "outcomes": dict(outcomes),
        "follows_rate": round(outcomes["follows"] / max(1, n_eligible) * 100, 2),
        "rejection_rate": round(outcomes["rejected_at_verification"] / max(1, n_eligible) * 100, 2),
        "reverted_rate": round(outcomes["reverted"] / max(1, n_eligible) * 100, 2),
        "items": results,
    }


def main():
    import argparse
    import sys
    from pathlib import Path
    from .stream_driver import MockGeneratorBackend

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/structured_msra_coldstart_v1/valid.jsonl", help="Dataset of MSRA traces")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of traces")
    parser.add_argument("--adapter", default=None, help="LoRA adapter directory (optional)")
    parser.add_argument("--model", default="mlx-community/Qwen3-8B-4bit", help="Base model identifier")
    parser.add_argument("--out", default=None, help="Output path for intervention summary")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: dataset {data_path} not found.")
        sys.exit(1)

    records = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    if args.adapter:
        from .mlx_backend import MLXGeneratorBackend
        backend = MLXGeneratorBackend(model_path=args.model, adapter_path=args.adapter)
    else:
        # Default mock backend for verification
        backend = MockGeneratorBackend({
            "v1 =": "<final_answer>40</final_answer>",
        })

    summary = run_msra_interventions(records, backend, limit=args.limit)
    out_json = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out_json + "\n", encoding="utf-8")
        print(f"Intervention results written to {args.out}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()

