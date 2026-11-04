"""A press sinks the button, the click still lands, and reduced motion keeps it still."""
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import pytest
from PyQt6.QtCore import QPoint, QPointF, QUrl, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest

app = QGuiApplication.instance() or QGuiApplication([])
QUICK_DIR = Path(__file__).resolve().parents[1] / 'rat' / 'ui' / 'quick'
HOST = '''
import QtQuick
import "%s"
Item {
    id: desk
    width: 300; height: 200
    property bool reduceMotion: %s
    property color accent: "#4c6b3c"; property color accentText: "white"
    property color ink: "black"; property color muted: "gray"; property color edge: "#ccc"
    property color selectedEdge: "#999"; property color selectedSurface: "#eee"
    property color hoverSurface: "#f4f4f4"; property color utilitySurface: "#fafafa"
    property int clicks: 0
    QuietButton { objectName: "labelled"; x: 20; y: 20; text: "Mở"; onClicked: desk.clicks++ }
    QuietButton { objectName: "iconOnly"; x: 20; y: 80; iconName: "close"; onClicked: desk.clicks++ }
    QuietButton { objectName: "plain"; x: 20; y: 130; plain: true; text: "Chữ"; onClicked: desk.clicks++ }
}
'''


@pytest.fixture
def host_view(tmp_path):
    views = []

    def build(reduce_motion):
        path = tmp_path / f'host_{len(views)}.qml'
        path.write_text(HOST % (QUICK_DIR.as_uri(), 'true' if reduce_motion else 'false'), encoding='utf-8')
        view = QQuickView()
        view.setSource(QUrl.fromLocalFile(str(path)))
        assert view.status() == QQuickView.Status.Ready, view.errors()
        view.show()
        views.append(view)
        return view

    yield build
    for view in views:
        view.close()
        view.deleteLater()
    QGuiApplication.processEvents()


def _center(button):
    point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
    return QPoint(int(point.x()), int(point.y()))


def _spin(ms):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        QGuiApplication.processEvents()
        time.sleep(0.002)


@pytest.mark.parametrize('name, depth', [('labelled', 2), ('iconOnly', 1), ('plain', 1)])
def test_press_sinks_and_click_still_lands(host_view, name, depth):
    view = host_view(reduce_motion=False)
    button = view.rootObject().findChild(QQuickItem, name)
    assert button.property('pressDepth') == 0
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _center(button))
    assert button.property('pressDepth') == depth
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _center(button))
    assert button.property('pressDepth') == 0
    assert view.rootObject().property('clicks') == 1


def test_action_does_not_wait_for_the_animation(host_view):
    view = host_view(reduce_motion=False)
    button = view.rootObject().findChild(QQuickItem, 'labelled')
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _center(button))
    assert view.rootObject().property('clicks') == 1


def test_reduced_motion_keeps_the_button_still(host_view):
    view = host_view(reduce_motion=True)
    button = view.rootObject().findChild(QQuickItem, 'labelled')
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _center(button))
    _spin(100)
    assert button.property('pressDepth') == 0
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _center(button))
    assert view.rootObject().property('clicks') == 1


def test_press_on_the_top_edge_still_clicks(host_view):
    """The face sinks away from the pointer, but the button must keep the press."""
    view = host_view(reduce_motion=False)
    button = view.rootObject().findChild(QQuickItem, 'labelled')
    top = button.mapToScene(QPointF(button.width() / 2, 0))
    edge = QPoint(int(top.x()), int(top.y()))
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, edge)
    _spin(100)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, edge)
    assert view.rootObject().property('clicks') == 1
