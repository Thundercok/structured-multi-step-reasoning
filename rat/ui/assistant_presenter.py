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


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ArtifactPanel(QWidget):
    """Keep a view instance while its artifact revision is unchanged."""
    def __init__(self, artifacts, provider, registry, on_action=None, on_input=None):
        super().__init__()
        self.provider, self.registry = provider, registry
        self.on_action, self.on_input = on_action, on_input
        self.renderers = {}
        self.artifacts = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.update_artifacts(artifacts)

    def update_from(self, other):
        self.provider, self.registry = other.provider, other.registry
        self.update_artifacts(other.artifacts)

    def update_artifacts(self, artifacts):
        self.artifacts = list(artifacts)
        self.covers_documents = any(a.kind in ("document_search", "document_content", "book_page_search", "book_page_content") for a in artifacts)
        ids = {a.id for a in artifacts}
        for key in list(self.renderers):
            if key not in ids:
                old = self.renderers.pop(key)
                self.layout.removeWidget(old)
                old.hide()
                old.deleteLater()
        for art in artifacts:
            old = self.renderers.get(art.id)
            if old and old.artifact.revision == art.revision:
                continue
            state = old.view_state() if old else {}
            spec = self.provider.provide_view(art)
            valid, reason = validate_view_spec(spec, art, self.registry)
            if not valid:
                spec = StandardViewProvider(self.registry).provide_view(art)
                valid, fallback_reason = validate_view_spec(spec, art, self.registry)
                if not valid:
                    raise ValueError(fallback_reason)
            renderer = QtViewRenderer(spec, artifact=art)
            renderer.set_compact(getattr(old, '_compact', True))
            renderer.restore_view_state(state)
            if reason:
                renderer.setToolTip("Đề xuất trình bày bị từ chối: " + reason)
            if self.on_action:
                renderer.action_dispatched.connect(self.on_action)
            if self.on_input:
                renderer.input_submitted.connect(self.on_input)
            if old:
                position = self.layout.indexOf(old)
                self.layout.removeWidget(old)
                old.hide()
                old.deleteLater()
                self.layout.insertWidget(position, renderer)
            else:
                self.layout.addWidget(renderer)
            self.renderers[art.id] = renderer


def source_panel(sources, open_natal=None, task_state=None, *, artifacts=None,
                 on_action=None, on_input=None, view_provider=None, registry=None):
    provider = view_provider or StandardViewProvider(registry)
    registry = registry or getattr(provider, "registry", None)
    active = [artifact for artifact in (artifacts or [])
              if artifact.provenance.get("presentation") != "trace"]
    if active:
        return ArtifactPanel(active, provider, registry, on_action, on_input)
    # Old recorded observations can still be viewed; live execution publishes artifacts.
    for source in sources or []:
        if source.get("type") == "natal_chart" and source.get("chart"):
            chart = source["chart"]
            active.append(Artifact("recorded-chart", "natal_chart", payload={"chart": chart},
                                   inputs=chart.get("birth", {}), title="Lá số đã tính"))
    if active:
        return ArtifactPanel(active, provider, registry)
    return schedule_card(sources)
