"""The structured thinking format: render, parse and check a model's trace.

A trace is the text the model writes after the assistant header:

    <think>
    Step 1: Natalia sold 48/2 = 24 clips in May.
    Calc: 48/2=24
    Step 2: Natalia sold 48+24 = 72 clips altogether.
    Calc: 48+24=72
    </think>

    Answer: 72

Every check here is deterministic, so structure is measured rather than judged.
"""

import ast
import operator
import re
from dataclasses import dataclass, field

# Spacing isn't part of the format: "Step 1:The" and "Calc: 1 + 1 = 2" mean the same thing.
_STEP = re.compile(r"Step (\d+):\s*(\S.*)")
_CALC = re.compile(r"Calc:\s*([^=]+?)\s*=\s*(-?(?:\d+\.?\d*|\.\d+))")
_ANSWER = re.compile(r"Answer: \$?(-?[\d,]*\.?\d+)\s*")
_NUMBER = re.compile(r"\d[\d,]*\.?\d*|\.\d+")
_SIGNED_NUMBER = re.compile(r"(?<![\w.])-?(?:\d[\d,]*\.?\d*|\.\d+)|(?<=-)\d[\d,]*\.?\d*")
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


@dataclass
class Step:
    text: str
    calcs: list = field(default_factory=list)  # (expression, stated result) strings


@dataclass
class Trace:
    steps: list
    answer: str | None
    errors: list


def render(steps, answer):
    lines = ["<think>"]
    for index, step in enumerate(steps, 1):
        lines.append(f"Step {index}: {step.text}")
        lines.extend(f"Calc: {expr}={result}" for expr, result in step.calcs)
    lines += ["</think>", "", f"Answer: {answer}"]
    return "\n".join(lines)


def parse(text):
    """Parse strictly; anything outside the grammar is recorded in errors."""
    text = text.strip()
    errors, steps, answer = [], [], None
    if not text.startswith("<think>"):
        errors.append("missing_think_open")
    head, closed, tail = text.removeprefix("<think>").partition("</think>")
    if not closed:
        errors.append("missing_think_close")
    for line in head.strip().splitlines():
        line = line.strip()
        if match := _STEP.fullmatch(line):
            if int(match[1]) != len(steps) + 1:
                errors.append("step_number")
            steps.append(Step(match[2]))
        elif (match := _CALC.fullmatch(line)) and steps:
            steps[-1].calcs.append((match[1].strip(), match[2]))
        elif line:
            errors.append("line_outside_grammar")
    if not steps:
        errors.append("no_steps")
    if match := _ANSWER.fullmatch(tail.strip()):
        answer = match[1].replace(",", "")
    else:
        errors.append("answer_line")
    return Trace(steps, answer, errors)


def evaluate_expr(expr):
    """Evaluate + - * / and parentheses only. Returns None if it can't."""

    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError(expr)

    try:
        return walk(ast.parse(expr.strip(), mode="eval").body)
    except (SyntaxError, ValueError, ZeroDivisionError):
        return None


def calc_is_correct(expr, stated):
    """Correct to the decimals written, so 2/3=.67 passes. Whole numbers must be exact: 10/3=3 fails."""
    value = evaluate_expr(expr)
    try:
        result = float(stated)
    except ValueError:
        return False
    if value is None:
        return False
    decimals = len(stated.partition(".")[2])
    tolerance = 0.5 * 10**-decimals if decimals else 0
    return abs(value - result) <= tolerance + 1e-9


def _numbers(text):
    found = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(float(token.replace(",", "")))
        except ValueError:
            pass
    return found


def loose_answer(text):
    """Final number after the thinking, in any layout, so free-form output is scored fairly.

    An "Answer:" line still counts when </think> is missing, and any further question the
    model goes on to invent is ignored. Thinking cut off with neither has no answer.
    """
    if "</think>" in text:
        tail = text.partition("</think>")[2]
    else:
        line = re.search(r"^Answer:\s*(.+)$", text, re.M)
        if not line:
            return None
        tail = line[1]
    tail = tail.split("\nQuestion:")[0]
    boxed = re.findall(r"\\boxed\{([^}]*)\}", tail)
    numbers = _SIGNED_NUMBER.findall(boxed[-1] if boxed else tail)
    if not numbers:
        return None
    try:
        return float(numbers[-1].replace(",", ""))
    except ValueError:
        return None


def check(text, question, gold=None):
    """Score one output. Rates are None when there is nothing to measure.

    format_valid is strict; correct uses loose_answer so accuracy stays comparable
    between trained output and a base model that ignores the format.
    """
    trace = parse(text)
    calcs = [calc for step in trace.steps for calc in step.calcs]
    correct = sum(calc_is_correct(expr, stated) for expr, stated in calcs)

    # An operand is grounded if it came from the question or an earlier result.
    known, operands, grounded = _numbers(question), 0, 0
    for expr, stated in calcs:
        for number in _numbers(expr):
            operands += 1
            grounded += number in known
        known |= _numbers(stated)

    answer = float(trace.answer) if trace.answer is not None else None
    last = float(calcs[-1][1]) if calcs and _NUMBER.search(calcs[-1][1]) else None
    loose = loose_answer(text)
    vacuous = sum(not re.search(r"\d\s*[-+*/]", expr) for expr, _ in calcs)
    return {
        "format_valid": not trace.errors,
        "errors": sorted(set(trace.errors)),
        "steps": len(trace.steps),
        "calcs": len(calcs),
        "calc_accuracy": correct / len(calcs) if calcs else None,
        "vacuous_rate": vacuous / len(calcs) if calcs else None,  # "Calc: 220=220" checks nothing
        "grounded_rate": grounded / operands if operands else None,
        "answer_from_last_calc": answer is not None and last is not None and abs(answer - last) < 1e-6,
        "answer": trace.answer,
        "answered": loose is not None,
        "correct": None if gold is None else loose is not None and abs(loose - float(gold)) < 1e-6,
    }
