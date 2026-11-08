"""How often does each saved signal flag a wrong answer, and how often a right one, on 100 MATH problems?

A plain-text equation reader was tried and dropped: read by hand, its hits were almost all misreads such as
`1 - 1/8 = 7/8` taken as 1 - 1/8 = 7. Only the LaTeX checker is reported for equations.
"""
import json
import sys
from pathlib import Path

from structured_llm.evaluate import score
from structured_llm.math_check import FALSE, check_text, final_answer, same_answer

HERE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
pal = {row["id"]: row for row in json.load((HERE / "pal_full.json").open())["rows"]}


def report(flags, truth):
    wrong = [key for key in truth if not truth[key]]
    right = [key for key in truth if truth[key]]
    return {"caught_wrong": f"{sum(flags[k] for k in wrong)}/{len(wrong)}",
            "false_alarm_right": f"{sum(flags[k] for k in right)}/{len(right)}"}


out = {}
for mode in ("base_prefill", "base_showcalc"):
    if not (HERE / f"{mode}.jsonl").exists():
        continue
    rows = {row["id"]: row for row in map(json.loads, (HERE / f"{mode}.jsonl").open())}
    truth = {k: score(mode, r["output"], r["question"], r["gold"], "latex")["correct"] for k, r in rows.items()}
    equation = {k: check_text(r["output"])["counts"][FALSE] > 0 for k, r in rows.items()}
    differs = {}
    for k, r in rows.items():
        text = "<think>\n\n</think>\n\n" + r["output"] if mode == "base_showcalc" else r["output"]
        value = pal[k]["value"]
        differs[k] = value is not None and not same_answer(final_answer(text), repr(value))
    out[mode] = {
        "correct": sum(truth.values()),
        "false_latex_equation": report(equation, truth),
        "differs_from_pal_all_100": report(differs, truth),
        "differs_from_pal_where_pal_gave_a_number": report(differs, {k: truth[k] for k in rows if pal[k]["value"] is not None}),
    }
(HERE / "checker_signal.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
