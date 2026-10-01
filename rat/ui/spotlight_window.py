"""
rat.ui.spotlight_window — 100% Genuine Apple macOS Light Theme Spotlight Window.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from rat.config import config
from rat.crawler.db import Database
from rat.engine.hybrid_search import SearchEngine
from rat.engine.reranker import SearchResultItem, sort_search_results
from rat.ui.feedback import SearchFeedback
from rat.ui.action_menu import ActionMenuDialog
from rat.ui.apple_item_delegate import AppleSpotlightDelegate
from rat.ui.preview_panel import (
    PreviewPanel,
    open_file_default,
    open_in_terminal,
    reveal_in_finder,
    trigger_quicklook,
)
from rat.ui.settings_dialog import SettingsDialog
from rat.ui.theme import RAYCAST_QSS

logger = logging.getLogger("rat.ui")

FILTER_CATEGORIES = [
    ("all", "Tất cả", []),
    ("docs", "Văn bản", [".docx", ".doc", ".pdf", ".txt", ".md"]),
    ("sheets", "Bảng tính", [".xlsx", ".xls", ".csv"]),
    ("slides", "Slide", [".pptx", ".ppt"]),
    ("code", "Code", [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"]),
    ("images", "Hình ảnh", [".png", ".jpg", ".jpeg", ".webp"]),
]


class SearchWorker(QObject):
    """Long-lived background search worker."""
    search_completed = pyqtSignal(int, dict)

    def __init__(self, engine: SearchEngine) -> None:
        super().__init__()
        self.engine = engine
        self._latest_id = 0
        self._lock = threading.Lock()
        try:
            self.engine.embedder.embed_query("warmup")
            self.engine.vector_cache.preload()
        except Exception as e:
            logger.warning(f"SearchWorker warmup error: {e}")

    @pyqtSlot(int, str, list)
    def do_search(self, request_id: int, query: str, extensions: list) -> None:
        with self._lock:
            if request_id < self._latest_id:
                return
            self._latest_id = request_id

        try:
            response = self.engine.search(
                query,
                limit=30,
                use_hyde=False,
                use_vector=True
            )
            with self._lock:
                if request_id < self._latest_id:
                    return

            if extensions:
                filtered = [r for r in response["results"] if r.file_ext.lower() in extensions]
                response["results"] = filtered

            self.search_completed.emit(request_id, response)
        except Exception as e:
            logger.error(f"SearchWorker error: {e}")
            self.search_completed.emit(
                request_id,
                {"query": query, "results": [], "latency_ms": 0, "parsed_context": {}}
            )



class SearchInputEventFilter(QObject):
    """Event filter on search_input to enable keyboard-first Raycast navigation."""

    def __init__(self, window: "SpotlightWindow") -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            modifiers = key_event.modifiers()

            # 1. Down / Up navigation in results list
            if key == Qt.Key.Key_Down:
                self.window.navigate_results(1)
                return True
            elif key == Qt.Key.Key_Up:
                self.window.navigate_results(-1)
                return True
            elif key == Qt.Key.Key_PageDown:
                self.window.navigate_results(5)
                return True
            elif key == Qt.Key.Key_PageUp:
                self.window.navigate_results(-5)
                return True

            # 2. Enter / Return actions
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    self.window._reveal_current_in_finder()
                elif modifiers & Qt.KeyboardModifier.AltModifier:
                    self.window._open_current_in_terminal()
                else:
                    self.window._open_current_file()
                return True

            # 3. Quick Look: Cmd + Y
            if key == Qt.Key.Key_Y and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._preview_quick_look()
                return True

            # 4. Copy Path / Content
            if key == Qt.Key.Key_C and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    self.window._copy_current_content()
                else:
                    self.window._copy_current_path()
                return True

            # 5. Action Menu: Cmd + K
            if key == Qt.Key.Key_K and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._open_action_menu()
                return True

            # 5b. Schedule Compositor: Cmd + T
            if key == Qt.Key.Key_T and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._open_schedule()
                return True

            # 5c. Claude Widget: Cmd + W
            if key == Qt.Key.Key_W and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._open_claude_widget()
                return True

            # 6. Filter Switching: Tab / Backtab or Cmd + 1..6
            if key == Qt.Key.Key_Tab:
                self.window.cycle_filter(1)
                return True
            elif key == Qt.Key.Key_Backtab:
                self.window.cycle_filter(-1)
                return True
            elif modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                if Qt.Key.Key_1 <= key <= Qt.Key.Key_6:
                    idx = key - Qt.Key.Key_1
                    self.window._select_filter(idx)
                    return True

            # 7. Escape: Clear text first, or hide window
            if key == Qt.Key.Key_Escape:
                if self.window.search_input.text():
                    self.window.search_input.clear()
                else:
                    self.window.hide()
                return True

        return super().eventFilter(watched, event)


class ResultListEventFilter(QObject):
    """Event filter on result_list for spacebar quick look and instant type-to-search."""

    def __init__(self, window: "SpotlightWindow") -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            modifiers = key_event.modifiers()

            # Space triggers macOS native Quick Look
            if key == Qt.Key.Key_Space:
                self.window._preview_quick_look()
                return True

            # Return / Enter
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                    self.window._reveal_current_in_finder()
                elif modifiers & Qt.KeyboardModifier.AltModifier:
                    self.window._open_current_in_terminal()
                else:
                    self.window._open_current_file()
                return True

            # Quick Look: Cmd + Y
            if key == Qt.Key.Key_Y and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._preview_quick_look()
                return True

            # Copy Path / Content
            if key == Qt.Key.Key_C and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    self.window._copy_current_content()
                else:
                    self.window._copy_current_path()
                return True

            # Action Menu: Cmd + K
            if key == Qt.Key.Key_K and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._open_action_menu()
                return True

            # Schedule Compositor: Cmd + T
            if key == Qt.Key.Key_T and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._open_schedule()
                return True

            # Claude Widget: Cmd + W
            if key == Qt.Key.Key_W and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
                self.window._open_claude_widget()
                return True

            # Escape hides window
            if key == Qt.Key.Key_Escape:
                self.window.hide()
                return True

            # Type-to-search: If user types printable characters while on list, forward to search_input
            text = key_event.text()
            if text and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.AltModifier)):
                self.window.search_input.setFocus()
                self.window.search_input.setText(self.window.search_input.text() + text)
                self.window.search_input.setCursorPosition(len(self.window.search_input.text()))
                return True

        return super().eventFilter(watched, event)


class SpotlightWindow(QMainWindow):
    """Pure Apple macOS Light Theme Spotlight Window with Native QPainter Item Delegate."""
    search_requested = pyqtSignal(int, str, list)

    def __init__(self) -> None:
        super().__init__()
        self.db = Database(config.db_path)
        self.engine = SearchEngine(self.db)
        self.active_filter_idx = 0
        self._request_counter = 0
        self._dialog_active = False
        self._is_opening = False
        self._was_activated = False
        self.current_query = ""

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._execute_search)

        self._drag_pos = QPoint()
        self._init_thread()
        self._init_window()
        self._init_ui()
        self.feedback = SearchFeedback(self, "spotlight", [self.result_list])
        self._load_initial_data()

    def _init_thread(self) -> None:
        # Crucial: Unparented QThread(None) prevents Qt C++ child destruction SIGABRT
        self.search_thread = QThread(None)
        self.worker = SearchWorker(self.engine)
        self.worker.moveToThread(self.search_thread)
        self.search_requested.connect(self.worker.do_search)
        self.worker.search_completed.connect(self._on_search_completed)
        self.search_thread.start()

    def _init_window(self) -> None:
        self.setWindowTitle("rat")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(950, 570)
        self.setStyleSheet(RAYCAST_QSS)

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2 - 30
            self.move(x, max(geo.y() + 30, y))

    def _init_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 55))
        shadow.setOffset(0, 8)

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)

        container = QFrame()
        container.setObjectName("SpotlightContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setGraphicsEffect(shadow)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 1. Search Header
        header = QFrame()
        header.setObjectName("SearchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 10)
        header_layout.setSpacing(8)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("🔍 Tìm tệp tin (VD: bài tập dsa thầy dũng, tiền cơm, đồ án tốt nghiệp...)")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.input_filter = SearchInputEventFilter(self)
        self.search_input.installEventFilter(self.input_filter)
        header_layout.addWidget(self.search_input)

        # Scope Bar (Filter Pills)
        self.filter_bar = QFrame()
        self.filter_bar.setObjectName("FilterPillsBar")
        filter_layout = QHBoxLayout(self.filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)

        self.filter_buttons: List[QPushButton] = []
        for idx, (cat_id, label, _) in enumerate(FILTER_CATEGORIES):
            btn = QPushButton(f"{label}")
            btn.setProperty("class", "FilterPill")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.clicked.connect(lambda checked, i=idx: self._select_filter(i))
            filter_layout.addWidget(btn)
            self.filter_buttons.append(btn)

        filter_layout.addStretch()

        self.btn_settings = QPushButton("⚙️ Cài đặt")
        self.btn_settings.setProperty("class", "FilterPill")
        self.btn_settings.clicked.connect(self._open_settings)
        filter_layout.addWidget(self.btn_settings)

        header_layout.addWidget(self.filter_bar)
        container_layout.addWidget(header)

        # 2. Main Dual Pane (50/50 Split)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #e5e5ea; width: 1px; }")

        # Left List (Rendered with Native Apple QPainter Delegate)
        self.result_list = QListWidget()
        self.result_list.setObjectName("ResultList")
        self.result_list.setFrameShape(QFrame.Shape.NoFrame)
        self.result_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_list.setItemDelegate(AppleSpotlightDelegate(self))
        self.result_list.currentRowChanged.connect(self._on_result_selected)
        self.result_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_filter = ResultListEventFilter(self)
        self.result_list.installEventFilter(self.list_filter)
        self.splitter.addWidget(self.result_list)

        # Right Quick Look Inspector
        self.preview_panel = PreviewPanel()
        self.splitter.addWidget(self.preview_panel)

        self.splitter.setSizes([475, 475])
        container_layout.addWidget(self.splitter, 1)

        # 3. Action Footer
        footer = QFrame()
        footer.setObjectName("ActionFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 8, 16, 8)
        footer_layout.setSpacing(12)

        self.footer_status = QLabel("⚡ Đang tải...")
        self.footer_status.setObjectName("FooterStatus")
        footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch()

        hotkeys = [
            ("↵", "Mở"),
            ("Space", "Xem nhanh"),
            ("⌘↵", "Finder"),
            ("⌥↵", "Terminal"),
            ("⌘C", "Copy"),
            ("⌘K", "Tác vụ"),
            ("Esc", "Đóng"),
        ]
        for key, desc in hotkeys:
            badge = QLabel(key)
            badge.setProperty("class", "HotkeyBadge")
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #636366; font-size: 11px; margin-right: 4px;")
            footer_layout.addWidget(badge)
            footer_layout.addWidget(desc_label)

        container_layout.addWidget(footer)
        main_layout.addWidget(container)

    def _load_initial_data(self) -> None:
        stats = self.db.get_stats()
        self.footer_status.setText(f"⚡ {stats['total_files']} tệp trong kho")
        self._execute_search()

    def _on_search_text_changed(self) -> None:
        self.search_timer.start()

    def _select_filter(self, idx: int) -> None:
        self.active_filter_idx = idx
        for i, btn in enumerate(self.filter_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._execute_search()

    def _execute_search(self) -> None:
        self.search_timer.stop()
        query = self.search_input.text().strip()
        self.current_query = query
        _, _, exts = FILTER_CATEGORIES[self.active_filter_idx]

        self._request_counter += 1
        req_id = self._request_counter
        self.footer_status.setText("Đang tìm...")
        self.search_requested.emit(req_id, query, list(exts) if exts else [])

    @pyqtSlot(int, dict)
    def _on_search_completed(self, request_id: int, response: Dict[str, Any]) -> None:
        try:
            if request_id != self._request_counter:
                return

            results: List[SearchResultItem] = response.get("results", [])
            latency = response.get("latency_ms", 0)

            # Sort results naturally A-Z (case-insensitive / in hoa or not), tie-breaker by most recent time
            results = sort_search_results(results, "score")

            # Check if query targets club timetable/schedule compositor or dual-degree schedule
            q_text = getattr(self, "current_query", "") or self.search_input.text().strip()
            q_lower = q_text.lower()

            # 1. Quick Math / Calculation Card (safe_calculate zero-eval)
            import re
            calc_expr = None
            if re.search(r"\d", q_text) and any(op in q_text for op in ["+", "*", "/", "%", "^", " - "]):
                calc_expr = re.sub(r"^(?:tính|tinh|calc|calculate|\=)\s*", "", q_text, flags=re.I).strip()
            elif re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q_text, flags=re.I):
                m = re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q_text, flags=re.I)
                if m:
                    calc_expr = m.group(1).strip()

            if calc_expr:
                try:
                    from reasoning_strategies import safe_calculate
                    res_str = safe_calculate(calc_expr)
                    if res_str and "Lỗi" not in res_str and res_str != "None":
                        calc_item = SearchResultItem(
                            file_path=f"rat://calc_copy/{res_str}",
                            file_name=f"🧮 Kết quả tính toán: {res_str}",
                            file_ext=".calc",
                            file_size=0,
                            modified_at=time.time(),
                            score=2000.0,
                            explanation="⚡ Tính toán an toàn tức thì • Nhấn ↵ để sao chép kết quả",
                            snippet=f"Biểu thức: {calc_expr} = {res_str}\nNhấn Enter để sao chép số này vào clipboard.",
                        )
                        results.insert(0, calc_item)
                except Exception as e:
                    logger.debug(f"Spotlight calc card error: {e}")

            # 2. Campus Room Guide Card (TDTU Tân Phong)
            room_match = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", q_text)
            if room_match:
                try:
                    from rat.timetable.model import resolve_room_location
                    rm = room_match.group(1).upper()
                    loc = resolve_room_location(rm)
                    room_item = SearchResultItem(
                        file_path="rat://room_location",
                        file_name=f"📍 Vị trí phòng {rm}: {loc}",
                        file_ext=".map",
                        file_size=0,
                        modified_at=time.time(),
                        score=1800.0,
                        explanation="🏫 Cơ sở Tân Phong, ĐH Tôn Đức Thắng • Nhấn ↵ để xem chi tiết",
                        snippet=f"Phòng {rm} nằm tại {loc}.\nNhấn Enter để mở thẻ tra cứu chi tiết và bản đồ phòng.",
                    )
                    results.insert(0, room_item)
                except Exception as e:
                    logger.debug(f"Spotlight room card error: {e}")

            # 3. Live Agenda / Today's Schedule Card
            agenda_kw = ["hôm nay", "hom nay", "chiều nay", "chieu nay", "sáng nay", "sang nay", "tối nay", "toi nay", "tiết sau", "tiet sau", "lịch học", "lich hoc", "ai rảnh", "ai ranh"]
            if any(k in q_lower for k in agenda_kw):
                try:
                    from rat.timetable.compositor import TimetableCompositor
                    from rat.timetable.data import load_club_members
                    comp = TimetableCompositor()
                    members = load_club_members()
                    huy = next((m for m in members if "Huy" in m.name), members[0])
                    agenda = comp.get_today_agenda(huy)
                    c_count = len(agenda)
                    if c_count > 0:
                        first_c = agenda[0]
                        first_s = first_c["session"]
                        deg = "[ThS]" if first_s.degree_level == "master" else "[ĐH]"
                        ag_snip = f"Hôm nay ({huy.name}) có {c_count} ca học: [{first_c['start_time']} - {first_c['end_time']}] {deg} {first_s.course_name} (Phòng {first_s.room}) • {first_c['countdown']}"
                    else:
                        ag_snip = f"Hôm nay ({huy.name}) không có ca học nào trên TKB. Bạn đang hoàn toàn rảnh!"
                    ag_item = SearchResultItem(
                        file_path="rat://claude_widget",
                        file_name=f"⚡ Lịch học hôm nay: {c_count} ca học ({huy.name})",
                        file_ext=".app",
                        file_size=0,
                        modified_at=time.time(),
                        score=1500.0,
                        explanation="Nhấn ↵ để mở chi tiết trong Claude Widget (⌘W)",
                        snippet=ag_snip,
                    )
                    results.insert(0, ag_item)
                except Exception as e:
                    logger.debug(f"Spotlight agenda card error: {e}")

            schedule_keywords = [
                "tkb", "lich", "lịch", "thời khóa biểu", "thoi khoa bieu",
                "schedule", "clb", "golden slot", "thac si", "thạc sĩ",
                "cao hoc", "cao học", "song bang", "song bằng", "hop nhat", "hợp nhất"
            ]
            if any(k in q_lower for k in schedule_keywords):
                schedule_item = SearchResultItem(
                    file_path="rat://schedule_compositor",
                    file_name="🎓 Ghép Thời Khóa Biểu & TKB Hợp Nhất (Đại Học & Thạc Sĩ)",
                    file_ext=".app",
                    file_size=0,
                    modified_at=time.time(),
                    score=999.0,
                    explanation="⚡ Tác vụ nhanh: Mở bộ TKB Hợp Nhất Song Bằng & Ghép lịch CLB TDTU",
                    snippet="Live Updated • Hợp nhất môn cử nhân & cao học, nhận diện xung đột/chuyển ca, tìm khung giờ vàng nhóm và xuất .ics Calendar.",
                )
                results.insert(0, schedule_item)

            widget_keywords = ["widget", "mini", "claude", "tro ly", "trợ lý", "hoi tkb", "hỏi tkb", "ai ranh", "ai rảnh"]
            if any(k in q_lower for k in widget_keywords):
                widget_item = SearchResultItem(
                    file_path="rat://claude_widget",
                    file_name="✦ Trợ Lý TKB & Widget Tương Tác (Claude Form Mode)",
                    file_ext=".app",
                    file_size=0,
                    modified_at=time.time(),
                    score=1000.0,
                    explanation="⚡ Tác vụ nhanh: Mở Widget TKB tương tác đa năng dạng Claude Form",
                    snippet="Truy cập dynamic: Hỏi tự nhiên hôm nay/chiều nay, kiểm tra phòng TDTU, ai rảnh, cảnh báo xung đột và sổ tay ghi chú.",
                )
                results.insert(0, widget_item)

            self.result_list.clear()

            for item in results:
                list_item = QListWidgetItem(self.result_list)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                self.result_list.addItem(list_item)

            trace = response.get("reasoning_trace")
            self.feedback.refresh(
                self.result_list, response.get("query", self.current_query),
                response.get("parsed_context", {}),
                response.get("latency_ms"),
            )
            plan = response.get("plan")
            self.preview_panel.set_reasoning_trace(trace, plan)

            cot_badge = f"  •  🧠 CoT {int(trace.final_confidence*100)}%" if trace and trace.steps else ""
            q_text = getattr(self, "current_query", "") or self.search_input.text().strip()
            if results:
                self.result_list.setCurrentRow(0)
                self.footer_status.setText(f"{len(results)} kết quả ({latency}ms){cot_badge}")
            else:
                self.preview_panel.set_item(None)
                query_hint = f" cho '{q_text}'" if q_text else ""
                self.footer_status.setText(f"Không tìm thấy kết quả{query_hint} ({latency}ms) — Thử tìm theo phần mở rộng (.pdf, .py) hoặc mở rộng thư mục{cot_badge}")
        except Exception as e:
            logger.error(f"Error handling search completed in Spotlight: {e}", exc_info=True)

    def _on_result_selected(self, row: int) -> None:
        try:
            item = self.result_list.item(row)
            if item:
                search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
                q_text = getattr(self, "current_query", "") or self.search_input.text().strip()
                self.preview_panel.set_item(search_item, query=q_text)
            else:
                self.preview_panel.set_item(None)
        except Exception as e:
            logger.error(f"Error handling result selected in Spotlight: {e}", exc_info=True)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        try:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                if getattr(search_item, "file_path", "") == "rat://schedule_compositor":
                    self._open_schedule()
                    return
                elif getattr(search_item, "file_path", "") == "rat://claude_widget":
                    self._open_claude_widget()
                    return
                self.feedback.perform("open", search_item, open_file_default)
        except Exception as e:
            logger.error(f"Error handling double click in Spotlight: {e}", exc_info=True)

    def navigate_results(self, delta: int) -> None:
        count = self.result_list.count()
        if count == 0:
            return
        curr = self.result_list.currentRow()
        new_row = max(0, min(count - 1, curr + delta))
        self.result_list.setCurrentRow(new_row)

    def cycle_filter(self, delta: int) -> None:
        total = len(FILTER_CATEGORIES)
        new_idx = (self.active_filter_idx + delta) % total
        self._select_filter(new_idx)

    def show_spotlight(self) -> None:
        """Summon Spotlight window instantly (< 16ms) with pre-warmed state."""
        self._is_opening = True
        self._was_activated = False
        try:
            from rat.os.app import activate_macos_app
            activate_macos_app()
        except Exception:
            pass
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()
        self.search_input.selectAll()
        QTimer.singleShot(350, self._finish_opening)

    def _finish_opening(self) -> None:
        self._is_opening = False
        if self.isActiveWindow():
            self._was_activated = True

    def _open_current_file(self) -> None:
        curr_row = self.result_list.currentRow()
        item = self.result_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                if getattr(search_item, "file_path", "") == "rat://schedule_compositor":
                    self._open_schedule()
                    return
                elif getattr(search_item, "file_path", "") == "rat://claude_widget":
                    self._open_claude_widget()
                    return
                elif getattr(search_item, "file_path", "").startswith("rat://calc_copy/"):
                    res_val = search_item.file_path.split("rat://calc_copy/", 1)[1]
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(res_val)
                    self.show_toast(f"📋 Đã sao chép kết quả: {res_val}")
                    return
                elif getattr(search_item, "file_path", "") == "rat://room_location":
                    self._open_claude_widget()
                    return
                self.feedback.perform("open", search_item, open_file_default)

    def _reveal_current_in_finder(self) -> None:
        curr_row = self.result_list.currentRow()
        item = self.result_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                self.feedback.perform("reveal", search_item, reveal_in_finder)

    def _open_current_in_terminal(self) -> None:
        curr_row = self.result_list.currentRow()
        item = self.result_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                self.feedback.perform("terminal", search_item, open_in_terminal)
                self.show_toast(f"💻 Đã mở Terminal: {search_item.file_name}")

    def _preview_quick_look(self) -> None:
        curr_row = self.result_list.currentRow()
        item = self.result_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                trigger_quicklook(search_item.file_path)

    def _copy_current_path(self) -> None:
        curr_row = self.result_list.currentRow()
        item = self.result_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            cb = QApplication.clipboard()
            if cb and search_item:
                cb.setText(search_item.file_path)
                self.show_toast(f"✓ Đã sao chép đường dẫn: {search_item.file_name}")

    def _copy_current_content(self) -> None:
        curr_row = self.result_list.currentRow()
        item = self.result_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                from rat.crawler.extractors import extract_document_content
                text = extract_document_content(search_item.file_path)
                cb = QApplication.clipboard()
                if cb:
                    cb.setText(text)
                    self.show_toast(f"✓ Đã chép nội dung ({len(text)} ký tự)")

    def show_toast(self, message: str, timeout_ms: int = 2500) -> None:
        """Show temporary status feedback in action footer."""
        old_text = self.footer_status.text()
        self.footer_status.setText(message)
        self.footer_status.setStyleSheet("color: #34c759; font-weight: 600;")

        def _restore():
            self.footer_status.setText(old_text)
            self.footer_status.setStyleSheet("")

        QTimer.singleShot(timeout_ms, _restore)

    def _open_action_menu(self) -> None:
        curr_row = self.result_list.currentRow()
        curr_item = self.result_list.item(curr_row)
        search_item = curr_item.data(Qt.ItemDataRole.UserRole) if curr_item else None

        self._dialog_active = True
        try:
            dialog = ActionMenuDialog(search_item, self)
            dialog.action_triggered.connect(self._handle_action)
            pos = self.mapToGlobal(QPoint((self.width() - dialog.width()) // 2, (self.height() - dialog.height()) // 2))
            dialog.move(pos)
            dialog.exec()
        finally:
            self._dialog_active = False
            self.search_input.setFocus()

    def _handle_action(self, action_id: str) -> None:
        curr_row = self.result_list.currentRow()
        curr_item = self.result_list.item(curr_row)
        search_item: Optional[SearchResultItem] = curr_item.data(Qt.ItemDataRole.UserRole) if curr_item else None

        if action_id == "open" and search_item:
            self._open_current_file()
        elif action_id == "quicklook" and search_item:
            self._preview_quick_look()
        elif action_id == "finder" and search_item:
            self._reveal_current_in_finder()
        elif action_id == "terminal" and search_item:
            self._open_current_in_terminal()
        elif action_id == "copy_path" and search_item:
            self._copy_current_path()
        elif action_id == "copy_content" and search_item:
            self._copy_current_content()
        elif action_id == "ask_ai" and search_item:
            self.preview_panel.ask_input.setFocus()
        elif action_id == "schedule":
            self._open_schedule()
        elif action_id == "widget":
            self._open_claude_widget()
        elif action_id == "settings":
            self._open_settings()

    def _open_schedule(self) -> None:
        self._dialog_active = True
        try:
            from rat.ui.schedule_window import ScheduleCompositorWindow
            if not hasattr(self, "_schedule_window") or not self._schedule_window:
                self._schedule_window = ScheduleCompositorWindow()
            self._schedule_window.show()
            self._schedule_window.raise_()
            self._schedule_window.activateWindow()
        except Exception as e:
            logger.error(f"Error opening ScheduleCompositorWindow: {e}", exc_info=True)
        finally:
            self._dialog_active = False

    def _open_claude_widget(self) -> None:
        self._dialog_active = True
        try:
            from rat.ui.claude_widget import ClaudeTimetableWindow
            if not hasattr(self, "_claude_widget_window") or not self._claude_widget_window:
                self._claude_widget_window = ClaudeTimetableWindow()
            self._claude_widget_window.show()
            self._claude_widget_window.raise_()
            self._claude_widget_window.activateWindow()
            self.hide()
        except Exception as e:
            logger.error(f"Error opening ClaudeTimetableWindow: {e}", exc_info=True)
        finally:
            self._dialog_active = False

    def _open_settings(self) -> None:
        self._dialog_active = True
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        finally:
            self._dialog_active = False
            self.search_input.setFocus()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._was_activated = True
            elif (
                not getattr(self, "_dialog_active", False)
                and not getattr(self, "_is_opening", False)
                and getattr(self, "_was_activated", False)
            ):
                self.hide()
                self._was_activated = False
        super().changeEvent(event)

    def hideEvent(self, event) -> None:
        self._is_opening = False
        self._was_activated = False
        super().hideEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        # CMD + Number for Tab switching (⌘1, ⌘2, ⌘3, ⌘4, ⌘5, ⌘6)
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_6:
                idx = key - Qt.Key.Key_1
                if idx < len(FILTER_CATEGORIES):
                    self._select_filter(idx)
                    return

        if key == Qt.Key.Key_K and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
            self._open_action_menu()
            return

        # Quick Look: Cmd + Y
        if key == Qt.Key.Key_Y and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
            self._preview_quick_look()
            return

        # Space -> Quick Look when focused on window
        if key == Qt.Key.Key_Space and not self.search_input.hasFocus():
            self._preview_quick_look()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                self._reveal_current_in_finder()
            elif modifiers & Qt.KeyboardModifier.AltModifier:
                self._open_current_in_terminal()
            else:
                self._open_current_file()
            return

        if key == Qt.Key.Key_C and (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._copy_current_content()
            else:
                self._copy_current_path()
            return

        if key == Qt.Key.Key_Tab:
            self.cycle_filter(1)
            return
        elif key == Qt.Key.Key_Backtab:
            self.cycle_filter(-1)
            return

        if key == Qt.Key.Key_Escape:
            if self.search_input.text():
                self.search_input.clear()
            else:
                self.hide()
            return

        if key == Qt.Key.Key_Down:
            self.navigate_results(1)
            return
        elif key == Qt.Key.Key_Up:
            self.navigate_results(-1)
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def shutdown(self) -> None:
        """Gracefully stop search thread, timers, and clean up resources with zero hang/crash."""
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
                        logger.warning("Spotlight search_thread did not terminate in 1.5s; forcing...")
                        self.search_thread.terminate()
                        self.search_thread.wait(500)
                self.search_thread.deleteLater()
            except Exception as e:
                logger.debug(f"Spotlight shutdown thread cleanup note: {e}")
            finally:
                self.search_thread = None

    def closeEvent(self, event) -> None:
        # Keep pre-warmed unless application is quitting
        app = QApplication.instance()
        if app and not getattr(app, "_is_quitting", False):
            event.ignore()
            self.hide()
            return

        self.shutdown()
        super().closeEvent(event)
