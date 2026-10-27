"""rat.ui.mini_translate — tiny EN→VI translator in rat's warm paper style.

Three inputs: typed/pasted text, selected text (Cmd+C via System Events),
screen region (screencapture -i + shared Apple Vision OCR). Translation uses the
keyless Google gtx endpoint: no LLM tokens. Run: python -m rat.ui.mini_translate
"""
import json
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget

# Frozen (PyInstaller) builds unpack data under sys._MEIPASS with the same rat/{assets,bin} layout.
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent)) / "rat"
APPLE_CLI = BASE / "bin" / "apple_translate"


def apple_translate(text: str, target: str = "vi") -> str:
    """Offline Apple Translation (built by tools/apple_translate.swift); '' if unavailable."""
    if not APPLE_CLI.is_file():
        return ""
    try:
        r = subprocess.run([str(APPLE_CLI), target], input=text, capture_output=True,
                           text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else ""
    except subprocess.TimeoutExpired:
        return ""


def translate(text: str, target: str = "vi") -> str:
    if out := apple_translate(text, target):
        return out
    q = urllib.parse.quote(text)
    # Ship a CA bundle with the app; another Mac may not have Python's CA path.
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        req = urllib.request.Request(
            "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl="
            f"{target}&dt=t&q={q}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10, context=context) as r:
            return "".join(seg[0] for seg in json.load(r)[0] if seg[0])
    except Exception:  # rate-limited (429) etc.: fall back to MyMemory (keyless, ~500 chars)
        url = f"https://api.mymemory.translated.net/get?q={q[:1500]}&langpair=en|{target}"
        with urllib.request.urlopen(url, timeout=10, context=context) as r:
            return json.load(r)["responseData"]["translatedText"]


def ocr_region() -> str:
    """Drag-select a screen region; return recognized text ('' if cancelled)."""
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "r.png"
        subprocess.run(["screencapture", "-i", "-x", str(png)], check=False)
        if not png.is_file():
            return ""
        from document_intake.vision import recognize_tokens
        return " ".join(t["text"] for t in recognize_tokens(str(png)))


def selected_text() -> str:
    """Copy the frontmost app's selection and read the clipboard (needs Accessibility)."""
    subprocess.run(["osascript", "-e",
                    'tell application "System Events" to keystroke "c" using command down'],
                   check=False, timeout=3)
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


class Job(QThread):
    done = pyqtSignal(str, str)  # source, translation

    def __init__(self, getter):
        super().__init__()
        self.getter = getter

    def run(self):
        try:
            src = self.getter().strip()
            self.done.emit(src, translate(src) if src else "")
        except Exception as exc:  # network, permissions, OCR
            self.done.emit("", f"Lỗi: {exc}")


ASSET = BASE / "assets" / "rat_mascot_cutout.png"
HINT = "⌥⇧D rồi kéo chọn chữ, mình dịch cho! · r2"


class MiniTranslate(QWidget):
    """Frameless rat mascot; its speech bubble shows the meaning. Drag to move,
    click = translate selection, right-click = menu, click bubble = copy."""
    hotkey = pyqtSignal()  # emitted from pynput's thread, handled on the Qt thread

    def __init__(self):
        super().__init__()
        self.hotkey.connect(lambda: self.start(ocr_region))
        self.setWindowTitle("rat · dịch nhanh")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.bubble = QLabel(HINT)
        self.bubble.setWordWrap(True)
        self.bubble.setMaximumWidth(300)
        self.bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.bubble.setStyleSheet(
            "background:#FFFDF9; color:#1F1A16; border:1px solid #DEC88E; "
            "border-bottom:2.5px solid #C9A952; border-radius:12px; padding:8px 10px;")
        self.rat = QLabel()
        self.rat.setPixmap(QPixmap(str(ASSET)).scaledToHeight(
            130, Qt.TransformationMode.SmoothTransformation))
        lay = QVBoxLayout(self)
        lay.addWidget(self.bubble)
        lay.addWidget(self.rat, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.job, self._drag, self._moved = None, None, False
        # Always-available exits: Esc (hide), Cmd+Q (quit), × on the bubble, tray menu.
        QShortcut(QKeySequence("Esc"), self, self.hide)
        QShortcut(QKeySequence("Ctrl+Q"), self, QApplication.quit)  # Qt maps Ctrl→Cmd on macOS
        close = QPushButton("×", self)
        close.setFixedSize(20, 20)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet("QPushButton{background:#F0ECE4;border:1px solid #D6CEBE;"
                            "border-radius:10px;color:#4B4339;font-weight:bold;}")
        close.clicked.connect(self.hide)
        close.move(self.sizeHint().width() - 26, 2)
        self.close_btn = close
        self.tray = QSystemTrayIcon(QIcon(str(ASSET)), self)
        menu = QMenu()
        menu.addAction("Hiện rat", self.show)
        menu.addAction("Quét vùng (⌥⇧D)", lambda: self.start(ocr_region))
        menu.addAction("Thoát", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda *_: self.show())
        self.tray.show()
        self._menu = menu

    def resizeEvent(self, e):
        self.close_btn.move(self.width() - 26, 2)

    def start(self, getter):
        self.bubble.setText("…")
        self.job = Job(getter)
        self.job.done.connect(self.show_result)
        self.job.start()

    def show_result(self, src, out):
        self.bubble.setText(out or "Không thấy chữ nào.")
        self.adjustSize()
        self.show()
        self.raise_()

    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        self._moved = False

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self._moved = True
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        if not self._moved and e.button() == Qt.MouseButton.LeftButton:
            self.start(selected_text)
        self._drag = None

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("Quét vùng (⌥⇧D)", lambda: self.start(ocr_region))
        m.addAction("Dịch clipboard", lambda: self.start(
            lambda: subprocess.run(["pbpaste"], capture_output=True, text=True).stdout))
        m.addAction("Sao chép bản dịch", lambda: QApplication.clipboard().setText(self.bubble.text()))
        m.addAction("Thoát", QApplication.quit)
        m.exec(e.globalPos())


_carbon_keepalive = []


def register_hotkey(callback, keycode=2, modifiers=2048 | 512):
    """Option+Shift+D via Carbon RegisterEventHotKey: needs no Input Monitoring permission."""
    import ctypes
    import ctypes.util
    c = ctypes.CDLL(ctypes.util.find_library("Carbon"))
    c.GetApplicationEventTarget.restype = ctypes.c_void_p

    class Spec(ctypes.Structure):
        _fields_ = [("cls", ctypes.c_uint32), ("kind", ctypes.c_uint32)]

    class HotID(ctypes.Structure):
        _fields_ = [("sig", ctypes.c_uint32), ("id", ctypes.c_uint32)]

    proto = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    handler = proto(lambda *_: (callback(), 0)[1])
    spec = Spec(int.from_bytes(b"keyb", "big"), 5)  # kEventHotKeyPressed
    target = c.GetApplicationEventTarget()
    c.InstallEventHandler.argtypes = [ctypes.c_void_p, proto, ctypes.c_uint32,
                                      ctypes.POINTER(Spec), ctypes.c_void_p, ctypes.c_void_p]
    if c.InstallEventHandler(target, handler, 1, ctypes.byref(spec), None, None):
        raise OSError("InstallEventHandler failed")
    ref = ctypes.c_void_p()
    c.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, HotID, ctypes.c_void_p,
                                      ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    if c.RegisterEventHotKey(keycode, modifiers, HotID(int.from_bytes(b"rtrn", "big"), 1),
                             target, 0, ctypes.byref(ref)):
        raise OSError("RegisterEventHotKey failed (shortcut taken?)")
    _carbon_keepalive.extend([handler, spec, ref])


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # hidden rat keeps living in the tray
    w = MiniTranslate()
    w.show()
    try:  # global hotkey: Option+Shift+D → drag a region like Cmd+Shift+4 → translate
        register_hotkey(w.hotkey.emit)
    except Exception as exc:
        print("Hotkey unavailable:", exc)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
