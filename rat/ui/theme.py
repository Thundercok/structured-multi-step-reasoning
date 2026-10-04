"""
rat.ui.theme — warm, tactile light surfaces for rat
A little paper, a little ink, and enough depth to feel touchable.
"""

# Warm Paper Harmonized File Badges
EXT_COLORS = {
    # Pages / Word -> Classic Ink Blue
    ".docx": {"bg": "#2563eb", "fg": "#ffffff", "border": "#1d4ed8", "label": "DOC"},
    ".doc": {"bg": "#2563eb", "fg": "#ffffff", "border": "#1d4ed8", "label": "DOC"},
    # Preview / PDF -> Warm Crimson
    ".pdf": {"bg": "#dc2626", "fg": "#ffffff", "border": "#b91c1c", "label": "PDF"},
    # Numbers / Excel -> Forest Green
    ".xlsx": {"bg": "#16a34a", "fg": "#ffffff", "border": "#15803d", "label": "XLS"},
    ".xls": {"bg": "#16a34a", "fg": "#ffffff", "border": "#15803d", "label": "XLS"},
    ".csv": {"bg": "#16a34a", "fg": "#ffffff", "border": "#15803d", "label": "CSV"},
    # Keynote / Slide -> Amber Orange
    ".pptx": {"bg": "#ea580c", "fg": "#ffffff", "border": "#c2410c", "label": "PPT"},
    ".ppt": {"bg": "#ea580c", "fg": "#ffffff", "border": "#c2410c", "label": "PPT"},
    # Photos / Images -> Teal / Cyan
    ".png": {"bg": "#0891b2", "fg": "#ffffff", "border": "#0e7490", "label": "IMG"},
    ".jpg": {"bg": "#0891b2", "fg": "#ffffff", "border": "#0e7490", "label": "IMG"},
    ".jpeg": {"bg": "#0891b2", "fg": "#ffffff", "border": "#0e7490", "label": "IMG"},
    ".webp": {"bg": "#0891b2", "fg": "#ffffff", "border": "#0e7490", "label": "IMG"},
    # Code -> Royal Purple
    ".py": {"bg": "#7c3aed", "fg": "#ffffff", "border": "#6d28d9", "label": "PY"},
    ".js": {"bg": "#d97706", "fg": "#ffffff", "border": "#b45309", "label": "JS"},
    ".ts": {"bg": "#2563eb", "fg": "#ffffff", "border": "#1d4ed8", "label": "TS"},
    ".html": {"bg": "#ea580c", "fg": "#ffffff", "border": "#c2410c", "label": "HTML"},
    ".css": {"bg": "#0891b2", "fg": "#ffffff", "border": "#0e7490", "label": "CSS"},
    ".json": {"bg": "#7c3aed", "fg": "#ffffff", "border": "#6d28d9", "label": "JSON"},
    ".sh": {"bg": "#16a34a", "fg": "#ffffff", "border": "#15803d", "label": "SH"},
    ".sql": {"bg": "#4f46e5", "fg": "#ffffff", "border": "#4338ca", "label": "SQL"},
    # TextEdit / Notes -> Warm Stone
    ".txt": {"bg": "#78716c", "fg": "#ffffff", "border": "#57534e", "label": "TXT"},
    ".md": {"bg": "#78716c", "fg": "#ffffff", "border": "#57534e", "label": "MD"},
    # AI / Chatbot Assistant -> Gold Sparkle
    ".ai": {"bg": "#d97706", "fg": "#ffffff", "border": "#b45309", "label": "AI"},
    ".calc": {"bg": "#ea580c", "fg": "#ffffff", "border": "#c2410c", "label": "CALC"},
    ".map": {"bg": "#16a34a", "fg": "#ffffff", "border": "#15803d", "label": "MAP"},
    ".app": {"bg": "#2563eb", "fg": "#ffffff", "border": "#1d4ed8", "label": "APP"},
}


def get_ext_badge_info(ext: str) -> dict:
    ext_clean = ext.lower()
    if ext_clean in EXT_COLORS:
        return EXT_COLORS[ext_clean]
    label = ext_clean.lstrip(".").upper() or "FILE"
    return {"bg": "#8c7e6f", "fg": "#ffffff", "border": "#75685a", "label": label[:4]}


# Quiet conversation surfaces: shared by finished replies, streaming replies and
# their secondary actions. The existing paper shell and mascot stay unchanged.
CHAT_COLORS = {
    "ink": "#302B24",
    "secondary": "#6F6456",
    "border": "#E9E1D5",
    "paper": "#FFFDFA",
    "tint": "#F7F3EC",
    "hover": "#EEE6D8",
    "focus": "#B49A6B",
}

CHAT_CARD_QSS = f"""
    QFrame#AssistantCard {{
        background: {CHAT_COLORS['paper']};
        border: 1px solid {CHAT_COLORS['border']};
        border-left: 3px solid #D8CDBE;
        border-radius: 11px;
    }}
    QLabel {{ border: none; background: transparent; color: {CHAT_COLORS['ink']}; }}
"""

CONVERSATION_RIBBON_QSS = f"""
    QFrame#ConversationRibbon {{
        background: #FAF7F2;
        border: 1px solid #EBE4D8;
        border-radius: 8px;
    }}
    QLabel#RibbonTag {{
        color: #5C5245;
        font-size: 11px;
        font-weight: 600;
        background: transparent;
        border: none;
    }}
    QLabel#RibbonTurnBadge {{
        color: #7B6E5F;
        font-size: 10px;
        font-weight: 500;
        background: #EDE5D8;
        border-radius: 4px;
        padding: 1px 6px;
        border: none;
    }}
    QPushButton#RibbonClearBtn {{
        background: transparent;
        border: none;
        border-radius: 4px;
        color: #8A7E70;
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
    }}
    QPushButton#RibbonClearBtn:hover {{
        background: #EDE5D8;
        color: #241E19;
    }}
    QPushButton#RibbonClearBtn:pressed {{
        background: #E3D9C9;
    }}
"""

CHAT_ACTION_QSS = f"""
    QPushButton {{
        background: transparent; border: 1px solid transparent; border-radius: 5px;
        color: {CHAT_COLORS['secondary']}; font-size: 10px; font-weight: 400;
        padding: 3px 6px;
    }}
    QPushButton:hover {{ background: {CHAT_COLORS['tint']}; color: {CHAT_COLORS['ink']}; }}
    QPushButton:pressed {{ background: {CHAT_COLORS['hover']}; }}
    QPushButton:focus {{ border-color: {CHAT_COLORS['focus']}; }}
    QPushButton:disabled {{ color: #9A9184; }}
"""

CHAT_USER_QSS = f"""
    QFrame#UserBubble {{
        background: #F4EFE6; border: 1px solid #E2D7C6;
        border-radius: 11px; border-bottom-right-radius: 4px;
    }}
    QLabel {{ color: {CHAT_COLORS['ink']}; font-size: 13px; font-weight: 400;
        border: none; background: transparent; }}
"""

# Only visible while reading above the latest message. It never takes layout space.
CHAT_JUMP_QSS = f"""
    QPushButton {{ background: {CHAT_COLORS['paper']}; color: {CHAT_COLORS['ink']};
        border: 1px solid #D6C7AF; border-radius: 12px;
        font-size: 11px; padding: 5px 10px; }}
    QPushButton:hover {{ background: {CHAT_COLORS['tint']}; }}
    QPushButton:pressed {{ background: {CHAT_COLORS['hover']}; }}
    QPushButton:focus {{ border-color: {CHAT_COLORS['focus']}; }}
"""


RAYCAST_QSS = """
/* ========================================================================= */
/* AGENT CHUỘT - LIGHT MODE REFINED (WARM LIGHT GLASS SPECIFICATION)         */
/* Clean, modern, warm light glass aesthetic with peeking mascot              */
/* ========================================================================= */

* {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Helvetica Neue", sans-serif;
    outline: none;
    color: #1F2937;
}

/* Global Reset */
QLabel {
    border: none;
    background: transparent;
    color: #1F2937;
}

/* Single Unified Container - Warm Paper Light Surface */
QFrame#SpotlightContainer {
    background-color: #FCFAF7;
    border: 1.5px solid rgba(43, 38, 31, 0.12);
    border-radius: 16px;
}

/* Integrated Input Bar */
QFrame#QuickBar {
    background: transparent;
    border: none;
    padding: 0px 4px;
}

QFrame#QuickBar:hover {
    background: transparent;
}

QFrame#HairlineDivider {
    background-color: rgba(43, 38, 31, 0.08);
    max-height: 1px;
    min-height: 1px;
    border: none;
}

QLineEdit#ChatComposerInput {
    background: transparent;
    color: #1F1A16;
    border: none;
    padding: 6px 8px;
    font-size: 13.5px;
    font-weight: 550;
    selection-background-color: #FDE68A;
    selection-color: #1F1A16;
}

/* Tactile Physical Mac Keycap */
QLabel#ReturnKeycap {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "JetBrains Mono", monospace;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F0ECE4);
    color: #4B4339;
    border: 1px solid #D6CEBE;
    border-bottom: 2.5px solid #BCB2A0;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#ReturnKeycap[active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FDE68A, stop:1 #F59E0B);
    color: #1F1C18;
    border: 1px solid #D97706;
    border-bottom: 2.5px solid #B45309;
    font-weight: 800;
}

/* Tactile Suggestion Chips */
QPushButton.QuickSuggestionChip {
    background-color: #FFFFFF;
    color: #4A4036;
    border: 1px solid #E6DFD5;
    border-bottom: 2px solid #D4C9BA;
    border-radius: 9px;
    padding: 5px 12px;
    font-size: 11.5px;
    font-weight: 650;
}

QPushButton.QuickSuggestionChip:hover, QPushButton.QuickSuggestionChip:focus {
    background-color: #FFFDF9;
    color: #1F1A16;
    border-color: #DEC88E;
    border-bottom: 2px solid #C9A952;
}

QPushButton.QuickSuggestionChip:pressed {
    background-color: #FEE8A2;
    border-bottom: 1px solid #D4B872;
    padding-top: 6px;
    padding-bottom: 4px;
}

/* Status Indicator */
QLabel#QuickModelBadge {
    background-color: #FFF8E6;
    color: #8C6200;
    border: 1px solid #EAD494;
    border-radius: 10px;
    padding: 2px 9px;
    font-size: 10.5px;
    font-weight: 700;
}

QPushButton#OverlayExpandBtn {
    background-color: #FFFFFF;
    color: #6B5E50;
    border: 1px solid rgba(43, 38, 31, 0.15);
    border-radius: 13px;
    font-size: 11px;
    font-weight: 700;
    min-width: 26px;
    min-height: 26px;
    max-width: 26px;
    max-height: 26px;
}

QPushButton#OverlayExpandBtn:hover {
    background-color: #FFF6DD;
    color: #1F1C18;
    border-color: #E8CA7C;
}

QPushButton#OverlayExpandBtn:pressed {
    background-color: #FFB800;
}

QPushButton#OverlayCloseBtn {
    background-color: #FFFFFF;
    color: #6B5E50;
    border: 1px solid rgba(43, 38, 31, 0.15);
    border-radius: 13px;
    font-size: 10.5px;
    font-weight: 700;
    min-width: 26px;
    min-height: 26px;
    max-width: 26px;
    max-height: 26px;
}

QPushButton#OverlayCloseBtn:hover {
    background-color: #FFECEC;
    color: #E03535;
    border-color: #F8B4B4;
}

QPushButton#OverlayCloseBtn:pressed {
    background-color: #FFD4D4;
}

/* Tactile Segmented Pill Switcher (Warm Paper Groove) */
QFrame#FilterPillsBar {
    background-color: #EFE9DF;
    border: 1px solid rgba(43, 38, 31, 0.10);
    border-radius: 9px;
    padding: 2px 3px;
}

QPushButton.FilterPill {
    background-color: transparent;
    color: #6E6254;
    font-size: 11.5px;
    font-weight: 600;
    padding: 5px 14px;
    border: none;
    border-radius: 7px;
    margin-right: 2px;
}

QPushButton.FilterPill:hover {
    background-color: rgba(255, 255, 255, 0.65);
    color: #1F1C18;
}

QPushButton.FilterPill[active="true"] {
    background-color: #FFFFFF;
    color: #1F1C18;
    border: 1px solid #DCD4C7;
    border-bottom: 2px solid #C8BFB0;
    font-weight: 750;
}

QPushButton.FilterPill:pressed {
    background-color: #FEE8A2;
    color: #1F1C18;
}

/* File Search Input Field */
QLineEdit#SearchInput {
    background-color: #FFFFFF;
    color: #2B261F;
    font-size: 13px;
    font-weight: 550;
    border: 1px solid rgba(43, 38, 31, 0.14);
    border-radius: 8px;
    padding: 6px 12px;
    selection-background-color: #FFBE3B;
    selection-color: #2B261F;
}

/* Tactile Send / Action Button */
QPushButton#SendButton, QPushButton.SendButton {
    background-color: #FFB800;
    color: #1F1C18;
    border: 1px solid #E5A500;
    border-radius: 8px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 750;
}

QPushButton#SendButton:hover, QPushButton.SendButton:hover {
    background-color: #FFA500;
}

QPushButton#SendButton:pressed, QPushButton.SendButton:pressed {
    background-color: #E29300;
}

/* Splitter */
QSplitter::handle {
    background-color: rgba(43, 38, 31, 0.08);
    width: 1px;
}

/* Result and Recent Lists */
QListWidget#ResultList, QListWidget#RecentList {
    background-color: #FFFFFF;
    border: 1px solid rgba(43, 38, 31, 0.10);
    border-radius: 10px;
    outline: none;
    padding: 4px;
}

QListWidget#ResultList::item, QListWidget#RecentList::item {
    background-color: transparent;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 1px 0px;
}

QListWidget#ResultList::item:selected, QListWidget#RecentList::item:selected {
    background-color: #FFF4D4;
    color: #2B261F;
}

/* Preview Inspector Panel */
QFrame#PreviewPanel {
    background-color: #FAFAF8;
    border-left: 1px solid rgba(43, 38, 31, 0.08);
    border-bottom-right-radius: 14px;
    padding: 12px 14px;
}

QTextEdit#PreviewContent {
    background-color: #FFFFFF;
    color: #2B261F;
    border: 1px solid rgba(43, 38, 31, 0.10);
    border-radius: 8px;
    font-size: 12px;
    padding: 10px;
    font-family: "SF Mono", "Menlo", monospace;
    line-height: 1.5;
}

/* Vintage Action Footer */
QFrame#ActionFooter {
    background-color: #F8F5F0;
    border-top: 1px solid rgba(43, 38, 31, 0.08);
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
    padding: 6px 14px;
}

QLabel#FooterStatus {
    color: #2B261F;
    font-size: 11px;
    font-weight: 700;
}

QLabel.HotkeyBadge {
    background-color: #FFFFFF;
    color: #5A5044;
    border: 1px solid rgba(43, 38, 31, 0.14);
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: 700;
}

/* macOS Minimalist Ghost Scrollbars */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 2px 2px 2px 0px;
}

QScrollBar::handle:vertical {
    background: rgba(43, 38, 31, 0.20);
    min-height: 24px;
    border-radius: 3px;
    border: none;
}

QScrollBar::handle:vertical:hover {
    background: rgba(43, 38, 31, 0.40);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    height: 0px;
}
"""
