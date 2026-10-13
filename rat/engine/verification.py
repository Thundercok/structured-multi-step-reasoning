"""Scoped, headless verification in the existing RAT execution loop.

PASS describes the named check, never the quality of a whole conversation.
Checkers belong to operation contracts; they are not model-selectable tools.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, replace
from enum import Enum
from fractions import Fraction
from typing import Any, Protocol


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VerificationReport:
    status: VerificationStatus
    scope: str
    reason: str
    evidence_ids: tuple[str, ...] = ()
    checked: tuple[str, ...] = ()
    retryable: bool = False
    duration_ms: float = 0.0
    answer_schema: dict | None = None

    def to_dict(self):
        value = asdict(self)
        value["status"] = self.status.value
        return value


@dataclass(frozen=True)
class ExecutionEvidence:
    id: str
    operation: str
    args: dict
    result: Any
    sha256: str


class OperationVerifier(Protocol):
    def check_execution(self, evidence: ExecutionEvidence) -> VerificationReport: ...

    def check_answer(self, goal: str, answer: str,
                     evidence: tuple[ExecutionEvidence, ...]) -> VerificationReport | None: ...


class VerificationSession:
    """Evidence is isolated to one request and snapshotted before checking."""

    def __init__(self, registry, goal: str, request_id: str):
        self.registry, self.goal, self.request_id = registry, goal, request_id
        self.evidence: dict[int, list[ExecutionEvidence]] = {}
        self.reports: list[dict] = []
        self.duration_ms = 0.0

    def _check(self, checker, phase, callback):
        started = time.perf_counter()
        try:
            report = callback()
            if report is not None and (not isinstance(report, VerificationReport)
                    or not isinstance(report.status, VerificationStatus)
                    or not isinstance(report.scope, str) or not report.scope
                    or not isinstance(report.reason, str) or type(report.retryable) is not bool):
                raise TypeError("Verifier returned an invalid report")
        except Exception:
            report = VerificationReport(VerificationStatus.UNKNOWN, "checker_execution",
                                        "Bộ kiểm tra chưa thực hiện được phép đối chiếu này.", retryable=True)
        elapsed = (time.perf_counter() - started) * 1000
        self.duration_ms += elapsed
        if report is None:
            return None
        report = replace(report, duration_ms=elapsed)
        data = {**report.to_dict(), "phase": phase, "checker": type(checker).__name__}
        self.reports.append(data)
        return data

    def observe(self, name, args, result, step_number):
        operation = self.registry.get_operation(name)
        checker = operation.verifier if operation else None
        if checker is None:
            return []
        try:
            snapshot = copy.deepcopy({"args": args, "result": result})
            digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
        except Exception:
            def invalid_evidence():
                raise ValueError("Evidence could not be snapshotted")
            return [self._check(checker, "execution", invalid_evidence)]
        evidence = ExecutionEvidence(f"{self.request_id}:step:{step_number}:{digest[:12]}",
                                     name, snapshot["args"], snapshot["result"], digest)
        self.evidence.setdefault(id(checker), []).append(evidence)
        report = self._check(checker, "execution", lambda: checker.check_execution(evidence))
        return [report] if report else []

    def check_answer(self, answer):
        reports, seen = [], set()
        for operation in self.registry.list_operations():
            checker = operation.verifier
            if checker is None or id(checker) in seen:
                continue
            seen.add(id(checker))
            evidence = tuple(self.evidence.get(id(checker), []))
            report = self._check(checker, "answer", lambda: checker.check_answer(self.goal, answer, evidence))
            if report:
                reports.append(report)
        return reports


def answer_status(reports):
    if any(r["status"] == "FAIL" for r in reports):
        return "FAIL"
    if not reports or any(r["status"] == "UNKNOWN" for r in reports):
        return "UNKNOWN"
    return "PASS"


def verification_action(reports, *, can_continue: bool, repairs: int, repair_limit: int):
    """A correctness guard independent of the fitted utility predictor."""
    blocked = any(r["status"] == "FAIL" or (r["status"] == "UNKNOWN" and r["retryable"])
                  for r in reports)
    if not blocked:
        return "ACCEPT"  # UNKNOWN outside a supported scope stays UNKNOWN.
    if can_continue and repairs < repair_limit:
        return "REPAIR"
    return "REJECT"


def _normalize_expression(text):
    return text.strip().replace("×", "*").replace("÷", "/").replace("−", "-")


def evaluate_expression(expression: str) -> Fraction:
    """Independent rational arithmetic with bounded syntax and intermediates."""
    expression = _normalize_expression(expression)
    if not expression or len(expression) > 512:
        raise ValueError("Expression exceeds the verification budget")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError("Expression exceeds the verification budget")

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            literal = ast.get_source_segment(expression, node)
            exponent = re.search(r"[eE]([+-]?\d+)$", literal)
            if exponent and abs(int(exponent.group(1))) > 1000:
                raise ValueError("Literal exceeds the verification budget")
            value = Fraction(literal)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.Div):
                value = left / right
            elif isinstance(node.op, ast.FloorDiv):
                value = Fraction(left // right)
            elif isinstance(node.op, ast.Mod):
                value = left % right
            elif isinstance(node.op, ast.Pow) and right.denominator == 1 and abs(right) <= 64:
                if max(left.numerator.bit_length(), left.denominator.bit_length()) * abs(right) > 4096:
                    raise ValueError("Power exceeds the verification budget")
                value = left ** int(right)
            else:
                raise ValueError("Unsupported arithmetic")
        else:
            raise ValueError("Unsupported arithmetic")
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
            raise ValueError("Intermediate exceeds the verification budget")
        return value

    return evaluate(tree.body)


def literal_request(goal):
    """Parse only a whole literal expression, not a word-problem interpretation."""
    text = re.sub(r"^(?:tính|calculate|compute|calc|what is)\s*:?\s*", "", goal.strip(), flags=re.I)
    text = _normalize_expression(text.rstrip("? "))
    if len(text) > 512:
        return None
    try:
        tree = ast.parse(text, mode="eval")
        if not isinstance(tree.body, ast.BinOp):
            return None
        # Names, calls and strings are not an explicit numerical request.
        if any(isinstance(n, (ast.Name, ast.Call)) for n in ast.walk(tree)):
            return None
        evaluate_expression(text)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
        return None
    return text


def _answer_value(answer):
    """Whole answer only: never extract a convenient number from prose."""
    if len(answer) > 2048:
        raise ValueError("Answer exceeds verification budget")
    text = answer.strip()
    if text.endswith("."):
        text = text[:-1].strip()
    if text.startswith("**") and text.endswith("**"):
        text = text[2:-2].strip()
    text = re.sub(r"^(?:answer|result|kết quả|đáp án)(?:\s+(?:is|là))?\s*:?\s*", "", text, flags=re.I)
    if text.startswith("**") and text.endswith("**"):
        text = text[2:-2].strip()
    expression = None
    if text.count("=") == 1:
        expression, text = (part.strip() for part in text.split("="))
    if len(text) > 512 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?(?:\s*/\s*[+-]?\d+)?", text):
        raise ValueError("No whole scalar answer")
    value = Fraction(text.replace(" ", ""))
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
        raise ValueError("Answer exceeds verification budget")
    return expression, value


def _same_number(left, right):
    # The runtime calculator may return floating point representations.
    if left.denominator == right.denominator == 1:
        return left == right
    return abs(left - right) <= Fraction(1, 10**9)


class CalculationVerifier:
    """Check an operation result and bind a complete scalar final to its scope."""

    answer_schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "pattern": r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?(?:\s*/\s*[+-]?\d+)?$"}},
        "required": ["answer"],
    }

    def checked_answer_schema(self, expected):
        """A unique formal result can constrain decoding; it is not a learned answer."""
        schema = copy.deepcopy(self.answer_schema)
        schema['properties']['answer']['enum'] = [str(expected)]
        return schema

    def check_execution(self, evidence):
        ids = (evidence.id,)
        expression = evidence.args.get("expression", "")
        result = evidence.result
        if not isinstance(result, dict) or result.get("error"):
            return VerificationReport(VerificationStatus.UNKNOWN, "calculation_execution",
                                      "Phép tính chưa trả về dữ liệu để đối chiếu.", ids)
        if result.get("expression") != expression:
            return VerificationReport(VerificationStatus.FAIL, "calculation_execution",
                                      "Biểu thức trong kết quả khác đầu vào đã thực hiện.", ids)
        try:
            expected = evaluate_expression(expression)
            candidate_expression, candidate = _answer_value(str(result.get("result", "")))
            if candidate_expression is not None:
                raise ValueError("Operation must return a scalar")
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            return VerificationReport(VerificationStatus.UNKNOWN, "calculation_execution",
                                      "Phép tính nằm ngoài phạm vi kiểm tra số học hiện tại.", ids)
        status = VerificationStatus.PASS if _same_number(candidate, expected) else VerificationStatus.FAIL
        return VerificationReport(status, "calculation_execution",
                                  f"Đối chiếu {expression}: công cụ trả {candidate}; tính độc lập được {expected}.",
                                  ids, ("input_expression", "independent_arithmetic", "operation_result"))

    def check_answer(self, goal, answer, evidence):
        expression = literal_request(goal)
        bound_to_request = expression is not None
        source = None
        try:
            answer_expression, candidate = _answer_value(answer)
        except (ValueError, ZeroDivisionError, OverflowError):
            if not bound_to_request:
                return None
            return VerificationReport(VerificationStatus.UNKNOWN, "literal_arithmetic_answer",
                                      f"Đối chiếu {expression} độc lập được {evaluate_expression(expression)}. Chưa đối chiếu được toàn bộ kết luận; cần một kết quả số rõ ràng.",
                                      retryable=True, answer_schema=self.checked_answer_schema(evaluate_expression(expression)))
        if not bound_to_request:
            # Never infer that the model's expression solves a natural-language problem.
            matches = []
            for item in evidence:
                try:
                    if self.check_execution(item).status != VerificationStatus.PASS:
                        continue
                    if answer_expression is not None:
                        if ast.dump(ast.parse(_normalize_expression(answer_expression), mode="eval")) != ast.dump(ast.parse(_normalize_expression(item.args["expression"]), mode="eval")):
                            continue
                    matches.append(item)
                except (ValueError, SyntaxError):
                    continue
            if len(matches) != 1:
                return None
            source = matches[0]
            expression = source.args["expression"]
        try:
            expected = evaluate_expression(expression)
            if answer_expression is not None and ast.dump(ast.parse(_normalize_expression(answer_expression), mode="eval")) != ast.dump(ast.parse(_normalize_expression(expression), mode="eval")):
                return VerificationReport(VerificationStatus.FAIL, "literal_arithmetic_answer",
                                          f"Kết luận dùng biểu thức khác yêu cầu {expression}; đối chiếu được {expected}.",
                                          retryable=True, answer_schema=self.checked_answer_schema(expected))
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            return VerificationReport(VerificationStatus.UNKNOWN, "calculation_answer",
                                      "Chưa thể kiểm chứng biểu thức trong kết luận.")
        status = VerificationStatus.PASS if _same_number(candidate, expected) else VerificationStatus.FAIL
        scope = "literal_arithmetic_answer" if bound_to_request else "calculation_answer_only"
        reason = f"Kết luận {candidate}; đối chiếu {expression} được {expected}."
        if not bound_to_request:
            reason += " Chỉ kiểm tra kết quả phép tính; cách diễn giải đề bài chưa được kiểm chứng."
        return VerificationReport(status, scope, reason, (source.id,) if source else (),
                                  ("whole_scalar_answer", "independent_arithmetic", "request_expression" if bound_to_request else "observed_expression"),
                                  retryable=status == VerificationStatus.FAIL,
                                  answer_schema=self.checked_answer_schema(expected) if status == VerificationStatus.FAIL else None)
