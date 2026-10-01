"""
rat.os.menu_bar — macOS Top Menu Bar (Status Item) Resident Controller.
Places a native status indicator on the macOS top bar for quick search, stats, and background control.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from rat.config import config
from rat.crawler.db import Database
from rat.crawler.indexer import Indexer
from rat.os.daemon import is_launch_agent_installed, set_launch_at_login

logger = logging.getLogger("rat.os.menu_bar")


class RescanWorker(QThread):
    """Background thread worker for manual database rescan."""
    finished_rescan = pyqtSignal(int, int)

    def __init__(self, db: Database) -> None:
        super().__init__(None)  # Explicitly unparented for zero-crash destruction
        self.db = db

    def run(self) -> None:
        indexer = Indexer(self.db)
        indexed, total = indexer.run_full_index()
        if not self.isInterruptionRequested():
            self.finished_rescan.emit(indexed, total)


def create_tray_pixmap() -> QPixmap:
    """Draw a clean, native macOS monochrome menu bar icon."""
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw magnifying glass / rat silhouette icon
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#000000"))

    # Lens circle
    painter.drawEllipse(3, 3, 11, 11)
    # Clear inner
    painter.setBrush(QColor(Qt.GlobalColor.transparent))
    # Handle
    painter.setPen(QColor("#000000"))
    painter.drawLine(12, 12, 18, 18)
    painter.end()

    return pixmap


class SystemTrayManager:
    """Manages the macOS Menu Bar Status Item."""

    def __init__(
        self,
        on_open_spotlight: Optional[Callable[[], None]] = None,
        on_open_finder: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_open_schedule: Optional[Callable[[], None]] = None,
        on_open_widget: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_open_spotlight = on_open_spotlight
        self.on_open_finder = on_open_finder
        self.on_open_settings = on_open_settings
        self.on_open_schedule = on_open_schedule
        self.on_open_widget = on_open_widget
        self.tray_icon = QSystemTrayIcon()
        self.db = Database(config.db_path)
        self.rescan_worker: Optional[RescanWorker] = None
        self._init_tray()

    def _init_tray(self) -> None:
        # Create macOS template icon (automatically inverts in dark mode)
        icon = QIcon(create_tray_pixmap())
        icon.setIsMask(True)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("rat — Trợ lý sinh viên & công việc macOS")

        # Create Menu with warm paper styling
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #fffdf9;
                color: #2c241c;
                border: 1px solid #d9d0c5;
                border-radius: 10px;
                padding: 5px;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #f7eedb;
                color: #4c3a21;
            }
            QMenu::separator {
                height: 1px;
                background-color: #ebe4db;
                margin: 4px 8px;
            }
        """)

        # Check Accessibility permission
        from rat.os.hotkey import is_accessibility_trusted, open_accessibility_settings
        if not is_accessibility_trusted():
            action_perm = QAction("⚠️ Cấp quyền Phím tắt (Accessibility)...", menu)
            action_perm.triggered.connect(open_accessibility_settings)
            menu.addAction(action_perm)
            menu.addSeparator()

        # Search Quick Actions
        action_spotlight = QAction(f"🔍 Tìm kiếm nhanh ({config.get_hotkey_display()})", menu)
        if self.on_open_spotlight:
            action_spotlight.triggered.connect(self.on_open_spotlight)
        menu.addAction(action_spotlight)

        action_finder = QAction("📁 Mở AI Finder đầy đủ", menu)
        if self.on_open_finder:
            action_finder.triggered.connect(self.on_open_finder)
        menu.addAction(action_finder)

        # Club Timetable Compositor Action
        action_schedule = QAction("🍵 Ghép Lịch CLB & Khung Giờ Vàng...", menu)
        if self.on_open_schedule:
            action_schedule.triggered.connect(self.on_open_schedule)
        menu.addAction(action_schedule)

        # Floating Widget Action
        action_widget = QAction("⚡ Widget Thời Khóa Biểu (Claude Floating)", menu)
        if self.on_open_widget:
            action_widget.triggered.connect(self.on_open_widget)
        menu.addAction(action_widget)

        menu.addSeparator()

        # Stats info item (disabled)
        stats = self.db.get_stats()
        size_mb = stats["total_size_bytes"] / (1024 * 1024)
        action_stats = QAction(f"📊 Đã lập chỉ mục: {stats['total_files']} tệp (~{size_mb:.1f} MB)", menu)
        action_stats.setEnabled(False)
        menu.addAction(action_stats)

        # Rescan action
        self.action_rescan = QAction("🔄 Quét lại kho dữ liệu ngay", menu)
        self.action_rescan.triggered.connect(self._trigger_rescan)
        menu.addAction(self.action_rescan)

        # Free RAM Action
        self.action_free_ram = QAction("🧹 Giải phóng RAM (Evict ML Model)", menu)
        self.action_free_ram.triggered.connect(self._trigger_free_ram)
        menu.addAction(self.action_free_ram)

        menu.addSeparator()

        # Settings
        if self.on_open_settings:
            action_settings = QAction("⚙️ Cài đặt...", menu)
            action_settings.triggered.connect(self.on_open_settings)
            menu.addAction(action_settings)

        # Launch at Login Checkbox
        action_autostart = QAction("🚀 Tự khởi động cùng macOS", menu)
        action_autostart.setCheckable(True)
        action_autostart.setChecked(is_launch_agent_installed() or config.launch_at_login)
        action_autostart.toggled.connect(self._toggle_launch_at_login)
        menu.addAction(action_autostart)

        menu.addSeparator()

        # Quit
        action_quit = QAction("❌ Thoát RAT", menu)
        action_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(action_quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        logger.info("macOS System Tray resident item loaded.")

    def _toggle_launch_at_login(self, checked: bool) -> None:
        set_launch_at_login(checked)
        status_str = "bật" if checked else "tắt"
        self.tray_icon.showMessage(
            "rat — Khởi động cùng macOS",
            f"Đã {status_str} tự động chạy ngầm khi đăng nhập hệ thống!",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.on_open_spotlight:
                self.on_open_spotlight()

    def _trigger_rescan(self) -> None:
        logger.info("Asynchronous rescan triggered from Menu Bar tray.")
        self.action_rescan.setEnabled(False)
        self.tray_icon.showMessage(
            "rat — Bắt đầu quét",
            "Đang quét kho tệp tin trong nền (QoS Background)...",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
        self.rescan_worker = RescanWorker(self.db)
        self.rescan_worker.finished_rescan.connect(self._on_rescan_finished)
        self.rescan_worker.start()

    def _on_rescan_finished(self, indexed: int, total: int) -> None:
        self.action_rescan.setEnabled(True)
        self.tray_icon.showMessage(
            "rat — Quét hoàn tất",
            f"Đã cập nhật chỉ mục {indexed}/{total} tệp tin an toàn!",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

    def _trigger_free_ram(self) -> None:
        try:
            from rat.engine.embedder import embedder
            was_loaded = embedder.is_loaded
            embedder.evict()
            msg = "Đã giải phóng ~300MB RAM thành công!" if was_loaded else "Bộ nhớ RAM mô hình đã ở trạng thái trống (Idle)."
            self.tray_icon.showMessage(
                "rat — Quản trị Bộ nhớ RAM",
                msg,
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        except Exception as e:
            logger.error(f"Error freeing RAM: {e}")

    def shutdown(self) -> None:
        """Safely terminate any active background rescan worker."""
        if hasattr(self, "rescan_worker") and self.rescan_worker is not None:
            try:
                if self.rescan_worker.isRunning():
                    self.rescan_worker.requestInterruption()
                    self.rescan_worker.quit()
                    if not self.rescan_worker.wait(1500):
                        self.rescan_worker.terminate()
                        self.rescan_worker.wait(500)
                self.rescan_worker.deleteLater()
            except Exception as e:
                logger.debug(f"Tray rescan worker shutdown note: {e}")
            finally:
                self.rescan_worker = None

