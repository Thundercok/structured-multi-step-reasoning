import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF
from PyQt6.QtGui import (QPainter, QPainterPath, QColor, QPen, QLinearGradient, 
                         QFont, QBrush)
from rat.ui.chat_stream import get_mascot_pixmap

class ArtisticSpeechBubble(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(22, 10, 16, 10)
        self.main_layout.setSpacing(6)
        
        # 1. Header Meta Row (clean, no distracting buttons)
        header = QHBoxLayout()
        header.setSpacing(6)
        
        self.dot = QLabel("●")
        self.dot.setStyleSheet("font-size: 8px; color: #F59E0B; margin-top: 1px;")
        header.addWidget(self.dot)
        
        self.name_tag = QLabel("CHUỘT")
        self.name_tag.setStyleSheet("font-size: 10px; font-weight: 800; color: #8C7E6F; letter-spacing: 1.2px;")
        header.addWidget(self.name_tag)
        
        self.context_pill = QLabel("Sẵn sàng")
        self.context_pill.setStyleSheet("font-size: 10px; font-weight: 600; color: #6B7280; background: #F3F4F6; border-radius: 5px; padding: 1px 7px;")
        header.addWidget(self.context_pill)
        
        header.addStretch()
        self.main_layout.addLayout(header)
        
        # 2. Main Dialogue Text
        self.dialogue = QLabel("Nghe đây. Cần tìm gì?")
        self.dialogue.setStyleSheet("font-size: 13.5px; font-weight: 550; color: #1E293B; line-height: 1.45;")
        self.dialogue.setWordWrap(True)
        self.main_layout.addWidget(self.dialogue)
        
    def set_reply(self, text: str, context_text: str = "Trả lời"):
        self.dialogue.setText(text)
        self.context_pill.setText(context_text)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        tail_w = 12
        tail_h = 14
        tail_y = 30
        
        w = self.width() - 4
        h = self.height() - 4
        r = 14
        
        path = QPainterPath()
        path.moveTo(2 + tail_w + r, 2)
        path.lineTo(2 + w - r, 2)
        path.quadTo(2 + w, 2, 2 + w, 2 + r)
        path.lineTo(2 + w, 2 + h - r)
        path.quadTo(2 + w, 2 + h, 2 + w - r, 2 + h)
        path.lineTo(2 + tail_w + r, 2 + h)
        path.quadTo(2 + tail_w, 2 + h, 2 + tail_w, 2 + h - r)
        
        # Organic smooth bezier tail pointing to Chuột
        path.lineTo(2 + tail_w, tail_y + tail_h)
        tip_x = 2.0
        tip_y = tail_y + tail_h * 0.45
        path.quadTo(2 + tail_w * 0.4, tail_y + tail_h * 0.85, tip_x, tip_y)
        path.quadTo(2 + tail_w * 0.35, tail_y + tail_h * 0.15, 2 + tail_w, tail_y)
        
        path.lineTo(2 + tail_w, 2 + r)
        path.quadTo(2 + tail_w, 2, 2 + tail_w + r, 2)
        path.closeSubpath()
        
        # Soft multi-pass drop shadow
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 24, 16, 12))
        painter.translate(0, 4)
        painter.drawPath(path)
        painter.setBrush(QColor(30, 24, 16, 18))
        painter.translate(0, -2)
        painter.drawPath(path)
        painter.restore()
        
        # Warm porcelain gradient fill
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(255, 255, 255, 252))
        grad.setColorAt(1.0, QColor(252, 250, 247, 248))
        painter.setBrush(QBrush(grad))
        
        painter.setPen(QPen(QColor(40, 30, 20, 22), 1.0))
        painter.drawPath(path)


def create_window():
    win = QWidget()
    win.resize(652, 238)
    win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    win.setStyleSheet("background: transparent;")
    
    # 1. Main container card
    container = QFrame(win)
    container.setGeometry(16, 120, 620, 102)
    container.setStyleSheet("""
        QFrame {
            background: #FFFFFF;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 16px;
        }
    """)
    c_l = QVBoxLayout(container)
    c_l.setContentsMargins(14, 12, 14, 10)
    c_l.setSpacing(8)
    
    inp = QLineEdit()
    inp.setPlaceholderText("Gõ câu hỏi, tên file, lịch học...")
    inp.setStyleSheet("""
        QLineEdit {
            font-size: 14px;
            border: none;
            background: transparent;
            color: #1F2937;
            padding-left: 2px;
        }
    """)
    c_l.addWidget(inp)
    
    chips = QHBoxLayout()
    chips.setSpacing(6)
    for text in ["📅 Hôm nay học gì?", "📍 Phòng C302 ở đâu?", "📁 Tìm tài liệu", "👥 Giờ rảnh CLB"]:
        chip = QPushButton(text)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setStyleSheet("""
            QPushButton {
                background: #FAFAFA;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
                color: #4B5563;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #F3F4F6;
                border-color: #D1D5DB;
                color: #111827;
            }
        """)
        chips.addWidget(chip)
    chips.addStretch()
    c_l.addLayout(chips)
    
    # 2. Peeking mascot (bust only, gripping container top edge)
    mascot = QLabel(win)
    pm = get_mascot_pixmap(146, 146, bust_only=True)
    mascot.setPixmap(pm)
    mascot.setGeometry(24, 8, 146, 146)
    mascot.stackUnder(container)
    
    # 3. Speech bubble
    bubble = ArtisticSpeechBubble(win)
    bubble.setGeometry(176, 14, 460, 92)
    
    return win

app = QApplication(sys.argv)
w = create_window()
w.show()
app.processEvents()
w.grab().save("scratch/test_user_requested_clean.png")
print("Saved scratch/test_user_requested_clean.png successfully")
