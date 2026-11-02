"""Deterministic changes to a trace, with no model in the loop.

A trace's Calc lines form a small program, so changing one value can be propagated
through the later steps by code. Two uses:

counterfactual()     change a number in the question and recompute the whole trace,
                     producing a new training example.
plan_intervention()  change one intermediate result and work out what the final answer
                     should become if the rest of the thinking really depends on it.

Run: python -m structured_llm.counterfactual
"""

import argparse
import collections
import hashlib
import json
import random
import re
import shutil
from pathlib import Path

from .gsm8k import OUTPUT, convert, gold_answer, load_splits, training_row, write_jsonl
from .trace import Step, calc_is_correct, check, evaluate_expr, parse, render

CF_OUTPUT = Path("data/structured_gsm8k_cf_v1")
SEED = "structured-gsm8k-cf-v1"

_TOKEN = re.compile(r"(?<![\w.])(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?!\w)")
# Operands a solution may use without stating them: "half" is 2, an hour is 60 minutes.
_COMMON_CONSTANTS = {1.0, 2.0, 3.0, 4.0, 7.0, 10.0, 12.0, 24.0, 30.0, 52.0, 60.0, 100.0, 365.0, 1000.0}
_NUMBER_WORDS = {
    2.0: "two|twice|double|half|pair|pairs|couple|both|second", 3.0: "three|triple|thrice|third", 4.0: "four|quarter|fourth",
    5.0: "five|fifth", 6.0: "six|sixth", 7.0: "seven|seventh|week|weeks", 8.0: "eight|eighth", 9.0: "nine|ninth",
    10.0: "ten|tenth", 11.0: "eleven", 12.0: "twelve|dozen|year|years", 60.0: "hour|hours|minute|minutes",
    100.0: "hundred|percent", 1000.0: "thousand",
}


def values(text):
    return [float(token.replace(",", "")) for token in _TOKEN.findall(text)]


def fmt(value):
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def substitute(text, mapping):
    def replace(match):
        new = mapping.get(float(match[0].replace(",", "")))
        return match[0] if new is None else fmt(new)

    return _TOKEN.sub(replace, text)


def flat_calcs(steps):
    return [calc for step in steps for calc in step.calcs]


def reexecute(steps, changes, skip=0):
    """Recompute Calc lines after the first `skip`, carrying `changes` forward.

    Returns new steps, or None when one old value would need two different new values,
    because then the change can't be followed unambiguously.
    """
    mapping, new_steps, seen = dict(changes), [], 0
    for step in steps:
        new_calcs = []
        for expr, stated in step.calcs:
            seen += 1
            if seen <= skip:
                new_calcs.append((expr, stated))
                continue
            new_expr = substitute(expr, mapping)
            value = evaluate_expr(new_expr)
            if value is None:
                return None
            old = float(stated)
            unchanged = calc_is_correct(new_expr, stated)
            if old in mapping:
                if unchanged or abs(mapping[old] - value) > 1e-6:
                    return None
            elif not unchanged:
                mapping[old] = value
            new_calcs.append((new_expr, stated if unchanged else fmt(value)))
        text = step.text if seen <= skip else substitute(step.text, mapping)
        new_steps.append(Step(text, new_calcs))
    return new_steps


def _operands(calcs):
    return [number for expr, _ in calcs for number in values(expr)]


def _collides(old_calcs, new_calcs, question_values):
    """True if a changed result shares its value with a number that must stay fixed.

    With "$30 - $15 = $15", changing the result 15 would also rewrite the unrelated $15.
    """
    for index, (old, new) in enumerate(zip(old_calcs, new_calcs)):
        if old[1] != new[1]:
            value = float(old[1])
            if value in question_values or value in _operands(old_calcs[:index + 1]):
                return True
    return False


def _also_written_as_word(question, value):
    """True if "2" may also come from "two" or "half", which changing the digit wouldn't update."""
    words = _NUMBER_WORDS.get(value)
    return bool(words and re.search(rf"\b(?:{words})\b", question, re.I))


def counterfactual(row, seed):
    """Return ({question, trace, answer}, None), or (None, reason) if the row is unsafe to change."""
    text, reason = convert(row)
    if text is None:
        return None, reason
    trace = parse(text)
    question, calcs = row["question"], flat_calcs(trace.steps)
    results = [float(stated) for _, stated in calcs]
    if abs(float(trace.answer) - results[-1]) > 1e-6:
        return None, "answer_not_last_calc"

    in_question = values(question)
    known = set(in_question)
    for expr, stated in calcs:
        if any(number not in known and number not in _COMMON_CONSTANTS for number in values(expr)):
            return None, "ungrounded_operand"
        known.add(float(stated))
    explained = set(in_question) | set(_operands(calcs)) | set(results)
    if any(number not in explained for step in trace.steps for number in values(step.text)):
        return None, "unexplained_number_in_text"

    counts = collections.Counter(in_question)
    operands = set(_operands(calcs))
    candidates = []
    for match in _TOKEN.finditer(question):
        value = float(match[0].replace(",", ""))
        if (value.is_integer() and value >= 2 and counts[value] == 1 and value in operands
                and value not in results and question[match.end():match.end() + 1] != "%"
                and not _also_written_as_word(question, value)
                and not any(_also_written_as_word(step.text, value) for step in trace.steps)):
            candidates.append((match, value))
    if not candidates:
        return None, "no_safe_number"

    rng = random.Random(seed)
    for _ in range(8):
        match, value = rng.choice(candidates)
        new = float(rng.randint(max(2, int(value) // 2), int(value) * 2))
        if new == value or new in known:
            continue
        steps = reexecute(trace.steps, {value: new})
        if steps is None or _collides(calcs, flat_calcs(steps), set(in_question)):
            continue
        new_results = [float(stated) for _, stated in flat_calcs(steps)]
        if any(number <= 0 for number in new_results):
            continue
        if any(old.is_integer() and not number.is_integer() for old, number in zip(results, new_results)):
            continue
        if new_results[-1] == results[-1]:
            continue
        new_question = question[:match.start()] + fmt(new) + question[match.end():]
        answer = fmt(new_results[-1])
        new_text = render(steps, answer)
        result = check(new_text, new_question, answer)
        if result["errors"] or result["calc_accuracy"] != 1.0:
            continue
        return {"question": new_question, "trace": new_text, "answer": answer}, None
    return None, "no_valid_change"


def plan_intervention(output, question, key):
    """Plan a change to one intermediate result. Returns (plan, None) or (None, reason).

    The plan's prefix ends right after the changed Calc line; the model continues from
    there. A trace with a wrong Calc, or an answer not taken from its last Calc, is the kind
    a checker flags, so it stays in: its expected answer is unknown (None), but whether the
    answer moved at all can still be observed.
    """
    trace = parse(output)
    if trace.errors:
        return None, "invalid_format"
    calcs = flat_calcs(trace.steps)
    if len(calcs) < 2:
        return None, "too_few_calcs"
    correct = [calc_is_correct(*calc) for calc in calcs]
    original = float(trace.answer)
    flags = []
    if not all(correct):
        flags.append("wrong_calc")
    if abs(original - float(calcs[-1][1])) > 1e-6:
        flags.append("answer_not_last_calc")
    usable = correct.index(False) if not all(correct) else len(calcs) - 1

    in_question = set(values(question))
    results = [float(stated) for _, stated in calcs]
    target = None
    for index, value in enumerate(results[:usable]):
        later = {number for expr, _ in calcs[index + 1:] for number in values(expr)}
        if value.is_integer() and value in later and value not in in_question and results.count(value) == 1:
            target = index
            break
    if target is None:
        return None, "no_result_used_later"

    used = in_question | set(results) | set(_operands(calcs))
    old = results[target]
    digest = int(hashlib.sha256(str(key).encode()).hexdigest(), 16)
    new = old + digest % 9 + 1
    while new in used:
        new += 1
    if old in _operands(calcs[:target + 1]):
        return None, "ambiguous_propagation"
    expected = None
    if not flags:
        steps = reexecute(trace.steps, {old: new}, skip=target + 1)
        if steps is None or _collides(calcs, flat_calcs(steps), in_question):
            return None, "ambiguous_propagation"
        expected = float(flat_calcs(steps)[-1][1])
        if abs(expected - original) < 1e-6:
            return None, "change_does_not_reach_answer"

    lines, seen = ["<think>"], 0
    for number, step in enumerate(trace.steps, 1):
        if seen + len(step.calcs) <= target:
            lines.append(f"Step {number}: {step.text}")
            lines.extend(f"Calc: {expr}={stated}" for expr, stated in step.calcs)
            seen += len(step.calcs)
            continue
        lines.append(f"Step {number}: {substitute(step.text, {old: new})}")
        lines.extend(f"Calc: {expr}={stated}" for expr, stated in step.calcs[:target - seen])
        lines.append(f"Calc: {step.calcs[target - seen][0]}={fmt(new)}")
        break
    return {"prefix": "\n".join(lines) + "\n", "old": old, "new": new,
            "expected": expected, "original": original, "flags": flags}, None


def build(source=None, output=CF_OUTPUT):
    train, _, _ = load_splits(*([source] if source else []))
    reasons, rows = collections.Counter(), []
    for row in train:
        trace, reason = convert(row)
        if trace is None:
            continue
        rows.append(training_row(row, trace))
        made, reason = counterfactual(row, f"{SEED}:{row['question']}")
        if made is None:
            reasons[reason] += 1
        else:
            reasons["made"] += 1
            rows.append(training_row({"question": made["question"]}, made["trace"]))
    random.Random(SEED).shuffle(rows)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUTPUT / "valid.jsonl", output / "valid.jsonl")
    manifest = {
        "seed": SEED,
        "train_rows": len(rows),
        "counterfactual": dict(reasons),
        "valid_is_unchanged_copy_of": str(OUTPUT / "valid.jsonl"),
        "sha256": {"train.jsonl": write_jsonl(output / "train.jsonl", rows)},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=CF_OUTPUT)
    print(json.dumps(build(output=parser.parse_args().output), indent=2))
