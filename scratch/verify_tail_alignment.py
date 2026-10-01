import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtProperty, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QPen, QTransform, QLinearGradient, QBrush, QImage
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from test_animation_flow import PeekingRatMascot

class ArtisticSpeechBubble(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.dialogue = QLabel("Nghe đây. Cần gì?", self)
        self.dialogue.setStyleSheet("font-size: 13px; font-weight: 500; color: #111827; line-height: 1.35;")
        self.dialogue.setWordWrap(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 10, 14, 8)
        layout.addWidget(self.dialogue)
        
        self.tail_y = 46  # Aligned directly to Chuột's tilted snout

    def set_tail_y(self, val: int) -> None:
        self.tail_y = val
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width() - 4
        h = self.height() - 4
        r = 16

        tail_w = 16
        tail_h = 18
        tail_y = self.tail_y

        path = QPainterPath()
        path.moveTo(2 + tail_w + r, 2)
        path.lineTo(2 + w - r, 2)
        path.quadTo(2 + w, 2, 2 + w, 2 + r)
        path.lineTo(2 + w, 2 + h - r)
        path.quadTo(2 + w, 2 + h, 2 + w - r, 2 + h)
        path.lineTo(2 + tail_w + r, 2 + h)
        path.quadTo(2 + tail_w, 2 + h, 2 + tail_w, 2 + h - r)

        # Left edge leading to smooth sweep tail pointing towards Chuột's tilted snout
        path.lineTo(2 + tail_w, tail_y + tail_h)
        path.cubicTo(
            2 + tail_w * 0.4, tail_y + tail_h * 0.95,
            2 + tail_w * 0.1, tail_y + tail_h * 0.7,
            1.0, tail_y + tail_h * 0.5,
        )
        path.cubicTo(
            2 + tail_w * 0.15, tail_y + tail_h * 0.25,
            2 + tail_w * 0.5, tail_y + tail_h * 0.1,
            2 + tail_w, tail_y,
        )
        path.lineTo(2 + tail_w, 2 + r)
        path.quadTo(2 + tail_w, 2, 2 + tail_w + r, 2)
        path.closeSubpath()

        # Soft drop shadow
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 15, 10, 16))
        p.translate(0, 4)
        p.drawPath(path)
        p.restore()

        # Warm porcelain glass gradient fill
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(255, 255, 255, 252))
        grad.setColorAt(1.0, QColor(250, 248, 245, 250))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(0, 0, 0, 22), 1.0))
        p.drawPath(path)
        p.end()

def test_align():
    app = QApplication.instance() or QApplication(sys.argv)
    
    win = QWidget()
    win.resize(652, 238)
    win.setStyleSheet("background-color: #F8F9FA;")
    
    container = QFrame(win)
    container.setStyleSheet("""
        QFrame {
            background-color: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 16px;
        }
    """)
    container.setGeometry(16, 120, 620, 102)
    
    mascot = PeekingRatMascot(win)
    mascot.stackUnder(container)
    mascot.set_anchors(container.x(), container.y())
    
    bubble = ArtisticSpeechBubble(win)
    bubble.setGeometry(container.x() + 150, 12, 450, 98)
    bubble.set_tail_y(46)
    
    # State: SPEAKING
    mascot.move(mascot.x_speaking, mascot.y_speaking)
    mascot.rotation = mascot.rot_speaking
    mascot.is_speaking = True
    bubble.show()
    
    win.show()
    app.processEvents()
    
    img = QImage(win.size(), QImage.Format.Format_ARGB32_Premultiplied)
    win.render(img)
    img.save("scratch/verified_speaking_tail.png")
    print("Saved scratch/verified_speaking_tail.png")

if __name__ == "__main__":
    test_align()
