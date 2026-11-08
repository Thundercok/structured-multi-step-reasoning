"""Exploratory cuts, all thought of after seeing the result. None of this can change the reading in signal.json.

Hand labels come from an agent that read the end of each solution and the flags together, so they are not blind.
Run after translate_signal.py: python audit/math_translate_20261104/secondary.py
"""
import collections
import json
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import read_jsonl
from structured_llm.math_check import same_answer

HERE = Path(__file__).parent
SOURCE = HERE.parent / "math_dev200_20261103"
# Wrong solutions, not truncated, where the translated program disagreed with the answer.
TRANSLATED_CATCHES = {
    "plan_without_computing": "6ebb17 39eb48 96c684 7c95aa 8b8732 b885f3 16d581 42eb9b 7d919f 3b4f78 bd2c36 d25999",
    "answer_line_garbled": "a99738 45f772 3227cd b3a868 4ea4f6 0d2baa ca68c0 33783f 16aaa0",
    "hand_step_redone_right": "c189a4 55d3cc 4651f8 257c40 228b68 4b03a0 41fbbd",
    "flag_for_another_reason": "9f89da 5713b2 03a6de 19cc7b 7d347b 70cc85",
}
# Wrong solutions where independent PAL disagreed and the translated program repeated the answer.
ONLY_PAL_CATCHES = {
    "reasoning_error_copied": "55125b 8f57aa cd8af9 554ae8 61f0dd bab7a3 9a5a2e 4ddfea 26f3b6 fee416",
    "scorer_or_prompt_noise": "8670a0 3ac26b",
}

rows = json.load((HERE / "rows.json").open())
solutions = {row["id"]: row for row in read_jsonl(SOURCE / "base_showcalc.jsonl")}
tokens = {
    "solution": solutions,
    "translated": {row["id"]: row for row in read_jsonl(HERE / "translated.jsonl")},
    "pal": {row["id"]: row for row in read_jsonl(SOURCE / "base_pal.jsonl")},
}
for row in rows:
    gold = solutions[row["id"]]["gold"]
    row["translated_right"] = row["translated_value"] is not None and same_answer(repr(row["translated_value"]), gold)
    row["pal_right"] = row["pal_value"] is not None and same_answer(repr(row["pal_value"]), gold)


def rate(flag, pool):
    hits = sum(flag(row) for row in pool)
    return {"count": f"{hits}/{len(pool)}", "ci": wilson(hits, len(pool))}


def paired(a, b):
    only_a, only_b = sum(a(r) and not b(r) for r in rows), sum(b(r) and not a(r) for r in rows)
    return {"only_first": only_a, "only_second": only_b, "mcnemar_p": exact_mcnemar(only_a, only_b)}


wrong = [r for r in rows if not r["right"]]
right = [r for r in rows if r["right"]]
either = lambda r: r["pal_flag"] or r["translated_flag"]
agree = [r for r in rows if r["translated_value"] is not None and not r["translated_flag"]]
out = {
    "correct": {"solution": len(right), "pal": sum(r["pal_right"] for r in rows),
                "translated_program": sum(r["translated_right"] for r in rows)},
    "translated_program_vs_solution": paired(lambda r: r["translated_right"], lambda r: r["right"]),
    "translated_program_vs_pal": paired(lambda r: r["translated_right"], lambda r: r["pal_right"]),
    "flag_either": {"caught": rate(either, wrong), "false_alarm": rate(either, right)},
    "right_when_translated_agrees": rate(lambda r: r["right"], agree),
    "mean_tokens": {name: round(sum(r["tokens"] for r in group.values()) / len(group), 1) for name, group in tokens.items()},
    "translated_catches_hand_read": {key: len(ids.split()) for key, ids in TRANSLATED_CATCHES.items()},
    "only_pal_catches_hand_read": {key: len(ids.split()) for key, ids in ONLY_PAL_CATCHES.items()},
    "refusals": collections.Counter(str(r["refused"]) for r in rows if r["translated_value"] is None).most_common(),
}
for label, groups, flag in (("translated", TRANSLATED_CATCHES, lambda r: r["translated_flag"] and not r["solution_truncated"]),
                            ("only_pal", ONLY_PAL_CATCHES, lambda r: r["pal_flag"] and not r["translated_flag"] and r["translated_value"] is not None)):
    labelled = {key for ids in groups.values() for key in ids.split()}
    found = {r["id"][:6] for r in wrong if flag(r)}
    assert found == labelled, (label, found ^ labelled)
(HERE / "secondary.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
