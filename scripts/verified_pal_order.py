"""Query-Derived Certificate Verifier for Logic Ordering Tasks.

Pure offline, fail-closed verification of witness certificates produced by PAL.
Does NOT access ground truth labels or item['meta']. Parses query text into a
Constraint IR and validates the candidate permutation and final answer.
The generic default also solves the parsed constraints to establish uniqueness
of the asked occupant. This is not a witness-only constant-cost verifier.
"""

from __future__ import annotations

import ast
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


_QUERY = re.compile(
    r"\s*([2-8])\s+runners\s*\(([A-Za-z]+(?:\s*,\s*[A-Za-z]+)+)\)"
    r"\s+ran\s+a\s+race\s+with\s+no\s+ties\.\s*Clues:\s*(.+)\."
    r"\s*Who\s+finished\s+in\s+([1-8](?:st|nd|rd|th))\s+place\?\s*",
    re.I | re.S,
)


def parse_order_query(query: str) -> OrderConstraintIR | None:
    """Consume the entire supported template; no clause is silently dropped."""
    if not isinstance(query, str) or len(query) > 8192:
        return None
    match = _QUERY.fullmatch(query)
    if match is None:
        return None
    n = int(match[1])
    runners = tuple(name.strip() for name in match[2].split(","))
    if not 2 <= n <= 8 or len(runners) != n or len({name.casefold() for name in runners}) != n:
        return None
    names = {name.casefold(): name for name in runners}
    rank = _ORD_MAP.get(match[4].lower())
    if rank is None or rank > n:
        return None
    clauses = [text.strip() for text in match[3].split(";")]
    if not clauses or any(not text for text in clauses):
        return None
    clues = []
    for text in clauses:
        relation = re.fullmatch(
            r"([A-Za-z]+)\s+finished\s+(immediately\s+before|immediately\s+after|before|after)\s+([A-Za-z]+)",
            text, re.I,
        )
        if relation:
            x, y = relation[1].casefold(), relation[3].casefold()
            kind = " ".join(relation[2].lower().split())
            if kind.endswith("after"):
                x, y = y, x
            offset = 1 if kind.startswith("immediately") else None
            clue_type = "immediately_before" if offset else "before"
        else:
            gap_b = re.fullmatch(
                r"([A-Za-z]+)\s+finished\s+(\d+)\s+places\s+ahead\s+of\s+([A-Za-z]+):"
                r"\s*if\s+\1\s+is\s+in\s+position\s+p,\s*then\s+\3\s+is\s+in\s+position\s+p\+(\d+)",
                text, re.I,
            )
            gap_a = re.fullmatch(
                r"([A-Za-z]+)\s+finished\s+exactly\s+(\d+)\s+places\s+ahead\s+of\s+([A-Za-z]+),"
                r"\s*with\s+exactly\s+(\d+)\s+runners?\s+between\s+them",
                text, re.I,
            )
            gap = gap_b or gap_a
            if gap is None:
                return None
            if len(gap[2]) > 1 or len(gap[4]) > 1:
                return None
            x, y, offset = gap[1].casefold(), gap[3].casefold(), int(gap[2])
            other = int(gap[4]) if gap_b else int(gap[4]) + 1
            if not 1 <= offset < n or offset != other:
                return None
            clue_type = "gap"
        if x not in names or y not in names or x == y:
            return None
        clues.append(OrderClue(clue_type, names[x], names[y], offset, text))
    return OrderConstraintIR(runners, tuple(clues), rank, query)


@dataclass(frozen=True)
class OrderSolveResult:
    status: str  # solved, ambiguous, unsatisfiable, unsupported
    answer: str | None = None
    order: tuple[str, ...] | None = None
    solution_count: int = 0
    assignments_checked: int = 0


def solve_order_ir(ir: OrderConstraintIR) -> OrderSolveResult:
    """Exact query-only baseline. Multiple orders may share one asked occupant."""
    occupants: set[str] = set()
    witness = None
    count, checked = 0, 0
    pos: dict[str, int] = {}

    def partial_holds():
        for clue in ir.clues:
            px, py = pos.get(clue.runner_x), pos.get(clue.runner_y)
            if px is None or py is None:
                continue
            if clue.clue_type == "before" and px >= py:
                return False
            if clue.clue_type in ("immediately_before", "gap") and py - px != clue.offset:
                return False
        return True

    def visit(order):
        nonlocal witness, count, checked
        if len(occupants) > 1:
            return
        if len(order) == len(ir.runners):
            count += 1
            occupants.add(order[ir.ask_rank - 1])
            if witness is None:
                witness = order
            return
        for name in ir.runners:
            if name in pos:
                continue
            checked += 1
            pos[name] = len(order) + 1
            if partial_holds():
                visit((*order, name))
            del pos[name]
            if len(occupants) > 1:
                return

    visit(())
    if not occupants:
        return OrderSolveResult("unsatisfiable", assignments_checked=checked)
    if len(occupants) > 1:
        return OrderSolveResult("ambiguous", solution_count=count, assignments_checked=checked)
    return OrderSolveResult("solved", next(iter(occupants)), witness, count, checked)


def solve_order_query(query: str) -> OrderSolveResult:
    """Return only an entailed occupant; abstain on ambiguous/unsupported input."""
    ir = parse_order_query(query)
    return OrderSolveResult("unsupported") if ir is None else solve_order_ir(ir)


def _unique_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate certificate key")
        result[key] = value
    return result


def extract_order_certificate(raw: Any) -> dict[str, Any] | None:
    """Decode a whole execution payload; never search source code for a witness."""
    if isinstance(raw, dict):
        return raw if set(raw) == {"order", "answer"} else None
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 16384:
        return None
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence[1]
    try:
        data = json.loads(text, object_pairs_hook=_unique_json_keys)
    except (ValueError, RecursionError):
        try:
            tree = ast.parse(text, mode="eval")
            if not isinstance(tree.body, ast.Dict):
                return None
            keys = [ast.literal_eval(key) for key in tree.body.keys]
            if len(keys) != len(set(keys)):
                return None
            data = ast.literal_eval(tree)
        except (ValueError, TypeError, SyntaxError, RecursionError):
            return None
    return data if isinstance(data, dict) and set(data) == {"order", "answer"} else None


def verify_order_certificate(
    query: str,
    raw_or_cert: Any,
    *, require_unique_answer: bool = True,
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

    if not all(isinstance(name, str) for name in order):
        return OrderVerificationResult(
            OrderVerificationStatus.INVALID, "order_runner_not_a_string", ir, cert,
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
    clean_ans = answer
    if not isinstance(answer, str) or clean_ans != expected_answer:
        return OrderVerificationResult(
            status=OrderVerificationStatus.INVALID,
            reason=f"answer_mismatch: asked rank {ir.ask_rank} is {expected_answer}, certificate claims {clean_ans}",
            ir=ir,
            certificate=cert,
        )

    if require_unique_answer:
        solved = solve_order_ir(ir)
        if solved.status != "solved":
            return OrderVerificationResult(
                OrderVerificationStatus.UNVERIFIABLE, f"query_{solved.status}", ir, cert,
            )

    return OrderVerificationResult(
        status=OrderVerificationStatus.VALID,
        reason="ok",
        ir=ir,
        certificate=cert,
    )


def verify_order_execution(
    query: str, execution: dict, *, require_unique_answer: bool = True,
) -> OrderVerificationResult:
    """Gate the actual successful result, never a literal in generated source.

    Set require_unique_answer=False only for a release whose unique asked-rank
    guarantee was independently reviewed. The generic default includes solving.
    """
    if not isinstance(execution, dict) or execution.get("ok") is not True:
        return OrderVerificationResult(OrderVerificationStatus.UNVERIFIABLE, "execution_failed")
    if execution.get("finish_reason") == "length":
        return OrderVerificationResult(OrderVerificationStatus.UNVERIFIABLE, "generation_length")
    if execution.get("finish_reason") not in ("stop", "stop_answer"):
        return OrderVerificationResult(OrderVerificationStatus.UNVERIFIABLE, "termination_unrecorded_or_failed")
    return verify_order_certificate(
        query, execution.get("output"), require_unique_answer=require_unique_answer,
    )


def should_escalate(result: OrderVerificationResult) -> bool:
    """Fail-closed policy: escalate unless strictly VALID."""
    return result.status != OrderVerificationStatus.VALID
