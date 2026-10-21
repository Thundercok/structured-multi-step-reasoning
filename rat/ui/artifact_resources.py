"""Registered domain drawings; they do not own application or task lifecycles."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

RESOURCE_RENDERERS = {}


class WheelResource(QWidget):
    """Resize the drawing without losing its selected point or calculated data."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.compact = True
        self._fit_pending = False

    def set_compact(self, compact):
        self.compact = bool(compact)
        self._fit_wheel()

    def _fit_wheel(self):
        self._fit_pending = False
        if hasattr(self, 'canvas'):
            preferred = 280 if self.compact else 500
            diameter = max(180, min(self.width(), preferred)) if self.isVisible() else preferred
            if self.canvas.width() == diameter and self.minimumHeight() >= diameter:
                return
            self.canvas.setFixedSize(diameter, diameter)
            # The host must reserve the new drawing height before Qt lays out
            # the surrounding conversation; otherwise the label clips the wheel.
            self.setMinimumHeight(diameter + self.detail.sizeHint().height() + self.layout().spacing())
            self.layout().invalidate()
            self.layout().activate()
            self.updateGeometry()
            # Revisions are inserted into an already-visible panel. Invalidate
            # its ancestor layout items as well as the drawing's own layout.
            from PyQt6.QtWidgets import QScrollArea
            ancestor = self.parentWidget()
            while ancestor is not None and not isinstance(ancestor, QScrollArea):
                parent_layout = QWidget.layout(ancestor)
                if parent_layout is not None:
                    parent_layout.invalidate()
                    parent_layout.activate()
                ancestor.updateGeometry()
                ancestor = ancestor.parentWidget()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Wait until the parent finishes its layout pass before changing the
        # child's constraints; changes during that pass can leave cached sizes.
        if not self._fit_pending:
            self._fit_pending = True
            QTimer.singleShot(0, self._fit_wheel)

    def _apply_theme(self):
        from rat.ui.workbench import WorkbenchTokens, FONT_FAMILY
        tokens = WorkbenchTokens.get()
        if hasattr(self, 'detail'):
            self.detail.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY};")


def register_resource_renderer(name, renderer):
    RESOURCE_RENDERERS[name] = renderer


def chart_resource(data, parent=None):
    from rat.astrology.chart import NatalChart, point_map, degree_text
    from rat.ui.natal_chart import ChartCanvas
    chart = NatalChart.from_dict(data['value'])
    host = WheelResource(parent)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    canvas = ChartCanvas(host)
    canvas.setMinimumSize(180, 180)
    canvas.setMaximumSize(500, 500)
    canvas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    canvas.set_chart(chart)
    detail = QLabel('Chọn một thiên thể để xem tọa độ và nhà.')
    detail.setWordWrap(True)
    detail.setTextFormat(Qt.TextFormat.PlainText)
    def selected(point_id):
        point = point_map(chart).get(point_id)
        if point:
            detail.setText(f'{point.name} · {degree_text(point.longitude, seconds=True)}' +
                           (f' · Nhà {point.house}' if point.house else ''))
    canvas.point_selected.connect(selected)
    layout.addWidget(canvas, 0, Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(detail)
    host.canvas = canvas
    host.detail = detail
    host._fit_wheel()
    return host


register_resource_renderer('wheel', chart_resource)
