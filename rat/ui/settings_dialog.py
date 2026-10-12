"""
rat.ui.settings_dialog — Settings dialog for folder management, indexing, and LLM keys.
"""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rat.config import config
from rat.crawler.db import Database
from rat.crawler.indexer import Indexer


class IndexWorker(QThread):
    """Background worker for indexing files."""
    progress = pyqtSignal(int, int, str)
    finished_indexing = pyqtSignal(int, int)

    def __init__(self, indexer: Indexer) -> None:
        super().__init__(None)  # Explicitly unparented for zero-crash destruction
        self.indexer = indexer

    def run(self) -> None:
        def on_prog(done: int, total: int, filename: str) -> None:
            if not self.isInterruptionRequested():
                self.progress.emit(done, total, filename)

        indexed, total = self.indexer.run_full_index(progress_callback=on_prog)
        if not self.isInterruptionRequested():
            self.finished_indexing.emit(indexed, total)


class SettingsDialog(QDialog):
    """Settings modal for rat."""

    def __init__(self, parent: Optional[QWidget] = None, on_settings_changed=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt 'rat' — Trợ lý Tìm kiếm Tệp tin")
        self.setFixedSize(560, 660)
        self.on_settings_changed = on_settings_changed
        self.indexer = Indexer()
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #f4f4f5;
            }
            QGroupBox {
                color: #f4f4f5;
                font-weight: bold;
                border: 1px solid #27272a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QListWidget {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                color: #f4f4f5;
                padding: 4px;
            }
            QLineEdit {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                color: #f4f4f5;
                padding: 6px 10px;
            }
            QPushButton {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
            QPushButton#SaveBtn {
                background-color: #2563eb;
                border: 1px solid #3b82f6;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 1. Folder Management Group
        folder_group = QGroupBox("📁 Thư mục theo dõi & quét tệp")
        folder_layout = QVBoxLayout(folder_group)

        self.folder_list = QListWidget()
        for d in config.indexed_directories:
            self.folder_list.addItem(d)
        folder_layout.addWidget(self.folder_list)

        btn_row = QHBoxLayout()
        self.btn_add_folder = QPushButton("➕ Thêm thư mục...")
        self.btn_add_folder.clicked.connect(self._add_folder)

        self.btn_remove_folder = QPushButton("➖ Xóa thư mục chọn")
        self.btn_remove_folder.clicked.connect(self._remove_folder)

        btn_row.addWidget(self.btn_add_folder)
        btn_row.addWidget(self.btn_remove_folder)
        folder_layout.addLayout(btn_row)

        layout.addWidget(folder_group)

        # 2. Index Status & Re-index Action
        index_group = QGroupBox("⚡ Trạng thái & Lập chỉ mục")
        index_layout = QVBoxLayout(index_group)

        self.stats_label = QLabel()
        self._update_stats_label()
        index_layout.addWidget(self.stats_label)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setTextVisible(True)
        self.prog_bar.hide()
        index_layout.addWidget(self.prog_bar)

        self.prog_status = QLabel("")
        self.prog_status.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.prog_status.hide()
        index_layout.addWidget(self.prog_status)

        self.btn_reindex = QPushButton("🔄 Quét & Lập chỉ mục lại ngay")
        self.btn_reindex.clicked.connect(self._start_reindex)
        index_layout.addWidget(self.btn_reindex)

        self.chk_autowatch = QCheckBox("Tự động theo dõi thay đổi tệp theo thời gian thực (Live Watch)")
        self.chk_autowatch.setChecked(config.auto_watch)
        index_layout.addWidget(self.chk_autowatch)

        layout.addWidget(index_group)

        # 3. System Integration & Auto-start Group
        sys_group = QGroupBox("🖥️ Tích hợp hệ điều hành & Khởi động")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setSpacing(6)

        from rat.os.daemon import is_launch_agent_installed
        self.chk_launch_at_login = QCheckBox("Tự khởi động cùng macOS khi đăng nhập (Launch at Login)")
        self.chk_launch_at_login.setChecked(is_launch_agent_installed() or config.launch_at_login)
        sys_layout.addWidget(self.chk_launch_at_login)

        hotkey_box = QVBoxLayout()
        hotkey_box.setSpacing(4)
        hotkey_lbl = QLabel("⌨️ Phím tắt toàn cầu gọi Spotlight (Global Hotkey):")
        hotkey_lbl.setStyleSheet("color: #e4e4e7; font-size: 12px; font-weight: 500;")
        hotkey_box.addWidget(hotkey_lbl)

        self.combo_hotkey = QComboBox()
        self.combo_hotkey.setStyleSheet("""
            QComboBox {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #18181b;
                color: #f4f4f5;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
        """)
        self.combo_hotkey.addItem("⌘ ⇧ Space (Command + Shift + Space) — Chuẩn RAT [Mặc định]", "<cmd>+<shift>+<space>")
        self.combo_hotkey.addItem("⌥ Space (Option + Space) — Chuẩn Raycast / Alfred", "<alt>+<space>")
        self.combo_hotkey.addItem("⌥ R (Option + R) — Gợi nhớ RAT", "<alt>+r")
        self.combo_hotkey.addItem("⌥ ⇧ Space (Option + Shift + Space)", "<alt>+<shift>+<space>")

        curr_hotkey = config.global_hotkey.strip()
        found_idx = self.combo_hotkey.findData(curr_hotkey)
        if found_idx >= 0:
            self.combo_hotkey.setCurrentIndex(found_idx)
        else:
            self.combo_hotkey.addItem(f"Tùy chỉnh ({config.get_hotkey_display()})", curr_hotkey)
            self.combo_hotkey.setCurrentIndex(self.combo_hotkey.count() - 1)

        hotkey_box.addWidget(self.combo_hotkey)
        sys_layout.addLayout(hotkey_box)

        layout.addWidget(sys_group)

        # 4. Local SLM Group (On-Device)
        slm_group = QGroupBox("🧠 Mô hình ngôn ngữ nhỏ SLM (Cục bộ on-device)")
        slm_layout = QVBoxLayout(slm_group)
        slm_layout.setSpacing(8)

        from rat.engine.slm import slm_engine
        is_installed = slm_engine.is_model_installed(config.ollama_model)
        status_text = "🟢 Sẵn sàng hoạt động (Apple Silicon Metal)" if is_installed else "🟡 Chưa tải model"

        self.slm_status_label = QLabel(f"Trạng thái Model ({config.ollama_model}): {status_text}")
        self.slm_status_label.setStyleSheet("color: #34d399; font-size: 12px; font-weight: 500;")
        slm_layout.addWidget(self.slm_status_label)

        self.chk_slm = QCheckBox("Kích hoạt SLM Context Engineering & Hỏi đáp tức thì")
        self.chk_slm.setChecked(config.use_slm)
        slm_layout.addWidget(self.chk_slm)

        layout.addWidget(slm_group)

        # 5. LLM API Keys Group (Optional Cloud)
        llm_group = QGroupBox("☁️ Cloud AI / LLM (Tùy chọn)")
        llm_layout = QFormLayout(llm_group)
        llm_layout.setSpacing(8)

        self.input_gemini = QLineEdit()
        self.input_gemini.setPlaceholderText("AIzaSy...")
        self.input_gemini.setText(config.gemini_api_key)
        self.input_gemini.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        llm_layout.addRow("Google Gemini Key:", self.input_gemini)

        self.input_openai = QLineEdit()
        self.input_openai.setPlaceholderText("sk-proj-...")
        self.input_openai.setText(config.openai_api_key)
        self.input_openai.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        llm_layout.addRow("OpenAI Key:", self.input_openai)

        note_label = QLabel("ℹ️ 'rat' ưu tiên chạy hoàn toàn Offline bằng SLM cục bộ.")
        note_label.setStyleSheet("color: #71717a; font-size: 11px;")
        llm_layout.addRow(note_label)

        layout.addWidget(llm_group)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_save = QPushButton("Lưu cấu hình")
        self.btn_save.setObjectName("SaveBtn")
        self.btn_save.clicked.connect(self._save_settings)

        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.close)

        bottom_layout.addWidget(self.btn_save)
        bottom_layout.addWidget(self.btn_close)
        layout.addLayout(bottom_layout)

    def _update_stats_label(self) -> None:
        db = Database(config.db_path)
        stats = db.get_stats()
        size_mb = stats["total_size_bytes"] / (1024 * 1024)
        self.stats_label.setText(
            f"Tổng số file đã lưu chỉ mục: {stats['total_files']} tệp (~{size_mb:.1f} MB)"
        )

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục cần quét")
        if folder and folder not in [self.folder_list.item(i).text() for i in range(self.folder_list.count())]:
            self.folder_list.addItem(folder)

    def _remove_folder(self) -> None:
        row = self.folder_list.currentRow()
        if row >= 0:
            self.folder_list.takeItem(row)

    def _start_reindex(self) -> None:
        self.btn_reindex.setEnabled(False)
        self.prog_bar.show()
        self.prog_status.show()
        self.prog_bar.setValue(0)
        self.prog_status.setText("Đang bắt đầu quét các thư mục...")

        dirs = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        config.indexed_directories = dirs
        config.save()

        self.worker = IndexWorker(self.indexer)
        self.worker.progress.connect(self._on_index_progress)
        self.worker.finished_indexing.connect(self._on_index_finished)
        self.worker.start()

    def _on_index_progress(self, done: int, total: int, filename: str) -> None:
        if total > 0:
            pct = int((done / total) * 100)
            self.prog_bar.setValue(pct)
            self.prog_status.setText(f"Đang lập chỉ mục ({done}/{total}): {filename[:30]}...")

    def _on_index_finished(self, indexed: int, total: int) -> None:
        self.prog_bar.setValue(100)
        self.prog_status.setText(f"✓ Hoàn tất: Đã cập nhật {indexed}/{total} tệp tin!")
        self.btn_reindex.setEnabled(True)
        self._update_stats_label()

    def _save_settings(self) -> None:
        dirs = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        config.indexed_directories = dirs
        config.gemini_api_key = self.input_gemini.text().strip()
        config.openai_api_key = self.input_openai.text().strip()
        config.auto_watch = self.chk_autowatch.isChecked()
        config.use_slm = self.chk_slm.isChecked()

        # Update global hotkey if changed
        chosen_hotkey = self.combo_hotkey.currentData()
        if chosen_hotkey and chosen_hotkey != config.global_hotkey:
            config.global_hotkey = chosen_hotkey
            from rat.os.hotkey import restart_global_hotkey
            restart_global_hotkey()

        config.save()

        # Update Launch at Login status
        from rat.os.daemon import set_launch_at_login
        want_launch = self.chk_launch_at_login.isChecked()
        set_launch_at_login(want_launch)

        if self.on_settings_changed:
            self.on_settings_changed()
        self.accept()

    def _shutdown_worker(self) -> None:
        """Safely terminate IndexWorker thread if still active."""
        if hasattr(self, "worker") and self.worker is not None:
            try:
                if self.worker.isRunning():
                    self.worker.requestInterruption()
                    self.worker.quit()
                    if not self.worker.wait(1500):
                        self.worker.terminate()
                        self.worker.wait(500)
                self.worker.deleteLater()
            except Exception as e:
                logger.debug(f"Settings worker shutdown note: {e}")
            finally:
                self.worker = None

    def closeEvent(self, event) -> None:
        self._shutdown_worker()
        super().closeEvent(event)

    def reject(self) -> None:
        self._shutdown_worker()
        super().reject()
