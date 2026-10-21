"""
rat.ui.onboarding_dialog — Apple-standard First-Run Onboarding & Permissions Wizard.
Guides new users through granting macOS Accessibility and Full Disk Access permissions,
and selecting initial directories to watch.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rat.config import DEFAULT_WATCH_DIRS, config


def check_accessibility_status() -> bool:
    """Check if the process is trusted for macOS Accessibility APIs."""
    if platform.system() != "Darwin":
        return True
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def open_accessibility_settings() -> None:
    """Open macOS System Settings directly to Accessibility panel."""
    if platform.system() == "Darwin":
        try:
            from ApplicationServices import AXIsProcessTrustedWithOptions
            from Foundation import NSDictionary
            options = NSDictionary.dictionaryWithObject_forKey_(True, "AXTrustedCheckOptionPrompt")
            AXIsProcessTrustedWithOptions(options)
        except Exception:
            pass
        subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])


def open_full_disk_access_settings() -> None:
    """Open macOS System Settings directly to Full Disk Access panel."""
    if platform.system() == "Darwin":
        subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"])


class OnboardingDialog(QDialog):
    """First-Run Setup & Permission Wizard."""
    setup_completed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("rat — Thiết lập lần đầu")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(540, 520)
        self._center_window()
        self._init_ui()

    def _center_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.move((geom.width() - self.width()) // 2, (geom.height() - self.height()) // 2)

    def _init_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 10)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setGraphicsEffect(shadow)
        container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 22, 24, 20)
        container_layout.setSpacing(16)

        # 1. Header (Logo + Welcome + Close)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        logo_label = QLabel("⚡")
        logo_label.setFixedSize(48, 48)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            background-color: #312e81;
            color: #ffffff;
            font-size: 24px;
            border-radius: 12px;
        """)
        header_layout.addWidget(logo_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_label = QLabel("Chào mừng bạn đến với rat")
        title_label.setStyleSheet("color: #0f172a; font-size: 18px; font-weight: 700;")
        sub_label = QLabel("Tìm kiếm tệp ngữ nghĩa siêu tốc & bảo mật 100% trên máy Mac.")
        sub_label.setStyleSheet("color: #64748b; font-size: 12px;")
        title_col.addWidget(title_label)
        title_col.addWidget(sub_label)

        header_layout.addLayout(title_col, 1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setToolTip("Bỏ qua thiết lập")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 13px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #475569;
            }
        """)
        btn_close.clicked.connect(self.reject)
        header_layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignTop)

        container_layout.addLayout(header_layout)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("border-top: 1px solid #f1f5f9;")
        container_layout.addWidget(div1)

        # 2. Permissions Section
        perm_label = QLabel("1. Cấp quyền hệ thống bắt buộc:")
        perm_label.setStyleSheet("color: #334155; font-size: 13px; font-weight: 600;")
        container_layout.addWidget(perm_label)

        # Card: Accessibility
        acc_card = QFrame()
        acc_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 10px;")
        acc_layout = QHBoxLayout(acc_card)
        acc_layout.setContentsMargins(8, 6, 8, 6)
        
        acc_text_col = QVBoxLayout()
        acc_text_col.setSpacing(2)
        acc_title = QLabel("Quyền Trợ năng (Accessibility)")
        acc_title.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 600;")
        acc_desc = QLabel(f"Để lắng nghe phím tắt toàn cầu ({config.get_hotkey_display()}) từ mọi app.")
        acc_desc.setStyleSheet("color: #64748b; font-size: 10.5px;")
        acc_text_col.addWidget(acc_title)
        acc_text_col.addWidget(acc_desc)
        acc_layout.addLayout(acc_text_col, 1)

        self.btn_acc = QPushButton("Mở Cài đặt")
        self.btn_acc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_acc.setStyleSheet("""
            QPushButton {
                background-color: #e0e7ff;
                color: #3730a3;
                border: 1px solid #c7d2fe;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #c7d2fe; }
        """)
        self.btn_acc.clicked.connect(open_accessibility_settings)
        acc_layout.addWidget(self.btn_acc)
        container_layout.addWidget(acc_card)

        # Card: Full Disk Access
        fda_card = QFrame()
        fda_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 10px;")
        fda_layout = QHBoxLayout(fda_card)
        fda_layout.setContentsMargins(8, 6, 8, 6)

        fda_text_col = QVBoxLayout()
        fda_text_col.setSpacing(2)
        fda_title = QLabel("Quyền Đọc Toàn Bộ Tệp (Full Disk Access)")
        fda_title.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 600;")
        fda_desc = QLabel("Cho phép quét nội dung văn bản, slide, bảng tính trong ổ đĩa.")
        fda_desc.setStyleSheet("color: #64748b; font-size: 10.5px;")
        fda_text_col.addWidget(fda_title)
        fda_text_col.addWidget(fda_desc)
        fda_layout.addLayout(fda_text_col, 1)

        btn_fda = QPushButton("Mở Cài đặt")
        btn_fda.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fda.setStyleSheet("""
            QPushButton {
                background-color: #e0e7ff;
                color: #3730a3;
                border: 1px solid #c7d2fe;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #c7d2fe; }
        """)
        btn_fda.clicked.connect(open_full_disk_access_settings)
        fda_layout.addWidget(btn_fda)
        container_layout.addWidget(fda_card)

        # 3. Watched Directories Section
        dirs_label = QLabel("2. Thư mục theo dõi tự động ban đầu:")
        dirs_label.setStyleSheet("color: #334155; font-size: 13px; font-weight: 600; margin-top: 4px;")
        container_layout.addWidget(dirs_label)

        self.dir_checkboxes: List[QCheckBox] = []
        dirs_layout = QVBoxLayout()
        dirs_layout.setSpacing(6)

        for d in DEFAULT_WATCH_DIRS:
            p = Path(d)
            if p.exists():
                cb = QCheckBox(f"📁 {p.name} ({p})")
                cb.setChecked(True)
                cb.setStyleSheet("color: #334155; font-size: 11.5px;")
                dirs_layout.addWidget(cb)
                self.dir_checkboxes.append(cb)

        container_layout.addLayout(dirs_layout)

        container_layout.addStretch()

        # 4. Action Button
        self.btn_finish = QPushButton(f"Hoàn tất & Bắt đầu sử dụng ({config.get_hotkey_display()}) 🚀")
        self.btn_finish.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finish.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #4338ca; }
        """)
        self.btn_finish.clicked.connect(self._on_finish)
        container_layout.addWidget(self.btn_finish)

        main_layout.addWidget(container)

        # Setup real-time permission status watcher
        self._check_timer = QTimer(self)
        self._check_timer.setInterval(1500)
        self._check_timer.timeout.connect(self._refresh_permission_status)
        self._check_timer.start()
        self._refresh_permission_status()

    def _refresh_permission_status(self) -> None:
        """Check live macOS Accessibility status and update button UI immediately."""
        if check_accessibility_status():
            self.btn_acc.setText("✓ Đã cấp quyền")
            self.btn_acc.setEnabled(False)
            self.btn_acc.setStyleSheet("""
                QPushButton {
                    background-color: #dcfce7;
                    color: #15803d;
                    border: 1px solid #bbf7d0;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """)

    def _on_finish(self) -> None:
        if hasattr(self, "_check_timer") and self._check_timer:
            self._check_timer.stop()

        # Save selected directories
        selected = []
        for cb in self.dir_checkboxes:
            if cb.isChecked():
                # Extract path inside parentheses
                txt = cb.text()
                if "(" in txt and ")" in txt:
                    path_str = txt.split("(")[1].split(")")[0].strip()
                    selected.append(path_str)

        if selected:
            config.indexed_directories = selected

        config.first_run_completed = True
        config.save()
        self.setup_completed.emit()
        self.accept()

    def reject(self) -> None:
        if hasattr(self, "_check_timer") and self._check_timer:
            self._check_timer.stop()
        super().reject()
