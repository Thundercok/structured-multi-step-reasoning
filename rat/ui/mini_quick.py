"""RAT Mini's Qt Quick entry; reuse the main RAT's production QML components."""
from pathlib import Path
import sys
import os
import logging
import json

os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PyQt6.QtCore import QLockFile, QTimer, QUrl, Qt
from PyQt6.QtGui import QAction, QFont, QGuiApplication
from PyQt6.QtQuick import QQuickView, QQuickWindow

from rat.engine.mini_settings import state_directory
from rat.os.native_menu import NativeMenu, NativeStatusItem
from rat.os.mini_hotkey import register_hotkey
from rat.ui.mini_quick_controller import MiniQuickController
from rat.ui.mini_instance import MiniInstanceBridge, present_running_mini
from rat.ui.image_drop import ImageDropFilter
from rat.ui.mini_shell import MiniShell

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))


def create_mini_desk(settings=None):
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setApplicationName('RAT Mini')
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont('Helvetica Neue', 13))
    controller = MiniQuickController(settings)
    QQuickWindow.setDefaultAlphaBuffer(True)
    view = QQuickView()
    fmt = view.format()
    fmt.setAlphaBufferSize(8)
    view.setFormat(fmt)
    view.setTitle('RAT Mini · Look source')
    view.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    # Look standby is only the original 122x128 mascot. Normal panels enforce
    # their own width; a window-level minimum must not enlarge passive Look.
    view.setMinimumWidth(1)
    screen = view.screen().availableGeometry()
    view.setInitialProperties(dict(liveController=controller,
        mascotSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_mascot_cutout.png')),
        lookHeadSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_look_head_v1.png')),
        lookPeekSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_look_peek_v1.png')),
        darkMode=app.styleHints().colorScheme() == Qt.ColorScheme.Dark,
        maxPaperHeight=max(180, min(420, screen.height()-250))))
    view.engine().addImageProvider('mini-input', controller.image_preview)
    view.setSource(QUrl.fromLocalFile(str(BASE/'rat/ui/quick/MiniDesk.qml')))
    if view.status() != QQuickView.Status.Ready:
        errors = '\n'.join(e.toString() for e in view.errors())
        raise RuntimeError('Mini QML could not load: '+errors)
    root = view.rootObject()
    image_drop = ImageDropFilter(view, controller, state_directory()/'last-image-drop.json')
    app.aboutToQuit.connect(image_drop.close)
    shell = MiniShell(view, root, controller)
    present = shell.present
    menu = NativeMenu()
    tray = NativeStatusItem()
    tray.setToolTip('RAT Mini · Look source')
    for label, callback in [
        ('Hiện RAT Mini', present),
        ('Chuột ơi, coi nè · ⌥⇧Space', controller.summonLook),
        ('Minimal · giữ ⌥⇧Space', controller.summonMinimal),
        ('Chọn vùng chữ để dịch…', controller.captureRegion),
        ('Dịch Clipboard', lambda: (present(), controller.translateClipboard())),
        ('Thiết lập & trợ giúp…', lambda: (present(), controller.helpRequested.emit())),
        ('Cài đặt…', lambda: (present(), controller.settingsRequested.emit())),
        ('Dừng tác vụ', controller.cancel), ('Ẩn RAT Mini', shell.dismiss),
        ('Thoát RAT Mini', controller.quit)]:
        action = QAction(label, menu)
        action.triggered.connect(lambda _checked=False, fn=callback: fn())
        menu.addAction(action)
    tray.setContextMenu(menu)
    tray.setPrimaryAction(shell.toggle)
    tray.menuVisibilityChanged.connect(shell.set_status_menu_open)
    tray.show()
    app.aboutToQuit.connect(tray.hide)
    def record_hotkey(stage):
        # Only this app's registered chord and outcome; no typed text/clipboard.
        try:
            (state_directory()/'last-hotkey.json').write_text(json.dumps({'protocol':'HOLD2','stage':stage}))
        except OSError:
            logging.getLogger(__name__).warning('hotkey_diagnostic_write_failed')
    try:
        hotkeys = register_hotkey(controller.summonLook,
            on_minimal=controller.summonMinimal,
            on_event=record_hotkey,
            on_error=lambda message: controller.update(hotkeyStatus=message)) if app.platformName() == 'cocoa' else None
        if hotkeys:
            app.aboutToQuit.connect(hotkeys.close)
    except OSError as exc:
        # Registration conflicts/missing helper do not block menus or image I/O.
        hotkeys = None
        controller.update(hotkeyStatus=str(exc))
    view._refs = (controller, tray, menu, shell, image_drop, hotkeys)
    return view, controller


def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s')
    # HTTP request URLs can contain snippet text or credentials. Keep stage
    # diagnostics, but never emit request URLs at the app's INFO log level.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    app = QGuiApplication(sys.argv)
    state_directory().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(state_directory()/'mini.lock'))
    if not lock.tryLock():
        if present_running_mini(state_directory()):
            return 0
        raise SystemExit('RAT Mini đang chạy. Chọn Hiện RAT Mini trên menu bar.')
    instance_bridge = MiniInstanceBridge(state_directory(), app)
    view, controller = create_mini_desk()
    instance_bridge.showRequested.connect(controller.presentRequested.emit)
    app.aboutToQuit.connect(instance_bridge.close)
    view._refs[3].present()
    # Look summons an observation surface. Capture itself still uses explicit
    # macOS screenshot/drop/paste; no global shortcut captures the screen.
    app._mini_refs = (view, controller, lock, instance_bridge)
    return app.exec()
