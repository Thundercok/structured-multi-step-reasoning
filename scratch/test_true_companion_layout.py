import sys
import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QGraphicsDropShadowEffect, QStackedWidget
)

MASCOT_PATH = Path("/Users/thundercock2/Documents/Github/Spider-The-Web-Crawler/rat/assets/rat_mascot_cutout.png")

class ComicBubblePointingDown(QFrame):
    """
    Freestanding Comic Speech Bubble hovering ABOVE Chuột.
    Features a comic pointer tail at the bottom-left pointing DOWN to the mascot below.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Bubble body bounds leaving bottom margin for the tail
        tail_h = 14
        tail_x = 75   # aligns right over Chuột's head
        tail_w = 18

        w = self.width() - 4
        h = self.height() - tail_h - 4
        r = 16

        # Rounded rectangle for the bubble body
        path = QPainterPath()
        path.moveTo(2 + r, 2)
        path.lineTo(2 + w - r, 2)
        path.quadTo(2 + w, 2, 2 + w, 2 + r)
        path.lineTo(2 + w, 2 + h - r)
        path.quadTo(2 + w, 2 + h, 2 + w - r, 2 + h)

        # Bottom edge with downward comic tail pointing to Chuột's snout
        path.lineTo(tail_x + tail_w, 2 + h)
        path.lineTo(tail_x + tail_w // 2 - 6, 2 + h + tail_h)  # tail tip
        path.lineTo(tail_x, 2 + h)

        path.lineTo(2 + r, 2 + h)
        path.quadTo(2, 2 + h, 2, 2 + h - r)
        path.lineTo(2, 2 + r)
        path.quadTo(2, 2, 2 + r, 2)
        path.closeSubpath()

        # Ambient soft shadow
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(30, 26, 20, 22))
        p.translate(0, 4)
        p.drawPath(path)
        p.restore()

        # Crisp porcelain fill
        p.setBrush(QColor("#FFFFFF"))
        # Ultra-fine hairline border
        p.setPen(QPen(QColor(43, 38, 31, 32), 1.0))
        p.drawPath(path)
        p.end()

def build_test_ui(expanded=False):
    app = QApplication.instance() or QApplication(sys.argv)
    
    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    
    w = 720 if not expanded else 800
    h = 290 if not expanded else 590
    window.setFixedSize(w, h)
    
    main_layout = QVBoxLayout(window)
    main_layout.setContentsMargins(12, 10, 12, 10)
    main_layout.setSpacing(6)
    
    # =============================================================
    # ROW 1 (CELL 1): FLOATING COMIC SPEECH BUBBLE (Above Chuột!)
    # =============================================================
    speech_bubble = ComicBubblePointingDown()
    speech_bubble.setFixedHeight(98 if not expanded else 110)
    
    sb_layout = QVBoxLayout(speech_bubble)
    sb_layout.setContentsMargins(18, 10, 16, 20)  # bottom margin for tail
    sb_layout.setSpacing(4)
    
    # Bubble top meta bar
    b_top = QHBoxLayout()
    b_top.setSpacing(6)
    
    tag_lbl = QLabel("🧀 Chuột:")
    tag_lbl.setStyleSheet("color: #7A5800; font-size: 11.5px; font-weight: 800; letter-spacing: 0.2px;")
    b_top.addWidget(tag_lbl)
    
    b_top.addStretch()
    
    model_badge = QLabel("● Qwen2.5 Metal")
    model_badge.setStyleSheet("""
        background-color: #FFF6DD;
        color: #7A5800;
        border: 1px solid #E5C470;
        border-radius: 10px;
        padding: 2px 9px;
        font-size: 10px;
        font-weight: 700;
    """)
    b_top.addWidget(model_badge)
    
    btn_expand = QPushButton("⤢" if not expanded else "⤡")
    btn_expand.setFixedSize(22, 22)
    btn_expand.setStyleSheet("""
        QPushButton {
            background-color: #F5EFE6;
            color: #5A5044;
            border: 1px solid rgba(43, 38, 31, 0.12);
            border-radius: 11px;
            font-size: 11px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #FFF2D6;
            color: #2B261F;
        }
    """)
    b_top.addWidget(btn_expand)
    
    btn_close = QPushButton("✕")
    btn_close.setFixedSize(22, 22)
    btn_close.setStyleSheet("""
        QPushButton {
            background-color: #F5EFE6;
            color: #5A5044;
            border: 1px solid rgba(43, 38, 31, 0.12);
            border-radius: 11px;
            font-size: 10px;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #FEE2E2;
            color: #991B1B;
        }
    """)
    b_top.addWidget(btn_close)
    
    sb_layout.addLayout(b_top)
    
    speech_text = QLabel("Hỏi Chuột bất cứ điều gì nè! Lịch học, tìm phòng C302, tìm tài liệu hay tính nhanh... 🧀✨")
    speech_text.setStyleSheet("color: #2B261F; font-size: 12.5px; font-weight: 550; line-height: 1.4;")
    speech_text.setWordWrap(True)
    sb_layout.addWidget(speech_text)
    
    main_layout.addWidget(speech_bubble, 0)
    
    # =============================================================
    # ROW 2 & 3: RAT MASCOT ON LEFT + COMMAND CONSOLE ON RIGHT
    # =============================================================
    bottom_row = QHBoxLayout()
    bottom_row.setContentsMargins(0, 0, 0, 0)
    bottom_row.setSpacing(12)
    
    # -------------------------------------------------------------
    # LEFT: BIG RAT MASCOT (No cringe 'Trực chiến' badge!)
    # -------------------------------------------------------------
    rat_stage = QWidget()
    rat_stage.setFixedWidth(160)
    rs_layout = QVBoxLayout(rat_stage)
    rs_layout.setContentsMargins(0, 0, 0, 0)
    rs_layout.setSpacing(0)
    rs_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
    
    mascot_lbl = QLabel()
    mascot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    mascot_h = 165 if not expanded else 310
    mascot_w = int(mascot_h * (474 / 531))
    rat_stage.setFixedWidth(max(160, mascot_w + 10))
    pm = QPixmap(str(MASCOT_PATH))
    if not pm.isNull():
        scaled = pm.scaled(mascot_w, mascot_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        mascot_lbl.setPixmap(scaled)
        mascot_lbl.setFixedSize(mascot_w, mascot_h)
    
    m_shadow = QGraphicsDropShadowEffect(mascot_lbl)
    m_shadow.setBlurRadius(20)
    m_shadow.setOffset(0, 6)
    m_shadow.setColor(QColor(30, 26, 20, 45))
    mascot_lbl.setGraphicsEffect(m_shadow)
    
    rs_layout.addWidget(mascot_lbl, 0, Qt.AlignmentFlag.AlignCenter)
    bottom_row.addWidget(rat_stage, 0, Qt.AlignmentFlag.AlignBottom)
    
    # -------------------------------------------------------------
    # RIGHT: COMMAND CONSOLE / INPUT CARD
    # -------------------------------------------------------------
    command_card = QFrame()
    command_card.setObjectName("CommandCard")
    command_card.setStyleSheet("""
        QFrame#CommandCard {
            background-color: #FCFBF9;
            border: 1px solid rgba(43, 38, 31, 0.12);
            border-radius: 16px;
        }
    """)
    card_shadow = QGraphicsDropShadowEffect(command_card)
    card_shadow.setBlurRadius(20)
    card_shadow.setOffset(0, 6)
    card_shadow.setColor(QColor(30, 26, 20, 35))
    command_card.setGraphicsEffect(card_shadow)
    
    cc_layout = QVBoxLayout(command_card)
    cc_layout.setContentsMargins(12, 10, 12, 10)
    cc_layout.setSpacing(8)
    
    if expanded:
        # Tab bar
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
        cc_layout.addLayout(tab_bar)
        
        # Convo pane
        convo_area = QFrame()
        convo_area.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 10px; padding: 10px;")
        convo_layout = QVBoxLayout(convo_area)
        
        user_msg = QLabel("Thứ 4 tuần này tui có môn gì không Chuột?")
        user_msg.setStyleSheet("background-color: #F5EFEB; border-radius: 9px; padding: 7px 12px; color: #2B261F; font-size: 12px; font-weight: 600;")
        convo_layout.addWidget(user_msg, 0, Qt.AlignmentFlag.AlignRight)
        
        chuột_reply = QLabel("<b>Chuột đã kiểm tra TKB Thứ Tư cho bạn nè:</b><br>• Tiết 1-3 (06:45 - 09:15): <b>Lập trình Python</b> (Phòng C302)<br>• Tiết 7-9 (12:30 - 15:00): <b>Cơ sở dữ liệu</b> (Phòng B204)<br><br>Nhớ đi sớm xíu kẻo kẹt thang máy nhà C nhé! 🧀")
        chuột_reply.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 9px; padding: 8px 12px; color: #2B261F; font-size: 12px; line-height: 1.45;")
        convo_layout.addWidget(chuột_reply, 0, Qt.AlignmentFlag.AlignLeft)
        convo_layout.addStretch()
        
        cc_layout.addWidget(convo_area, 1)
        
    # Input Bar
    input_box = QFrame()
    input_box.setObjectName("InputBoxFrame")
    input_box.setStyleSheet("""
        QFrame#InputBoxFrame {
            background-color: #FFFFFF;
            border: 1px solid rgba(43, 38, 31, 0.14);
            border-radius: 9px;
            padding: 3px 8px;
        }
    """)
    ib_layout = QHBoxLayout(input_box)
    ib_layout.setContentsMargins(4, 2, 4, 2)
    ib_layout.setSpacing(8)
    
    paw = QLabel("🧀")
    paw.setStyleSheet("font-size: 15px;")
    ib_layout.addWidget(paw)
    
    inp = QLineEdit()
    inp.setPlaceholderText("Hỏi lẹ Chuột nghe nè... (Enter)")
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
    
    cc_layout.addWidget(input_box)
    
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
        cc_layout.addLayout(sugg_layout)
        
    bottom_row.addWidget(command_card, 1)
    main_layout.addLayout(bottom_row)
    
    window.show()
    return window

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    w_compact = build_test_ui(expanded=False)
    w_compact.grab().save("scratch/true_companion_compact.png")
    
    w_expanded = build_test_ui(expanded=True)
    w_expanded.grab().save("scratch/true_companion_expanded.png")
    
    print("True companion screenshots saved successfully!")
