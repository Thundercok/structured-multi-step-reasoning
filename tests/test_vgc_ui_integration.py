"""
tests/test_vgc_ui_integration.py — Integration Tests for VGC in UI (ChatStream & Omnibar).
Verifies CitationChip rendering, QuickLook hooks, ThinkingAccordion VGC styling,
and MetaReasoner grounded citation delivery.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.meta_reasoner import MetaReasonerEngine
from rat.engine.vgc import VGCCertificate, VGCVerificationStatus, VGCVerifier, vgc_engine
from rat.ui.chat_stream import ChatStreamWidget, CitationChip, ThinkingAccordion


class TestVGCUIIntegration(unittest.TestCase):
    def test_citation_chip_ui(self):
        cit = {
            "file_name": "QuyCheDaoTao.pdf",
            "file_path": "/tmp/QuyCheDaoTao.pdf",
            "page": 4,
            "snippet": "Sinh viên tích lũy đủ 80% tín chỉ được đăng ký khóa luận tốt nghiệp.",
        }
        chip = CitationChip(cit)
        self.assertEqual(chip.file_name, "QuyCheDaoTao.pdf")
        self.assertEqual(chip.page, 4)
        self.assertIn("Sinh viên tích lũy", chip.toolTip())
        self.assertIn("Trang 4", chip.toolTip())

    def test_thinking_accordion_vgc_badge_verified(self):
        steps = [
            "Giai đoạn 1 (Fast-W): Trích xuất biểu thức",
            "Giai đoạn 2 (Verifier Gate): Kiểm chứng chứng chỉ",
            "✓ Chứng chỉ HỢP LỆ (0.4ms): AST calculation verified",
        ]
        accordion = ThinkingAccordion(steps, latency_ms=12.5)
        self.assertIn("Đã kiểm chứng (VGC)", accordion._header_prefix)
        self.assertEqual(len(accordion.steps), 3)

    def test_thinking_accordion_vgc_badge_escalated(self):
        steps = [
            "Giai đoạn 1 (Fast-W): Trích xuất biểu thức",
            "⚠️ Chứng chỉ BỊ TỪ CHỐI: Numerical mismatch",
            "Giai đoạn 3 (Escalation): Kích hoạt suy luận sâu đa bước",
        ]
        accordion = ThinkingAccordion(steps, latency_ms=85.0)
        self.assertIn("ESCALATED", accordion._header_prefix)

    def test_chat_stream_renders_citations(self):
        stream = ChatStreamWidget()
        citations = [
            {
                "file_name": "SoTaySinhVien.pdf",
                "file_path": "/tmp/SoTaySinhVien.pdf",
                "page": 12,
                "snippet": "Học bổng khuyến khích loại Giỏi yêu cầu ĐTB >= 8.0.",
            }
        ]
        steps = [
            "Tra cứu quy chế đào tạo",
            "✓ Chứng chỉ HỢP LỆ: Đối chiếu tài liệu gốc",
        ]
        stream.add_assistant_message(
            answer="Điều kiện nhận học bổng loại Giỏi là ĐTB >= 8.0.",
            reasoning_steps=steps,
            citations=citations,
            strategy="CoT",
        )
        self.assertEqual(stream._message_count, 1)

    def test_meta_reasoner_delivers_vgc_certificates_and_citations(self):
        engine = MetaReasonerEngine(lam=0.02)

        # Quantitative query with PAL & VGC
        q_math = "Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này thêm 4 môn..."
        res_math = engine.solve(q_math)
        self.assertEqual(res_math.strategy, "PAL")
        self.assertEqual(res_math.verification_status, "valid")
        self.assertIsNotNone(res_math.witness_proof)
        self.assertTrue(any("✓" in s or "hợp lệ" in s.lower() for s in res_math.steps))

        # Academic policy query with grounded citations
        q_policy = "Điều kiện nhận học bổng khuyến khích học tập loại Giỏi?"
        res_policy = engine.solve(q_policy)
        self.assertGreaterEqual(len(res_policy.citations), 1)
        self.assertIn("Sổ tay sinh viên", res_policy.citations[0]["file_name"])
        self.assertEqual(res_policy.verification_status, "valid")

    def test_search_result_item_vgc_and_citation(self):
        from rat.engine.reranker import SearchResultItem
        item = SearchResultItem(
            file_path="/Users/test/Documents/DSA_Syllabus.pdf",
            file_name="DSA_Syllabus.pdf",
            file_ext=".pdf",
            file_size=1024 * 1024,
            modified_at=1700000000.0,
            score=95.0,
            explanation="Khớp từ khóa DSA",
            snippet="Môn Cấu trúc dữ liệu và giải thuật gồm 3 tín chỉ lý thuyết và 1 thực hành.",
            verified=True,
            page_num=2,
            vgc_certificate={"claim": "3 tín chỉ", "witness": "3 tín chỉ"},
        )
        self.assertTrue(item.verified)
        self.assertEqual(item.page_num, 2)
        citation = item.to_citation()
        self.assertEqual(citation["file_name"], "DSA_Syllabus.pdf")
        self.assertEqual(citation["page"], 2)
        self.assertIn("Cấu trúc dữ liệu", citation["snippet"])

    def test_compact_file_row_vgc_badge(self):
        from rat.engine.reranker import SearchResultItem
        from rat.ui.compact_results import CompactFileRow
        item = SearchResultItem(
            file_path="/Users/test/Documents/SoTay.pdf",
            file_name="SoTay.pdf",
            file_ext=".pdf",
            file_size=2048,
            modified_at=1700000000.0,
            score=90.0,
            explanation="Quy chế đào tạo",
            snippet="Điều kiện học vượt",
            verified=True,
            page_num=5,
        )
        from PyQt6.QtWidgets import QLabel
        row = CompactFileRow(item)
        # Check that row has VGC badge
        badges = [lbl.text() for lbl in row.findChildren(QLabel) if "VGC" in lbl.text()]
        self.assertTrue(any("VGC" in b for b in badges))


if __name__ == "__main__":
    unittest.main()
