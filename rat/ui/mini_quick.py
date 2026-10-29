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
from rat.ui.mini_diagnostics import BUILD
from rat.ui.mini_instance import MiniInstanceBridge, present_running_mini
from rat.ui.image_drop import ImageDropFilter
from rat.ui.mini_shell import MiniShell
from rat.ui.mini_placement import LOOK_WIDTH, LOOK_HEIGHT, LOOK_OPTICAL_HEIGHT, MINI_PANEL_WIDTH, MINI_TEXT_SIZE

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
    view.setTitle('RAT Mini')
    view.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    # Look sizes its own mascot and speech surface. Normal panels enforce
    # their own width; a window-level minimum must not enlarge passive Look.
    view.setMinimumWidth(1)
    screen = view.screen().availableGeometry()
    reduce_motion = False
    if app.platformName() == 'cocoa':
        from AppKit import NSWorkspace
        workspace = NSWorkspace.sharedWorkspace()
        if hasattr(workspace, 'accessibilityDisplayShouldReduceMotion'):
            reduce_motion = bool(workspace.accessibilityDisplayShouldReduceMotion())
    view.setInitialProperties(dict(liveController=controller, reduceMotion=reduce_motion,
        buildLabel=f'{BUILD} · PID {os.getpid()}',
        lookMascotWidth=LOOK_WIDTH, lookMascotHeight=LOOK_HEIGHT, lookOpticalHeight=LOOK_OPTICAL_HEIGHT,
        sharedPanelWidth=MINI_PANEL_WIDTH, sharedTextSize=MINI_TEXT_SIZE,
        mascotSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_mascot_cutout.png')),
        lookHeadSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_look_head_v2.png')),
        lookIdleSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_look_idle_seated_v1.png')),
        lookErrorSource=QUrl.fromLocalFile(str(BASE/'rat/assets/rat_look_error_seated_v1.png')),
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
    tray.setToolTip('RAT Mini')
    tray_actions = {}
    for label, callback in [
        ('Xem lại công việc · ⌥⇧Space', controller.summonLook),
        ('Viết yêu cầu · giữ ⌥⇧Space', controller.summonMinimal),
        ('Bật theo dõi Clipboard', controller.toggleLookPaused),
        ('Tắt theo dõi Clipboard', controller.stopLook),
        ('Xem đoạn chờ', controller.previewPending),
        ('Xem lại kết quả', controller.recallLookResult),
        ('Chọn vùng chữ để dịch…', controller.captureRegion),
        ('Dịch Clipboard', lambda: (present(), controller.translateClipboard())),
        ('Thiết lập & trợ giúp…', lambda: (present(), controller.helpRequested.emit())),
        ('Cài đặt…', lambda: (present(), controller.settingsRequested.emit())),
        ('Dừng tác vụ', controller.cancel), ('Ẩn RAT Mini', shell.dismiss),
        ('Thoát RAT Mini', controller.quit)]:
        action = QAction(label, menu)
        action.triggered.connect(lambda _checked=False, fn=callback: fn())
        menu.addAction(action)
        tray_actions[callback] = action
    tray.setContextMenu(menu)
    tray.setPrimaryAction(controller.summonLook)
    def refresh_tray():
        state = controller.snapshot
        pending = bool(state['lookHasQueued'])
        tray.setBadgeText('1' if pending else '')
        tray.setToolTip('RAT Mini · ' + ('Có đoạn chờ dịch. Bấm để xem.' if pending else state['lookStatusLabel']))
        tray_actions[controller.previewPending].setEnabled(pending)
        tray_actions[controller.recallLookResult].setEnabled(state['hasWorkbench'])
        tray_actions[controller.toggleLookPaused].setText('Bật theo dõi Clipboard' if not state['lookWatching']
            else 'Tiếp tục Clipboard' if state['lookPaused'] else 'Tạm dừng Clipboard')
        tray_actions[controller.stopLook].setEnabled(state['lookWatching'])
    controller.changed.connect(refresh_tray)
    refresh_tray()
    tray.menuVisibilityChanged.connect(shell.set_status_menu_open)
    tray.show()
    app.aboutToQuit.connect(tray.hide)
    def record_hotkey(stage):
        # Only this app's registered chord and outcome; no typed text/clipboard.
        try:
            (state_directory()/'last-hotkey.json').write_text(json.dumps({'protocol':'HOLD2','stage':stage,'ui_build':BUILD,'pid':os.getpid()}))
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
        controller.update(hotkeyStatus='Phím gọi đang bận hoặc chưa sẵn sàng. Dùng biểu tượng RAT trên menu bar để mở.')
        logging.getLogger(__name__).warning('hotkey_unavailable %s', exc)
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
    requested_presentation = 'look' if '--look' in sys.argv else 'minimal' if '--minimal' in sys.argv else 'show'
    lock = QLockFile(str(state_directory()/'mini.lock'))
    if not lock.tryLock():
        if present_running_mini(state_directory(), requested_presentation):
            return 0
        raise SystemExit('RAT Mini đang chạy. Chọn Hiện RAT Mini trên menu bar.')
    instance_bridge = MiniInstanceBridge(state_directory(), app)
    view, controller = create_mini_desk()
    instance_bridge.showRequested.connect(controller.summonLook)
    instance_bridge.lookRequested.connect(controller.summonLook)
    instance_bridge.minimalRequested.connect(controller.summonMinimal)
    app.aboutToQuit.connect(instance_bridge.close)
    if requested_presentation == 'look':
        controller.summonLook()
    elif requested_presentation == 'minimal':
        controller.summonMinimal()
    else:
        view._refs[3].present()
    # Look summons an observation surface. Capture itself still uses explicit
    # macOS screenshot/drop/paste; no global shortcut captures the screen.
    app._mini_refs = (view, controller, lock, instance_bridge)
    return app.exec()
