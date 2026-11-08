"""Score the last run under the rule in docs/research_plan.md.

Run: python audit/math_final_20261104/final_signal.py wrong OUT_DIR    write the wrong solutions for labelling, nothing else
     python audit/math_final_20261104/final_signal.py read OUT_DIR     apply the rule, once programs and labels exist
"""
import json
import re
import signal
import sys
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import _EMPTY_THINK, read_jsonl
from structured_llm.math_check import TRUE, compare, final_answer, parse, same_answer, to_expression
from structured_llm.pal import refusal, run_program

EXECUTION = {"calculation", "plan_only", "answer_line"}
_DEGREE = re.compile(r"\^\{?\\circ\}?")


def is_right(found, gold):
    return same_answer(found, _DEGREE.sub("", gold))


def differs(found, value):
    """Would a program raise a flag? Not without a number, and not against an answer that still has a variable."""
    if value is None:
        return False
    if found is None:
        return True
    answer, number = parse(to_expression(found)), parse(to_expression(repr(value)))
    if answer is None:
        return True
    return not answer.free_symbols and compare(answer, number, tolerance=1e-3) != TRUE


class Timeout(Exception):
    pass


def alarm(*_):
    raise Timeout


def execute(text):
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(30)
    try:
        value = run_program(text, full=True)
        signal.alarm(0)
        return value, refusal(text) if value is None else None
    except Timeout:
        return None, "timeout"
    finally:
        signal.alarm(0)


def group(label):
    if label in EXECUTION:
        return "execution"
    return label


def kappa(first, second):
    """Cohen's kappa over the ids both passes labelled."""
    keys = sorted(first)
    seen = {group(first[key]) for key in keys} | {group(second[key]) for key in keys}
    agreed = sum(group(first[key]) == group(second[key]) for key in keys) / len(keys)
    chance = sum(sum(group(first[key]) == label for key in keys) * sum(group(second[key]) == label for key in keys)
                 for label in seen) / len(keys) ** 2
    return round((agreed - chance) / (1 - chance), 3) if chance < 1 else 1.0


def rate(flag, pool):
    hits = sum(flag(row) for row in pool)
    return {"count": f"{hits}/{len(pool)}", "share": round(hits / len(pool), 3) if pool else 0.0,
            "ci": wilson(hits, len(pool)) if pool else None}


def paired(pool):
    only_independent = sum(r["independent_flag"] and not r["translated_flag"] for r in pool)
    only_translated = sum(r["translated_flag"] and not r["independent_flag"] for r in pool)
    return {"independent": rate(lambda r: r["independent_flag"], pool), "translated": rate(lambda r: r["translated_flag"], pool),
            "only_independent": only_independent, "only_translated": only_translated,
            "mcnemar_p": exact_mcnemar(only_independent, only_translated)}


def judge(rows):
    right = [r for r in rows if r["right"]]
    wrong = [r for r in rows if not r["right"]]
    reasoning = paired([r for r in wrong if r["group"] == "reasoning"])
    execution = paired([r for r in wrong if r["group"] == "execution"])
    alarms = paired(right)
    either = lambda r: r["independent_flag"] or r["translated_flag"]
    caught, false_alarm = rate(either, wrong), rate(either, right)
    catch_gap = reasoning["independent"]["share"] - reasoning["translated"]["share"]
    alarm_gap = alarms["independent"]["share"] - alarms["translated"]["share"]
    conditions = {
        "1_at_least_20_reasoning": sum(r["group"] == "reasoning" for r in wrong) >= 20,
        "2_independent_catches_more_reasoning": catch_gap > 0 and reasoning["mcnemar_p"] < 0.05,
        "3_catch_gap_above_false_alarm_gap": catch_gap > alarm_gap,
        "4_translated_at_least_equal_on_execution": execution["translated"]["share"] >= execution["independent"]["share"],
        "5_either_flag_meets_gate_4": caught["share"] >= 0.5 and false_alarm["share"] <= 0.2,
    }
    return {"right": len(right), "wrong": len(wrong),
            "groups": {name: sum(r["group"] == name for r in wrong) for name in sorted({r["group"] for r in wrong})},
            "reasoning": reasoning, "execution": execution, "false_alarms": alarms,
            "either_flag": {"caught": caught, "false_alarm": false_alarm},
            "catch_gap": round(catch_gap, 3), "false_alarm_gap": round(alarm_gap, 3),
            "conditions": conditions, "holds": all(conditions.values())}


def write_wrong(out):
    """Solutions the scorer calls wrong, with no program anywhere near them. Truncated ones need no label."""
    lines, count = [], 0
    for row in read_jsonl(out / "solution.jsonl"):
        found = final_answer(_EMPTY_THINK + row["output"])
        if is_right(found, row["gold"]) or row["truncated"]:
            continue
        count += 1
        lines += [f"## {row['id'][:6]}", f"**Problem:** {row['question']}", f"**Reference answer:** {row['gold']}",
                  f"**Answer read by the scorer:** {found}", "**Solution:**", row["output"].strip(), ""]
    (out / "wrong_for_labels.md").write_text("\n".join(lines))
    print(count, "to label")


def read(out):
    first = json.load((out / "labels_a.json").open())
    second = json.load((out / "labels_b.json").open())
    programs = {name: {row["id"]: row for row in read_jsonl(out / f"{name}.jsonl")} for name in ("independent", "translated")}
    rows = []
    for row in read_jsonl(out / "solution.jsonl"):
        key, short = row["id"], row["id"][:6]
        found = final_answer(_EMPTY_THINK + row["output"])
        values = {name: execute(programs[name][key]["output"]) for name in programs}
        a, b = first.get(short), second.get(short)
        scored = is_right(found, row["gold"])
        rows.append({
            "id": key, "gold": row["gold"], "answer": found, "scored_right": scored,
            "truncated": row["truncated"], "label_a": a, "label_b": b,
            "independent_value": values["independent"][0], "independent_refused": values["independent"][1],
            "translated_value": values["translated"][0], "translated_refused": values["translated"][1],
            "independent_flag": differs(found, values["independent"][0]),
            "translated_flag": differs(found, values["translated"][0]),
        })

    def labelled(pick):
        result = []
        for r in rows:
            name = pick(r)
            result.append({**r, "right": r["scored_right"] or name == "scorer_miss", "group": name})
        return result

    def agreed(r):
        if r["scored_right"]:
            return "right"
        if r["truncated"]:
            return "truncated"
        a, b = group(r["label_a"]), group(r["label_b"])
        return a if a == b and a != "unclear" else "excluded"

    primary = labelled(agreed)
    common = {k: first[k] for k in first if k in second}
    tokens = {name: round(sum(p["tokens"] for p in programs[name].values()) / len(programs[name]), 1) for name in programs}
    solution_rows = read_jsonl(out / "solution.jsonl")
    both = [r for r in primary if r["independent_value"] is not None and r["translated_value"] is not None]
    report = {
        "primary": judge(primary),
        "labels": {"both_passes": len(common), "kappa": kappa(common, {k: second[k] for k in common}) if common else None,
                   "excluded": sum(r["group"] == "excluded" for r in primary)},
        "not_for_conclusions": {
            "labels_a_only": judge(labelled(lambda r: group(r["label_a"]) if r["label_a"] else ("truncated" if r["truncated"] else "right"))),
            "labels_b_only": judge(labelled(lambda r: group(r["label_b"]) if r["label_b"] else ("truncated" if r["truncated"] else "right"))),
            "both_gave_a_value": judge(both),
            "correct": {"solution": sum(r["right"] for r in primary),
                        "independent": sum(r["independent_value"] is not None and is_right(repr(r["independent_value"]), r["gold"]) for r in primary),
                        "translated": sum(r["translated_value"] is not None and is_right(repr(r["translated_value"]), r["gold"]) for r in primary)},
        },
        "no_value": {name: sum(r[f"{name}_value"] is None for r in rows) for name in programs},
        "mean_tokens": {**tokens, "solution": round(sum(r["tokens"] for r in solution_rows) / len(solution_rows), 1)},
    }
    (out / "signal.json").write_text(json.dumps(report, indent=1) + "\n")
    (out / "rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    {"wrong": write_wrong, "read": read}[sys.argv[1]](Path(sys.argv[2]))
