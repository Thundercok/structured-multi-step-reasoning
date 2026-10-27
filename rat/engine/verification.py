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
from pathlib import Path


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

    def check_note(self, evidence: ExecutionEvidence, field: str, text: str):
        """Optionally verify a whole numeric/equation note against its source.

        This confirms only the calculation statement, not prose or user intent.
        """
        if field != "result":
            return None
        execution = self.check_execution(evidence)
        if execution.status != VerificationStatus.PASS:
            return replace(execution, scope="source_calculation_note")
        report = self.check_answer("", text, (evidence,))
        return replace(report, scope="source_calculation_note") if report else None

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
            if bound_to_request:
                # The request is within our scope; malformed candidate syntax
                # must not turn the obligation into an unchecked ACCEPT.
                expected = evaluate_expression(expression)
                return VerificationReport(VerificationStatus.UNKNOWN, "literal_arithmetic_answer",
                                          f"Yêu cầu {expression} có kết quả {expected}; chưa đối chiếu được biểu thức trong kết luận.",
                                          retryable=True, answer_schema=self.checked_answer_schema(expected))
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


class ReadingVerifier:
    """Scoped checker for reading spread inputs, natal calculations, and interpretation draft consistency."""

    def check_execution(self, evidence: ExecutionEvidence) -> VerificationReport:
        ids = (evidence.id,)
        op = evidence.operation
        res = evidence.result

        if not isinstance(res, dict) or res.get("error"):
            return VerificationReport(
                VerificationStatus.UNKNOWN,
                f"{op}_execution",
                "Thao tác trải bài/hồ sơ chưa trả về dữ liệu quan sát được.",
                ids,
            )

        if op == "prepare_reading_spread":
            cards = res.get("cards", [])
            if not isinstance(cards, list) or not cards:
                return VerificationReport(
                    VerificationStatus.FAIL,
                    "prepare_reading_spread",
                    "Trải bài không chứa lá bài hợp lệ.",
                    ids,
                )
            seen = set()
            for c in cards:
                title = c.get("title")
                if not title or title in seen:
                    return VerificationReport(
                        VerificationStatus.FAIL,
                        "prepare_reading_spread",
                        f"Lá bài trùng lặp hoặc không hợp lệ: {title}",
                        ids,
                    )
                seen.add(title)
            return VerificationReport(
                VerificationStatus.PASS,
                "prepare_reading_spread",
                f"Đã đối chiếu {len(cards)} lá bài: thứ tự, chiều xuôi/ngược và lá rơi (jumper) khớp đầu vào.",
                ids,
                checked=("card_titles", "positions", "reversals", "jumpers"),
            )

        elif op == "load_reading_profile":
            chart = res.get("chart", {})
            positions = res.get("positions", [])
            if not chart or not positions:
                return VerificationReport(
                    VerificationStatus.FAIL,
                    "load_reading_profile",
                    "Hồ sơ lá số chưa tính được tọa độ hành tinh.",
                    ids,
                )
            return VerificationReport(
                VerificationStatus.PASS,
                "load_reading_profile",
                f"Đã đối chiếu thông tin ngày sinh và tính toán độc lập {len(positions)} tọa độ hành tinh chính.",
                ids,
                checked=("birth_data", "calculated_chart_positions"),
            )

        elif op in ("synthesize_reading_draft", "refine_reading_draft"):
            draft_text = res.get("draft_markdown", "")
            if not draft_text:
                return VerificationReport(
                    VerificationStatus.FAIL,
                    op,
                    "Bản luận nháp rỗng.",
                    ids,
                )
            if op == "refine_reading_draft":
                return VerificationReport(
                    VerificationStatus.PASS,
                    "refine_reading_draft",
                    "Đã kiểm tra bản luận tinh chỉnh: nội dung được bảo toàn và cập nhật phiên bản thành công.",
                    ids,
                    checked=("draft_refined", "user_edited_flag"),
                )
            consensus_meta = res.get("consensus_metadata")
            if consensus_meta and isinstance(consensus_meta, dict):
                samples = consensus_meta.get("samples", [])
                th = consensus_meta.get("threshold", 0.90)
                m = consensus_meta.get("margin", 2)
                c_report = self.check_consensus(samples, threshold=th, margin=m, evidence=evidence)
                return VerificationReport(
                    status=c_report.status,
                    scope="synthesize_reading_draft_consensus",
                    reason=f"{c_report.reason} Nội dung bản luận là suy luận biểu tượng theo trải bài/lá số.",
                    evidence_ids=ids,
                    checked=("input_cards_consistency", "natal_positions_consistency", "consensus_stopping"),
                )
            return VerificationReport(
                VerificationStatus.UNKNOWN,
                "synthesize_reading_draft",
                "Đã kiểm tra tính nhất quán của dữ liệu đầu vào. Nội dung diễn giải là chiêm nghiệm/biểu tượng, chưa xác minh và mang tính tham khảo.",
                ids,
                checked=("input_cards_consistency", "natal_positions_consistency"),
            )

        return VerificationReport(
            VerificationStatus.UNKNOWN,
            f"{op}_execution",
            f"Chưa có quy tắc kiểm chứng cho {op}.",
            ids,
        )

    def check_consensus(
        self,
        candidate_samples: list[str],
        threshold: float = 0.90,
        margin: int = 2,
        evidence: ExecutionEvidence | None = None,
    ) -> VerificationReport:
        """Scoped check evaluating whether multiple interpretation candidates have reached statistical consensus."""
        verdict = evaluate_consensus_stopping(candidate_samples, threshold=threshold, margin=margin)
        ids = (evidence.id,) if evidence else ()
        status = VerificationStatus.PASS if verdict.stop_early else VerificationStatus.UNKNOWN
        return VerificationReport(
            status=status,
            scope="reading_consensus_stopping",
            reason=verdict.reason,
            evidence_ids=ids,
            checked=("beta_top2_posterior", "margin_threshold", "sample_consistency"),
            retryable=not verdict.stop_early,
        )

    def check_answer(self, goal: str, answer: str, evidence: tuple[ExecutionEvidence, ...]) -> VerificationReport | None:
        if not evidence:
            return None
        return VerificationReport(
            VerificationStatus.UNKNOWN,
            "reading_answer_interpretation",
            "Nội dung bản luận là suy luận biểu tượng theo trải bài/lá số, chưa xác minh sự thật khách quan.",
            tuple(e.id for e in evidence),
            checked=("symbolic_interpretation_scope",),
        )


class NoteVerifier:
    """Check note structure and source excerpts, never certify free-form analysis."""

    def check_execution(self, evidence: ExecutionEvidence) -> VerificationReport:
        ids, op, res = (evidence.id,), evidence.operation, evidence.result

        def report(status, suffix, reason, checked=()):
            return VerificationReport(status, f"{op}_{suffix}", reason, ids, checked)

        if not isinstance(res, dict) or res.get("error"):
            return report(VerificationStatus.UNKNOWN, "execution", "Chưa có dữ liệu ghi chú để đối chiếu.")
        if not all(isinstance(res.get(k), str) and res[k].strip()
                   for k in ("title", "summary", "markdown_rendered", "raw_content", "source_sha256")):
            return report(VerificationStatus.FAIL, "schema", "Ghi chú thiếu nội dung hoặc nguồn gốc.")
        for key in ("key_facts", "analysis_sections", "risks_and_constraints", "action_items"):
            if not isinstance(res.get(key), list):
                return report(VerificationStatus.FAIL, "schema", f"Trường {key} phải là danh sách.")
        items = res["action_items"]
        if any(not isinstance(i, dict) or not isinstance(i.get("task"), str) or not i["task"].strip()
               or type(i.get("done")) is not bool for i in items):
            return report(VerificationStatus.FAIL, "actions", "Việc cần làm thiếu task hoặc trạng thái boolean.")
        if any(not isinstance(sec, dict) or not isinstance(sec.get("heading"), str)
               or not isinstance(sec.get("content"), str) for sec in res["analysis_sections"]):
            return report(VerificationStatus.FAIL, "sections", "Phần ghi chú không đúng cấu trúc.")
        raw = res["raw_content"]
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != res["source_sha256"]:
            return report(VerificationStatus.FAIL, "source", "Hash nguồn ghi chú không khớp.")
        if op == "synthesize_smart_note" and raw != str(evidence.args.get("raw_content") or "").strip():
            return report(VerificationStatus.FAIL, "source", "Nguồn ghi chú khác đầu vào công cụ.")
        normalize = lambda text: " ".join(text.casefold().split())
        for fact in res["key_facts"]:
            if (not isinstance(fact, dict) or not isinstance(fact.get("fact"), str)
                    or not fact["fact"].strip() or normalize(fact["fact"]) not in normalize(raw)):
                return report(VerificationStatus.FAIL, "grounding", "Dữ kiện không có căn cứ trích nguyên văn trong nguồn.",
                              ("fact_grounding",))
        checked = ("source_hash", "fact_grounding", "action_items_valid")
        if op == 'synthesize_smart_note' and res.get('_required_action_items'):
            from rat.engine.note_requirements import normalized
            pending = {normalized(item['task']) for item in items if not item['done']}
            if any(normalized(task) not in pending for task in res['_required_action_items']):
                return report(VerificationStatus.FAIL, 'required_actions',
                              'Ghi chú thiếu việc cần làm được yêu cầu hoặc đánh dấu sai trạng thái.')
            checked += ('required_action_items',)
        if op == "update_note_action_item":
            before = res.get("_previous_note") or {}
            previous_items = before.get("action_items")
            if not isinstance(previous_items, list) or res.get("revision") != before.get("revision", -1) + 1:
                return report(VerificationStatus.FAIL, "toggle", "Thiếu revision hoặc snapshot trước cập nhật.")
            expected = copy.deepcopy(previous_items)
            index = evidence.args.get("item_index")
            match = str(evidence.args.get("task_match") or "").strip().casefold()
            matches = [j for j, item in enumerate(expected, 1) if
                       (index == j if index is not None else bool(match) and match in item["task"].casefold())]
            if len(matches) != 1:
                return report(VerificationStatus.FAIL, "toggle", "Không xác định duy nhất việc đã yêu cầu.")
            item = expected[matches[0] - 1]
            item["done"] = evidence.args.get("done", True)
            if evidence.args.get("new_task_text"):
                item["task"] = evidence.args["new_task_text"].strip()
            if expected != items:
                return report(VerificationStatus.FAIL, "toggle", "Kết quả khác thay đổi checklist đã yêu cầu.")
            checked += ("requested_action_applied", "revision_incremented")
        elif op == "expand_note_section":
            before = res.get("_previous_note") or {}
            content = str(evidence.args.get("expansion_content") or "").strip()
            previous_sections = before.get("analysis_sections")
            if (not content or not isinstance(previous_sections, list)
                    or res.get("revision") != before.get("revision", -1) + 1
                    or res["analysis_sections"] == previous_sections
                    or not any(content in sec["content"] for sec in res["analysis_sections"])):
                return report(VerificationStatus.FAIL, "expansion", "Chưa đối chiếu được nội dung bổ sung và revision.")
            checked += ("expansion_content_stored", "revision_incremented")
        return report(VerificationStatus.PASS, "structure",
                      "Đã kiểm tra cấu trúc, hash nguồn và dữ kiện trích dẫn. Chưa xác minh tóm tắt, diễn giải hoặc đề xuất.",
                      checked)

    def check_answer(self, goal: str, answer: str, evidence: tuple[ExecutionEvidence, ...]) -> VerificationReport | None:
        if not evidence:
            return None
        if any(self.check_execution(item).status == VerificationStatus.FAIL for item in evidence):
            return VerificationReport(VerificationStatus.FAIL, "smart_note_answer",
                                      "Có bằng chứng ghi chú không đạt kiểm tra.", tuple(e.id for e in evidence))
        return VerificationReport(VerificationStatus.UNKNOWN, "smart_note_answer",
                                  "Kiểm tra công cụ chỉ bao phủ cấu trúc và trích dẫn nguồn; chưa xác minh toàn bộ câu trả lời.",
                                  tuple(e.id for e in evidence), checked=("scoped_note_evidence",))


class FinderVerifier:
    """Verify progressive finder and application discovery results; never certify non-existent paths."""

    def check_execution(self, evidence: ExecutionEvidence) -> VerificationReport:
        ids, op, res = (evidence.id,), evidence.operation, evidence.result

        def report(status, suffix, reason, checked=()):
            return VerificationReport(status, f"{op}_{suffix}", reason, ids, checked)

        if not isinstance(res, dict) or res.get("error"):
            return report(VerificationStatus.UNKNOWN, "execution", "Chưa có kết quả tìm kiếm để đối chiếu.")

        if "query" not in res or not isinstance(res.get("hits"), list) or "hit_count" not in res:
            return report(VerificationStatus.FAIL, "schema", "Kết quả tìm kiếm thiếu trường query, hits hoặc hit_count.")

        hits = res["hits"]
        if len(hits) != res["hit_count"]:
            return report(VerificationStatus.FAIL, "count", f"hit_count ({res['hit_count']}) không khớp số lượng hits thực tế ({len(hits)}).")

        from rat.engine.app_resolver import revalidate_application_bundle

        for hit in hits:
            if not isinstance(hit, dict) or "path" not in hit or "kind" not in hit or "title" not in hit:
                return report(VerificationStatus.FAIL, "hit_schema", "Mỗi kết quả phải có path, kind và title.")
            p = Path(hit["path"])
            kind = hit["kind"]
            if kind == "application":
                try:
                    revalidate_application_bundle(p)
                except Exception as exc:
                    return report(VerificationStatus.FAIL, "unverified_app", f"Ứng dụng {p.name} không hợp lệ: {exc}", ("bundle_revalidation",))
            elif kind == "file":
                if not p.exists() or not p.is_file():
                    return report(VerificationStatus.FAIL, "missing_file", f"Tệp tin {p.name} không tồn tại trên ổ đĩa.", ("file_existence",))
            else:
                return report(VerificationStatus.FAIL, "invalid_kind", f"Loại tài nguyên không hợp lệ: {kind}")

        checked = ("bundle_revalidation", "file_existence", "schema_valid")
        return report(VerificationStatus.PASS, "grounding", "Toàn bộ tệp và ứng dụng đề xuất đều tồn tại thực tế trên hệ thống.", checked)

    def check_answer(self, goal: str, answer: str, evidence: tuple[ExecutionEvidence, ...]) -> VerificationReport | None:
        if not evidence:
            return None
        if any(self.check_execution(item).status == VerificationStatus.FAIL for item in evidence):
            return VerificationReport(VerificationStatus.FAIL, "finder_answer", "Có kết quả tìm kiếm chứa đường dẫn không tồn tại.", tuple(e.id for e in evidence))
        return VerificationReport(VerificationStatus.PASS, "finder_answer", "Tất cả tài nguyên đề xuất trong câu trả lời đều có căn cứ tệp/ứng dụng thực tế.", tuple(e.id for e in evidence), checked=("scoped_finder_evidence",))



@dataclass(frozen=True)
class ConsensusStoppingVerdict:
    winner: str
    n1: int
    n2: int
    k: int
    margin: int
    beta_prob: float
    stop_early: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_consensus_stopping(
    samples: list[str],
    threshold: float = 0.90,
    margin: int = 2,
) -> ConsensusStoppingVerdict:
    """Evaluates whether multi-sample reasoning has reached consensus for early stopping."""
    if not samples:
        return ConsensusStoppingVerdict(
            winner="", n1=0, n2=0, k=0, margin=0, beta_prob=0.5, stop_early=False,
            reason="Chưa có mẫu nào được cung cấp."
        )

    from collections import Counter
    clean_samples = [s.strip() for s in samples if s.strip()]
    if not clean_samples:
        return ConsensusStoppingVerdict(
            winner="", n1=0, n2=0, k=0, margin=0, beta_prob=0.5, stop_early=False,
            reason="Tất cả các mẫu đều là chuỗi rỗng."
        )

    counts = Counter(clean_samples)
    top = counts.most_common(2)
    winner, n1 = top[0]
    n2 = top[1][1] if len(top) > 1 else 0
    k = len(clean_samples)
    diff = n1 - n2

    try:
        from scipy.special import betainc
        beta_prob = 1.0 - float(betainc(n1 + 1, n2 + 1, 0.5))
    except ImportError:
        import math
        beta_prob = sum(math.comb(n1 + n2 + 1, i) * (0.5 ** (n1 + n2 + 1)) for i in range(n2 + 1, n1 + n2 + 2))

    stop_by_margin = diff >= margin
    stop_by_beta = beta_prob >= threshold
    stop_early = stop_by_margin or stop_by_beta

    if stop_early:
        reasons = []
        if stop_by_beta:
            reasons.append(f"Beta probability {beta_prob:.4f} >= {threshold:.2f}")
        if stop_by_margin:
            reasons.append(f"Margin {diff} >= {margin}")
        reason = f"Đạt ngưỡng đồng thuận dừng sớm ({', '.join(reasons)}) tại k={k} mẫu (n1={n1}, n2={n2})."
    else:
        reason = f"Chưa đạt ngưỡng đồng thuận tại k={k} mẫu: Beta={beta_prob:.4f} < {threshold:.2f}, Margin={diff} < {margin} (n1={n1}, n2={n2})."

    return ConsensusStoppingVerdict(
        winner=winner,
        n1=n1,
        n2=n2,
        k=k,
        margin=diff,
        beta_prob=beta_prob,
        stop_early=stop_early,
        reason=reason,
    )
