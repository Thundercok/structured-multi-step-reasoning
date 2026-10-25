"""
rat.ui.apple_item_delegate — macOS "Liquid Glass" List Item Delegate.
Renders frosted glass selection highlights, specular reflections, and Retina icons.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from PyQt6.QtCore import QFileInfo, QModelIndex, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QFileIconProvider, QStyle, QStyleOptionViewItem, QStyledItemDelegate

from rat.engine.reranker import SearchResultItem
from rat.ui.theme import get_ext_badge_info


class AppleSpotlightDelegate(QStyledItemDelegate):
    """
    Liquid Glass List.Item delegate.
    - 44px row height with frosted glass selection
    - Top specular glass light refraction
    - Crisp primary title (#f9fafb) & secondary subtitle (#9ca3af)
    - Right-aligned translucent accessories
    """

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self.row_height = 44

        # Typography
        self.title_font = QFont(".AppleSystemUIFont", 12)
        self.title_font.setWeight(QFont.Weight.Medium)

        self.sub_font = QFont(".AppleSystemUIFont", 11)
        self.sub_font.setWeight(QFont.Weight.Normal)

        self.accessory_font = QFont(".AppleSystemUIFont", 10)
        self.accessory_font.setWeight(QFont.Weight.Medium)

        self.badge_font = QFont(".AppleSystemUIFont", 8)
        self.badge_font.setWeight(QFont.Weight.Bold)

        self.icon_provider = QFileIconProvider()
        self._icon_cache: Dict[str, Optional[QPixmap]] = {}

    def _get_system_pixmap(self, file_path: str, ext: str) -> Optional[QPixmap]:
        cache_key = ext.lower() if ext else file_path
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        try:
            if file_path and os.path.exists(file_path):
                qicon = self.icon_provider.icon(QFileInfo(file_path))
            else:
                qicon = self.icon_provider.icon(QFileIconProvider.IconType.File)

            if not qicon.isNull():
                pm = qicon.pixmap(22, 22)
                self._icon_cache[cache_key] = pm
                return pm
        except Exception:
            pass

        self._icon_cache[cache_key] = None
        return None

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(option.rect.width(), self.row_height)

    def _draw_compact_badge_icon(self, painter: QPainter, rect: QRectF, bg_color_hex: str, label_text: str) -> None:
        base_color = QColor(bg_color_hex)
        path = QPainterPath()
        path.addRoundedRect(rect, 4.0, 4.0)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(base_color))
        painter.drawPath(path)

        painter.setFont(self.badge_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label_text)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        item: Optional[SearchResultItem] = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = option.rect
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # 1. Skeuomorphic Selection & Hover State
        bg_rect = QRectF(rect.x() + 4, rect.y() + 2, rect.width() - 8, rect.height() - 4)
        if is_selected:
            # Warm paper gold selection with tactile bottom border
            painter.setPen(QPen(QColor("#D9A838"), 1))
            painter.setBrush(QBrush(QColor("#FFF6DD")))
            painter.drawRoundedRect(bg_rect, 7, 7)
            bot_line = QRectF(bg_rect.x() + 4, bg_rect.bottom() - 1, bg_rect.width() - 8, 1)
            painter.fillRect(bot_line, QColor("#CFA02E"))
        elif is_hover:
            painter.setPen(QPen(QColor("#E2D8C8"), 1))
            painter.setBrush(QBrush(QColor("#FAF6EE")))
            painter.drawRoundedRect(bg_rect, 7, 7)

        # 2. Leading Icon (22x22px)
        ext = getattr(item, "file_ext", "")
        file_path = getattr(item, "file_path", "")
        icon_x = rect.x() + 12
        icon_y = rect.y() + (rect.height() - 22) / 2

        if ext in [".ai", ".calc", ".map", ".app"]:
            badge_info = get_ext_badge_info(ext)
            b_rect = QRectF(icon_x, icon_y, 22, 22)
            self._draw_compact_badge_icon(painter, b_rect, badge_info["bg"], badge_info["label"])
        else:
            sys_pm = self._get_system_pixmap(file_path, ext)
            if sys_pm and not sys_pm.isNull():
                painter.drawPixmap(int(icon_x), int(icon_y), 22, 22, sys_pm)
            else:
                badge_info = get_ext_badge_info(ext)
                b_rect = QRectF(icon_x, icon_y, 22, 22)
                self._draw_compact_badge_icon(painter, b_rect, badge_info["bg"], badge_info["label"])

        # 3. Typography
        text_x = rect.x() + 44
        avail_width = max(60, rect.width() - 44 - 90)

        # Title: Crisp dark ink (#1c1917)
        file_name = getattr(item, "file_name", "") or "Không rõ tên"
        painter.setFont(self.title_font)
        painter.setPen(QColor("#1c1917"))
        fm_title = QFontMetrics(self.title_font)
        elided_title = fm_title.elidedText(file_name, Qt.TextElideMode.ElideRight, int(avail_width))
        painter.drawText(int(text_x), int(rect.y() + 17), elided_title)

        # Subtitle: Muted ink (#78716c)
        subtitle = getattr(item, "file_path", "") or ""
        mod_time = getattr(item, "modified_formatted", "") or ""
        sub_text = f"{subtitle}  •  {mod_time}" if mod_time else subtitle

        painter.setFont(self.sub_font)
        painter.setPen(QColor("#78716c"))
        fm_sub = QFontMetrics(self.sub_font)
        elided_path = fm_sub.elidedText(sub_text, Qt.TextElideMode.ElideMiddle, int(avail_width))
        painter.drawText(int(text_x), int(rect.y() + 33), elided_path)

        # 4. Right Accessories (Tactile sketch badge)
        score_val = int(getattr(item, "score", 0))
        if score_val > 10 and score_val <= 100:
            tag_str = "Khớp 🧀" if score_val >= 70 else "Liên quan"
            bg_acc = QColor("#FEF3C7")
            fg_acc = QColor("#92400E")
            border_acc = QColor("#FCD34D")
        else:
            tag_str = getattr(item, "file_size_formatted", "") or ""
            bg_acc = QColor("#F5EFEB")
            fg_acc = QColor("#574E45")
            border_acc = QColor("#E0D6C8")

        if tag_str:
            fm_acc = QFontMetrics(self.accessory_font)
            text_w = fm_acc.horizontalAdvance(tag_str)
            acc_w = max(46, text_w + 14)
            acc_h = 19
            acc_x = rect.x() + rect.width() - acc_w - 12
            acc_y = rect.y() + (rect.height() - acc_h) / 2
            acc_rect = QRectF(acc_x, acc_y, acc_w, acc_h)

            painter.setPen(QPen(border_acc, 1))
            painter.setBrush(QBrush(bg_acc))
            painter.drawRoundedRect(acc_rect, 4, 4)

            painter.setFont(self.accessory_font)
            painter.setPen(fg_acc)
            painter.drawText(acc_rect, Qt.AlignmentFlag.AlignCenter, tag_str)

        painter.restore()
