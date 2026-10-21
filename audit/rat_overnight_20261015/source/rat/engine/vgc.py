"""Legacy cascade adapters for input-bound arithmetic and exact source excerpts.

These deterministic helpers do not call a model or establish measured research
quality. The live assistant uses operation verifier contracts in its own loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from rat.engine.context_parser import remove_accents
from reasoning_strategies import run_python_sandboxed, safe_calculate

logger = logging.getLogger("rat.engine.vgc")


class VGCVerificationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNVERIFIABLE = "unverifiable"


@dataclass
class VGCCertificate:
    """Formal witness certificate for an asserted claim."""
    claim: str
    witness: Any
    source_file: Optional[str] = None
    source_page: Optional[int] = None
    source_snippet: Optional[str] = None
    raw_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VGCVerificationResult:
    """Outcome produced by the independent Verifier Gate."""
    status: VGCVerificationStatus
    reason: str
    certificate: Optional[VGCCertificate] = None
    verification_ms: float = 0.0
    scope: str = "source_excerpt"


@dataclass
class VGCCascadeResult:
    """Complete result of a multi-stage Verified Cascade execution."""
    query: str
    answer: str
    strategy: str
    badge: str
    confidence: Optional[float]
    tokens: int
    latency_ms: float
    escalated: bool
    verification: VGCVerificationResult
    reasoning_steps: List[str]
    citations: List[Dict[str, Any]] = field(default_factory=list)


class VGCVerifier:
    """
    Compatibility verifier with explicitly limited calculation/excerpt scopes.
    """

    @staticmethod
    def verify_calculation(certificate: VGCCertificate, target_expr: str) -> VGCVerificationResult:
        """Compatibility adapter to the shared, input-bound arithmetic checker."""
        from rat.engine.verification import CalculationVerifier, ExecutionEvidence, VerificationStatus
        t0 = time.perf_counter()
        if not certificate or certificate.witness is None:
            return VGCVerificationResult(VGCVerificationStatus.UNVERIFIABLE,
                "No numeric witness to check", certificate, scope="calculation")
        if certificate.raw_code:
            ok, output = run_python_sandboxed(certificate.raw_code)
            if not ok or str(output).strip() != str(certificate.witness).strip():
                return VGCVerificationResult(VGCVerificationStatus.INVALID,
                    "Program output does not reproduce the witness", certificate,
                    (time.perf_counter() - t0) * 1000, scope="calculation")
        evidence = ExecutionEvidence("legacy:calculation", "calculate", {"expression": target_expr},
            {"expression": target_expr, "result": certificate.witness}, "")
        checker = CalculationVerifier()
        execution = checker.check_execution(evidence)
        answer = checker.check_answer(target_expr, certificate.claim, (evidence,))
        reports = [execution, *([answer] if answer else [])]
        status = (VGCVerificationStatus.INVALID if any(r.status == VerificationStatus.FAIL for r in reports)
                  else VGCVerificationStatus.UNVERIFIABLE if answer is None or any(r.status == VerificationStatus.UNKNOWN for r in reports)
                  else VGCVerificationStatus.VALID)
        return VGCVerificationResult(status, "; ".join(r.reason for r in reports), certificate,
            (time.perf_counter() - t0) * 1000, scope="calculation")

    @staticmethod
    def verify_document_fact(
        certificate: VGCCertificate,
        source_text: str,
        required_entities: Optional[List[str]] = None
    ) -> VGCVerificationResult:
        """
        Check an exact source excerpt. Semantic entailment is not supported.
        """
        t0 = time.perf_counter()
        if not source_text or not source_text.strip():
            ms = (time.perf_counter() - t0) * 1000.0
            return VGCVerificationResult(
                status=VGCVerificationStatus.UNVERIFIABLE,
                reason="No source document text available to verify against",
                certificate=certificate,
                verification_ms=ms,
            )

        doc_norm = remove_accents(source_text).lower()
        claim_norm = remove_accents(certificate.claim).lower()

        # 1. Audit all numbers in the claim (hallucinated numbers check)
        claim_numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", certificate.claim)
        for num in claim_numbers:
            # Check if number appears in source text
            clean_num = num.replace(",", ".").rstrip(".")
            if clean_num not in doc_norm and num not in source_text:
                ms = (time.perf_counter() - t0) * 1000.0
                return VGCVerificationResult(
                    status=VGCVerificationStatus.INVALID,
                    reason=f"Hallucination detected: Number '{num}' in claim not found in source text",
                    certificate=certificate,
                    verification_ms=ms,
                )

        # 2. Check required entities if specified
        if required_entities:
            missing = []
            for ent in required_entities:
                ent_norm = remove_accents(ent).lower()
                if ent_norm not in doc_norm:
                    missing.append(ent)
            if missing:
                ms = (time.perf_counter() - t0) * 1000.0
                return VGCVerificationResult(
                    status=VGCVerificationStatus.INVALID,
                    reason=f"Contradiction: Required entities {missing} absent from source text",
                    certificate=certificate,
                    verification_ms=ms,
                )

        # 3. Check witness snippet exactness
        if certificate.source_snippet:
            snippet_norm = remove_accents(certificate.source_snippet).lower()
            if certificate.source_snippet not in source_text:
                ms = (time.perf_counter() - t0) * 1000.0
                return VGCVerificationResult(
                    status=VGCVerificationStatus.INVALID,
                    reason="Source snippet could not be aligned with document text",
                    certificate=certificate,
                    verification_ms=ms,
                )

        if not certificate.claim.strip() or certificate.claim not in source_text:
            return VGCVerificationResult(
                status=VGCVerificationStatus.UNVERIFIABLE,
                reason="Only exact source excerpts are supported; semantic relations remain unchecked",
                certificate=certificate,
                verification_ms=(time.perf_counter() - t0) * 1000,
            )
        ms = (time.perf_counter() - t0) * 1000.0
        return VGCVerificationResult(
            status=VGCVerificationStatus.VALID,
            reason="Excerpt matches the supplied source text; relevance and source authenticity are unchecked",
            certificate=certificate,
            verification_ms=ms,
        )


class VGCCascadeEngine:
    """
    Deterministic compatibility cascade; AST rechecking is not model escalation.
    """

    def __init__(self, verifier: Optional[VGCVerifier] = None) -> None:
        self.verifier = verifier or VGCVerifier()

    def solve_quantitative(
        self,
        query: str,
        expr: str,
        python_code: Optional[str] = None
    ) -> VGCCascadeResult:
        """
        Execute VGC on a quantitative or calculations task.
        """
        t0 = time.perf_counter()
        steps = [
            f"Đầu vào phép tính: '{expr}'",
        ]

        # Stage 1: Generate fast witness
        if python_code:
            steps.append("Biên dịch mã Python sandbox để tính toán.")
            ok, val = run_python_sandboxed(python_code)
            raw_val = val if ok else safe_calculate(expr)
        else:
            steps.append("Tính toán qua bộ phân tích cú pháp AST.")
            raw_val = safe_calculate(expr)

        certificate = VGCCertificate(
            claim=str(raw_val),
            witness=raw_val,
            raw_code=python_code,
            metadata={"expr": expr},
        )

        # Stage 2: Verifier Gate
        steps.append("Đối chiếu đầu vào và kết luận bằng checker số học.")
        v_res = self.verifier.verify_calculation(certificate, expr)

        lat_ms = (time.perf_counter() - t0) * 1000.0

        if v_res.status == VGCVerificationStatus.VALID:
            steps.append(f"Phép tính khớp ({v_res.verification_ms:.1f}ms): {v_res.reason}")
            ans = f"Kết quả: **{raw_val}**"
            return VGCCascadeResult(
                query=query,
                answer=ans,
                strategy="VGC-Fast (Verified)",
                badge="Đã đối chiếu phép tính",
                confidence=None,
                tokens=0,
                latency_ms=lat_ms,
                escalated=False,
                verification=v_res,
                reasoning_steps=steps,
            )

        # Stage 3: Escalated Fallback
        steps.append(f"⚠️ Chứng chỉ BỊ TỪ CHỐI: {v_res.reason}")
        steps.append("Tính lại bằng AST và đối chiếu kết quả; bước này không gọi model.")
        corrected_val = safe_calculate(expr)
        corrected = VGCCertificate(str(corrected_val), corrected_val, metadata={"expr": expr})
        corrected_check = self.verifier.verify_calculation(corrected, expr)
        if corrected_check.status == VGCVerificationStatus.VALID:
            v_res = corrected_check
            ans = f"Đã tính lại và đối chiếu phép tính: **{corrected_val}**"
        else:
            ans = "Chưa thể kiểm chứng phép tính này trong phạm vi hiện tại."
        return VGCCascadeResult(
            query=query,
            answer=ans,
            strategy="VGC-AST (Recheck)",
            badge="Đã đối chiếu phép tính" if v_res.status == VGCVerificationStatus.VALID else "Chưa kiểm chứng",
            confidence=None,
            tokens=0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            escalated=False,
            verification=v_res,
            reasoning_steps=steps,
        )

    def solve_document_fact(
        self,
        query: str,
        doc_text: str,
        file_path: str,
        page_num: Optional[int] = None
    ) -> VGCCascadeResult:
        """
        Execute VGC on a document question with strict citation grounding.
        """
        t0 = time.perf_counter()
        file_name = file_path.split("/")[-1] if file_path else "Tài liệu"
        steps = [
            f"Giai đoạn 1 (Fast-W): Trích xuất sự kiện từ tệp `{file_name}`.",
        ]

        # Fast extractive heuristic
        paras = [p.strip() for p in re.split(r"\n{2,}|\r\n{2,}", doc_text) if p.strip()]
        q_norm = remove_accents(query).lower()
        q_words = [w for w in re.findall(r"\w+", q_norm) if len(w) > 2]

        best_para = ""
        best_score = -1
        for p in paras:
            p_norm = remove_accents(p).lower()
            hits = sum(1 for w in q_words if w in p_norm)
            if hits > best_score:
                best_score = hits
                best_para = p

        if not best_para:
            best_para = paras[0] if paras else doc_text[:300]

        steps.append(f"Đoạn trích tiềm năng: \"{best_para[:120]}...\"")

        certificate = VGCCertificate(
            claim=best_para,
            witness=best_para,
            source_file=file_path,
            source_page=page_num or 1,
            source_snippet=best_para[:250],
        )

        # Stage 2: Verifier Gate
        steps.append("Giai đoạn 2 (Verifier Gate): Kiểm chứng thực thể và chống ảo giác.")
        v_res = self.verifier.verify_document_fact(certificate, doc_text)

        lat_ms = (time.perf_counter() - t0) * 1000.0
        citations = [{
            "file_path": file_path,
            "file_name": file_name,
            "page": page_num or 1,
            "snippet": best_para[:220],
        }]

        if v_res.status == VGCVerificationStatus.VALID:
            steps.append(f"✓ Chứng chỉ HỢP LỆ: Đã xác thực thực thể từ nguồn gốc `{file_name}`.")
            ans = (
                f"Dựa trên nội dung trong tệp **`{file_name}`**:\n\n"
                f"> \"{best_para}\"\n\n"
                f"*(Đoạn trích khớp nguồn đã cung cấp)*"
            )
            return VGCCascadeResult(
                query=query,
                answer=ans,
                strategy="VGC-Fast (Grounded)",
                badge="Trích đoạn khớp nguồn",
                confidence=None,
                tokens=0,
                latency_ms=lat_ms,
                escalated=False,
                verification=v_res,
                reasoning_steps=steps,
                citations=citations,
            )

        # Escalation if unverifiable or hallucination detected
        steps.append(f"Chưa đối chiếu được đoạn trích: {v_res.reason}. Bước này không gọi model.")
        ans = (
            f"Trích đoạn liên quan từ **`{file_name}`**:\n\n"
            f"> \"{best_para}\"\n\n"
            f"*(Lưu ý: Đoạn trích cần đối chiếu thêm với ngữ cảnh văn bản)*"
        )
        return VGCCascadeResult(
            query=query,
            answer=ans,
            strategy="VGC-Excerpt (Unchecked)",
            badge="Chưa đối chiếu nguồn",
            confidence=None,
            tokens=0,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            escalated=False,
            verification=v_res,
            reasoning_steps=steps,
            citations=citations,
        )


# Global singleton
vgc_engine = VGCCascadeEngine()
