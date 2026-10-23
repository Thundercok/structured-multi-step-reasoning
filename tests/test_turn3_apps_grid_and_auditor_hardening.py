"""
Tests for Turn 3: Grid App Catalog, ContradictionAuditor hardening, and Quick controller boundary integrity.
"""

from __future__ import annotations

import sys
from pathlib import Path
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication

from rat.engine.app_resolver import Application, ApplicationCatalog
from rat.engine.contradiction_auditor import (
    ContradictionAuditor,
    ContradictionType,
)
from rat.kernel.contracts import SourceEvidence
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.engine.assistant_runtime import AgentResponse
from rat.engine.execution import ExecutionRequest


def get_or_create_app():
    return QApplication.instance() or QApplication([sys.argv[0]])


class TestContradictionAuditorHardening:
    def test_answer_claim_grounding_conflict_detected(self):
        """Finding 1: Answer claims are audited even when steps are pure runner telemetry."""
        auditor = ContradictionAuditor()
        evidence = SourceEvidence(
            source_id="src-probation",
            kind="pdf_page",
            excerpt="Sinh viên bị cảnh báo học vụ mức 3 sẽ bị buộc thôi học theo quy chế.",
        )
        operational_steps = [
            "Executed COT: 18 generated tokens.",
            "dispatched to solver policy with underlying_requests: 1.",
        ]
        answer = "Sinh viên bị cảnh báo học vụ mức 3 không bị cảnh báo và vẫn an toàn học vụ bình thường."
        report = auditor.audit_trace(operational_steps, [evidence], answer=answer)
        assert not report.passed
        assert len(report.findings) >= 1
        finding = report.findings[0]
        assert finding.is_contradiction
        assert finding.conflict_type == ContradictionType.GROUNDING_CONFLICT
        assert finding.claim_origin == "answer"
        assert finding.conflicting_source_id == "src-probation"
        assert report.claims_checked_count >= 1
        assert report.operational_events_count == 2
        assert report.coverage_status == "checked"

    def test_negative_control_threshold_vs_observed_score(self):
        """Finding 2a: Observed score meeting minimum threshold must NOT trigger collision."""
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-toeic-min",
            kind="pdf_page",
            excerpt="Quy định chuẩn đầu ra ngoại ngữ yêu cầu tối thiểu TOEIC 600 điểm.",
        )
        answer = "Sinh viên đạt TOEIC 650 điểm, cao hơn mức tối thiểu 600 điểm quy định."
        report = auditor.audit_trace([], [evidence], answer=answer)
        assert report.passed
        assert len(report.findings) == 0
        assert report.coverage_status == "checked"

    def test_negative_control_distinct_entities_an_and_binh(self):
        """Finding 2b: Separate subject entities (An vs Bình) must NOT trigger numeric collision."""
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-an-score",
            kind="pdf_page",
            excerpt="Sinh viên An đạt điểm TOEIC 650 trong đợt kiểm tra chuẩn đầu ra.",
        )
        answer = "Sinh viên Bình đạt điểm TOEIC 700 trong đợt kiểm tra chuẩn đầu ra."
        report = auditor.audit_trace([], [evidence], answer=answer)
        assert report.passed
        assert len(report.findings) == 0

    def test_positive_control_same_entity_fact_collision(self):
        """Positive control: Contradictory numeric facts for the same subject entity are caught."""
        auditor = ContradictionAuditor(strict_numeric=True)
        evidence = SourceEvidence(
            source_id="src-an-score",
            kind="pdf_page",
            excerpt="Sinh viên An đạt điểm TOEIC 650 trong đợt kiểm tra chuẩn đầu ra.",
        )
        answer = "Sinh viên An chỉ đạt TOEIC 500 điểm nên chưa đạt chuẩn đầu ra."
        report = auditor.audit_trace([], [evidence], answer=answer)
        assert not report.passed
        assert any(f.conflict_type == ContradictionType.NUMERIC_COLLISION for f in report.findings)
        finding = next(f for f in report.findings if f.conflict_type == ContradictionType.NUMERIC_COLLISION)
        assert finding.claim_origin == "answer"
        assert finding.conflicting_source_id == "src-an-score"

    def test_coverage_status_not_evaluated_on_operational_steps_only(self):
        """Research protocol: keep not_evaluated when no domain propositions match evidence."""
        auditor = ContradictionAuditor()
        evidence = SourceEvidence(
            source_id="src-doc",
            kind="pdf_page",
            excerpt="Đề cương học phần đại số tuyến tính.",
        )
        steps = [
            "Executed COT: 20 generated tokens.",
            "Telemetry: latency=210ms",
        ]
        report = auditor.audit_trace(steps, [evidence])
        assert report.passed
        assert report.coverage_status == "not_evaluated"
        assert report.claims_checked_count == 0
        assert report.operational_events_count == 2


class TestQuickPDFControllerAppsGrid:
    def _create_mock_catalog(self):
        apps = (
            Application("app:safari", "/Applications/Safari.app", "Safari", "com.apple.Safari", "17.0", ("safari", "trinh duyet")),
            Application("app:terminal", "/System/Applications/Utilities/Terminal.app", "Terminal", "com.apple.Terminal", "2.14", ("terminal", "command")),
            Application("app:calc", "/System/Applications/Calculator.app", "Calculator", "com.apple.calculator", "10.14", ("calculator", "may tinh")),
        )
        return ApplicationCatalog(applications=apps)

    def test_controller_populates_installed_apps(self):
        app = get_or_create_app()
        catalog = self._create_mock_catalog()
        ctrl = QuickPDFController(
            auto_init_finder=False,
            finder_catalog=catalog,
        )
        snap = ctrl.snapshot
        apps = snap["installedApps"]
        assert len(apps) == 3
        app_names = [a["name"] for a in apps]
        assert "Safari" in app_names
        assert "Terminal" in app_names
        assert "Calculator" in app_names
        ctrl.close()

    def test_open_and_close_apps_view_preserves_draft(self):
        app = get_or_create_app()
        catalog = self._create_mock_catalog()
        ctrl = QuickPDFController(
            auto_init_finder=False,
            finder_catalog=catalog,
        )
        assert not ctrl.snapshot["isAppsView"]
        
        # User is composing a draft
        original_draft = "Học kỳ chính sinh viên được đăng ký tối đa bao nhiêu tín chỉ?"
        ctrl.openAppsView(original_draft)
        
        snap = ctrl.snapshot
        assert snap["isAppsView"]
        assert snap["view"] == "apps"
        assert snap["hasWorkbench"]
        assert snap["savedDraft"] == original_draft
        assert "Ứng dụng đã cài đặt" in snap["status"]

        # User filters apps inside apps view
        ctrl.onComposerTextChanged("term")
        snap = ctrl.snapshot
        assert snap["finderQuery"] == "term"

        # User exits apps view
        restored = ctrl.closeAppsView()
        assert restored == original_draft
        
        snap = ctrl.snapshot
        assert not snap["isAppsView"]
        assert snap["view"] != "apps"
        ctrl.close()

    def test_launch_application_calls_open_hit(self):
        app = get_or_create_app()
        opened_urls = []
        def mock_open_url(url):
            opened_urls.append(url.toString())
            return True

        catalog = self._create_mock_catalog()
        ctrl = QuickPDFController(
            auto_init_finder=False,
            finder_catalog=catalog,
            open_url=mock_open_url,
        )
        ctrl.openAppsView("draft query")
        # Launching Safari
        if Path("/Applications/Safari.app").exists():
            res = ctrl.launchApplication("/Applications/Safari.app")
            assert res is True
            assert any("Safari.app" in u for u in opened_urls)
        ctrl.close()


class TestQuickPDFControllerBoundaryIntegrity:
    def test_telemetry_timing_reads_current_response(self):
        app = get_or_create_app()
        ctrl = QuickPDFController(auto_init_finder=False)
        snap = ctrl.conversation.begin_turn("query")
        ctrl._current_worker = object()
        ctrl._current_execution_id = snap.execution_id
        ctrl._current_turn_id = snap.turn_id

        # Set stale telemetry from previous turn
        ctrl._telemetry = {"target_artifact_id": "old_stale_artifact_id"}

        # New response with different telemetry
        resp = AgentResponse(
            answer="Đáp án mới",
            steps=[],
            total_time_ms=15.0,
            tool_call_count=0,
            token_estimate=12,
        )
        resp.status = "completed"
        resp.execution_id = snap.execution_id
        resp.qa_telemetry = {"target_artifact_id": "new_correct_artifact_id", "turn_id": snap.turn_id}
        ctrl._on_execution_response(resp)

        # Confirm that controller telemetry was updated to the current turn's telemetry
        assert ctrl._telemetry.get("target_artifact_id") == "new_correct_artifact_id"
        ctrl.close()

    def test_status_callback_ignores_mismatched_execution_or_generation(self):
        app = get_or_create_app()
        ctrl = QuickPDFController(auto_init_finder=False)
        ctrl._current_execution_id = "exec-live"
        ctrl._chat_generation = 2
        ctrl._status = "Chuột sẵn sàng."

        # Emit status with old execution ID
        ctrl._on_execution_status("exec-old", 2, "wait")
        assert ctrl._status == "Chuột sẵn sàng."

        # Emit status with old generation
        ctrl._on_execution_status("exec-live", 1, "wait")
        assert ctrl._status == "Chuột sẵn sàng."

        # Emit status matching current execution ID and generation
        ctrl._on_execution_status("exec-live", 2, "wait")
        assert ctrl._status == "Đang chờ kết quả…"
        ctrl.close()

    def test_close_safely_cancels_active_worker(self):
        app = get_or_create_app()
        ctrl = QuickPDFController(auto_init_finder=False)
        class DummyWorker:
            def __init__(self):
                self.interrupted = False
            def requestInterruption(self):
                self.interrupted = True
            def wait(self, ms):
                return True

        worker = DummyWorker()
        ctrl._current_worker = worker
        ctrl._current_execution_id = "exec-close-test"

        assert ctrl.close() is True
        assert worker.interrupted is True
        assert ctrl._current_worker is None
