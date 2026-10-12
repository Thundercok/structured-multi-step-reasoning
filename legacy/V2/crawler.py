"""
Web Crawler — cleaned & upgraded version
"""

import sys
import os
import sqlite3
import logging
import json
import csv
import queue
import time
import threading
import hashlib
import requests
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox,
    QProgressBar, QFileDialog, QFrame, QSizePolicy,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QDateTime
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database helper  (thread-safe: one connection per thread via threading.local)
# ---------------------------------------------------------------------------
DB_FILE = "crawler_results.db"
_thread_local = threading.local()
_db_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating it if needed."""
    if not hasattr(_thread_local, "conn"):
        _thread_local.conn = sqlite3.connect(DB_FILE, check_same_thread=True)
        _thread_local.conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                url   TEXT UNIQUE,
                title TEXT,
                depth INTEGER,
                ts    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _thread_local.conn.commit()
    return _thread_local.conn


def db_upsert(url: str, title: str, depth: int) -> None:
    """Insert or replace a crawled URL record (thread-safe)."""
    with _db_lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO results (url, title, depth) VALUES (?, ?, ?)",
            (url, title, depth),
        )
        conn.commit()


def db_export_csv(path: str) -> int:
    """Export all results to a CSV file. Returns row count."""
    conn = _get_conn()
    rows = conn.execute("SELECT url, title, depth, ts FROM results ORDER BY id").fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "title", "depth", "timestamp"])
        writer.writerows(rows)
    return len(rows)


def db_export_json(path: str) -> int:
    """Export all results to a JSON file. Returns row count."""
    conn = _get_conn()
    rows = conn.execute("SELECT url, title, depth, ts FROM results ORDER BY id").fetchall()
    data = [{"url": r[0], "title": r[1], "depth": r[2], "timestamp": r[3]} for r in rows]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return len(data)


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Strip fragment and trailing slash for consistent deduplication."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(path=path).geturl()


def safe_filename(url: str, ext: str = "") -> str:
    """Create a collision-free filename from a URL using its MD5 digest."""
    digest = hashlib.md5(url.encode()).hexdigest()[:12]
    base = os.path.basename(urlparse(url).path) or "file"
    name, original_ext = os.path.splitext(base)
    return f"{name}_{digest}{ext or original_ext or '.bin'}"


# ---------------------------------------------------------------------------
# Robots.txt cache
# ---------------------------------------------------------------------------
_robots_cache: dict[str, RobotFileParser] = {}
_robots_lock = threading.Lock()


def can_fetch(url: str, respect_robots: bool, user_agent: str = "*") -> bool:
    if not respect_robots:
        return True
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    with _robots_lock:
        if robots_url not in _robots_cache:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                # If robots.txt is unreachable, allow crawling
                rp = None  # type: ignore[assignment]
            _robots_cache[robots_url] = rp
        rp = _robots_cache[robots_url]
    if rp is None:
        return True
    return rp.can_fetch(user_agent, url)


# ---------------------------------------------------------------------------
# Spider (worker thread)
# ---------------------------------------------------------------------------

class Spider(QThread):
    # Signals
    log         = pyqtSignal(str)         # log message
    progress    = pyqtSignal(int)         # 0-100
    stats       = pyqtSignal(int, int, int)  # crawled, errors, images
    done        = pyqtSignal()            # crawling finished

    def __init__(
        self,
        start_url: str,
        *,
        max_depth: int = 3,
        rate_delay: float = 1.5,
        stay_on_domain: bool = True,
        respect_robots: bool = True,
        extract_links: bool = True,
        extract_images: bool = True,
        extract_text: bool = True,
        extract_metadata: bool = True,
        save_html: bool = True,
        output_folder: str = "output",
    ) -> None:
        super().__init__()
        self.start_url      = normalize_url(start_url)
        self.max_depth      = max_depth
        self.rate_delay     = rate_delay
        self.stay_on_domain = stay_on_domain
        self.respect_robots = respect_robots
        self.extract_links  = extract_links
        self.extract_images = extract_images
        self.extract_text   = extract_text
        self.extract_metadata = extract_metadata
        self.save_html      = save_html
        self.output_folder  = output_folder

        self._start_domain  = urlparse(self.start_url).netloc
        self._visited: set[str] = set()
        self._queue: queue.Queue[tuple[str, int]] = queue.Queue()
        self._queue.put((self.start_url, 0))
        self._stop_flag = False

        # Stats counters
        self._crawled = 0
        self._errors  = 0
        self._images  = 0

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop_flag = True

    # ------------------------------------------------------------------
    def run(self) -> None:
        os.makedirs(self.output_folder, exist_ok=True)
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
        try:
            self._crawl(driver)
        finally:
            driver.quit()
            self.done.emit()

    # ------------------------------------------------------------------
    def _crawl(self, driver) -> None:
        while not self._queue.empty() and not self._stop_flag:
            url, depth = self._queue.get()
            url = normalize_url(url)

            if depth > self.max_depth or url in self._visited:
                continue

            # Domain guard
            if self.stay_on_domain and urlparse(url).netloc != self._start_domain:
                continue

            # Robots.txt guard
            if not can_fetch(url, self.respect_robots):
                self.log.emit(f"🚫 Blocked by robots.txt: {url}")
                continue

            self._visited.add(url)

            try:
                driver.get(url)
                time.sleep(self.rate_delay)

                title = (driver.title or "Untitled Page").strip()

                # Build output folder: <output>/<domain>/<md5_of_url>/
                domain_slug = urlparse(url).netloc.replace(".", "_")
                url_hash    = hashlib.md5(url.encode()).hexdigest()[:10]
                url_folder  = os.path.join(self.output_folder, domain_slug, url_hash)
                os.makedirs(url_folder, exist_ok=True)

                # Save URL reference
                self._save_text(url_folder, "url.txt", url)
                self._save_text(url_folder, "title.txt", title)

                # Links
                links: list[str] = []
                if self.extract_links:
                    links = self._get_links(driver, url)
                    self._save_text(url_folder, "links.txt", "\n".join(links))

                # Images
                if self.extract_images:
                    image_urls = self._get_images(driver)
                    downloaded = self._download_images(image_urls, url_folder)
                    self._images += len(downloaded)
                    self._save_text(url_folder, "images.txt", "\n".join(downloaded))

                # Body text
                if self.extract_text:
                    text = driver.find_element(By.TAG_NAME, "body").text.strip()
                    self._save_text(url_folder, "text.txt", text)

                # Metadata
                if self.extract_metadata:
                    meta = self._get_metadata(driver)
                    self._save_json(url_folder, "metadata.json", meta)

                # Raw HTML
                if self.save_html:
                    self._save_text(url_folder, "source.html", driver.page_source)

                # Persist to DB
                db_upsert(url, title, depth)

                self._crawled += 1
                self.log.emit(f"✅ [{depth}/{self.max_depth}] {url}  →  {title}")
                self.stats.emit(self._crawled, self._errors, self._images)

                # Estimate progress (rough: queue fill level)
                total_seen = self._crawled + self._queue.qsize()
                pct = min(99, int(self._crawled / max(total_seen, 1) * 100))
                self.progress.emit(pct)

                # Enqueue discovered links
                for link in links:
                    if link not in self._visited:
                        self._queue.put((link, depth + 1))

            except Exception as exc:
                self._errors += 1
                logger.exception("Error processing %s", url)
                self.log.emit(f"❌ Error ({url}): {exc}")
                self.stats.emit(self._crawled, self._errors, self._images)

        self.progress.emit(100)

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _get_links(self, driver, base_url: str) -> list[str]:
        raw = [
            a.get_attribute("href")
            for a in driver.find_elements(By.TAG_NAME, "a")
            if a.get_attribute("href")
        ]
        absolute = [normalize_url(urljoin(base_url, href)) for href in raw]
        return sorted(set(absolute))

    def _get_images(self, driver) -> list[str]:
        return list({
            img.get_attribute("src")
            for img in driver.find_elements(By.TAG_NAME, "img")
            if img.get_attribute("src")
        })

    def _get_metadata(self, driver) -> dict:
        return {
            m.get_attribute("name"): m.get_attribute("content")
            for m in driver.find_elements(By.TAG_NAME, "meta")
            if m.get_attribute("name")
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _save_text(folder: str, filename: str, data: str) -> None:
        if data:
            with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
                f.write(data)

    @staticmethod
    def _save_json(folder: str, filename: str, data: dict) -> None:
        if data:
            with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def _download_images(self, image_urls: list[str], folder: str) -> list[str]:
        img_folder = os.path.join(folder, "images")
        os.makedirs(img_folder, exist_ok=True)
        downloaded: list[str] = []
        for img_url in image_urls:
            try:
                resp = requests.get(img_url, timeout=8)
                resp.raise_for_status()
                # Collision-safe filename
                filename = safe_filename(img_url)
                img_path = os.path.join(img_folder, filename)
                with open(img_path, "wb") as f:
                    f.write(resp.content)
                downloaded.append(filename)
            except Exception as exc:
                logger.warning("Image download failed (%s): %s", img_url, exc)
                self._errors += 1
        return downloaded


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

QSS = """
/* ── Base ─────────────────────────────────────────────────────────── */
QWidget {
    background: #1a1b1e;
    color: #c9ccd4;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

/* ── Window title bar strip ────────────────────────────────────────── */
QWidget#titlebar {
    background: #141517;
    border-bottom: 1px solid #2a2b30;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
QWidget#sidebar {
    background: #141517;
    border-right: 1px solid #2a2b30;
}

/* ── Section header labels inside sidebar ──────────────────────────── */
QLabel#section-heading {
    color: #555b6b;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}

/* ── URL input ──────────────────────────────────────────────────────── */
QLineEdit {
    background: #111214;
    border: 1px solid #2a2b30;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e2e8;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    selection-background-color: #3b82f6;
}
QLineEdit:focus {
    border-color: #3b82f6;
}
QLineEdit::placeholder {
    color: #40444f;
}

/* ── Checkboxes ─────────────────────────────────────────────────────── */
QCheckBox {
    spacing: 7px;
    color: #9aa0b0;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #3a3d47;
    background: #111214;
}
QCheckBox::indicator:checked {
    background: #3b82f6;
    border-color: #3b82f6;
    image: url(none);
}
QCheckBox::indicator:hover {
    border-color: #3b82f6;
}

/* ── Spin boxes ─────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {
    background: #111214;
    border: 1px solid #2a2b30;
    border-radius: 6px;
    padding: 4px 8px;
    color: #e0e2e8;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #3b82f6;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 16px;
    background: #1e2027;
    border: none;
}

/* ── Progress bar ───────────────────────────────────────────────────── */
QProgressBar {
    background: #111214;
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: #3b82f6;
    border-radius: 2px;
}

/* ── Log output ─────────────────────────────────────────────────────── */
QTextEdit {
    background: #0f1012;
    border: none;
    color: #9aa0b0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 10px 14px;
    selection-background-color: #2a3a5a;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
QPushButton {
    background: transparent;
    border: 1px solid #2a2b30;
    border-radius: 6px;
    padding: 6px 14px;
    color: #9aa0b0;
    font-size: 13px;
}
QPushButton:hover {
    background: #22252e;
    border-color: #3a3d47;
    color: #c9ccd4;
}
QPushButton:pressed {
    background: #1a1d25;
}
QPushButton:disabled {
    color: #3a3d47;
    border-color: #22252e;
}

QPushButton#btn-start {
    background: #1d4ed8;
    border-color: #1d4ed8;
    color: #ffffff;
    font-weight: 600;
    padding: 7px 20px;
}
QPushButton#btn-start:hover {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#btn-start:disabled {
    background: #1e2a42;
    border-color: #1e2a42;
    color: #4a5a7a;
}

QPushButton#btn-stop {
    background: #450a0a;
    border-color: #7f1d1d;
    color: #fca5a5;
}
QPushButton#btn-stop:hover {
    background: #5a0e0e;
    border-color: #991b1b;
    color: #fecaca;
}
QPushButton#btn-stop:disabled {
    background: #1a1214;
    border-color: #2a1a1a;
    color: #4a2a2a;
}

/* ── Dividers ───────────────────────────────────────────────────────── */
QFrame[frameShape="4"],   /* HLine */
QFrame[frameShape="5"] {  /* VLine */
    color: #2a2b30;
    border: none;
    background: #2a2b30;
    max-height: 1px;
    max-width: 1px;
}

/* ── Stat value labels ──────────────────────────────────────────────── */
QLabel#stat-value {
    font-size: 22px;
    font-weight: 600;
    color: #e0e2e8;
}
QLabel#stat-value-green  { font-size: 22px; font-weight: 600; color: #4ade80; }
QLabel#stat-value-red    { font-size: 22px; font-weight: 600; color: #f87171; }
QLabel#stat-label        { font-size: 10px; color: #555b6b; letter-spacing: 0.5px; }
QLabel#stat-domain       { font-size: 12px; color: #9aa0b0; font-family: "Consolas", monospace; }

/* ── Status badge ───────────────────────────────────────────────────── */
QLabel#badge-idle    { background: #1e2027; border: 1px solid #2a2b30; border-radius: 10px;
                        color: #555b6b; font-size: 11px; padding: 2px 10px; }
QLabel#badge-running { background: #052e16; border: 1px solid #166534; border-radius: 10px;
                        color: #4ade80; font-size: 11px; padding: 2px 10px; }
QLabel#badge-stopping{ background: #2d1a06; border: 1px solid #92400e; border-radius: 10px;
                        color: #fbbf24; font-size: 11px; padding: 2px 10px; }

/* ── Scrollbars ─────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #111214;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #2a2b30;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 0; }
"""

# ---------------------------------------------------------------------------
# Log colours  (used to paint rich text in the log pane)
# ---------------------------------------------------------------------------

LOG_COLORS = {
    "ok":   "#4ade80",   # green  — success
    "err":  "#f87171",   # red    — error
    "warn": "#fbbf24",   # amber  — warning / blocked
    "info": "#60a5fa",   # blue   — informational
    "ts":   "#3a3d47",   # dim    — timestamp
    "dim":  "#555b6b",   # muted  — secondary
}


def _classify(text: str) -> str:
    """Return a colour key based on the message prefix."""
    if text.startswith("✅") or text.startswith("✔") or text.startswith("▶"):
        return "ok"
    if text.startswith("❌") or "Error" in text:
        return "err"
    if text.startswith("🚫") or text.startswith("🛑") or text.startswith("⚠"):
        return "warn"
    return "info"


# ---------------------------------------------------------------------------
# Sidebar helpers
# ---------------------------------------------------------------------------

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section-heading")
    lbl.setContentsMargins(0, 0, 0, 2)
    return lbl


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    return f


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class CrawlerApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._output_folder = "output"
        self._worker: Spider | None = None
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle("Web Crawler")
        self.setMinimumSize(960, 700)

        # Root: title bar on top, body below
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_titlebar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_main(), 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        root.addWidget(body_widget, 1)

    # ── Title bar ─────────────────────────────────────────────────────
    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titlebar")
        bar.setFixedHeight(40)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("Web Crawler")
        title.setStyleSheet("font-size:13px; font-weight:600; color:#c9ccd4;")
        layout.addWidget(title)
        layout.addStretch()

        self.badge = QLabel("Idle")
        self.badge.setObjectName("badge-idle")
        layout.addWidget(self.badge)

        return bar

    # ── Sidebar ────────────────────────────────────────────────────────
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Extract group
        layout.addWidget(_section_label("Extract"))
        self.cb_links    = QCheckBox("Links",    checked=True)
        self.cb_images   = QCheckBox("Images",   checked=True)
        self.cb_text     = QCheckBox("Text",     checked=True)
        self.cb_metadata = QCheckBox("Metadata", checked=True)
        self.cb_html     = QCheckBox("Raw HTML", checked=False)
        for cb in [self.cb_links, self.cb_images, self.cb_text,
                   self.cb_metadata, self.cb_html]:
            layout.addWidget(cb)

        layout.addWidget(_hline())

        # Behaviour group
        layout.addWidget(_section_label("Behaviour"))
        self.cb_same_domain = QCheckBox("Stay on domain",     checked=True)
        self.cb_robots      = QCheckBox("Respect robots.txt", checked=True)
        layout.addWidget(self.cb_same_domain)
        layout.addWidget(self.cb_robots)

        layout.addWidget(_hline())

        # Numeric limits
        layout.addWidget(_section_label("Limits"))

        depth_row = QHBoxLayout()
        depth_lbl = QLabel("Max depth")
        depth_lbl.setStyleSheet("color:#555b6b; font-size:12px;")
        self.spin_depth = QSpinBox(minimum=1, maximum=20, value=3)
        self.spin_depth.setFixedWidth(64)
        depth_row.addWidget(depth_lbl, 1)
        depth_row.addWidget(self.spin_depth)
        layout.addLayout(depth_row)

        delay_row = QHBoxLayout()
        delay_lbl = QLabel("Delay (s)")
        delay_lbl.setStyleSheet("color:#555b6b; font-size:12px;")
        self.spin_delay = QDoubleSpinBox(minimum=0.5, maximum=30.0,
                                          value=1.5, singleStep=0.5,
                                          decimals=1)
        self.spin_delay.setFixedWidth(64)
        delay_row.addWidget(delay_lbl, 1)
        delay_row.addWidget(self.spin_delay)
        layout.addLayout(delay_row)

        layout.addWidget(_hline())

        # Output folder
        layout.addWidget(_section_label("Output folder"))
        self.folder_display = QLabel(self._output_folder)
        self.folder_display.setObjectName("stat-domain")
        self.folder_display.setWordWrap(True)
        layout.addWidget(self.folder_display)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._choose_folder)
        layout.addWidget(browse_btn)

        layout.addStretch()
        return sidebar

    # ── Main panel ─────────────────────────────────────────────────────
    def _build_main(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # URL bar
        layout.addWidget(self._build_url_bar())

        # Stats bar
        layout.addWidget(self._build_stats_bar())

        # Progress strip
        layout.addWidget(self._build_progress_strip())

        # Log
        self.log_output = QTextEdit(readOnly=True)
        layout.addWidget(self.log_output, 1)

        # Bottom toolbar
        layout.addWidget(self._build_toolbar())

        return panel

    # ── URL bar ────────────────────────────────────────────────────────
    def _build_url_bar(self) -> QWidget:
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
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btn-stop")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_crawl)
        layout.addWidget(self.btn_stop)

        return bar

    # ── Stats bar ──────────────────────────────────────────────────────
    def _build_stats_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("border-bottom:1px solid #2a2b30;")
        bar.setFixedHeight(70)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        def stat_cell(label: str, value_id: str, color_id: str = "stat-value") -> tuple:
            cell = QWidget()
            cell.setStyleSheet("border-right:1px solid #2a2b30;")
            vbox = QVBoxLayout(cell)
            vbox.setContentsMargins(18, 10, 18, 10)
            vbox.setSpacing(2)
            val = QLabel("0")
            val.setObjectName(color_id)
            lbl = QLabel(label.upper())
            lbl.setObjectName("stat-label")
            vbox.addWidget(val)
            vbox.addWidget(lbl)
            return cell, val

        cell_c, self.lbl_crawled = stat_cell("Pages crawled", "crawled", "stat-value-green")
        cell_i, self.lbl_images  = stat_cell("Images saved",  "images")
        cell_e, self.lbl_errors  = stat_cell("Errors",        "errors",  "stat-value-red")

        # Domain cell (no right border on last)
        cell_d = QWidget()
        vbox_d = QVBoxLayout(cell_d)
        vbox_d.setContentsMargins(18, 10, 18, 10)
        vbox_d.setSpacing(2)
        self.lbl_domain = QLabel("—")
        self.lbl_domain.setObjectName("stat-domain")
        lbl_d = QLabel("TARGET DOMAIN")
        lbl_d.setObjectName("stat-label")
        vbox_d.addWidget(self.lbl_domain)
        vbox_d.addWidget(lbl_d)

        for cell in [cell_c, cell_i, cell_e, cell_d]:
            layout.addWidget(cell, 1)

        return bar

    # ── Progress strip ──────────────────────────────────────────────────
    def _build_progress_strip(self) -> QWidget:
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
    def _build_toolbar(self) -> QWidget:
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
        btn_clear.clicked.connect(self._clear_log)
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

        domain = urlparse(url).netloc or url
        self.lbl_domain.setText(domain)
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
        )
        self._worker.log.connect(self._on_log)
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

    def _on_done(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_badge("idle")
        self.progress_bar.setValue(100)
        self.pct_label.setText("100%")
        self._log("Crawl complete.", kind="ok")

    # ──────────────────────────────────────────────────────────────────
    # Signal handlers
    # ──────────────────────────────────────────────────────────────────

    def _on_log(self, text: str) -> None:
        self._log(text, kind=_classify(text))

    def _on_progress(self, pct: int) -> None:
        self.progress_bar.setValue(pct)
        self.pct_label.setText(f"{pct}%")

    def _on_stats(self, crawled: int, errors: int, images: int) -> None:
        self.lbl_crawled.setText(str(crawled))
        self.lbl_errors.setText(str(errors))
        self.lbl_images.setText(str(images))

    # ──────────────────────────────────────────────────────────────────
    # Badge state
    # ──────────────────────────────────────────────────────────────────

    def _set_badge(self, state: str) -> None:
        texts  = {"idle": "Idle", "running": "Crawling", "stopping": "Stopping"}
        self.badge.setText(texts.get(state, state))
        self.badge.setObjectName(f"badge-{state}")
        # Force Qt to re-apply the stylesheet after objectName change
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    # ──────────────────────────────────────────────────────────────────
    # Log with colour
    # ──────────────────────────────────────────────────────────────────

    def _log(self, text: str, *, kind: str = "info") -> None:
        ts   = QDateTime.currentDateTime().toString("HH:mm:ss")
        col  = LOG_COLORS.get(kind, LOG_COLORS["info"])
        ts_c = LOG_COLORS["ts"]

        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Timestamp
        fmt_ts = QTextCharFormat()
        fmt_ts.setForeground(QColor(ts_c))
        cursor.insertText(ts + "  ", fmt_ts)

        # Message
        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(QColor(col))
        cursor.insertText(text + "\n", fmt_msg)

        # Auto-scroll
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def _clear_log(self) -> None:
        self.log_output.clear()

    # ──────────────────────────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "results.csv", "CSV Files (*.csv)"
        )
        if path:
            try:
                n = db_export_csv(path)
                self._log(f"Exported {n} rows → {path}", kind="ok")
            except Exception as exc:
                self._log(f"CSV export failed: {exc}", kind="err")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON", "results.json", "JSON Files (*.json)"
        )
        if path:
            try:
                n = db_export_json(path)
                self._log(f"Exported {n} records → {path}", kind="ok")
            except Exception as exc:
                self._log(f"JSON export failed: {exc}", kind="err")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = CrawlerApp()
    window.show()
    sys.exit(app.exec())
