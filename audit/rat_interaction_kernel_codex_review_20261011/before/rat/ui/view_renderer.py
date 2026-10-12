"""
rat.ui.view_renderer — Qt ViewRenderer for declarative ViewSpecs.

Renders ViewSpecs into native PyQt6 widgets with RAT's warm paper/ink/gold visual styling.
Supports:
- summary: title, text, metadata badges
- table/rows: clean formatted data rows
- resource: registered domain renderers (e.g. interactive ChartCanvas for 'wheel')
- input_form: inline input fields for InputRequest with preserved inputs and candidate pills
- actions: action buttons bound to ActionDispatcher with stale revision detection
- details: expandable/collapsible details section
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QDate, QRectF, QSize, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from rat.kernel.contracts import Artifact, ArtifactAction, InputRequest
from rat.kernel.view_spec import ViewBlock, ViewSpec


CARD_STYLE = """
QFrame#ArtifactCard {
    background-color: #FCFAF6;
    border: 1px solid #E2D9CA;
    border-radius: 12px;
    padding: 12px;
}
QLabel#CardTitle {
    color: #1F1A16;
    font-size: 13px;
    font-weight: 750;
}
QLabel#CardText {
    color: #4A4036;
    font-size: 12px;
    line-height: 1.4;
}
QLabel#CardBadge {
    background: #EFE8DC;
    color: #705C38;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 600;
}
QLabel#StaleBadge {
    background: #FBEAEB;
    color: #9B3F4B;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 600;
}
QPushButton.ActionBtn {
    background-color: #EEE7DA;
    border: 1px solid #D7CBB7;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #30363E;
}
QPushButton.ActionBtn:hover {
    background-color: #E6DCCB;
    border-color: #C5B69F;
}
QPushButton.ActionBtn:pressed {
    background-color: #DCD0BC;
}
QPushButton.ActionBtn:disabled {
    background-color: #F5F1E9;
    color: #A39C93;
    border-color: #EAE3D6;
}
QPushButton.CandidateBtn {
    background-color: #FFFFFF;
    border: 1px solid #D4B872;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    color: #7A5800;
    font-weight: 600;
}
QPushButton.CandidateBtn:hover {
    background-color: #FFFDF9;
    border-color: #B29661;
}
QLineEdit, QDateEdit, QTimeEdit {
    background: #FFFFFF;
    border: 1px solid #D6CEBF;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    color: #1F1A16;
}
QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus {
    border: 1px solid #9E8352;
}
"""


class QtViewRenderer(QFrame):
    """Renders a declarative ViewSpec into Qt widgets."""

    action_dispatched = pyqtSignal(object, dict)  # ArtifactAction, user_inputs
    input_submitted = pyqtSignal(str, dict)       # operation_name, supplied_inputs

    def __init__(
        self,
        spec: ViewSpec,
        artifact: Optional[Artifact] = None,
        is_latest: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.artifact = artifact
        self.is_latest = is_latest
        self.input_fields: Dict[str, QWidget] = {}
        self._wheel_widget: Optional[QWidget] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("ArtifactCard")
        self.setStyleSheet(CARD_STYLE)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)

        for block in self.spec.blocks:
            self._render_block(block)

    def _render_block(self, block: ViewBlock) -> None:
        b_type = block.type
        data = block.data

        if b_type == "summary":
            self._render_summary(data)
        elif b_type in ("table", "rows"):
            self._render_table(data)
        elif b_type == "resource":
            self._render_resource(data)
        elif b_type == "input_form":
            self._render_input_form(data)
        elif b_type == "actions":
            self._render_actions(data)
        elif b_type == "details":
            self._render_details(data)

    def _render_summary(self, data: Dict[str, Any]) -> None:
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        title = data.get("title", "")
        if title:
            lbl_title = QLabel(title)
            lbl_title.setObjectName("CardTitle")
            header_row.addWidget(lbl_title)

        header_row.addStretch()

        if not self.is_latest:
            stale_badge = QLabel("Phiên bản cũ")
            stale_badge.setObjectName("StaleBadge")
            stale_badge.setToolTip("Kết quả này đã được cập nhật ở phiên bản mới hơn.")
            header_row.addWidget(stale_badge)
        elif "badge" in data:
            badge = QLabel(data["badge"])
            badge.setObjectName("CardBadge")
            header_row.addWidget(badge)

        self.layout.addLayout(header_row)

        text = data.get("text", "")
        if text:
            lbl_text = QLabel(text)
            lbl_text.setObjectName("CardText")
            lbl_text.setWordWrap(True)
            self.layout.addWidget(lbl_text)

    def _render_table(self, data: Dict[str, Any]) -> None:
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        if not rows:
            return

        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background-color: #FAF7F2;
                border: 1px solid #ECE4D8;
                border-radius: 8px;
                padding: 4px;
            }
        """)
        t_layout = QVBoxLayout(table_frame)
        t_layout.setContentsMargins(6, 6, 6, 6)
        t_layout.setSpacing(3)

        # Header row
        if headers:
            h_row = QHBoxLayout()
            h_row.setSpacing(8)
            for h in headers:
                hl = QLabel(h)
                hl.setStyleSheet("color: #7A7267; font-size: 10px; font-weight: 700;")
                h_row.addWidget(hl, 1)
            t_layout.addLayout(h_row)

        for row_items in rows[:6]:
            r_row = QHBoxLayout()
            r_row.setSpacing(8)
            for item in row_items:
                rl = QLabel(str(item))
                rl.setStyleSheet("color: #30363E; font-size: 11px;")
                rl.setWordWrap(True)
                r_row.addWidget(rl, 1)
            t_layout.addLayout(r_row)

        self.layout.addWidget(table_frame)

    def _render_resource(self, data: Dict[str, Any]) -> None:
        res_name = data.get("resource")
        if res_name == "wheel":
            chart_data = data.get("chart_data")
            if chart_data:
                try:
                    from rat.astrology.chart import BirthData, NatalChart, calculate_chart
                    from rat.ui.natal_chart import ChartCanvas

                    # Reconstruct chart if necessary
                    chart = None
                    if isinstance(chart_data, dict) and "birth" in chart_data:
                        birth = BirthData(**chart_data["birth"])
                        chart = calculate_chart(birth)

                    if chart is not None:
                        canvas = ChartCanvas()
                        canvas.setMinimumSize(280, 280)
                        canvas.setMaximumSize(420, 420)
                        canvas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
                        canvas.set_chart(chart)
                        self._wheel_widget = canvas
                        self.layout.addWidget(canvas, 0, Qt.AlignmentFlag.AlignCenter)
                        return
                except Exception as exc:
                    err_lbl = QLabel(f"Không thể kết xuất vòng lá số: {exc}")
                    err_lbl.setStyleSheet("color: #9B3F4B; font-size: 11px;")
                    self.layout.addWidget(err_lbl)
                    return

    def _render_input_form(self, data: Dict[str, Any]) -> None:
        op_name = data.get("operation_name", "")
        missing = data.get("missing_fields", [])
        candidates = data.get("candidate_choices")
        supplied = data.get("supplied_inputs", {})

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F5F0;
                border: 1px dashed #C8BDB0;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        f_layout = QVBoxLayout(form_frame)
        f_layout.setContentsMargins(8, 8, 8, 8)
        f_layout.setSpacing(6)

        # Candidate choices (e.g. ambiguous cities)
        if candidates:
            cand_label = QLabel("Chọn địa điểm phù hợp:")
            cand_label.setStyleSheet("color: #705C38; font-size: 11px; font-weight: 700;")
            f_layout.addWidget(cand_label)

            c_flow = QHBoxLayout()
            c_flow.setSpacing(6)
            for c in candidates[:4]:
                name = c.get("name", "")
                btn = QPushButton(name)
                btn.setProperty("class", "CandidateBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, cand=c: self._on_candidate_chosen(op_name, cand, supplied))
                c_flow.addWidget(btn)
            c_flow.addStretch()
            f_layout.addLayout(c_flow)

        # Missing input fields
        for mf in missing:
            f_name = mf.get("name", "")
            f_label = mf.get("label", f_name)
            f_type = mf.get("type", "string")

            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(f"{f_label}:")
            lbl.setFixedWidth(80)
            lbl.setStyleSheet("color: #4A4036; font-size: 11px; font-weight: 600;")
            row.addWidget(lbl)

            input_widget: QWidget
            if f_type == "date":
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("YYYY-MM-DD (vd: 2000-06-15)")
                if f_name in supplied:
                    input_widget.setText(str(supplied[f_name]))
            elif f_type == "time":
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("HH:MM (vd: 09:30)")
                if f_name in supplied:
                    input_widget.setText(str(supplied[f_name]))
            else:
                input_widget = QLineEdit()
                input_widget.setPlaceholderText(mf.get("description", ""))
                if f_name in supplied:
                    input_widget.setText(str(supplied[f_name]))

            self.input_fields[f_name] = input_widget
            row.addWidget(input_widget)
            f_layout.addLayout(row)

        if missing:
            submit_row = QHBoxLayout()
            submit_row.addStretch()
            btn_submit = QPushButton("Xác nhận & Tiếp tục")
            btn_submit.setProperty("class", "ActionBtn")
            btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_submit.clicked.connect(lambda: self._on_form_submitted(op_name, supplied))
            submit_row.addWidget(btn_submit)
            f_layout.addLayout(submit_row)

        self.layout.addWidget(form_frame)

    def _on_candidate_chosen(self, op_name: str, candidate: Dict[str, Any], supplied: Dict[str, Any]) -> None:
        merged = dict(supplied)
        merged["place"] = candidate.get("name")
        merged["latitude"] = candidate.get("latitude")
        merged["longitude"] = candidate.get("longitude")
        merged["timezone"] = candidate.get("timezone")
        merged["selected_candidate"] = candidate.get("name")
        self.input_submitted.emit(op_name, merged)

    def _on_form_submitted(self, op_name: str, supplied: Dict[str, Any]) -> None:
        values = dict(supplied)
        for f_name, widget in self.input_fields.items():
            if isinstance(widget, QLineEdit):
                txt = widget.text().strip()
                if txt:
                    values[f_name] = txt
        self.input_submitted.emit(op_name, values)

    def _render_actions(self, data: Dict[str, Any]) -> None:
        actions = data.get("actions", [])
        if not actions:
            return

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        for act in actions:
            label = act.get("label", "Thao tác")
            btn = QPushButton(label)
            btn.setProperty("class", "ActionBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            if not self.is_latest:
                btn.setEnabled(False)
                btn.setToolTip("Nút này thuộc phiên bản trước; vui lòng thao tác trên kết quả mới nhất.")
            else:
                btn.clicked.connect(lambda _, a=act: self._on_action_clicked(a))

            btn_row.addWidget(btn)

        btn_row.addStretch()
        self.layout.addLayout(btn_row)

    def _on_action_clicked(self, act_dict: Dict[str, Any]) -> None:
        if not self.artifact:
            return

        target_rev = self.spec.revision
        op_name = act_dict.get("operation", "")
        params = act_dict.get("params", {})
        act_id = act_dict.get("id", f"act_{op_name}")

        # If action requires user input (e.g. edit_time)
        input_field = act_dict.get("input_field")
        user_inputs = {}
        if input_field == "time":
            # Quick inline prompt or default adjustment
            curr = act_dict.get("current_value", "12:00")
            # For demonstration / direct control, toggle or prompt
            # By default sends prompt or current params
            pass

        action_obj = ArtifactAction(
            id=act_id,
            label=act_dict.get("label", ""),
            target_artifact_id=self.spec.artifact_id,
            target_revision=target_rev,
            operation_name=op_name,
            params=params,
        )
        self.action_dispatched.emit(action_obj, user_inputs)

    def _render_details(self, data: Dict[str, Any]) -> None:
        title = data.get("title", "Chi tiết")
        content = data.get("content")
        t_headers = data.get("table_headers")
        t_rows = data.get("table_rows")

        container = QFrame()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 4, 0, 0)
        c_layout.setSpacing(4)

        btn_toggle = QPushButton(f"▸ {title}")
        btn_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #705C38;
                font-size: 11px;
                font-weight: 700;
                text-align: left;
                padding: 2px 0;
            }
            QPushButton:hover {
                color: #9E8352;
            }
        """)
        btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)

        content_widget = QWidget()
        cw_layout = QVBoxLayout(content_widget)
        cw_layout.setContentsMargins(4, 4, 4, 4)

        if content:
            browser = QTextBrowser()
            browser.setPlainText(str(content)[:1000])
            browser.setMaximumHeight(140)
            cw_layout.addWidget(browser)
        elif t_headers and t_rows:
            table = QTableWidget(len(t_rows[:12]), len(t_headers))
            table.setHorizontalHeaderLabels(t_headers)
            table.verticalHeader().setVisible(False)
            table.setStyleSheet("QTableWidget { background: #FFFFFF; font-size: 10.5px; border: 1px solid #ECE4D8; }")
            for r_idx, row in enumerate(t_rows[:12]):
                for c_idx, val in enumerate(row):
                    table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
            table.setMaximumHeight(160)
            cw_layout.addWidget(table)

        content_widget.hide()

        def _toggle():
            if content_widget.isVisible():
                content_widget.hide()
                btn_toggle.setText(f"▸ {title}")
            else:
                content_widget.show()
                btn_toggle.setText(f"▾ {title}")

        btn_toggle.clicked.connect(_toggle)
        c_layout.addWidget(btn_toggle)
        c_layout.addWidget(content_widget)
        self.layout.addWidget(container)
