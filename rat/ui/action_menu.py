"""
rat.ui.action_menu — Raycast-style Command Action Palette (⌘K Menu).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rat.engine.reranker import SearchResultItem


class ActionItemWidget(QWidget):
    """Row widget for an action item in the ⌘K menu."""

    def __init__(self, title: str, shortcut: str, description: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Title and description
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #1c1917; font-size: 13px; font-weight: 500;")
        text_layout.addWidget(self.title_label)

        if description:
            self.desc_label = QLabel(description)
            self.desc_label.setStyleSheet("color: #78716c; font-size: 11px;")
            text_layout.addWidget(self.desc_label)

        layout.addLayout(text_layout, 1)

        # Shortcut badge
        if shortcut:
            self.badge = QLabel(shortcut)
            self.badge.setStyleSheet("""
                background-color: #fffefa;
                color: #6d6258;
                border: 1px solid #d8cfc3;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: 600;
                font-family: -apple-system, BlinkMacSystemFont, "SF Mono", Menlo, monospace;
            """)
            layout.addWidget(self.badge)


class ActionMenuDialog(QDialog):
    """Raycast ⌘K Action Palette Modal."""
    action_triggered = pyqtSignal(str)

    def __init__(self, target_item: Optional[SearchResultItem], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.target_item = target_item
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(480, 360)
        self._init_ui()

    def _init_ui(self) -> None:
        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(136, 124, 112, 60))
        shadow.setOffset(0, 8)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        container = QFrame()
        container.setGraphicsEffect(shadow)
        container.setStyleSheet("""
            QFrame {
                background-color: #fffdf9;
                border: 1px solid #d9d0c5;
                border-radius: 16px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(6)

        # Target item label
        header_text = f"Tác vụ cho: {self.target_item.file_name}" if self.target_item else "Menu tác vụ nhanh"
        header_label = QLabel(header_text)
        header_label.setStyleSheet("color: #887c70; font-size: 11px; font-weight: 600; padding: 4px 6px;")
        container_layout.addWidget(header_label)

        # Filter box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Lọc hành động...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #1c1917;
                border: 1px solid #d5cabc;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1.5px solid #e2cd98;
            }
        """)
        self.search_box.textChanged.connect(self._filter_actions)
        container_layout.addWidget(self.search_box)

        # Action list
        self.action_list = QListWidget()
        self.action_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border-radius: 6px;
                margin: 2px 0px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #f7eedb;
                border: 1px solid #e2cd98;
            }
            QListWidget::item:hover {
                background-color: #f7f1e8;
            }
        """)
        self.action_list.itemActivated.connect(self._on_item_activated)
        container_layout.addWidget(self.action_list, 1)

        main_layout.addWidget(container)

        self._populate_actions()
        self.action_list.setCurrentRow(0)

    def _populate_actions(self) -> None:
        self.actions = [
            ("open", "⚡ Mở tệp (Open)", "↵", "Mở bằng ứng dụng mặc định của hệ thống"),
            ("quicklook", "👁️ Xem nhanh (Quick Look)", "Space / ⌘Y", "Mở cửa sổ xem nhanh nguyên bản của macOS"),
            ("finder", "📁 Mở trong Finder", "⌘↵", "Mở thư mục chứa và chọn tệp tin"),
            ("terminal", "💻 Mở thư mục trong Terminal", "⌥↵", "Mở thư mục chứa tệp này trong Terminal"),
            ("copy_path", "📋 Sao chép đường dẫn (Copy Path)", "⌘C", "Sao chép đường dẫn tuyệt đối vào clipboard"),
            ("copy_content", "📄 Sao chép nội dung văn bản", "⌘⇧C", "Sao chép toàn bộ văn bản đã trích xuất"),
            ("ask_ai", "🧠 Hỏi đáp AI với tệp này", "⌘A", "Mở khung trò chuyện với SLM Qwen2.5"),
            ("schedule", "🍵 Ghép Lịch CLB & Khung Giờ Vàng", "⌘T", "Mở bộ ghép thời khóa biểu sinh viên & tìm giờ rảnh"),
            ("widget", "✦ Trợ Lý TKB & Claude Form Mode", "⌘W", "Mở widget dạng thẻ Claude tương tác linh hoạt góc màn hình"),
            ("reindex_file", "🔄 Quét lại tệp tin này", "⌘R", "Cập nhật lại chỉ mục và vector cho tệp"),
            ("settings", "⚙️ Cài đặt hệ thống", "⌘,", "Mở bảng cấu hình thư mục và mô hình AI"),
        ]

        for action_id, title, shortcut, desc in self.actions:
            item = QListWidgetItem(self.action_list)
            item.setData(Qt.ItemDataRole.UserRole, action_id)
            widget = ActionItemWidget(title, shortcut, desc)
            item.setSizeHint(widget.sizeHint())
            self.action_list.addItem(item)
            self.action_list.setItemWidget(item, widget)

    def _filter_actions(self, text: str) -> None:
        search = text.lower().strip()
        for i in range(self.action_list.count()):
            item = self.action_list.item(i)
            action_id = item.data(Qt.ItemDataRole.UserRole)
            match = any(search in a[1].lower() or search in a[3].lower() for a in self.actions if a[0] == action_id)
            item.setHidden(not match)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        action_id = item.data(Qt.ItemDataRole.UserRole)
        self.action_triggered.emit(action_id)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            curr = self.action_list.currentRow()
            if event.key() == Qt.Key.Key_Down and curr < self.action_list.count() - 1:
                self.action_list.setCurrentRow(curr + 1)
            elif event.key() == Qt.Key.Key_Up and curr > 0:
                self.action_list.setCurrentRow(curr - 1)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            curr_item = self.action_list.currentItem()
            if curr_item:
                self._on_item_activated(curr_item)
        else:
            super().keyPressEvent(event)
