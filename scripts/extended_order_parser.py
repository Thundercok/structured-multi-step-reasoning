"""Extended rule-based parser for Order queries, developed and tuned strictly on Tuning Dev (Groups 1-3).

Frozen for out-of-sample evaluation on Held-out Dev (Groups 4-6).
"""

from __future__ import annotations

import re
from typing import Any

from scripts.verified_pal_order import OrderClue, OrderConstraintIR

_ORD_MAP = {
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
    "5th": 5, "6th": 6, "7th": 7, "8th": 8,
}

# Supported runner names in the domain
KNOWN_RUNNERS = {"Alice", "Bob", "Carol", "Dave", "Erin", "Frank", "Grace", "Heidi"}


def _extract_runners(query: str) -> tuple[str, ...] | None:
    # 1. Check parenthesized runner list
    paren = re.search(r"\(([^)]+)\)", query)
    if paren:
        raw = paren.group(1)
        parts = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", raw) if p.strip()]
        if 2 <= len(parts) <= 8 and all(n in KNOWN_RUNNERS for n in parts):
            return tuple(parts)

    # 2. Check "between Name1, Name2, ... and NameK with no ties"
    between_match = re.search(r"between\s+(.+?)\s+with\s+no\s+ties", query, re.I)
    if between_match:
        raw = between_match.group(1)
        parts = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", raw) if p.strip()]
        if 2 <= len(parts) <= 8 and all(n in KNOWN_RUNNERS for n in parts):
            return tuple(parts)

    return None


def _extract_ask_rank(query: str) -> int | None:
    # Tuned specifically on expressions observed in Tuning Dev (Groups 1-3):
    # - "Who finished in 1st place?" / "Which runner finished in 1st place?"
    # - "Who took 1st place?" / "Which participant took 4th place?"
    # - "Which competitor ended in 4th place?"
    # - "Which runner came in 5th place?"
    # - "Who secured 5th place in the race?"
    # Verbs observed in Tuning Dev: finished in, ended in, came in, took, secured
    pattern = re.compile(
        r"(?:Who|Which\s+(?:runner|competitor|participant))\s+"
        r"(?:finished\s+in|ended\s+in|came\s+in|took|secured)\s+"
        r"([1-8](?:st|nd|rd|th))\s+place",
        re.I,
    )
    m = pattern.search(query)
    if m:
        return _ORD_MAP.get(m.group(1).lower())
    return None


def _segment_clues(query: str) -> list[str] | None:
    # In Tuning Dev:
    # Baseline & Lexical have "Clues: ... Who/Which ..."
    clues_match = re.search(r"Clues:\s*(.+?)\.\s*(?:Who|Which)", query, re.I | re.S)
    if clues_match:
        raw_clues = clues_match.group(1)
        return [c.strip() for c in raw_clues.split(";") if c.strip()]

    # Natural prose in Tuning Dev:
    m_q = re.search(r"\s*(?:Who|Which\s+\w+)\s+.*?\?\s*$", query, re.I)
    if not m_q:
        return None
    body = query[:m_q.start()].strip()
    body = re.sub(r"^A\s+race\s+was\s+contested\s+by\s+[^\.]+\.\s*", "", body, flags=re.I)
    body = re.sub(r"^(?:In|During)\s+.*?(?:with\s+no\s+ties|\)),\s*", "", body, flags=re.I)
    sentences = [s.strip() for s in body.split(".") if s.strip()]
    raw_clauses = []
    for s in sentences:
        s = re.sub(r"^(?:Furthermore|Meanwhile|At the same time|In addition),?\s*", "", s, flags=re.I).strip()
        parts = re.split(r",?\s+while\s+|,\s+and\s+", s, flags=re.I)
        for p in parts:
            p = p.strip()
            if p:
                raw_clauses.append(p)
    return raw_clauses


def _parse_single_clause(clause: str, names_dict: dict[str, str], n: int) -> list[OrderClue] | None:
    # Tuned on patterns observed in Tuning Dev:
    clause = clause.strip()
    if not clause:
        return None

    # Compound pattern in Tuning Dev Group 3 prose:
    # "{X} finished behind both {Y} and {Z}"
    m_both = re.fullmatch(
        r"([A-Za-z]+)\s+finished\s+behind\s+both\s+([A-Za-z]+)\s+and\s+([A-Za-z]+)",
        clause,
        re.I,
    )
    if m_both:
        x, y, z = m_both.group(1).casefold(), m_both.group(2).casefold(), m_both.group(3).casefold()
        if x in names_dict and y in names_dict and z in names_dict:
            return [
                OrderClue("before", names_dict[y], names_dict[x], None, clause),
                OrderClue("before", names_dict[z], names_dict[x], None, clause),
            ]
        return None

    # Compound pattern in Tuning Dev Group 2 prose:
    # "{X} crossed the finish line directly ahead of {Y}, but also placed (\d+) spots ahead of {Z} with 1 runner separating them"
    m_but_also = re.fullmatch(
        r"([A-Za-z]+)\s+crossed\s+the\s+finish\s+line\s+directly\s+ahead\s+of\s+([A-Za-z]+),\s+but\s+also\s+placed\s+(\d+)\s+spots\s+ahead\s+of\s+([A-Za-z]+)\s+with\s+\d+\s+runner\s+separating\s+them",
        clause,
        re.I,
    )
    if m_but_also:
        x, y, k, z = m_but_also.group(1).casefold(), m_but_also.group(2).casefold(), int(m_but_also.group(3)), m_but_also.group(4).casefold()
        if x in names_dict and y in names_dict and z in names_dict and 1 <= k < n:
            return [
                OrderClue("immediately_before", names_dict[x], names_dict[y], 1, clause),
                OrderClue("gap", names_dict[x], names_dict[z], k, clause),
            ]
        return None

    # Compound pattern in Tuning Dev Group 2 prose:
    # "{X} came in after {Y} and crossed the line before {Z}"
    m_and_cross = re.fullmatch(
        r"([A-Za-z]+)\s+came\s+in\s+after\s+([A-Za-z]+)\s+and\s+crossed\s+the\s+line\s+before\s+([A-Za-z]+)",
        clause,
        re.I,
    )
    if m_and_cross:
        x, y, z = m_and_cross.group(1).casefold(), m_and_cross.group(2).casefold(), m_and_cross.group(3).casefold()
        if x in names_dict and y in names_dict and z in names_dict:
            return [
                OrderClue("before", names_dict[y], names_dict[x], None, clause),
                OrderClue("before", names_dict[x], names_dict[z], None, clause),
            ]
        return None

    # Standard Immediately Before:
    # "{X} (finished immediately before|arrived directly ahead of|placed immediately before|finished right before|crossed the finish line right before) {Y}"
    imm_before = re.fullmatch(
        r"([A-Za-z]+)\s+(?:finished|arrived|placed|crossed\s+the\s+finish\s+line)\s+"
        r"(?:immediately\s+before|directly\s+ahead\s+of|immediately\s+ahead\s+of|right\s+before)\s+([A-Za-z]+)",
        clause,
        re.I,
    )
    if imm_before:
        x, y = imm_before.group(1).casefold(), imm_before.group(2).casefold()
        if x in names_dict and y in names_dict and x != y:
            return [OrderClue("immediately_before", names_dict[x], names_dict[y], 1, clause)]
        return None

    # Standard Gap:
    # "{X} (crossed the finish line|crossed the line|arrived|placed|finished) (?:exactly )?(\d+) (?:spots|positions|places) ahead of {Y}..."
    gap = re.fullmatch(
        r"([A-Za-z]+)\s+(?:crossed\s+the\s+finish\s+line|crossed\s+the\s+line|arrived|placed|finished)\s+"
        r"(?:exactly\s+)?(\d+)\s+(?:spots|positions|places)\s+ahead\s+of\s+([A-Za-z]+)"
        r"(?:,?\s*(?:with|leaving)\s+(?:exactly\s+)?(?:\d+)\s+runners?\s+(?:between\s+them|separating\s+them))?",
        clause,
        re.I,
    )
    if gap:
        x, k_str, y = gap.group(1).casefold(), gap.group(2), gap.group(3).casefold()
        k = int(k_str)
        if x in names_dict and y in names_dict and x != y and 1 <= k < n:
            return [OrderClue("gap", names_dict[x], names_dict[y], k, clause)]
        return None

    # General Before:
    # "{X} (crossed the finish line ahead of|placed ahead of|finished ahead of|arrived ahead of|finished before) {Y}"
    bef = re.fullmatch(
        r"([A-Za-z]+)\s+(?:crossed\s+the\s+finish\s+line\s+ahead\s+of|placed\s+ahead\s+of|finished\s+ahead\s+of|arrived\s+ahead\s+of|finished\s+before)\s+([A-Za-z]+)",
        clause,
        re.I,
    )
    if bef:
        x, y = bef.group(1).casefold(), bef.group(2).casefold()
        if x in names_dict and y in names_dict and x != y:
            return [OrderClue("before", names_dict[x], names_dict[y], None, clause)]
        return None

    # General After:
    # "{X} (came in after|finished after|finished behind) {Y}"
    aft = re.fullmatch(
        r"([A-Za-z]+)\s+(?:came\s+in\s+after|finished\s+after|finished\s+behind)\s+([A-Za-z]+)",
        clause,
        re.I,
    )
    if aft:
        x, y = aft.group(1).casefold(), aft.group(2).casefold()
        if x in names_dict and y in names_dict and x != y:
            # X after Y means Y finished before X
            return [OrderClue("before", names_dict[y], names_dict[x], None, clause)]
        return None

    return None


def parse_order_query_extended(query: str) -> OrderConstraintIR | None:
    """Extended rule-based parser tuned strictly on Tuning Dev (Groups 1-3)."""
    if not isinstance(query, str) or len(query) > 8192:
        return None

    runners = _extract_runners(query)
    if runners is None:
        return None
    n = len(runners)
    names_dict = {name.casefold(): name for name in runners}

    ask_rank = _extract_ask_rank(query)
    if ask_rank is None or not (1 <= ask_rank <= n):
        return None

    clauses = _segment_clues(query)
    if not clauses:
        return None

    all_clues: list[OrderClue] = []
    for c in clauses:
        parsed_c = _parse_single_clause(c, names_dict, n)
        if parsed_c is None:
            # Fail closed if any clause cannot be parsed
            return None
        all_clues.extend(parsed_c)

    if not all_clues:
        return None

    return OrderConstraintIR(runners, tuple(all_clues), ask_rank, query)
