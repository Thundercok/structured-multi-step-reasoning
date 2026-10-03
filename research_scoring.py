"""Conservative answer parsing for explicitly typed research items.

Legacy callers keep their old extraction rules. Research collection supplies a
type so expressions and contradictory text cannot be collapsed into a label.
"""

import re
from decimal import Decimal, InvalidOperation


UNITS = r"(?:slices?|boxes?|units?|dollars?|USD|VND|dong|đồng|cm|km|kg|kilograms?|hours?|minutes?|%)"
MARKER = re.compile(r"(?P<outer>\*\*)?answer(?P<label_close>\*\*)?\s*:\s*(?P<candidate>[^\n]+)", re.I)


def _presentation(candidate):
    """Remove whole-answer bold and contiguous repeated labels, not prose."""
    while True:
        before = candidate
        if candidate.startswith("**") and candidate.endswith("**") and len(candidate) > 4:
            candidate = candidate[2:-2].strip()
        repeated = MARKER.fullmatch(candidate)
        if repeated:
            candidate = _marker_candidate(repeated)
        if candidate == before:
            return candidate


def _marker_candidate(match):
    candidate = match.group("candidate").strip()
    # **Answer: Frank** opens before the label and closes after the answer.
    # **Answer**: Frank closes the label before the colon instead.
    if match.group("outer") and not match.group("label_close") and candidate.endswith("**"):
        candidate = candidate[:-2].strip()
    return candidate


def numeric_literal(value, decimal_separator=".", allow_units=False):
    """Parse one whole scalar; locale is declared, never guessed from the gold."""
    if decimal_separator not in (".", ","):
        raise ValueError("decimal_separator must be '.' or ','")
    if decimal_separator == ",":
        number = r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)"
    else:
        number = r"[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
    number += r"(?:[eE][+-]?\d+)?"
    suffix = rf"(?:\s*{UNITS})?\.?" if allow_units else ""
    prefix = r"\$?\s*" if allow_units else ""
    match = re.fullmatch(rf"{prefix}({number}){suffix}", str(value).strip(), re.I)
    if not match:
        return None
    scalar = match.group(1)
    scalar = scalar.replace(",", ".") if decimal_separator == "," else scalar.replace(",", "")
    try:
        result = Decimal(scalar)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def parse_typed_answer(text, answer_type, decimal_separator="."):
    if answer_type not in ("number", "text", "expression"):
        raise ValueError("Unknown research answer type")
    matches = list(MARKER.finditer(text))
    if matches:
        candidate, status = _marker_candidate(matches[-1]), "marker"
    else:
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("```")]
        candidate, status = (lines[-1], "fallback") if lines else ("", "fail")
    candidate = _presentation(candidate)
    if not candidate or re.fullmatch(r"<[^>]+>\.?", candidate):
        return "", "fail", False
    if answer_type == "number":
        scalar = numeric_literal(candidate, decimal_separator, allow_units=True)
        # Keep an invalid candidate intact so the scorer can reject it.
        return (str(scalar), status, False) if scalar is not None else (candidate, "fail", True)
    if answer_type == "expression":
        candidate = candidate.replace("×", "*").replace("÷", "/")
        wordy = not bool(re.fullmatch(r"[\d\s+*/().=\-]+", candidate))
        return candidate, "fail" if wordy else status, wordy
    # A text answer is the whole candidate, never just the first Yes/No/name.
    candidate = candidate.removesuffix(".").strip()
    return candidate, status, len(candidate.split()) > 1


def typed_vote_key(answer, answer_type, decimal_separator="."):
    if answer_type == "number":
        scalar = numeric_literal(answer, decimal_separator, allow_units=True)
        if scalar is not None:
            return str(scalar.normalize()) if scalar else "0"
    if answer_type == "expression":
        return "".join(answer.replace("×", "*").replace("÷", "/").split())
    return " ".join(answer.casefold().split())
