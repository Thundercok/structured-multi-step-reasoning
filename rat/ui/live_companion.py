"""A visible, animated companion; decorative motion never performs app actions."""
from __future__ import annotations

import math
import time
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QPushButton
from rat.ui.chat_stream import get_mascot_pixmap
from rat.ui.surface_layout import motion_enabled


class LiveCompanion(QPushButton):
    """One persistent character beside the chat in both compact and full."""
    LABELS = {'idle': 'Mình ở đây', 'thinking': 'Đang làm cùng bạn',
        'searching': 'Đang tìm', 'noting': 'Ghi lại rồi', 'waiting': 'Cần thêm một chút dữ kiện',
        'done': 'Đã có phản hồi', 'error': 'Đang vướng một bước'}

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.current_state = 'idle'
        self.reaction = 'greet'
        self._started = time.monotonic()
        self._reaction_at = self._started
        self._motion_allowed = False
        self._motion_checked_at = 0.0
        self._sprite = get_mascot_pixmap(124, 124, bust_only=False)
        self.setObjectName('LiveCompanion')
        self.setFixedSize(160, 184)
        self.setAccessibleName('Chuột · chạm để chơi và mở ghi chép')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('QPushButton#LiveCompanion { background: transparent; border: none; }')
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.clicked.connect(self._on_clicked)
        self.set_state('idle')

    def _on_clicked(self):
        self.react('happy')
        pane = self.window.notebook_pane
        pane.set_open(not pane.opened)
        self.window._schedule_surface_fit()

    def react(self, reaction):
        self.reaction = reaction
        self._reaction_at = time.monotonic()
        self._sync_timer()
        self.update()

    def set_state(self, state):
        if state != self.current_state:
            self.current_state = state
            self.react('hop' if state in ('thinking', 'searching') else state)
        self.setToolTip(self.LABELS.get(state, self.LABELS['idle']) + ' · chạm để chơi và xem ghi chép')
        self._sync_timer()
        self.update()

    def _sync_timer(self):
        self._motion_allowed = motion_enabled()
        self._motion_checked_at = time.monotonic()
        if self.isVisible() and self._motion_allowed:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def _tick(self):
        if time.monotonic() - self._motion_checked_at >= 1:
            self._sync_timer()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self.current_state == 'idle':
            self.react('greet')
        self._sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def pose(self, now=None):
        """Bounded stage-local motion: no widget geometry, focus or task mutation."""
        now = time.monotonic() if now is None else now
        elapsed = now - self._started
        age = max(0, now - self._reaction_at)
        moving = self._motion_allowed
        active_reaction = self.reaction if age < 2 else ''
        x = self.width() / 2
        y, rotation, sx, sy = 99.0, 0.0, 1.0, 1.0
        if moving:
            breath = math.sin(elapsed * 2.4)
            y += breath * 1.2
            sy += breath * 0.015
            if self.current_state in ('thinking', 'searching'):
                rotation = math.sin(elapsed * 3.5) * 5
                x += math.sin(elapsed * 1.5) * 4
            elif self.current_state == 'noting':
                rotation = -7 + math.sin(elapsed * 7) * 2
            elif self.current_state in ('waiting', 'error'):
                rotation = 8 + math.sin(elapsed * 2) * 2
            else:
                x += math.sin(elapsed * 0.7) * 2
                rotation = math.sin(elapsed * 1.5) * 3
            if active_reaction in ('greet', 'hop', 'happy', 'done'):
                progress = min(age / 0.9, 1)
                jump = math.sin(progress * math.pi)
                y -= jump * 14
                rotation += math.sin(progress * math.pi * 2) * 6
                sx += jump * 0.04
                sy -= jump * 0.04
        return dict(x=x, y=y, rotation=rotation, sx=sx, sy=sy,
                    reaction=active_reaction, age=age, elapsed=elapsed, moving=moving)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pose = self.pose()
        x, y = pose['x'], pose['y']
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(133, 105, 72, 18))
        p.drawEllipse(QRectF(x - 42, 165, 84, 7))
        if self._sprite and not self._sprite.isNull():
            p.save()
            p.translate(x, y)
            p.rotate(pose['rotation'])
            p.scale(pose['sx'], pose['sy'])
            p.drawPixmap(-self._sprite.width() // 2, -self._sprite.height() // 2, self._sprite)
            p.restore()

        # Expression accents and a writing prop retain the original RAT drawing.
        state = self.current_state
        reaction = pose['reaction']
        writing = state == 'noting' or reaction == 'noting'
        glyph = '♡' if reaction == 'happy' else '✎' if writing else '✧' if state == 'done' or reaction == 'greet' else '?' if state in ('waiting', 'error') else '…' if state in ('thinking', 'searching') else '♪'
        p.setBrush(QColor('#F8EFE0'))
        p.drawEllipse(QRectF(x + 42, 14, 30, 28))
        p.setPen(QColor('#AC785F') if reaction == 'happy' else QColor('#91784F'))
        p.setFont(QFont('Arial', 14))
        p.drawText(QRectF(x + 42, 14, 30, 28), Qt.AlignmentFlag.AlignCenter, glyph)
        if writing:
            p.setBrush(QColor('#FFFCF5'))
            p.setPen(QPen(QColor('#BAA687'), 1))
            p.drawRoundedRect(QRectF(x + 22, 98, 30, 25), 2, 2)
            for row in range(3):
                p.drawLine(QPointF(x + 26, 105 + row * 5), QPointF(x + 47, 105 + row * 5))
            scribble = math.sin(pose['elapsed'] * 8) * 3 if pose['moving'] else 0
            p.setPen(QPen(QColor('#796347'), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x + 36 + scribble, 115), QPointF(x + 48 + scribble, 96))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#B3996E'), 1, Qt.PenStyle.DotLine))
            p.drawRoundedRect(QRectF(2, 2, self.width() - 4, self.height() - 4), 10, 10)
        p.end()
