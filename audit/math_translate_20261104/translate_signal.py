"""Does an independent program catch more wrong answers than one translated from the solution? Rule in docs/research_plan.md.

Run: python audit/math_translate_20261104/translate_signal.py SOURCE_RUN OUT_DIR
"""
import ast
import json
import re
import signal
import sys
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import _EMPTY_THINK, read_jsonl, score
from structured_llm.math_check import final_answer, same_answer
from structured_llm.pal import refusal, run_program

SOURCE, HERE = Path(sys.argv[1]), Path(sys.argv[2])
# Read by hand in the 200-problem run: three scorer misses, then five artefacts of the numeric-answer prompt.
READ_AS_RIGHT = ("8670a0", "291ac8", "0a3182", "3227cd", "ca68c0", "3ac26b", "0d2baa", "33783f")
_FENCE = re.compile(r"```(?:python)?\n(.*?)```", re.S)


class Timeout(Exception):
    pass


def alarm(*_):
    raise Timeout


def execute(text):
    signal.alarm(30)
    try:
        value = run_program(text, full=True)
        return value, refusal(text) if value is None else None
    except Timeout:
        return None, "timeout"
    finally:
        signal.alarm(0)


def only_constant(text):
    """True when the program does no work: every statement assigns a literal."""
    match = _FENCE.search(text)
    try:
        body = ast.parse(match[1] if match else text).body
    except SyntaxError:
        return False
    return bool(body) and all(isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) for node in body)


def rate(flag, pool):
    hits = sum(flag(item) for item in pool)
    return {"count": f"{hits}/{len(pool)}", "share": round(hits / len(pool), 3) if pool else None,
            "ci": wilson(hits, len(pool)) if pool else None}


def compare(pool):
    """Compare both flags on one set of problems; only_pal and only_translated feed the paired test."""
    wrong = [row for row in pool if not row["right"]]
    right = [row for row in pool if row["right"]]
    only_pal = sum(row["pal_flag"] and not row["translated_flag"] for row in wrong)
    only_translated = sum(row["translated_flag"] and not row["pal_flag"] for row in wrong)
    pal_caught, translated_caught = rate(lambda r: r["pal_flag"], wrong), rate(lambda r: r["translated_flag"], wrong)
    pal_alarm, translated_alarm = rate(lambda r: r["pal_flag"], right), rate(lambda r: r["translated_flag"], right)
    return {
        "wrong": len(wrong), "right": len(right),
        "pal": {"caught": pal_caught, "false_alarm": pal_alarm},
        "translated": {"caught": translated_caught, "false_alarm": translated_alarm},
        "only_pal": only_pal, "only_translated": only_translated, "mcnemar_p": exact_mcnemar(only_pal, only_translated),
        "catch_gap": round(pal_caught["share"] - translated_caught["share"], 3) if wrong else 0,
        "false_alarm_gap": round(pal_alarm["share"] - translated_alarm["share"], 3) if right else 0,
    }


signal.signal(signal.SIGALRM, alarm)
pal = {row["id"]: row for row in json.load((SOURCE / "pal_full.json").open())["rows"]} if (SOURCE / "pal_full.json").exists() else {}
translated = {row["id"]: row for row in read_jsonl(HERE / "translated.jsonl")}
rows = []
for solution in read_jsonl(SOURCE / "base_showcalc.jsonl"):
    key = solution["id"]
    if key not in translated:
        continue
    value, reason = execute(translated[key]["output"])
    found = final_answer(_EMPTY_THINK + solution["output"])
    independent = pal[key]["value"] if key in pal else None
    rows.append({
        "id": key,
        "right": score("base_showcalc", solution["output"], solution["question"], solution["gold"], "latex")["correct"],
        "solution_truncated": solution["truncated"],
        "translated_truncated": translated[key]["truncated"],
        "answer": found, "pal_value": independent, "translated_value": value, "refused": reason,
        "only_constant": only_constant(translated[key]["output"]),
        "pal_flag": independent is not None and not same_answer(found, repr(independent)),
        "translated_flag": value is not None and not same_answer(found, repr(value)),
    })

report = compare(rows)
holds = (report["catch_gap"] > 0 and report["mcnemar_p"] < 0.05 and report["catch_gap"] > report["false_alarm_gap"])
reverse = report["catch_gap"] < 0 and report["mcnemar_p"] < 0.05
out = {
    "primary": report,
    "reading": "holds" if holds else ("reverse" if reverse else "does_not_hold"),
    "not_for_conclusions": {
        "both_gave_a_value": compare([r for r in rows if r["pal_value"] is not None and r["translated_value"] is not None]),
        "solution_not_truncated": compare([r for r in rows if not r["solution_truncated"]]),
        "read_cases_counted_right": compare([{**r, "right": r["right"] or r["id"].startswith(READ_AS_RIGHT)} for r in rows]),
    },
    "translated_programs": {
        "n": len(rows),
        "no_value": sum(r["translated_value"] is None for r in rows),
        "only_constant": sum(r["only_constant"] for r in rows),
        "truncated": sum(r["translated_truncated"] for r in rows),
        "mean_tokens": round(sum(t["tokens"] for t in translated.values()) / max(len(translated), 1), 1),
    },
}
(HERE / "signal.json").write_text(json.dumps(out, indent=1) + "\n")
(HERE / "rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
print(json.dumps(out, indent=1))
