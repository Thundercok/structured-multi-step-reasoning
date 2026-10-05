#!/usr/bin/env python3
"""Deterministic program-verifier guardrails for reasoning traces.

Implements symbolic execution and constraint checking for:
- arith: recompute all arithmetic steps 'A op B = C' and check for non-integer final answers.
- order: parse the final full runner ordering and verify all problem clues and ask position.
"""
from __future__ import annotations

import re
from typing import Any


def arith_verifier(raw: str) -> tuple[bool, str]:
    """Recomputes every 'A op B = C' (+ - * × / ÷) in raw and flags non-integer final answers.

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
    # Examples: '1. Carol', '1: Dave', '1st: Bob', '- Heidi = 1'
    for start_line in range(len(lines) - 1, -1, -1):
        block: dict[int, str] = {}
        for idx in range(start_line, max(-1, start_line - 25), -1):
            cur_line = lines[idx]
            # Avoid disjunctions ('Grace or Heidi') and placeholders ('?')
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
        (flag, reason): flag=True if a constraint is violated (or unextractable if
        flag_unextractable=True), False if clean.
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

    # Check each clue in meta
    for clue in clues:
        if not _holds_clue(clue, pos):
            return True, f"clue_violated: {clue}"

    # Verify that the final answer matches the runner placed in the asked position
    if ask is not None and 0 <= ask < len(ordering):
        ans_match = re.search(r"Answer:\s*([A-Za-z]+)", raw, re.I)
        if ans_match:
            ans_runner = ans_match.group(1).strip()
            expected_runner = ordering[ask]
            if ans_runner.lower() != expected_runner.lower():
                return True, f"answer_position_mismatch: answered {ans_runner} but position is {expected_runner}"

    return False, "ok"
