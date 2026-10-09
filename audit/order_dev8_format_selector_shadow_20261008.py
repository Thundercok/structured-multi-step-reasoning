"""Exploratory, retrospective shadow policies on the exposed contract-v2 pilot.

No production parser, selector, gate, prompt, record or cost is changed.
Gold is consulted only to score AFTER shadow answers have been selected.
Run: python3.12 -B audit/order_dev8_format_selector_shadow_20261008.py
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "audit/order_certificate_pilot_dev8_contract_v2_real_20261008"
QA = ROOT / "audit/order_dev8_contract_v2_replay_review_20261008.py"
PATTERNS = (
    r"Answer:[ \t]*([A-Za-z]+)",
    r"\*\*Answer:[ \t]*([A-Za-z]+)\*\*",
    r"\*\*Answer:\*\*[ \t]*([A-Za-z]+)",
)


def final_block_answer(text, runners):
    """Bounded draft aliases on a terminal answer block, never a gold-name search.

    Whole plain/bold/bold-label Answer lines, optional Markdown heading prefix.
    Repeated adjacent answers must agree; unknown names and extra prose fail.
    This helper is an audit prototype, NOT the production scoring contract.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    answers = []
    for line in reversed(text.rstrip().splitlines()):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^#{1,6}[ \t]+", "", line)
        match = next((match for pattern in PATTERNS if (match := re.fullmatch(pattern, line))), None)
        if match is None:
            break
        if match[1] not in runners:
            return ""
        answers.append(match[1])
    return answers[0] if answers and len(set(answers)) == 1 else ""


def shadow_select(generations, runners, parser, *, unique_complete=False):
    """Keep an admissible selector choice; optionally use a sole admissible branch.

    If the stopped selector chooses an inadmissible branch, there must be exactly
    ONE stopped, format-parsable branch to redirect. Multiple/zero -> abstain.
    No ranking by correctness, clues, agreement, gold or runtime solving.
    """
    if len(generations) != 4:
        raise ValueError("Expected three candidates and one selector")
    selector = generations[3]
    index = parser(selector["output"])
    if index is None or selector["finish_reason"] not in ("stop", "stop_answer"):
        return {"index": None, "answer": "", "reason": "selector_invalid_or_truncated"}
    admissible = {}
    for branch, call in enumerate(generations[:3]):
        if call["finish_reason"] not in ("stop", "stop_answer"):
            continue
        answer = final_block_answer(call["output"], runners)
        if answer:
            admissible[branch] = answer
    if index in admissible:
        return {"index": index, "answer": admissible[index], "reason": "kept_selector"}
    if unique_complete and len(admissible) == 1:
        only = next(iter(admissible))
        return {"index": only, "answer": admissible[only], "reason": "sole_admissible_branch"}
    return {"index": None, "answer": "", "reason": "abstained_no_unique_admissible_branch"}


def regression_checks(parser):
    runners = ("Alice", "Bob")
    cases = [
        ("Answer: Alice", "Alice"),
        ("Reasoning.\nAnswer: Alice", "Alice"),
        ("**Answer: Alice**", "Alice"),
        ("**Answer:** Alice", "Alice"),
        ("### Answer: Alice", "Alice"),
        ("## **Answer: Alice**", "Alice"),
        ("Answer: Alice\n**Answer: Alice**", "Alice"),
        (" \nAnswer: Alice\n \n", "Alice"),
        ("", ""), (None, ""),
        ("Answer: Zelda", ""),
        ("Answer: Alice or Bob", ""),
        ("Answer: Alice because she won", ""),
        ("Not Answer: Alice", ""),
        ("Answer: not Alice", ""),
        ("Answer: Alice\nAnswer: Bob", ""),
        ("Answer: Alice\n\n**Answer: Bob**", ""),
        ("Answer: Zelda\nAnswer: Alice", ""),
        ("**Answer: Alice", ""),
        ("Answer: Alice**", ""),
        ("Answer: Alice\nExtra explanation", ""),
        ("```\nAnswer: Alice\n```", ""),
    ]
    for text, expected in cases:
        assert final_block_answer(text, runners) == expected, (text, expected)
    call = lambda text, finish="stop": {"output": text, "finish_reason": finish}
    branches = [call("Answer: Alice", "length"), call("**Answer: Bob**"), call("unfinished", "length")]
    generations = [*branches, call("Best: 0")]
    assert shadow_select(generations, runners, parser)["answer"] == ""
    assert shadow_select(generations, runners, parser, unique_complete=True) == {
        "index": 1, "answer": "Bob", "reason": "sole_admissible_branch",
    }
    # Never change an admissible choice even if another branch might be correct.
    generations = [call("Answer: Alice"), call("Answer: Bob"), call("Answer: Bob"), call("Best: 0")]
    assert shadow_select(generations, runners, parser, unique_complete=True)["index"] == 0
    # An invalid choice with TWO admissible alternatives must abstain, not rank them.
    generations[0] = call("unfinished", "length")
    assert shadow_select(generations, runners, parser, unique_complete=True)["answer"] == ""
    generations[3] = call("Best: 1", "length")
    assert shadow_select(generations, runners, parser, unique_complete=True)["answer"] == ""
    generations[3] = call("Best: 9")
    assert shadow_select(generations, runners, parser, unique_complete=True)["answer"] == ""
    return len(cases) + 6


def main():
    if not __debug__:
        raise RuntimeError("Assertions must remain enabled; do not use -O")
    # The original read-only QA checks all hashes, matrix, replay and old N=2 files.
    qa_result = subprocess.run([sys.executable, "-B", str(QA)], check=True,
                               text=True, capture_output=True, cwd=ROOT)
    qa = json.loads(qa_result.stdout)
    assert qa["source_hashes_valid"] == 8 and qa["replay_rows_equal"] == 64
    manifest = json.loads((RUN / "manifest.json").read_text())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    before = {name: sha(RUN / name) for name in ("manifest.json", *manifest["artifact_sha256"])}
    dataset = json.loads((RUN / "dataset.json").read_text())
    records = json.loads((RUN / "records.json").read_text())
    saved_rows = json.loads((RUN / "eval_rows.json").read_text())
    assert len(dataset["items"]) == 8 and {item["split"] for item in dataset["items"]} == {"train"}
    sys.path.insert(0, str(ROOT))
    from experiments.order_certificate_study import METHODS, parse_selector_index
    from experiments.research_study import check_answer
    from scripts.verified_pal_order import parse_order_query

    checks = regression_checks(parse_selector_index)
    items = {item["id"]: item for item in dataset["items"]}
    candidates = {row["id"]: row for row in records if row["arm"] == "candidate_selection"}
    # SELECT BEFORE accessing any gold labels, with query-derived names only.
    choices = {"A_format_only": {}, "B_format_plus_unique_complete": {}}
    for identifier, attempt in candidates.items():
        ir = parse_order_query(items[identifier]["query"])
        assert ir is not None
        for name, unique in (("A_format_only", False), ("B_format_plus_unique_complete", True)):
            choices[name][identifier] = shadow_select(attempt["generations"], ir.runners,
                                                     parse_selector_index, unique_complete=unique)
    scenario_rows = {"original_frozen": saved_rows}
    for scenario, selected in choices.items():
        rows = []
        for original in saved_rows:
            row = dict(original)
            if row["path"] and row["path"][-1] == "candidate_selection":
                choice = selected[row["id"]]
                row["answer"] = choice["answer"]
                row["correct"] = bool(choice["answer"] and check_answer(choice["answer"], items[row["id"]]))
            # Frozen PAL payload extraction, verifier gate, path and full call costs.
            for field in ("path", "tokens", "prompt_tokens", "completion_tokens", "escalated"):
                assert row[field] == original[field]
            rows.append(row)
        scenario_rows[scenario] = rows
    summaries = {}
    for scenario, rows in scenario_rows.items():
        metrics = {}
        for method in METHODS:
            group = [row for row in rows if row["method"] == method]
            assert len(group) == 8 and len({row["id"] for row in group}) == 8
            metric = {
                "correct_count": sum(row["correct"] for row in group),
                "mean_model_tokens": sum(row["tokens"] for row in group) / 8,
                "escalations": sum(row["escalated"] for row in group),
            }
            if method.startswith("w_") or method == "verified_certificate":
                metric["rescue_from_initial"] = sum(not row["initial_correct"] and row["correct"] for row in group)
                metric["harm_from_initial"] = sum(row["initial_correct"] and not row["correct"] for row in group)
            metrics[method] = metric
        summaries[scenario] = metrics
    assert before == {name: sha(RUN / name) for name in before}
    assert not any(name == "mlx" or name.startswith("mlx.") or name.startswith("mlx_lm") for name in sys.modules)
    print(json.dumps({
        "evidence": "retrospective_shadow_counterfactual_development_only",
        "questions": 8, "generation_seeds": [42], "additional_model_calls": 0,
        "regression_checks": checks, "source_and_artifacts_valid": True,
        "original_run_files_unchanged": True, "all_paths_and_costs_frozen": True,
        "selection_gold_independent": True, "summaries": summaries,
        "shadow_candidate_choices": choices,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
