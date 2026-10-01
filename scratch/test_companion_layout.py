import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QGraphicsDropShadowEffect, QStackedWidget
)

MASCOT_PATH = Path("/Users/thundercock2/Documents/Github/Spider-The-Web-Crawler/rat/assets/rat_mascot_cutout.png")

class ComicSpeechFrameLeft(QFrame):
    """Dialogue frame with a comic pointer tail on the LEFT pointing to the character."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        tail_w = 12
        tail_y = 28
        tail_h = 16
        rect = QRectF(tail_w, 1, self.width() - tail_w - 2, self.height() - 3)

        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        tail_path = QPainterPath()
        tail_path.moveTo(tail_w + 1, tail_y)
        tail_path.lineTo(1, tail_y + tail_h / 2)
        tail_path.lineTo(tail_w + 1, tail_y + tail_h)
        tail_path.closeSubpath()

        full_path = path.united(tail_path)

        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(43, 38, 31, 14))
        p.translate(0, 2)
        p.drawPath(full_path)
        p.restore()

        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QColor(43, 38, 31, 28))
        p.drawPath(full_path)
        p.end()

def build_test_ui(expanded=False):
    app = QApplication.instance() or QApplication(sys.argv)
    
    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    
    w = 720 if not expanded else 820
    h = 245 if not expanded else 560
    window.setFixedSize(w, h)
    
    root_layout = QHBoxLayout(window)
    root_layout.setContentsMargins(14, 10, 14, 10)
    root_layout.setSpacing(12)
    
    # -------------------------------------------------------------
    # 1. LEFT COLUMN: THE RAT COMPANION STAGE (Full Height)
    # -------------------------------------------------------------
    stage_widget = QWidget()
    stage_widget.setObjectName("RatStage")
    stage_w = 200
    stage_widget.setFixedWidth(stage_w)
    stage_layout = QVBoxLayout(stage_widget)
    stage_layout.setContentsMargins(0, 0, 0, 0)
    stage_layout.setSpacing(8)
    
    if expanded:
        # In expanded mode, we add a cute character profile card or status header
        stage_layout.addStretch()
        mascot_h = 280
    else:
        stage_layout.addStretch()
        mascot_h = 195
        
    mascot_w = int(mascot_h * (474 / 531))
    
    mascot_lbl = QLabel()
    mascot_lbl.setObjectName("RatAvatar")
    mascot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    pm = QPixmap(str(MASCOT_PATH))
    if not pm.isNull():
        scaled = pm.scaled(mascot_w, mascot_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        mascot_lbl.setPixmap(scaled)
        mascot_lbl.setFixedSize(mascot_w, mascot_h)
    
    shadow_effect = QGraphicsDropShadowEffect(mascot_lbl)
    shadow_effect.setBlurRadius(24)
    shadow_effect.setOffset(0, 8)
    shadow_effect.setColor(QColor(30, 26, 20, 50))
    mascot_lbl.setGraphicsEffect(shadow_effect)
    
    mood_pill = QLabel("🧀 Rat · Trực chiến")
    mood_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mood_pill.setStyleSheet("""
        background-color: #FFF6DD;
        color: #7A5800;
        border: 1px solid #E5C470;
        border-radius: 12px;
        padding: 4px 12px;
        font-size: 11px;
        font-weight: 750;
    """)
    mood_pill.setFixedHeight(24)
    
    stage_layout.addWidget(mascot_lbl, 0, Qt.AlignmentFlag.AlignCenter)
    stage_layout.addWidget(mood_pill, 0, Qt.AlignmentFlag.AlignCenter)
    
    if expanded:
        hint_lbl = QLabel("Click chuột để chọc Rat 🧀")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_lbl.setStyleSheet("color: #8C7B6B; font-size: 10px; font-weight: 550;")
        stage_layout.addWidget(hint_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        stage_layout.addSpacing(6)
        
    root_layout.addWidget(stage_widget, 0, Qt.AlignmentFlag.AlignBottom)
    
    # -------------------------------------------------------------
    # 2. RIGHT COLUMN: GAME DIALOGUE & WORKSPACE CONSOLE
    # -------------------------------------------------------------
    console_frame = QFrame()
    console_frame.setObjectName("ConsoleCard")
    console_frame.setStyleSheet("""
        QFrame#ConsoleCard {
            background-color: #FCFBF9;
            border: 1px solid rgba(43, 38, 31, 0.14);
            border-radius: 18px;
        }
    """)
    c_shadow = QGraphicsDropShadowEffect(console_frame)
    c_shadow.setBlurRadius(24)
    c_shadow.setOffset(0, 8)
    c_shadow.setColor(QColor(30, 26, 20, 45))
    console_frame.setGraphicsEffect(c_shadow)
    
    console_layout = QVBoxLayout(console_frame)
    console_layout.setContentsMargins(14, 12, 14, 12)
    console_layout.setSpacing(10)
    
    # Top Control Bar (Model pill, expand, close)
    header_bar = QHBoxLayout()
    header_bar.setSpacing(6)
    
    model_badge = QLabel("● Qwen2.5 Metal")
    model_badge.setStyleSheet("""
        background-color: #FFF6DD;
        color: #7A5800;
        border: 1px solid #E5C470;
        border-radius: 11px;
        padding: 3px 10px;
        font-size: 10px;
        font-weight: 700;
    """)
    header_bar.addWidget(model_badge)
    header_bar.addStretch()
    
    btn_expand = QPushButton("⤢" if not expanded else "⤡")
    btn_expand.setFixedSize(24, 24)
    btn_expand.setStyleSheet("""
        QPushButton {
            background-color: #F3EEE6;
            color: #5A5044;
            border: 1px solid rgba(43, 38, 31, 0.10);
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #FFF2D6;
            color: #2B261F;
        }
    """)
    header_bar.addWidget(btn_expand)
    
    btn_close = QPushButton("✕")
    btn_close.setFixedSize(24, 24)
    btn_close.setStyleSheet("""
        QPushButton {
            background-color: #F3EEE6;
            color: #5A5044;
            border: 1px solid rgba(43, 38, 31, 0.10);
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #FEE2E2;
            color: #991B1B;
        }
    """)
    header_bar.addWidget(btn_close)
    
    console_layout.addLayout(header_bar)
    
    if expanded:
        # Tab switcher
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(4)
        for i, t_label in enumerate(["💬 Trò chuyện", "📁 Tệp tin", "📅 TKB / Lịch", "👥 CLB"]):
            btn_tab = QPushButton(t_label)
            is_act = i == 0
            btn_tab.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#FFFFFF' if is_act else 'transparent'};
                    color: {'#2B261F' if is_act else '#7C7063'};
                    border: {('1px solid rgba(43, 38, 31, 0.12)' if is_act else 'none')};
                    border-radius: 7px;
                    padding: 5px 12px;
                    font-size: 11.5px;
                    font-weight: {'700' if is_act else '550'};
                }}
            """)
            tab_bar.addWidget(btn_tab)
        tab_bar.addStretch()
        console_layout.addLayout(tab_bar)
        
        # Expanded conversation pane
        convo_area = QFrame()
        convo_area.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 12px; padding: 12px;")
        convo_layout = QVBoxLayout(convo_area)
        
        user_msg = QLabel("Thứ 4 tuần này tui có môn gì không Rat?")
        user_msg.setStyleSheet("background-color: #F5EFEB; border-radius: 10px; padding: 8px 12px; color: #2B261F; font-size: 12.5px; font-weight: 600;")
        convo_layout.addWidget(user_msg, 0, Qt.AlignmentFlag.AlignRight)
        
        rat_reply = QLabel("<b>Rat đã kiểm tra TKB Thứ Tư cho bạn nè:</b><br><br>• Tiết 1-3 (06:45 - 09:15): <b>Lập trình Python nâng cao</b> (Phòng C302)<br>• Tiết 7-9 (12:30 - 15:00): <b>Cơ sở dữ liệu phân tán</b> (Phòng B204)<br><br>💡 <i>Buổi sáng nhớ đi sớm chút nha, phòng C302 lầu 3 nhà C hơi đông thang máy á! 🧀</i>")
        rat_reply.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(43, 38, 31, 0.10); border-radius: 10px; padding: 10px 14px; color: #2B261F; font-size: 12.5px; line-height: 1.5;")
        rat_reply.setWordWrap(True)
        convo_layout.addWidget(rat_reply, 0, Qt.AlignmentFlag.AlignLeft)
        convo_layout.addStretch()
        
        console_layout.addWidget(convo_area, 1)
    else:
        # Compact Dialogue Speech Balloon (with left tail pointing at Rat!)
        speech_bubble = ComicSpeechFrameLeft()
        sb_layout = QVBoxLayout(speech_bubble)
        sb_layout.setContentsMargins(22, 10, 14, 10)
        sb_layout.setSpacing(4)
        
        speech_tag = QLabel("🧀 Rat · Lời thoại")
        speech_tag.setStyleSheet("color: #9E8E7E; font-size: 10px; font-weight: 700; letter-spacing: 0.3px;")
        sb_layout.addWidget(speech_tag)
        
        speech_text = QLabel("Hỏi Rat bất cứ điều gì nè! Lịch học, tìm phòng C302, tìm tài liệu hay tính nhanh... 🧀✨")
        speech_text.setStyleSheet("color: #2B261F; font-size: 12.5px; font-weight: 550; line-height: 1.4;")
        speech_text.setWordWrap(True)
        sb_layout.addWidget(speech_text)
        
        console_layout.addWidget(speech_bubble, 1)
        
    # Input Composer Bar (Seamless porcelain)
    input_bar = QFrame()
    input_bar.setStyleSheet("""
        QFrame {
            background-color: #FFFFFF;
            border: 1px solid rgba(43, 38, 31, 0.14);
            border-radius: 10px;
            padding: 2px 8px;
        }
    """)
    ib_layout = QHBoxLayout(input_bar)
    ib_layout.setContentsMargins(4, 2, 4, 2)
    ib_layout.setSpacing(8)
    
    paw = QLabel("🧀")
    paw.setStyleSheet("font-size: 15px;")
    ib_layout.addWidget(paw)
    
    inp = QLineEdit()
    inp.setPlaceholderText("Hỏi lẹ Rat nghe nè... (Enter)")
    inp.setStyleSheet("border: none; background: transparent; color: #2B261F; font-size: 12.5px; font-weight: 550;")
    ib_layout.addWidget(inp, 1)
    
    keycap = QLabel("↵ Enter")
    keycap.setStyleSheet("""
        background-color: #FFB800;
        color: #1F1C18;
        border: 1px solid #E5A500;
        border-radius: 5px;
        padding: 3px 8px;
        font-size: 10.5px;
        font-weight: 750;
    """)
    ib_layout.addWidget(keycap)
    
    console_layout.addWidget(input_bar)
    
    if not expanded:
        # Quick Suggestion Strip
        sugg_layout = QHBoxLayout()
        sugg_layout.setSpacing(6)
        suggs = [
            ("📅 Hôm nay học gì?", "#FFF9E6", "#E8D8A8"),
            ("📍 Phòng C302 ở đâu?", "#FFF2EB", "#EDCFBE"),
            ("👥 Khung giờ rảnh CLB", "#EFF8F2", "#C6E6D0"),
        ]
        for s_txt, bg, bd in suggs:
            s_btn = QPushButton(s_txt)
            s_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: #2B261F;
                    border: 1px solid {bd};
                    border-radius: 12px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: 650;
                }}
            """)
            sugg_layout.addWidget(s_btn)
        sugg_layout.addStretch()
        console_layout.addLayout(sugg_layout)
    
    root_layout.addWidget(console_frame, 1)
    
    window.show()
    return window

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    w_compact = build_test_ui(expanded=False)
    w_compact.grab().save("scratch/companion_compact_v2.png")
    
    w_expanded = build_test_ui(expanded=True)
    w_expanded.grab().save("scratch/companion_expanded_v2.png")
    
    print("New companion screenshots saved successfully!")
