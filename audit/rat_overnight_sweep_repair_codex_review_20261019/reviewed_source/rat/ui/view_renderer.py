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
    QApplication,
    QMenu,
    QDateEdit,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLayout,
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

from rat.ui.surface_layout import Disclosure, ResponsiveFields
from rat.ui.experience import debug_ui_enabled
from rat.ui.workbench import WorkbenchTokens

from rat.kernel.contracts import Artifact, ArtifactAction, InputRequest
from rat.kernel.view_spec import ViewBlock, ViewSpec


def get_card_style(dark: Optional[bool] = None) -> str:
    tokens = WorkbenchTokens.get(dark=dark)
    return f"""
    QFrame#ArtifactCard {{ background: transparent; border: none; padding: 0; }}
    QLabel#CardTitle {{ color: {tokens.ink_hex}; font-size: 14px; font-weight: 600; background: transparent; border: none; }}
    QLabel#CardText {{ color: {tokens.muted_hex}; font-size: 12px; background: transparent; border: none; }}
    QLabel#CardBadge {{ color: {tokens.muted_hex}; font-size: 10px; background: transparent; border: none; }}
    QLabel#StaleBadge {{ color: {tokens.error_hex}; font-size: 10px; background: transparent; border: none; }}
    QPushButton.ActionBtn, QPushButton.CandidateBtn {{
        background: {tokens.soft_hex}; border: 1px solid {tokens.line_hex}; border-radius: 7px; padding: 7px 10px;
        font-size: 12px; color: {tokens.ink_hex}; text-align: left;
    }}
    QPushButton.ActionBtn:hover, QPushButton.CandidateBtn:hover {{ background: {tokens.line_hex}; color: {tokens.ink_hex}; }}
    QPushButton.ActionBtn:disabled {{ color: {tokens.muted_hex}; background: {tokens.soft_hex}; border-color: transparent; }}
    QPushButton::menu-indicator {{ image: none; width: 0; }}
    QLineEdit, QComboBox {{ background: {tokens.paper_hex}; border: 1px solid {tokens.line_hex}; border-radius: 7px; padding: 7px 9px; font-size: 12px; color: {tokens.ink_hex}; }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {tokens.focus_hex}; background: {tokens.paper_hex}; }}
    QTableWidget {{
        background: transparent;
        border: none;
        font-size: 12px;
        gridline-color: {tokens.line_hex};
        color: {tokens.ink_hex};
        selection-background-color: {tokens.soft_hex};
        selection-color: {tokens.accent_hex};
    }}
    QHeaderView::section {{
        background: {tokens.soft_hex};
        border: none;
        color: {tokens.muted_hex};
        padding: 5px;
        font-size: 11px;
        font-weight: 600;
    }}
    QTextBrowser {{
        background: transparent;
        border: none;
        font-size: 12px;
        color: {tokens.ink_hex};
    }}
    """


CARD_STYLE = get_card_style(dark=False)


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
        self.debug_ui = debug_ui_enabled()
        self.artifact = artifact
        self.is_latest = is_latest
        self.input_fields: Dict[str, QWidget] = {}
        self.input_types = {}
        self.disclosures = {}
        self.action_editors = {}
        self._resources = []
        self._compact = True
        self._wheel_widget: Optional[QWidget] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("ArtifactCard")
        self.setStyleSheet(get_card_style())
        self.layout = QVBoxLayout(self)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.layout.setContentsMargins(0, 3, 0, 3)
        self.layout.setSpacing(12)

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
            if self.debug_ui or (
                data.get("operation_name") == "open_application"
                and data.get("candidate_choices")
            ):
                self._render_input_form(data)
        elif b_type == "actions":
            if self.debug_ui:
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
            header_row.addWidget(lbl_title, 1)

        if not self.is_latest:
            stale_badge = QLabel("Phiên bản cũ")
            stale_badge.setObjectName("StaleBadge")
            stale_badge.setToolTip("Kết quả này đã được cập nhật ở phiên bản mới hơn.")
            header_row.addWidget(stale_badge)
        elif "badge" in data:
            badge = QLabel(data["badge"])
            badge.setObjectName("CardBadge")
            header_row.addWidget(badge)

        if header_row.count():
            self.layout.addLayout(header_row)

        text = data.get("text", "")
        if text:
            lbl_text = QLabel(text)
            lbl_text.setTextFormat(Qt.TextFormat.PlainText)
            lbl_text.setObjectName("CardText")
            lbl_text.setWordWrap(True)
            lbl_text.setMinimumWidth(0)
            lbl_text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.layout.addWidget(lbl_text)

    def _render_table(self, data: Dict[str, Any]) -> None:
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        if not rows:
            return

        tokens = WorkbenchTokens.get()
        table_frame = QFrame()
        table_frame.setObjectName("ResultRows")
        table_frame.setStyleSheet("""
            QFrame#ResultRows { background: transparent; border: none; }
            QLabel { background: transparent; border: none; }
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
                hl.setTextFormat(Qt.TextFormat.PlainText)
                hl.setProperty("role", "table_header")
                hl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 10px; font-weight: 700; background: transparent; border: none;")
                h_row.addWidget(hl, 1)
            t_layout.addLayout(h_row)

        for row_items in rows:
            r_row = QHBoxLayout()
            r_row.setSpacing(8)
            for item in row_items:
                rl = QLabel(str(item))
                rl.setProperty("role", "table_cell")
                rl.setStyleSheet(f"color: {tokens.ink_hex}; font-size: 11px; background: transparent; border: none;")
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
        self._resources.append(resource)
        self.layout.addWidget(resource)

    def _render_input_form(self, data: Dict[str, Any]) -> None:
        op_name = data.get("operation_name", "")
        missing = data.get("missing_fields", [])
        candidates = data.get("candidate_choices")
        supplied = data.get("supplied_inputs", {})

        form_frame = QFrame()
        form_frame.setObjectName('InlineInputs')
        form_frame.setStyleSheet('QFrame#InlineInputs { background: transparent; border: none; }')
        f_layout = QVBoxLayout(form_frame)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(6)

        # Candidate choices (e.g. ambiguous cities)
        if candidates:
            tokens = WorkbenchTokens.get()
            cand_label = QLabel("Chọn kết quả phù hợp:")
            cand_label.setProperty("role", "candidate_prompt")
            cand_label.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
            f_layout.addWidget(cand_label)

            c_flow = QVBoxLayout()
            c_flow.setSpacing(6)
            all_paths = [str(c.get("path") or "") for c in candidates if c.get("path")]
            has_paths = len(all_paths) > 1

            for index, c in enumerate(candidates):
                name = c.get("name", "")
                p = str(c.get("path") or "")

                full_tooltip_parts = [name]
                if c.get("admin") or c.get("country"):
                    full_tooltip_parts.append(c.get("admin", c.get("country", "")))
                if p:
                    full_tooltip_parts.append(p)
                if c.get("bundle_id"):
                    full_tooltip_parts.append(str(c.get("bundle_id")))
                if c.get("version"):
                    full_tooltip_parts.append(f"v{c.get('version')}")
                full_tooltip = " · ".join(part for part in full_tooltip_parts if part)

                if p and has_paths:
                    import os
                    from pathlib import Path
                    try:
                        common = os.path.commonpath(all_paths)
                        rel = os.path.relpath(p, common)
                        parent_folder = Path(p).parent.name
                        diff_label = parent_folder if parent_folder else rel
                    except Exception:
                        diff_label = Path(p).parent.name
                    label_parts = [f"{diff_label} · {name}"]
                elif c.get("admin") or c.get("country"):
                    label_parts = [f"{name} ({c.get('admin', c.get('country', ''))})"]
                else:
                    label_parts = [name]

                if c.get("version"):
                    label_parts.append(f"v{c.get('version')}")

                btn_text = " · ".join(label_parts)
                btn = QPushButton(btn_text)
                btn.setObjectName("CandidateBtn")
                btn.setProperty("class", "CandidateBtn")
                btn.setToolTip(full_tooltip)
                btn.setMinimumWidth(0)
                btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, idx=index: self._on_candidate_chosen(op_name, idx, supplied))
                c_flow.addWidget(btn)
            c_flow.addStretch()
            f_layout.addLayout(c_flow)

        fields_layout = ResponsiveFields()
        f_layout.addWidget(fields_layout)
        # Missing input fields
        for mf in missing:
            f_name = mf.get("name", "")
            f_label = mf.get("label", f_name)
            f_type = mf.get("type", "string")

            field_host = QWidget()
            row = QVBoxLayout(field_host)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            lbl = QLabel(f_label)
            lbl.setWordWrap(True)
            lbl.setProperty("role", "input_label")
            tokens = WorkbenchTokens.get()
            lbl.setStyleSheet(f'color: {tokens.muted_hex}; font-size: 11px; background: transparent; border: none;')
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
            input_widget.setAccessibleName(f_label)
            input_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            lbl.setBuddy(input_widget)
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
            fields_layout.add_field(field_host)

        if missing:
            submit_row = QHBoxLayout()
            submit_row.addStretch()
            btn_submit = QPushButton("Tiếp tục →")
            btn_submit.setProperty("class", "ActionBtn")
            btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_submit.clicked.connect(lambda: self._on_form_submitted(op_name, supplied))
            submit_row.addWidget(btn_submit)
            f_layout.addLayout(submit_row)

        self.layout.addWidget(form_frame)

    def _notify_layout(self):
        window = self.window()
        if hasattr(window, '_schedule_surface_fit'):
            window._schedule_surface_fit()

    def set_compact(self, compact):
        self._compact = bool(compact)
        for resource in self._resources:
            if hasattr(resource, 'set_compact'):
                resource.set_compact(compact)

    def view_state(self):
        edits = {}
        for name, edit in [(w.objectName(), w) for w in self.findChildren(QLineEdit)]:
            edits[name] = (edit.text(), edit.selectionStart(), len(edit.selectedText()), edit.cursorPosition())
        focus = QApplication.focusWidget()
        return dict(draft=self.draft_values(), edits=edits,
            focus=focus.objectName() if focus and self.isAncestorOf(focus) else None,
            details=[name for name, item in self.disclosures.items() if item.opened],
            editors=[name for name, (widget, fields) in self.action_editors.items() if not widget.isHidden()],
            selected=getattr(self._wheel_widget, 'selected', None))

    def restore_view_state(self, state):
        self.restore_draft(state.get('draft', {}))
        for name, values in state.get('edits', {}).items():
            edit = self.findChild(QLineEdit, name)
            if edit:
                text, start, length, caret = values
                edit.setText(text)
                edit.setSelection(start, length) if start >= 0 else edit.setCursorPosition(caret)
        if 'details' in state:
            opened_names = set(state.get('details', []))
            for name, item in self.disclosures.items():
                item.set_open(name in opened_names, animate=False)
        else:
            for name in state.get('details', []):
                if name in self.disclosures:
                    self.disclosures[name].set_open(True, animate=False)
        for name in state.get('editors', []):
            if name in self.action_editors:
                self.action_editors[name][0].show()
        if state.get('selected') and self._wheel_widget:
            self._wheel_widget.select(state['selected'])
        if state.get('focus'):
            edit = self.findChild(QWidget, state['focus'])
            if edit:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, edit.setFocus)

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
        row = QHBoxLayout()
        row.setSpacing(7)
        secondary = []
        for item in data.get('actions', []):
            action = ArtifactAction.from_dict(item)
            if not action.input_schema:
                secondary.append(action)
                continue
            button = QPushButton(action.label)
            button.setObjectName('action-' + action.id)
            button.setProperty('class', 'ActionBtn')
            button.setEnabled(self.is_latest)
            button.setToolTip(action.label)
            row.addWidget(button)
            editor = QWidget()
            layout = QHBoxLayout(editor)
            layout.setContentsMargins(0, 0, 0, 0)
            fields = {}
            for name, field in action.input_schema.get('properties', {}).items():
                edit = QLineEdit(str(field.get('default', '')))
                edit.setObjectName('action-input-' + name)
                edit.setAccessibleName(field.get('title', name))
                edit.setPlaceholderText(field.get('title', name))
                fields[name] = edit
                layout.addWidget(edit)
            submit = QPushButton('Áp dụng')
            submit.setObjectName('apply-' + action.id)
            submit.setProperty('class', 'ActionBtn')
            submit.clicked.connect(lambda _, a=action, fs=fields: self.action_dispatched.emit(a, {k: w.text().strip() for k, w in fs.items()}))
            cancel = QPushButton('Hủy')
            cancel.setProperty('class', 'ActionBtn')
            def close_editor(_, e=editor, b=button, fs=fields, a=action):
                for name, edit in fs.items():
                    edit.setText(str(a.input_schema['properties'][name].get('default', '')))
                e.hide()
                b.setFocus()
            cancel.clicked.connect(close_editor)
            layout.addWidget(submit)
            layout.addWidget(cancel)
            editor.hide()
            def toggle(_, e=editor, fs=fields):
                e.setVisible(e.isHidden())
                if e.isVisible() and fs:
                    next(iter(fs.values())).setFocus()
                    next(iter(fs.values())).selectAll()
                self._notify_layout()
            button.clicked.connect(toggle)
            self.action_editors[action.id] = (editor, fields)
            self.layout.addWidget(editor)
        if secondary:
            button = QPushButton('Thao tác ⋯')
            button.setProperty('class', 'ActionBtn')
            button.setEnabled(self.is_latest)
            menu = QMenu(button)
            for action in secondary:
                menu.addAction(action.label, lambda checked=False, a=action: self.action_dispatched.emit(a, {}))
            button.setMenu(menu)
            row.addWidget(button)
        row.addStretch()
        self.layout.addLayout(row)

    def _render_details(self, data):
        title = data.get('title', 'Chi tiết')
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 2, 0, 3)
        tokens = WorkbenchTokens.get()
        if data.get('content'):
            browser = QTextBrowser()
            browser.setPlainText(str(data['content']))
            browser.setStyleSheet(f'QTextBrowser {{ background: transparent; border: none; font-size: 12px; color: {tokens.ink_hex}; }}')
            browser.setMaximumHeight(220)
            layout.addWidget(browser)
        elif data.get('table_headers') and data.get('table_rows'):
            from PyQt6.QtWidgets import QAbstractItemView, QHeaderView
            headers, rows = data['table_headers'], data['table_rows']
            table = QTableWidget(len(rows), len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().hide()
            table.setStyleSheet(f"""
                QTableWidget {{
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    gridline-color: {tokens.line_hex};
                    color: {tokens.ink_hex};
                    selection-background-color: {tokens.soft_hex};
                    selection-color: {tokens.accent_hex};
                }}
                QHeaderView::section {{
                    background: {tokens.soft_hex};
                    border: none;
                    color: {tokens.muted_hex};
                    padding: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }}
            """)
            for r, values in enumerate(rows):
                for c, value in enumerate(values):
                    table.setItem(r, c, QTableWidgetItem(str(value)))
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setMaximumHeight(240)
            table.setMinimumHeight(min(220, 35 + len(rows) * 30))
            layout.addWidget(table)
        disclosure = Disclosure(title, body)
        disclosure.changed.connect(self._notify_layout)
        self.disclosures[title] = disclosure
        if not self.debug_ui:
            disclosure.set_open(True, animate=False)
            disclosure.button.hide()
        self.layout.addWidget(disclosure)

    def _apply_theme(self) -> None:
        tokens = WorkbenchTokens.get()
        self.setStyleSheet(get_card_style())
        for hl in self.findChildren(QLabel):
            role = hl.property("role")
            if role == "table_header":
                hl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 10px; font-weight: 700; background: transparent; border: none;")
            elif role == "table_cell":
                hl.setStyleSheet(f"color: {tokens.ink_hex}; font-size: 11px; background: transparent; border: none;")
            elif role == "input_label":
                hl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 11px; background: transparent; border: none;")
            elif role == "candidate_prompt":
                hl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        for table in self.findChildren(QTableWidget):
            table.setStyleSheet(f"""
                QTableWidget {{
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    gridline-color: {tokens.line_hex};
                    color: {tokens.ink_hex};
                    selection-background-color: {tokens.soft_hex};
                    selection-color: {tokens.accent_hex};
                }}
                QHeaderView::section {{
                    background: {tokens.soft_hex};
                    border: none;
                    color: {tokens.muted_hex};
                    padding: 5px;
                    font-size: 11px;
                    font-weight: 600;
                }}
            """)
        for browser in self.findChildren(QTextBrowser):
            browser.setStyleSheet(f"QTextBrowser {{ background: transparent; border: none; font-size: 12px; color: {tokens.ink_hex}; }}")
        for edit in self.findChildren(QLineEdit):
            edit.setStyleSheet(f"QLineEdit {{ background: {tokens.paper_hex}; border: 1px solid {tokens.line_hex}; border-radius: 7px; padding: 7px 9px; font-size: 12px; color: {tokens.ink_hex}; }}")
        for combo in self.findChildren(QComboBox):
            combo.setStyleSheet(f"QComboBox {{ background: {tokens.paper_hex}; border: 1px solid {tokens.line_hex}; border-radius: 7px; padding: 7px 9px; font-size: 12px; color: {tokens.ink_hex}; }}")
        for res in self._resources:
            if hasattr(res, "_apply_theme"):
                res._apply_theme()
