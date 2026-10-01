import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QPoint, QRect, QPointF
from PyQt6.QtGui import (QPainter, QPainterPath, QColor, QPen, QLinearGradient, 
                         QFont, QBrush)
from rat.ui.chat_stream import get_mascot_pixmap

class ArtisticSpeechBubble(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(22, 9, 14, 10)
        self.main_layout.setSpacing(5)
        
        # 1. Header Meta Row
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
        
        self.btn_copy = QPushButton("Sao chép")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setFixedHeight(20)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 5px;
                font-size: 10.5px;
                font-weight: 600;
                color: #64748B;
                padding: 0 7px;
            }
            QPushButton:hover {
                background: #F1F5F9;
                color: #0F172A;
                border-color: #CBD5E1;
            }
        """)
        header.addWidget(self.btn_copy)
        
        self.btn_hist = QPushButton("Lịch sử ↗")
        self.btn_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hist.setFixedHeight(20)
        self.btn_hist.setStyleSheet("""
            QPushButton {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 5px;
                font-size: 10.5px;
                font-weight: 600;
                color: #64748B;
                padding: 0 7px;
            }
            QPushButton:hover {
                background: #F1F5F9;
                color: #0F172A;
                border-color: #CBD5E1;
            }
        """)
        header.addWidget(self.btn_hist)
        self.main_layout.addLayout(header)
        
        # 2. Main Dialogue Text
        self.dialogue = QLabel("Nghe đây. Cần tìm gì?")
        self.dialogue.setStyleSheet("font-size: 13.5px; font-weight: 520; color: #1E293B; line-height: 1.45;")
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
        
        # Organic smooth bezier tail
        path.lineTo(2 + tail_w, tail_y + tail_h)
        tip_x = 2.0
        tip_y = tail_y + tail_h * 0.45
        path.quadTo(2 + tail_w * 0.4, tail_y + tail_h * 0.85, tip_x, tip_y)
        path.quadTo(2 + tail_w * 0.35, tail_y + tail_h * 0.15, 2 + tail_w, tail_y)
        
        path.lineTo(2 + tail_w, 2 + r)
        path.quadTo(2 + tail_w, 2, 2 + tail_w + r, 2)
        path.closeSubpath()
        
        # Soft multi-pass shadow
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


def create_demo_window(state: str, query: str, reply: str, context: str):
    win = QWidget()
    win.resize(652, 242)
    win.setStyleSheet("background: transparent;")
    
    container = QFrame(win)
    container.setGeometry(16, 124, 620, 102)
    container.setStyleSheet("background: #FFFFFF; border: 1px solid rgba(0,0,0,0.08); border-radius: 16px;")
    c_l = QVBoxLayout(container)
    c_l.setContentsMargins(14, 12, 14, 10)
    c_l.setSpacing(8)
    
    inp = QLineEdit()
    inp.setText(query)
    inp.setPlaceholderText("Gõ câu hỏi, tên file, lịch học...")
    inp.setStyleSheet("font-size: 14px; border: none; background: transparent; color: #1F2937;")
    c_l.addWidget(inp)
    
    chips = QHBoxLayout()
    chips.setSpacing(6)
    for text in ["📅 Hôm nay học gì?", "📍 Phòng C302 ở đâu?", "📁 Tìm tài liệu", "👥 Giờ rảnh CLB"]:
        chip = QLabel(text)
        chip.setStyleSheet("background: #FAFAFA; border: 1px solid #E5E7EB; border-radius: 8px; padding: 4px 10px; font-size: 11px; color: #4B5563;")
        chips.addWidget(chip)
    chips.addStretch()
    c_l.addLayout(chips)
    
    mascot = QLabel(win)
    if state == "peeking":
        # Bust only, paws resting on container top bezel (y=124)
        pm = get_mascot_pixmap(146, 146, bust_only=True)
        mascot.setPixmap(pm)
        mascot.setGeometry(24, 12, 146, 146)
        mascot.stackUnder(container)
    else:
        # Full character with feet & tail!
        # Scaled to 134x142 so feet reach exactly y=124 without overlapping text
        pm = get_mascot_pixmap(134, 142, bust_only=False)
        mascot.setPixmap(pm)
        mascot.setGeometry(20, -16, 134, 142)
        
    bubble = ArtisticSpeechBubble(win)
    bubble.setGeometry(174, 20, 462, 92)
    bubble.set_reply(reply, context)
    
    return win

def main():
    app = QApplication(sys.argv)
    
    # 1. State: Peeking (Idle welcome)
    w1 = create_demo_window(
        state="peeking",
        query="",
        reply="Nghe đây. Cần tìm gì?",
        context="Sẵn sàng"
    )
    w1.show()
    app.processEvents()
    w1.grab().save("scratch/refined_peeking_welcome.png")
    w1.close()
    
    # 2. State: Revealed (Room C302 query)
    w2 = create_demo_window(
        state="revealed",
        query="Phòng C302 ở đâu?",
        reply="Tầng 3, Tòa C. Rẽ trái từ thang máy.",
        context="Phòng C302 · 12ms"
    )
    w2.show()
    app.processEvents()
    w2.grab().save("scratch/refined_revealed_room.png")
    w2.close()
    
    # 3. State: Revealed (Schedule query)
    w3 = create_demo_window(
        state="revealed",
        query="Hôm nay học gì?",
        reply="Hôm nay (2 môn): Giải tích (7:30, C302) và Lập trình Python (13:00, A105).",
        context="Lịch hôm nay · 8ms"
    )
    w3.show()
    app.processEvents()
    w3.grab().save("scratch/refined_revealed_schedule.png")
    w3.close()
    
    # 4. State: Revealed (File search query)
    w4 = create_demo_window(
        state="revealed",
        query="báo cáo.pdf",
        reply="Không có file này trong máy. Bạn nhớ nhầm tên à?",
        context="Tệp tin · 15ms"
    )
    w4.show()
    app.processEvents()
    w4.grab().save("scratch/refined_revealed_files.png")
    w4.close()
    
    print("SUCCESS: Refined demo windows saved successfully!")

if __name__ == "__main__":
    main()
