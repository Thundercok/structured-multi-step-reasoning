"""RAT natal atlas: local birth form, interactive vector wheel and exact tables."""
from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
from pathlib import Path

from PyQt6.QtCore import QByteArray, QDate, QRectF, QSize, QSizeF, Qt, QThread, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QKeyEvent, QPainter, QPdfWriter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
    QTimeEdit, QVBoxLayout, QWidget, QHeaderView,
)

from rat.astrology.chart import BirthData, HOUSE_SYSTEMS, NatalChart, SIGNS, calculate_chart, degree_text, point_map
from rat.astrology.places import PRESETS, Place, search_places
from rat.astrology.svg import ELEMENT_COLORS, planet_targets, render_poster, render_wheel

# The atlas extends RAT's warm paper palette. Selected state always has a border,
# table text and focus outline as well as color. See docs/natal_chart.md.
ATLAS_QSS = """
QMainWindow, QWidget#AtlasRoot { background: #f4f0e8; color: #30363e; }
QWidget { font-family: 'Helvetica Neue', Arial; font-size: 12px; color: #30363e; }
QFrame#PaperCard { background: #fcfaf6; border: 1px solid #e2d9ca; border-radius: 14px; }
QLabel#Eyebrow { color: #876e44; font-size: 10px; font-weight: 650; letter-spacing: 2px; }
QLabel#PageTitle { font-family: 'Georgia'; font-size: 33px; color: #30363e; }
QLabel#Muted { color: #72777c; }
QLabel#Error { color: #9b3f4b; }
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QDoubleSpinBox {
 background: #fffefa; border: 1px solid #d6cebf; border-radius: 7px; padding: 7px; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QDoubleSpinBox:focus { border: 2px solid #9e8352; padding: 6px; }
QPushButton { background: #eee7da; border: 1px solid #d7cbb7; border-radius: 8px; padding: 9px 12px; }
QPushButton:hover { background: #e6dccb; }
QPushButton:focus { border: 2px solid #9e8352; padding: 8px 11px; }
QPushButton:disabled { color: #99948b; background: #ede9e2; }
QPushButton#Primary { background: #3b4148; color: #fffaf1; border: 1px solid #3b4148; font-weight: 600; }
QPushButton#Primary:hover { background: #515860; }
QPushButton#Primary:focus { border: 2px solid #b69a62; }
QPushButton#Quiet { background: transparent; border: none; color: #7b6541; padding: 5px; }
QCheckBox { spacing: 7px; padding: 4px 0; }
QCheckBox::indicator { width: 16px; height: 16px; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: #737575; padding: 9px 7px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #30363e; border-bottom: 2px solid #a58b59; font-weight: 600; }
QTableWidget { background: #fcfaf6; alternate-background-color: #f5f1e9; border: none; gridline-color: #ece4d8; selection-background-color: #e6dac4; selection-color: #30363e; }
QHeaderView::section { background: #f5f1e9; border: none; padding: 8px 5px; color: #737575; font-size: 10px; }
QTextBrowser { background: transparent; border: none; padding: 4px; }
QScrollArea { background: transparent; border: none; }
QWidget#BirthForm, QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #d4c9b7; min-height: 25px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""


def label(text, object_name=None, wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if object_name:
        widget.setObjectName(object_name)
    widget.setWordWrap(wrap)
    return widget


def paper_card():
    card = QFrame()
    card.setObjectName("PaperCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)
    return card, layout


class PlaceSearchWorker(QThread):
    results_ready = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        try:
            self.results_ready.emit(search_places(self.query))
        except Exception:
            self.failed.emit("Không kết nối được dịch vụ tìm thành phố. Chọn địa điểm có sẵn hoặc nhập tọa độ trong Nâng cao.")


class ChartCanvas(QWidget):
    point_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = None
        self.selected = None
        self.show_aspects = True
        self.major_only = True
        self.renderer = QSvgRenderer(self)
        self.setMinimumSize(380, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("Vòng lá số tương tác")
        self.setAccessibleDescription("Bấm hành tinh để xem chi tiết. Dùng phím trái hoặc phải để chọn hành tinh.")

    def sizeHint(self):
        return QSize(620, 620)

    def set_chart(self, chart):
        self.chart = chart
        self.selected = None
        self.refresh()

    def refresh(self):
        if self.chart:
            self.renderer.load(QByteArray(render_wheel(self.chart, selected=self.selected,
                                                      show_aspects=self.show_aspects, major_only=self.major_only).encode()))
            self.update()

    def _bounds(self):
        side = min(self.width(), self.height())
        return QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.renderer.isValid():
            self.renderer.render(painter, self._bounds())
        if self.hasFocus():
            painter.setPen(QColor("#b29661"))
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -3, -3), 8, 8)

    def _point_at(self, pos):
        if not self.chart:
            return None
        bounds = self._bounds()
        x = (pos.x() - bounds.x()) * 900 / bounds.width()
        y = (pos.y() - bounds.y()) * 900 / bounds.height()
        candidates = [(key, (tx - x) ** 2 + (ty - y) ** 2) for key, (tx, ty) in planet_targets(self.chart).items()]
        key, distance = min(candidates, key=lambda pair: pair[1])
        return key if distance <= 24 ** 2 else None

    def select(self, point_id):
        self.selected = point_id
        self.refresh()
        self.point_selected.emit(point_id)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            key = self._point_at(event.position())
            if key:
                self.select(key)
                self.setFocus()

    def mouseMoveEvent(self, event):
        key = self._point_at(event.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if key else Qt.CursorShape.ArrowCursor)
        p = next((p for p in self.chart.positions if p.id == key), None) if self.chart else None
        self.setToolTip(f"{p.name} · {degree_text(p.longitude, seconds=True)}" + (f" · Nhà {p.house}" if p.house else "") if p else "Bấm một hành tinh, hoặc dùng phím ← → để xem chi tiết.")

    def keyPressEvent(self, event: QKeyEvent):
        if self.chart and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            ids = [p.id for p in self.chart.positions]
            index = ids.index(self.selected) if self.selected in ids else -1
            self.select(ids[(index + (1 if event.key() == Qt.Key.Key_Right else -1)) % len(ids)])
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.selected = None
            self.refresh()
        else:
            super().keyPressEvent(event)


class NatalChartWindow(QMainWindow):
    ask_assistant = pyqtSignal(str, object)

    def __init__(self, parent=None, birth=None):
        super().__init__(parent)
        self.chart: NatalChart | None = None
        self._place_worker = None
        self.setWindowTitle("RAT · Bản đồ sao cá nhân")
        self.setMinimumSize(1080, 730)
        self.resize(1400, 940)
        self.setStyleSheet(ATLAS_QSS)
        self._build_ui()
        self.load_birth(birth or BirthData("Ví dụ minh họa", "2000-06-15", "09:30", PRESETS[0].name,
                                         PRESETS[0].latitude, PRESETS[0].longitude, PRESETS[0].timezone))
        self.generate_chart(sample=birth is None)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("AtlasRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 20)
        outer.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(7)
        titles.addWidget(label("RAT  /  NATAL ATLAS", "Eyebrow"))
        titles.addWidget(label("Khoảnh khắc của bạn.", "PageTitle"))
        titles.addWidget(label("Một lá số đầy đủ. Một cách khám phá dễ dàng.", "Muted"))
        header.addLayout(titles)
        header.addStretch()
        self.btn_open = QPushButton("Mở hồ sơ")
        self.btn_open.clicked.connect(self.open_profile)
        self.btn_save = QPushButton("Lưu hồ sơ")
        self.btn_save.clicked.connect(self.save_profile)
        self.btn_export = QPushButton("Xuất bản đồ ↗")
        self.btn_export.clicked.connect(self.export_dialog)
        for btn in (self.btn_open, self.btn_save, self.btn_export):
            header.addWidget(btn)
        outer.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(18)
        outer.addLayout(body, 1)

        form_card, form_layout = paper_card()
        form_card.setFixedWidth(264)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_widget.setObjectName("BirthForm")
        form = QVBoxLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(13)
        form_layout.addWidget(form_scroll)
        form_scroll.setWidget(form_widget)
        form.addWidget(label("01  /  DỮ LIỆU SINH", "Eyebrow"))
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        self.name_input.setPlaceholderText("Tên hoặc biệt danh")
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd / MM / yyyy")
        self.date_input.setDateRange(QDate(1800, 1, 1), QDate(2399, 12, 31))
        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("HH : mm : ss")
        for title, widget in (("Tên lá số", self.name_input), ("Ngày sinh · ngày / tháng / năm", self.date_input), ("Giờ sinh tại nơi sinh · 24 giờ", self.time_input)):
            buddy = label(title)
            buddy.setBuddy(widget)
            widget.setAccessibleName(title)
            form.addWidget(buddy)
            form.addWidget(widget)
        self.unknown_time = QCheckBox("Mình chưa biết giờ sinh")
        self.unknown_time.toggled.connect(lambda value: self.time_input.setEnabled(not value))
        form.addWidget(self.unknown_time)
        form.addWidget(label("Nơi sinh", wrap=True))
        self.place_input = QComboBox()
        self.place_input.setEditable(True)
        self.place_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for place in PRESETS:
            self.place_input.addItem(place.name, place)
        self.place_input.currentIndexChanged.connect(self._select_place)
        self.place_input.setAccessibleName("Thành phố sinh, chọn hoặc tìm thành phố")
        form.addWidget(self.place_input)
        self.btn_search = QPushButton("Tìm thành phố khác")
        self.btn_search.setToolTip("Tìm qua Open-Meteo / GeoNames. Chỉ tên thành phố được gửi; ngày và giờ sinh ở máy bạn.")
        self.btn_search.clicked.connect(self._search_place)
        form.addWidget(self.btn_search)
        self.place_note = label("", "Muted", wrap=True)
        form.addWidget(self.place_note)
        form.addWidget(label("Hệ nhà", wrap=True))
        self.house_input = QComboBox()
        for code, name in HOUSE_SYSTEMS.items():
            self.house_input.addItem(name, code)
        self.house_input.setAccessibleName("Hệ nhà")
        form.addWidget(self.house_input)
        self.advanced_btn = QPushButton("Nâng cao  +")
        self.advanced_btn.setObjectName("Quiet")
        self.advanced_btn.setCheckable(True)
        form.addWidget(self.advanced_btn)
        self.advanced = QWidget()
        advanced = QFormLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        self.latitude = QDoubleSpinBox()
        self.longitude = QDoubleSpinBox()
        self.latitude.setRange(-89.9, 89.9)
        self.longitude.setRange(-180, 180)
        for spin in (self.latitude, self.longitude):
            spin.setDecimals(5)
            spin.setSingleStep(0.01)
        self.zone_input = QLineEdit()
        self.zone_input.setMaxLength(80)
        self.zone_input.setPlaceholderText("Asia/Ho_Chi_Minh")
        self.zodiac_input = QComboBox()
        self.zodiac_input.addItem("Tropical", "tropical")
        self.zodiac_input.addItem("Sidereal · Lahiri", "sidereal_lahiri")
        self.fold_input = QComboBox()
        for text, value in (("Tự kiểm tra", None), ("Giờ trùng: lần đầu", 0), ("Giờ trùng: lần sau", 1)):
            self.fold_input.addItem(text, value)
        self.orb_input = QDoubleSpinBox()
        self.orb_input.setRange(0.1, 10)
        self.orb_input.setDecimals(1)
        self.orb_input.setSuffix("°")
        self.orb_input.setValue(8)
        for text, widget in (("Vĩ độ", self.latitude), ("Kinh độ", self.longitude), ("Múi giờ IANA", self.zone_input), ("Hoàng đạo", self.zodiac_input), ("Chuyển giờ mùa hè", self.fold_input), ("Orb tối đa", self.orb_input)):
            advanced.addRow(text, widget)
            widget.setAccessibleName(text)
        self.advanced.hide()
        self.advanced_btn.toggled.connect(self.advanced.setVisible)
        self.advanced_btn.toggled.connect(lambda on: self.advanced_btn.setText("Nâng cao  −" if on else "Nâng cao  +"))
        form.addWidget(self.advanced)
        self.generate_btn = QPushButton("Lập lá số   →")
        self.generate_btn.setObjectName("Primary")
        self.generate_btn.clicked.connect(lambda: self.generate_chart())
        form.addWidget(self.generate_btn)
        self.form_status = label("", "Error", wrap=True)
        form.addWidget(self.form_status)
        form.addWidget(label("Tọa độ thành phố là điểm tham chiếu. Bạn có thể sửa tọa độ chính xác và múi giờ lịch sử trong Nâng cao.", "Muted", wrap=True))
        form.addStretch()
        form.addWidget(label("Địa điểm: Open-Meteo / GeoNames\nDữ liệu sinh lưu tại máy khi bạn chọn Lưu.", "Muted", wrap=True))
        body.addWidget(form_card)

        center = QVBoxLayout()
        center.setSpacing(13)
        self.big_three = QHBoxLayout()
        self.big_three.setSpacing(10)
        center.addLayout(self.big_three)
        chart_card, chart_layout = paper_card()
        chart_layout.setContentsMargins(12, 14, 12, 12)
        wheel_heading = QHBoxLayout()
        self.chart_title = label("Lá số gốc")
        self.chart_title.setWordWrap(True)
        self.chart_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.chart_title.setStyleSheet("font-family: Georgia; font-size: 22px;")
        wheel_heading.addWidget(self.chart_title, 1)
        self.chart_mode = label("", "Muted")
        wheel_heading.addWidget(self.chart_mode)
        chart_layout.addLayout(wheel_heading)
        self.canvas = ChartCanvas()
        self.canvas.point_selected.connect(self.select_point)
        chart_layout.addWidget(self.canvas, 1)
        controls = QHBoxLayout()
        self.aspects_check = QCheckBox("Góc chiếu")
        self.aspects_check.setChecked(True)
        self.major_check = QCheckBox("Chỉ góc chính")
        self.major_check.setChecked(True)
        self.aspects_check.toggled.connect(self._change_aspects)
        self.major_check.toggled.connect(self._change_aspects)
        controls.addWidget(self.aspects_check)
        controls.addWidget(self.major_check)
        controls.addStretch()
        controls.addWidget(label("Chọn hành tinh · ← →", "Muted"))
        chart_layout.addLayout(controls)
        center.addWidget(chart_card, 1)
        self.chart_notice = label("", "Muted", wrap=True)
        center.addWidget(self.chart_notice)
        body.addLayout(center, 1)

        details_card, details_layout = paper_card()
        details_card.setFixedWidth(320)
        details_layout.setContentsMargins(13, 17, 13, 14)
        details_layout.addWidget(label("02  /  KHÁM PHÁ LÁ SỐ", "Eyebrow"))
        self.details = QTextBrowser()
        self.details.setMinimumHeight(165)
        self.details.setMaximumHeight(235)
        details_layout.addWidget(self.details)
        self.tabs = QTabWidget()
        self.planet_table = self._table(("Điểm", "Vị trí", "Nhà"))
        self.house_table = self._table(("Nhà", "Đỉnh nhà"))
        self.aspect_table = self._table(("Cặp điểm", "Góc", "Orb"))
        self.guide = QTextBrowser()
        self.guide.setHtml(self._guide_html())
        for widget, title in ((self.planet_table, "Điểm"), (self.house_table, "Nhà"), (self.aspect_table, "Góc chiếu"), (self.guide, "Hướng dẫn")):
            self.tabs.addTab(widget, title)
        self.planet_table.cellClicked.connect(lambda row, col: self.canvas.select(self.chart.positions[row].id) if self.chart else None)
        self.aspect_table.cellClicked.connect(self.select_aspect)
        self.house_table.cellClicked.connect(lambda row, col: self.select_point(self.house_table.item(row, 0).text()) if self.chart else None)
        details_layout.addWidget(self.tabs, 1)
        self.balance = label("", "Muted", wrap=True)
        details_layout.addWidget(self.balance)
        self.ask_btn = QPushButton("Hỏi Chuột về lá số này")
        self.ask_btn.setToolTip("Gửi các vị trí đã tính vào cuộc trò chuyện để model diễn giải.")
        self.ask_btn.clicked.connect(self._ask)
        self.ask_btn.setVisible(self.parent() is not None)
        details_layout.addWidget(self.ask_btn)
        body.addWidget(details_card)
        footer = QHBoxLayout()
        self.sample_note = label("", "Muted", wrap=True)
        footer.addWidget(self.sample_note)
        footer.addStretch()
        footer.addWidget(label("Tính vị trí offline  ·  Giờ sinh theo múi giờ lịch sử  ·  Xuất SVG / PNG / PDF", "Muted"))
        outer.addLayout(footer)
        # Mark the displayed result stale whenever any birth/calculation input changes.
        for widget in (self.name_input, self.zone_input):
            widget.textChanged.connect(self._mark_dirty)
        self.place_input.editTextChanged.connect(self._mark_dirty)
        self.date_input.dateChanged.connect(self._mark_dirty)
        self.time_input.timeChanged.connect(self._mark_dirty)
        self.unknown_time.toggled.connect(self._mark_dirty)
        for widget in (self.latitude, self.longitude, self.orb_input):
            widget.valueChanged.connect(self._mark_dirty)
        for widget in (self.house_input, self.zodiac_input, self.fold_input):
            widget.currentIndexChanged.connect(self._mark_dirty)

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setDefaultSectionSize(36)
        return table

    def _mark_dirty(self, *args):
        if self.chart:
            self.form_status.setText("Dữ liệu đã đổi. Bấm Lập lá số để cập nhật.")
            self.btn_export.setEnabled(False)
            self.ask_btn.setEnabled(False)
            self.sample_note.setText("Đang hiển thị lá số trước khi sửa.")

    def _select_place(self, index):
        place = self.place_input.itemData(index)
        if isinstance(place, Place):
            self.latitude.setValue(place.latitude)
            self.longitude.setValue(place.longitude)
            self.zone_input.setText(place.timezone)
            self.place_note.setText(f"{place.latitude:.4f}°, {place.longitude:.4f}°\n{place.timezone}")

    def _search_place(self):
        if self._place_worker and self._place_worker.isRunning():
            return
        query = self.place_input.currentText().strip()
        if len(query) < 2:
            self.form_status.setText("Nhập tên thành phố từ 2 ký tự.")
            return
        self.btn_search.setEnabled(False)
        self.btn_search.setText("Đang tìm…")
        worker = PlaceSearchWorker(query, self)
        self._place_worker = worker
        worker.results_ready.connect(self._places_found)
        worker.failed.connect(self.form_status.setText)
        worker.finished.connect(lambda: self.btn_search.setEnabled(True))
        worker.finished.connect(lambda: self.btn_search.setText("Tìm thành phố khác"))
        worker.start()

    def _places_found(self, places):
        if not places:
            self.form_status.setText("Không tìm thấy. Thử tên khác của thành phố, hoặc nhập tọa độ trong Nâng cao.")
            return
        self.place_input.clear()
        for place in places:
            self.place_input.addItem(place.name, place)
        self._select_place(0)
        self.form_status.setText("Chọn đúng thành phố trong danh sách rồi lập lá số.")
        self.place_input.showPopup()

    def birth_from_form(self):
        place = self.place_input.currentData()
        title = self.place_input.currentText().strip()
        if not title:
            raise ValueError("Nhập nơi sinh hoặc chọn một thành phố.")
        # Typed text is never treated as a resolved place with a previous city's coordinates.
        if isinstance(place, Place) and title != place.name and not self.advanced_btn.isChecked():
            raise ValueError("Bấm Tìm thành phố khác và chọn kết quả, hoặc nhập tọa độ trong Nâng cao.")
        if not isinstance(place, Place) and not self.advanced_btn.isChecked():
            raise ValueError("Chọn kết quả địa điểm hoặc nhập tọa độ trong Nâng cao.")
        return BirthData(self.name_input.text().strip()[:100] or "Lá số cá nhân", self.date_input.date().toString("yyyy-MM-dd"),
                         self.time_input.time().toString("HH:mm:ss"), title[:200], self.latitude.value(),
                         self.longitude.value(), self.zone_input.text().strip(), not self.unknown_time.isChecked(),
                         self.fold_input.currentData(), self.house_input.currentData(), self.zodiac_input.currentData(),
                         self.orb_input.value())

    def load_birth(self, birth):
        self.name_input.setText(birth.name)
        self.date_input.setDate(QDate.fromString(birth.date, "yyyy-MM-dd"))
        parsed = QTime.fromString(birth.time, "HH:mm:ss")
        self.time_input.setTime(parsed if parsed.isValid() else QTime.fromString(birth.time, "HH:mm"))
        self.unknown_time.setChecked(not birth.time_known)
        place = Place(birth.place, birth.latitude, birth.longitude, birth.timezone)
        self.place_input.addItem(place.name, place)
        self.place_input.setCurrentIndex(self.place_input.count() - 1)
        self.latitude.setValue(birth.latitude)
        self.longitude.setValue(birth.longitude)
        self.zone_input.setText(birth.timezone)
        self.house_input.setCurrentIndex(self.house_input.findData(birth.house_system))
        self.zodiac_input.setCurrentIndex(self.zodiac_input.findData(birth.zodiac))
        self.fold_input.setCurrentIndex(self.fold_input.findData(birth.fold))
        self.orb_input.setValue(birth.max_orb)

    def generate_chart(self, sample=False):
        try:
            chart = calculate_chart(self.birth_from_form())
        except (ValueError, TypeError) as exc:
            self.form_status.setText(str(exc))
            self.btn_export.setEnabled(False)
            self.ask_btn.setEnabled(False)
            return
        self.chart = chart
        self.canvas.set_chart(chart)
        self.form_status.setText("")
        self.btn_export.setEnabled(True)
        self.ask_btn.setEnabled(True)
        self.sample_note.setText("Ví dụ minh họa · sửa dữ liệu sinh để tạo lá số của bạn." if sample else f"{chart.birth.name} · {chart.birth.date} · {chart.birth.time if chart.birth.time_known else 'chưa biết giờ'} · {chart.birth.place}")
        self.chart_title.setText(chart.birth.name)
        self.chart_mode.setText(("Tropical" if chart.birth.zodiac == "tropical" else "Lahiri") + " · " + (HOUSE_SYSTEMS[chart.birth.house_system] if chart.cusps else "Chưa biết giờ"))
        self.chart_notice.setText("\n".join(chart.notices) or "Vạch chỉ tọa độ chính xác; ký hiệu được giãn khi các hành tinh đứng gần nhau.")
        while self.big_three.count():
            item = self.big_three.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for key, title, glyph in (("sun", "MẶT TRỜI", "☉"), ("moon", "MẶT TRĂNG", "☽"), ("ASC", "CUNG MỌC", "↗")):
            point = next((p for p in chart.positions if p.id == key), None)
            longitude = point.longitude if point else chart.angles.get(key)
            card, layout = paper_card()
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(6)
            layout.addWidget(label(f"{glyph}  {title}", "Eyebrow"))
            name = SIGNS[int(longitude // 30)][0] if longitude is not None else "Chưa biết giờ"
            big = label(name)
            big.setStyleSheet("font-family: Georgia; font-size: 19px;")
            layout.addWidget(big)
            layout.addWidget(label(degree_text(longitude).split(' ', 1)[0] if longitude is not None else "Cần giờ sinh", "Muted"))
            self.big_three.addWidget(card)
        self._populate_tables()
        self.balance.setText("10 hành tinh · " + " · ".join(f"{key} {value}" for key, value in chart.elements.items()) + "\n" + " · ".join(f"{key} {value}" for key, value in chart.modalities.items()))
        self.select_point("sun")
        self.canvas.selected = None
        self.canvas.refresh()

    def _populate_tables(self):
        self.planet_table.setRowCount(len(self.chart.positions))
        for row, p in enumerate(self.chart.positions):
            values = (f"{p.glyph} {p.name.split(' (')[0]}" + (" ℞" if p.retrograde else ""), degree_text(p.longitude), str(p.house) if p.house else "—")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(f"{p.name}\n{degree_text(p.longitude, seconds=True)}\nTốc độ: {p.speed:.6f}°/ngày")
                self.planet_table.setItem(row, col, item)
        self.house_table.setRowCount(len(self.chart.cusps) + len(self.chart.angles))
        for row, (title, longitude) in enumerate([(str(i + 1), cusp) for i, cusp in enumerate(self.chart.cusps)] + list(self.chart.angles.items())):
            self.house_table.setItem(row, 0, QTableWidgetItem(title))
            self.house_table.setItem(row, 1, QTableWidgetItem(degree_text(longitude, seconds=True)))
        self.aspect_table.setRowCount(len(self.chart.aspects))
        names = point_map(self.chart)
        for row, aspect in enumerate(self.chart.aspects):
            values = (f"{names[aspect.first].glyph}  {names[aspect.second].glyph}", f"{aspect.glyph} {aspect.name}", f"{aspect.orb:.2f}°")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(f"{names[aspect.first].name} – {names[aspect.second].name}\nGóc thực: {aspect.separation:.6f}° · Orb giới hạn: {aspect.max_orb}°")
                self.aspect_table.setItem(row, col, item)
        self.planet_table.resizeColumnsToContents()

    def select_point(self, key):
        if not self.chart:
            return
        p = point_map(self.chart).get(key)
        if not p:
            return
        sign = SIGNS[p.sign_index]
        aspects = [a for a in self.chart.aspects if key in (a.first, a.second)]
        others = point_map(self.chart)
        lines = []
        for a in aspects:
            other = others[a.second if a.first == key else a.first]
            lines.append(f"{escape(a.glyph)} {escape(other.name.split(' (')[0])} · {escape(a.name)} · {a.orb:.2f}°")
        interval = ""
        if p.day_range:
            interval = f"<p>Hai đầu ngày: {escape(degree_text(p.day_range[0]))} → {escape(degree_text(p.day_range[1]))}. Giờ chưa biết nên góc chiếu chỉ tạm tính.</p>"
        self.details.setHtml(f'<p style="color:#876e44; font-size:10px;">ĐIỂM ĐANG CHỌN</p><h2 style="font-family:Georgia; font-weight:400; margin:5px 0;">{escape(p.glyph)} {escape(p.name)}</h2>'
                             f'<p><b>{escape(degree_text(p.longitude, seconds=True))}</b><br>{escape(sign[2])} · {escape(sign[3])}'
                             + (f' · Nhà {p.house}' if p.house else '') + (' · Nghịch hành ℞' if p.retrograde else '') +
                             '<br><span style="color:#777c82">' + ('Điểm trục tính từ giờ và nơi sinh' if p.ephemeris == 'axis_geometry' else f'Tốc độ {p.speed:.5f}°/ngày · Vĩ độ {p.latitude:.4f}°') + '</span></p>'
                             + interval + '<p style="line-height:1.6">' + '<br>'.join(lines) + '</p>')
        if p in self.chart.positions:
            self.planet_table.selectRow(self.chart.positions.index(p))
        else:
            self.planet_table.clearSelection()
        self.canvas.selected = key
        self.canvas.refresh()

    def select_aspect(self, row, col):
        if not self.chart:
            return
        a = self.chart.aspects[row]
        names = {key: point.name for key, point in point_map(self.chart).items()}
        self.canvas.selected = a.first
        self.canvas.refresh()
        motion = "Đang tiến gần góc chính xác" if a.applying else "Đang rời góc chính xác" if a.applying is False else "Tại góc chính xác" if a.orb < 1e-8 else "Không tính xu hướng cho góc với trục"
        self.details.setHtml(f'<h2 style="font-family:Georgia;font-weight:400">{escape(a.glyph)} {escape(a.name)}</h2>'
                             f'<p>{escape(names[a.first])} × {escape(names[a.second])}</p>'
                             f'<p>Góc thực <b>{a.separation:.6f}°</b><br>Góc chuẩn {a.exact_angle}° · Orb {a.orb:.6f}°<br>Giới hạn orb {a.max_orb}°<br>{motion}</p>'
                             '<p style="color:#777c82">Xu hướng tính theo vận tốc tức thời tại giờ sinh.</p>')

    def _change_aspects(self, *args):
        self.canvas.show_aspects = self.aspects_check.isChecked()
        self.canvas.major_only = self.major_check.isChecked()
        self.canvas.refresh()

    @staticmethod
    def _guide_html():
        return """<h3>Đọc lá số từ đâu?</h3><p>Bắt đầu với Mặt Trời, Mặt Trăng và Cung Mọc, rồi chọn từng hành tinh trên vòng tròn hoặc trong bảng.</p>
        <p><b>Cung:</b> đoạn 30° trong vòng hoàng đạo. Tropical lấy xuân phân làm mốc; Sidereal ở đây dùng Lahiri.</p>
        <p><b>Nhà:</b> 12 vùng phụ thuộc giờ và nơi sinh. Chọn hệ nhà trong biểu mẫu; hệ nhà khác có thể đổi vị trí nhà của một hành tinh.</p>
        <p><b>ASC / DSC:</b> Cung Mọc và điểm đối diện. <b>MC / IC:</b> Thiên Đỉnh và điểm đối diện. Whole Sign không nhất thiết đặt MC ở đỉnh nhà 10.</p>
        <p><b>℞:</b> chuyển động biểu kiến nghịch hành. Các nút và Lilith là điểm hình học, không phải hành tinh.</p>
        <p><b>Orb:</b> độ lệch so với góc chuẩn. Orb càng nhỏ, góc càng sát. Trùng tụ / đối đỉnh ≤8°; vuông / tam hợp ≤6°; lục hợp ≤4°; quincunx ≤2°. Nâng cao cho phép giảm giới hạn chung.</p>
        <p><b>Đường màu:</b> xanh lam: tam hợp; xanh lục: lục hợp; hồng: vuông / đối đỉnh. Bảng ghi tên góc để bạn không cần nhận diện màu.</p>
        <p><b>Chưa biết giờ:</b> dùng 12:00 làm mốc tham khảo và ẩn toàn bộ nhà / góc trục. Vị trí Mặt Trăng có thể thay đổi đáng kể trong ngày.</p>
        <p>Ứng dụng tính vị trí thiên thể. Phần diễn giải chiêm tinh, nếu yêu cầu Chuột, là diễn giải biểu tượng từ những vị trí đó.</p>"""

    def save_profile(self):
        try:
            birth = self.birth_from_form()
            calculate_chart(birth)  # reject invalid time/zone before saving a usable profile
            path, _ = QFileDialog.getSaveFileName(self, "Lưu dữ liệu sinh tại máy", "la-so.json", "Hồ sơ lá số (*.json)")
            if path:
                Path(path).write_text(json.dumps({"schema": "rat-natal-v1", "birth": asdict(birth)}, ensure_ascii=False, indent=2) + "\n")
                self.form_status.setText("Đã lưu hồ sơ tại máy.")
        except (ValueError, OSError) as exc:
            self.form_status.setText(str(exc))

    def open_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Mở hồ sơ lá số", "", "Hồ sơ lá số (*.json)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > 20_000:
                raise ValueError("Hồ sơ quá lớn.")
            payload = json.loads(Path(path).read_text())
            if payload.get("schema") != "rat-natal-v1":
                raise ValueError("Định dạng hồ sơ không được hỗ trợ.")
            birth = BirthData(**payload["birth"])
            calculate_chart(birth)
            self.load_birth(birth)
            self.generate_chart()
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.form_status.setText(f"Không mở được hồ sơ: {exc}")

    def export_dialog(self):
        if not self.chart or not self.btn_export.isEnabled():
            return
        path, selected_filter = QFileDialog.getSaveFileName(self, "Xuất lá số", "la-so", "SVG vector (*.svg);;PNG độ phân giải cao (*.png);;PDF (*.pdf)")
        if not path:
            return
        suffix = {"SVG": ".svg", "PNG": ".png", "PDF": ".pdf"}[selected_filter.split()[0]]
        target = Path(path)
        if target.suffix.lower() not in (".svg", ".png", ".pdf"):
            target = target.with_suffix(suffix)
        try:
            self.export_to(target)
            self.form_status.setText(f"Đã xuất {target.name}.")
        except (OSError, ValueError) as exc:
            self.form_status.setText(f"Không xuất được: {exc}")

    def export_to(self, path):
        if not self.chart:
            raise ValueError("Chưa có lá số để xuất.")
        from rat.astrology.export import export_chart
        export_chart(
            self.chart,
            path,
            show_aspects=self.canvas.show_aspects,
            major_only=self.canvas.major_only,
        )

    def _ask(self):
        if self.chart:
            self.ask_assistant.emit("Diễn giải lá số gốc của " + self.chart.birth.name + " bằng tiếng Việt, dựa trên dữ liệu đã tính. Phân biệt vị trí thiên thể và diễn giải biểu tượng; không suy đoán sự kiện tương lai.", self.chart.to_dict())

    def closeEvent(self, event):
        if self._place_worker and self._place_worker.isRunning():
            self._place_worker.wait(11_000)
        super().closeEvent(event)
