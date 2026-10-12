"""Convert actual tool observations and versioned artifacts to actionable UI cards, without judging answers."""
from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

from rat.engine.reranker import SearchResultItem
from rat.kernel.contracts import Artifact, InputRequest
from rat.kernel.view_spec import StandardViewProvider, validate_view_spec
from rat.ui.view_renderer import QtViewRenderer


def document_cards(sources):
    cards, seen = [], set()
    for source in sorted(sources, key=lambda s: not s.get("read", False)):
        path = source.get("path")
        if source.get("type") != "document" or not path or path in seen:
            continue
        seen.add(path)
        p = Path(path)
        try:
            stat = p.stat()
            size, modified = stat.st_size, stat.st_mtime
        except OSError:
            size, modified = 0, time.time()
        cards.append(SearchResultItem(
            file_path=path, file_name=source.get("filename") or p.name,
            file_ext=source.get("extension") or p.suffix, file_size=size,
            modified_at=modified, score=0, explanation="Đã đọc" if source.get("read") else "Đã tìm thấy",
            snippet=source.get("snippet", ""), verified=False,
        ))
    return cards[:4]


def schedule_card(sources):
    from rat.timetable.model import ClassSession
    from rat.ui.chat_stream import TimetableDeckWidget
    schedules = [s for s in sources if s.get("type") == "schedule"]
    sessions, seen = [], set()
    for s in schedules:
        key = (s.get("day_code"), s.get("course_code"), s.get("course_name"), s.get("start_period"))
        if key in seen or "start_period" not in s or "end_period" not in s:
            continue
        seen.add(key)
        sessions.append(ClassSession(
            start_period=s["start_period"], end_period=s["end_period"], course_name=s["course_name"],
            room=s.get("room", ""), degree_level=s.get("degree_level", "undergrad"),
            course_code=s.get("course_code", ""), lecturer=s.get("instructor", ""),
            notes=s.get("day", ""),
        ))
    if not sessions:
        return None
    return TimetableDeckWidget(sessions[:4], day_label=schedules[0].get("day", "đã tra"))


def source_panel(
    sources,
    open_natal=None,
    task_state=None,
    *,
    artifacts: Optional[List[Artifact]] = None,
    on_action: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
    on_input: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    view_provider=None,
):
    """Compose actual schedule, document, and natal chart artifacts into one presentation panel."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

    provider = view_provider or StandardViewProvider()

    # Determine artifacts to render
    active_artifacts: List[Artifact] = list(artifacts or [])

    # If no explicit artifacts, synthesize from sources for seamless backward compatibility
    if not active_artifacts and sources:
        charts = [s["chart"] for s in sources if s.get("type") == "natal_chart" and s.get("chart")]
        for idx, chart in enumerate(charts[-2:]):
            birth = chart.get("birth", {})
            name = birth.get("name", "Lá số cá nhân")
            art = Artifact(
                id=f"art_natal_legacy_{idx}",
                kind="natal_chart",
                revision=1,
                payload={"chart": chart},
                inputs=dict(birth),
                title=f"✧ Lá số · {name}",
            )
            active_artifacts.append(art)

        # Check for input requests or candidate places
        places = [s["candidates"] for s in sources if s.get("type") == "birth_places" and s.get("candidates")]
        if places and not charts:
            cands = places[-1]
            art = Artifact(
                id="art_places_choice",
                kind="input_request",
                revision=1,
                payload={
                    "operation_name": "create_natal_chart",
                    "prompt": "Tìm thấy nhiều địa điểm phù hợp. Vui lòng chọn địa điểm chính xác:",
                    "candidate_choices": cands,
                    "missing_fields": [],
                    "supplied_inputs": {},
                },
                title="Chọn địa điểm",
            )
            active_artifacts.append(art)

    # Legacy schedule card fallback if no schedule artifact
    has_schedule_art = any(a.kind == "schedule" for a in active_artifacts)
    agenda = None if has_schedule_art else schedule_card(sources)

    if not active_artifacts and not agenda and not task_state:
        return None

    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    # Task state banner
    if task_state:
        text = "Mục tiêu Chuột ghi nhận: " + task_state.get("goal", "")
        if task_state.get("constraints"):
            text += "\nGiới hạn: " + " · ".join(task_state["constraints"][:3])
        if task_state.get("remaining"):
            text += "\nCòn cần: " + " · ".join(task_state["remaining"][:3])
        memory = QLabel(text)
        memory.setTextFormat(Qt.TextFormat.PlainText)
        memory.setWordWrap(True)
        memory.setStyleSheet(
            "QLabel { background: #F3EEE4; color: #625749; border-radius: 8px; padding: 9px; font-size: 11px; }"
        )
        memory.setToolTip("Đây là trạng thái do model ghi nhận; chưa phải xác nhận đã hoàn thành đúng yêu cầu.")
        layout.addWidget(memory)

    if agenda:
        layout.addWidget(agenda)

    # Render versioned artifacts via ViewSpec and QtViewRenderer
    for art in active_artifacts:
        try:
            view_spec = provider.provide_view(art)
            is_valid, reason = validate_view_spec(view_spec, art)
            if not is_valid:
                # If provider proposed an invalid spec, fallback to generic view
                fallback_provider = StandardViewProvider()
                view_spec = fallback_provider._view_generic(art, {})

            renderer = QtViewRenderer(view_spec, artifact=art, is_latest=(art.status != "stale"))
            if on_action:
                renderer.action_dispatched.connect(on_action)
            if on_input:
                renderer.input_submitted.connect(on_input)

            layout.addWidget(renderer)
        except Exception as exc:
            err_box = QLabel(f"Lỗi hiển thị kết quả {art.id}: {exc}")
            err_box.setStyleSheet("color: #9B3F4B; font-size: 11px;")
            layout.addWidget(err_box)

    return panel
