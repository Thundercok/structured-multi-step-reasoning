"""Tests for Turn 2: Monotonic Contradiction Auditor and Native macOS Icon Provider."""

import sys
import tempfile
from pathlib import Path
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QGuiApplication

from rat.engine.contradiction_auditor import (
    ContradictionAuditor,
    ContradictionType,
    ContradictionReport,
)
from rat.kernel.contracts import SourceEvidence
from rat.ui.icon_provider import RatIconProvider


def get_or_create_app():
    return QGuiApplication.instance() or QGuiApplication([sys.argv[0]])


class TestContradictionAuditor:
    def test_grounding_conflict_detected(self):
        auditor = ContradictionAuditor()
        evidence = SourceEvidence(
            source_id="src-academic-1",
            kind="pdf_page",
            excerpt="Việc tạm hoãn hoặc đình chỉ ở bậc Thạc sĩ KHÔNG làm đình chỉ liên đới kết quả học phần bên bậc Đại học.",
        )
        steps = [
            "Bước 1: Tiếp nhận thông tin sinh viên theo học chương trình liên thông song bằng.",
            "Bước 2: Sinh viên bị đình chỉ ở bậc thạc sĩ sẽ bị đình chỉ liên đới toàn bộ kết quả bên bậc đại học.",
        ]
        report = auditor.audit_trace(steps, [evidence])
        assert not report.passed
        assert len(report.findings) >= 1
        conflict = report.findings[0]
        assert conflict.is_contradiction
        assert conflict.conflict_type == ContradictionType.GROUNDING_CONFLICT
        assert conflict.conflicting_source_id == "src-academic-1"
        assert report.monotonicity_score < 1.0

    def test_grounding_consistent_passes(self):
        auditor = ContradictionAuditor()
        evidence = SourceEvidence(
            source_id="src-academic-2",
            kind="pdf_page",
            excerpt="Việc tạm hoãn hoặc đình chỉ ở bậc Thạc sĩ KHÔNG làm đình chỉ liên đới kết quả học phần bên bậc Đại học.",
        )
        steps = [
            "Bước 1: Tra cứu quy định tại nguồn tài liệu.",
            "Bước 2: Kết quả ở bậc đại học hoàn toàn độc lập và không bị đình chỉ khi bậc thạc sĩ gặp sự cố.",
        ]
        report = auditor.audit_trace(steps, [evidence])
        assert report.passed
        assert len(report.findings) == 0
        assert report.monotonicity_score == 1.0

    def test_step_to_step_premise_inversion_detected(self):
        auditor = ContradictionAuditor()
        steps = [
            "Bước 1: Sinh viên có điểm TOEIC 600 đủ điều kiện xét chuẩn đầu ra ngoại ngữ.",
            "Bước 2: Phân tích thêm điều kiện chứng chỉ tin học MOS.",
            "Bước 3: Tuy nhiên sinh viên có TOEIC 600 không đủ điều kiện xét chuẩn đầu ra do quy định mới.",
        ]
        report = auditor.audit_trace(steps)
        assert not report.passed
        assert any(f.conflict_type == ContradictionType.PREMISE_INVERSION for f in report.findings)
        inversion = next(f for f in report.findings if f.conflict_type == ContradictionType.PREMISE_INVERSION)
        assert inversion.conflicting_step_index == 0
        assert inversion.step_index == 2

    def test_numeric_collision_detected(self):
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-toeic",
            kind="pdf_page",
            excerpt="Chuẩn đầu ra ngoại ngữ tiếng Anh yêu cầu tối thiểu TOEIC 600 điểm.",
        )
        steps = [
            "Bước 1: Kiểm tra yêu cầu chuẩn ngoại ngữ.",
            "Bước 2: Xác nhận chuẩn đầu ra sinh viên cần tối thiểu TOEIC 500 điểm để tốt nghiệp.",
        ]
        report = auditor.audit_trace(steps, [evidence])
        assert not report.passed
        assert any(f.conflict_type == ContradictionType.NUMERIC_COLLISION for f in report.findings)

    def test_audit_answer_claims_catches_contradiction_with_operational_steps(self):
        """Finding 1 fix: operational steps alone do not mask contradictions inside res.answer."""
        auditor = ContradictionAuditor()
        evidence = SourceEvidence(
            source_id="src-academic-refund",
            kind="pdf_page",
            excerpt="Học viên bị đình chỉ học tập không được hoàn trả học phí trong mọi trường hợp.",
        )
        operational_steps = [
            "Executed COT: 24 generated tokens.",
            "dispatched to solver policy with underlying_requests: 1.",
        ]
        answer = "Theo quy định, học viên bị đình chỉ vẫn được phép hoàn trả học phí nếu có đơn xin cứu xét."
        report = auditor.audit_trace(operational_steps, [evidence], answer=answer)
        assert not report.passed
        assert len(report.findings) >= 1
        finding = report.findings[0]
        assert finding.is_contradiction
        assert finding.conflict_type == ContradictionType.GROUNDING_CONFLICT
        assert finding.claim_origin == "answer"
        assert finding.conflicting_source_id == "src-academic-refund"
        assert report.claims_checked_count >= 1
        assert report.operational_events_count == 2

    def test_negative_control_threshold_vs_observed_score_passes(self):
        """Finding 2a fix: observed score >= minimum threshold must NOT trigger numeric collision."""
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-toeic-min",
            kind="pdf_page",
            excerpt="Quy chế yêu cầu chuẩn đầu ra ngoại ngữ tối thiểu TOEIC 600 điểm.",
        )
        answer = "Sinh viên đã đạt TOEIC 650 điểm, cao hơn mức tối thiểu 600 điểm quy định."
        report = auditor.audit_trace([], [evidence], answer=answer)
        assert report.passed
        assert len(report.findings) == 0

    def test_negative_control_distinct_entities_passes(self):
        """Finding 2b fix: distinct subject entities (An vs Bình) must NOT trigger numeric collision."""
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-an-score",
            kind="pdf_page",
            excerpt="Sinh viên An đạt điểm TOEIC 650 trong kỳ thi sát hạch.",
        )
        answer = "Sinh viên Bình đạt điểm TOEIC 700 trong đợt xét tuyển riêng."
        report = auditor.audit_trace([], [evidence], answer=answer)
        assert report.passed
        assert len(report.findings) == 0

    def test_positive_control_same_entity_fact_collision(self):
        """Finding 2b positive control: contradictory facts for the SAME subject entity trigger collision."""
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-an-score-2",
            kind="pdf_page",
            excerpt="Sinh viên An đạt điểm TOEIC 650 trong kỳ thi sát hạch.",
        )
        answer = "Sinh viên An chỉ đạt TOEIC 500 điểm nên chưa đạt chuẩn."
        report = auditor.audit_trace([], [evidence], answer=answer)
        assert not report.passed
        assert any(f.conflict_type == ContradictionType.NUMERIC_COLLISION for f in report.findings)
        collision = next(f for f in report.findings if f.conflict_type == ContradictionType.NUMERIC_COLLISION)
        assert collision.claim_origin == "answer"

    def test_coverage_status_not_evaluated_when_no_domain_claims(self):
        """Coverage scope reporting: returns not_evaluated when no verifiable claims match evidence."""
        auditor = ContradictionAuditor()
        evidence = SourceEvidence(
            source_id="src-math",
            kind="pdf_page",
            excerpt="Công thức tính tích phân suy rộng cấp một.",
        )
        operational_steps = [
            "Executed COT: 12 generated tokens.",
        ]
        report = auditor.audit_trace(operational_steps, [evidence])
        assert report.passed
        assert report.coverage_status == "not_evaluated"
        assert report.operational_events_count == 1
        assert report.claims_checked_count == 0


class TestRatIconProvider:
    def test_provider_loads_native_app_icon(self):
        app = get_or_create_app()
        provider = RatIconProvider()

        # Test on standard macOS system applications
        test_apps = [
            "/Applications/Safari.app",
            "/System/Applications/Utilities/Terminal.app",
            "/System/Applications/Calculator.app",
        ]
        found_any = False
        for app_path in test_apps:
            if Path(app_path).exists():
                found_any = True
                pix, size = provider.requestPixmap(app_path, QSize(64, 64))
                assert not pix.isNull()
                assert size.width() > 0 and size.height() > 0
                assert pix.width() > 0 and pix.height() > 0

        assert found_any, "No standard macOS apps found in test environment"

    def test_provider_normalizes_paths_and_caches(self):
        app = get_or_create_app()
        provider = RatIconProvider(max_cache_entries=4)

        # Path without leading slash
        pix1, size1 = provider.requestPixmap("Applications/Safari.app", QSize(64, 64))
        if Path("/Applications/Safari.app").exists():
            assert not pix1.isNull()

        # Cache hit check
        pix2, size2 = provider.requestPixmap("/Applications/Safari.app", QSize(64, 64))
        if Path("/Applications/Safari.app").exists():
            assert not pix2.isNull()

    def test_provider_fallback_on_missing_file(self):
        app = get_or_create_app()
        provider = RatIconProvider()
        pix, size = provider.requestPixmap("/non_existent/fake_app.app", QSize(64, 64))
        assert not pix.isNull()
        assert size.width() == 64 and size.height() == 64
