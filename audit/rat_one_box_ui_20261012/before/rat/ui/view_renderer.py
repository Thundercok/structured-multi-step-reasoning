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
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QGridLayout,
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
        self.input_types = {}
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
            lbl_title.setTextFormat(Qt.TextFormat.PlainText)
            lbl_title.setWordWrap(True)
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
            lbl_text.setTextFormat(Qt.TextFormat.PlainText)
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

        for row_items in rows:
            r_row = QHBoxLayout()
            r_row.setSpacing(8)
            for item in row_items:
                rl = QLabel(str(item))
                rl.setStyleSheet("color: #30363E; font-size: 11px;")
                rl.setTextFormat(Qt.TextFormat.PlainText)
                rl.setWordWrap(True)
                r_row.addWidget(rl, 1)
            t_layout.addLayout(r_row)

        self.layout.addWidget(table_frame)

    def _render_resource(self, data):
        from rat.ui.artifact_resources import RESOURCE_RENDERERS
        factory = RESOURCE_RENDERERS.get(data.get("resource"))
        if factory is None:
            raise ValueError("Hình yêu cầu chưa có bộ hiển thị đăng ký.")
        if self.artifact is None:
            raise ValueError("Hình chưa được gắn với kết quả thật.")
        bound = {**data, "value": self.artifact.payload[data["field"]]}
        resource = factory(bound, self)
        self._wheel_widget = getattr(resource, "canvas", None)
        self.layout.addWidget(resource)

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
            cand_label = QLabel("Chọn kết quả phù hợp:")
            cand_label.setStyleSheet("color: #705C38; font-size: 11px; font-weight: 700;")
            f_layout.addWidget(cand_label)

            c_flow = QVBoxLayout()
            c_flow.setSpacing(6)
            for index, c in enumerate(candidates):
                name = c.get("name", "")
                btn = QPushButton(name + (" · " + c.get("admin", c.get("country", "")) if c.get("admin") or c.get("country") else ""))
                btn.setProperty("class", "CandidateBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, idx=index: self._on_candidate_chosen(op_name, idx, supplied))
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
            if f_type == "choice":
                input_widget = QComboBox()
                input_widget.addItem("Chọn…", None)
                for choice in mf.get("choices", []):
                    input_widget.addItem(choice["label"], choice["value"])
            elif f_type == "boolean":
                input_widget = QCheckBox()
                input_widget.setChecked(supplied.get(f_name, mf.get("default", False)))
            elif f_type == "date":
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("Ngày/tháng/năm (vd: 15/06/2000)")
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

            input_widget.setObjectName("input-" + f_name)
            if f_type == "save_file":
                browse = QPushButton("Chọn nơi lưu…")
                def choose_path(_, edit=input_widget, field=mf):
                    path, _ = QFileDialog.getSaveFileName(self, "Lưu kết quả", edit.text(), field.get("filter", "All files (*)"))
                    if path:
                        edit.setText(path)
                browse.clicked.connect(choose_path)
                row.addWidget(browse)
            self.input_fields[f_name] = input_widget
            self.input_types[f_name] = f_type
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

    def draft_values(self):
        values = {}
        for name, widget in self.input_fields.items():
            if isinstance(widget, QLineEdit):
                if widget.text().strip():
                    text = widget.text().strip()
                    if self.input_types.get(name) == "number":
                        try:
                            values[name] = float(text)
                        except ValueError:
                            values[name] = text  # The operation reports validation failure and retains the draft.
                    else:
                        values[name] = text
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QComboBox) and widget.currentData() is not None:
                values[name] = widget.currentData()
        return values

    def restore_draft(self, values):
        for name, value in values.items():
            widget = self.input_fields.get(name)
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(widget.findData(value))

    def _on_candidate_chosen(self, op_name, index, supplied):
        self.input_submitted.emit(self.spec.artifact_id, {**self.draft_values(), "selected_candidate": index})

    def _on_form_submitted(self, op_name, supplied):
        self.input_submitted.emit(self.spec.artifact_id, self.draft_values())

    def _render_actions(self, data):
        items = data.get("actions", [])
        row = QGridLayout() if len(items) > 4 else QHBoxLayout()
        for index, item in enumerate(items):
            action = ArtifactAction.from_dict(item)
            button = QPushButton(action.label if len(action.label) <= 30 else action.label[:27] + "…")
            button.setToolTip(action.label)
            button.setProperty("class", "ActionBtn")
            button.setEnabled(self.is_latest)
            if isinstance(row, QGridLayout):
                row.addWidget(button, index // 2, index % 2)
            else:
                row.addWidget(button)
            if action.input_schema:
                editor = QWidget()
                layout = QHBoxLayout(editor)
                fields = {}
                for name, field in action.input_schema.get("properties", {}).items():
                    layout.addWidget(QLabel(field.get("title", name)))
                    edit = QLineEdit(str(field.get("default", "")))
                    edit.setObjectName("action-input-" + name)
                    fields[name] = edit
                    layout.addWidget(edit)
                submit = QPushButton("Áp dụng")
                submit.setObjectName("apply-" + action.id)
                submit.clicked.connect(lambda _, a=action, fs=fields: self.action_dispatched.emit(a, {k: w.text().strip() for k, w in fs.items()}))
                layout.addWidget(submit)
                editor.hide()
                button.clicked.connect(lambda _, e=editor: e.setVisible(e.isHidden()))
                self.layout.addWidget(editor)
            else:
                button.clicked.connect(lambda _, a=action: self.action_dispatched.emit(a, {}))
        if isinstance(row, QHBoxLayout):
            row.addStretch()
        self.layout.addLayout(row)

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
            browser.setPlainText(str(content))
            browser.setMaximumHeight(140)
            cw_layout.addWidget(browser)
        elif t_headers and t_rows:
            table = QTableWidget(len(t_rows), len(t_headers))
            table.setHorizontalHeaderLabels(t_headers)
            table.verticalHeader().setVisible(False)
            table.setStyleSheet("QTableWidget { background: #FFFFFF; font-size: 10.5px; border: 1px solid #ECE4D8; }")
            for r_idx, row in enumerate(t_rows):
                for c_idx, val in enumerate(row):
                    table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
            from PyQt6.QtWidgets import QAbstractItemView, QHeaderView
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setMaximumHeight(220)
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
