import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtProperty, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QPen, QTransform, QLinearGradient, QBrush
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

MASCOT_PATH = Path("rat/assets/rat_mascot_cutout.png")

class PeekingRatMascot(QWidget):
    """
    Refactored Mascot widget supporting:
    - Layered behind Chatbox container (stackUnder)
    - IDLE: Only eyes and gripping paws peeking over the top edge of chatbox (0 deg rotation)
    - SPEAKING: Diagonal pop-out (Y-up, X-shift 15-25px, Rotation -10° to +10°, OutBack easing, full body revealed)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self._rotation: float = 0.0
        self._mascot_pixmap = QPixmap()
        if MASCOT_PATH.exists():
            orig = QPixmap(str(MASCOT_PATH))
            if not orig.isNull():
                # Scale smoothly to character size
                self._mascot_pixmap = orig.scaled(138, 147, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # Fixed widget size large enough to avoid any clipping during rotation
        self.setFixedSize(160, 160)

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

        # Draw mascot rotated around its base pivot
        pm_w = self._mascot_pixmap.width()
        pm_h = self._mascot_pixmap.height()
        
        # Center horizontally in widget
        draw_x = (self.width() - pm_w) // 2
        draw_y = self.height() - pm_h
        
        # Pivot near bottom center of the mascot
        pivot_x = draw_x + pm_w / 2
        pivot_y = draw_y + pm_h * 0.85

        p.save()
        p.translate(pivot_x, pivot_y)
        p.rotate(self._rotation)
        p.translate(-pivot_x, -pivot_y)
        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)
        p.restore()
        p.end()

print("PeekingRatMascot defined successfully.")
