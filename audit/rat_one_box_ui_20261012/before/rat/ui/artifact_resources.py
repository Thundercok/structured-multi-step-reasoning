"""Registered domain drawings; they do not own application or task lifecycles."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

RESOURCE_RENDERERS = {}


def register_resource_renderer(name, renderer):
    RESOURCE_RENDERERS[name] = renderer


def chart_resource(data, parent=None):
    from rat.astrology.chart import NatalChart, point_map, degree_text
    from rat.ui.natal_chart import ChartCanvas
    chart = NatalChart.from_dict(data['value'])
    host = QWidget(parent)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    canvas = ChartCanvas(host)
    canvas.setMinimumSize(280, 280)
    canvas.setMaximumSize(420, 420)
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
    return host


register_resource_renderer('wheel', chart_resource)
