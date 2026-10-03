"""Small, actionable file rows shared by the quick surface and chat."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from rat.engine.reranker import SearchResultItem
from rat.ui.theme import get_ext_badge_info


class ElidedLabel(QLabel):
    """Keep long filenames from widening the whole overlay; tooltip keeps the original."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.full_text = text
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setToolTip(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideMiddle, self.width()))

    def set_full_text(self, text: str):
        self.full_text = text
        self.setToolTip(text)
        self.setText(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, self.width()))


class CompactFileRow(QFrame):
    open_requested = pyqtSignal(object)
    preview_requested = pyqtSignal(object)
    reveal_requested = pyqtSignal(object)
    ROW_HEIGHT = 48

    def __init__(self, item: SearchResultItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("CompactFileRow")
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setStyleSheet("""
            QFrame#CompactFileRow { background: transparent; border: none; }
            QLabel { background: transparent; border: none; }
            QPushButton {
                background: transparent; border: none; border-radius: 6px;
                color: #635C51; font-size: 11px; padding: 4px 7px;
            }
            QPushButton:hover, QPushButton:focus { background: #EDE5D6; color: #302B24; }
            QPushButton#OpenCompactFile { background: #F0E2C4; color: #56401D; }
            QPushButton#OpenCompactFile:hover { background: #E8D4AA; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        info = get_ext_badge_info(item.file_ext)
        color = QColor(info["bg"])
        tint = QColor(*[round(component * 0.12 + 255 * 0.88) for component in color.getRgb()[:3]])
        badge = QLabel(info["label"])
        badge.setFixedSize(34, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {tint.name()}; color: {info['border']}; border-radius: 6px; "
            "font-size: 9px; font-weight: 600;"
        )
        layout.addWidget(badge)

        details = QVBoxLayout()
        details.setSpacing(2)
        self.name_label = ElidedLabel(item.file_name)
        self.name_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #302B24;")
        details.addWidget(self.name_label)
        folder = Path(item.file_path).parent.name
        self.detail_label = ElidedLabel(f"{folder} · {item.file_size_formatted} · {item.modified_formatted}")
        self.detail_label.setStyleSheet("font-size: 10px; color: #766E63;")
        details.addWidget(self.detail_label)
        layout.addLayout(details, 1)

        self.btn_preview = QPushButton("Xem nhanh")
        self.btn_preview.setToolTip("Xem nhanh tệp (Space)")
        self.btn_preview.setAccessibleName(f"Xem nhanh {item.file_name}")
        self.btn_preview.clicked.connect(lambda: self.preview_requested.emit(self.item))
        self.btn_open = QPushButton("Mở")
        self.btn_open.setObjectName("OpenCompactFile")
        self.btn_open.setToolTip("Mở tệp (Enter)")
        self.btn_open.setAccessibleName(f"Mở {item.file_name}")
        self.btn_open.clicked.connect(lambda: self.open_requested.emit(self.item))
        self.btn_reveal = QPushButton("↗")
        self.btn_reveal.setToolTip("Hiện trong Finder (⌘Enter)")
        self.btn_reveal.setAccessibleName(f"Hiện {item.file_name} trong Finder")
        self.btn_reveal.clicked.connect(lambda: self.reveal_requested.emit(self.item))
        for button in (self.btn_preview, self.btn_open, self.btn_reveal):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(button)
