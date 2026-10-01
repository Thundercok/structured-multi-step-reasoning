"""
tests/test_cot_ui.py — Automated UI & Component Test for Minimalist CoT PreviewPanel.
Ensures zero crashes, correct tab switching, and seamless ReasoningTrace rendering.
Runs in headless offscreen Qt mode.
"""

import os
import sys
import time
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

# Ensure singleton QApplication
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.reasoning_trace import ReasoningStep, ReasoningTrace
from rat.engine.reranker import SearchResultItem
from rat.ui.preview_panel import PreviewPanel


class TestCoTPreviewPanelUI(unittest.TestCase):

    def setUp(self) -> None:
        self.panel = PreviewPanel()

    def tearDown(self) -> None:
        self.panel.deleteLater()

    def test_initial_state_empty(self) -> None:
        """Verify panel initializes cleanly in empty state."""
        self.panel.set_item(None)
        self.assertEqual(self.panel.stack.currentIndex(), 0)
        self.assertEqual(self.panel.btn_tab_preview.property("selected"), "true")
        self.assertEqual(self.panel.name_label.text(), "Chọn một mục hoặc đặt câu hỏi")
        self.assertEqual(self.panel.preview_text.toPlainText(), "")

    def test_set_search_result_item(self) -> None:
        """Verify setting a SearchResultItem populates title, badge, and preview text."""
        item = SearchResultItem(
            file_path="/tmp/Hop_Dong_Thue_Nha.pdf",
            file_name="Hop_Dong_Thue_Nha.pdf",
            file_ext=".pdf",
            file_size=2048,
            modified_at=time.time(),
            score=95.0,
            explanation="Khớp từ khóa hợp đồng • 95%",
            snippet="Cộng hòa xã hội chủ nghĩa Việt Nam\nĐiều 1: Tiền thuê nhà hàng tháng...",
        )
        self.panel.set_item(item)

        self.assertEqual(self.panel.name_label.text(), "Hop_Dong_Thue_Nha.pdf")
        self.assertEqual(self.panel.badge_label.text(), "PDF")
        self.assertIn("Tiền thuê nhà", self.panel.preview_text.toPlainText())
        self.assertFalse(self.panel.reason_box.isHidden())

    def test_cot_reasoning_trace_rendering(self) -> None:
        """Verify CoT reasoning trace populates timeline cards and updates tab label."""
        trace = ReasoningTrace(raw_query="tìm hợp đồng thuê nhà")
        trace.add_step(
            phase="decompose",
            thought="Phân tích intent câu hỏi",
            action="decompose()",
            observation="Kích hoạt: Lexical, Temporal",
            evaluation="Tiêu chuẩn",
            latency_ms=4.2,
        )
        trace.add_step(
            phase="retrieve",
            thought="Truy xuất FTS5 và Vectors",
            action="fuse_multi_way_rrf()",
            observation="FTS5: 25 | Dense: 30 → 28 tệp",
            evaluation="Dung hợp tốt",
            latency_ms=35.1,
        )
        trace.add_step(
            phase="evaluate",
            thought="Đánh giá đủ điều kiện",
            action="evaluate_sufficiency()",
            observation="SUFFICIENT (95%)",
            evaluation="Đạt độ tin cậy 95%",
            latency_ms=0.4,
        )
        trace.finalize(confidence=0.95, is_sufficient=True)

        self.panel.set_reasoning_trace(trace)

        # Button should show badge percentage
        self.assertIn("95%", self.panel.btn_tab_cot.text())

        # Switch to CoT tab
        self.panel.set_active_tab(1)
        self.assertEqual(self.panel.stack.currentIndex(), 1)
        self.assertEqual(self.panel.btn_tab_cot.property("selected"), "true")
        self.assertEqual(self.panel.btn_tab_preview.property("selected"), "false")

        # Switch back to preview tab
        self.panel.set_active_tab(0)
        self.assertEqual(self.panel.stack.currentIndex(), 0)
        self.assertEqual(self.panel.btn_tab_preview.property("selected"), "true")
        self.assertEqual(self.panel.btn_tab_cot.property("selected"), "false")

    def test_qa_answer_display(self) -> None:
        """Verify set_qa_answer sets text and switches to tab 0."""
        self.panel.set_active_tab(1)
        qa_data = {"answer": "Số tiền thuê nhà là 15.000.000 VNĐ."}
        self.panel.set_qa_answer(qa_data)

        self.assertEqual(self.panel.stack.currentIndex(), 0)
        self.assertEqual(self.panel.preview_text.toPlainText(), "Số tiền thuê nhà là 15.000.000 VNĐ.")


if __name__ == "__main__":
    unittest.main()
