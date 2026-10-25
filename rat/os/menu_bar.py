"""
rat.os.menu_bar — macOS Top Menu Bar (Status Item) Resident Controller.
Places a native status indicator on the macOS top bar for quick search, stats, and background control.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Callable, Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QGuiApplication
from rat.os.native_menu import NativeMenu, NativeStatusItem

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


class SystemTrayManager:
    """Manages the macOS Menu Bar Status Item."""

    def __init__(
        self,
        on_open_spotlight: Optional[Callable[[], None]] = None,
        on_open_finder: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_open_schedule: Optional[Callable[[], None]] = None,
        on_open_widget: Optional[Callable[[], None]] = None,
        on_open_natal: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_open_spotlight = on_open_spotlight
        self.on_open_finder = on_open_finder
        self.on_open_settings = on_open_settings
        self.on_open_schedule = on_open_schedule
        self.on_open_widget = on_open_widget
        self.on_open_natal = on_open_natal
        self.on_quit = on_quit
        self.tray_icon = NativeStatusItem()
        self.db = Database(config.db_path)
        self.rescan_worker: Optional[RescanWorker] = None
        self._init_tray()

    def _init_tray(self) -> None:
        self.tray_icon.setToolTip("RAT — Trợ lý sinh viên & công việc macOS")
        menu = NativeMenu()

        # Check Accessibility permission
        from rat.os.hotkey import is_accessibility_trusted, open_accessibility_settings
        action_perm = QAction("⚠️ Cấp quyền Phím tắt (Accessibility)...", menu)
        action_perm.triggered.connect(open_accessibility_settings)
        menu.addAction(action_perm)
        permission_separator = menu.addSeparator()
        def refresh_permission_action():
            missing = not is_accessibility_trusted()
            action_perm.setVisible(missing)
            permission_separator.setVisible(missing)
        menu.aboutToShow.connect(refresh_permission_action)
        refresh_permission_action()

        # Search & Desk Quick Actions
        action_spotlight = QAction(f"✨ Mở RAT Desk ({config.get_hotkey_display()})", menu)
        if self.on_open_spotlight:
            action_spotlight.triggered.connect(self.on_open_spotlight)
        menu.addAction(action_spotlight)

        action_finder = QAction("📁 Chọn tài liệu / Mở PDF Desk...", menu)
        if self.on_open_finder:
            action_finder.triggered.connect(self.on_open_finder)
        menu.addAction(action_finder)

        menu.addSeparator()

        # Optional Domain Verticals (Dynamic Tool Packs)
        action_natal = QAction("🔮 Gói mở rộng: Bàn xem Chiêm tinh & Tarot...", menu)
        if self.on_open_natal:
            action_natal.triggered.connect(self.on_open_natal)
        menu.addAction(action_natal)

        if self.on_open_schedule:
            action_schedule = QAction("🍵 Gói mở rộng: Ghép Lịch & Khung Giờ...", menu)
            action_schedule.triggered.connect(self.on_open_schedule)
            menu.addAction(action_schedule)

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
        if self.on_quit:
            action_quit.triggered.connect(self.on_quit)
        else:
            action_quit.triggered.connect(QGuiApplication.instance().quit)
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
            NativeStatusItem.MessageIcon.Information,
            2000
        )

    def _on_tray_activated(self, reason: NativeStatusItem.ActivationReason) -> None:
        if reason == NativeStatusItem.ActivationReason.Trigger:
            if self.on_open_spotlight:
                self.on_open_spotlight()

    def _trigger_rescan(self) -> None:
        logger.info("Asynchronous rescan triggered from Menu Bar tray.")
        self.action_rescan.setEnabled(False)
        self.tray_icon.showMessage(
            "rat — Bắt đầu quét",
            "Đang quét kho tệp tin trong nền (QoS Background)...",
            NativeStatusItem.MessageIcon.Information,
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
            NativeStatusItem.MessageIcon.Information,
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
                NativeStatusItem.MessageIcon.Information,
                2500,
            )
        except Exception as e:
            logger.error(f"Error freeing RAM: {e}")

    def request_shutdown(self) -> None:
        """Non-blocking cancellation request for background rescan worker."""
        if hasattr(self, "rescan_worker") and self.rescan_worker is not None:
            try:
                if self.rescan_worker.isRunning():
                    self.rescan_worker.requestInterruption()
                    self.rescan_worker.quit()
            except Exception as e:
                logger.debug(f"Tray rescan worker request_shutdown note: {e}")

    def shutdown(self) -> bool:
        """Request cancellation without terminating a thread using the database."""
        if hasattr(self, "rescan_worker") and self.rescan_worker is not None:
            try:
                if self.rescan_worker.isRunning():
                    self.rescan_worker.requestInterruption()
                    self.rescan_worker.quit()
                    return False
                self.rescan_worker.deleteLater()
            except Exception as e:
                logger.debug(f"Tray rescan worker shutdown note: {e}")
                return False
            self.rescan_worker = None
        self.tray_icon.hide()
        return True

