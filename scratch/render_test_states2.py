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
                self._mascot_pixmap = orig.scaled(112, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.setFixedSize(144, 144)

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

        # In IDLE (rotation == 0), clip out the high tail on the right so ONLY eyes & 2 gripping paws peek out!
        if abs(self._rotation) < 0.5:
            # Right edge of right paw is ~68% of pixmap width
            p.setClipRect(draw_x, draw_y, int(pm_w * 0.69), pm_h)

        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)
        p.restore()
        p.end()

def test_render():
    app = QApplication.instance() or QApplication(sys.argv)
    
    win = QWidget()
    win.resize(652, 238)
    win.setStyleSheet("background-color: #F3F4F6;")
    
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
    
    # IDLE: paws at container rim (y = 120)
    # inside mascot widget: draw_y = 144 - 120 = 24. Paws are ~46px down => 70 from top of widget.
    # widget Y = 120 - 70 = 50.
    mascot.move(26, 50)
    mascot.rotation = 0.0
    
    win.show()
    app.processEvents()
    
    img_idle = QImage(win.size(), QImage.Format.Format_ARGB32_Premultiplied)
    win.render(img_idle)
    img_idle.save("scratch/state_idle2.png")
    print("Saved scratch/state_idle2.png")

if __name__ == "__main__":
    test_render()
