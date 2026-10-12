"""
rat.ui.naming_dialog — macOS Sequoia styled AI Filename Suggestion & Renaming Dialog.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rat.engine.naming import (
    resolve_filename_conflict,
    sanitize_filename,
    suggest_document_names,
)
from rat.engine.reranker import SearchResultItem
from rat.ui.theme import get_ext_badge_info

logger = logging.getLogger("rat.ui.naming")


class NamingWorker(QThread):
    """Background worker to query SLM/LLM for filename suggestions without freezing UI."""
    results_ready = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        excerpt: str,
        extension: str,
        instructions: str = "",
        existing_filenames: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.excerpt = excerpt
        self.extension = extension
        self.instructions = instructions
        self.existing_filenames = existing_filenames or []

    def run(self) -> None:
        try:
            names = suggest_document_names(
                title=self.title,
                excerpt=self.excerpt,
                extension=self.extension,
                instructions=self.instructions,
                count=5,
                existing_filenames=self.existing_filenames,
                fallback_on_error=True,
            )
            self.results_ready.emit(names)
        except Exception as e:
            logger.error(f"NamingWorker error: {e}", exc_info=True)
            self.failed.emit(str(e))


class SuggestionRowWidget(QWidget):
    """Row widget for each filename suggestion."""

    def __init__(self, filename: str, badge_text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("color: #1c1917; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.name_label, 1)

        if badge_text:
            badge = QLabel(badge_text)
            badge.setStyleSheet("""
                background-color: #f5eedf;
                color: #8b6e3f;
                border: 1px solid #e5d5be;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 600;
            """)
            layout.addWidget(badge)


class FilenameSuggestionDialog(QDialog):
    """Raycast/Sequoia modal to inspect and apply AI-suggested document names."""
    file_renamed = pyqtSignal(str, str)  # old_path, new_path

    def __init__(
        self,
        target_item: Optional[SearchResultItem] = None,
        file_path: Optional[str] = None,
        title: str = "",
        excerpt: str = "",
        extension: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.target_item = target_item

        # Resolve paths and context
        if target_item:
            self.file_path = target_item.file_path
            self.title = target_item.file_name
            self.excerpt = target_item.snippet or ""
            self.extension = target_item.file_ext or os.path.splitext(target_item.file_name)[1]
        else:
            self.file_path = file_path or ""
            self.title = title or (os.path.basename(file_path) if file_path else "")
            self.excerpt = excerpt
            self.extension = extension or (os.path.splitext(self.title)[1] if self.title else ".docx")

        if not self.extension:
            self.extension = ".docx"

        # Attempt to read excerpt from file on disk if empty
        if not self.excerpt and self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    self.excerpt = f.read(1500)
            except Exception:
                pass

        self.worker: Optional[NamingWorker] = None
        self.existing_filenames: List[str] = []
        if self.file_path and os.path.exists(self.file_path):
            parent_dir = os.path.dirname(self.file_path)
            if os.path.isdir(parent_dir):
                try:
                    self.existing_filenames = os.listdir(parent_dir)
                except Exception:
                    self.existing_filenames = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(540, 480)
        self._init_ui()
        self._start_generation()

    def _init_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(136, 124, 112, 70))
        shadow.setOffset(0, 10)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setGraphicsEffect(shadow)
        container.setStyleSheet("""
            QFrame {
                background-color: #fffdf9;
                border: 1px solid #d9d0c5;
                border-radius: 16px;
            }
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(10)

        # 1. Header Card
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # File badge
        badge_info = get_ext_badge_info(self.extension)
        badge_text = badge_info.get("label", "FILE")
        badge_color = badge_info.get("bg", "#8c7e6f")
        badge_fg = badge_info.get("fg", "#ffffff")
        badge_lbl = QLabel(badge_text)
        badge_lbl.setStyleSheet(f"""
            background-color: {badge_color};
            color: {badge_fg};
            font-size: 11px;
            font-weight: 700;
            border-radius: 6px;
            padding: 6px 8px;
        """)
        header_layout.addWidget(badge_lbl)

        # Info texts
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        h_title = QLabel(f"🏷️ Gợi ý tên tệp AI: {self.title}")
        h_title.setStyleSheet("color: #1c1917; font-size: 14px; font-weight: 600;")
        title_box.addWidget(h_title)

        dir_hint = os.path.dirname(self.file_path) if self.file_path else "Tài liệu mới"
        h_path = QLabel(f"📁 {dir_hint}")
        h_path.setStyleSheet("color: #78716c; font-size: 11px;")
        title_box.addWidget(h_path)

        header_layout.addLayout(title_box, 1)
        c_layout.addLayout(header_layout)

        # 2. Instruction Box
        instr_layout = QHBoxLayout()
        instr_layout.setSpacing(6)

        self.instr_input = QLineEdit()
        self.instr_input.setPlaceholderText("Yêu cầu tùy chỉnh (vd: snake_case, không dấu, thêm ngày tháng...)")
        self.instr_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #1c1917;
                border: 1px solid #d5cabc;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1.5px solid #d4a359;
            }
        """)
        self.instr_input.returnPressed.connect(self._start_generation)
        instr_layout.addWidget(self.instr_input, 1)

        self.btn_regenerate = QPushButton("✨ Gợi ý lại")
        self.btn_regenerate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_regenerate.setStyleSheet("""
            QPushButton {
                background-color: #f7eedb;
                color: #5c4d3c;
                border: 1px solid #d9c8aa;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #efe2c8;
            }
        """)
        self.btn_regenerate.clicked.connect(self._start_generation)
        instr_layout.addWidget(self.btn_regenerate)

        c_layout.addLayout(instr_layout)

        # 3. Status label
        self.status_label = QLabel("⏳ Đang phân tích nội dung và tạo gợi ý tên tệp...")
        self.status_label.setStyleSheet("color: #8b6e3f; font-size: 11px; font-style: italic; padding: 0px 2px;")
        c_layout.addWidget(self.status_label)

        # 4. List of Suggestions
        self.suggestion_list = QListWidget()
        self.suggestion_list.setStyleSheet("""
            QListWidget {
                background-color: #faf7f2;
                border: 1px solid #e0d5c7;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                border-radius: 6px;
                margin: 2px 0px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #f7eedb;
                border: 1px solid #d4a359;
            }
            QListWidget::item:hover {
                background-color: #f2ebe0;
            }
        """)
        self.suggestion_list.itemClicked.connect(self._on_item_clicked)
        self.suggestion_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        c_layout.addWidget(self.suggestion_list, 1)

        # 5. Selected / Custom Name Input
        target_layout = QHBoxLayout()
        target_layout.setSpacing(6)

        target_lbl = QLabel("Tên áp dụng:")
        target_lbl.setStyleSheet("color: #44403c; font-size: 12px; font-weight: 600;")
        target_layout.addWidget(target_lbl)

        self.target_input = QLineEdit()
        self.target_input.setText(self.title)
        self.target_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #1c1917;
                border: 1px solid #d5cabc;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 1.5px solid #d4a359;
            }
        """)
        target_layout.addWidget(self.target_input, 1)
        c_layout.addLayout(target_layout)

        # 6. Action Buttons Bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_copy = QPushButton("📋 Sao chép tên")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #57534e;
                border: 1px solid #d5cabc;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f5f0e8;
            }
        """)
        self.btn_copy.clicked.connect(self._copy_chosen_name)
        btn_layout.addWidget(self.btn_copy)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Đóng (Esc)")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #78716c;
                border: 1px solid #d5cabc;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f5f0e8;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("🏷️ Đổi tên tệp (↵)")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #d4a359;
                color: #ffffff;
                border: 1px solid #bf8e43;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #c7964b;
            }
        """)
        self.btn_apply.clicked.connect(self._apply_rename)
        btn_layout.addWidget(self.btn_apply)

        c_layout.addLayout(btn_layout)
        main_layout.addWidget(container)

    def _start_generation(self) -> None:
        """Start background worker to generate names."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(500)

        instructions = self.instr_input.text().strip()
        self.status_label.setText("⏳ Đang phân tích nội dung và tạo gợi ý tên tệp...")
        self.suggestion_list.clear()

        self.worker = NamingWorker(
            title=self.title,
            excerpt=self.excerpt,
            extension=self.extension,
            instructions=instructions,
            existing_filenames=self.existing_filenames,
            parent=self,
        )
        self.worker.results_ready.connect(self._on_suggestions_ready)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_suggestions_ready(self, names: List[str]) -> None:
        self.suggestion_list.clear()
        if not names:
            self.status_label.setText("⚠️ Không tạo được tên phù hợp. Bạn có thể tự gõ tên mới bên dưới.")
            return

        self.status_label.setText(f"✓ Đã tạo {len(names)} gợi ý tên phù hợp:")
        for idx, name in enumerate(names, 1):
            item = QListWidgetItem(self.suggestion_list)
            item.setData(Qt.ItemDataRole.UserRole, name)
            widget = SuggestionRowWidget(name, badge_text=f"#{idx}")
            item.setSizeHint(widget.sizeHint())
            self.suggestion_list.addItem(item)
            self.suggestion_list.setItemWidget(item, widget)

        # Preselect first suggestion
        if self.suggestion_list.count() > 0:
            self.suggestion_list.setCurrentRow(0)
            first_name = names[0]
            self.target_input.setText(first_name)

    def _on_worker_failed(self, error_msg: str) -> None:
        self.status_label.setText(f"⚠️ Quá trình gọi AI gặp lỗi: {error_msg}")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.target_input.setText(name)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._on_item_clicked(item)
        self._apply_rename()

    def _copy_chosen_name(self) -> None:
        name = self.target_input.text().strip()
        if name:
            clipboard = QApplication.clipboard()
            clipboard.setText(name)
            self.status_label.setText(f"📋 Đã sao chép '{name}' vào bộ nhớ tạm.")

    def _apply_rename(self) -> None:
        """Apply renaming operation to the target file."""
        chosen_name = self.target_input.text().strip()
        if not chosen_name:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập hoặc chọn tên tệp.")
            return

        # Sanitize and ensure extension
        sanitized = sanitize_filename(chosen_name, extension=self.extension)

        if not self.file_path or not os.path.exists(self.file_path):
            # No physical file on disk (e.g. untitled virtual document)
            self._copy_chosen_name()
            self.accept()
            return

        parent_dir = os.path.dirname(self.file_path)
        existing_in_dir = os.listdir(parent_dir) if os.path.isdir(parent_dir) else []
        # Exclude self from collision check
        existing_other = [f for f in existing_in_dir if f.lower() != os.path.basename(self.file_path).lower()]
        final_name = resolve_filename_conflict(sanitized, existing_other, extension=self.extension)
        new_path = os.path.join(parent_dir, final_name)

        if os.path.abspath(self.file_path) == os.path.abspath(new_path):
            self.accept()
            return

        try:
            os.rename(self.file_path, new_path)
            logger.info(f"Renamed '{self.file_path}' to '{new_path}'")
            old_path = self.file_path
            self.file_path = new_path
            self.title = final_name

            if self.target_item:
                self.target_item.file_path = new_path
                self.target_item.file_name = final_name

            self.file_renamed.emit(old_path, new_path)
            self.accept()
        except Exception as e:
            logger.error(f"Failed to rename file: {e}", exc_info=True)
            QMessageBox.critical(self, "Lỗi đổi tên", f"Không thể đổi tên tệp:\n{e}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.instr_input.hasFocus():
                self._apply_rename()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
