"""
rat.ui.preview_panel — macOS Sequoia "Liquid Glass" Detail & Conversational AI Panel.
Features:
- Translucent frosted glass containers with physical top specular highlight
- Interactive Chatbot Conversation Stream (User & Assistant bubbles)
- Structured file metadata & Quick Look preview
- In-situ continuous conversational bar
"""

from __future__ import annotations

import html
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rat.engine.reasoning_trace import ReasoningTrace
from rat.engine.reranker import SearchResultItem
from rat.ui.theme import get_ext_badge_info

EXT_DESCRIPTIONS = {
    ".docx": "Tài liệu Word",
    ".doc": "Tài liệu Word",
    ".pdf": "Tài liệu PDF",
    ".xlsx": "Bảng tính Excel",
    ".xls": "Bảng tính Excel",
    ".csv": "Dữ liệu CSV",
    ".pptx": "Bản trình chiếu PPT",
    ".ppt": "Bản trình chiếu PPT",
    ".py": "Mã nguồn Python",
    ".js": "Mã nguồn JavaScript",
    ".ts": "Mã nguồn TypeScript",
    ".html": "Trang web HTML",
    ".css": "Định dạng CSS",
    ".json": "Cấu hình JSON",
    ".sh": "Tập lệnh Shell",
    ".sql": "Cơ sở dữ liệu SQL",
    ".txt": "Văn bản thuần Text",
    ".md": "Tài liệu Markdown",
    ".png": "Hình ảnh PNG",
    ".jpg": "Hình ảnh JPEG",
    ".jpeg": "Hình ảnh JPEG",
    ".webp": "Hình ảnh WebP",
    ".ai": "Tri thức & Phản hồi AI",
}


def open_file_default(file_path: str) -> None:
    if not os.path.exists(file_path):
        return
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", file_path])
    elif system == "Windows":
        os.startfile(file_path)
    else:
        subprocess.run(["xdg-open", file_path])


def reveal_in_finder(file_path: str) -> None:
    if not os.path.exists(file_path):
        return
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", "-R", file_path])
    elif system == "Windows":
        subprocess.run(["explorer", "/select,", os.path.normpath(file_path)])
    else:
        parent_dir = str(Path(file_path).parent)
        subprocess.run(["xdg-open", parent_dir])


def open_in_terminal(file_path: str) -> None:
    if not file_path:
        return
    system = platform.system()
    target_dir = file_path if os.path.isdir(file_path) else str(Path(file_path).parent)
    if system == "Darwin":
        subprocess.run(["open", "-a", "Terminal", target_dir])
    elif system == "Windows":
        subprocess.run(["cmd.exe", "/K", f"cd /d {target_dir}"])
    else:
        subprocess.run(["x-terminal-emulator", f"--working-directory={target_dir}"])


_quicklook_proc: Optional[subprocess.Popen] = None
_quicklook_current_path: Optional[str] = None


def trigger_quicklook(file_path: str) -> bool:
    """
    Toggle native macOS QuickLook preview window for the target file.
    If already previewing the same file, closes the preview window.
    If previewing a different file, closes previous and launches new preview.
    """
    global _quicklook_proc, _quicklook_current_path
    if not file_path or not os.path.exists(file_path):
        return False

    system = platform.system()
    if system == "Darwin":
        if _quicklook_proc and _quicklook_proc.poll() is None:
            prev_path = _quicklook_current_path
            try:
                _quicklook_proc.terminate()
            except Exception:
                pass
            _quicklook_proc = None
            _quicklook_current_path = None
            if prev_path == file_path:
                return False

        try:
            _quicklook_current_path = file_path
            _quicklook_proc = subprocess.Popen(
                ["qlmanage", "-p", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to launch qlmanage: {e}")
            return False
    else:
        open_file_default(file_path)
        return True


def close_quicklook() -> None:
    """Close any active QuickLook preview process."""
    global _quicklook_proc, _quicklook_current_path
    if _quicklook_proc and _quicklook_proc.poll() is None:
        try:
            _quicklook_proc.terminate()
        except Exception:
            pass
    _quicklook_proc = None
    _quicklook_current_path = None


class PreviewPanel(QFrame):
    """Liquid Glass Detail & Conversational AI Chatbot Panel."""
    ask_requested = pyqtSignal(str, str, str)
    suggest_name_requested = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewPanel")
        self.current_item: Optional[SearchResultItem] = None
        self.current_trace: Optional[ReasoningTrace] = None
        self.current_plan: Optional[Dict[str, Any]] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # -------------------------------------------------------------
        # 1. Hero File Header (Liquid Glass Card)
        # -------------------------------------------------------------
        header_card = QFrame()
        header_card.setObjectName("DetailHeaderCard")
        header_card.setStyleSheet("""
            QFrame#DetailHeaderCard {
                background-color: #fffdf9;
                border: 1px solid #e2d9cd;
                border-top: 1px solid #e2d9cd;
                border-radius: 8px;
                padding: 6px 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)

        self.badge_label = QLabel("✦")
        self.badge_label.setFixedSize(32, 32)
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_label.setStyleSheet("""
            background-color: #f7eedb;
            color: #60a5fa;
            font-weight: 700;
            font-size: 13px;
            border-radius: 6px;
            border: 1px solid #e2cd98;
            border-top: 1px solid #e2cd98;
        """)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        self.name_label = QLabel("Chọn một mục hoặc đặt câu hỏi")
        self.name_label.setStyleSheet("color: #1c1917; font-size: 13px; font-weight: 600;")
        self.name_label.setWordWrap(True)

        self.meta_sub_label = QLabel("Trợ lý AI sẵn sàng giải đáp thắc mắc")
        self.meta_sub_label.setStyleSheet("color: #78716c; font-size: 11px;")

        title_col.addWidget(self.name_label)
        title_col.addWidget(self.meta_sub_label)

        self.btn_suggest_name = QPushButton("🏷️ Đổi tên")
        self.btn_suggest_name.setToolTip("Gợi ý & Đổi tên tệp bằng AI (⌘N)")
        self.btn_suggest_name.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_suggest_name.setStyleSheet("""
            QPushButton {
                background-color: #fffdf9;
                color: #78716c;
                border: 1px solid #e2d9cd;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f7eedb;
                color: #5c4d3c;
                border: 1px solid #d4a359;
            }
        """)
        self.btn_suggest_name.clicked.connect(self._trigger_suggest_name)

        self.btn_quicklook = QPushButton("Space")
        self.btn_quicklook.setToolTip("macOS Quick Look (Phím Space)")
        self.btn_quicklook.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quicklook.setStyleSheet("""
            QPushButton {
                background-color: #fffdf9;
                color: #78716c;
                border: 1px solid #e2d9cd;
                border-top: 1px solid #e2d9cd;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #fffdf9;
                color: #1c1917;
            }
        """)
        self.btn_quicklook.clicked.connect(self._trigger_quicklook)

        h_layout.addWidget(self.badge_label)
        h_layout.addLayout(title_col, 1)
        h_layout.addWidget(self.btn_suggest_name)
        h_layout.addWidget(self.btn_quicklook)
        layout.addWidget(header_card)

        # -------------------------------------------------------------
        # 2. Image Thumbnail Quick Look (Only for images)
        # -------------------------------------------------------------
        self.image_preview_box = QLabel()
        self.image_preview_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_box.setFixedHeight(120)
        self.image_preview_box.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #e2d9cd;
            border-radius: 6px;
            padding: 4px;
        """)
        self.image_preview_box.hide()
        layout.addWidget(self.image_preview_box)

        # -------------------------------------------------------------
        # 3. Translucent Metadata Key-Value List
        # -------------------------------------------------------------
        self.metadata_frame = QFrame()
        self.reason_box = self.metadata_frame  # Backward compatibility alias
        self.metadata_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-bottom: 1px solid #e2d9cd;
                padding-bottom: 4px;
            }
            QLabel.MetaKey {
                color: #78716c;
                font-size: 11px;
                font-weight: 500;
            }
            QLabel.MetaVal {
                color: #2c241c;
                font-size: 11px;
                font-weight: 400;
            }
        """)
        meta_layout = QVBoxLayout(self.metadata_frame)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(3)

        row_path = QHBoxLayout()
        lbl_k1 = QLabel("Đường dẫn")
        lbl_k1.setProperty("class", "MetaKey")
        self.val_path = QLabel("-")
        self.val_path.setProperty("class", "MetaVal")
        row_path.addWidget(lbl_k1)
        row_path.addStretch()
        row_path.addWidget(self.val_path)
        meta_layout.addLayout(row_path)

        row_mod = QHBoxLayout()
        lbl_k2 = QLabel("Sửa đổi")
        lbl_k2.setProperty("class", "MetaKey")
        self.val_time = QLabel("-")
        self.val_time.setProperty("class", "MetaVal")
        row_mod.addWidget(lbl_k2)
        row_mod.addStretch()
        row_mod.addWidget(self.val_time)
        meta_layout.addLayout(row_mod)

        self.row_score = QHBoxLayout()
        self.lbl_k3 = QLabel("Độ khớp AI")
        self.lbl_k3.setProperty("class", "MetaKey")
        self.val_score = QLabel("-")
        self.val_score.setStyleSheet("""
            background-color: #f7eedb;
            color: #93c5fd;
            border: 1px solid #e2cd98;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 10px;
            font-weight: 600;
        """)
        self.row_score.addWidget(self.lbl_k3)
        self.row_score.addStretch()
        self.row_score.addWidget(self.val_score)
        meta_layout.addLayout(self.row_score)

        layout.addWidget(self.metadata_frame)

        # -------------------------------------------------------------
        # 4. Liquid Glass Segmented View Switcher
        # -------------------------------------------------------------
        switch_row = QHBoxLayout()
        switch_row.setSpacing(4)
        switch_row.setContentsMargins(0, 2, 0, 2)

        self.seg_container = QFrame()
        self.seg_container.setObjectName("SegContainer")
        self.seg_container.setStyleSheet("""
            QFrame#SegContainer {
                background-color: #fffdf9;
                border: 1px solid #e2d9cd;
                border-top: 1px solid #e2d9cd;
                border-radius: 5px;
            }
            QPushButton {
                border: none;
                border-radius: 4px;
                padding: 3px 9px;
                font-size: 11px;
                font-weight: 500;
                color: #78716c;
                background-color: transparent;
            }
            QPushButton:hover {
                color: #1c1917;
            }
            QPushButton[selected="true"] {
                background-color: #f7eedb;
                color: #1c1917;
                font-weight: 600;
                border: 1px solid #e2cd98;
            }
        """)
        seg_layout = QHBoxLayout(self.seg_container)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)

        self.btn_tab_preview = QPushButton("📄 Nội dung")
        self.btn_tab_preview.setProperty("selected", "true")
        self.btn_tab_preview.clicked.connect(lambda: self.set_active_tab(0))

        self.btn_tab_cot = QPushButton("✦ Trợ lý AI")
        self.btn_tab_cot.setProperty("selected", "false")
        self.btn_tab_cot.clicked.connect(lambda: self.set_active_tab(1))

        seg_layout.addWidget(self.btn_tab_preview)
        seg_layout.addWidget(self.btn_tab_cot)

        switch_row.addWidget(self.seg_container)
        switch_row.addStretch()
        layout.addLayout(switch_row)

        # -------------------------------------------------------------
        # 5. Stacked Content Pages: [Page 0: Preview | Page 1: Chatbot Stream]
        # -------------------------------------------------------------
        self.stack = QStackedWidget()

        # Page 0: Quick Look Text Editor
        self.preview_text = QTextEdit()
        self.preview_text.setObjectName("PreviewContent")
        self.preview_text.setReadOnly(True)
        self.preview_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #e2d9cd;
                border-top: 1px solid #e2d9cd;
                border-radius: 6px;
                color: #2c241c;
                font-size: 11.5px;
                font-family: "SF Mono", "Menlo", "Fira Code", monospace;
                line-height: 1.45;
                padding: 8px;
            }
        """)
        self.stack.addWidget(self.preview_text)

        # Page 1: Chatbot Stream & Reasoning View
        self.cot_scroll = QScrollArea()
        self.cot_scroll.setWidgetResizable(True)
        self.cot_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cot_scroll.setStyleSheet("background-color: transparent;")

        self.cot_content_widget = QWidget()
        self.cot_content_layout = QVBoxLayout(self.cot_content_widget)
        self.cot_content_layout.setContentsMargins(0, 0, 0, 0)
        self.cot_content_layout.setSpacing(6)
        self.cot_scroll.setWidget(self.cot_content_widget)

        self.stack.addWidget(self.cot_scroll)
        layout.addWidget(self.stack, 1)

        # -------------------------------------------------------------
        # 6. In-Situ Conversational AI Bar
        # -------------------------------------------------------------
        chat_frame = QFrame()
        chat_frame.setObjectName("ChatFrame")
        chat_frame.setStyleSheet("""
            QFrame#ChatFrame {
                background-color: #fffdf9;
                border: 1px solid #e2d9cd;
                border-top: 1px solid #e2d9cd;
                border-radius: 6px;
                padding: 3px 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        chat_layout = QVBoxLayout(chat_frame)
        chat_layout.setContentsMargins(3, 3, 3, 3)
        chat_layout.setSpacing(4)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        ai_glyph = QLabel("✦")
        ai_glyph.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: 700; padding-left: 2px;")
        input_row.addWidget(ai_glyph)

        self.ask_input = QLineEdit()
        self.ask_input.setPlaceholderText("Trò chuyện cùng AI hoặc hỏi về tài liệu này... (↵)")
        self.ask_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #1c1917;
                border: none;
                padding: 4px 4px;
                font-size: 11.5px;
            }
        """)
        self.ask_input.returnPressed.connect(self._trigger_ask)

        self.ask_btn = QPushButton("↵ Gửi")
        self.ask_btn.setToolTip("Gửi tin nhắn cho AI")
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2c94c;
                color: #3b2c15;
                font-weight: 600;
                font-size: 10.5px;
                border-radius: 4px;
                padding: 3px 8px;
                border: 1px solid #e2cd98;
                border-top: 1px solid #e2cd98;
            }
            QPushButton:hover {
                background-color: #e2cd98;
            }
        """)
        self.ask_btn.clicked.connect(self._trigger_ask)

        input_row.addWidget(self.ask_input, 1)
        input_row.addWidget(self.ask_btn)
        chat_layout.addLayout(input_row)

        self.qa_response_box = QLabel("")
        self.qa_response_box.setStyleSheet("""
            background-color: #f8f6f2;
            color: #2c241c;
            font-size: 11.5px;
            padding: 8px 10px;
            border-radius: 6px;
            border: 1px solid #e2cd98;
            border-top: 1px solid #e2cd98;
            line-height: 1.45;
        """)
        self.qa_response_box.setWordWrap(True)
        self.qa_response_box.hide()
        chat_layout.addWidget(self.qa_response_box)

        layout.addWidget(chat_frame)
        self._render_empty_cot()

    def set_active_tab(self, tab_index: int) -> None:
        self.stack.setCurrentIndex(tab_index)
        if tab_index == 0:
            self.btn_tab_preview.setProperty("selected", "true")
            self.btn_tab_cot.setProperty("selected", "false")
        else:
            self.btn_tab_preview.setProperty("selected", "false")
            self.btn_tab_cot.setProperty("selected", "true")

        self.btn_tab_preview.style().unpolish(self.btn_tab_preview)
        self.btn_tab_preview.style().polish(self.btn_tab_preview)
        self.btn_tab_cot.style().unpolish(self.btn_tab_cot)
        self.btn_tab_cot.style().polish(self.btn_tab_cot)

    def _render_empty_cot(self) -> None:
        while self.cot_content_layout.count():
            item = self.cot_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        welcome_card = QFrame()
        welcome_card.setStyleSheet("""
            QFrame {
                background-color: #fffdf9;
                border: 1px solid #e2d9cd;
                border-top: 1px solid #e2d9cd;
                border-radius: 8px;
                padding: 16px 12px;
            }
        """)
        w_layout = QVBoxLayout(welcome_card)
        w_layout.setSpacing(6)

        w_title = QLabel("✦ Trợ Lý Hội Thoại AI (Copilot)")
        w_title.setStyleSheet("color: #60a5fa; font-size: 12.5px; font-weight: 600;")
        w_layout.addWidget(w_title)

        w_desc = QLabel("Nhập bất kỳ câu hỏi nào ở ô tìm kiếm hoặc thanh hội thoại bên dưới để trò chuyện cùng AI.")
        w_desc.setStyleSheet("color: #78716c; font-size: 11px; line-height: 1.4;")
        w_desc.setWordWrap(True)
        w_layout.addWidget(w_desc)

        self.cot_content_layout.addWidget(welcome_card)
        self.cot_content_layout.addStretch()

    def set_reasoning_trace(
        self,
        trace: Optional[ReasoningTrace],
        plan: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.current_trace = trace
        self.current_plan = plan

        if not trace or not trace.steps:
            self.btn_tab_cot.setText("✦ Trợ lý AI")
            self._render_empty_cot()
            return

        conf_pct = int(trace.final_confidence * 100)
        self.btn_tab_cot.setText(f"✦ Trợ lý AI ({conf_pct}%)")

        while self.cot_content_layout.count():
            item = self.cot_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. Chatbot Assistant Response Bubble
        ai_bubble = QFrame()
        ai_bubble.setStyleSheet("""
            QFrame {
                background-color: #f8f6f2;
                border: 1px solid #e2cd98;
                border-top: 1px solid #e2cd98;
                border-radius: 8px;
                padding: 8px 10px;
            }
        """)
        ai_b_layout = QVBoxLayout(ai_bubble)
        ai_b_layout.setSpacing(4)

        ai_header = QHBoxLayout()
        ai_tag = QLabel("✦ Trợ lý Copilot")
        ai_tag.setStyleSheet("color: #60a5fa; font-size: 11px; font-weight: 700;")
        ai_header.addWidget(ai_tag)
        ai_header.addStretch()

        latency_lbl = QLabel(f"⚡ {trace.total_latency_ms}ms • {len(trace.steps)} bước suy luận")
        latency_lbl.setStyleSheet("color: #887c70; font-size: 10px;")
        ai_header.addWidget(latency_lbl)
        ai_b_layout.addLayout(ai_header)

        # Direct Answer Text
        if trace.steps and trace.steps[-1].thought:
            ans_text = trace.steps[-1].thought
        else:
            ans_text = "Đã hoàn thành phân tích và xác minh bằng chứng."

        ans_lbl = QLabel(ans_text)
        ans_lbl.setStyleSheet("color: #1c1917; font-size: 11.5px; line-height: 1.45;")
        ans_lbl.setWordWrap(True)
        ai_b_layout.addWidget(ans_lbl)

        self.cot_content_layout.addWidget(ai_bubble)

        # 2. Reasoning Ladder Steps (Glass Cards)
        for idx, step in enumerate(trace.steps):
            step_card = QFrame()
            step_card.setStyleSheet("""
                QFrame {
                    background-color: #fffdf9;
                    border: 1px solid #e2d9cd;
                    border-top: 1px solid #e2d9cd;
                    border-radius: 6px;
                    padding: 5px 8px;
                }
            """)
            s_layout = QVBoxLayout(step_card)
            s_layout.setContentsMargins(6, 4, 6, 4)
            s_layout.setSpacing(2)

            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            title_lbl = QLabel(f"Bước {idx + 1}: {step.phase.upper()}")
            title_lbl.setStyleSheet("color: #38bdf8; font-size: 10.5px; font-weight: 600;")
            title_row.addWidget(title_lbl)
            title_row.addStretch()

            step_ms = QLabel(f"{step.latency_ms}ms")
            step_ms.setStyleSheet("color: #887c70; font-size: 9.5px;")
            title_row.addWidget(step_ms)
            s_layout.addLayout(title_row)

            obs_text = step.observation if step.observation else step.thought
            if obs_text:
                desc_lbl = QLabel(obs_text)
                desc_lbl.setStyleSheet("color: #2c241c; font-size: 10.5px; line-height: 1.35;")
                desc_lbl.setWordWrap(True)
                s_layout.addWidget(desc_lbl)

            self.cot_content_layout.addWidget(step_card)

        self.cot_content_layout.addStretch()
        self.set_active_tab(1)

    def set_item(self, item: Optional[SearchResultItem], query: str = "") -> None:
        self.current_item = item
        self.qa_response_box.hide()
        self.qa_response_box.setText("")
        self.ask_input.clear()

        if not item:
            self.badge_label.setText("✦")
            self.badge_label.setStyleSheet("background-color: #f7eedb; color: #60a5fa; font-weight: 700; font-size: 12px; border-radius: 6px;")
            self.name_label.setText("Chọn một mục hoặc đặt câu hỏi")
            self.meta_sub_label.setText("Trợ lý AI sẵn sàng giải đáp thắc mắc")
            self.val_path.setText("-")
            self.val_time.setText("-")
            self.val_score.setText("-")
            self.image_preview_box.hide()
            self.preview_text.setPlainText("")
            return

        info = get_ext_badge_info(item.file_ext)
        self.badge_label.setText(info["label"])
        self.badge_label.setStyleSheet(f"""
            background-color: {info['bg']};
            color: {info['fg']};
            font-weight: 700;
            font-size: 10px;
            border-radius: 6px;
            border: 1px solid #e2d9cd;
        """)

        if getattr(item, "verified", False):
            self.name_label.setText(f"{item.file_name}  ✓ VGC")
        else:
            self.name_label.setText(item.file_name)

        ext_clean = item.file_ext.lower()
        desc = EXT_DESCRIPTIONS.get(ext_clean, f"Tệp {ext_clean.upper()}")
        v_tag = "  •  ✓ Đã kiểm chứng trích đoạn" if getattr(item, "verified", False) else ""
        self.meta_sub_label.setText(f"{desc}  •  {item.file_size_formatted}{v_tag}")

        # Metadata
        p = item.file_path
        if len(p) > 36:
            p = "..." + p[-32:]
        self.val_path.setText(p)
        self.val_time.setText(item.modified_formatted)

        score_val = int(getattr(item, "score", 0))
        if score_val > 10:
            self.val_score.setText(f"{score_val}%")
            self.val_score.show()
            self.lbl_k3.show()
        else:
            self.val_score.hide()
            self.lbl_k3.hide()

        # Image Thumbnail View
        if ext_clean in [".png", ".jpg", ".jpeg", ".webp"] and os.path.exists(item.file_path):
            pix = QPixmap(item.file_path)
            if not pix.isNull():
                scaled = pix.scaled(280, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_preview_box.setPixmap(scaled)
                self.image_preview_box.show()
            else:
                self.image_preview_box.hide()
        else:
            self.image_preview_box.hide()

        # Content Preview with keyword highlight
        snippet_text = item.snippet or ""
        preview_body = snippet_text if snippet_text else "(Không có nội dung trích đoạn xem trước)"
        if query and query.strip() and snippet_text:
            escaped_body = html.escape(preview_body)
            terms = [re.escape(w) for w in query.strip().split() if len(w) >= 2]
            if terms:
                pattern = re.compile(r"(" + "|".join(terms) + r")", re.IGNORECASE)
                highlighted = pattern.sub(
                    r'<mark style="background-color: #f7eedb; color: #1c1917; padding: 1px 3px; border-radius: 3px;">\1</mark>',
                    escaped_body
                )
                self.preview_text.setHtml(f"<div style='font-family: \"SF Mono\", \"Menlo\", \"Fira Code\", monospace; font-size: 11.5px; line-height: 1.45; white-space: pre-wrap; color: #2c241c;'>{highlighted}</div>")
            else:
                self.preview_text.setPlainText(preview_body)
        else:
            self.preview_text.setPlainText(preview_body)

    def _trigger_ask(self) -> None:
        q = self.ask_input.text().strip()
        if not q:
            return

        target_path = self.current_item.file_path if self.current_item else ""
        target_name = self.current_item.file_name if self.current_item else "General Query"

        self.qa_response_box.show()
        self.qa_response_box.setText("✦ <i>Đang phân tích & suy luận câu trả lời...</i>")
        self.ask_requested.emit(target_path, target_name, q)

    def set_qa_answer(self, result: Dict[str, Any]) -> None:
        ans = result.get("answer", "Không có câu trả lời.")
        engine = result.get("engine", "✦ Trợ lý AI")
        self.qa_response_box.show()
        self.qa_response_box.setText(f"<b>{engine}:</b>\n{ans}")
        if not self.preview_text.toPlainText() or "💡" in self.preview_text.toPlainText() or "✦" in self.preview_text.toPlainText():
            self.preview_text.setPlainText(ans)
        self.set_active_tab(0)

    def _trigger_quicklook(self) -> None:
        if self.current_item and os.path.exists(self.current_item.file_path):
            trigger_quicklook(self.current_item.file_path)

    def _trigger_suggest_name(self) -> None:
        if self.current_item:
            self.suggest_name_requested.emit(self.current_item)

