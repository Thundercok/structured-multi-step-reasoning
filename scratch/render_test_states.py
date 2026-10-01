import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtProperty, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QPen, QTransform, QLinearGradient, QBrush, QImage
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

MASCOT_PATH = Path("rat/assets/rat_mascot_cutout.png")

class PeekingRatMascot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self._rotation: float = 0.0
        self._mascot_pixmap = QPixmap()
        if MASCOT_PATH.exists():
            orig = QPixmap(str(MASCOT_PATH))
            if not orig.isNull():
                # Scaled to 110px height (width ~104px) so full body fits smoothly in the top 120px stage
                self._mascot_pixmap = orig.scaled(106, 114, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.setFixedSize(140, 140)

    @pyqtProperty(float)
    def rotation(self) -> float:
        return self._rotation

    @rotation.setter
    def rotation(self, val: float) -> None:
        self._rotation = val
        self.update()

    def paintEvent(self, event):
        if self._mascot_pixmap.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pm_w = self._mascot_pixmap.width()
        pm_h = self._mascot_pixmap.height()
        
        draw_x = (self.width() - pm_w) // 2
        draw_y = self.height() - pm_h
        
        pivot_x = draw_x + pm_w / 2
        pivot_y = draw_y + pm_h * 0.90

        p.save()
        p.translate(pivot_x, pivot_y)
        p.rotate(self._rotation)
        p.translate(-pivot_x, -pivot_y)
        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)
        p.restore()
        p.end()

class ModernSpeechBubble(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.dialogue = QLabel("Nghe đây. Cần gì?", self)
        self.dialogue.setStyleSheet("font-size: 12.5px; font-weight: 500; color: #111827;")
        self.dialogue.setWordWrap(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 10, 14, 8)
        layout.addWidget(self.dialogue)
        
        # Tail target Y for pointing at the rat's tilted head
        self.tail_tip_y = 38

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width() - 4
        h = self.height() - 4
        r = 16

        tail_w = 16
        tail_h = 18
        tail_y = self.tail_tip_y

        path = QPainterPath()
        path.moveTo(2 + tail_w + r, 2)
        path.lineTo(2 + w - r, 2)
        path.quadTo(2 + w, 2, 2 + w, 2 + r)
        path.lineTo(2 + w, 2 + h - r)
        path.quadTo(2 + w, 2 + h, 2 + w - r, 2 + h)
        path.lineTo(2 + tail_w + r, 2 + h)
        path.quadTo(2 + tail_w, 2 + h, 2 + tail_w, 2 + h - r)

        # Smooth bezier sweep tail pointing towards mouse's head
        path.lineTo(2 + tail_w, tail_y + tail_h)
        path.cubicTo(
            2 + tail_w * 0.4, tail_y + tail_h * 0.95,
            2 + tail_w * 0.1, tail_y + tail_h * 0.7,
            1.0, tail_y + tail_h * 0.45,
        )
        path.cubicTo(
            2 + tail_w * 0.15, tail_y + tail_h * 0.25,
            2 + tail_w * 0.5, tail_y + tail_h * 0.1,
            2 + tail_w, tail_y,
        )
        path.lineTo(2 + tail_w, 2 + r)
        path.quadTo(2 + tail_w, 2, 2 + tail_w + r, 2)
        path.closeSubpath()

        # Shadow
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 15, 10, 16))
        p.translate(0, 4)
        p.drawPath(path)
        p.restore()

        # Porcelain white gradient
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(255, 255, 255, 252))
        grad.setColorAt(1.0, QColor(250, 248, 245, 250))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(0, 0, 0, 22), 1.0))
        p.drawPath(path)
        p.end()

def test_render():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Outer window
    win = QWidget()
    win.resize(652, 238)
    win.setStyleSheet("background-color: #F3F4F6;") # light desktop background
    
    # Main container
    container = QFrame(win)
    container.setStyleSheet("""
        QFrame {
            background-color: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 16px;
        }
    """)
    container.setGeometry(16, 120, 620, 102)
    
    # Peeking Mascot
    mascot = PeekingRatMascot(win)
    mascot.stackUnder(container)
    
    # Speech bubble
    bubble = ModernSpeechBubble(win)
    bubble.setGeometry(166, 12, 470, 98)
    
    # --- State 1: IDLE ---
    # In IDLE:
    # Mascot Y is sunken so chatbox covers almost everything, leaving only eyes & paws visible!
    # Paws are at container top Y = 120. Inside mascot widget (140h, draw_y=26, paws_y=44 down => 70 from widget top)
    # So widget Y = 120 - 70 = 50.
    mascot.move(24, 50)
    mascot.rotation = 0.0
    bubble.hide()
    
    win.show()
    app.processEvents()
    
    img_idle = QImage(win.size(), QImage.Format.Format_ARGB32_Premultiplied)
    win.render(img_idle)
    img_idle.save("scratch/state_idle.png")
    print("Saved scratch/state_idle.png")
    
    # --- State 2: SPEAKING ---
    # Slides Y up by ~42px (50 -> 8)
    # Slides X by +20px (24 -> 44)
    # Rotation: +10.0 deg
    mascot.move(44, 8)
    mascot.rotation = 10.0
    bubble.show()
    bubble.tail_tip_y = 42
    
    app.processEvents()
    img_speaking = QImage(win.size(), QImage.Format.Format_ARGB32_Premultiplied)
    win.render(img_speaking)
    img_speaking.save("scratch/state_speaking.png")
    print("Saved scratch/state_speaking.png")

if __name__ == "__main__":
    test_render()
