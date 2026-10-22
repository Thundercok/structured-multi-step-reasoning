#!/usr/bin/env python3
"""Isolated Qt Quick UI feasibility preview. Uses fixtures and never starts RAT."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Validate states offscreen and exit")
    parser.add_argument("--capture-dir", type=Path, help="Save offscreen screenshots of fixture states")
    parser.add_argument("--scene", choices=("idle", "unread", "folded", "startup", "receiving", "working", "result"), default="idle")
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    if args.smoke or args.capture_dir:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    from PyQt6.QtCore import QT_VERSION_STR, QCoreApplication, QObject, QPoint, QPointF, QUrl, Qt, qInstallMessageHandler
    from PyQt6.QtGui import QFont, QGuiApplication
    from PyQt6.QtQuick import QQuickItem, QQuickView
    from PyQt6.QtTest import QTest

    project = Path(__file__).resolve().parents[1]
    messages: list[str] = []

    def log_message(kind, context, message):
        messages.append(message)
        print(message, file=sys.stderr)

    qInstallMessageHandler(log_message)
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("RAT Quick Preview")
    if sys.platform == "darwin":
        app.setFont(QFont("Helvetica Neue", 13))
    view = QQuickView()
    view.setTitle("RAT · Qt Quick feasibility preview · fixtures")
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setInitialProperties({
        "darkMode": args.dark or app.styleHints().colorScheme() == Qt.ColorScheme.Dark,
        "mascotSource": QUrl.fromLocalFile(str(project / "rat/assets/rat_mascot_cutout.png")),
        "previewScene": args.scene,
        "reduceMotion": bool(args.smoke),
    })
    view.setSource(QUrl.fromLocalFile(str(project / "prototypes/rat_quick/PaperDesk.qml")))
    if view.status() != QQuickView.Status.Ready:
        print(json.dumps({"ready": False, "qml_errors": [e.toString() for e in view.errors()]}))
        return 1
    root = view.rootObject()
    root.copyRequested.connect(QGuiApplication.clipboard().setText)
    view.resize(640, 640)
    view.show()
    if not (args.smoke or args.capture_dir):
        return app.exec()

    checked: list[dict] = []
    captures = args.capture_dir.resolve() if args.capture_dir else None
    if captures:
        captures.mkdir(parents=True, exist_ok=True)

    def settle():
        QCoreApplication.processEvents()
        QTest.qWait(100)

    def require(condition: bool, detail: str):
        if not condition:
            raise AssertionError(detail)

    def click_control(name: str):
        item = root.findChild(QQuickItem, name)
        require(item is not None and item.isVisible(), f"{name}: missing/hidden control")
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(round(point.x()), round(point.y())))
        settle()

    try:
        for width in (640, 520):
            view.resize(width, 640)
            for scene in ("idle", "unread", "folded", "startup", "receiving", "working", "result"):
                root.setProperty("previewScene", scene)
                root.applyScene(scene)
                settle()
                composer = root.findChild(QObject, "composer")
                result = root.findChild(QObject, "resultPaper")
                notice = root.findChild(QObject, "notice")
                editor = root.findChild(QObject, "draftEditor")
                require(bool(root.property("noticeVisible")) == (scene == "unread"), f"{scene}: unread flag")
                require(bool(result.property("visible")) == (scene in ("working", "result")), f"{scene}: expanded result")
                require(float(result.property("y")) >= 70 or not result.property("visible"), f"{scene}: paper overlaps preview controls")
                require(not root.property("animationsRunning"), f"{scene}: reduced-motion animation")
                require(float(composer.property("x")) >= 0, "composer left edge")
                require(float(composer.property("width")) < width, "composer width")
                anchor = float(composer.property("y")) + float(composer.property("height"))
                checked.append({"width": width, "scene": scene, "composer_bottom": anchor})
                if captures:
                    require(view.grabWindow().save(str(captures / f"quick-{scene}-{width}.png")), f"{scene}: screenshot")
            anchors = [m["composer_bottom"] for m in checked if m["width"] == width]
            require(max(anchors) - min(anchors) < 0.5, f"{width}: composer moved")

        root.applyScene("unread")
        settle()
        click_control("notice")
        require(root.property("expanded") and not root.property("unread"), "read must acknowledge notice")
        click_control("foldButton")
        require(not root.property("noticeVisible"), "fold must stay quiet after reading")
        root.applyScene("idle")
        editor = root.findChild(QObject, "draftEditor")
        draft = "Học kỳ hè thì sao?\nKiểm tra điều kiện tiên quyết.\nVà lịch học nữa."
        editor.setProperty("text", draft)
        settle()
        root.submitDraft()
        require(root.property("phase") == "receiving", "submit must enter receiving")
        settle()
        click_control("sendButton")
        require(root.property("phase") == "idle" and editor.property("text") == draft, "stop must preserve draft")
        editor.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Return)
        require(root.property("phase") == "receiving", "Enter must submit draft")
        QTest.keyClick(view, Qt.Key.Key_Return)
        require(root.property("phase") == "receiving", "Enter must not stop a request")
        root.stopRequest()
        editor.setProperty("text", "")
        root.setProperty("reduceMotion", False)
        editor.setProperty("text", draft)
        QTest.qWait(240)
        require(not root.property("animationsRunning"), "resize animation must settle")
        root.setProperty("reduceMotion", True)
        root.applyScene("working")
        settle()
        click_control("trailMode")
        require(root.property("compactTrail"), "trail button must select compact mode")
        compact_height = float(root.findChild(QObject, "resultPaper").property("height"))
        click_control("trailMode")
        require(not root.property("compactTrail"), "trail button must restore visual mode")
        require(float(root.findChild(QObject, "resultPaper").property("height")) > compact_height, "visual trail must expand")
        root.applyScene("result")
        root.setProperty("sourceOpen", True)
        root.setProperty("logOpen", True)
        settle()
        root.setProperty("darkMode", True)
        root.applyScene("unread")
        editor.setProperty("text", "")
        settle()
        if captures:
            require(view.grabWindow().save(str(captures / "quick-unread-dark.png")), "dark screenshot")
        require(not messages, "Qt emitted warnings/errors: " + "; ".join(messages))
        report = {"ready": True, "qt": QT_VERSION_STR, "rendering": "offscreen software; not a performance benchmark", "fixture_states": len(checked), "notice_acknowledged": True, "draft_preserved": True, "keyboard_submit": True, "finite_resize_motion": True, "warnings": messages, "geometry": checked}
        if captures:
            (captures / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    finally:
        view.close()
        QCoreApplication.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
