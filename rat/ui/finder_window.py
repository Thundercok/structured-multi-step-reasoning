"""
rat.ui.finder_window — Premium macOS Native AI Finder Window.
Engineered with Raycast/Apple HIG design standards: Frosted Glass Sidebar,
Apple Folded-Corner Document Icons, Non-blocking Multi-threaded Search & In-situ AI Assistant.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, QPoint, QRect, QSize, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QIcon, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rat.config import config
from rat.crawler.db import Database
from rat.crawler.dedup import dedup_engine
from rat.crawler.extractors import extract_document_content
from rat.engine.hybrid_search import SearchEngine
from rat.engine.qa_engine import qa_engine
from rat.engine.reranker import SearchResultItem, format_file_size, format_relative_time, sort_search_results
from rat.ui.apple_item_delegate import AppleSpotlightDelegate
from rat.ui.preview_panel import EXT_DESCRIPTIONS, PreviewPanel, open_file_default, reveal_in_finder
from rat.ui.theme import RAYCAST_QSS, get_ext_badge_info

logger = logging.getLogger("rat.finder")

COLLECTION_DEFINITIONS = [
    ("all", "🌟 Tất cả tệp", []),
    ("docs", "📄 Tài liệu văn phòng", [".docx", ".doc", ".pdf", ".txt", ".md"]),
    ("slides", "📊 Slide thuyết trình", [".pptx", ".ppt"]),
    ("sheets", "📈 Bảng tính & Dữ liệu", [".xlsx", ".xls", ".csv"]),
    ("images", "🖼️ Hình ảnh & Trực quan", [".png", ".jpg", ".jpeg", ".webp", ".svg"]),
    ("code", "💻 Mã nguồn & Kịch bản", [".py", ".js", ".ts", ".html", ".css", ".json", ".sql", ".sh", ".yaml"]),
    ("provenance", "🌐 Tải về từ Web & Cloud", []),
    ("recent", "🕒 Sửa đổi gần đây", []),
]


class AsyncSearchWorker(QObject):
    """Long-lived non-blocking background search worker."""
    search_finished = pyqtSignal(int, dict)

    def __init__(self, engine: SearchEngine) -> None:
        super().__init__()
        self.engine = engine
        try:
            self.engine.embedder.embed_query("warmup")
            self.engine.vector_cache.preload()
        except Exception as e:
            logger.debug(f"AsyncSearchWorker warmup: {e}")

    @pyqtSlot(int, str, str, list)
    def execute_query(self, req_id: int, query: str, collection_key: str, extensions: list) -> None:
        try:
            clean_q = query.strip()
            if not clean_q:
                # Query default collection list from SQLite
                results = self._fetch_collection(collection_key, extensions)
                self.search_finished.emit(req_id, {"results": results, "query": ""})
            else:
                # Run hybrid search with optional extension filters
                response = self.engine.search(
                    clean_q,
                    limit=45,
                    use_hyde=False,
                    use_vector=True,
                )
                raw_results = response.get("results", [])
                if extensions:
                    filtered = [r for r in raw_results if r.file_ext.lower() in extensions]
                    response["results"] = filtered
                self.search_finished.emit(req_id, response)
        except Exception as e:
            logger.error(f"AsyncSearchWorker error: {e}")
            self.search_finished.emit(req_id, {"results": [], "query": query, "error": str(e)})

    def _fetch_collection(self, collection_key: str, extensions: list) -> List[SearchResultItem]:
        conn = self.engine.db.get_connection()
        cursor = conn.cursor()

        if collection_key == "provenance":
            cursor.execute("""
                SELECT * FROM documents
                WHERE content_text LIKE '%[File Provenance]%'
                ORDER BY modified_at DESC LIMIT 60
            """)
        elif extensions:
            placeholders = ",".join(["?"] * len(extensions))
            cursor.execute(f"""
                SELECT * FROM documents
                WHERE file_ext IN ({placeholders})
                ORDER BY modified_at DESC LIMIT 60
            """, extensions)
        else:
            cursor.execute("SELECT * FROM documents ORDER BY modified_at DESC LIMIT 60")

        rows = [dict(r) for r in cursor.fetchall()]
        items = []
        for r in rows:
            desc = EXT_DESCRIPTIONS.get(r["file_ext"].lower(), f"Tệp {r['file_ext'].upper()}")
            snippet = r.get("content_text", "")[:240]
            v_info = dedup_engine.get_document_version_info(r["file_path"])
            item = SearchResultItem(
                file_path=r["file_path"],
                file_name=r["file_name"],
                file_ext=r["file_ext"],
                file_size=r["file_size"],
                modified_at=r["modified_at"],
                score=100.0,
                explanation=f"{desc} • Sửa {format_relative_time(r['modified_at'])}",
                snippet=snippet,
                version_info=v_info,
            )
            items.append(item)
        return sort_search_results(items, "abc")


class AsyncQAWorker(QObject):
    """Background worker for non-blocking in-situ AI Document Q&A."""
    qa_finished = pyqtSignal(dict)

    @pyqtSlot(str, str, str)
    def ask_document(self, file_path: str, file_name: str, question: str) -> None:
        try:
            content = extract_document_content(file_path)
            qa_res = qa_engine.answer_question(content, question, file_name=file_name)
            self.qa_finished.emit(qa_res)
        except Exception as e:
            self.qa_finished.emit({"answer": f"⚠️ Lỗi xử lý: {e}", "engine": "Error"})


class ModernFinderPreview(QFrame):
    """Refined Apple HIG Inspector Panel with Image QuickLook and AI Chat."""
    ask_requested = pyqtSignal(str, str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("FinderPreview")
        self.current_item: Optional[SearchResultItem] = None
        self.current_trace: Optional[Any] = None
        self.current_plan: Optional[Dict[str, Any]] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Info Card
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #f2f2f7; border-radius: 10px; padding: 10px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(12)

        self.badge_label = QLabel("FILE")
        self.badge_label.setFixedSize(42, 42)
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_label.setStyleSheet("background-color: #007aff; color: #ffffff; font-weight: 700; font-size: 11px; border-radius: 8px;")

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.name_label = QLabel("Chọn một tệp tin")
        self.name_label.setStyleSheet("color: #1c1c1e; font-size: 14px; font-weight: 600;")
        self.name_label.setWordWrap(True)

        self.meta_sub_label = QLabel("")
        self.meta_sub_label.setStyleSheet("color: #636366; font-size: 11.5px;")
        title_col.addWidget(self.name_label)
        title_col.addWidget(self.meta_sub_label)

        h_layout.addWidget(self.badge_label)
        h_layout.addLayout(title_col, 1)
        layout.addWidget(header_frame)

        # Image Thumbnail View
        self.image_preview_box = QLabel()
        self.image_preview_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_box.setFixedHeight(150)
        self.image_preview_box.setStyleSheet("background-color: #ffffff; border: 1px solid #d1d1d6; border-radius: 10px; padding: 4px;")
        self.image_preview_box.hide()
        layout.addWidget(self.image_preview_box)

        # AI Reason Badge Card
        self.reason_card = QFrame()
        self.reason_card.setStyleSheet("background-color: #e0f2fe; border-radius: 8px; padding: 8px; border: 1px solid #7dd3fc;")
        r_layout = QVBoxLayout(self.reason_card)
        r_layout.setContentsMargins(4, 4, 4, 4)
        self.reason_title = QLabel("💡 Khớp ngữ cảnh AI:")
        self.reason_title.setStyleSheet("color: #0284c7; font-size: 11px; font-weight: 700;")
        self.reason_text = QLabel("")
        self.reason_text.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 500;")
        self.reason_text.setWordWrap(True)
        r_layout.addWidget(self.reason_title)
        r_layout.addWidget(self.reason_text)
        layout.addWidget(self.reason_card)

        # Text Quick Look Row with Minimalist CoT button
        ql_row = QHBoxLayout()
        ql_row.setSpacing(6)
        ql_label = QLabel("📄 Xem trước nội dung:")
        ql_label.setStyleSheet("color: #636366; font-size: 11px; font-weight: 600;")
        ql_row.addWidget(ql_label)
        ql_row.addStretch()

        self.cot_badge_btn = QPushButton("🧠 Suy luận CoT")
        self.cot_badge_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0284c7;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #e0f2fe;
            }
        """)
        self.cot_badge_btn.clicked.connect(self._toggle_cot_trace)
        self.cot_badge_btn.hide()
        ql_row.addWidget(self.cot_badge_btn)
        layout.addLayout(ql_row)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #1c1c1e;
                border: 1px solid #e5e5ea;
                border-radius: 8px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 11.5px;
                line-height: 1.45;
                padding: 8px;
            }
        """)
        layout.addWidget(self.preview_text, 1)

        # In-Situ AI Chat Section
        chat_card = QFrame()
        chat_card.setStyleSheet("background-color: #f8fafc; border-radius: 10px; border: 1px solid #cbd5e1; padding: 8px;")
        c_layout = QVBoxLayout(chat_card)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(6)

        c_header = QLabel("🧠 Trợ lý AI Hỏi - Đáp trực tiếp:")
        c_header.setStyleSheet("color: #0f172a; font-size: 11.5px; font-weight: 700;")
        c_layout.addWidget(c_header)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self.ask_input = QLineEdit()
        self.ask_input.setPlaceholderText("Hỏi gì đó về file này... (Nhấn Enter)")
        self.ask_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11.5px;
            }
            QLineEdit:focus {
                border: 1.5px solid #007aff;
            }
        """)
        self.ask_input.returnPressed.connect(self._trigger_ask)

        self.ask_btn = QPushButton("Hỏi AI")
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background-color: #007aff;
                color: #ffffff;
                font-weight: 600;
                font-size: 11.5px;
                border-radius: 6px;
                padding: 6px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.ask_btn.clicked.connect(self._trigger_ask)
        input_row.addWidget(self.ask_input, 1)
        input_row.addWidget(self.ask_btn)
        c_layout.addLayout(input_row)

        self.qa_response_box = QLabel("")
        self.qa_response_box.setStyleSheet("""
            background-color: #ffffff;
            color: #1e293b;
            font-size: 11.5px;
            padding: 8px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            line-height: 1.4;
        """)
        self.qa_response_box.setWordWrap(True)
        self.qa_response_box.hide()
        c_layout.addWidget(self.qa_response_box)

        layout.addWidget(chat_card)

    def set_item(self, item: Optional[SearchResultItem]) -> None:
        self.current_item = item
        self.qa_response_box.hide()
        self.qa_response_box.setText("")
        self.ask_input.clear()

        if not item:
            self.badge_label.setText("FILE")
            self.badge_label.setStyleSheet("background-color: #e5e5ea; color: #636366; font-weight: 700; border-radius: 8px;")
            self.name_label.setText("Chọn một tệp tin")
            self.meta_sub_label.setText("")
            self.image_preview_box.hide()
            self.reason_card.hide()
            self.preview_text.setPlainText("")
            return

        info = get_ext_badge_info(item.file_ext)
        self.badge_label.setText(info["label"])
        self.badge_label.setStyleSheet(f"background-color: {info['bg']}; color: {info['fg']}; font-weight: 700; font-size: 11px; border-radius: 8px;")
        self.name_label.setText(item.file_name)
        self.meta_sub_label.setText(f"{item.file_size_formatted} • Sửa {item.modified_formatted}")

        # Image Thumbnail
        ext = item.file_ext.lower()
        if ext in [".png", ".jpg", ".jpeg", ".webp"] and os.path.exists(item.file_path):
            pix = QPixmap(item.file_path)
            if not pix.isNull():
                scaled = pix.scaled(280, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_preview_box.setPixmap(scaled)
                self.image_preview_box.show()
            else:
                self.image_preview_box.hide()
        else:
            self.image_preview_box.hide()

        # Reason badge
        if item.explanation:
            self.reason_card.show()
            self.reason_text.setText(item.explanation)
        else:
            self.reason_card.hide()

        # Preview content
        self.preview_text.setPlainText(item.snippet or "(Không có đoạn trích nội dung)")

    def _trigger_ask(self) -> None:
        q = self.ask_input.text().strip()
        if not q or not self.current_item:
            return

        self.qa_response_box.show()
        self.qa_response_box.setText("⏳ <i>Đang phân tích tài liệu và suy luận...</i>")
        self.ask_requested.emit(self.current_item.file_path, self.current_item.file_name, q)

    def set_qa_answer(self, result: Dict[str, Any]) -> None:
        ans = result.get("answer", "Không có câu trả lời.")
        engine = result.get("engine", "AI")
        self.qa_response_box.show()
        self.qa_response_box.setText(f"<b>💡 {engine}:</b>\n{ans}")

    def _toggle_cot_trace(self) -> None:
        if not self.current_trace:
            return
        if self.preview_text.toPlainText().startswith("### 🧠 FR-CoT"):
            if self.current_item:
                self.preview_text.setPlainText(self.current_item.snippet or "(Không có đoạn trích nội dung)")
            conf_pct = int(self.current_trace.final_confidence * 100)
            status_tag = "Đủ" if self.current_trace.is_sufficient else "Phần nào"
            self.cot_badge_btn.setText(f"🧠 CoT: {conf_pct}% ({status_tag})")
        else:
            self.preview_text.setPlainText(self.current_trace.render_markdown())
            self.cot_badge_btn.setText("📄 Xem lại tệp")

    def set_reasoning_trace(self, trace: Optional[Any], plan: Optional[Dict[str, Any]] = None) -> None:
        self.current_trace = trace
        self.current_plan = plan
        if trace and hasattr(trace, "steps") and trace.steps:
            conf_pct = int(trace.final_confidence * 100)
            status_tag = "Đủ" if trace.is_sufficient else "Phần nào"
            self.cot_badge_btn.setText(f"🧠 CoT: {conf_pct}% ({status_tag})")
            self.cot_badge_btn.show()
        else:
            self.cot_badge_btn.hide()



class FinderWindow(QMainWindow):
    """Complete, responsive, and gorgeous macOS AI Finder Application Window."""
    search_requested = pyqtSignal(int, str, str, list)
    ask_requested = pyqtSignal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.db = Database(config.db_path)
        self.engine = SearchEngine(self.db)
        self.active_collection_idx = 0
        self._request_id = 0
        self.current_results: List[SearchResultItem] = []
        self.current_sort_mode = "abc"

        # Search debounce timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(90)
        self.search_timer.timeout.connect(self._dispatch_search)

        self._init_threads()
        self._init_window()
        self._init_ui()
        self._init_shortcuts()

        # Initial load
        self._dispatch_search()

    def _init_threads(self) -> None:
        # Crucial: Unparented QThread(None) prevents Qt C++ child destruction SIGABRT
        self.search_thread = QThread(None)
        self.search_worker = AsyncSearchWorker(self.engine)
        self.search_worker.moveToThread(self.search_thread)
        self.search_requested.connect(self.search_worker.execute_query)
        self.search_worker.search_finished.connect(self._on_search_finished)
        self.search_thread.start()

        # QA Thread
        self.qa_thread = QThread(None)
        self.qa_worker = AsyncQAWorker()
        self.qa_worker.moveToThread(self.qa_thread)
        self.ask_requested.connect(self.qa_worker.ask_document)
        self.qa_worker.qa_finished.connect(self._on_qa_finished)
        self.qa_thread.start()

    def _init_window(self) -> None:
        self.setWindowTitle("rat — macOS Smart AI Finder")
        self.resize(1140, 720)
        self.setMinimumSize(920, 580)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f2f2f7;
            }
            QSplitter::handle {
                background-color: #d1d1d6;
                width: 1px;
            }
        """)

    def _init_ui(self) -> None:
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(1)

        # 1. Left Sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(230)
        sidebar_frame.setStyleSheet("background-color: #e5e5ea; border-right: 1px solid #d1d1d6;")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 16, 10, 16)
        sidebar_layout.setSpacing(4)

        sb_header = QLabel("THƯ MỤC THÔNG MINH")
        sb_header.setStyleSheet("color: #8e8e93; font-size: 10.5px; font-weight: 700; padding-left: 8px; margin-bottom: 4px;")
        sidebar_layout.addWidget(sb_header)

        self.sidebar_list = QListWidget()
        self.sidebar_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 8px;
                color: #1c1c1e;
                font-size: 12.5px;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background-color: #007aff;
                color: #ffffff;
                font-weight: 600;
            }
            QListWidget::item:hover:!selected {
                background-color: #dcdce2;
            }
        """)

        for key, label, _ in COLLECTION_DEFINITIONS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.sidebar_list.addItem(item)

        self.sidebar_list.setCurrentRow(0)
        self.sidebar_list.currentRowChanged.connect(self._on_sidebar_changed)
        sidebar_layout.addWidget(self.sidebar_list, 1)

        # Watched folders info
        wf_header = QLabel("VỊ TRÍ THEO DÕI")
        wf_header.setStyleSheet("color: #8e8e93; font-size: 10.5px; font-weight: 700; padding-left: 8px; margin-top: 12px;")
        sidebar_layout.addWidget(wf_header)

        watched_box = QLabel("• ~/Downloads\n• ~/Documents\n• ~/Desktop")
        watched_box.setStyleSheet("color: #48484a; font-size: 11.5px; padding-left: 10px; line-height: 1.5;")
        sidebar_layout.addWidget(watched_box)

        main_splitter.addWidget(sidebar_frame)

        # 2. Center Panel (Toolbar + Results List)
        center_frame = QFrame()
        center_frame.setStyleSheet("background-color: #ffffff;")
        center_layout = QVBoxLayout(center_frame)
        center_layout.setContentsMargins(16, 14, 16, 14)
        center_layout.setSpacing(10)

        # Top Search Bar Row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Tìm kiếm tự nhiên: 'slide nami', 'báo cáo tài chính', 'ảnh biểu đồ'...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #f2f2f7;
                color: #1c1c1e;
                font-size: 13.5px;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                background-color: #ffffff;
                border: 1.5px solid #007aff;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.search_input, 1)

        btn_open = QPushButton("Mở")
        btn_open.setStyleSheet("background-color: #007aff; color: #ffffff; font-weight: 600; border-radius: 6px; padding: 7px 14px; font-size: 12px;")
        btn_open.clicked.connect(self._open_selected_file)
        search_row.addWidget(btn_open)

        btn_reveal = QPushButton("Finder")
        btn_reveal.setStyleSheet("background-color: #f2f2f7; color: #1c1c1e; border: 1px solid #d1d1d6; border-radius: 6px; padding: 7px 12px; font-size: 12px;")
        btn_reveal.clicked.connect(self._reveal_selected_file)
        search_row.addWidget(btn_reveal)

        center_layout.addLayout(search_row)

        # Status Bar & Sort Selector Row
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_label = QLabel("Đang tải dữ liệu...")
        self.status_label.setStyleSheet("color: #8e8e93; font-size: 11px;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        sort_label = QLabel("Sắp xếp:")
        sort_label.setStyleSheet("color: #636366; font-size: 11.5px; font-weight: 500;")
        status_row.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("🔤 Tên A-Z (Bảng chữ cái)", "abc")
        self.sort_combo.addItem("🕒 Mới nhất (Thời gian gần nhất)", "recent")
        self.sort_combo.addItem("🎯 Độ phù hợp (Khớp nhất)", "score")
        self.sort_combo.addItem("📦 Kích thước (Lớn → Nhỏ)", "size")
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #f2f2f7;
                color: #1c1c1e;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11.5px;
                font-weight: 500;
            }
            QComboBox:hover {
                background-color: #e5e5ea;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        status_row.addWidget(self.sort_combo)
        center_layout.addLayout(status_row)

        # Beautiful Custom Rendered Results List
        self.results_list = QListWidget()
        self.results_list.setItemDelegate(AppleSpotlightDelegate(self.results_list))
        self.results_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 10px;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #f2f2f7;
            }
            QListWidget::item:selected {
                background-color: #e5f1fb;
                border-radius: 8px;
            }
        """)
        self.results_list.currentRowChanged.connect(self._on_list_row_changed)
        self.results_list.itemDoubleClicked.connect(self._open_selected_file)
        center_layout.addWidget(self.results_list, 1)

        main_splitter.addWidget(center_frame)

        # 3. Right SOTA Inspector Panel
        self.preview_panel = PreviewPanel()
        self.preview_panel.setFixedWidth(350)
        self.preview_panel.setStyleSheet("background-color: #fbfbfd; border-left: 1px solid #e2e8f0;")
        self.preview_panel.ask_requested.connect(self._on_ask_requested)
        main_splitter.addWidget(self.preview_panel)

        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)

        # Root container with SOTA Raycast Action Footer
        root_widget = QWidget()
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(main_splitter, 1)

        # Bottom SOTA Action Footer
        footer = QFrame()
        footer.setObjectName("ActionFooter")
        footer.setStyleSheet("""
            QFrame#ActionFooter {
                background-color: #f8fafc;
                border-top: 1px solid #e2e8f0;
                padding: 6px 14px;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 5, 14, 5)
        footer_layout.setSpacing(10)

        self.footer_live_lbl = QLabel("🟢 Sẵn sàng")
        self.footer_live_lbl.setStyleSheet("color: #475569; font-size: 11px; font-weight: 500;")
        footer_layout.addWidget(self.footer_live_lbl)
        footer_layout.addStretch()

        hotkeys = [
            ("Space", "Xem nhanh"),
            ("↵", "Mở"),
            ("⌘↵", "Finder"),
            ("⌘C", "Copy"),
            ("⌘F", "Tìm"),
            ("⌘⇧Space", "Spotlight"),
        ]
        for key, desc in hotkeys:
            badge = QLabel(key)
            badge.setProperty("class", "HotkeyBadge")
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #64748b; font-size: 10.5px; margin-right: 4px;")
            footer_layout.addWidget(badge)
            footer_layout.addWidget(desc_label)

        root_layout.addWidget(footer)
        self.setCentralWidget(root_widget)

    def _init_shortcuts(self) -> None:
        """Bind native macOS shortcuts."""
        # Space -> Quick Look
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._preview_quick_look)
        # Cmd + C -> Copy Path
        QShortcut(QKeySequence.StandardKey.Copy, self, self._copy_file_path)
        # Cmd + O -> Open File
        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_O), self, self._open_selected_file)
        # Cmd + R -> Reveal in Finder
        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_R), self, self._reveal_selected_file)
        # Cmd + F -> Focus search
        QShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_F), self, self._focus_search)
        # Escape -> Reset search
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._clear_search)

    def _on_sidebar_changed(self, row: int) -> None:
        if 0 <= row < len(COLLECTION_DEFINITIONS):
            self.active_collection_idx = row
            self.search_input.clear()
            self._dispatch_search()

    def _on_search_text_changed(self, text: str) -> None:
        self.search_timer.start()

    def _dispatch_search(self) -> None:
        self._request_id += 1
        query = self.search_input.text()
        col_key, _, exts = COLLECTION_DEFINITIONS[self.active_collection_idx]
        self.status_label.setText("⚡ Đang tìm kiếm...")
        self.search_requested.emit(self._request_id, query, col_key, exts)

    def _on_sort_changed(self, index: int) -> None:
        mode = self.sort_combo.itemData(index)
        if mode:
            self.current_sort_mode = mode
            self._populate_results_list()

    def _populate_results_list(self) -> None:
        sorted_items = sort_search_results(self.current_results, self.current_sort_mode)
        self.current_results = sorted_items

        self.results_list.clear()
        for item in sorted_items:
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(self.results_list.width(), 44))
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.results_list.addItem(list_item)

        if sorted_items:
            self.results_list.setCurrentRow(0)
        else:
            self.preview_panel.set_item(None)

    @pyqtSlot(int, dict)
    def _on_search_finished(self, req_id: int, response: Dict[str, Any]) -> None:
        if req_id != self._request_id:
            return  # Discard outdated request

        results: List[SearchResultItem] = response.get("results", [])
        self.current_results = results

        trace = response.get("reasoning_trace")
        plan = response.get("plan")
        if trace and trace.steps:
            conf_pct = int(trace.final_confidence * 100)
            self.status_label.setText(f"Hiển thị {len(results)} tệp  •  🧠 CoT: {conf_pct}% ({trace.total_latency_ms}ms)")
            self.footer_live_lbl.setText(f"🟢 {len(results)} tệp  •  ⚡ {response.get('latency_ms', 0)}ms  •  🧠 CoT {conf_pct}%")
        else:
            self.status_label.setText(f"Hiển thị {len(results)} tệp tin")
            self.footer_live_lbl.setText(f"🟢 {len(results)} tệp  •  ⚡ {response.get('latency_ms', 0)}ms")

        self.preview_panel.set_reasoning_trace(trace, plan)
        self._populate_results_list()

    def _on_list_row_changed(self, row: int) -> None:
        if 0 <= row < len(self.current_results):
            self.preview_panel.set_item(self.current_results[row])

    def _on_ask_requested(self, file_path: str, file_name: str, question: str) -> None:
        self.ask_requested.emit(file_path, file_name, question)

    @pyqtSlot(dict)
    def _on_qa_finished(self, qa_res: Dict[str, Any]) -> None:
        self.preview_panel.set_qa_answer(qa_res)

    def _open_selected_file(self) -> None:
        row = self.results_list.currentRow()
        if 0 <= row < len(self.current_results):
            open_file_default(self.current_results[row].file_path)

    def _reveal_selected_file(self) -> None:
        row = self.results_list.currentRow()
        if 0 <= row < len(self.current_results):
            reveal_in_finder(self.current_results[row].file_path)

    def _preview_quick_look(self) -> None:
        row = self.results_list.currentRow()
        if 0 <= row < len(self.current_results):
            item = self.current_results[row]
            if platform.system() == "Darwin" and os.path.exists(item.file_path):
                subprocess.Popen(["qlmanage", "-p", item.file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _copy_file_path(self) -> None:
        row = self.results_list.currentRow()
        if 0 <= row < len(self.current_results):
            cb = QGuiApplication.clipboard()
            if cb:
                cb.setText(self.current_results[row].file_path)
                self.status_label.setText(f"✓ Đã sao chép: {self.current_results[row].file_name}")

    def _focus_search(self) -> None:
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _clear_search(self) -> None:
        self.search_input.clear()
        self.results_list.setFocus()

    def shutdown(self) -> None:
        """Gracefully stop background search and QA threads with zero hang/crash."""
        try:
            if hasattr(self, "search_timer") and self.search_timer.isActive():
                self.search_timer.stop()
        except Exception:
            pass

        if hasattr(self, "search_thread") and self.search_thread is not None:
            try:
                if self.search_thread.isRunning():
                    self.search_thread.quit()
                    if not self.search_thread.wait(1500):
                        logger.warning("Finder search_thread did not exit in 1.5s; forcing...")
                        self.search_thread.terminate()
                        self.search_thread.wait(500)
                self.search_thread.deleteLater()
            except Exception as e:
                logger.debug(f"Finder shutdown search_thread note: {e}")
            finally:
                self.search_thread = None

        if hasattr(self, "qa_thread") and self.qa_thread is not None:
            try:
                if self.qa_thread.isRunning():
                    self.qa_thread.quit()
                    if not self.qa_thread.wait(1500):
                        logger.warning("Finder qa_thread did not exit in 1.5s; forcing...")
                        self.qa_thread.terminate()
                        self.qa_thread.wait(500)
                self.qa_thread.deleteLater()
            except Exception as e:
                logger.debug(f"Finder shutdown qa_thread note: {e}")
            finally:
                self.qa_thread = None

    def closeEvent(self, event: Any) -> None:
        app = QApplication.instance()
        if app and not getattr(app, "_is_quitting", False):
            event.ignore()
            self.hide()
            return

        self.shutdown()
        event.accept()


def run_finder() -> None:
    """Run standalone Finder window."""
    import sys
    app = QApplication(sys.argv)
    window = FinderWindow()
    window.show()
    sys.exit(app.exec())
