"""
rat.ui.compact_cot — Minimalist Chain-of-Thought (CoT) Ribbon & Micro-Ladder for Min Mode.
Renders real-time reasoning progression (Thought -> Action -> Verification) directly
inside the compact Omnibar container without requiring full window expansion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CompactCoTBar(QFrame):
    """
    Sleek, horizontal Chain-of-Thought strip designed specifically for Min Mode.
    Shows reasoning phases (Decompose -> Retrieve -> Verify), confidence score,
    and supports 1-click micro-expansion of step thoughts.
    """

    heightChanged = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.is_details_expanded = False
        self._current_steps: List[str] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("CompactCoTBar")
        self.setStyleSheet("""
            QFrame#CompactCoTBar {
                background: #FAF7F1;
                border: 1px solid #E8E1D5;
                border-radius: 9px;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 4, 8, 4)
        self.main_layout.setSpacing(4)

        # -------------------------------------------------------------
        # Header Row (Always visible when CoT active)
        # -------------------------------------------------------------
        self.header_row = QWidget()
        h_layout = QHBoxLayout(self.header_row)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self.tag_icon = QLabel("✦")
        self.tag_icon.setStyleSheet("color: #D97706; font-size: 11px; font-weight: bold;")
        h_layout.addWidget(self.tag_icon)

        self.flow_container = QWidget()
        self.flow_layout = QHBoxLayout(self.flow_container)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(4)
        h_layout.addWidget(self.flow_container, 1)

        self.conf_badge = QLabel("98% tin cậy")
        self.conf_badge.setStyleSheet("""
            background: #E8F5E9;
            color: #1B5E20;
            border-radius: 4px;
            padding: 1px 5px;
            font-size: 10px;
            font-weight: 600;
        """)
        h_layout.addWidget(self.conf_badge)

        self.toggle_btn = QPushButton("▾")
        self.toggle_btn.setFixedSize(18, 18)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setToolTip("Xem các mắt xích suy luận")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #8C8275;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #2B261F;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_details)
        h_layout.addWidget(self.toggle_btn)

        self.main_layout.addWidget(self.header_row)

        # -------------------------------------------------------------
        # Details Drawer (Micro-ladder, collapsed by default)
        # -------------------------------------------------------------
        self.details_box = QWidget()
        self.details_layout = QVBoxLayout(self.details_box)
        self.details_layout.setContentsMargins(4, 2, 4, 4)
        self.details_layout.setSpacing(3)
        self.details_box.hide()
        self.main_layout.addWidget(self.details_box)

        self.hide()

    def set_thinking_state(self, message: str = "Đang suy luận nhiều bước...") -> None:
        """Show dynamic pulsing thinking phase."""
        self._clear_flow()
        lbl = QLabel(f"Đang suy nghĩ: {message}")
        lbl.setStyleSheet("color: #B45309; font-size: 11px; font-style: italic;")
        self.flow_layout.addWidget(lbl)
        self.conf_badge.setText("⚡ CoT")
        self.conf_badge.setStyleSheet("background: #FEF3C7; color: #92400E; border-radius: 4px; padding: 1px 5px; font-size: 10px;")
        self.details_box.hide()
        self.is_details_expanded = False
        self.toggle_btn.hide()
        self.show()
        self.heightChanged.emit()

    def set_steps(
        self,
        steps: List[str],
        latency_ms: float = 0.0,
        confidence: float = 1.0,
        strategy: str = "CoT",
    ) -> None:
        """Populate the CoT ribbon and details drawer with verified steps."""
        if not steps:
            self.hide()
            self.heightChanged.emit()
            return

        self._current_steps = steps
        self._clear_flow()
        self._clear_details()

        # Build Flow Pills
        phase_names = self._extract_phase_labels(steps)
        for i, (name, icon) in enumerate(phase_names):
            if i > 0:
                sep = QLabel("→")
                sep.setStyleSheet("color: #C4B9A9; font-size: 9px;")
                self.flow_layout.addWidget(sep)

            pill = QLabel(f"{icon} {name}")
            pill.setStyleSheet("""
                background: #F2ECE0;
                color: #3D352E;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 500;
            """)
            self.flow_layout.addWidget(pill)

        self.flow_layout.addStretch()

        # Confidence Badge
        conf_pct = int(confidence * 100) if confidence <= 1.0 else int(confidence)
        if conf_pct >= 90:
            self.conf_badge.setText(f"✓ {conf_pct}% tin cậy")
            self.conf_badge.setStyleSheet("background: #E8F5E9; color: #1B5E20; border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 600;")
        elif conf_pct >= 70:
            self.conf_badge.setText(f"⚡ {conf_pct}%")
            self.conf_badge.setStyleSheet("background: #FEF3C7; color: #92400E; border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 600;")
        else:
            self.conf_badge.setText(f"{conf_pct}%")
            self.conf_badge.setStyleSheet("background: #F3EFE8; color: #786F66; border-radius: 4px; padding: 1px 5px; font-size: 10px;")

        # Populate Details Drawer
        for idx, step_txt in enumerate(steps):
            step_row = QLabel(f"<b>{idx + 1}.</b> {step_txt}")
            step_row.setStyleSheet("color: #2E2822; font-size: 10.5px; line-height: 1.3;")
            step_row.setWordWrap(True)
            self.details_layout.addWidget(step_row)

        self.toggle_btn.show()
        self.toggle_btn.setText("▾")
        self.details_box.hide()
        self.is_details_expanded = False
        self.show()
        self.heightChanged.emit()

    def _extract_phase_labels(self, steps: List[str]) -> List[tuple[str, str]]:
        """Map text steps to compact phase icons & labels."""
        phases = []
        for s in steps:
            s_low = s.lower()
            if "phân rã" in s_low or "mã môn" in s_low or "decompose" in s_low or "nhận diện" in s_low:
                phases.append(("Phân rã", "🔍"))
            elif "truy xuất" in s_low or "fts5" in s_low or "vector" in s_low or "retrieve" in s_low or "khai thác" in s_low:
                phases.append(("Truy xuất", "⚡"))
            elif "kiểm chứng" in s_low or "vgc" in s_low or "pal" in s_low or "verify" in s_low or "hợp lệ" in s_low:
                phases.append(("Kiểm chứng", "✓"))
            elif "sửa lỗi" in s_low or "typo" in s_low or "levenshtein" in s_low:
                phases.append(("Sửa lỗi", "🛠️"))
            elif "quy chế" in s_low or "tính toán" in s_low or "điểm" in s_low:
                phases.append(("Logic", "🎯"))
            else:
                # Truncate step summary
                short_text = s[:14] + "…" if len(s) > 14 else s
                phases.append((short_text, "•"))

        # Deduplicate consecutive similar phases
        dedup = []
        for p in phases:
            if not dedup or dedup[-1][0] != p[0]:
                dedup.append(p)
        return dedup[:4] if dedup else [("Suy luận", "✦")]

    def toggle_details(self) -> None:
        """Toggle the micro-ladder drawer."""
        self.is_details_expanded = not self.is_details_expanded
        self.toggle_btn.setText("▴" if self.is_details_expanded else "▾")
        self.details_box.setVisible(self.is_details_expanded)
        self.heightChanged.emit()

    def clear(self) -> None:
        """Hide and reset CoT strip."""
        self._current_steps = []
        self._clear_flow()
        self._clear_details()
        self.details_box.hide()
        self.is_details_expanded = False
        self.hide()
        self.heightChanged.emit()

    def _clear_flow(self) -> None:
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_details(self) -> None:
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
