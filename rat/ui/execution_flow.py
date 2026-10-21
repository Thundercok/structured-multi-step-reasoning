"""A visual view of public execution events and evidence; no model internals."""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from rat.engine.work_trace import TraceEntry
from rat.ui.workbench import WorkbenchStyle, WorkbenchTokens, workbench_button_style, workbench_text


STATUS_LABELS = {
    'proposed': 'Dự định', 'running': 'Đang chạy', 'found': 'Đã tìm thấy',
    'read': 'Đã đọc', 'verified_pass': 'Kiểm tra đạt', 'verified_fail': 'Chưa đạt',
    'unchecked': 'Chưa kiểm tra', 'waiting': 'Chờ bạn', 'error': 'Lỗi',
    'cancelled': 'Đã dừng', 'stopped': 'Đã dừng', 'done': 'Đã xong',
}

# Resolution is deliberately supplied by the scene's observed source map.
SourceLink = tuple[str, str]


class ExecutionFlowNode(QWidget):
    source_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.entry: Optional[TraceEntry] = None
        self.source_id = ''
        self.first = False
        self.last = False
        root = QHBoxLayout(self)
        root.setContentsMargins(28, 0, 0, 0)
        self.card = QFrame(self)
        self.card.setObjectName('ExecutionFlowNodeCard')
        root.addWidget(self.card)
        body = QVBoxLayout(self.card)
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(6)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.title = QLabel(self.card)
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self.title, 1)
        self.status = QLabel(self.card)
        header.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)
        self.detail = QLabel(self.card)
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        body.addWidget(self.detail)
        self.source = QPushButton(self.card)
        self.source.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.source.setMinimumWidth(0)
        self.source.setCursor(Qt.CursorShape.PointingHandCursor)
        self.source.clicked.connect(lambda: self.source_requested.emit(self.source_id))
        body.addWidget(self.source)

    def set_entry(self, entry: TraceEntry, source: Optional[SourceLink], *, first: bool, last: bool) -> None:
        self.entry, self.first, self.last = entry, first, last
        tokens = WorkbenchTokens.get()
        caution = entry.status in {'error', 'verified_fail'}
        color = tokens.error_hex if caution else tokens.accent_hex
        quiet = entry.status in {'proposed', 'unchecked', 'cancelled', 'stopped'}
        if quiet:
            color = tokens.muted_hex
        self.card.setStyleSheet(
            f'QFrame#ExecutionFlowNodeCard {{ background: {tokens.soft_hex}; '
            f'border: 1px {"dashed" if entry.status == "proposed" else "solid"} {tokens.line_hex}; '
            f'border-radius: {WorkbenchStyle.CARD_RADIUS}px; }}'
        )
        self.title.setStyleSheet(workbench_text(tokens.ink_hex, WorkbenchStyle.BODY, 600))
        self.status.setStyleSheet(workbench_text(color, WorkbenchStyle.CAPTION, 600))
        self.detail.setStyleSheet(workbench_text(tokens.muted_hex, WorkbenchStyle.META))
        self.title.setText(entry.title)
        self.status.setText(STATUS_LABELS.get(entry.status, 'Chưa kiểm tra'))
        self.detail.setText(entry.detail)
        self.detail.setVisible(bool(entry.detail))
        self.source_id = source[0] if source else ''
        self.source.setText(('↗ ' + source[1].replace('&', '&&')) if source else '')
        self.source.setToolTip(source[1] if source else '')
        self.source.setStyleSheet(workbench_button_style(tokens, quiet=True) + 'QPushButton { text-align: left; }')
        self.source.setVisible(source is not None)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.entry is None:
            return
        tokens = WorkbenchTokens.get()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(tokens.line, 1.5))
        y = 20.0
        p.drawLine(QPointF(12, y if self.first else 0), QPointF(12, y if self.last else self.height()))
        caution = self.entry.status in {'error', 'verified_fail'}
        color = tokens.error if caution else tokens.accent
        p.setPen(QPen(color, 1.5))
        p.setBrush(tokens.paper if self.entry.status in {'proposed', 'unchecked'} else color)
        p.drawEllipse(QPointF(12, y), 4.0, 4.0)
        p.end()


class ExecutionFlowWidget(QWidget):
    source_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.entries: list[TraceEntry] = []
        self.nodes: dict[tuple[int, str], ExecutionFlowNode] = {}
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 8, 0, 0)
        self.body.setSpacing(6)

    def set_entries(self, entries: Sequence[TraceEntry], resolve_source: Callable[[TraceEntry], Optional[SourceLink]]) -> None:
        self.entries = list(entries)
        wanted = {(e.number, e.stage) for e in entries}
        for key in list(self.nodes):
            if key not in wanted:
                node = self.nodes.pop(key)
                self.body.removeWidget(node)
                node.hide()
                node.deleteLater()
        for index, entry in enumerate(entries):
            key = entry.number, entry.stage
            node = self.nodes.get(key)
            if node is None:
                node = ExecutionFlowNode(self)
                node.source_requested.connect(self.source_requested.emit)
                self.nodes[key] = node
            self.body.insertWidget(index, node)
            node.set_entry(entry, resolve_source(entry), first=index == 0, last=index == len(entries)-1)
            node.show()
