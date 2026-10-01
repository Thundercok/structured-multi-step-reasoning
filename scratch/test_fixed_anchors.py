import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtProperty, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QPen, QTransform, QLinearGradient, QBrush, QImage
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from rat.ui.chat_stream import get_mascot_pixmap

class TestPeekingRat(QWidget):
    speaking_popped_out = pyqtSignal()
    idle_retreated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._rotation: float = 0.0
        self.is_speaking: bool = False
        
        pm = get_mascot_pixmap(112, 120, bust_only=False)
        self._mascot_pixmap = pm if (pm and not pm.isNull()) else QPixmap()
        
        self.setFixedSize(150, 140)
        
        # Base anchors
        self.x_idle = 26
        self.y_idle = 66
        self.x_speaking = 46
        self.y_speaking = 2
        self.rot_idle = 0.0
        self.rot_speaking = 10.0
        
        self.move(self.x_idle, self.y_idle)

    @pyqtProperty(float)
    def rotation(self) -> float:
        return self._rotation

    @rotation.setter
    def rotation(self, val: float) -> None:
        self._rotation = val
        self.update()

    def set_anchors(self, container_x: int, container_y: int) -> None:
        cx = container_x if container_x > 0 else 16
        cy = container_y if container_y > 50 else 120
        
        self.x_idle = cx + 10
        self.y_idle = cy - 54    # paws at cy (120)
        self.x_speaking = self.x_idle + 20
        self.y_speaking = 2       # near top of window (y=2)
        
        if not self.is_speaking:
            self.move(self.x_idle, self.y_idle)
            self._rotation = self.rot_idle
        else:
            self.move(self.x_speaking, self.y_speaking)
            self._rotation = self.rot_speaking
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
        draw_y = 10  # 10px margin at top

        # Pivot near bottom of sprite
        pivot_x = draw_x + pm_w / 2
        pivot_y = draw_y + pm_h * 0.90

        p.save()
        p.translate(pivot_x, pivot_y)
        p.rotate(self._rotation)
        p.translate(-pivot_x, -pivot_y)

        # In IDLE, clip out the high tail on the right so ONLY eyes & paws peek out
        if abs(self._rotation) < 0.5:
            p.setClipRect(draw_x, draw_y, int(pm_w * 0.69), pm_h)

        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)
        p.restore()
        p.end()

def test():
    app = QApplication([])
    win = QWidget()
    win.resize(652, 238)
    win.setStyleSheet("background-color: #F8F9FA;")
    
    container = QFrame(win)
    container.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(0,0,0,0.08); border-radius: 16px;")
    container.setGeometry(16, 120, 620, 102)
    
    mascot = TestPeekingRat(win)
    mascot.stackUnder(container)
    mascot.set_anchors(16, 120)
    
    win.show()
    app.processEvents()
    
    # Render IDLE
    img_idle = QImage(win.size(), QImage.Format.Format_ARGB32_Premultiplied)
    win.render(img_idle)
    img_idle.save("scratch/test_anchors_idle.png")
    print("Saved scratch/test_anchors_idle.png")
    
    # Render SPEAKING
    mascot.is_speaking = True
    mascot.move(mascot.x_speaking, mascot.y_speaking)
    mascot.rotation = mascot.rot_speaking
    app.processEvents()
    
    img_speaking = QImage(win.size(), QImage.Format.Format_ARGB32_Premultiplied)
    win.render(img_speaking)
    img_speaking.save("scratch/test_anchors_speaking.png")
    print("Saved scratch/test_anchors_speaking.png")

if __name__ == "__main__":
    test()
