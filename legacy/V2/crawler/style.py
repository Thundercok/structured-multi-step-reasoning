"""
style.py — Application stylesheet and log-message colour utilities.

Keeping QSS in its own file means the UI code never has to scroll past
hundreds of lines of CSS to find a widget method.
"""

# ---------------------------------------------------------------------------
# Qt stylesheet
# ---------------------------------------------------------------------------

QSS = """
QWidget {
    background: #1a1b1e;
    color: #c9ccd4;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

QWidget#titlebar {
    background: #141517;
    border-bottom: 1px solid #2a2b30;
}

QWidget#sidebar {
    background: #141517;
    border-right: 1px solid #2a2b30;
}

QLabel#section-heading {
    color: #555b6b;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}

QLineEdit {
    background: #111214;
    border: 1px solid #2a2b30;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e2e8;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    selection-background-color: #3b82f6;
}
QLineEdit:focus { border-color: #3b82f6; }

QCheckBox {
    spacing: 7px;
    color: #9aa0b0;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #3a3d47;
    background: #111214;
}
QCheckBox::indicator:checked {
    background: #3b82f6;
    border-color: #3b82f6;
}
QCheckBox::indicator:hover { border-color: #3b82f6; }

QSpinBox, QDoubleSpinBox {
    background: #111214;
    border: 1px solid #2a2b30;
    border-radius: 6px;
    padding: 4px 8px;
    color: #e0e2e8;
}
QSpinBox:focus, QDoubleSpinBox:focus { border-color: #3b82f6; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 16px;
    background: #1e2027;
    border: none;
}

QProgressBar {
    background: #111214;
    border: none;
    border-radius: 2px;
    height: 4px;
    color: transparent;
}
QProgressBar::chunk {
    background: #3b82f6;
    border-radius: 2px;
}

QTextEdit {
    background: #0f1012;
    border: none;
    color: #9aa0b0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 10px 14px;
    selection-background-color: #2a3a5a;
}

QPushButton {
    background: transparent;
    border: 1px solid #2a2b30;
    border-radius: 6px;
    padding: 6px 14px;
    color: #9aa0b0;
    font-size: 13px;
}
QPushButton:hover  { background: #22252e; border-color: #3a3d47; color: #c9ccd4; }
QPushButton:pressed { background: #1a1d25; }
QPushButton:disabled { color: #3a3d47; border-color: #22252e; }

QPushButton#btn-start {
    background: #1d4ed8;
    border-color: #1d4ed8;
    color: #ffffff;
    font-weight: 600;
    padding: 7px 20px;
}
QPushButton#btn-start:hover    { background: #2563eb; border-color: #2563eb; color: #ffffff; }
QPushButton#btn-start:disabled { background: #1e2a42; border-color: #1e2a42; color: #4a5a7a; }

QPushButton#btn-stop {
    background: #450a0a;
    border-color: #7f1d1d;
    color: #fca5a5;
}
QPushButton#btn-stop:hover    { background: #5a0e0e; border-color: #991b1b; color: #fecaca; }
QPushButton#btn-stop:disabled { background: #1a1214; border-color: #2a1a1a; color: #4a2a2a; }

QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #2a2b30;
    border: none;
    background: #2a2b30;
    max-height: 1px;
    max-width: 1px;
}

QLabel#stat-value       { font-size: 22px; font-weight: 600; color: #e0e2e8; }
QLabel#stat-value-green { font-size: 22px; font-weight: 600; color: #4ade80; }
QLabel#stat-value-red   { font-size: 22px; font-weight: 600; color: #f87171; }
QLabel#stat-label       { font-size: 10px; color: #555b6b; letter-spacing: 0.5px; }
QLabel#stat-domain      { font-size: 12px; color: #9aa0b0; font-family: "Consolas", monospace; }

QLabel#badge-idle     { background: #1e2027; border: 1px solid #2a2b30;
                         border-radius: 10px; color: #555b6b;
                         font-size: 11px; padding: 2px 10px; }
QLabel#badge-running  { background: #052e16; border: 1px solid #166534;
                         border-radius: 10px; color: #4ade80;
                         font-size: 11px; padding: 2px 10px; }
QLabel#badge-stopping { background: #2d1a06; border: 1px solid #92400e;
                         border-radius: 10px; color: #fbbf24;
                         font-size: 11px; padding: 2px 10px; }

QScrollBar:vertical     { background: #111214; width: 8px; border: none; }
QScrollBar::handle:vertical { background: #2a2b30; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal   { height: 0; }
"""

# ---------------------------------------------------------------------------
# Log colouring
# ---------------------------------------------------------------------------

LOG_COLORS: dict[str, str] = {
    "ok":   "#4ade80",
    "err":  "#f87171",
    "warn": "#fbbf24",
    "info": "#60a5fa",
    "ts":   "#3a3d47",
    "dim":  "#555b6b",
}


def classify(text: str) -> str:
    """Map a log message to a colour key based on its leading character."""
    if text.startswith("✅") or text.startswith("✔") or text.startswith("▶"):
        return "ok"
    if text.startswith("❌") or "Error" in text:
        return "err"
    if text.startswith("🚫") or text.startswith("🛑") or text.startswith("⚠"):
        return "warn"
    return "info"
