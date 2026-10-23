"""Authored public-answer checker probes; not a model-quality benchmark."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.verifiers import verify_arith_rationale, verify_g24_rationale, verify_order_rationale

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = ("scripts/verifiers.py", "scripts/gen_tasks.py")
    before = {p: sha(ROOT / p) for p in sources}
    # Expected statuses follow the declared expression grammar and manually
    # checked arithmetic, not the shared evaluator's labels or generated data.
    cases = [
        ("plain_product", "Answer: 1 * 2 * 3 * 4", [1, 2, 3, 4], "valid"),
        ("unicode_product", "Answer: 1 × 2 × 3 × 4", [1, 2, 3, 4], "valid"),
        ("wrapped_product", "**Answer**: **1 * 2 * 3 * 4**", [1, 2, 3, 4], "valid"),
        ("explicit_target", "Answer: 1 * 2 * 3 * 4 = 24", [1, 2, 3, 4], "valid"),
        ("extra_operand", "Answer: 1 * 1 * 2 * 3 * 4", [1, 2, 3, 4], "invalid"),
        ("missing_operands", "Answer: 6 * 4", [1, 2, 3, 4], "invalid"),
        ("bare_target", "Answer: 24", [1, 2, 3, 4], "invalid"),
        ("wrong_value", "Answer: 1 + 2 + 3 + 4", [1, 2, 3, 4], "invalid"),
        ("exact_fraction", "Answer: 8 / (3 - 8 / 3)", [3, 3, 8, 8], "valid"),
        ("missing_marker", "Expression: 1 * 2 * 3 * 4", [1, 2, 3, 4], "unverifiable"),
        ("empty_answer", "Answer:", [1, 2, 3, 4], "unverifiable"),
        ("broken_syntax", "Answer: 1 + (", [1, 2, 3, 4], "unverifiable"),
        ("missing_inputs", "Answer: 1 * 2 * 3 * 4", None, "unverifiable"),
        ("disallowed_call", "Answer: sum([1, 2, 3, 4])", [1, 2, 3, 4], "invalid"),
        ("zero_division", "Answer: 1 / (2 - 2) * 3 * 4", [1, 2, 3, 4], "invalid"),
        ("wrong_equality_rhs", "Answer: 1 * 2 * 3 * 4 = 25", [1, 2, 3, 4], "invalid"),
        ("wrong_input_multiset", "Answer: 1 * 2 * 3 * 4", [1, 2, 3, 5], "invalid"),
    ]
    observed = []
    for name, answer, numbers, expected in cases:
        result = verify_g24_rationale(answer, {} if numbers is None else {"numbers": numbers})
        observed.append({"name": name, "public_answer": answer, "input_numbers": numbers,
                         "expected": expected, "observed": result.status.value,
                         "reason": result.reason, "matches_contract": result.status.value == expected})
    limits = []
    arith = verify_arith_rationale("Public equation: 2 + 3 = 5.\nAnswer: 99")
    limits.append({"name": "equation_consistency_not_final_answer", "status": arith.status.value,
                   "interpretation": "A clean arithmetic equation does not certify the final answer or query interpretation."})
    fraction = verify_arith_rationale("Public equation: 1 / 2 = 0.5.\nAnswer: 0.5")
    limits.append({"name": "integer_domain_assumption", "status": fraction.status.value,
                   "interpretation": "Do not apply this integer-answer rationale checker as a general math-answer verifier."})
    order = verify_order_rationale("Final order: Alice, Bob, Carol", {
        "names": ["Alice", "Bob", "Carol"], "clues": [["b", 0, 1], ["b", 1, 2]], "ask": 2,
    })
    limits.append({"name": "ordering_witness_without_final_answer", "status": order.status.value,
                   "interpretation": "A valid ordering witness does not prove the requested answer was actually returned."})
    a = verify_g24_rationale("Answer: 1 * 2 * 3 * 4", {"numbers": [1, 2, 3, 4], "gold": "wrong"})
    b = verify_g24_rationale("Answer: 1 * 2 * 3 * 4", {"numbers": [1, 2, 3, 4], "gold": "another"})
    assert all(row["matches_contract"] for row in observed)
    assert [row["status"] for row in limits] == ["valid", "invalid", "valid"]
    assert a == b
    assert before == {p: sha(ROOT / p) for p in sources}
    output = {
        "evidence": "authored synthetic software contract probes", "real_model_calls": 0,
        "dataset_items_read": 0, "policy_fitting": False, "source_sha256": before,
        "probe_sha256": sha(Path(__file__)), "g24_cases": observed, "scope_limits": limits,
        "gold_field_independence": a == b, "sources_unchanged": True,
        "important_limit": "The online G24 checker and procedural evaluator share check24; matching them is not independent verifier validation.",
    }
    (OUT / "checker_scope.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"G24 authored contract cases: {len(observed)}/{len(observed)} matched; scope limitations: {len(limits)} reproduced; model calls: 0.")


if __name__ == "__main__":
    main()
