import copy

import pytest

from scripts.gen_tasks import render_arith, render_g24, render_order
from scripts.review_tuning_sweep import analyze, legacy_implementation


@pytest.fixture(scope="module")
def legacy():
    return legacy_implementation()[:2]


def fixture(legacy):
    parser, checker = legacy
    arith = {"start": 246, "steps": [["div", 6], ["sub", 5], ["mul", 6], ["add", 980]]}
    order = {"names": ["Alice", "Bob", "Carol", "Dave"], "clues": [["a", 0, 1], ["a", 1, 2], ["a", 2, 3]], "ask": 3}
    g24 = {"numbers": [1, 2, 3, 4]}
    items = [
        {"id": "arith", "group_id": "arith", "family": "arith", "level": 1, "split": "test", "query": render_arith(arith), "answer": "1196", "meta": arith},
        {"id": "order", "group_id": "order", "family": "order", "level": 1, "split": "dev", "query": render_order(order), "answer": "Dave", "meta": order},
        {"id": "g24", "group_id": "g24", "family": "g24", "level": 1, "split": "calib", "query": render_g24(g24), "answer": "1*2*3*4", "meta": g24},
    ]
    records = []
    for item in items:
        for arm in ("DIRECT", "COT"):
            raw = "Step 4: Add 980 → 216 + 980 = 1196" if item["family"] == "arith" and arm == "DIRECT" else "**Answer: Dave**" if item["family"] == "order" else "Answer: 1*2*3*4=24" if item["family"] == "g24" else "Answer: 1196"
            parsed, status, wordy = parser(raw)
            records.append({
                **{key: item[key] for key in ("id", "group_id", "family", "level")},
                "arm": arm, "raw_output": raw, "parsed": parsed, "parse_status": status, "wordy": wordy,
                "correct": checker(item, parsed), "gold": item["answer"], "wall_ms": 1.0,
                "prompt_tokens": 10, "completion_tokens": 96 if item["family"] == "arith" and arm == "DIRECT" else 20,
                "finish_reason": "length" if item["family"] == "arith" and arm == "DIRECT" else "stop",
            })
    return records, items


def test_review_separates_format_recovery_expression_recovery_and_budget_tail_rejection(legacy):
    records, items = fixture(legacy)
    before = copy.deepcopy((records, items))
    summary, outcomes, proofs = analyze(records, items, *legacy)
    assert (records, items) == before
    assert summary["legacy_records_reproduced"] == 6
    assert len(proofs) == 3  # Includes obsolete test content in an exposed pool.
    by_key = {(row["id"], row["arm"]): row for row in outcomes}
    tail = by_key[("arith", "DIRECT")]
    assert tail["legacy"]["correct"] and not tail["typed"]["correct"]
    bold = by_key[("order", "COT")]
    assert bold["legacy"]["correct"] and not bold["strict_checker_on_legacy_parse"] and bold["typed"]["correct"]
    expression = by_key[("g24", "COT")]
    assert not expression["legacy"]["correct"] and expression["typed"]["correct"]
    assert summary["parse_recoveries_from_strict_legacy_parse"] == 4
    assert summary["presentation_cases_recovered_from_strict_legacy_parse"] == 2
    assert summary["g24_parser_score_gains"] == 2
    assert summary["new_model_calls"] == 0 and not summary["parameters_frozen"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "legacy_score", "legacy_parse", "gold", "length_tokens"])
def test_review_rejects_unpaired_or_inconsistent_artifacts(legacy, mutation):
    records, items = fixture(legacy)
    if mutation == "missing": records.pop()
    elif mutation == "duplicate": records.append(copy.deepcopy(records[0]))
    elif mutation == "legacy_score": records[0]["correct"] = not records[0]["correct"]
    elif mutation == "legacy_parse": records[0]["parsed"] = "modified"
    elif mutation == "gold": items[0]["answer"] = "999"
    else: records[0]["completion_tokens"] = 95
    with pytest.raises(ValueError):
        analyze(records, items, *legacy)
