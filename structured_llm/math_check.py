"""Find the equations in LaTeX math text and check them with SymPy.

Run: python -m structured_llm.math_check

Equations are read conservatively: anything outside a small grammar is skipped rather than
guessed at, so coverage is a lower bound. Text is whitelisted before SymPy parses it, since
parse_expr evaluates what it is given and this text comes from a dataset or a model.
"""

import argparse
import collections
import json
import random
import re
import signal
import warnings
from pathlib import Path

from sympy import N
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

SOURCE = Path("data/math_source/train.jsonl")
HARD_LEVELS = ("Level 3", "Level 4", "Level 5")
TRUE, FALSE, CONDITIONAL = "true", "false", "conditional"

_SEGMENT = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$|\\\[(.+?)\\\]|\\begin\{align\*?\}(.+?)\\end\{align\*?\}", re.S)
_DROP = re.compile(r"\\left|\\right|\\!|\\,|\\;|\\:|\\\$|&")
# "3\frac{2}{3}" is a mixed number in arithmetic but a product in algebra, so it isn't guessed.
_DIGIT_BEFORE_FRAC = re.compile(r"\d\s*\\frac")
_REJECT = re.compile(r"\\text|\\mbox|\\mathbf|\\dots|\\ldots|\\cdots|\\equiv|\\pmod|\\le|\\ge|\\ne|\\lt|\\gt|\\approx|"
                     r"\\sum|\\prod|\\binom|\\begin|\\Rightarrow|\\implies|\\overline|\\angle|\\triangle|[<>_!|%,:;\[\]]")
_ALLOWED = re.compile(r"[0-9a-z+\-*/^().\s]+")
_NAMES = re.compile(r"[a-z]+")
_FUNCTIONS = {"sqrt", "sin", "cos", "tan", "log", "pi"}
_TOWER = re.compile(r"\^\(?[^()]*\^")
_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_POINTS = 3
_TIMEOUT_SECONDS = 1.0


class _Timeout(Exception):
    pass


def _raise_timeout(*_):
    raise _Timeout


def _braced(text, start):
    """Return (content, index after) of the {...} group at start, or None."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[start + 1:index], index + 1
    return None


def _replace_frac(text):
    while (start := text.find("\\frac")) != -1:
        top = _braced(text, start + 5)
        bottom = _braced(text, top[1]) if top else None
        if not bottom:
            raise ValueError("frac")
        text = f"{text[:start]}(({top[0]})/({bottom[0]})){text[bottom[1]:]}"
    return text


def _replace_sqrt(text):
    while (start := text.find("\\sqrt")) != -1:
        inner = _braced(text, start + 5)
        if not inner:
            raise ValueError("sqrt")
        text = f"{text[:start]}sqrt({inner[0]}){text[inner[1]:]}"
    return text


def to_expression(latex):
    """Translate one side of an equation to a whitelisted string, or return None."""
    text = _DROP.sub("", latex.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")).replace("\\ ", " ")
    text = text.strip().rstrip(".,;").strip()
    text = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", text)
    text = re.sub(r"\\frac\s*(\d)\s*(\d)", r"\\frac{\1}{\2}", text)
    text = re.sub(r"\\frac\s*(\d)\s*\{", r"\\frac{\1}{", text)
    text = re.sub(r"\\frac\{([^{}]*)\}\s*(\d)", r"\\frac{\1}{\2}", text)
    if not text or _REJECT.search(text) or _DIGIT_BEFORE_FRAC.search(text):
        return None
    text = re.sub(r"\\(sin|cos|tan)\s*([0-9.]+)\^\\circ", r"\1(\2*(pi/180))", text)
    try:
        text = _replace_sqrt(_replace_frac(text))
    except ValueError:
        return None
    text = (text.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/").replace("\\pi", "pi")
            .replace("^\\circ", "*(pi/180)").replace("\\sin", "sin").replace("\\cos", "cos").replace("\\tan", "tan")
            .replace("\\log", "log").replace("{", "(").replace("}", ")"))
    if "\\" in text or not _ALLOWED.fullmatch(text) or _TOWER.search(text):
        return None
    if any(name not in _FUNCTIONS and len(name) > 2 for name in _NAMES.findall(text)):
        return None
    return text


def parse(expression):
    """Parse a whitelisted string, or return None. Never pass unchecked text here."""
    if expression is None:
        return None
    previous = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, _TIMEOUT_SECONDS)
    try:
        return parse_expr(expression, transformations=_TRANSFORMS, evaluate=False)
    except (_Timeout, Exception):  # SymPy raises many types on malformed input.
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _numeric(expr, values):
    value = N(expr.subs(values))
    return complex(value)


def compare(left, right, seed=0, tolerance=1e-6):
    """Return TRUE, FALSE, CONDITIONAL, or None if the two sides can't be evaluated."""
    previous = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, _TIMEOUT_SECONDS)
    try:
        symbols = sorted(left.free_symbols | right.free_symbols, key=str)
        rng = random.Random(seed)
        for _ in range(_POINTS if symbols else 1):
            values = {symbol: rng.uniform(1.5, 4.5) for symbol in symbols}
            a, b = _numeric(left, values), _numeric(right, values)
            if abs(a - b) > tolerance * max(1.0, abs(a), abs(b)):
                return CONDITIONAL if symbols else FALSE
        return TRUE
    except (_Timeout, Exception):
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _math_segments(text):
    for match in _SEGMENT.finditer(text):
        yield next(group for group in match.groups() if group is not None)


def equations(text):
    """Yield (left, right) LaTeX for every adjacent pair in every equation chain."""
    for segment in _math_segments(text):
        previous = None
        for line in re.split(r"\\\\", segment):
            sides = [side.replace("&", "").strip() for side in line.split("=")]
            if len(sides) < 2:
                previous = None
                continue
            if not sides[0]:  # An aligned "&= next" continues the last line.
                if previous is None:
                    continue
                sides[0] = previous
            yield from zip(sides, sides[1:])
            previous = sides[-1]


def is_trivial(left, right):
    """True when no calculation is claimed, as in "x = 5" or "5 = 5"."""
    has_operation = re.compile(r"[-+*/^]|\\frac|\\sqrt|\\cdot|\\times|\(")
    return not (has_operation.search(left) or has_operation.search(right))


def boxed_answer(text):
    start = text.rfind("\\boxed")
    if start == -1:
        return None
    inner = _braced(text, start + 6)
    return inner[0] if inner else None


def _latex_symbols(text):
    """Models often write π and √5 where the dataset writes \\pi and \\sqrt{5}."""
    text = re.sub(r"√\s*\(([^()]*)\)", r"\\sqrt{\1}", text)
    text = re.sub(r"√\s*\{([^{}]*)\}", r"\\sqrt{\1}", text)
    text = re.sub(r"√\s*([0-9a-z]+)", r"\\sqrt{\1}", text)
    return text.replace("π", "\\pi ").replace("×", "\\cdot ").replace("−", "-")


def _plain_expression(text):
    """Return an answer line that is itself an expression, like "4x^2 + 2/x", or None.

    A digit, a space and then a letter reads as a unit ("6 m"), which the caller reduces to its number.
    """
    text = text.strip().rstrip(".")
    words = re.sub(r"\\[a-z]+|sqrt|pi", " ", text)
    if not re.search(r"[a-z\\]", text) or re.search(r"[a-zA-Z]{2}|\d\s+[a-zA-Z]", words):
        return None
    return text if parse(to_expression(text)) is not None else None


def final_answer(text):
    """Find the final answer's LaTeX in an output: boxed, an Answer line, or its last math or number."""
    if "</think>" in text:
        tail = text.partition("</think>")[2]
    elif "<think>" in text:
        line = re.search(r"^Answer:\s*.+$", text, re.M)
        tail = line[0] if line else ""
    else:
        tail = text
    tail = _latex_symbols(tail.split("\nQuestion:")[0])
    if not tail.strip():
        return None
    if (boxed := boxed_answer(tail)) is not None:
        return boxed
    tail = tail.replace("**", "")
    answer_line = re.findall(r"Answer:\s*(.+)", tail)
    if answer_line:
        tail = answer_line[-1]
    segments = list(_math_segments(tail))
    if segments:
        return segments[-1]
    if answer_line and (expression := _plain_expression(tail)) is not None:
        return expression
    numbers = re.findall(r"-?\d[\d,]*(?:\.\d+)?(?:/\d+)?", tail)
    if numbers:
        return numbers[-1]
    return tail.strip() if "Answer:" in text else None


def same_answer(found, gold):
    """True if two LaTeX answers have the same value, or the same text when they can't be parsed."""
    if found is None or gold is None:
        return False
    normal = lambda text: re.sub(r"\s+|\\!|\\,|\\left|\\right|\$", "", text).replace("dfrac", "frac").rstrip(".")
    if normal(found) == normal(gold):
        return True
    a, b = parse(to_expression(found)), parse(to_expression(gold))
    # Tighter than the equation check: 99999999 is not 100000000, though a rounded step may pass there.
    return a is not None and b is not None and compare(a, b, tolerance=1e-9) == TRUE


def check_text(text):
    """Count checked equations in a solution and say whether they reach its boxed answer."""
    counts = collections.Counter()
    answer = parse(to_expression(boxed_answer(text) or ""))
    reaches_answer = False
    false_examples = []
    for left_latex, right_latex in equations(text):
        if is_trivial(left_latex, right_latex):
            counts["trivial"] += 1
            continue
        left, right = parse(to_expression(left_latex)), parse(to_expression(right_latex.replace("\\boxed", "")))
        if left is None or right is None:
            counts["unreadable"] += 1
            continue
        verdict = compare(left, right)
        counts[verdict or "unreadable"] += 1
        if verdict == FALSE:
            false_examples.append(f"{left_latex} = {right_latex}")
        if verdict == TRUE and answer is not None and compare(right, answer) == TRUE:
            reaches_answer = True
    return {"counts": counts, "reaches_answer": reaches_answer, "answer_readable": answer is not None,
            "false_examples": false_examples}


def is_covered(result, minimum=2):
    return result["counts"][TRUE] >= minimum and result["reaches_answer"]


def _rate(part, whole):
    return round(part / whole, 4) if whole else None


def coverage(rows):
    results = [(row, check_text(row["solution"])) for row in rows]
    totals = sum((result["counts"] for _, result in results), collections.Counter())
    def group(items):
        return {"n": len(items), "covered": _rate(sum(is_covered(r) for _, r in items), len(items)),
                "two_true": _rate(sum(r["counts"][TRUE] >= 2 for _, r in items), len(items)),
                "one_true": _rate(sum(r["counts"][TRUE] >= 1 for _, r in items), len(items))}
    by = lambda key: {value: group([pair for pair in results if pair[0][key] == value])
                      for value in sorted({row[key] for row in rows})}
    hard = [pair for pair in results if pair[0]["level"] in HARD_LEVELS]
    return {
        "gate_3a_hard_levels": group(hard),
        "all_levels": group(results),
        "by_level": by("level"),
        "by_subject_hard": {value: group([p for p in hard if p[0]["subject"] == value])
                            for value in sorted({p[0]["subject"] for p in hard})},
        "equations": dict(totals),
        "false_rate_of_decided": _rate(totals[FALSE], totals[FALSE] + totals[TRUE]),
        "answer_readable": _rate(sum(r["answer_readable"] for _, r in results), len(results)),
        "false_examples": [example for _, r in results for example in r["false_examples"]],
    }


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--out")
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.source).read_text().splitlines()]
    report = coverage(rows)
    examples = report.pop("false_examples")
    report["false_equations"] = len(examples)
    if args.out:
        Path(args.out).write_text(json.dumps({**report, "false_examples": examples}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2))
