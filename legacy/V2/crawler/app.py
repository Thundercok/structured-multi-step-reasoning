"""
app.py — Main application window (CrawlerApp).

Imports Spider, db helpers, and style constants from sibling modules.
Contains only UI construction and signal wiring — no crawl logic lives here.
"""

from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QWidget,
)

from . import db
from .spider import Spider
from .style import LOG_COLORS, classify


# ---------------------------------------------------------------------------
# Small layout helpers
# ---------------------------------------------------------------------------

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section-heading")
    lbl.setContentsMargins(0, 0, 0, 2)
    return lbl


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class CrawlerApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._output_folder = "output"
        self._worker: Spider | None = None
        self._build()

    # ──────────────────────────────────────────────────────────────────
    # Top-level layout
    # ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setWindowTitle("Spider — The Web Crawler")
        self.setMinimumSize(960, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._titlebar())

        body_widget = QWidget()
        body = QHBoxLayout(body_widget)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._sidebar())
        body.addWidget(self._main_panel(), 1)

        root.addWidget(body_widget, 1)

    # ──────────────────────────────────────────────────────────────────
    # Title bar
    # ──────────────────────────────────────────────────────────────────

    def _titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titlebar")
        bar.setFixedHeight(40)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("Spider — The Web Crawler")
        title.setStyleSheet("font-size:13px; font-weight:600; color:#c9ccd4;")
        layout.addWidget(title)
        layout.addStretch()

        self.badge = QLabel("Idle")
        self.badge.setObjectName("badge-idle")
        layout.addWidget(self.badge)

        return bar

    # ──────────────────────────────────────────────────────────────────
    # Sidebar (settings)
    # ──────────────────────────────────────────────────────────────────

    def _sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Extract
        layout.addWidget(_section_label("Extract"))
        self.cb_links    = QCheckBox("Links",    checked=True)
        self.cb_images   = QCheckBox("Images",   checked=True)
        self.cb_text     = QCheckBox("Text",     checked=True)
        self.cb_metadata = QCheckBox("Metadata", checked=True)
        self.cb_html     = QCheckBox("Raw HTML", checked=False)
        for cb in (self.cb_links, self.cb_images, self.cb_text,
                   self.cb_metadata, self.cb_html):
            layout.addWidget(cb)

        layout.addWidget(_hline())

        # Behaviour
        layout.addWidget(_section_label("Behaviour"))
        self.cb_same_domain = QCheckBox("Stay on domain",     checked=True)
        self.cb_robots      = QCheckBox("Respect robots.txt", checked=True)
        self.cb_stealth     = QCheckBox("Stealth mode",       checked=True)
        layout.addWidget(self.cb_same_domain)
        layout.addWidget(self.cb_robots)
        layout.addWidget(self.cb_stealth)

        layout.addWidget(_hline())

        # Limits
        layout.addWidget(_section_label("Limits"))

        for attr, label, cls, kw in [
            ("spin_depth",   "Max depth",  QSpinBox,       dict(minimum=1, maximum=20, value=3)),
            ("spin_delay",   "Delay (s)",  QDoubleSpinBox, dict(minimum=0.5, maximum=30.0,
                                                                  value=1.5, singleStep=0.5,
                                                                  decimals=1)),
            ("spin_retries", "Retries",    QSpinBox,       dict(minimum=0, maximum=10, value=2)),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#555b6b; font-size:12px;")
            spin = cls(**kw)
            spin.setFixedWidth(64)
            setattr(self, attr, spin)
            row.addWidget(lbl, 1)
            row.addWidget(spin)
            layout.addLayout(row)

        layout.addWidget(_hline())

        # Output folder
        layout.addWidget(_section_label("Output folder"))
        self.folder_display = QLabel(self._output_folder)
        self.folder_display.setObjectName("stat-domain")
        self.folder_display.setWordWrap(True)
        layout.addWidget(self.folder_display)

        browse = QPushButton("Browse…")
        browse.clicked.connect(self._choose_folder)
        layout.addWidget(browse)

        layout.addStretch()
        return sidebar

    # ──────────────────────────────────────────────────────────────────
    # Main panel (URL bar + stats + log)
    # ──────────────────────────────────────────────────────────────────

    def _main_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._url_bar())
        layout.addWidget(self._stats_bar())
        layout.addWidget(self._progress_strip())

        self.log_output = QTextEdit(readOnly=True)
        layout.addWidget(self.log_output, 1)

        layout.addWidget(self._toolbar())
        return panel

    # ── URL bar ────────────────────────────────────────────────────────

    def _url_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background:#111214; border-bottom:1px solid #2a2b30;")
        bar.setFixedHeight(52)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self.url_input = QLineEdit(placeholderText="https://")
        self.url_input.setText("https://books.toscrape.com")
        self.url_input.returnPressed.connect(self.start_crawl)
        layout.addWidget(self.url_input, 1)

        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("btn-start")
        self.btn_start.setFixedHeight(34)
        self.btn_start.clicked.connect(self.start_crawl)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btn-stop")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_crawl)

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)
        return bar

    # ── Stats bar ──────────────────────────────────────────────────────

    def _stats_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("border-bottom:1px solid #2a2b30;")
        bar.setFixedHeight(70)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        def cell(heading: str, obj_id: str) -> tuple[QWidget, QLabel]:
            w = QWidget()
            w.setStyleSheet("border-right:1px solid #2a2b30;")
            vbox = QVBoxLayout(w)
            vbox.setContentsMargins(18, 10, 18, 10)
            vbox.setSpacing(2)
            val = QLabel("0")
            val.setObjectName(obj_id)
            lbl = QLabel(heading.upper())
            lbl.setObjectName("stat-label")
            vbox.addWidget(val)
            vbox.addWidget(lbl)
            return w, val

        c1, self.lbl_crawled = cell("Pages crawled", "stat-value-green")
        c2, self.lbl_images  = cell("Images saved",  "stat-value")
        c3, self.lbl_errors  = cell("Errors",         "stat-value-red")

        # Domain cell (no right border)
        c4 = QWidget()
        vbox4 = QVBoxLayout(c4)
        vbox4.setContentsMargins(18, 10, 18, 10)
        vbox4.setSpacing(2)
        self.lbl_domain = QLabel("—")
        self.lbl_domain.setObjectName("stat-domain")
        vbox4.addWidget(self.lbl_domain)
        lbl4 = QLabel("TARGET DOMAIN")
        lbl4.setObjectName("stat-label")
        vbox4.addWidget(lbl4)

        for w in (c1, c2, c3, c4):
            layout.addWidget(w, 1)

        return bar

    # ── Progress strip ──────────────────────────────────────────────────

    def _progress_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedHeight(20)
        strip.setStyleSheet("background:#0f1012; border-bottom:1px solid #2a2b30;")

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar, 1)

        self.pct_label = QLabel("0%")
        self.pct_label.setStyleSheet("font-size:11px; color:#555b6b; min-width:28px;")
        layout.addWidget(self.pct_label)

        return strip

    # ── Bottom toolbar ──────────────────────────────────────────────────

    def _toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background:#111214; border-top:1px solid #2a2b30;")
        bar.setFixedHeight(42)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(6)

        btn_csv  = QPushButton("Export CSV")
        btn_json = QPushButton("Export JSON")
        btn_csv.clicked.connect(self._export_csv)
        btn_json.clicked.connect(self._export_json)
        layout.addWidget(btn_csv)
        layout.addWidget(btn_json)
        layout.addStretch()

        btn_clear = QPushButton("Clear log")
        btn_clear.clicked.connect(self.log_output.clear)
        layout.addWidget(btn_clear)

        return bar

    # ──────────────────────────────────────────────────────────────────
    # Folder selection
    # ──────────────────────────────────────────────────────────────────

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._output_folder = folder
            self.folder_display.setText(folder)
            self._log(f"Output folder → {folder}", kind="info")

    # ──────────────────────────────────────────────────────────────────
    # Crawl control
    # ──────────────────────────────────────────────────────────────────

    def start_crawl(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self._log("Please enter a URL.", kind="warn")
            return

        self.lbl_domain.setText(urlparse(url).netloc or url)
        self.lbl_crawled.setText("0")
        self.lbl_images.setText("0")
        self.lbl_errors.setText("0")

        self._worker = Spider(
            url,
            max_depth        = self.spin_depth.value(),
            rate_delay       = self.spin_delay.value(),
            stay_on_domain   = self.cb_same_domain.isChecked(),
            respect_robots   = self.cb_robots.isChecked(),
            extract_links    = self.cb_links.isChecked(),
            extract_images   = self.cb_images.isChecked(),
            extract_text     = self.cb_text.isChecked(),
            extract_metadata = self.cb_metadata.isChecked(),
            save_html        = self.cb_html.isChecked(),
            output_folder    = self._output_folder,
            stealth          = self.cb_stealth.isChecked(),
            max_retries      = self.spin_retries.value(),
        )
        self._worker.log.connect(lambda t: self._log(t, kind=classify(t)))
        self._worker.progress.connect(self._on_progress)
        self._worker.stats.connect(self._on_stats)
        self._worker.done.connect(self._on_done)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self._set_badge("running")
        self._log(f"Started crawling: {url}", kind="ok")
        self._worker.start()

    def stop_crawl(self) -> None:
        if self._worker:
            self._worker.stop()
            self._set_badge("stopping")
            self._log("Stop requested — finishing current page…", kind="warn")

    # ──────────────────────────────────────────────────────────────────
    # Signal handlers
    # ──────────────────────────────────────────────────────────────────

    def _on_progress(self, pct: int) -> None:
        self.progress_bar.setValue(pct)
        self.pct_label.setText(f"{pct}%")

    def _on_stats(self, crawled: int, errors: int, images: int) -> None:
        self.lbl_crawled.setText(str(crawled))
        self.lbl_errors.setText(str(errors))
        self.lbl_images.setText(str(images))

    def _on_done(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_badge("idle")
        self.progress_bar.setValue(100)
        self.pct_label.setText("100%")
        self._log("Crawl complete.", kind="ok")

    # ──────────────────────────────────────────────────────────────────
    # Badge
    # ──────────────────────────────────────────────────────────────────

    def _set_badge(self, state: str) -> None:
        labels = {"idle": "Idle", "running": "Crawling", "stopping": "Stopping"}
        self.badge.setText(labels.get(state, state))
        self.badge.setObjectName(f"badge-{state}")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    # ──────────────────────────────────────────────────────────────────
    # Coloured log output
    # ──────────────────────────────────────────────────────────────────

    def _log(self, text: str, *, kind: str = "info") -> None:
        ts  = QDateTime.currentDateTime().toString("HH:mm:ss")
        cur = self.log_output.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)

        fmt_ts = QTextCharFormat()
        fmt_ts.setForeground(QColor(LOG_COLORS["ts"]))
        cur.insertText(ts + "  ", fmt_ts)

        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(QColor(LOG_COLORS.get(kind, LOG_COLORS["info"])))
        cur.insertText(text + "\n", fmt_msg)

        self.log_output.setTextCursor(cur)
        self.log_output.ensureCursorVisible()

    # ──────────────────────────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "results.csv", "CSV Files (*.csv)"
        )
        if path:
            try:
                self._log(f"Exported {db.export_csv(path)} rows → {path}", kind="ok")
            except Exception as exc:
                self._log(f"CSV export failed: {exc}", kind="err")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON", "results.json", "JSON Files (*.json)"
        )
        if path:
            try:
                self._log(f"Exported {db.export_json(path)} records → {path}", kind="ok")
            except Exception as exc:
                self._log(f"JSON export failed: {exc}", kind="err")
