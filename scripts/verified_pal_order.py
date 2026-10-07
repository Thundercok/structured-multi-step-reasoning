"""Query-Derived Certificate Verifier for Logic Ordering Tasks.

Pure offline, fail-closed verification of witness certificates produced by PAL.
Does NOT access ground truth labels or item['meta']. Parses query text into a
Constraint IR and validates the candidate permutation and final answer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OrderVerificationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class OrderClue:
    clue_type: str  # "before", "immediately_before", "gap"
    runner_x: str   # ahead runner
    runner_y: str   # behind runner
    offset: int | None  # 1 for immediately_before, k for gap, None for general before
    raw_text: str


@dataclass(frozen=True)
class OrderConstraintIR:
    runners: tuple[str, ...]
    clues: tuple[OrderClue, ...]
    ask_rank: int  # 1-indexed rank
    raw_query: str


@dataclass(frozen=True)
class OrderVerificationResult:
    status: OrderVerificationStatus
    reason: str
    ir: OrderConstraintIR | None = None
    certificate: dict[str, Any] | None = None


_ORD_MAP = {
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
    "5th": 5, "6th": 6, "7th": 7, "8th": 8,
}


def parse_order_query(query: str) -> OrderConstraintIR | None:
    """Parses raw ordering query text into a structured Constraint IR.

    Returns None (fail-closed) if the query grammar is unrecognized.
    """
    if not query:
        return None

    # 1. Parse runner names from preamble: 'N runners (Name1, Name2, ...) ran a race'
    m_preamble = re.search(r"(\d+)\s+runners\s*\(([^)]+)\)\s+ran\s+a\s+race\s+with\s+no\s+ties", query, re.I)
    if not m_preamble:
        return None

    expected_n = int(m_preamble.group(1))
    runners = tuple(r.strip() for r in m_preamble.group(2).split(",") if r.strip())
    if len(runners) != expected_n or len(set(runners)) != expected_n:
        return None
    runner_set = set(runners)

    # 2. Parse asked position: 'Who finished in {ord} place?'
    m_ask = re.search(r"Who\s+finished\s+in\s+(\d+(?:st|nd|rd|th))\s+place\?", query, re.I)
    if not m_ask:
        return None
    ask_ord = m_ask.group(1).lower()
    if ask_ord not in _ORD_MAP:
        return None
    ask_rank = _ORD_MAP[ask_ord]
    if ask_rank < 1 or ask_rank > expected_n:
        return None

    # 3. Parse Clues section: 'Clues: clue1; clue2; ...'
    m_clues = re.search(r"Clues:\s*(.*?)\.\s*Who\s+finished\s+in", query, re.DOTALL | re.I)
    if not m_clues:
        return None

    clue_texts = [c.strip() for c in m_clues.group(1).split(";") if c.strip()]
    if not clue_texts:
        return None

    parsed_clues: list[OrderClue] = []
    for raw_c in clue_texts:
        c_clean = raw_c.strip()

        # Check: Immediately before: 'X finished immediately before Y'
        m_adj = re.fullmatch(r"([A-Za-z]+)\s+finished\s+immediately\s+before\s+([A-Za-z]+)", c_clean)
        if m_adj:
            x, y = m_adj.group(1), m_adj.group(2)
            if x not in runner_set or y not in runner_set or x == y:
                return None
            parsed_clues.append(OrderClue("immediately_before", x, y, 1, c_clean))
            continue

        # Check: Gap Clue Style B: 'X finished K places ahead of Y: if X is in position p, then Y is in position p+K'
        m_gap_b = re.fullmatch(
            r"([A-Za-z]+)\s+finished\s+(\d+)\s+places\s+ahead\s+of\s+([A-Za-z]+):\s*if\s+\1\s+is\s+in\s+position\s+p,\s*then\s+\3\s+is\s+in\s+position\s+p\+(\d+)",
            c_clean,
        )
        if m_gap_b:
            x, k1, y, k2 = m_gap_b.group(1), int(m_gap_b.group(2)), m_gap_b.group(3), int(m_gap_b.group(4))
            if k1 != k2 or k1 < 1:
                return None
            if x not in runner_set or y not in runner_set or x == y:
                return None
            parsed_clues.append(OrderClue("gap", x, y, k1, c_clean))
            continue

        # Check: Gap Clue Style A: 'X finished exactly K places ahead of Y, with exactly M runner(s) between them'
        m_gap_a = re.fullmatch(
            r"([A-Za-z]+)\s+finished\s+exactly\s+(\d+)\s+places\s+ahead\s+of\s+([A-Za-z]+),\s*with\s+exactly\s+(\d+)\s+runners?\s+between\s+them",
            c_clean,
        )
        if m_gap_a:
            x, k, y, between = m_gap_a.group(1), int(m_gap_a.group(2)), m_gap_a.group(3), int(m_gap_a.group(4))
            if between != k - 1 or k < 1:
                return None
            if x not in runner_set or y not in runner_set or x == y:
                return None
            parsed_clues.append(OrderClue("gap", x, y, k, c_clean))
            continue

        # Check: General Before: 'X finished before Y'
        m_bef = re.fullmatch(r"([A-Za-z]+)\s+finished\s+before\s+([A-Za-z]+)", c_clean)
        if m_bef:
            x, y = m_bef.group(1), m_bef.group(2)
            if x not in runner_set or y not in runner_set or x == y:
                return None
            parsed_clues.append(OrderClue("before", x, y, None, c_clean))
            continue

        # Check: General After: 'Y finished after X' (meaning X finished before Y)
        m_aft = re.fullmatch(r"([A-Za-z]+)\s+finished\s+after\s+([A-Za-z]+)", c_clean)
        if m_aft:
            y, x = m_aft.group(1), m_aft.group(2)
            if x not in runner_set or y not in runner_set or x == y:
                return None
            parsed_clues.append(OrderClue("before", x, y, None, c_clean))
            continue

        # If any clue does not match known grammar, fail closed
        return None

    return OrderConstraintIR(
        runners=runners,
        clues=tuple(parsed_clues),
        ask_rank=ask_rank,
        raw_query=query,
    )


def extract_order_certificate(raw: Any) -> dict[str, Any] | None:
    """Extracts candidate certificate {'order': [...], 'answer': '...'} from raw output or payload.

    Accepts:
    1. A dictionary already containing 'order' and 'answer'
    2. A JSON string or JSON block in raw text
    3. Python dictionary literal in raw text
    """
    if isinstance(raw, dict):
        if "order" in raw and "answer" in raw:
            return raw
        return None

    if not isinstance(raw, str) or not raw.strip():
        return None

    text = raw.strip()

    # 1. Search for JSON block ```json ... ```
    json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for block in reversed(json_blocks):
        try:
            data = json.loads(block)
            if isinstance(data, dict) and "order" in data and "answer" in data:
                return data
        except Exception:
            pass

    # 2. Direct JSON object
    for m in reversed(list(re.finditer(r"\{[^{}]*\"order\"[^{}]*\}", text, re.DOTALL))):
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict) and "order" in data and "answer" in data:
                return data
        except Exception:
            pass

    # 3. Handle result = {"order": [...], "answer": "..."} in code or output
    m_dict = re.search(r"result\s*=\s*(\{[^}]+\})", text)
    if m_dict:
        try:
            # Replace single quotes for json parsing if needed
            s = m_dict.group(1).replace("'", '"')
            data = json.loads(s)
            if isinstance(data, dict) and "order" in data and "answer" in data:
                return data
        except Exception:
            pass

    return None


def verify_order_certificate(
    query: str,
    raw_or_cert: Any,
) -> OrderVerificationResult:
    """Evaluates an ordering witness certificate against the parsed query constraints.

    Returns:
    - VALID: strictly verified, permit early stop and accept answer.
    - INVALID: constraint violated, permutation invalid, or answer mismatch -> escalate.
    - UNVERIFIABLE: parser failed, certificate unextractable, or runtime error -> escalate.
    """
    # 1. Query parser check (fail-closed)
    ir = parse_order_query(query)
    if ir is None:
        return OrderVerificationResult(
            status=OrderVerificationStatus.UNVERIFIABLE,
            reason="query_parser_unsupported_or_failed",
            ir=None,
            certificate=None,
        )

    # 2. Certificate extraction check
    cert = extract_order_certificate(raw_or_cert)
    if cert is None:
        return OrderVerificationResult(
            status=OrderVerificationStatus.UNVERIFIABLE,
            reason="certificate_unextractable_or_missing",
            ir=ir,
            certificate=None,
        )

    order = cert.get("order")
    answer = cert.get("answer")

    # 3. Permutation validation
    if not isinstance(order, (list, tuple)):
        return OrderVerificationResult(
            status=OrderVerificationStatus.INVALID,
            reason="certificate_order_not_a_list",
            ir=ir,
            certificate=cert,
        )

    n_expected = len(ir.runners)
    if len(order) != n_expected:
        return OrderVerificationResult(
            status=OrderVerificationStatus.INVALID,
            reason=f"order_length_mismatch: expected {n_expected}, got {len(order)}",
            ir=ir,
            certificate=cert,
        )

    if set(order) != set(ir.runners):
        missing = set(ir.runners) - set(order)
        extra = set(order) - set(ir.runners)
        return OrderVerificationResult(
            status=OrderVerificationStatus.INVALID,
            reason=f"order_runner_set_mismatch: missing={missing}, extra={extra}",
            ir=ir,
            certificate=cert,
        )

    # 4. Check all relational constraints
    # pos maps runner_name -> 1-indexed rank
    pos = {name: idx + 1 for idx, name in enumerate(order)}

    for clue in ir.clues:
        px = pos[clue.runner_x]
        py = pos[clue.runner_y]

        if clue.clue_type == "immediately_before":
            if py != px + 1:
                return OrderVerificationResult(
                    status=OrderVerificationStatus.INVALID,
                    reason=f"clue_violated: {clue.raw_text} (pos({clue.runner_x})={px}, pos({clue.runner_y})={py})",
                    ir=ir,
                    certificate=cert,
                )
        elif clue.clue_type == "before":
            if px >= py:
                return OrderVerificationResult(
                    status=OrderVerificationStatus.INVALID,
                    reason=f"clue_violated: {clue.raw_text} (pos({clue.runner_x})={px}, pos({clue.runner_y})={py})",
                    ir=ir,
                    certificate=cert,
                )
        elif clue.clue_type == "gap":
            expected_diff = clue.offset
            actual_diff = py - px
            if actual_diff != expected_diff:
                return OrderVerificationResult(
                    status=OrderVerificationStatus.INVALID,
                    reason=f"clue_violated: {clue.raw_text} (expected gap {expected_diff}, got {actual_diff})",
                    ir=ir,
                    certificate=cert,
                )

    # 5. Check answer alignment with asked rank
    expected_answer = order[ir.ask_rank - 1]
    clean_ans = str(answer).strip()
    if clean_ans != expected_answer:
        return OrderVerificationResult(
            status=OrderVerificationStatus.INVALID,
            reason=f"answer_mismatch: asked rank {ir.ask_rank} is {expected_answer}, certificate claims {clean_ans}",
            ir=ir,
            certificate=cert,
        )

    return OrderVerificationResult(
        status=OrderVerificationStatus.VALID,
        reason="ok",
        ir=ir,
        certificate=cert,
    )


def should_escalate(result: OrderVerificationResult) -> bool:
    """Fail-closed policy: escalate unless strictly VALID."""
    return result.status != OrderVerificationStatus.VALID
