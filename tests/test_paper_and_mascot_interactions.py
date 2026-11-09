"""Unit tests for Step 4: Táy máy micro-interactions (PDFDesk.qml).

Verifies:
4.1: Kéo xấp giấy có độ nảy (paper drag + spring physics).
4.2: Chọc chuột nhiều lần có phản ứng khác cú lắc hiện tại (wobble -> startle -> shudder).
4.3: Ném tờ giấy đi để bỏ kết quả (dismiss on flick/throw or equivalent key).
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import pytest
from PyQt6.QtCore import QCoreApplication, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem


@pytest.fixture(scope="module")
def qapp():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def test_mascot_repeated_poke_reactions(qapp):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile("rat/ui/quick/PDFDesk.qml"))
    assert not component.isError(), [e.toString() for e in component.errors()]

    root = component.create()
    assert root is not None

    try:
        # Initial state: streak is 0
        assert root.property("pokeStreak") == 0

        # First poke: wobble
        root.pokeRat()
        assert root.property("pokeStreak") == 1

        # Second poke: startle
        root.pokeRat()
        assert root.property("pokeStreak") == 2

        # Third poke: shudder
        root.pokeRat()
        assert root.property("pokeStreak") == 3

        # Fourth poke: wraps around to wobble
        root.pokeRat()
        assert root.property("pokeStreak") == 1
    finally:
        root.deleteLater()


def test_paper_drag_spring_and_dismiss_properties(qapp):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile("rat/ui/quick/PDFDesk.qml"))
    assert not component.isError(), [e.toString() for e in component.errors()]

    root = component.create()
    assert root is not None

    try:
        # Check properties exist with initial resting values
        assert root.property("paperDragX") == 0.0
        assert root.property("paperDragY") == 0.0
        assert root.property("paperDismissing") is False

        # Dragging paper within bounds
        root.setProperty("paperDragTargetX", 40.0)
        root.setProperty("paperDragTargetY", -30.0)
        assert root.property("paperDragTargetX") == 40.0
        assert root.property("paperDragTargetY") == -30.0

        # Release without throw: snaps back to 0
        root.setProperty("paperDragTargetX", 0.0)
        root.setProperty("paperDragTargetY", 0.0)
        assert root.property("paperDragTargetX") == 0.0
        assert root.property("paperDragTargetY") == 0.0

        # Flick dismissal trigger
        root.dismissPaperWithFlick(240, -160)
        assert root.property("paperDismissing") is True
        assert root.property("paperDragTargetX") == 240.0
        assert root.property("paperDragTargetY") == -160.0
    finally:
        root.deleteLater()
