"""
rat.engine.contradiction_auditor — Monotonic Contradiction Auditor & Step Integrity Guard.

Audits multi-step structured reasoning traces and public answer claims to verify epistemic monotonicity:
1. Grounding Integrity: No reasoning claim or step may contradict facts in authoritative SourceEvidence.
2. Premise Invariance: Once a premise P is established, subsequent steps cannot assert ¬P without formal branching.
3. Numeric & Policy Consistency: Quantities and regulatory bounds must not drift or invert across steps/claims,
   distinguishing thresholds (e.g. minimum requirements) from observed scores, and distinguishing entities.
4. Scope & Coverage: Distinguishes operational execution events from verifiable claims. Reports not_evaluated
   when claims cannot be evaluated against evidence.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("rat.engine.contradiction_auditor")


class ContradictionType(str, Enum):
    GROUNDING_CONFLICT = "grounding_conflict"
    PREMISE_INVERSION = "premise_inversion"
    NUMERIC_COLLISION = "numeric_collision"
    POLICY_VIOLATION = "policy_violation"


@dataclass(frozen=True)
class AuditFinding:
    is_contradiction: bool
    conflict_type: ContradictionType
    step_index: int
    claim: str
    basis: str
    conflicting_source_id: Optional[str] = None
    conflicting_step_index: Optional[int] = None
    severity: str = "blocking"  # "blocking" | "warning"
    explanation: str = ""
    claim_origin: str = "step"  # "step" | "answer"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_contradiction": self.is_contradiction,
            "conflict_type": self.conflict_type.value,
            "step_index": self.step_index,
            "claim": self.claim,
            "basis": self.basis,
            "conflicting_source_id": self.conflicting_source_id,
            "conflicting_step_index": self.conflicting_step_index,
            "severity": self.severity,
            "explanation": self.explanation,
            "claim_origin": self.claim_origin,
        }


@dataclass
class ContradictionReport:
    passed: bool
    findings: List[AuditFinding] = field(default_factory=list)
    monotonicity_score: float = 1.0
    audited_steps_count: int = 0
    source_evidences_count: int = 0
    duration_ms: float = 0.0
    coverage_status: str = "checked"  # "checked" | "not_evaluated" | "no_evidences"
    claims_checked_count: int = 0
    operational_events_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "monotonicity_score": round(self.monotonicity_score, 3),
            "audited_steps_count": self.audited_steps_count,
            "source_evidences_count": self.source_evidences_count,
            "duration_ms": round(self.duration_ms, 2),
            "coverage_status": self.coverage_status,
            "claims_checked_count": self.claims_checked_count,
            "operational_events_count": self.operational_events_count,
        }


# Antonym / Inversion pattern pairs (positive phrase vs negative phrase)
INVERSION_PAIRS: List[Tuple[str, str, str]] = [
    (
        r"\b(?:được phép|có quyền|đủ điều kiện|hợp lệ)\b",
        r"\b(?:không được phép|bị cấm|không đủ điều kiện|không hợp lệ|từ chối)\b",
        "Quyền / Điều kiện thực hiện (Allowed vs Disallowed)",
    ),
    (
        r"\b(?:bắt buộc|phải|tiên quyết)\b",
        r"\b(?:không bắt buộc|tùy chọn|không cần|miễn trừ)\b",
        "Tính bắt buộc (Mandatory vs Optional)",
    ),
    (
        r"\b(?:bị đình chỉ|đình chỉ liên đới|bị hủy kết quả)\b",
        r"\b(?:không làm đình chỉ|không bị đình chỉ|độc lập|không ảnh hưởng)\b",
        "Chế tài đình chỉ (Suspension vs Independence)",
    ),
    (
        r"\b(?:được hoàn|hoàn trả học phí)\b",
        r"\b(?:không được hoàn|không hoàn trả|mất học phí)\b",
        "Hoàn phí học phần (Refund vs Non-refund)",
    ),
    (
        r"\b(?:bị cảnh báo|cảnh báo học vụ)\b",
        r"\b(?:không bị cảnh báo|thoát cảnh báo|an toàn học vụ)\b",
        "Cảnh báo học vụ (Academic probation)",
    ),
]

KNOWN_ENTITIES = [
    "an", "bình", "binh", "cường", "cuong", "dũng", "dung",
    "giang", "hương", "huong", "hùng", "hung", "khoa", "lan",
    "linh", "mai", "minh", "nam", "phúc", "phuc", "quân", "quan",
    "thảo", "thao", "trang", "tuấn", "tuan", "vy"
]


def extract_topic_polarity(text: str, pos_raw: str, neg_raw: str) -> Optional[str]:
    """
    Evaluates the semantic polarity of text against a pos/neg concept pair,
    prioritizing explicit negation qualifiers.
    """
    neg_re = re.compile(neg_raw, re.IGNORECASE)
    has_neg = bool(neg_re.search(text))

    if has_neg:
        return "negative"

    guard = r"(?<!không\s)(?<!chưa\s)(?<!chẳng\s)(?<!không\slàm\s)(?<!không\sbị\s)(?<!không\sđược\s)"
    pos_re = re.compile(f"{guard}{pos_raw}", re.IGNORECASE)
    has_pos = bool(pos_re.search(text))

    if has_pos:
        return "positive"

    return None


def is_operational_event(text: str) -> bool:
    """Distinguishes internal runner execution logs from domain propositions."""
    t = text.strip().lower()
    if re.match(r"^executed\s+(?:cot|planner|strategy|worker|reasoning)", t):
        return True
    if "generated tokens" in t:
        return True
    if "underlying_requests" in t or "dispatched" in t:
        return True
    if t.startswith("telemetry:") or "latency=" in t:
        return True
    return False


def extract_entity(text: str) -> str:
    """Extracts named subject entity if explicitly present; otherwise 'generic'."""
    for name in KNOWN_ENTITIES:
        if re.search(rf"\b(?:sinh viên|học viên|bạn|anh|chị)?\s*{name}\b", text, re.IGNORECASE):
            return name.lower()
    return "generic"


def determine_bound_type(pre_text: str, post_text: str, full_text: str) -> str:
    """Determines if a number in context is a threshold or an observed quantity."""
    pre = pre_text.lower().strip()
    post = post_text.lower().strip()

    # Preceding indicators
    if re.search(r"(?:tối thiểu|ít nhất|yêu cầu|mức tối thiểu|chuẩn đầu ra)\s*(?:toeic|cpa|gpa|là|điểm|từ)?$", pre):
        return "threshold_min"
    if re.search(r"(?:tối đa|không quá|nhiều nhất|mức tối đa)\s*(?:toeic|cpa|gpa|là|điểm|dưới)?$", pre):
        return "threshold_max"
    if re.search(r"(?:đạt|được|có|kết quả|thi được|đạt mức)\s*(?:toeic|cpa|gpa|chứng chỉ|điểm|số)?$", pre):
        return "observed"

    # Post indicators
    if re.search(r"^(?:điểm\s+)?(?:tối thiểu|ít nhất|chuẩn|trở lên)", post):
        return "threshold_min"
    if re.search(r"^(?:điểm\s+)?(?:tối đa|trở xuống)", post):
        return "threshold_max"

    # Broader sentence context fallback
    if "tối thiểu" in pre or "yêu cầu" in pre or "chuẩn đầu ra" in full_text.lower():
        return "threshold_min"
    if "đạt" in pre or "kết quả" in pre:
        return "observed"

    return "observed"


def extract_numeric_facts(text: str) -> List[Dict[str, Any]]:
    """Extracts structured numeric attributes: metric, bound_type, value, entity."""
    facts = []
    entity = extract_entity(text)

    # 1. TOEIC scores
    if re.search(r"\btoeic\b", text, re.IGNORECASE):
        matches = re.finditer(r"(\b\d{3}\b)", text)
        for m in matches:
            val = float(m.group(1))
            if 100 <= val <= 990:
                pre_text = text[max(0, m.start() - 35):m.start()]
                post_text = text[m.end():min(len(text), m.end() + 25)]
                b_type = determine_bound_type(pre_text, post_text, text)
                facts.append({
                    "metric": "toeic",
                    "bound_type": b_type,
                    "value": val,
                    "entity": entity,
                    "raw": m.group(0),
                })

    # 2. CPA / GPA
    if re.search(r"\b(?:cpa|gpa)\b", text, re.IGNORECASE):
        matches = re.finditer(r"(\b\d+(?:\.\d+)?\b)", text)
        for m in matches:
            val = float(m.group(1))
            if 0.0 <= val <= 10.0:
                pre_text = text[max(0, m.start() - 30):m.start()]
                post_text = text[m.end():min(len(text), m.end() + 20)]
                b_type = determine_bound_type(pre_text, post_text, text)
                facts.append({
                    "metric": "gpa",
                    "bound_type": b_type,
                    "value": val,
                    "entity": entity,
                    "raw": m.group(0),
                })

    # 3. Credits (Tín chỉ)
    if re.search(r"\btín chỉ\b", text, re.IGNORECASE):
        matches = re.finditer(r"(\b\d{1,2}\b)\s*tín chỉ", text, re.IGNORECASE)
        for m in matches:
            val = float(m.group(1))
            pre_text = text[max(0, m.start() - 30):m.start()]
            post_text = text[m.end():min(len(text), m.end() + 20)]
            b_type = determine_bound_type(pre_text, post_text, text)
            facts.append({
                "metric": "credits",
                "bound_type": b_type,
                "value": val,
                "entity": entity,
                "raw": m.group(0),
            })

    return facts


class ContradictionAuditor:
    """
    Auditor for reasoning step monotonicity, public answer claims, and source grounding consistency.
    """

    def __init__(self, strict_numeric: bool = True) -> None:
        self.strict_numeric = strict_numeric

    def audit_trace(
        self,
        steps: Sequence[str],
        source_evidences: Optional[Sequence[Any]] = None,
        answer: Optional[str] = None,
    ) -> ContradictionReport:
        t0 = time.time()
        findings: List[AuditFinding] = []
        evidences = list(source_evidences or [])

        claims_to_audit: List[Tuple[int, str, str]] = []  # (index, text, origin)
        operational_events_count = 0

        # Classify steps into claims vs operational logs
        for s_idx, step_text in enumerate(steps):
            step_clean = step_text.strip()
            if not step_clean:
                continue
            if is_operational_event(step_clean):
                operational_events_count += 1
            else:
                claims_to_audit.append((s_idx, step_clean, "step"))

        # Extract answer claims (sentences) if answer is provided
        if answer:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", answer) if s.strip()]
            for a_idx, sent in enumerate(sentences):
                if not is_operational_event(sent):
                    claims_to_audit.append((len(steps) + a_idx, sent, "answer"))

        claims_checked_count = len(claims_to_audit)

        # 1. Audit each claim against authoritative SourceEvidence (Grounding & Numeric)
        for c_idx, claim_text, origin in claims_to_audit:
            for ev in evidences:
                ev_id = getattr(ev, "source_id", "") or (ev.get("source_id", "") if isinstance(ev, dict) else "")
                excerpt = getattr(ev, "excerpt", "") or (ev.get("excerpt", "") if isinstance(ev, dict) else "")
                if not excerpt:
                    continue

                finding = self._check_grounding_conflict(c_idx, claim_text, ev_id, excerpt, origin=origin)
                if finding:
                    findings.append(finding)

                # Check numeric collisions with source evidence
                if self.strict_numeric:
                    num_finding = self._check_numeric_collision(c_idx, claim_text, excerpt, ev_id=ev_id, origin=origin)
                    if num_finding:
                        findings.append(num_finding)

        # 2. Audit step-to-step monotonicity (Premise Inversion between reasoning steps)
        step_claims = [(idx, text) for idx, text, origin in claims_to_audit if origin == "step"]
        for j in range(len(step_claims)):
            idx_j, text_j = step_claims[j]
            for i in range(j):
                idx_i, text_i = step_claims[i]
                inversion = self._check_step_inversion(idx_i, text_i, idx_j, text_j)
                if inversion:
                    findings.append(inversion)

                if self.strict_numeric:
                    num_col = self._check_numeric_collision(idx_j, text_j, text_i, prior_step_idx=idx_i, origin="step")
                    if num_col:
                        findings.append(num_col)

        dur_ms = (time.time() - t0) * 1000.0
        total_items = max(1, len(steps) + (1 if answer else 0))
        score = 1.0 if not findings else max(0.0, 1.0 - (len(findings) / total_items))

        # Coverage status determination
        if not evidences:
            coverage = "no_evidences"
        elif claims_checked_count == 0:
            coverage = "not_evaluated"
        else:
            # Check if any verifiable topic matched between claims and evidences
            any_topic_matched = False
            for _, claim_text, _ in claims_to_audit:
                for ev in evidences:
                    excerpt = getattr(ev, "excerpt", "") or (ev.get("excerpt", "") if isinstance(ev, dict) else "")
                    if self._extract_shared_topics(claim_text, excerpt):
                        any_topic_matched = True
                        break
                if any_topic_matched:
                    break
            coverage = "checked" if any_topic_matched else "not_evaluated"

        return ContradictionReport(
            passed=len(findings) == 0,
            findings=findings,
            monotonicity_score=score,
            audited_steps_count=len(steps),
            source_evidences_count=len(evidences),
            duration_ms=dur_ms,
            coverage_status=coverage,
            claims_checked_count=claims_checked_count,
            operational_events_count=operational_events_count,
        )

    def _check_grounding_conflict(
        self,
        step_idx: int,
        step_text: str,
        ev_id: str,
        excerpt: str,
        origin: str = "step",
    ) -> Optional[AuditFinding]:
        """Detects if claim contradicts source excerpt polarities."""
        shared_topics = self._extract_shared_topics(step_text, excerpt)
        if not shared_topics:
            return None

        target_label = "Nội dung câu trả lời" if origin == "answer" else f"Bước suy luận {step_idx + 1}"

        for pos_raw, neg_raw, desc in INVERSION_PAIRS:
            pol_source = extract_topic_polarity(excerpt, pos_raw, neg_raw)
            pol_step = extract_topic_polarity(step_text, pos_raw, neg_raw)

            if pol_source and pol_step and pol_source != pol_step:
                if pol_source == "negative" and pol_step == "positive":
                    return AuditFinding(
                        is_contradiction=True,
                        conflict_type=ContradictionType.GROUNDING_CONFLICT,
                        step_index=step_idx,
                        claim=step_text,
                        basis=excerpt,
                        conflicting_source_id=ev_id,
                        claim_origin=origin,
                        explanation=f"{target_label} khẳng định điều trái ngược với nguồn căn cứ [{ev_id}]: {desc}",
                    )
                elif pol_source == "positive" and pol_step == "negative":
                    return AuditFinding(
                        is_contradiction=True,
                        conflict_type=ContradictionType.GROUNDING_CONFLICT,
                        step_index=step_idx,
                        claim=step_text,
                        basis=excerpt,
                        conflicting_source_id=ev_id,
                        claim_origin=origin,
                        explanation=f"{target_label} phủ định dữ kiện đã được xác nhận trong nguồn căn cứ [{ev_id}]: {desc}",
                    )
        return None

    def _check_step_inversion(
        self,
        step_i: int,
        text_i: str,
        step_j: int,
        text_j: str,
    ) -> Optional[AuditFinding]:
        """Detects if step j inverts a premise asserted in prior step i."""
        shared_topics = self._extract_shared_topics(text_i, text_j)
        if not shared_topics:
            return None

        for pos_raw, neg_raw, desc in INVERSION_PAIRS:
            pol_i = extract_topic_polarity(text_i, pos_raw, neg_raw)
            pol_j = extract_topic_polarity(text_j, pos_raw, neg_raw)

            if pol_i and pol_j and pol_i != pol_j:
                return AuditFinding(
                    is_contradiction=True,
                    conflict_type=ContradictionType.PREMISE_INVERSION,
                    step_index=step_j,
                    claim=text_j,
                    basis=text_i,
                    conflicting_step_index=step_i,
                    claim_origin="step",
                    explanation=f"Bước {step_j + 1} đảo ngược tiền đề đã xác lập tại Bước {step_i + 1}: {desc}",
                )
        return None

    def _check_numeric_collision(
        self,
        step_idx: int,
        text_claim: str,
        text_basis: str,
        ev_id: Optional[str] = None,
        prior_step_idx: Optional[int] = None,
        origin: str = "step",
    ) -> Optional[AuditFinding]:
        """
        Detects numerical clashing while respecting entity identity and
        threshold vs observed attribute semantics.
        """
        facts_claim = extract_numeric_facts(text_claim)
        facts_basis = extract_numeric_facts(text_basis)

        if not facts_claim or not facts_basis:
            return None

        for fc in facts_claim:
            for fb in facts_basis:
                if fc["metric"] != fb["metric"]:
                    continue

                # 1. Entity boundary: distinct subjects do not collide
                if fc["entity"] != "generic" and fb["entity"] != "generic" and fc["entity"] != fb["entity"]:
                    continue

                # 2. Threshold vs Observed Score boundary
                if fb["bound_type"] == "threshold_min" and fc["bound_type"] == "observed":
                    # Observed score meeting or exceeding threshold is compliant, NOT a collision
                    if fc["value"] >= fb["value"]:
                        continue
                    else:
                        target_label = "Câu trả lời" if origin == "answer" else f"Bước {step_idx + 1}"
                        source_ref = f"nguồn căn cứ [{ev_id}]" if ev_id else f"Bước {prior_step_idx + 1}"
                        return AuditFinding(
                            is_contradiction=True,
                            conflict_type=ContradictionType.NUMERIC_COLLISION,
                            step_index=step_idx,
                            claim=text_claim,
                            basis=text_basis,
                            conflicting_source_id=ev_id,
                            conflicting_step_index=prior_step_idx,
                            claim_origin=origin,
                            explanation=f"{target_label} ghi nhận điểm quan sát ({fc['value']}) không đạt chuẩn tối thiểu của {source_ref} ({fb['value']})",
                        )

                if fb["bound_type"] == "observed" and fc["bound_type"] == "threshold_min":
                    if fb["value"] >= fc["value"]:
                        continue

                # 3. Conflicting thresholds for the same metric
                if fb["bound_type"] == "threshold_min" and fc["bound_type"] == "threshold_min":
                    if fc["value"] != fb["value"]:
                        target_label = "Câu trả lời" if origin == "answer" else f"Bước {step_idx + 1}"
                        source_ref = f"nguồn căn cứ [{ev_id}]" if ev_id else f"Bước {prior_step_idx + 1}"
                        return AuditFinding(
                            is_contradiction=True,
                            conflict_type=ContradictionType.NUMERIC_COLLISION,
                            step_index=step_idx,
                            claim=text_claim,
                            basis=text_basis,
                            conflicting_source_id=ev_id,
                            conflicting_step_index=prior_step_idx,
                            claim_origin=origin,
                            explanation=f"Mâu thuẫn thông số ngưỡng tại {target_label.lower()} ({fc['value']}) so với {source_ref} ({fb['value']})",
                        )

                # 4. Conflicting observed values for the same subject
                if fb["bound_type"] == "observed" and fc["bound_type"] == "observed":
                    if fc["value"] != fb["value"]:
                        target_label = "Câu trả lời" if origin == "answer" else f"Bước {step_idx + 1}"
                        source_ref = f"nguồn căn cứ [{ev_id}]" if ev_id else f"Bước {prior_step_idx + 1}"
                        subject_desc = f" của đối tượng '{fc['entity']}'" if fc["entity"] != "generic" else ""
                        return AuditFinding(
                            is_contradiction=True,
                            conflict_type=ContradictionType.NUMERIC_COLLISION,
                            step_index=step_idx,
                            claim=text_claim,
                            basis=text_basis,
                            conflicting_source_id=ev_id,
                            conflicting_step_index=prior_step_idx,
                            claim_origin=origin,
                            explanation=f"Mâu thuẫn số liệu quan sát{subject_desc} tại {target_label.lower()} ({fc['value']}) so với {source_ref} ({fb['value']})",
                        )

        return None

    def _extract_shared_topics(self, text_a: str, text_b: str) -> Set[str]:
        """Extracts significant overlapping domain topics."""
        a_low = text_a.lower()
        b_low = text_b.lower()
        topics = [
            "đình chỉ", "thạc sĩ", "song bằng", "đại học", "học vượt",
            "tín chỉ", "toeic", "tiếng anh", "cảnh báo học vụ", "rút môn",
            "học phí", "khóa luận", "rèn luyện", "học bổng", "tốt nghiệp",
            "chuẩn đầu ra",
        ]
        shared = {t for t in topics if t in a_low and t in b_low}
        return shared
