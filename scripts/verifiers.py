#!/usr/bin/env python3
r"""Deterministic program-verifier guardrails for reasoning traces.

Implements symbolic execution and constraint checking for:
- arith: recompute all arithmetic steps 'A op B = C' (supporting +, -, *, /, ×, ÷, \times, \div, \cdot)
  and check for non-integer final answers.
- order: parse the final full runner ordering and verify all problem clues and ask position.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Any


class VerificationStatus(str, Enum):
    """Outcome of a fail-closed rationale verification attempt."""

    VALID = "valid"
    INVALID = "invalid"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class VerificationResult:
    """Structured verifier result used by development-only routing analyses."""

    status: VerificationStatus
    reason: str


def arith_verifier(raw: str) -> tuple[bool, str]:
    """Recomputes every 'A op B = C' in raw and flags non-integer final answers.

    Supported operators: +, -, *, ×, /, ÷, \\times, \\div, \\cdot.

    Returns:
        (flag, reason): flag=True if an error or invalid step is detected, False otherwise.
    """
    # 1. Check final answer for non-integer values
    ans_match = re.search(r"Answer:\s*([^\n\r]+)", raw, re.I)
    if ans_match:
        ans_str = ans_match.group(1).strip().rstrip(".")
        clean_ans = ans_str.replace(",", "").strip()
        try:
            val = float(clean_ans.rstrip("."))
            if not val.is_integer():
                return True, f"non_integer_final_answer: {ans_str}"
        except ValueError:
            if "." in clean_ans or "..." in clean_ans:
                return True, f"non_integer_final_answer: {ans_str}"

    # 2. Recompute every arithmetic step 'A op B = C'
    # Remove thousand separators inside numbers (e.g. 310,005 -> 310005)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", raw)
    text = text.replace("−", "-").replace("–", "-")
    # Normalize LaTeX operators
    text = text.replace(r"\times", "*").replace(r"\div", "/").replace(r"\cdot", "*")

    # Match equations of form A op B = C
    eq_pattern = re.compile(
        r"(-?\d+(?:\.\d+)?)\s*([\+\-\*\/×÷])\s*(-?\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)"
    )
    for m in eq_pattern.finditer(text):
        a_str, op, b_str, c_str = m.group(1), m.group(2), m.group(3), m.group(4)
        try:
            a, b, c = float(a_str), float(b_str), float(c_str)
        except ValueError:
            continue

        if op == "+":
            expected = a + b
        elif op == "-":
            expected = a - b
        elif op in ("*", "×"):
            expected = a * b
        elif op in ("/", "÷"):
            if b == 0:
                return True, f"division_by_zero: {m.group(0)}"
            expected = a / b
        else:
            continue

        if abs(expected - c) > 1e-4:
            return True, f"arith_step_mismatch: {a_str} {op} {b_str} = {c_str} (expected {expected})"

    return False, "ok"


def verify_arith_rationale(raw: str, meta: dict[str, Any] | None = None) -> VerificationResult:
    """Classify an arithmetic rationale without consulting a reference answer.

    ``meta`` is accepted so all family verifiers have a compatible call shape,
    but it is intentionally ignored.  In particular, neither ``gold`` nor
    ``answer`` fields can affect this result.

    The legacy :func:`arith_verifier` remains unchanged and fail-open when it
    cannot extract an equation.  This API makes that third state explicit.
    """
    del meta

    flagged, reason = arith_verifier(raw)
    if flagged:
        return VerificationResult(VerificationStatus.INVALID, reason)

    # The legacy verifier does not recognize fractional final answers.  Treat a
    # syntactically scalar fraction as invalid when it is not an integer, while
    # leaving prose/unparseable answers to the equation-based classification.
    ans_match = re.search(r"Answer:\s*([^\n\r]+)", raw, re.I)
    if ans_match:
        answer = ans_match.group(1).strip().rstrip(".").replace(",", "")
        if re.fullmatch(r"[+-]?\d+\s*/\s*[+-]?\d+", answer):
            try:
                if Fraction(answer.replace(" ", "")).denominator != 1:
                    return VerificationResult(
                        VerificationStatus.INVALID,
                        f"non_integer_final_answer: {ans_match.group(1).strip().rstrip('.')}",
                    )
            except (ValueError, ZeroDivisionError):
                return VerificationResult(
                    VerificationStatus.INVALID,
                    f"invalid_final_answer: {ans_match.group(1).strip().rstrip('.')}",
                )

    # Mirror the legacy normalization and equation grammar exactly.  This keeps
    # legacy decisions stable while distinguishing "no checked evidence" from
    # a genuinely clean rationale.
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", raw)
    text = text.replace("−", "-").replace("–", "-")
    text = text.replace(r"\times", "*").replace(r"\div", "/").replace(r"\cdot", "*")
    eq_pattern = re.compile(
        r"(-?\d+(?:\.\d+)?)\s*([\+\-\*\/×÷])\s*(-?\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)"
    )
    if not eq_pattern.search(text):
        return VerificationResult(VerificationStatus.UNVERIFIABLE, "no arithmetic equation extractable")
    return VerificationResult(VerificationStatus.VALID, "ok")


def _holds_clue(clue: list[Any], pos: dict[int, int]) -> bool:
    """Evaluates whether clue holds given pos mapping entity_idx -> position."""
    t, x, y = clue[0], clue[1], clue[2]
    if t == "b":
        return pos[x] < pos[y]
    if t == "a":
        return pos[y] == pos[x] + 1
    if t in ("g", "gap"):
        return pos[y] == pos[x] + clue[3]
    raise ValueError(f"Unknown clue type: {t}")


def _parse_full_ordering(raw: str, names: list[str]) -> list[str] | None:
    """Extracts the final full ordering of all runner names from raw output."""
    n = len(names)
    names_lower = {name.lower(): name for name in names}

    # Strategy 1: Arrow sequence (e.g. 'A < B < C < D < E')
    for m in reversed(list(re.finditer(r"([A-Za-z]+(?:\s*<\s*[A-Za-z]+)+)", raw))):
        seq = [x.strip() for x in m.group(1).split("<")]
        if len(seq) == n and all(x.lower() in names_lower for x in seq):
            if len(set(x.lower() for x in seq)) == n:
                return [names_lower[x.lower()] for x in seq]

    # Strategy 2: Comma sequence with positions (e.g. 'Grace (1), Erin (2)...' or 'Grace (1st)...')
    paren_seq_pattern = re.compile(
        r"(?:(?:order(?:\s+is)?:\s*)|(?:Final order:\s*))?"
        r"([A-Za-z]+\s*\(\d+(?:st|nd|rd|th)?\)(?:\s*,\s*[A-Za-z]+\s*\(\d+(?:st|nd|rd|th)?\))+)",
        re.I,
    )
    for m in reversed(list(paren_seq_pattern.finditer(raw))):
        items = re.findall(r"([A-Za-z]+)\s*\((\d+)(?:st|nd|rd|th)?\)", m.group(1))
        if len(items) == n:
            parsed: dict[int, str] = {}
            for name, rank in items:
                if name.lower() in names_lower:
                    parsed[int(rank)] = names_lower[name.lower()]
            if len(parsed) == n:
                min_r = min(parsed.keys())
                if sorted(parsed.keys()) == list(range(min_r, min_r + n)):
                    return [parsed[r] for r in sorted(parsed.keys())]

    # Strategy 3: Explicit 'Final order: Name, Name...' or 'order is: Name, Name...'
    order_header_pattern = re.compile(
        r"(?:(?:Final\s+order)|(?:order\s+is)|(?:order\s+must\s+be))\s*:\s*([A-Za-z]+(?:\s*,\s*[A-Za-z]+)+)",
        re.I,
    )
    for m in reversed(list(order_header_pattern.finditer(raw))):
        seq = [x.strip() for x in m.group(1).split(",")]
        if len(seq) == n and all(x.lower() in names_lower for x in seq):
            if len(set(x.lower() for x in seq)) == n:
                return [names_lower[x.lower()] for x in seq]

    # Strategy 4: Standalone line with comma-separated names of length n
    lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
    for line in reversed(lines):
        if "," in line and not any(kw in line.lower() for kw in ["clue", "if", "try", "assume", "let", "check", "start"]):
            parts = [x.strip() for x in line.split(",")]
            if len(parts) == n and all(p.lower() in names_lower for p in parts):
                if len(set(p.lower() for p in parts)) == n:
                    return [names_lower[p.lower()] for p in parts]

    # Strategy 5: Numbered list or assignment block near conclusion
    for start_line in range(len(lines) - 1, -1, -1):
        block: dict[int, str] = {}
        for idx in range(start_line, max(-1, start_line - 25), -1):
            cur_line = lines[idx]
            if " or " in cur_line.lower() or "?" in cur_line:
                continue
            m1 = re.match(r"^(?:[-*]\s*)?(\d+)(?:st|nd|rd|th)?\s*[:.]\s*([A-Za-z]+)\s*$", cur_line)
            if m1:
                rank = int(m1.group(1))
                name = m1.group(2)
                if name.lower() in names_lower:
                    block[rank] = names_lower[name.lower()]
                continue
            m2 = re.search(r"\b([A-Za-z]+)\s*=\s*(\d+)\b", cur_line)
            if m2:
                name = m2.group(1)
                rank = int(m2.group(2))
                if name.lower() in names_lower:
                    block[rank] = names_lower[name.lower()]
                continue
            if block and len(block) >= n:
                break
        if len(block) == n:
            min_r = min(block.keys())
            if sorted(block.keys()) == list(range(min_r, min_r + n)):
                if len(set(block.values())) == n:
                    return [block[r] for r in sorted(block.keys())]

    return None


def order_verifier(raw: str, meta: dict[str, Any], flag_unextractable: bool = False) -> tuple[bool, str]:
    """Parses the final full ordering from raw output and validates clues in meta.

    Returns:
        (flag, reason): flag=True if constraints are violated (or unextractable if
        flag_unextractable=True), False if clean.
        When clues are violated, returns ALL violated clues in reason:
        'clues_violated: [clue1, clue2, ...]'.
        'ordering not extractable' is returned as its own status when no full
        ordering can be parsed.
    """
    names = meta.get("names", [])
    clues = meta.get("clues", [])
    ask = meta.get("ask")

    ordering = _parse_full_ordering(raw, names)
    if ordering is None:
        return flag_unextractable, "ordering not extractable"

    # Map each entity index to its 0-based position in the extracted ordering
    pos = {i: ordering.index(names[i]) for i in range(len(names))}

    # Check each clue in meta; collect ALL violated clues
    violated_clues = [clue for clue in clues if not _holds_clue(clue, pos)]
    if violated_clues:
        return True, f"clues_violated: {violated_clues}"

    # Verify that the final answer matches the runner placed in the asked position
    if ask is not None and 0 <= ask < len(ordering):
        ans_match = re.search(r"Answer:\s*([A-Za-z]+)", raw, re.I)
        if ans_match:
            ans_runner = ans_match.group(1).strip()
            expected_runner = ordering[ask]
            if ans_runner.lower() != expected_runner.lower():
                return True, f"answer_position_mismatch: answered {ans_runner} but position is {expected_runner}"

    return False, "ok"


def verify_order_rationale(raw: str, meta: dict[str, Any]) -> VerificationResult:
    """Classify a full ordering as valid, invalid, or unextractable.

    Only the puzzle structure (``names``, ``clues`` and ``ask``) is used.
    Reference-answer-like fields in ``meta`` are deliberately ignored.
    """
    names = meta.get("names", [])
    if _parse_full_ordering(raw, names) is None:
        return VerificationResult(VerificationStatus.UNVERIFIABLE, "ordering not extractable")

    flagged, reason = order_verifier(raw, meta, flag_unextractable=False)
    if flagged:
        return VerificationResult(VerificationStatus.INVALID, reason)
    return VerificationResult(VerificationStatus.VALID, reason)


_G24_ANSWER_MARKER = re.compile(
    r"(?P<outer>\*\*)?(?:final\s+)?answer(?P<label_close>\*\*)?\s*:\s*(?P<candidate>[^\n\r]*)",
    re.I,
)


def _extract_g24_answer(raw: str) -> str | None:
    """Return the last explicitly marked Game-of-24 expression, if present."""
    matches = list(_G24_ANSWER_MARKER.finditer(raw))
    if not matches:
        return None

    match = matches[-1]
    candidate = match.group("candidate").strip()
    if not candidate:
        for line in raw[match.end() :].splitlines():
            candidate = line.strip()
            if candidate and not candidate.startswith("```"):
                break
        else:
            return None

    # Normalize presentation-only wrappers.  The mathematical expression is
    # still validated independently by check24 below.
    if match.group("outer") and not match.group("label_close") and candidate.endswith("**"):
        candidate = candidate[:-2].strip()
    if candidate.startswith("**") and candidate.endswith("**") and len(candidate) > 4:
        candidate = candidate[2:-2].strip()
    candidate = candidate.strip("`").strip()
    if len(candidate) >= 2 and candidate[0] == candidate[-1] == "$":
        candidate = candidate[1:-1].strip()
    boxed = re.fullmatch(r"\\boxed\{(.+)\}", candidate)
    if boxed:
        candidate = boxed.group(1).strip()
    if candidate.endswith(".") and not candidate.endswith("..."):
        candidate = candidate[:-1].rstrip()
    return candidate or None


def verify_g24_rationale(raw: str, meta: dict[str, Any]) -> VerificationResult:
    """Validate the final marked Game-of-24 expression using only input numbers."""
    expression = _extract_g24_answer(raw)
    if expression is None:
        return VerificationResult(VerificationStatus.UNVERIFIABLE, "answer expression not extractable")

    normalized = expression.replace("×", "*").replace("÷", "/")
    parts = normalized.split("=")
    if not parts or len(parts) > 2 or not parts[0].strip():
        return VerificationResult(VerificationStatus.UNVERIFIABLE, "answer expression not parseable")
    try:
        ast.parse(parts[0].strip(), mode="eval")
    except (SyntaxError, ValueError):
        return VerificationResult(VerificationStatus.UNVERIFIABLE, "answer expression not parseable")

    numbers = meta.get("numbers")
    if not isinstance(numbers, (list, tuple)):
        return VerificationResult(VerificationStatus.UNVERIFIABLE, "input numbers unavailable")

    # Imported lazily to keep the existing arithmetic/order verifier path light.
    from scripts.gen_tasks import check24

    if not check24(normalized, list(numbers)):
        return VerificationResult(
            VerificationStatus.INVALID,
            "expression does not make 24 using each input number exactly once",
        )
    return VerificationResult(VerificationStatus.VALID, "ok")
