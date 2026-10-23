"""RAT's unified Qt Quick Desk for AI reasoning and explicitly selected PDFs."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import os
import sys

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def bind_desk_window(view):
    """Fit the paper surface upwards, retaining the composer's screen anchor."""
    from PyQt6.QtCore import QTimer

    root = view.rootObject()
    timer = QTimer(view)
    timer.setSingleShot(True)

    def fit_content():
        screen = view.screen().availableGeometry()
        wanted = min(round(root.property("preferredWindowHeight")), screen.height() - 32)
        bottom = view.y() + view.height()
        y = max(screen.top() + 16, min(bottom - wanted, screen.bottom() - wanted - 16))
        view.setGeometry(view.x(), y, view.width(), wanted)

    timer.timeout.connect(fit_content)
    root.preferredWindowHeightChanged.connect(lambda: timer.start(0))
    timer.start(0)
    return timer


def bind_desk_close(view, controller):
    """Hide promptly, then close once native workers have actually finished."""
    from PyQt6.QtCore import QCoreApplication, QTimer

    timer = QTimer(view)
    timer.setInterval(50)

    def finish_close():
        if controller.close():
            timer.stop()
            view.close()
            QCoreApplication.quit()

    def request_close():
        if controller.snapshot["busy"]:
            controller.cancel()
        if controller.close():
            view.close()
        else:
            view.hide()
            timer.start()

    timer.timeout.connect(finish_close)
    view.rootObject().closeRequested.connect(request_close)
    return timer


def main(
    argv=None,
    *,
    reasoning_engine=None,
    allow_synthetic_policy=False,
    assistant_runtime=None,
    conversation=None,
):
    parser = argparse.ArgumentParser(description="RAT — macOS AI Assistant & PDF Desk")
    parser.add_argument("--document", type=Path, help="Open one explicitly selected PDF")
    parser.add_argument("document_pos", nargs="?", type=Path, help="Optional document path")
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument("--local-assistant-model", help="Installed Ollama model for the assistant in this run")
    parser.add_argument("--discover-tools", action="store_true", help="Start with core document tools; discover other operations as needed")
    args = parser.parse_args(argv)
    if assistant_runtime is not None and (args.local_assistant_model or args.discover_tools):
        parser.error("Assistant CLI options cannot override an injected assistant_runtime")
    if args.local_assistant_model or args.discover_tools:
        from rat.engine.assistant_runtime import AssistantRuntime
        from rat.engine.slm import SLMEngine
        assistant_runtime = AssistantRuntime(
            model_client=SLMEngine(model=args.local_assistant_model) if args.local_assistant_model else None,
            discover_tools=args.discover_tools,
        )
    doc_target = args.document or args.document_pos
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    from PyQt6.QtCore import QCoreApplication, QEvent, QTimer, QUrl, Qt
    from PyQt6.QtGui import QFont, QGuiApplication
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtQuick import QQuickView, QQuickWindow
    from rat.ui.icon_provider import RatIconProvider
    from rat.ui.quick_pdf_controller import QuickPDFController

    app = QApplication.instance() or QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setApplicationName("RAT")
    if sys.platform == "darwin":
        app.setFont(QFont("Helvetica Neue", 13))

    eng = reasoning_engine or (app.property("ratReasoningEngine") if hasattr(app, "property") else None)
    allow_synth = allow_synthetic_policy or (app.property("ratAllowSyntheticPolicy") is True if hasattr(app, "property") else False)

    controller = QuickPDFController(
        assistant_runtime=assistant_runtime,
        conversation=conversation,
        reasoning_engine=eng,
        allow_synthetic_policy=allow_synth,
    )
    controller.copyReady.connect(app.clipboard().setText)
    project = Path(__file__).resolve().parents[2]
    QQuickWindow.setDefaultAlphaBuffer(True)
    view = QQuickView()
    RatIconProvider.register(view.engine(), "icon")
    surface_format = view.format()
    surface_format.setAlphaBufferSize(8)
    view.setFormat(surface_format)
    view.setTitle("RAT · Trợ lý thông minh & PDF")
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setMinimumWidth(520)
    view.setMinimumHeight(200)
    view.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    view.setColor(Qt.GlobalColor.transparent)
    available = view.screen().availableGeometry()
    view.setInitialProperties({
        "liveController": controller,
        "darkMode": args.dark or app.styleHints().colorScheme() == Qt.ColorScheme.Dark,
        "reduceMotion": args.reduced_motion,
        "maxPaperHeight": max(220, min(460, available.height() - 280)),
        "mascotSource": QUrl.fromLocalFile(str(project / "rat/assets/rat_mascot_cutout.png")),
    })
    view.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "quick/PDFDesk.qml")))
    if view.status() != QQuickView.Status.Ready:
        for error in view.errors():
            print(error.toString(), file=sys.stderr)
        controller.close()
        return 1
    root = view.rootObject()
    width = min(720, available.width() - 48)
    height = round(root.property("preferredWindowHeight"))
    view.resize(width, height)
    view.setPosition(available.center().x() - width // 2,
                     available.y() + available.height() * 4 // 5 - height)

    resize_timer = bind_desk_window(view)
    root.moveRequested.connect(view.startSystemMove)
    close_timer = bind_desk_close(view, controller)
    view.show()

    def initialize():
        controller.ready()
        logging.getLogger(__name__).info("RAT Qt Quick Desk is ready.")
        if doc_target:
            controller.selectFile(str(doc_target.absolute()))

    QTimer.singleShot(0, initialize)
    try:
        return app.exec()
    finally:
        resize_timer.stop()
        close_timer.stop()
        controller.close()
        view.setSource(QUrl())
        view.close()
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    raise SystemExit(main())
