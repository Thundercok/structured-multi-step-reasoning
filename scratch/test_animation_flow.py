import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtProperty, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QPen, QTransform, QLinearGradient, QBrush, QImage
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

MASCOT_PATH = Path("rat/assets/rat_mascot_cutout.png")

class PeekingRatMascot(QWidget):
    speaking_popped_out = pyqtSignal()
    idle_retreated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._rotation: float = 0.0
        self._mascot_pixmap = QPixmap()
        if MASCOT_PATH.exists():
            orig = QPixmap(str(MASCOT_PATH))
            if not orig.isNull():
                self._mascot_pixmap = orig.scaled(112, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.setFixedSize(144, 144)
        
        # Geometry anchors
        self.x_idle = 26
        self.y_idle = 50
        self.x_speaking = 46    # +20px shift sideways
        self.y_speaking = 6     # -44px slide up
        self.rot_idle = 0.0     # 0 degree
        self.rot_speaking = 10.0 # +10 degree tilt
        
        self.is_speaking = False
        
        # Parallel animation group for smooth simultaneous transform
        self._anim_group = QParallelAnimationGroup(self)
        
        self._pos_anim = QPropertyAnimation(self, b"pos")
        self._pos_anim.setDuration(350)
        
        self._rot_anim = QPropertyAnimation(self, b"rotation")
        self._rot_anim.setDuration(350)
        
        self._anim_group.addAnimation(self._pos_anim)
        self._anim_group.addAnimation(self._rot_anim)
        self._anim_group.finished.connect(self._on_animation_finished)

    @pyqtProperty(float)
    def rotation(self) -> float:
        return self._rotation

    @rotation.setter
    def rotation(self, val: float) -> None:
        self._rotation = val
        self.update()

    def set_anchors(self, container_x: int, container_y: int) -> None:
        """Update anchors when container geometry changes."""
        self.x_idle = container_x + 10
        self.y_idle = container_y - 70
        self.x_speaking = self.x_idle + 20
        self.y_speaking = self.y_idle - 44
        if not self.is_speaking:
            self.move(self.x_idle, self.y_idle)
            self._rotation = self.rot_idle
        else:
            self.move(self.x_speaking, self.y_speaking)
            self._rotation = self.rot_speaking
        self.update()

    def pop_out_speaking(self) -> None:
        """Trigger diagonal pop-out animation (~350ms, OutBack easing)."""
        self.is_speaking = True
        self._anim_group.stop()
        
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(self.x_speaking, self.y_speaking))
        
        self._rot_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._rot_anim.setStartValue(self._rotation)
        self._rot_anim.setEndValue(self.rot_speaking)
        
        self._anim_group.start()

    def retreat_to_idle(self) -> None:
        """Retreat back to hiding/idle position (eyes & paws peeking only, 0 deg)."""
        self.is_speaking = False
        self._anim_group.stop()
        
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(self.x_idle, self.y_idle))
        
        self._rot_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rot_anim.setStartValue(self._rotation)
        self._rot_anim.setEndValue(self.rot_idle)
        
        self._anim_group.start()

    def _on_animation_finished(self) -> None:
        if self.is_speaking:
            self.speaking_popped_out.emit()
        else:
            self.idle_retreated.emit()

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

        # In IDLE, clip out the high tail on the right so ONLY eyes & 2 gripping paws peek out!
        if abs(self._rotation) < 0.5:
            p.setClipRect(draw_x, draw_y, int(pm_w * 0.69), pm_h)

        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)
        p.restore()
        p.end()

print("Animation flow test compiled.")
