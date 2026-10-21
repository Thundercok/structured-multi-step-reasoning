"""
rat.ui.workbench — Native PyQt6 RAT Workbench.

Implements the user-approved compact separated Workbench:
1. Work canvas above: paper card with brand chrome, work title, duration badge, and useful content.
2. RAT stage and speech below: prominent mouse companion outside the card, with paper speech bubble pointing to it.
3. User dialogue at the bottom: editable green bubble aligned with RAT speech, tail pointing down-right.

Design reference:
- Specimen footprint: approx 520 x 335 CSS px in compact default.
- Desktop mouse width: 104px (slot: 112 x 82).
- Narrow mouse width: 80px (slot: 84 x 88).
- Expanded mouse width: 132px (slot: 144 x 150).
"""
from __future__ import annotations

import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rat.ui.surface_layout import ChatComposer, motion_enabled

FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif'
MASCOT_CUTOUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "rat_mascot_cutout.png"
MASCOT_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "assets" / "rat_mascot.png"


def is_dark_mode() -> bool:
    app = QApplication.instance()
    if app and app.property("ratDarkMode") is not None:
        return bool(app.property("ratDarkMode"))
    if os.getenv("RAT_DARK_MODE", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from PyQt6.QtGui import QPalette
        if app:
            return app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    except Exception:
        pass
    return False


@dataclass(frozen=True)
class WorkbenchTokens:
    paper: QColor
    ink: QColor
    muted: QColor
    line: QColor
    soft: QColor
    user: QColor
    user_line: QColor
    accent: QColor
    focus: QColor
    shadow: QColor
    floor: QColor
    error: QColor

    paper_hex: str
    ink_hex: str
    muted_hex: str
    line_hex: str
    soft_hex: str
    user_hex: str
    user_line_hex: str
    accent_hex: str
    focus_hex: str
    error_hex: str

    @classmethod
    def get(cls, dark: Optional[bool] = None) -> "WorkbenchTokens":
        if dark is None:
            dark = is_dark_mode()
        if dark:
            return cls(
                paper=QColor("#272a25"),
                ink=QColor("#eeeee6"),
                muted=QColor("#b5bbae"),
                line=QColor("#42483c"),
                soft=QColor("#33392d"),
                user=QColor("#35402c"),
                user_line=QColor("#566649"),
                accent=QColor("#bdd39f"),
                focus=QColor("#b4ce93"),
                shadow=QColor(0, 0, 0, 52),
                floor=QColor(0, 0, 0, 69),
                error=QColor("#edb4a4"),
                paper_hex="#272a25",
                ink_hex="#eeeee6",
                muted_hex="#b5bbae",
                line_hex="#42483c",
                soft_hex="#33392d",
                user_hex="#35402c",
                user_line_hex="#566649",
                accent_hex="#bdd39f",
                focus_hex="#b4ce93",
                error_hex="#edb4a4",
            )
        else:
            return cls(
                paper=QColor("#fffefa"),
                ink=QColor("#30382f"),
                muted=QColor("#616b5c"),
                line=QColor("#e4e7dc"),
                soft=QColor("#f2f3eb"),
                user=QColor("#e9eedf"),
                user_line=QColor("#d4ddc7"),
                accent=QColor("#536b3f"),
                focus=QColor("#738d5b"),
                shadow=QColor(52, 65, 43, 18),
                floor=QColor(100, 114, 82, 32),
                error=QColor("#984a3a"),
                paper_hex="#fffefa",
                ink_hex="#30382f",
                muted_hex="#616b5c",
                line_hex="#e4e7dc",
                soft_hex="#f2f3eb",
                user_hex="#e9eedf",
                user_line_hex="#d4ddc7",
                accent_hex="#536b3f",
                focus_hex="#738d5b",
                error_hex="#984a3a",
            )


def normalize_command(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.strip())
    without_marks = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = without_marks.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", cleaned).strip(" .!")


def is_expand_command(text: str) -> bool:
    cmd = normalize_command(text)
    return cmd in {"xem chi tiet", "chi tiet", "mo rong", "doc day du"}


def is_collapse_command(text: str) -> bool:
    cmd = normalize_command(text)
    return cmd in {"thu gon", "gon lai"}


def is_stop_command(text: str) -> bool:
    cmd = normalize_command(text)
    return cmd in {"dung", "dung lai", "thoi", "stop", "huy", "cancel"}


# =========================================================================
# 1. RAT ACTOR WIDGET
# =========================================================================
class WorkbenchActorWidget(QPushButton):
    """
    Prominent RAT companion outside the paper card.
    Desktop compact: 104px wide sprite inside 112 x 82 slot (overflowing freely).
    Narrow: 80px wide sprite in 84 x 88 slot.
    Expanded: 132px wide sprite in 144 x 150 slot.
    """
    LABELS = {
        "idle": "Mình ở đây",
        "thinking": "Đang làm cùng bạn",
        "searching": "Đang tìm",
        "noting": "Ghi lại rồi",
        "waiting": "Cần thêm một chút dữ kiện",
        "done": "Đã có phản hồi",
        "error": "Đang vướng một bước",
        "working": "Đang làm cùng bạn",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchActor")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Chuột · chạm để vẫy chào")
        self.setStyleSheet("QPushButton#WorkbenchActor { background: transparent; border: none; }")

        self.current_state = "idle"
        self.reaction = "greet"
        self.prop_kind = "plan"  # "plan", "calculation", "file", "note"
        self.is_expanded = False
        self.is_narrow = False

        self._started = time.monotonic()
        self._reaction_at = self._started
        self._motion_allowed = False
        self._motion_checked_at = 0.0

        target_file = MASCOT_CUTOUT_PATH if MASCOT_CUTOUT_PATH.exists() else MASCOT_FALLBACK_PATH
        self._sprite_raw = QPixmap(str(target_file)) if target_file.exists() else QPixmap()

        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.clicked.connect(self._on_clicked)

        self._sync_geometry()
        self.set_state("idle")

    def _sync_geometry(self) -> None:
        if self.is_expanded:
            self.slot_w, self.slot_h = 144, 150
            self.actor_w = 132
        elif self.is_narrow:
            self.slot_w, self.slot_h = 84, 88
            self.actor_w = 80
        else:
            self.slot_w, self.slot_h = 112, 82
            self.actor_w = 104
        # Give sufficient paint height to prevent clipping feet/shadow/motion
        total_h = max(self.slot_h + 36, 120)
        self.setFixedSize(self.slot_w, total_h)

    def set_presentation(self, expanded: bool, narrow: bool = False) -> None:
        if self.is_expanded != expanded or self.is_narrow != narrow:
            self.is_expanded = expanded
            self.is_narrow = narrow
            self._sync_geometry()
            self.update()

    def set_prop_kind(self, kind: str) -> None:
        if self.prop_kind != kind:
            self.prop_kind = kind
            self.update()

    def set_state(self, state: str) -> None:
        if state != self.current_state:
            self.current_state = state
            self.react("hop" if state in ("thinking", "searching", "working") else state)
        self.setToolTip(self.LABELS.get(state, self.LABELS["idle"]) + " · Chạm Chuột để vẫy chào")
        self._sync_timer()
        self.update()

    def react(self, reaction: str) -> None:
        self.reaction = reaction
        self._reaction_at = time.monotonic()
        self._sync_timer()
        self.update()

    def _on_clicked(self) -> None:
        self.react("happy")

    def pose(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.monotonic() if now is None else now
        elapsed = now - self._started
        age = max(0.0, now - self._reaction_at)
        moving = self._motion_allowed
        active_reaction = self.reaction if age < 2.0 else ""
        x = self.width() / 2.0
        y, rotation, sx, sy = 99.0, 0.0, 1.0, 1.0
        if moving:
            breath = math.sin(elapsed * 2.4)
            y += breath * 1.2
            sy += breath * 0.015
            if self.current_state in ("thinking", "searching", "working"):
                rotation = math.sin(elapsed * 3.5) * 5.0
                x += math.sin(elapsed * 1.5) * 4.0
            elif self.current_state == "noting":
                rotation = -7.0 + math.sin(elapsed * 7.0) * 2.0
            elif self.current_state in ("waiting", "error"):
                rotation = 8.0 + math.sin(elapsed * 2.0) * 2.0
            else:
                x += math.sin(elapsed * 0.7) * 2.0
                rotation = math.sin(elapsed * 1.5) * 3.0
            if active_reaction in ("greet", "hop", "happy", "done"):
                progress = min(age / 0.9, 1.0)
                jump = math.sin(progress * math.pi)
                y -= jump * 14.0
                rotation += math.sin(progress * math.pi * 2.0) * 6.0
                sx += jump * 0.04
                sy -= jump * 0.04
        return dict(
            x=x, y=y, rotation=rotation, sx=sx, sy=sy,
            reaction=active_reaction, age=age, elapsed=elapsed, moving=moving,
        )

    def _sync_timer(self) -> None:
        try:
            import rat.ui.live_companion as lc
            self._motion_allowed = lc.motion_enabled()
        except Exception:
            self._motion_allowed = motion_enabled()
        self._motion_checked_at = time.monotonic()
        if (self.isVisible() or (self.window() is not None and self.window().isVisible())) and self._motion_allowed:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def _tick(self) -> None:
        if time.monotonic() - self._motion_checked_at >= 1.0:
            self._sync_timer()
        self.update()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event: Any) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        tokens = WorkbenchTokens.get()
        now = time.monotonic()
        elapsed = now - self._started
        age = max(0.0, now - self._reaction_at)
        moving = self._motion_allowed

        # Bounded motion calculation
        dy, rot = 0.0, 0.0
        if moving:
            dy = math.sin(elapsed * 2.4) * 1.2
            if age < 0.6 and self.reaction in ("greet", "hop", "happy", "done"):
                # Jump 7px, rotate -3 deg, return
                progress = age / 0.52
                jump = math.sin(min(1.0, progress) * math.pi)
                dy -= jump * 7.0
                rot -= jump * 3.0

        # Sprite target sizing
        if self._sprite_raw.isNull():
            p.end()
            return

        raw_w = self._sprite_raw.width()
        raw_h = self._sprite_raw.height()
        aspect = raw_h / max(1, raw_w)
        target_w = self.actor_w
        target_h = int(target_w * aspect)

        # Anchors from spec with 8px top headroom so the 7px hop never clips ears
        pad_top = 8.0
        if self.is_expanded:
            sprite_x = 0
            sprite_y = max(pad_top, 150 - target_h - 4 + pad_top) + dy
            ground_x, ground_y, ground_w, ground_h = 10, 150 - 9 + pad_top, 108, 9
            prop_x, prop_y, prop_w, prop_h = 100, 150 - 37 - 37 + pad_top, 30, 37
        elif self.is_narrow:
            sprite_x = 0
            sprite_y = pad_top - 1 + dy
            ground_x, ground_y, ground_w, ground_h = 6, pad_top + int(target_h - 4), 62, 7
            prop_x, prop_y, prop_w, prop_h = 58, pad_top + int(target_h - 40), 21, 26
        else:
            # Desktop compact: 104px sprite, top -1px (+pad_top), ground 82x7 under feet, prop 26x32 at left 78
            sprite_x = 0
            sprite_y = pad_top - 1 + dy
            ground_x, ground_y, ground_w, ground_h = 10, pad_top + int(target_h - 6), 82, 7
            prop_x, prop_y, prop_w, prop_h = 78, pad_top + int(target_h - 42), 26, 32

        # 1. Ground ellipse
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tokens.floor)
        p.drawEllipse(QRectF(ground_x, ground_y, ground_w, ground_h))

        # 2. RAT sprite
        p.save()
        if rot != 0.0:
            center_x = sprite_x + target_w * 0.55
            center_y = sprite_y + target_h * 0.88
            p.translate(center_x, center_y)
            p.rotate(rot)
            p.translate(-center_x, -center_y)

        scaled_sprite = self._sprite_raw.scaled(
            target_w, target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        p.drawPixmap(int(sprite_x), int(sprite_y), scaled_sprite)
        p.restore()

        # 3. Prop (notepad / calc / file) rotated 7°
        p.save()
        p.translate(prop_x + prop_w / 2, prop_y + prop_h / 2)
        p.rotate(7.0 + rot)
        p.translate(-prop_w / 2, -prop_h / 2)

        prop_rect = QRectF(0, 0, prop_w, prop_h)
        p.setBrush(tokens.user)
        p.setPen(QPen(tokens.user_line, 1))
        p.drawRoundedRect(prop_rect, 4, 4)

        # Prop icon
        p.setPen(QPen(tokens.accent, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self.prop_kind == "file":
            # File icon
            fx, fy, fw, fh = prop_w * 0.25, prop_h * 0.25, prop_w * 0.5, prop_h * 0.5
            p.drawRect(QRectF(fx, fy, fw, fh))
            p.drawLine(QPointF(fx + 2, fy + fh * 0.4), QPointF(fx + fw - 2, fy + fh * 0.4))
            p.drawLine(QPointF(fx + 2, fy + fh * 0.7), QPointF(fx + fw - 2, fy + fh * 0.7))
        elif self.prop_kind == "calculation":
            # Calculator grid
            fx, fy, fw, fh = prop_w * 0.22, prop_h * 0.22, prop_w * 0.56, prop_h * 0.56
            p.drawRect(QRectF(fx, fy, fw, fh))
            p.drawLine(QPointF(fx + 2, fy + 4), QPointF(fx + fw - 2, fy + 4))
            p.drawPoint(QPointF(fx + fw * 0.35, fy + fh * 0.65))
            p.drawPoint(QPointF(fx + fw * 0.7, fy + fh * 0.65))
        else:
            # Notebook lines + pencil tip
            for row in range(3):
                ry = prop_h * 0.28 + row * (prop_h * 0.18)
                p.drawLine(QPointF(prop_w * 0.22, ry), QPointF(prop_w * 0.78, ry))
        p.restore()
        p.end()


# =========================================================================
# 2. RAT SPEECH BUBBLE
# =========================================================================
class WorkbenchRatBubble(QWidget):
    """
    Paper-colored speech bubble with tail pointing back toward RAT.
    Tail at left -6px, top min(28px, 100% - 22px).
    Corners 14, 14, 14, 5 (compact) / 18, 18, 18, 7 (expanded).
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchRatBubble")
        self.is_expanded = False
        self.is_error = False

        self._full_reply = ""
        self._copy_text = ""
        self.has_reply = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 8, 12, 8)
        self.layout.setSpacing(4)

        # Action row for read-full / copy (used by tests and reading mode)
        self.action_row = QWidget(self)
        ar_layout = QHBoxLayout(self.action_row)
        ar_layout.setContentsMargins(0, 0, 0, 0)
        ar_layout.setSpacing(6)
        ar_layout.addStretch()

        action_style = """
            QPushButton {
                background: transparent; border: none; border-radius: 4px;
                color: #616b5c; font-size: 11px; padding: 1px 4px;
            }
            QPushButton:hover { background: #f2f3eb; color: #30382f; }
        """
        self.btn_copy = QPushButton("Sao chép", self.action_row)
        self.btn_copy.setStyleSheet(action_style)
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_copy.hide()
        ar_layout.addWidget(self.btn_copy)

        self.btn_hist = QPushButton("Đọc hết", self.action_row)
        self.btn_hist.setStyleSheet(action_style)
        self.btn_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hist.clicked.connect(self._on_read_full_clicked)
        self.btn_hist.hide()
        ar_layout.addWidget(self.btn_hist)

        self.layout.addWidget(self.action_row)
        self.action_row.hide()

        self.dialogue = QLabel(self)
        self.dialogue.setObjectName("WorkbenchRatText")
        self.dialogue.setWordWrap(True)
        self.dialogue.setTextFormat(Qt.TextFormat.PlainText)
        self.dialogue.setStyleSheet("QLabel { background: transparent; border: none; }")
        self.layout.addWidget(self.dialogue)

        self._sync_font()
        self.reset_welcome()

    def _sync_font(self) -> None:
        tokens = WorkbenchTokens.get()
        size = 14 if self.is_expanded else 13
        color = tokens.error_hex if self.is_error else tokens.ink_hex
        self.dialogue.setStyleSheet(f"""
            QLabel#WorkbenchRatText {{
                font-family: {FONT_FAMILY};
                font-size: {size}px;
                line-height: 1.6;
                color: {color};
                background: transparent;
                border: none;
            }}
        """)

    def set_presentation(self, expanded: bool) -> None:
        if self.is_expanded != expanded:
            self.is_expanded = expanded
            pad_v = 14 if expanded else 8
            pad_h = 18 if expanded else 12
            self.layout.setContentsMargins(pad_h + 4, pad_v, pad_h, pad_v)
            self._sync_font()
            self.update()

    @property
    def has_reply(self) -> bool:
        return bool(self._copy_text.strip())

    @has_reply.setter
    def has_reply(self, val: bool) -> None:
        if not val:
            self._copy_text = ""

    def _fit_reply(self, text: str) -> str:
        """Fit a preview to the bubble, retaining the full reply separately."""
        fm = self.dialogue.fontMetrics()

        def fits(candidate: str) -> bool:
            rect = fm.boundingRect(QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, candidate)
            return rect.height() <= 66 and rect.width() <= 420

        if fits(text):
            return text
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if fits(text[:mid].rstrip() + "…"):
                low = mid
            else:
                high = mid - 1
        prefix = text[:low].rstrip()
        boundary = prefix.rfind(" ")
        if boundary > len(prefix) * 0.7:
            prefix = prefix[:boundary].rstrip()
        return prefix + "…"

    def set_reply(
        self,
        text: str,
        header: Optional[str] = None,
        *,
        copy_text: Optional[str] = None,
        has_details: bool = False,
        file_summary: bool = False,
        **kwargs: Any,
    ) -> None:
        self._full_reply = text
        self._copy_text = text if copy_text is None else copy_text
        self._has_details = has_details
        self._file_summary = file_summary

        preview_source = re.sub(r"\s*\n\s*", " ", text)
        preview = self._fit_reply(preview_source)
        self._truncated = preview != preview_source
        self.dialogue.setText(preview)

        has_rep = bool(self._copy_text.strip())
        self.btn_copy.setVisible(has_rep and not file_summary)
        show_hist = has_rep and not file_summary and (self._truncated or self._has_details or self.is_expanded)
        self.btn_hist.setVisible(show_hist)
        self.btn_hist.setText("Thu gọn" if self.is_expanded else "Xem kết quả" if has_details else "Đọc hết")
        self.action_row.setVisible(self.btn_copy.isVisible() or self.btn_hist.isVisible())
        self.update()

    def stream_token(self, token: str) -> None:
        self.set_reply(self._copy_text + token, "Đang gõ")

    def _on_copy_clicked(self) -> None:
        if not self.has_reply or not self._copy_text:
            return
        QApplication.clipboard().setText(self._copy_text)

    def _on_read_full_clicked(self) -> None:
        w = self.window()
        if hasattr(w, "toggle_expand"):
            w.toggle_expand()

    def set_error(self, is_error: bool) -> None:
        if self.is_error != is_error:
            self.is_error = is_error
            self._sync_font()
            self.update()

    def text(self) -> str:
        return self._copy_text or self._full_reply or self.dialogue.text()

    def reset_welcome(self) -> None:
        self._full_reply = ""
        self._copy_text = ""
        self._truncated = False
        self._has_details = False
        self._file_summary = False
        self.btn_copy.hide()
        self.btn_hist.hide()
        self.action_row.hide()
        self.dialogue.setText("Mình ở đây. Bạn cứ nói điều đang cần, rồi mình cùng làm nhé.")
        self.update()

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = WorkbenchTokens.get()

        w, h = self.width(), self.height()
        r = 18.0 if self.is_expanded else 14.0
        r_bl = 7.0 if self.is_expanded else 5.0

        # Body rect inset slightly for tail on left
        body_rect = QRectF(6.0, 1.0, w - 7.0, h - 2.0)
        tail_y = min(42.0 if self.is_expanded else 28.0, max(10.0, h - 22.0))

        path = QPainterPath()
        path.moveTo(body_rect.left() + r, body_rect.top())
        path.lineTo(body_rect.right() - r, body_rect.top())
        path.quadTo(body_rect.right(), body_rect.top(), body_rect.right(), body_rect.top() + r)
        path.lineTo(body_rect.right(), body_rect.bottom() - r)
        path.quadTo(body_rect.right(), body_rect.bottom(), body_rect.right() - r, body_rect.bottom())
        path.lineTo(body_rect.left() + r_bl, body_rect.bottom())
        path.quadTo(body_rect.left(), body_rect.bottom(), body_rect.left(), body_rect.bottom() - r_bl)
        # Left edge up to bottom of tail
        path.lineTo(body_rect.left(), tail_y + 11.0)
        # Tail point pointing left toward RAT
        path.lineTo(body_rect.left() - 5.5, tail_y + 5.5)
        path.lineTo(body_rect.left(), tail_y)
        path.lineTo(body_rect.left(), body_rect.top() + r)
        path.quadTo(body_rect.left(), body_rect.top(), body_rect.left() + r, body_rect.top())
        path.closeSubpath()

        p.fillPath(path, tokens.paper)
        p.strokePath(path, QPen(tokens.line, 1))
        p.end()


# =========================================================================
# 3. USER COMPOSER BUBBLE
# =========================================================================
class WorkbenchUserBubble(QWidget):
    """
    Softly green user speech bubble with downward tail on bottom-right.
    Corners 14, 14, 5, 14 (compact) / 18, 18, 7, 18 (expanded).
    Focus accents border and soft 3px halo.
    """
    def __init__(self, composer: ChatComposer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchUserBubble")
        self.composer = composer
        self.is_expanded = False
        self.is_focused = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(13, 9, 13, 13)
        self.layout.setSpacing(0)
        self.layout.addWidget(composer)

        self._sync_composer_style()
        composer.installEventFilter(self)

    def set_presentation(self, expanded: bool, narrow: bool = False) -> None:
        if self.is_expanded != expanded or getattr(self, "is_narrow", False) != narrow:
            self.is_expanded = expanded
            self.is_narrow = narrow
            pad_v = 14 if expanded else 9
            pad_h = 18 if expanded else 13
            if narrow:
                pad_v, pad_h = 15, 16
            self.layout.setContentsMargins(pad_h, pad_v, pad_h, 13)
            self._sync_composer_style(narrow)
            self.update()

    def _sync_composer_style(self, narrow: bool = False) -> None:
        tokens = WorkbenchTokens.get()
        size = 16 if narrow else 15
        self.composer.setStyleSheet(f"""
            QPlainTextEdit {{
                font-family: {FONT_FAMILY};
                font-size: {size}px;
                line-height: 1.65;
                color: {tokens.ink_hex};
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }}
        """)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.composer:
            if event.type() == QEvent.Type.FocusIn:
                self.is_focused = True
                self.update()
            elif event.type() == QEvent.Type.FocusOut:
                self.is_focused = False
                self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = WorkbenchTokens.get()

        w, h = self.width(), self.height()
        r = 18.0 if self.is_expanded else 14.0
        r_br = 7.0 if self.is_expanded else 5.0

        # Body rect inset for bottom tail
        body_rect = QRectF(2.0, 1.0, w - 4.0, h - 7.0)
        tail_right = body_rect.right() - 22.0
        tail_left = tail_right - 12.0

        path = QPainterPath()
        path.moveTo(body_rect.left() + r, body_rect.top())
        path.lineTo(body_rect.right() - r, body_rect.top())
        path.quadTo(body_rect.right(), body_rect.top(), body_rect.right(), body_rect.top() + r)
        path.lineTo(body_rect.right(), body_rect.bottom() - r_br)
        path.quadTo(body_rect.right(), body_rect.bottom(), body_rect.right() - r_br, body_rect.bottom())
        # Bottom edge to right of tail
        path.lineTo(tail_right, body_rect.bottom())
        # Tail point pointing down
        path.lineTo(tail_right - 4.0, body_rect.bottom() + 5.5)
        path.lineTo(tail_left, body_rect.bottom())
        # Continue to bottom-left corner
        path.lineTo(body_rect.left() + r, body_rect.bottom())
        path.quadTo(body_rect.left(), body_rect.bottom(), body_rect.left(), body_rect.bottom() - r)
        path.lineTo(body_rect.left(), body_rect.top() + r)
        path.quadTo(body_rect.left(), body_rect.top(), body_rect.left() + r, body_rect.top())
        path.closeSubpath()

        # Focus halo (soft 3px halo with 16% opacity)
        if self.is_focused:
            halo_color = QColor(tokens.focus.red(), tokens.focus.green(), tokens.focus.blue(), 41)
            p.strokePath(path, QPen(halo_color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

        p.fillPath(path, tokens.user)
        border_color = tokens.focus if self.is_focused else tokens.user_line
        p.strokePath(path, QPen(border_color, 1))
        p.end()


# =========================================================================
# 4. WORKBENCH CANVAS (Paper card above stage)
# =========================================================================
class WorkbenchCanvas(QFrame):
    """
    Work canvas card with brand chrome, work title, duration badge, content rows, and footer.
    Elevation: 0 5px 18px shadow.
    """
    action_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.is_expanded = False
        self.is_narrow = False
        self.kind = "empty"  # "empty", "custom", "plan", etc.

        # Plan state (for optional fixtures)
        self.minutes: List[int] = []
        self.plan_rows: List[Any] = []
        self.edited = False
        self.long_text = False

        self._init_ui()
        self.set_presentation(False)

    def _init_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 5)
        shadow.setColor(WorkbenchTokens.get().shadow)
        self.setGraphicsEffect(shadow)

        self.canvas_layout = QVBoxLayout(self)
        self.canvas_layout.setContentsMargins(16, 8, 16, 5)
        self.canvas_layout.setSpacing(4)

        # 1. Chrome row
        self.chrome_row = QWidget(self)
        cr_layout = QHBoxLayout(self.chrome_row)
        cr_layout.setContentsMargins(0, 2, 0, 4)
        cr_layout.setSpacing(8)

        self.brand_lbl = QLabel(self.chrome_row)
        self.brand_lbl.setObjectName("WorkbenchBrand")
        cr_layout.addWidget(self.brand_lbl)
        cr_layout.addStretch()

        self.mode_lbl = QLabel("Workbench", self.chrome_row)
        self.mode_lbl.setObjectName("WorkbenchMode")
        cr_layout.addWidget(self.mode_lbl)
        self.canvas_layout.addWidget(self.chrome_row)

        # 2. Heading row
        self.heading_row = QWidget(self)
        hr_layout = QHBoxLayout(self.heading_row)
        hr_layout.setContentsMargins(0, 0, 0, 3)
        hr_layout.setSpacing(12)

        self.heading_left = QWidget(self.heading_row)
        hl_layout = QVBoxLayout(self.heading_left)
        hl_layout.setContentsMargins(0, 0, 0, 0)
        hl_layout.setSpacing(2)

        self.eyebrow_lbl = QLabel("", self.heading_left)
        self.eyebrow_lbl.setObjectName("WorkbenchEyebrow")
        self.eyebrow_lbl.hide()
        hl_layout.addWidget(self.eyebrow_lbl)

        self.title_lbl = QLabel("Không gian làm việc", self.heading_left)
        self.title_lbl.setObjectName("WorkbenchTitle")
        self.title_lbl.setWordWrap(True)
        hl_layout.addWidget(self.title_lbl)
        hr_layout.addWidget(self.heading_left, 1)

        self.duration_badge = QLabel("", self.heading_row)
        self.duration_badge.setObjectName("WorkbenchDuration")
        self.duration_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_badge.hide()
        hr_layout.addWidget(self.duration_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.canvas_layout.addWidget(self.heading_row)

        # 3. Dynamic content container
        self.content_container = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.canvas_layout.addWidget(self.content_container, 1)

        # 4. Canvas footer (expanded only)
        self.foot_row = QWidget(self)
        fr_layout = QHBoxLayout(self.foot_row)
        fr_layout.setContentsMargins(0, 10, 0, 4)
        fr_layout.setSpacing(8)

        self.status_lbl = QLabel("", self.foot_row)
        self.status_lbl.setObjectName("WorkbenchStatus")
        self.status_lbl.hide()
        fr_layout.addWidget(self.status_lbl)
        fr_layout.addStretch()

        self.context_lbl = QLabel("", self.foot_row)
        self.context_lbl.setObjectName("WorkbenchContext")
        self.context_lbl.hide()
        fr_layout.addWidget(self.context_lbl)
        self.canvas_layout.addWidget(self.foot_row)
        self.foot_row.hide()

        self.render_content()

    def set_presentation(self, expanded: bool, narrow: bool = False) -> None:
        self.is_expanded = expanded
        self.is_narrow = narrow
        tokens = WorkbenchTokens.get()

        pad_top = 12 if expanded else 8
        pad_side = 28 if expanded else (14 if narrow else 16)
        pad_bottom = 0 if expanded else 5
        self.canvas_layout.setContentsMargins(pad_side, pad_top, pad_side, pad_bottom)

        radius = 18 if expanded else 16
        self.setStyleSheet(f"""
            QFrame#WorkbenchCanvas {{
                background-color: {tokens.paper_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: {radius}px;
            }}
        """)

        # Chrome
        self.brand_lbl.setText(f'<span style="font-size:{20 if expanded else 18}px; font-weight:bold; color:{tokens.ink_hex};">rat</span><span style="font-size:{20 if expanded else 18}px; font-weight:bold; color:{tokens.accent_hex};">.</span>')
        self.brand_lbl.setStyleSheet(f"font-family: {FONT_FAMILY}; border: none;")
        self.mode_lbl.setText("Đọc chi tiết" if expanded else "Workbench")
        self.mode_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY};")

        # Eyebrow (hidden in compact)
        self.eyebrow_lbl.setVisible(expanded and bool(self.eyebrow_lbl.text()))
        self.eyebrow_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-weight: 500; letter-spacing: 0.7px; font-family: {FONT_FAMILY};")

        # Title
        t_size = 24 if expanded else (18 if narrow else 20)
        self.title_lbl.setStyleSheet(f"color: {tokens.ink_hex}; font-size: {t_size}px; font-weight: 500; font-family: {FONT_FAMILY};")

        # Duration
        d_pad_v = 6 if expanded else 4
        d_pad_h = 12 if expanded else 9
        self.duration_badge.setVisible(bool(self.duration_badge.text().strip()))
        self.duration_badge.setStyleSheet(f"""
            background-color: {tokens.soft_hex};
            color: {tokens.accent_hex};
            border-radius: 14px;
            padding: {d_pad_v}px {d_pad_h}px;
            font-size: 12px;
            font-weight: 500;
            font-family: {FONT_FAMILY};
        """)

        # Foot (hidden in compact)
        has_foot = bool(self.status_lbl.text().strip() or self.context_lbl.text().strip())
        self.foot_row.setVisible(expanded and has_foot)
        self.foot_row.setStyleSheet(f"border-top: 1px solid {tokens.line_hex};")
        self.status_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY}; border: none;")
        self.context_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY}; border: none;")

        if getattr(self, "embedded_stack", None) is None:
            self.render_content()

    def set_work(
        self,
        title: str,
        *,
        eyebrow: Optional[str] = None,
        badge: Optional[str] = None,
        status: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self.title_lbl.setText(title or "Không gian làm việc")
        if eyebrow:
            self.eyebrow_lbl.setText(eyebrow)
            self.eyebrow_lbl.setVisible(self.is_expanded)
        else:
            self.eyebrow_lbl.setText("")
            self.eyebrow_lbl.hide()

        if badge:
            self.duration_badge.setText(badge)
            self.duration_badge.setVisible(True)
        else:
            self.duration_badge.setText("")
            self.duration_badge.hide()

        if status:
            self.status_lbl.setText(status)
            self.status_lbl.setVisible(self.is_expanded)
        else:
            self.status_lbl.setText("")
            self.status_lbl.hide()

        if context:
            self.context_lbl.setText(context)
            self.context_lbl.setVisible(self.is_expanded)
        else:
            self.context_lbl.setText("")
            self.context_lbl.hide()

        has_foot = bool(self.status_lbl.text().strip() or self.context_lbl.text().strip())
        self.foot_row.setVisible(self.is_expanded and has_foot)
        self.update()

    def reset_work(self) -> None:
        self.kind = "empty"
        self.minutes = []
        self.plan_rows = []
        self.set_work("Không gian làm việc")
        self.duration_badge.setText("")
        self.duration_badge.hide()
        self.eyebrow_lbl.setText("")
        self.eyebrow_lbl.hide()
        self.status_lbl.setText("")
        self.status_lbl.hide()
        self.context_lbl.setText("")
        self.context_lbl.hide()
        self.foot_row.hide()

    def set_fixture_plan(self, minutes: Optional[List[int]] = None, edited: bool = False) -> None:
        """Configure study plan fixture for test specimens and visual inspections."""
        self.kind = "plan"
        self.minutes = list(minutes) if minutes is not None else [20, 55, 15]
        self.edited = edited
        self.plan_rows = [
            ("01", "Ôn lại phần đang học", "Nhặt lại ý chính, đánh dấu chỗ còn vướng.", f"{self.minutes[0]} phút"),
            ("02", "Làm bài tập", "Tập trung vào một dạng bài cho trọn vẹn.", f"{self.minutes[1]} phút"),
            ("03", "Ôn tập nhanh" if self.edited else "Ghi lại điều cần hỏi",
             "Tự nhắc lại ý chính trước khi kết thúc." if self.edited else "Để buổi học sau bắt đầu dễ hơn.",
             f"{self.minutes[2]} phút"),
        ]
        self.set_work("Buổi học tối nay", eyebrow="BẢN NHÁP CỦA BẠN", badge=f"{sum(self.minutes)} phút", status="• Có thể chỉnh tiếp", context=f"{len(self.minutes)} phần")
        self.render_content()

    def chrome_height(self) -> int:
        margins = self.canvas_layout.contentsMargins()
        h = margins.top() + margins.bottom()
        spacing = self.canvas_layout.spacing()
        if self.chrome_row.isVisible():
            h += self.chrome_row.sizeHint().height() + spacing
        if self.heading_row.isVisible():
            avail_w = max(400, self.width())
            hh = self.heading_row.heightForWidth(avail_w)
            if hh <= 0:
                hh = self.heading_row.height() if self.heading_row.height() > 0 else self.heading_row.sizeHint().height()
            h += hh + spacing
        if hasattr(self, "foot_row") and self.foot_row.isVisible():
            h += self.foot_row.sizeHint().height() + spacing
        return max(74, h)

    def set_embedded_stack(self, stack: QWidget) -> None:
        self.embedded_stack = stack
        self.kind = "custom"
        self.render_content()

    def set_work_kind(self, kind: str) -> None:
        self.kind = kind
        self.render_content()

    def render_content(self) -> None:
        if getattr(self, "embedded_stack", None) is not None:
            while self.content_layout.count():
                item = self.content_layout.takeAt(0)
                w = item.widget()
                if w and w is not self.embedded_stack:
                    w.setParent(None)
                    w.deleteLater()
            if self.content_layout.indexOf(self.embedded_stack) < 0:
                self.content_layout.addWidget(self.embedded_stack)
            self.duration_badge.setVisible(bool(self.duration_badge.text().strip()))
            return

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        tokens = WorkbenchTokens.get()
        if self.kind == "plan" and self.minutes:
            total_mins = sum(self.minutes)
            self.duration_badge.setText(f"{total_mins} phút")
            self.duration_badge.setVisible(True)
        elif self.kind != "custom":
            self.duration_badge.setText("")
            self.duration_badge.setVisible(False)

        if self.kind == "empty":
            self.title_lbl.setText("Không gian làm việc")
            self.eyebrow_lbl.setText("")
            self.eyebrow_lbl.hide()
            self.duration_badge.setText("")
            self.duration_badge.hide()
            self.status_lbl.setText("")
            self.status_lbl.hide()
            self.context_lbl.setText("")
            self.context_lbl.hide()
            self.foot_row.hide()
            return

        # Render explicit typed rows if provided by caller/fixture
        rows = getattr(self, "plan_rows", None)
        if self.kind == "plan" and rows:
            row_pad = 14 if self.is_expanded else 5
            for i, (order, title, desc, mins) in enumerate(rows):
                row_widget = QWidget(self.content_container)
                border_bottom = f"border-bottom: 1px solid {tokens.line_hex};" if i < len(rows) - 1 else "border-bottom: none;"
                row_widget.setStyleSheet(f"background: transparent; {border_bottom}")
                r_layout = QHBoxLayout(row_widget)
                r_layout.setContentsMargins(0, row_pad, 0, row_pad)
                r_layout.setSpacing(10 if not self.is_expanded else 16)

                order_lbl = QLabel(order, row_widget)
                order_lbl.setFixedWidth(20 if not self.is_expanded else 27)
                order_lbl.setStyleSheet(f"color: {tokens.accent_hex}; font-size: 12px; font-weight: 500; font-family: {FONT_FAMILY}; border: none;")
                r_layout.addWidget(order_lbl, 0, Qt.AlignmentFlag.AlignTop if self.is_expanded else Qt.AlignmentFlag.AlignVCenter)

                mid_box = QWidget(row_widget)
                mid_layout = QVBoxLayout(mid_box)
                mid_layout.setContentsMargins(0, 0, 0, 0)
                mid_layout.setSpacing(2)
                title_lbl = QLabel(title, mid_box)
                title_lbl.setStyleSheet(f"color: {tokens.ink_hex}; font-size: {15 if self.is_expanded else 14}px; font-weight: 500; font-family: {FONT_FAMILY}; border: none;")
                mid_layout.addWidget(title_lbl)

                if self.is_expanded and desc:
                    desc_lbl = QLabel(desc, mid_box)
                    desc_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 13px; font-family: {FONT_FAMILY}; border: none;")
                    desc_lbl.setWordWrap(True)
                    mid_layout.addWidget(desc_lbl)
                r_layout.addWidget(mid_box, 1)

                mins_lbl = QLabel(mins, row_widget)
                mins_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: {13 if self.is_expanded else 12}px; font-family: {FONT_FAMILY}; border: none;")
                r_layout.addWidget(mins_lbl, 0, Qt.AlignmentFlag.AlignTop if self.is_expanded else Qt.AlignmentFlag.AlignVCenter)

                self.content_layout.addWidget(row_widget)



# =========================================================================
# 5. USER LANE (Green bubble + foot)
# =========================================================================
class WorkbenchUserLane(QWidget):
    """
    User dialogue lane containing:
    - Last user turn (expanded only)
    - "Bạn" label (expanded only)
    - Green composer bubble
    - Composer footer with state and keyboard hint
    """
    def __init__(self, composer: ChatComposer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchUserLane")
        self.composer = composer
        self.is_expanded = False
        self.is_narrow = False
        self.phase = "done"  # "done", "working", "error", "cancelled", etc.
        self._last_user_query = ""

        self.lane_layout = QVBoxLayout(self)
        self.lane_layout.setContentsMargins(0, 0, 0, 0)
        self.lane_layout.setSpacing(0)

        # 1. Last user turn (expanded only)
        self.last_turn_box = QWidget(self)
        lt_layout = QVBoxLayout(self.last_turn_box)
        lt_layout.setContentsMargins(60, 4, 0, 8)
        lt_layout.setSpacing(2)
        self.last_label = QLabel("Bạn vừa nói", self.last_turn_box)
        self.last_text = QLabel("", self.last_turn_box)
        self.last_text.setWordWrap(True)
        lt_layout.addWidget(self.last_label, 0, Qt.AlignmentFlag.AlignRight)
        lt_layout.addWidget(self.last_text, 0, Qt.AlignmentFlag.AlignRight)
        self.lane_layout.addWidget(self.last_turn_box)
        self.last_turn_box.hide()

        # 2. Speaker label "Bạn" (expanded only)
        self.speaker_label = QLabel("Bạn", self)
        self.speaker_label.setObjectName("WorkbenchSpeakerUser")
        self.lane_layout.addWidget(self.speaker_label, 0, Qt.AlignmentFlag.AlignRight)
        self.speaker_label.hide()

        # 3. User composer bubble
        self.bubble = WorkbenchUserBubble(composer, self)
        self.lane_layout.addWidget(self.bubble)

        # 4. Composer foot
        self.foot = QWidget(self)
        self.foot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.foot.setFixedHeight(24)
        f_layout = QHBoxLayout(self.foot)
        f_layout.setContentsMargins(4, 4, 4, 0)
        f_layout.setSpacing(8)

        self.input_state_lbl = QLabel("Nói “xem chi tiết”", self.foot)
        self.input_state_lbl.setObjectName("WorkbenchInputState")
        self.input_state_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        f_layout.addWidget(self.input_state_lbl, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f_layout.addStretch(1)

        self.kbd_hint_lbl = QLabel("↵ gửi", self.foot)
        self.kbd_hint_lbl.setObjectName("WorkbenchKbdHint")
        self.kbd_hint_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.kbd_hint_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        f_layout.addWidget(self.kbd_hint_lbl, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lane_layout.addWidget(self.foot)

        self.composer.textChanged.connect(self._sync_foot_state)
        self.set_presentation(False)

    def set_presentation(self, expanded: bool, narrow: bool = False) -> None:
        self.is_expanded = expanded
        self.is_narrow = narrow
        tokens = WorkbenchTokens.get()

        # In dialogue region, column 1 already provides the 120px / 152px offset
        self.lane_layout.setContentsMargins(0, 0, 0, 0)
        self.bubble.set_presentation(expanded, narrow)

        self.last_label.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY};")
        self.last_text.setStyleSheet(f"color: {tokens.ink_hex}; font-size: 13px; font-family: {FONT_FAMILY};")
        self.speaker_label.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY}; margin-bottom: 4px; margin-right: 16px;")

        self.last_turn_box.setVisible(expanded and bool(self._last_user_query))
        self.speaker_label.setVisible(expanded)

        self.input_state_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY};")
        self.kbd_hint_lbl.setStyleSheet(f"color: {tokens.muted_hex}; font-size: 12px; font-family: {FONT_FAMILY};")
        if narrow:
            self.kbd_hint_lbl.hide()
        else:
            self.kbd_hint_lbl.show()

        self._sync_foot_state()

    def set_last_user_query(self, query: str) -> None:
        self._last_user_query = query
        self.last_text.setText(query)
        self.last_turn_box.setVisible(self.is_expanded and bool(query))

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self._sync_foot_state()

    def _sync_foot_state(self) -> None:
        count = len(self.composer.text())
        if count >= 1700:
            self.input_state_lbl.setText(f"{count} / 2.000 ký tự")
        elif self.phase == "working":
            self.input_state_lbl.setText("Gõ tiếp · Esc để dừng")
        elif self.is_expanded:
            self.input_state_lbl.setText("Nói “thu gọn”")
        else:
            self.input_state_lbl.setText("Nói “xem chi tiết”")

        if self.is_expanded:
            self.kbd_hint_lbl.setText("↵ gửi · Shift + ↵ xuống dòng")
        else:
            self.kbd_hint_lbl.setText("↵ gửi")


# =========================================================================
# 6. WORKBENCH DIALOGUE REGION (Stage + User Lane)
# =========================================================================
class WorkbenchDialogueRegion(QWidget):
    """
    Coordinated layout for Actor, RAT speech bubble, and User lane.
    Handles seamless desktop alignment and narrow reflow.
    """
    def __init__(self, composer: ChatComposer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchDialogueRegion")
        self.is_expanded = False
        self.is_narrow = False

        self.actor = WorkbenchActorWidget(self)
        self.rat_bubble = WorkbenchRatBubble(self)
        self.user_lane = WorkbenchUserLane(composer, self)

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)

        self._apply_layout()

    def set_presentation(self, expanded: bool, narrow: bool = False) -> None:
        self.is_expanded = expanded
        self.is_narrow = narrow
        self.actor.set_presentation(expanded, narrow)
        self.rat_bubble.set_presentation(expanded)
        self.user_lane.set_presentation(expanded, narrow)
        self._apply_layout()

    def _apply_layout(self) -> None:
        while self.grid.count():
            self.grid.takeAt(0)

        if self.is_narrow:
            # Narrow: Stage on row 0 (actor col 0, rat_bubble col 1), user lane on row 1 (full width)
            self.grid.addWidget(self.actor, 0, 0, 1, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.grid.addWidget(self.rat_bubble, 0, 1, 1, 1)
            self.grid.addWidget(self.user_lane, 1, 0, 1, 2)
            self.grid.setColumnStretch(0, 0)
            self.grid.setColumnStretch(1, 1)
        else:
            # Desktop: Actor on col 0 spanning rows 0 and 1!
            # Row 0: RAT bubble (col 1)
            # Row 1: User lane (col 1)
            # Both bubbles share left edge at 120px!
            self.grid.addWidget(self.actor, 0, 0, 2, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.grid.addWidget(self.rat_bubble, 0, 1, 1, 1)
            self.grid.addWidget(self.user_lane, 1, 1, 1, 1)
            self.grid.setColumnStretch(0, 0)
            self.grid.setColumnStretch(1, 1)
