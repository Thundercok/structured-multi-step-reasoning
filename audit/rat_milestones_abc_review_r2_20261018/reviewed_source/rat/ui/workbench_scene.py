"""
rat.ui.workbench_scene — Native PyQt6 two-level Workbench Scene (Argon slice).

Provides a desk-like workspace where RAT and the user work side-by-side:
- Level 1 (overview): Observed sources (capped at ~5 primary desk objects with
  expandable overflow), attentive excerpt attached to its source, grounded
  relationships (only when backed by real file/excerpt, artifact derivation ref,
  or revision history), and forming/committed result card.
- Level 2 (source_detail): Deep inspection of a single observed source and its
  read scope using the existing QtViewRenderer / StandardViewProvider, without
  triggering model calls, extra file reads, task mutations, or composer draft loss.

Gated behind environment flag `RAT_WORKBENCH_SCENE=1`.
"""
from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rat.engine.work_trace import TraceEntry, build_reasoning_flow, summarize_step
from rat.engine.progressive_search import SearchHit, SearchSnapshot
from rat.kernel.contracts import Artifact, ArtifactStore, DispatchResult
from rat.kernel.view_spec import StandardViewProvider, validate_view_spec
from rat.ui.assistant_presenter import ArtifactPanel
from rat.ui.preview_panel import open_file_default, reveal_in_finder, trigger_quicklook
from rat.ui.surface_layout import motion_enabled
from rat.ui.theme import get_ext_badge_info
from rat.ui.view_renderer import QtViewRenderer
from rat.ui.workbench import FONT_FAMILY, WorkbenchTokens, normalize_command


MAX_PRIMARY_DESK_OBJECTS = 5


def workbench_scene_enabled() -> bool:
    """Return True when the experimental Workbench scene flag is active."""
    app = QApplication.instance()
    if app is not None and app.property("ratWorkbenchScene") is not None:
        return bool(app.property("ratWorkbenchScene"))
    return os.getenv("RAT_WORKBENCH_SCENE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def workbench_finder_enabled() -> bool:
    """Return True when the progressive finder integration is active."""
    app = QApplication.instance()
    if app is not None and app.property("ratWorkbenchFinder") is not None:
        return bool(app.property("ratWorkbenchFinder"))
    return os.getenv("RAT_WORKBENCH_FINDER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def sanitize_public_text(text: Any, *, max_chars: int = 600, max_len: Optional[int] = None) -> str:
    """Sanitize public display text; strip internal prefixes, thoughts, raw tool JSON, and user paths."""
    if text is None:
        return ""
    limit = max_len if max_len is not None else max_chars
    raw = str(text).strip()
    if not raw:
        return ""
    cleaned_lines: List[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^(?:thought|raw_completion|model_input|system_prompt)\s*:", s, flags=re.I):
            continue
        if s.startswith("{") and any(
            k in s for k in ('"thought"', '"tool_args"', '"arguments"', '"raw_completion"', '"model_input"')
        ):
            continue
        cleaned_lines.append(s)
    raw = "\n".join(cleaned_lines).strip()
    if not raw:
        return ""
    # Remove internal cancellation codes or raw exception prefixes
    raw = re.sub(r"^cancelled:[a-z0-9_]+\s*:?\s*", "Đã dừng. ", raw, flags=re.I)
    raw = re.sub(r"^(?:ValueError|RuntimeError|OSError)\s*:\s*", "", raw)
    # Collapse home/user directory paths in prose/errors to basename for privacy/clarity
    raw = re.sub(
        r"(?:/Users/[^/\s,:;\"')]+|/home/[^/\s,:;\"')]+)(?:/[^\s,:;\"')]+)+",
        lambda m: Path(m.group(0)).name,
        raw,
    )
    raw = re.sub(r"[ \t]+", " ", raw)
    if len(raw) > limit:
        return raw[: limit - 1].rstrip() + "…"
    return raw


def sanitize_error_text(error: Any) -> str:
    """Convert raw error codes/exceptions into concise public Vietnamese status."""
    if not error:
        return "Còn một bước chưa hoàn tất."
    raw = str(error).strip()
    known = {
        "cancelled": "Đã dừng theo yêu cầu.",
        "cancelled:execution_cancelled": "Đã dừng theo yêu cầu.",
        "cancelled:conversation_reset": "Phiên làm việc đã đặt lại.",
        "token_budget_exhausted": "Chưa hoàn tất trong giới hạn lượt này.",
        "step_budget_exhausted": "Chưa hoàn tất trong giới hạn bước hiện tại.",
        "controller_finish_refused": "Chưa đủ dữ kiện để kết luận.",
        "completion_unresolved": "Cần thu hẹp yêu cầu để hoàn tất.",
        "verification_failed": "Kết luận chưa khớp khi đối chiếu dữ kiện.",
        "verification_unresolved": "Chưa đối chiếu xong kết luận.",
        "selected_document_read_failed": "Không đọc lại được tệp đã chọn.",
        "selected_document_no_text": "Phần đã đọc không có văn bản.",
        "stale_revision": "Phiên bản kết quả đã thay đổi.",
    }
    if raw in known:
        return known[raw]
    lines = [
        ln.strip()
        for ln in raw.splitlines()
        if ln.strip() and not ln.strip().startswith("Traceback (most recent call last)")
    ]
    compact = lines[-1] if lines else raw
    return sanitize_public_text(compact, max_chars=240)


# =========================================================================
# 1. PROJECTION DATACLASSES
# =========================================================================
@dataclass
class SceneSourceNode:
    node_id: str
    kind: str  # "document", "book_pages", "schedule", "natal_chart", "calculation", "artifact"
    title: str
    subtitle: str = ""
    scope_label: str = ""
    snippet: str = ""
    file_path: Optional[str] = None
    artifact_id: Optional[str] = None
    revision: Optional[int] = None
    previous_revision: Optional[int] = None
    read: bool = False
    truncated: bool = False
    page: Optional[int] = None
    page_label: Optional[str] = None
    searched_range: Optional[Tuple[int, int]] = None
    matched_pages: Optional[int] = None
    read_chars: Optional[int] = None
    total_chars: Optional[int] = None
    available: bool = True
    availability_note: str = ""
    order_index: int = 0
    is_compact_ref: bool = False
    is_attentive: bool = False

    def refresh_availability(self) -> None:
        if self.file_path:
            p = Path(self.file_path)
            if p.is_absolute() and p.is_file():
                self.available = True
                self.availability_note = ""
            else:
                self.available = False
                self.availability_note = "Tệp không còn trên máy"


@dataclass
class SceneExcerptNode:
    node_id: str
    parent_source_id: str
    title: str
    snippet: str
    scope_badge: str = ""
    file_path: Optional[str] = None
    page: Optional[int] = None
    page_label: Optional[str] = None
    artifact_id: Optional[str] = None
    revision: Optional[int] = None


@dataclass
class SceneResultNode:
    node_id: str
    title: str
    summary: str = ""
    answer_text: str = ""
    status: str = "working"  # "working", "ready", "waiting", "error", "cancelled"
    status_label: str = ""
    artifact_id: Optional[str] = None
    kind: Optional[str] = None
    revision: Optional[int] = None
    previous_revision: Optional[int] = None
    source_refs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SceneEdge:
    edge_id: str
    source_id: str
    target_id: str
    kind: str  # "file_contains_excerpt" | "artifact_derived_from_ref" | "revision_supersedes"
    label: str


@dataclass
class WorkSceneSnapshot:
    generation: int
    turn_id: Optional[str]
    execution_id: Optional[str]
    query: str
    phase: str  # "empty", "working", "waiting", "done", "error", "cancelled"
    phase_label: str
    rat_speech: str
    actor_state: str
    prop_kind: str
    primary_sources: List[SceneSourceNode]
    overflow_sources: List[SceneSourceNode]
    active_excerpt: Optional[SceneExcerptNode]
    result_node: Optional[SceneResultNode]
    edges: List[SceneEdge]
    trace_entries: List[TraceEntry]
    reasoning_flow: List[TraceEntry] = field(default_factory=list)
    qa_telemetry: Optional[Dict[str, Any]] = None


def parse_scene_command(
    text: str,
    sources: Sequence[SceneSourceNode],
    *,
    in_source_detail: bool = False,
) -> Optional[Tuple[str, Optional[str]]]:
    """
    Parse local navigation commands between overview and a specific source.
    Returns:
      - ("overview", None) to return to overview
      - ("source_detail", node_id) to inspect a source
      - None if `text` is not a local scene navigation command.
    """
    cmd = normalize_command(text)
    if not cmd:
        return None

    if cmd in {
        "quay lai",
        "tro lai",
        "ve tong quan",
        "tong quan",
        "tong quan cong viec",
        "dong nguon",
    }:
        return ("overview", None)

    if in_source_detail and cmd in {"thu gon", "gon lai"}:
        return ("overview", None)

    prefixes = (
        "xem nguon",
        "mo nguon",
        "doc nguon",
        "chi tiet nguon",
        "di sau vao nguon",
    )
    matched_prefix = next((p for p in prefixes if cmd == p or cmd.startswith(p + " ")), None)
    if matched_prefix is not None:
        if not sources:
            return None
        rest = cmd[len(matched_prefix) :].strip(" :#-")
        if not rest:
            attentive = next((s for s in sources if s.is_attentive), sources[0])
            return ("source_detail", attentive.node_id)
        if rest.isdigit():
            idx = int(rest) - 1
            if 0 <= idx < len(sources):
                return ("source_detail", sources[idx].node_id)
        for src in sources:
            title_norm = normalize_command(src.title)
            stem_norm = normalize_command(Path(src.title).stem)
            if rest in title_norm or (stem_norm and rest in stem_norm):
                return ("source_detail", src.node_id)
        return None

    # Allow "xem chi tiết <tên tệp đã quan sát>" when it explicitly names an observed source
    for prefix in ("xem chi tiet ", "mo chi tiet ", "xem tep "):
        if cmd.startswith(prefix):
            target = cmd[len(prefix) :].strip()
            if not target:
                continue
            for src in sources:
                title_norm = normalize_command(src.title)
                stem_norm = normalize_command(Path(src.title).stem)
                if target == title_norm or (stem_norm and target == stem_norm):
                    return ("source_detail", src.node_id)
    return None


# =========================================================================
# 2. HEADLESS SCENE PROJECTOR (Scoped Ownership, Revisions & Grounded Edges)
# =========================================================================
class WorkSceneProjector:
    """
    Projects real runtime steps, progress phases, and ArtifactStore records into
    a bounded WorkSceneSnapshot.

    Invariants:
    - Enforces generation and execution_id ownership; ignores late callbacks after
      cancel or conversation reset.
    - Never reads raw `thought`, `raw_completion`, or `model_input`.
    - Emits edges ONLY for grounded relationships:
      1. `file_contains_excerpt`: observed file source -> observed read excerpt/page
      2. `artifact_derived_from_ref`: verified artifact ref -> derived artifact
      3. `revision_supersedes`: verified prior revision -> updated artifact revision
    """

    def __init__(self) -> None:
        self.generation: int = 0
        self.active_turn_id: Optional[str] = None
        self.active_execution_id: Optional[str] = None
        self.cancelled_executions: Set[str] = set()
        self.query: str = ""
        self.phase: str = "empty"
        self.phase_label: str = "Sẵn sàng cùng bạn"
        self.rat_speech: str = "Mình ở đây. Bạn cứ nói điều đang cần, rồi mình cùng làm nhé."
        self.actor_state: str = "idle"
        self.prop_kind: str = "plan"

        self._sources: Dict[str, SceneSourceNode] = {}
        self._next_source_order: int = 0
        self.active_excerpt: Optional[SceneExcerptNode] = None
        self.result_node: Optional[SceneResultNode] = None
        self._artifacts: Dict[str, Artifact] = {}
        self._revision_seen: Dict[str, List[int]] = {}
        self._trace_entries: Dict[int, TraceEntry] = {}
        self._steps: List[Any] = []
        self.turn_contract: Optional[Any] = None
        self.reconciliation: Optional[Any] = None
        self.execution_journal: Optional[Any] = None
        self.qa_telemetry: Optional[Dict[str, Any]] = None
        self._finder_intent: Optional[Any] = None
        self._finder_hits_count: int = 0
        self._direct_artifact: Optional[Artifact] = None
        self._streaming_chars: int = 0
        self._streaming_raw_text: str = ""

    def reset(self, *, generation: Optional[int] = None) -> WorkSceneSnapshot:
        if generation is not None:
            self.generation = int(generation)
        else:
            self.generation += 1
        self.active_turn_id = None
        self.active_execution_id = None
        self.cancelled_executions.clear()
        self.query = ""
        self.phase = "empty"
        self.phase_label = "Sẵn sàng cùng bạn"
        self.rat_speech = "Mình ở đây. Bạn cứ nói điều đang cần, rồi mình cùng làm nhé."
        self.actor_state = "idle"
        self.prop_kind = "plan"
        self._sources.clear()
        self._next_source_order = 0
        self.active_excerpt = None
        self.result_node = None
        self._artifacts.clear()
        self._revision_seen.clear()
        self._trace_entries.clear()
        self._steps.clear()
        self.turn_contract = None
        self.reconciliation = None
        self.execution_journal = None
        self.qa_telemetry = None
        self._finder_intent = None
        self._finder_hits_count = 0
        self._direct_artifact = None
        self._streaming_chars = 0
        self._streaming_raw_text = ""
        return self.snapshot()

    def _accepts_callback(
        self,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
        require_active: bool = True,
    ) -> bool:
        if generation is not None and generation != self.generation:
            return False
        if execution_id and execution_id in self.cancelled_executions:
            return False
        if self.active_execution_id is not None:
            if execution_id is not None and execution_id != self.active_execution_id:
                return False
            return True
        if require_active:
            return False
        return True

    def begin_turn(
        self,
        query: str,
        *,
        turn_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        generation: Optional[int] = None,
        turn_contract: Optional[Any] = None,
    ) -> WorkSceneSnapshot:
        if generation is not None:
            self.generation = int(generation)
        self.query = sanitize_public_text(query, max_chars=240)
        self.active_turn_id = str(turn_id) if turn_id is not None else None
        self.active_execution_id = str(execution_id) if execution_id is not None else f"exec-gen-{self.generation}"
        self.phase = "working"
        self.phase_label = "Đã nhận việc"
        self.actor_state = "working"
        self._trace_entries.clear()
        self._steps.clear()
        self.turn_contract = turn_contract
        self.reconciliation = None
        self.execution_journal = None
        self.qa_telemetry = None
        self._finder_intent = None
        self._finder_hits_count = 0
        self._direct_artifact = None
        self._streaming_chars = 0
        self._streaming_raw_text = ""
        for src in self._sources.values():
            src.is_attentive = False
        if self.result_node is not None:
            self.result_node.status = "working"
            self.result_node.status_label = "Đang điều chỉnh · kết quả trước vẫn giữ trên bàn"
            self.rat_speech = "Mình đang điều chỉnh. Phần đã làm vẫn ở đây để bạn xem tiếp."
        else:
            self.rat_speech = "Mình đang tìm dữ kiện và mở phần liên quan cho bạn."
        return self.snapshot()

    def record_turn_contract(
        self,
        contract: Any,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        if not self._accepts_callback(generation=generation, execution_id=execution_id, require_active=True):
            return False
        self.turn_contract = contract
        return True

    def record_finder_intent(self, snapshot: Optional[SearchSnapshot]) -> None:
        if snapshot is None:
            self._finder_intent = None
            self._finder_hits_count = 0
            return
        self._finder_intent = getattr(snapshot, "intent", None)
        self._finder_hits_count = len(getattr(snapshot, "hits", ()) or ())
        if self.phase != "empty" and not self.query and getattr(snapshot, "query", ""):
            self.query = sanitize_public_text(snapshot.query, max_chars=240)

    def record_text_stream(
        self,
        text: str,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        if not self._accepts_callback(generation=generation, execution_id=execution_id, require_active=True):
            return False
        chunk = str(text or "")
        if not chunk:
            return False
        self._streaming_chars += len(chunk)
        self._streaming_raw_text += chunk
        if self.result_node is None:
            self.result_node = SceneResultNode(
                node_id=f"result:turn:{self.active_turn_id or self.generation}",
                title=self.query or "Đang trả lời trên bàn",
                summary="",
                answer_text="",
                status="working",
                status_label="Đang sinh câu trả lời…",
            )
        self.result_node.answer_text = sanitize_public_text(self._streaming_raw_text, max_chars=2000)
        self.result_node.status = "working"
        self.result_node.status_label = "Đang sinh câu trả lời…"
        return True

    def record_progress(
        self,
        status: str,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        if not self._accepts_callback(generation=generation, execution_id=execution_id, require_active=True):
            return False
        clean = sanitize_public_text(status, max_chars=160)
        if not clean:
            return False
        self.phase_label = clean
        # Progress is a phase notice, not a tool completion or fake %
        if self.phase == "working":
            self.rat_speech = clean
        return True

    def _upsert_file_source(
        self,
        path: str,
        *,
        filename: Optional[str] = None,
        snippet: str = "",
        scope_label: str = "",
        read: Optional[bool] = None,
        truncated: Optional[bool] = None,
        page: Optional[int] = None,
        page_label: Optional[str] = None,
        searched_range: Optional[Tuple[int, int]] = None,
        matched_pages: Optional[int] = None,
        read_chars: Optional[int] = None,
        total_chars: Optional[int] = None,
        artifact_id: Optional[str] = None,
        revision: Optional[int] = None,
        attentive: bool = False,
    ) -> SceneSourceNode:
        norm_path = str(path).strip()
        node_id = f"source:file:{norm_path}"
        node = self._sources.get(node_id)
        display_name = filename or Path(norm_path).name or norm_path
        if node is None:
            node = SceneSourceNode(
                node_id=node_id,
                kind="document",
                title=display_name,
                subtitle=Path(norm_path).suffix.upper().lstrip(".") or "TỆP",
                scope_label=scope_label or "Đã tìm thấy trong chỉ mục",
                snippet=sanitize_public_text(snippet, max_chars=280),
                file_path=norm_path,
                artifact_id=artifact_id,
                revision=revision,
                read=bool(read),
                truncated=bool(truncated),
                page=page,
                page_label=page_label,
                searched_range=searched_range,
                matched_pages=matched_pages,
                read_chars=read_chars,
                total_chars=total_chars,
                order_index=self._next_source_order,
            )
            self._next_source_order += 1
            self._sources[node_id] = node
        else:
            if filename:
                node.title = filename
            if scope_label:
                node.scope_label = scope_label
            if snippet:
                node.snippet = sanitize_public_text(snippet, max_chars=280)
            if read is not None:
                node.read = bool(read) or node.read
            if truncated is not None:
                node.truncated = bool(truncated)
            if page is not None:
                node.page = page
            if page_label is not None:
                node.page_label = page_label
            if searched_range is not None:
                node.searched_range = searched_range
            if matched_pages is not None:
                node.matched_pages = matched_pages
            if read_chars is not None:
                node.read_chars = read_chars
            if total_chars is not None:
                node.total_chars = total_chars
            if artifact_id is not None:
                node.artifact_id = artifact_id
            if revision is not None:
                node.revision = revision

        if attentive:
            for other in self._sources.values():
                other.is_attentive = False
            node.is_attentive = True
            node.is_compact_ref = False
        node.refresh_availability()
        return node

    def _record_revision(self, artifact: Artifact, store: Optional[ArtifactStore] = None) -> Optional[int]:
        history = self._revision_seen.setdefault(artifact.id, [])
        if store is not None:
            try:
                for h_art in store.get_history(artifact.id):
                    if h_art.revision not in history:
                        history.append(h_art.revision)
            except Exception:
                pass
        parent_rev = artifact.provenance.get("parent_revision")
        if isinstance(parent_rev, int) and parent_rev not in history:
            history.append(parent_rev)
        if artifact.revision not in history:
            history.append(artifact.revision)
        history.sort()
        prior = [r for r in history if r < artifact.revision]
        return prior[-1] if prior else None

    def _ingest_artifact(
        self,
        artifact: Artifact,
        *,
        store: Optional[ArtifactStore] = None,
        is_direct: bool = False,
    ) -> None:
        self._artifacts[artifact.id] = artifact
        if is_direct:
            self._direct_artifact = artifact
            if artifact.kind in ("input_request", "application_launch"):
                self._steps.clear()
                self._trace_entries.clear()
                self.turn_contract = None
                self.reconciliation = None
                self.execution_journal = None
                self.qa_telemetry = None
                self._streaming_chars = 0
                self._streaming_raw_text = ""
        prev_rev = self._record_revision(artifact, store=store)
        data = artifact.payload if isinstance(artifact.payload, dict) else {}
        kind = artifact.kind
        if store is not None and kind != "input_request":
            for stale_id in [
                aid for aid, a in list(self._artifacts.items())
                if a.kind == "input_request" and store.get(aid) is None
            ]:
                self._artifacts.pop(stale_id, None)

        if kind == "document_search":
            items = data.get("items", data.get("results", []))
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and item.get("path"):
                    self._upsert_file_source(
                        item["path"],
                        filename=item.get("filename"),
                        snippet=item.get("snippet", ""),
                        scope_label="Đã tìm thấy trong chỉ mục",
                        read=False,
                        artifact_id=artifact.id,
                        revision=artifact.revision,
                    )
            self.prop_kind = "file"
            self.actor_state = "searching"
            return

        if kind == "document_content":
            path = data.get("path")
            if isinstance(path, str) and path:
                content = str(data.get("content", ""))
                read_chars = len(content)
                total_chars = int(data.get("total_chars", read_chars) or read_chars)
                truncated = bool(data.get("truncated"))
                scope = f"Đã đọc {read_chars:,}/{total_chars:,} ký tự" + (" · phần đầu" if truncated else "")
                src = self._upsert_file_source(
                    path,
                    filename=data.get("filename"),
                    snippet=content[:280],
                    scope_label=scope,
                    read=True,
                    truncated=truncated,
                    read_chars=read_chars,
                    total_chars=total_chars,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                    attentive=True,
                )
                self.active_excerpt = SceneExcerptNode(
                    node_id=f"excerpt:{src.node_id}",
                    parent_source_id=src.node_id,
                    title=f"Đoạn đã đọc · {src.title}",
                    snippet=sanitize_public_text(content, max_chars=360),
                    scope_badge=scope,
                    file_path=path,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                )
                self.prop_kind = "file"
                self.rat_speech = f"Đã mở {src.title} ({scope}). Chạm thẻ nguồn nếu bạn muốn đọc chi tiết."
            return

        if kind == "book_page_search":
            path = data.get("path")
            if isinstance(path, str) and path:
                s_range = tuple(data.get("searched_range", (1, 1)))
                matched = int(data.get("matched_pages", 0) or 0)
                scope = f"Tìm trang PDF {s_range[0]}–{s_range[1]} · {matched} trang khớp"
                items = data.get("items", [])
                first_snip = items[0].get("snippet", "") if items else ""
                src = self._upsert_file_source(
                    path,
                    filename=data.get("filename"),
                    snippet=first_snip,
                    scope_label=scope,
                    searched_range=(int(s_range[0]), int(s_range[1])),
                    matched_pages=matched,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                    attentive=True,
                )
                if items and isinstance(items[0], dict):
                    top = items[0]
                    pg = top.get("page")
                    pg_lbl = str(top.get("page_label", pg))
                    self.active_excerpt = SceneExcerptNode(
                        node_id=f"excerpt:{src.node_id}:p{pg}",
                        parent_source_id=src.node_id,
                        title=f"{src.title} · Trang PDF {pg} (nhãn {pg_lbl})",
                        snippet=sanitize_public_text(top.get("snippet", ""), max_chars=360),
                        scope_badge=f"Trang PDF {pg} · Nhãn {pg_lbl}",
                        file_path=path,
                        page=pg,
                        page_label=pg_lbl,
                        artifact_id=artifact.id,
                        revision=artifact.revision,
                    )
                self.prop_kind = "file"
            return

        if kind == "book_page_content":
            path = data.get("path")
            if isinstance(path, str) and path:
                page = int(data.get("page", 1) or 1)
                page_label = str(data.get("page_label", page))
                content = str(data.get("content", ""))
                read_chars = len(content)
                total_chars = int(data.get("total_chars", read_chars) or read_chars)
                truncated = bool(data.get("truncated"))
                scope = f"Trang PDF {page} (nhãn {page_label}) · {read_chars:,}/{total_chars:,} ký tự"
                src = self._upsert_file_source(
                    path,
                    filename=data.get("filename"),
                    snippet=content[:280],
                    scope_label=scope,
                    read=True,
                    truncated=truncated,
                    page=page,
                    page_label=page_label,
                    read_chars=read_chars,
                    total_chars=total_chars,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                    attentive=True,
                )
                self.active_excerpt = SceneExcerptNode(
                    node_id=f"excerpt:{src.node_id}:p{page}",
                    parent_source_id=src.node_id,
                    title=f"{src.title} · Trang PDF {page} (nhãn {page_label})",
                    snippet=sanitize_public_text(content, max_chars=360),
                    scope_badge=scope,
                    file_path=path,
                    page=page,
                    page_label=page_label,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                )
                self.prop_kind = "file"
                self.rat_speech = f"Đã đọc trang PDF {page} của {src.title}."
            return

        if kind == "document_file":
            path = data.get("path")
            if isinstance(path, str) and path and data.get("delivered"):
                src = self._upsert_file_source(
                    path,
                    filename=data.get("filename"),
                    scope_label="Tệp gốc trên máy",
                    read=True,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                    attentive=True,
                )
                self.prop_kind = "file"
                if self.result_node is None:
                    self.result_node = SceneResultNode(
                        node_id=f"result:{artifact.id}",
                        title=src.title,
                        summary="Tệp gốc trên máy đã sẵn sàng để mở." if src.available else "Tệp không còn trên máy.",
                        status="ready" if src.available else "error",
                        status_label="Đã giao tệp" if src.available else "Tệp không còn trên máy",
                        artifact_id=artifact.id,
                        kind=kind,
                        revision=artifact.revision,
                        previous_revision=prev_rev,
                    )
            return

        if kind == "calculation":
            expr = str(data.get("expression", artifact.inputs.get("expression", ""))).strip()
            val = str(data.get("result", "")).strip()
            node_id = f"source:art:{artifact.id}"
            node = self._sources.get(node_id)
            scope = f"{expr} = {val}" if expr else f"= {val}"
            if node is None:
                node = SceneSourceNode(
                    node_id=node_id,
                    kind="calculation",
                    title=f"Phép tính · {expr or artifact.id}",
                    subtitle="TÍNH",
                    scope_label=scope,
                    snippet=scope,
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                    read=True,
                    order_index=self._next_source_order,
                )
                self._next_source_order += 1
                self._sources[node_id] = node
            else:
                node.title = f"Phép tính · {expr or artifact.id}"
                node.scope_label = scope
                node.snippet = scope
                node.revision = artifact.revision
            self.prop_kind = "calculation"
            if self.result_node is None or self.result_node.artifact_id == artifact.id:
                self.result_node = SceneResultNode(
                    node_id=f"result:{artifact.id}",
                    title=f"Kết quả tính · {val}",
                    summary=scope,
                    status="ready",
                    status_label=f"Phiên bản {artifact.revision}",
                    artifact_id=artifact.id,
                    kind=kind,
                    revision=artifact.revision,
                    previous_revision=prev_rev,
                )
            return

        if kind == "input_request":
            prompt = sanitize_public_text(data.get("prompt", "Cần thêm thông tin để tiếp tục."), max_chars=240)
            self.phase = "waiting"
            self.phase_label = "Cần thêm thông tin"
            self.actor_state = "waiting"
            self.rat_speech = prompt
            self.result_node = SceneResultNode(
                node_id=f"result:{artifact.id}",
                title=artifact.title or "Cần thêm thông tin",
                summary=prompt,
                status="waiting",
                status_label="Đang chờ bạn xác nhận",
                artifact_id=artifact.id,
                kind=kind,
                revision=artifact.revision,
                previous_revision=prev_rev,
            )
            return

        if kind == "application_launch":
            app_name = str(data.get("name") or artifact.title or "Ứng dụng").strip()
            status_note = sanitize_public_text(
                data.get("status_note")
                or f"Hệ điều hành đã nhận lệnh mở {app_name}.",
                max_chars=260,
            )
            self.prop_kind = "note"
            self.result_node = SceneResultNode(
                node_id=f"result:{artifact.id}",
                title=artifact.title or f"Mở ứng dụng · {app_name}",
                summary=status_note,
                answer_text=status_note,
                status="ready",
                status_label="Hệ điều hành đã nhận lệnh",
                artifact_id=artifact.id,
                kind=kind,
                revision=artifact.revision,
                previous_revision=prev_rev,
            )
            if is_direct:
                self.phase = "done"
                self.phase_label = "Đã gửi lệnh mở"
                self.actor_state = "done"
                self.rat_speech = status_note
            return

        # Deliverables: natal_chart, result_table, schedule, file_export, or generic artifact
        refs: List[Dict[str, Any]] = []
        if isinstance(data.get("source_refs"), list):
            refs.extend(copy.deepcopy(r) for r in data["source_refs"] if isinstance(r, dict))
        src_art_id = artifact.provenance.get("source_artifact_id")
        if isinstance(src_art_id, str) and src_art_id:
            refs.append(
                {
                    "artifact_id": src_art_id,
                    "revision": artifact.provenance.get("source_revision", 1),
                    "title": src_art_id,
                }
            )

        # Ensure any referenced source artifacts exist as source nodes on the desk
        for ref in refs:
            ref_id = ref.get("artifact_id")
            if not isinstance(ref_id, str) or not ref_id:
                continue
            ref_art = (store.get(ref_id) if store is not None else None) or self._artifacts.get(ref_id)
            if ref_art is not None:
                self._ensure_artifact_source_node(ref_art, ref_dict=ref, store=store)

        summary = self._summarize_deliverable(artifact)
        if kind == "natal_chart":
            self.prop_kind = "note"
        elif kind in ("result_table", "schedule"):
            self.prop_kind = "plan"
        elif kind == "file_export":
            self.prop_kind = "file"

        # If this artifact is already tracked as an upstream source on the desk
        # (e.g., an input to a derived result_table), keep its source node updated.
        src_node_id = f"source:art:{artifact.id}"
        if src_node_id in self._sources:
            self._ensure_artifact_source_node(artifact, store=store)

        # If the current result_node is a derived artifact that references this artifact
        # as an upstream source, keep the derived result_node in place so stale-ref
        # detection and derived context remain visible on the desk.
        is_upstream_of_current_result = bool(
            self.result_node is not None
            and self.result_node.artifact_id != artifact.id
            and any(r.get("artifact_id") == artifact.id for r in self.result_node.source_refs)
        )
        if not is_upstream_of_current_result:
            existing_answer = (
                self.result_node.answer_text
                if (self.result_node and self.result_node.artifact_id == artifact.id)
                else ""
            )
            self.result_node = SceneResultNode(
                node_id=f"result:{artifact.id}",
                title=artifact.title or data.get("title") or kind,
                summary=summary,
                answer_text=existing_answer,
                status="ready",
                status_label=f"Phiên bản {artifact.revision}",
                artifact_id=artifact.id,
                kind=kind,
                revision=artifact.revision,
                previous_revision=prev_rev,
                source_refs=refs,
            )
        if is_direct:
            self.phase = "done"
            self.phase_label = "Đã cập nhật"
            self.actor_state = "done"
            target_title = artifact.title or data.get("title") or kind
            if prev_rev is not None:
                self.rat_speech = f"Đã cập nhật {target_title} sang phiên bản {artifact.revision}."
            else:
                self.rat_speech = f"Đã tạo xong {target_title}."

    def _summarize_deliverable(self, artifact: Artifact) -> str:
        data = artifact.payload if isinstance(artifact.payload, dict) else {}
        kind = artifact.kind
        if kind == "application_launch":
            return sanitize_public_text(data.get("status_note") or data.get("path") or "", max_chars=180)
        if kind == "natal_chart":
            chart = data.get("chart", data)
            birth = chart.get("birth", artifact.inputs) if isinstance(chart, dict) else artifact.inputs
            place = birth.get("place", "")
            date_s = birth.get("date", "")
            time_s = birth.get("time", "")
            return f"{date_s} {time_s} · {place}".strip(" ·")
        if kind == "result_table":
            refs = data.get("source_refs", [])
            return f"Ghép từ {len(refs) if isinstance(refs, list) else 0} nguồn dữ liệu đã quan sát."
        if kind == "schedule":
            items = data.get("items", [])
            return f"Có {len(items) if isinstance(items, list) else 0} ca học trong lịch."
        if kind == "file_export":
            exp_path = data.get("exported_path", "")
            return Path(exp_path).name if exp_path else str(data.get("filename", ""))
        if kind == "calculation":
            expr = str(data.get("expression", artifact.inputs.get("expression", ""))).strip()
            val = str(data.get("result", "")).strip()
            return f"{expr} = {val}".strip(" =")
        return sanitize_public_text(data.get("summary", ""), max_chars=180)

    def _ensure_artifact_source_node(
        self,
        artifact: Artifact,
        *,
        ref_dict: Optional[Dict[str, Any]] = None,
        store: Optional[ArtifactStore] = None,
    ) -> SceneSourceNode:
        self._artifacts[artifact.id] = artifact
        prev_rev = self._record_revision(artifact, store=store)
        node_id = f"source:art:{artifact.id}"
        node = self._sources.get(node_id)
        summary = self._summarize_deliverable(artifact)
        scope = f"Phiên bản {artifact.revision}" + (f" · {summary}" if summary else "")
        title = artifact.title or (ref_dict.get("title") if isinstance(ref_dict, dict) else None) or artifact.id
        badge_map = {
            "natal_chart": "LÁ SỐ",
            "calculation": "TÍNH",
            "schedule": "LỊCH",
            "document_content": "TÀI LIỆU",
            "book_page_content": "TRANG SÁCH",
            "application_launch": "ỨNG DỤNG",
        }
        subtitle = badge_map.get(artifact.kind, artifact.kind.upper()[:10])
        if node is None:
            node = SceneSourceNode(
                node_id=node_id,
                kind=artifact.kind,
                title=str(title),
                subtitle=subtitle,
                scope_label=scope,
                snippet=summary,
                artifact_id=artifact.id,
                revision=artifact.revision,
                previous_revision=prev_rev,
                read=True,
                order_index=self._next_source_order,
            )
            self._next_source_order += 1
            self._sources[node_id] = node
        else:
            node.title = str(title)
            node.subtitle = subtitle
            node.scope_label = scope
            node.snippet = summary
            if prev_rev is not None:
                node.previous_revision = prev_rev
            node.revision = artifact.revision
            node.read = True
        return node

    def record_step(
        self,
        step: Any,
        *,
        store: Optional[ArtifactStore] = None,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        eff_exec = execution_id or getattr(step, "execution_id", None)
        if not self._accepts_callback(generation=generation, execution_id=eff_exec, require_active=True):
            return False

        step_num = int(getattr(step, "step_number", 0) or (len(self._steps) + 1))
        replaced = False
        for idx, existing in enumerate(self._steps):
            if getattr(existing, "step_number", None) == step_num:
                self._steps[idx] = step
                replaced = True
                break
        if not replaced:
            self._steps.append(step)

        entry = summarize_step(step)
        entry.detail = sanitize_public_text(entry.detail, max_chars=240)
        self._trace_entries[entry.number] = entry

        for art in getattr(step, "artifacts", []) or []:
            if isinstance(art, Artifact):
                self._ingest_artifact(art, store=store)

        name = getattr(step, "tool_name", None)
        res = getattr(step, "tool_result", None)
        if getattr(step, "error", None):
            self.phase_label = sanitize_error_text(step.error)
            return True

        if isinstance(res, dict) and (res.get("error") or res.get("found") is False):
            self.phase_label = sanitize_error_text(res.get("error") or "Bước này chưa có dữ liệu phù hợp.")
            return True

        if name == "search_documents":
            items = (
                res
                if isinstance(res, list)
                else (res.get("documents") or res.get("items") or res.get("results") or [])
                if isinstance(res, dict)
                else []
            )
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict):
                    p = item.get("path") or item.get("file_path")
                    if p:
                        self._upsert_file_source(
                            p,
                            filename=item.get("filename") or item.get("file_name"),
                            snippet=item.get("snippet", ""),
                            scope_label="Đã tìm thấy trong chỉ mục",
                            read=False,
                        )
            self.prop_kind = "file"
            self.actor_state = "searching"
            self.rat_speech = f"Đã tìm thấy {len(items) if isinstance(items, list) else 0} tệp liên quan trên bàn."
        elif name == "read_document" and isinstance(res, dict) and (res.get("found") or res.get("status") == "ok" or res.get("content")):
            path = res.get("path") or res.get("file_path") or ""
            if path and not getattr(step, "artifacts", None):
                content = str(res.get("content", ""))
                read_chars = len(content)
                total_chars = int(res.get("total_chars", read_chars) or read_chars)
                truncated = bool(res.get("truncated"))
                args = getattr(step, "tool_args", None) or {}
                start_line = res.get("start_line") or args.get("start_line")
                end_line = res.get("end_line") or args.get("end_line")
                if start_line is not None and end_line is not None:
                    scope = f"Dòng {start_line}–{end_line} · {read_chars:,}/{total_chars:,} ký tự"
                else:
                    scope = f"Đã đọc {read_chars:,}/{total_chars:,} ký tự" + (" · phần đầu" if truncated else "")
                src = self._upsert_file_source(
                    path,
                    filename=res.get("filename") or res.get("file_name"),
                    snippet=content[:280],
                    scope_label=scope,
                    read=True,
                    truncated=truncated,
                    read_chars=read_chars,
                    total_chars=total_chars,
                    attentive=True,
                )
                self.active_excerpt = SceneExcerptNode(
                    node_id=f"excerpt:{src.node_id}",
                    parent_source_id=src.node_id,
                    title=f"Đoạn đã đọc · {src.title}",
                    snippet=sanitize_public_text(content, max_chars=360),
                    scope_badge=scope,
                    file_path=path,
                )
                self.prop_kind = "file"
                self.rat_speech = f"Đã mở {src.title} ({scope})."
        elif name == "calculate" and isinstance(res, dict) and "result" in res and not getattr(step, "artifacts", None):
            expr = str(res.get("expression", "")).strip()
            val = str(res.get("result", "")).strip()
            node_id = f"source:calc:{expr or step.step_number}"
            if node_id not in self._sources:
                self._sources[node_id] = SceneSourceNode(
                    node_id=node_id,
                    kind="calculation",
                    title=f"Phép tính · {expr}",
                    subtitle="TÍNH",
                    scope_label=f"{expr} = {val}",
                    snippet=f"{expr} = {val}",
                    read=True,
                    order_index=self._next_source_order,
                )
                self._next_source_order += 1
            self.prop_kind = "calculation"
        elif name == "record_work_note" and isinstance(res, dict) and res.get("note"):
            self.actor_state = "noting"
            self.prop_kind = "note"
            self.rat_speech = "Đã ghi lại dữ kiện vào sổ tay trên bàn."
        return True

    def record_artifact_result(
        self,
        result: DispatchResult,
        *,
        store: Optional[ArtifactStore] = None,
        generation: Optional[int] = None,
    ) -> bool:
        if generation is not None and generation != self.generation:
            return False
        if result.status == "cancelled":
            return False
        if result.status not in ("success", "needs_input"):
            self.phase = "error"
            self.actor_state = "error"
            err_msg = sanitize_error_text(result.error)
            self.phase_label = err_msg
            self.rat_speech = f"Vướng một bước: {err_msg} Kết quả trước vẫn được giữ."
            return True

        if result.artifact is not None:
            self._direct_artifact = result.artifact
            self._steps.clear()
            self._trace_entries.clear()
            self.turn_contract = None
            self.reconciliation = None
            self.execution_journal = None
            self.qa_telemetry = None
            self._streaming_chars = 0
            self._streaming_raw_text = ""
            if isinstance(result.artifact.inputs, dict) and result.artifact.inputs.get("query"):
                self.query = sanitize_public_text(result.artifact.inputs.get("query"), max_chars=240)
            self._ingest_artifact(result.artifact, store=store, is_direct=True)
        if result.status == "needs_input" and result.input_request is not None:
            self.phase = "waiting"
            self.actor_state = "waiting"
            self.phase_label = "Cần thêm thông tin"
            self.rat_speech = sanitize_public_text(result.input_request.prompt or "Cần thêm một ý từ bạn.")
        else:
            self.phase = "done"
            self.actor_state = "done"
            self.phase_label = "Đã cập nhật"
        return True

    def record_response(
        self,
        response: Any,
        *,
        store: Optional[ArtifactStore] = None,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        eff_exec = execution_id or getattr(response, "execution_id", None)
        if not self._accepts_callback(generation=generation, execution_id=eff_exec, require_active=True):
            return False

        if getattr(response, "turn_contract", None) is not None:
            self.turn_contract = getattr(response, "turn_contract", None)
        if getattr(response, "reconciliation", None) is not None:
            self.reconciliation = getattr(response, "reconciliation", None)
        if getattr(response, "execution_journal", None) is not None:
            self.execution_journal = getattr(response, "execution_journal", None)
        if getattr(response, "qa_telemetry", None) is not None:
            self.qa_telemetry = copy.deepcopy(getattr(response, "qa_telemetry", None))

        for step in getattr(response, "steps", []) or []:
            if getattr(step, "step_number", None) not in self._trace_entries:
                self.record_step(step, store=store, generation=self.generation, execution_id=eff_exec)

        for art in getattr(response, "artifacts", []) or []:
            if isinstance(art, Artifact):
                self._ingest_artifact(art, store=store)

        self.active_execution_id = None
        error = getattr(response, "error", None)
        pending = getattr(response, "pending_input_request", None)
        rec = getattr(response, "reconciliation", None)
        rec_failed = rec is not None and getattr(rec, "outcome_status", None) in {"failed", "unresolved", "refused"}

        if error == "cancelled":
            self.phase = "cancelled"
            self.phase_label = "Đã dừng"
            self.actor_state = "idle"
            self.rat_speech = "Đã dừng. Những phần đã làm xong vẫn ở trên bàn."
            if self.result_node and self.result_node.status == "working":
                self.result_node.status = "cancelled"
                self.result_node.status_label = "Đã dừng"
            return True

        if error or rec_failed:
            self.phase = "error"
            self.phase_label = "Chưa hoàn tất"
            self.actor_state = "error"
            self.rat_speech = sanitize_error_text(error or "Chưa hoàn tất yêu cầu trong lượt này.")
            if self.result_node and self.result_node.status == "working":
                self.result_node.status = "error"
                self.result_node.status_label = "Chưa hoàn tất"
            return True

        if pending is not None:
            self.phase = "waiting"
            self.phase_label = "Cần thêm thông tin"
            self.actor_state = "waiting"
            prompt = sanitize_public_text(getattr(pending, "prompt", "") or getattr(response, "answer", ""))
            self.rat_speech = prompt or "Cần thêm thông tin từ bạn để tiếp tục."
            return True

        # Completed turn
        self.phase = "done"
        self.phase_label = "Đã xong"
        self.actor_state = "done"
        ans = sanitize_public_text(getattr(response, "answer", ""), max_chars=2000)

        if self.result_node is not None:
            self.result_node.answer_text = ans
            self.result_node.status = "ready"
            if self.result_node.revision:
                self.result_node.status_label = f"Phiên bản {self.result_node.revision}"
            else:
                self.result_node.status_label = "Đã xong"
        elif ans:
            self.result_node = SceneResultNode(
                node_id=f"result:turn:{self.active_turn_id or self.generation}",
                title=self.query or "Kết quả trên bàn",
                summary="",
                answer_text=ans,
                status="ready",
                status_label="Đã xong",
            )

        # Compact observed sources into reference posture once result is committed
        if self.result_node is not None:
            for src in self._sources.values():
                src.is_compact_ref = True

        if self._sources:
            self.rat_speech = "Mình đã đặt kết quả và nguồn tham chiếu trên bàn. Chạm nguồn để xem chi tiết."
        elif len(ans) <= 120 and ans:
            self.rat_speech = ans
        else:
            self.rat_speech = "Xong rồi. Kết quả đã đặt trên bàn để bạn xem."
        return True

    def cancel(
        self,
        execution_id: Optional[str] = None,
        *,
        new_generation: Optional[int] = None,
    ) -> WorkSceneSnapshot:
        target_exec = execution_id or self.active_execution_id
        if target_exec:
            self.cancelled_executions.add(str(target_exec))
        if new_generation is not None:
            self.generation = int(new_generation)
        self.active_execution_id = None
        self.phase = "cancelled"
        self.phase_label = "Đã dừng"
        self.actor_state = "idle"
        self.rat_speech = "Đã dừng. Những phần đã làm xong vẫn ở trên bàn."
        if self.result_node and self.result_node.status == "working":
            self.result_node.status = "cancelled"
            self.result_node.status_label = "Đã dừng"
        return self.snapshot()

    def _compute_edges(self, store: Optional[ArtifactStore] = None) -> List[SceneEdge]:
        edges: List[SceneEdge] = []

        # 1. Grounded relationship: file_contains_excerpt
        if self.active_excerpt is not None:
            parent = self._sources.get(self.active_excerpt.parent_source_id)
            if (
                parent is not None
                and parent.file_path
                and self.active_excerpt.file_path == parent.file_path
            ):
                edges.append(
                    SceneEdge(
                        edge_id=f"edge:excerpt:{parent.node_id}->{self.active_excerpt.node_id}",
                        source_id=parent.node_id,
                        target_id=self.active_excerpt.node_id,
                        kind="file_contains_excerpt",
                        label=self.active_excerpt.scope_badge or "Chứa đoạn đã đọc",
                    )
                )

        # 2. Grounded relationship: artifact_derived_from_ref & revision_supersedes
        if self.result_node is not None:
            for ref in self.result_node.source_refs:
                ref_art_id = ref.get("artifact_id")
                ref_rev = ref.get("revision")
                if not isinstance(ref_art_id, str) or not ref_art_id:
                    continue
                # Verify against ArtifactStore if provided
                if store is not None:
                    current_art = store.get(ref_art_id)
                    specific_art = store.get(ref_art_id, ref_rev) if isinstance(ref_rev, int) else current_art
                    if current_art is None or specific_art is None or specific_art.status != "ready":
                        ref["missing"] = True
                        ref["stale"] = False
                        continue
                    ref["missing"] = False
                    ref["stale"] = bool(isinstance(ref_rev, int) and current_art.revision != ref_rev) or bool(
                        ref.get("historical")
                    )
                else:
                    if ref_art_id not in self._artifacts:
                        ref["missing"] = True
                        continue
                    ref["missing"] = False
                    cur = self._artifacts[ref_art_id]
                    ref["stale"] = bool(isinstance(ref_rev, int) and cur.revision != ref_rev)

                # Match source node in scene
                src_node = next(
                    (s for s in self._sources.values() if s.artifact_id == ref_art_id),
                    None,
                )
                if src_node is not None:
                    lbl = f"Dẫn xuất từ bản {ref_rev}" if ref_rev else "Dẫn xuất từ nguồn"
                    if ref.get("stale"):
                        lbl += " (bản cũ)"
                    edges.append(
                        SceneEdge(
                            edge_id=f"edge:derived:{src_node.node_id}->{self.result_node.node_id}:v{ref_rev}",
                            source_id=src_node.node_id,
                            target_id=self.result_node.node_id,
                            kind="artifact_derived_from_ref",
                            label=lbl,
                        )
                    )

        # 3. Grounded relationship: revision_supersedes
        candidate_nodes: List[Any] = list(self._sources.values())
        if self.result_node is not None:
            candidate_nodes.append(self.result_node)

        for n in candidate_nodes:
            prev_r = n.previous_revision
            curr_r = n.revision
            if (
                n.artifact_id
                and curr_r is not None
                and prev_r is not None
                and curr_r > prev_r
            ):
                valid_history = True
                if store is not None:
                    hist_revs = {a.revision for a in store.get_history(n.artifact_id)}
                    art_obj = store.get(n.artifact_id)
                    parent_rev = art_obj.provenance.get("parent_revision") if art_obj else None
                    valid_history = (prev_r in hist_revs) or (parent_rev == prev_r)
                if valid_history:
                    edges.append(
                        SceneEdge(
                            edge_id=f"edge:rev:{n.artifact_id}:v{prev_r}->v{curr_r}",
                            source_id=f"{n.node_id}@v{prev_r}",
                            target_id=n.node_id,
                            kind="revision_supersedes",
                            label=f"Phiên bản {prev_r} → {curr_r}",
                        )
                    )

        return edges

    def snapshot(self, *, store: Optional[ArtifactStore] = None) -> WorkSceneSnapshot:
        for src in self._sources.values():
            src.refresh_availability()

        ordered_sources = sorted(self._sources.values(), key=lambda s: s.order_index)
        edges = self._compute_edges(store=store)

        reserved = (1 if self.result_node is not None else 0) + (
            1 if self.active_excerpt is not None else 0
        )
        max_primary = max(1, MAX_PRIMARY_DESK_OBJECTS - reserved)

        if len(ordered_sources) <= max_primary:
            primary = list(ordered_sources)
            overflow: List[SceneSourceNode] = []
        else:
            # Keep stable order_index while ensuring attentive/referenced sources stay in primary view
            connected_ids = {e.source_id for e in edges}
            must_keep = [
                s
                for s in ordered_sources
                if s.is_attentive or s.node_id in connected_ids
            ]
            chosen_ids = {s.node_id for s in must_keep[:max_primary]}
            for s in ordered_sources:
                if len(chosen_ids) >= max_primary:
                    break
                chosen_ids.add(s.node_id)
            primary = [s for s in ordered_sources if s.node_id in chosen_ids]
            overflow = [s for s in ordered_sources if s.node_id not in chosen_ids]

        flow = build_reasoning_flow(
            self._steps,
            contract=self.turn_contract,
            reconciliation=self.reconciliation,
            journal=self.execution_journal,
            finder_intent=self._finder_intent,
            finder_hits_count=self._finder_hits_count,
            direct_artifact=self._direct_artifact,
            active_phase=self.phase,
            active_label=self.phase_label,
            streaming_chars=self._streaming_chars,
            error="cancelled" if self.phase == "cancelled" else (self.phase_label if self.phase == "error" else None),
        )

        return WorkSceneSnapshot(
            generation=self.generation,
            turn_id=self.active_turn_id,
            execution_id=self.active_execution_id,
            query=self.query,
            phase=self.phase,
            phase_label=self.phase_label,
            rat_speech=self.rat_speech,
            actor_state=self.actor_state,
            prop_kind=self.prop_kind,
            primary_sources=[copy.deepcopy(s) for s in primary],
            overflow_sources=[copy.deepcopy(s) for s in overflow],
            active_excerpt=copy.deepcopy(self.active_excerpt),
            result_node=copy.deepcopy(self.result_node),
            edges=list(edges),
            trace_entries=[
                copy.deepcopy(self._trace_entries[k])
                for k in sorted(self._trace_entries)
            ],
            reasoning_flow=[copy.deepcopy(e) for e in flow],
            qa_telemetry=copy.deepcopy(self.qa_telemetry),
        )


# =========================================================================
# 3. NATIVE PYQT6 SCENE WIDGETS
# =========================================================================
class SourceCardWidget(QFrame):
    """
    Interactive source card on the Workbench desk.
    Maintains stable identity across incremental updates; clicking/Enter drills
    into source detail without stealing or clearing the composer draft.
    """

    selected = pyqtSignal(str)
    open_file_requested = pyqtSignal(str)

    def __init__(self, node: SceneSourceNode, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.node = node
        self._highlight = 0.0
        self.setObjectName(f"SceneSourceCard_{node.node_id}")
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._anim = QPropertyAnimation(self, b"highlightProgress", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 7, 10, 7)
        self.main_layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.kind_badge = QLabel(self)
        self.kind_badge.setObjectName("SceneSourceBadge")
        self.kind_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_row.addWidget(self.kind_badge)

        self.title_lbl = QLabel(self)
        self.title_lbl.setObjectName("SceneSourceTitle")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top_row.addWidget(self.title_lbl, 1)

        self.btn_open = QPushButton("Mở tệp", self)
        self.btn_open.setObjectName("SceneSourceOpenBtn")
        self.btn_open.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(self._on_open_clicked)
        top_row.addWidget(self.btn_open)

        self.main_layout.addLayout(top_row)

        self.scope_lbl = QLabel(self)
        self.scope_lbl.setObjectName("SceneSourceScope")
        self.scope_lbl.setWordWrap(True)
        self.scope_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.scope_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.main_layout.addWidget(self.scope_lbl)

        self.update_node(node, animate=False)

    @pyqtProperty(float)
    def highlightProgress(self) -> float:
        return self._highlight

    @highlightProgress.setter
    def highlightProgress(self, val: float) -> None:
        self._highlight = float(val)
        self._apply_style()

    def stop_animation(self) -> None:
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        self._highlight = 0.0

    def _on_open_clicked(self) -> None:
        self.node.refresh_availability()
        if self.node.file_path and self.node.available:
            self.open_file_requested.emit(self.node.file_path)
        else:
            self.update_node(self.node, animate=False)

    def update_node(self, node: SceneSourceNode, *, animate: bool = True) -> None:
        changed = (
            node.scope_label != self.node.scope_label
            or node.read != self.node.read
            or node.revision != self.node.revision
            or node.is_compact_ref != self.node.is_compact_ref
            or node.available != self.node.available
        )
        self.node = node
        self.setAccessibleName(f"Nguồn {node.title} · {node.scope_label}")

        badge_text = node.subtitle or ("ĐÃ ĐỌC" if node.read else "NGUỒN")
        if node.is_compact_ref:
            badge_text = "THAM CHIẾU"
        self.kind_badge.setText(badge_text)
        self.title_lbl.setText(node.title)

        scope_parts = [node.scope_label] if node.scope_label else []
        if not node.available and node.availability_note:
            scope_parts.append(node.availability_note)
        self.scope_lbl.setText(" · ".join(p for p in scope_parts if p))

        has_file = bool(node.file_path)
        self.btn_open.setVisible(has_file)
        self.btn_open.setEnabled(has_file and node.available)
        self.btn_open.setText("Mở tệp" if node.available else "Không còn tệp")
        if node.file_path:
            self.btn_open.setToolTip(
                node.file_path if node.available else "Tệp không còn tồn tại trên máy"
            )

        pad_v = 5 if node.is_compact_ref else 7
        self.main_layout.setContentsMargins(10, pad_v, 10, pad_v)
        self._apply_style()

        if animate and changed and motion_enabled() and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.start()
        else:
            self._anim.stop()
            self._highlight = 0.0

    def _apply_style(self) -> None:
        tokens = WorkbenchTokens.get()
        border_hex = tokens.accent_hex if (self.node.is_attentive or self._highlight > 0.2) else tokens.line_hex
        bg_hex = tokens.soft_hex if self.node.is_compact_ref else tokens.paper_hex
        scope_color = tokens.error_hex if not self.node.available else tokens.muted_hex
        self.setStyleSheet(
            f"""
            QFrame#{self.objectName()} {{
                background-color: {bg_hex};
                border: 1px solid {border_hex};
                border-radius: 10px;
            }}
            QLabel#SceneSourceBadge {{
                background-color: {tokens.user_hex};
                color: {tokens.accent_hex};
                border-radius: 5px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
                font-family: {FONT_FAMILY};
                border: none;
            }}
            QLabel#SceneSourceTitle {{
                color: {tokens.ink_hex};
                font-size: 13px;
                font-weight: 500;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            QLabel#SceneSourceScope {{
                color: {scope_color};
                font-size: 11px;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            QPushButton#SceneSourceOpenBtn {{
                background-color: {tokens.soft_hex};
                color: {tokens.ink_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton#SceneSourceOpenBtn:disabled {{
                color: {tokens.error_hex};
            }}
            """
        )

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.selected.emit(self.node.node_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.selected.emit(self.node.node_id)
            event.accept()
            return
        super().keyPressEvent(event)


class ExcerptCardWidget(QFrame):
    """
    Displays an observed passage/page excerpt tethered to its parent source.
    """

    inspect_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SceneExcerptCard")
        self.parent_source_id: str = ""
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 7, 11, 7)
        layout.setSpacing(3)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.title_lbl = QLabel(self)
        self.title_lbl.setObjectName("SceneExcerptTitle")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self.title_lbl, 1)

        self.badge_lbl = QLabel(self)
        self.badge_lbl.setObjectName("SceneExcerptBadge")
        header.addWidget(self.badge_lbl)
        layout.addLayout(header)

        self.snippet_lbl = QLabel(self)
        self.snippet_lbl.setObjectName("SceneExcerptSnippet")
        self.snippet_lbl.setWordWrap(True)
        self.snippet_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.snippet_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.snippet_lbl)

    def set_excerpt(self, excerpt: Optional[SceneExcerptNode]) -> None:
        if excerpt is None:
            self.parent_source_id = ""
            self.hide()
            return
        self.parent_source_id = excerpt.parent_source_id
        self.title_lbl.setText(excerpt.title)
        self.badge_lbl.setText(excerpt.scope_badge)
        self.badge_lbl.setVisible(bool(excerpt.scope_badge))
        self.snippet_lbl.setText(excerpt.snippet)
        self._apply_style()
        self.show()

    def _apply_style(self) -> None:
        tokens = WorkbenchTokens.get()
        self.setStyleSheet(
            f"""
            QFrame#SceneExcerptCard {{
                background-color: {tokens.soft_hex};
                border-left: 3px solid {tokens.accent_hex};
                border-top: 1px solid {tokens.line_hex};
                border-right: 1px solid {tokens.line_hex};
                border-bottom: 1px solid {tokens.line_hex};
                border-radius: 8px;
            }}
            QLabel#SceneExcerptTitle {{
                color: {tokens.ink_hex};
                font-size: 12px;
                font-weight: 600;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            QLabel#SceneExcerptBadge {{
                color: {tokens.accent_hex};
                font-size: 11px;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            QLabel#SceneExcerptSnippet {{
                color: {tokens.muted_hex};
                font-size: 12px;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            """
        )

    def mouseReleaseEvent(self, event: Any) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.parent_source_id
            and self.rect().contains(event.position().toPoint())
        ):
            self.inspect_requested.emit(self.parent_source_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.parent_source_id:
            self.inspect_requested.emit(self.parent_source_id)
            event.accept()
            return
        super().keyPressEvent(event)


class GroundedRelationsWidget(QWidget):
    """
    Renders grounded relationship connectors and labels between scene objects.
    Hidden completely when no verified edge exists (never draws fake causal links).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SceneGroundedRelations")
        self.edges: List[SceneEdge] = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 2, 8, 2)
        self.layout.setSpacing(3)
        self.labels: List[QLabel] = []
        self.hide()

    def set_edges(self, edges: Sequence[SceneEdge]) -> None:
        self.edges = list(edges)
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.labels.clear()

        if not self.edges:
            self.hide()
            return

        tokens = WorkbenchTokens.get()
        kind_prefix = {
            "file_contains_excerpt": "↳ Nguồn → Đoạn đã đọc",
            "artifact_derived_from_ref": "↳ Dẫn xuất có tham chiếu",
            "revision_supersedes": "↻ Cập nhật phiên bản",
        }
        for edge in self.edges:
            lbl = QLabel(self)
            lbl.setObjectName(f"SceneEdge_{edge.kind}")
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            prefix = kind_prefix.get(edge.kind, "↳ Liên kết")
            lbl.setText(f"{prefix}: {edge.label}")
            lbl.setStyleSheet(
                f"""
                QLabel {{
                    color: {tokens.accent_hex};
                    font-size: 11px;
                    font-weight: 500;
                    font-family: {FONT_FAMILY};
                    background: transparent;
                    border: none;
                    padding-left: 6px;
                }}
                """
            )
            self.layout.addWidget(lbl)
            self.labels.append(lbl)
        self.show()
        self.update()

    def paintEvent(self, event: Any) -> None:
        if not self.edges:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = WorkbenchTokens.get()
        pen = QPen(tokens.accent, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        h = self.height()
        p.drawLine(QPointF(6.0, 2.0), QPointF(6.0, max(4.0, h - 2.0)))
        p.end()


class ResultDeskCard(QFrame):
    """
    Forming or committed result card on the Workbench desk.
    Hosts the single shared ArtifactPanel so interactive controls and revisions
    update in-place without duplicating renderers.
    """

    def __init__(self, artifact_panel: ArtifactPanel, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SceneResultCard")
        self.artifact_panel = artifact_panel
        self.result_node: Optional[SceneResultNode] = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 6, 10, 6)
        self.layout.setSpacing(4)

        self.header_row = QWidget(self)
        header = QHBoxLayout(self.header_row)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.title_lbl = QLabel(self.header_row)
        self.title_lbl.setObjectName("SceneResultTitle")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self.title_lbl, 1)

        self.rev_badge = QLabel(self.header_row)
        self.rev_badge.setObjectName("SceneResultRevisionBadge")
        header.addWidget(self.rev_badge)
        self.layout.addWidget(self.header_row)

        self.ref_notice_lbl = QLabel(self)
        self.ref_notice_lbl.setObjectName("SceneResultRefNotice")
        self.ref_notice_lbl.setWordWrap(True)
        self.ref_notice_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.ref_notice_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.ref_notice_lbl.hide()
        self.layout.addWidget(self.ref_notice_lbl)

        self.artifact_host = QWidget(self)
        self.artifact_host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.artifact_host_layout = QVBoxLayout(self.artifact_host)
        self.artifact_host_layout.setContentsMargins(0, 0, 0, 0)
        self.artifact_host_layout.setSpacing(4)
        self.artifact_host_layout.addWidget(self.artifact_panel)
        self.layout.addWidget(self.artifact_host)

        self.answer_lbl = QLabel(self)
        self.answer_lbl.setObjectName("SceneResultAnswer")
        self.answer_lbl.setWordWrap(True)
        self.answer_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.answer_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.answer_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.answer_lbl.hide()
        self.layout.addWidget(self.answer_lbl)

        self.hide()

    def ensure_artifact_panel_attached(self) -> None:
        if self.artifact_host_layout.indexOf(self.artifact_panel) < 0:
            self.artifact_host_layout.addWidget(self.artifact_panel)
            self.artifact_panel.show()

    def update_result(
        self,
        node: Optional[SceneResultNode],
        *,
        has_rendered_artifacts: bool = False,
    ) -> None:
        self.result_node = node
        if node is None and not has_rendered_artifacts:
            self.hide()
            return

        tokens = WorkbenchTokens.get()
        if node is not None:
            self.title_lbl.setText(node.title or "Kết quả")
            if node.revision is not None:
                if node.previous_revision is not None:
                    self.rev_badge.setText(f"Phiên bản {node.previous_revision} → {node.revision}")
                else:
                    self.rev_badge.setText(f"Phiên bản {node.revision}")
                self.rev_badge.show()
            elif node.status_label:
                self.rev_badge.setText(node.status_label)
                self.rev_badge.show()
            else:
                self.rev_badge.hide()

            # Avoid duplicating the task/artifact title when WorkbenchCanvas or QtViewRenderer
            # already displays the exact same title and no revision transition badge is active.
            show_header = bool(
                node.previous_revision is not None
                or (node.revision is not None and not has_rendered_artifacts)
            )
            self.header_row.setVisible(show_header)

            # Check for missing or stale references
            notices = []
            for ref in node.source_refs:
                if ref.get("missing"):
                    notices.append(f"Tham chiếu nguồn ({ref.get('artifact_id')}) không còn trong phiên.")
                elif ref.get("stale"):
                    notices.append(
                        f"Đang dùng dữ liệu từ phiên bản cũ (bản {ref.get('revision')}) của {ref.get('title') or ref.get('artifact_id')}."
                    )
            if notices:
                self.ref_notice_lbl.setText(" ".join(notices))
                self.ref_notice_lbl.show()
            else:
                self.ref_notice_lbl.hide()

            ans = (node.answer_text or node.summary or "").strip()
            if ans and (not has_rendered_artifacts or bool(node.answer_text.strip())):
                self.answer_lbl.setText(ans)
                self.answer_lbl.show()
            else:
                self.answer_lbl.hide()
        else:
            self.title_lbl.setText("Kết quả trên bàn")
            self.rev_badge.hide()
            self.header_row.hide()
            self.ref_notice_lbl.hide()
            self.answer_lbl.hide()

        self.artifact_host.setVisible(has_rendered_artifacts)
        self.setStyleSheet(
            f"""
            QFrame#SceneResultCard {{
                background-color: {tokens.paper_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 12px;
            }}
            QLabel#SceneResultTitle {{
                color: {tokens.ink_hex};
                font-size: 13px;
                font-weight: 600;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            QLabel#SceneResultRevisionBadge {{
                background-color: {tokens.user_hex};
                color: {tokens.accent_hex};
                border-radius: 6px;
                padding: 2px 7px;
                font-size: 11px;
                font-weight: 600;
                font-family: {FONT_FAMILY};
                border: none;
            }}
            QLabel#SceneResultRefNotice {{
                color: {tokens.error_hex};
                font-size: 11px;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            QLabel#SceneResultAnswer {{
                color: {tokens.ink_hex};
                font-size: 13px;
                line-height: 1.5;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            """
        )
        self.show()


class ElidedLabel(QLabel):
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        elide_mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
    ) -> None:
        super().__init__(parent)
        self.full_text = str(text or "")
        self.elide_mode = elide_mode
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setToolTip(self.full_text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(self.full_text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided()

    def set_full_text(self, text: str) -> None:
        self.full_text = str(text or "")
        self.setToolTip(self.full_text)
        self._update_elided()

    def _update_elided(self) -> None:
        w = max(0, self.width())
        if w > 0 and self.full_text:
            super().setText(self.fontMetrics().elidedText(self.full_text, self.elide_mode, w))
        else:
            super().setText(self.full_text)


class FinderHitRow(QFrame):
    """A compact, keyboard-navigable hit row in the Workbench Scene representing an app or file."""
    selected = pyqtSignal(str)  # resource_id
    question_requested = pyqtSignal(object)  # hit
    open_requested = pyqtSignal(str)  # file_path
    app_open_requested = pyqtSignal(object)  # SearchHit (application)
    preview_requested = pyqtSignal(str)  # file_path
    reveal_requested = pyqtSignal(str)  # file_path

    def __init__(self, hit: SearchHit, *, is_selected: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.hit = hit
        self.is_selected = is_selected
        self.setObjectName("FinderHitRow")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._init_ui()
        self._apply_style()

    @staticmethod
    def _format_subtitle(hit: SearchHit) -> str:
        if hit.kind == "application":
            parts: List[str] = []
            if getattr(hit, "version", ""):
                parts.append(f"v{hit.version}")
            if hit.bundle_id:
                parts.append(hit.bundle_id)
            if hit.path:
                parts.append(hit.path)
            return " · ".join(parts) if parts else "Ứng dụng macOS"
        folder = Path(hit.path).parent.name
        snip = f" · {hit.snippet[:80]}" if hit.snippet else ""
        return f"{folder}{snip}"

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        tokens = WorkbenchTokens.get()
        self.badge = QLabel(self)
        self.badge.setFixedSize(34, 22)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.hit.kind == "application":
            self.badge.setText("APP")
            self.badge.setStyleSheet(
                "background: #4F46E5; color: #FFFFFF; border-radius: 4px; font-size: 9px; font-weight: 700;"
            )
        else:
            ext = Path(self.hit.path).suffix.lower()
            info = get_ext_badge_info(ext)
            bg = info.get("bg", "#6B7280")
            lbl = info.get("label", ext.lstrip(".").upper() or "FILE")
            self.badge.setText(lbl[:5])
            self.badge.setStyleSheet(
                f"background: {bg}; color: #FFFFFF; border-radius: 4px; font-size: 9px; font-weight: 700;"
            )
        layout.addWidget(self.badge)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)

        self.title_lbl = ElidedLabel(self.hit.title, self, elide_mode=Qt.TextElideMode.ElideRight)
        self.title_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens.ink_hex};")
        col.addWidget(self.title_lbl)

        sub_text = self._format_subtitle(self.hit)
        self.sub_lbl = ElidedLabel(sub_text, self, elide_mode=Qt.TextElideMode.ElideRight)
        self.sub_lbl.setStyleSheet(f"font-size: 10px; color: {tokens.muted_hex};")
        col.addWidget(self.sub_lbl)
        layout.addLayout(col, 1)

        btn_style = f"""
            QPushButton {{
                background: {tokens.soft_hex};
                color: {tokens.ink_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {tokens.paper_hex};
                border-color: {tokens.accent_hex};
            }}
        """

        if self.hit.kind == "file":
            self.btn_ask = QPushButton("Hỏi", self)
            self.btn_ask.setToolTip("Hỏi về tệp này trong ô chat")
            self.btn_ask.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_ask.clicked.connect(lambda: self.question_requested.emit(self.hit))

            self.btn_open = QPushButton("Mở", self)
            self.btn_open.setToolTip("Mở tệp")
            self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_open.clicked.connect(lambda: self.open_requested.emit(self.hit.path))

            self.btn_preview = QPushButton("Xem", self)
            self.btn_preview.setToolTip("Xem nhanh (Space)")
            self.btn_preview.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_preview.clicked.connect(lambda: self.preview_requested.emit(self.hit.path))

            self.btn_reveal = QPushButton("↗", self)
            self.btn_reveal.setToolTip("Hiện trong Finder (⌘Enter)")
            self.btn_reveal.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_reveal.clicked.connect(lambda: self.reveal_requested.emit(self.hit.path))

            for btn in (self.btn_ask, self.btn_open, self.btn_preview, self.btn_reveal):
                btn.installEventFilter(self)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.setStyleSheet(btn_style)
                layout.addWidget(btn)
        else:
            self.btn_open = QPushButton("Mở", self)
            self.btn_open.setToolTip("Mở ứng dụng macOS (Enter)")
            self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_open.clicked.connect(lambda: self.app_open_requested.emit(self.hit))

            self.btn_reveal = QPushButton("↗", self)
            self.btn_reveal.setToolTip("Hiện trong Finder (⌘Enter)")
            self.btn_reveal.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_reveal.clicked.connect(lambda: self.reveal_requested.emit(self.hit.path))

            for btn in (self.btn_open, self.btn_reveal):
                btn.installEventFilter(self)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.setStyleSheet(btn_style)
                layout.addWidget(btn)

    def set_selected(self, selected: bool) -> None:
        if self.is_selected != selected:
            self.is_selected = selected
            self._apply_style()

    def _apply_style(self) -> None:
        tokens = WorkbenchTokens.get()
        if self.is_selected:
            self.setStyleSheet(f"""
                QFrame#FinderHitRow {{
                    background: {tokens.soft_hex};
                    border: 1px solid {tokens.accent_hex};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#FinderHitRow {{
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                }}
                QFrame#FinderHitRow:hover {{
                    background: {tokens.soft_hex};
                    border: 1px solid {tokens.line_hex};
                }}
            """)

    def _apply_theme(self) -> None:
        tokens = WorkbenchTokens.get()
        self.title_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {tokens.ink_hex};")
        self.sub_lbl.setStyleSheet(f"font-size: 10px; color: {tokens.muted_hex};")
        self._apply_style()
        btn_style = f"""
            QPushButton {{
                background: {tokens.soft_hex};
                color: {tokens.ink_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {tokens.paper_hex};
                border-color: {tokens.accent_hex};
            }}
        """
        for attr in ("btn_ask", "btn_open", "btn_preview", "btn_reveal"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setStyleSheet(btn_style)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.hit.resource_id)
        super().mousePressEvent(event)

    def focusInEvent(self, event) -> None:
        self.selected.emit(self.hit.resource_id)
        super().focusInEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn:
            self.selected.emit(self.hit.resource_id)
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Down:
            parent = self.parentWidget()
            while parent is not None and not isinstance(parent, FinderSuggestionsWidget):
                parent = parent.parentWidget()
            if parent is not None:
                parent.navigate(1)
                event.accept()
                return
        elif key == Qt.Key.Key_Up:
            parent = self.parentWidget()
            while parent is not None and not isinstance(parent, FinderSuggestionsWidget):
                parent = parent.parentWidget()
            if parent is not None:
                parent.navigate(-1)
                event.accept()
                return
        super().keyPressEvent(event)


class FinderSuggestionsWidget(QWidget):
    """Suggestions panel presenting progressive finder hits on the Workbench desk."""
    hit_selected = pyqtSignal(str)  # resource_id
    question_requested = pyqtSignal(object)  # hit
    open_requested = pyqtSignal(str)
    app_open_requested = pyqtSignal(object)  # SearchHit
    preview_requested = pyqtSignal(str)
    reveal_requested = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("FinderSuggestionsWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(0)
        self.snapshot: Optional[SearchSnapshot] = None
        self.selected_resource_id: Optional[str] = None
        self._rows: Dict[str, FinderHitRow] = {}
        self._row_order: List[str] = []
        self._event_filter: Optional[QObject] = None

        self._init_ui()
        self._apply_theme()

    def set_event_filter(self, filter_obj: QObject) -> None:
        self._event_filter = filter_obj
        self.installEventFilter(filter_obj)
        if hasattr(self, "scroll") and self.scroll is not None:
            self.scroll.installEventFilter(filter_obj)
        if hasattr(self, "container") and self.container is not None:
            self.container.installEventFilter(filter_obj)
        for row in self._rows.values():
            self._install_filter_on_row(row)

    def _install_filter_on_row(self, row: FinderHitRow) -> None:
        if self._event_filter is None:
            return
        row.installEventFilter(self._event_filter)
        for attr in ("btn_ask", "btn_open", "btn_preview", "btn_reveal", "badge", "title_lbl", "sub_lbl"):
            w = getattr(row, attr, None)
            if w is not None:
                w.installEventFilter(self._event_filter)

    def _init_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 1, 0, 2)
        self.layout.setSpacing(3)

        tokens = WorkbenchTokens.get()
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.caption = QLabel("Gợi ý tìm kiếm", self)
        self.caption.setObjectName("FinderCaption")
        self.caption.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {tokens.muted_hex};")
        header_row.addWidget(self.caption)

        self.intent_lbl = QLabel("", self)
        self.intent_lbl.setObjectName("FinderIntentChips")
        self.intent_lbl.setWordWrap(True)
        self.intent_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.intent_lbl.hide()
        header_row.addWidget(self.intent_lbl, 1)

        self.layout.addLayout(header_row)

        self.notice_lbl = QLabel("", self)
        self.notice_lbl.setObjectName("FinderNoticeLabel")
        self.notice_lbl.setWordWrap(True)
        self.notice_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.notice_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.notice_lbl.hide()
        self.layout.addWidget(self.notice_lbl)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll.setMaximumHeight(280)
        self.scroll.setMinimumWidth(0)

        self.container = QWidget(self.scroll)
        self.container.setStyleSheet("background: transparent;")
        self.container.setMinimumWidth(0)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(2)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)

    def has_visible_content(self) -> bool:
        if self.snapshot is None:
            return False
        if self.snapshot.hits:
            return True
        intent = getattr(self.snapshot, "intent", None)
        if intent is not None and (
            intent.needs_clarification
            or intent.action == "negated_open"
            or intent.slide_rule
            or intent.report_rule
            or intent.date_min is not None
            or intent.file_exts
            or intent.action == "open_app"
        ):
            return True
        return False

    def sizeHint(self) -> QSize:
        h = 22
        if self.notice_lbl.isVisible():
            h += max(22, self.notice_lbl.sizeHint().height()) + 4
        if self.scroll.isVisible():
            scroll_h = self.scroll.height() if self.scroll.height() > 0 else 56
            h += scroll_h + 4
        return QSize(200, h)

    def set_snapshot(self, snapshot: SearchSnapshot, selected_id: Optional[str] = None) -> None:
        self.snapshot = snapshot
        intent = getattr(snapshot, "intent", None)

        # Update caption & intent filter chips
        total = len(snapshot.hits)
        caption_text = f"Gợi ý ({total})"
        if snapshot.phase == "lexical" and not snapshot.complete:
            caption_text += " · đang tìm…"
        if "file_index_unavailable" in snapshot.errors:
            caption_text += " · (chỉ mục tệp tạm thời không khả dụng)"
        self.caption.setText(caption_text)

        if intent is not None and intent.interpretation_chips:
            self.intent_lbl.setText(" · ".join(intent.interpretation_chips))
            self.intent_lbl.show()
        else:
            self.intent_lbl.setText("")
            self.intent_lbl.hide()

        notice_text = ""
        if intent is not None and intent.clarification_reason:
            notice_text = intent.clarification_reason
        elif not snapshot.hits and intent is not None and (
            intent.slide_rule
            or intent.report_rule
            or intent.date_min is not None
            or intent.file_exts
            or intent.action == "open_app"
        ):
            if intent.action == "open_app":
                notice_text = f"Không tìm thấy ứng dụng khớp ‘{intent.app_query or snapshot.query}’ trên máy."
            else:
                notice_text = intent.scope_note or "Chưa tìm thấy tệp khớp với bộ lọc trong chỉ mục."
        elif intent is not None and intent.scope_note:
            notice_text = intent.scope_note

        if notice_text:
            self.notice_lbl.setText(notice_text)
            self.notice_lbl.show()
        else:
            self.notice_lbl.setText("")
            self.notice_lbl.hide()

        # Capture focused action role, resource_id, and scroll position
        focused_widget = QApplication.focusWidget()
        focused_rid = None
        focused_role = None
        for rid, row in self._rows.items():
            if focused_widget is row:
                focused_rid = rid
                focused_role = "row"
                break
            for role in ("btn_ask", "btn_open", "btn_preview", "btn_reveal"):
                btn = getattr(row, role, None)
                if btn is not None and focused_widget is btn:
                    focused_rid = rid
                    focused_role = role
                    break
            if focused_rid is not None:
                break

        scroll_val = self.scroll.verticalScrollBar().value()

        # Determine selection by resource_id
        target_id = selected_id or focused_rid or self.selected_resource_id
        if not any(h.resource_id == target_id for h in snapshot.hits):
            target_id = snapshot.hits[0].resource_id if snapshot.hits else None
        self.selected_resource_id = target_id

        # Reconcile rows
        old_rows = self._rows
        new_rows = {}
        new_order = []

        new_ids = {h.resource_id for h in snapshot.hits}
        for rid, row in old_rows.items():
            if rid not in new_ids:
                self.container_layout.removeWidget(row)
                row.deleteLater()

        for idx, hit in enumerate(snapshot.hits):
            is_sel = (hit.resource_id == self.selected_resource_id)
            if hit.resource_id in old_rows:
                row = old_rows[hit.resource_id]
                row.hit = hit
                row.title_lbl.set_full_text(hit.title)
                row.sub_lbl.set_full_text(FinderHitRow._format_subtitle(hit))
                row.set_selected(is_sel)
                self.container_layout.insertWidget(idx, row)
            else:
                row = FinderHitRow(hit, is_selected=is_sel, parent=self.container)
                self._install_filter_on_row(row)
                row.selected.connect(self._on_row_selected)
                row.question_requested.connect(self.question_requested.emit)
                row.open_requested.connect(self.open_requested.emit)
                row.app_open_requested.connect(self.app_open_requested.emit)
                row.preview_requested.connect(self.preview_requested.emit)
                row.reveal_requested.connect(self.reveal_requested.emit)
                self.container_layout.insertWidget(idx, row)
            new_rows[hit.resource_id] = row
            new_order.append(hit.resource_id)

        self._rows = new_rows
        self._row_order = new_order

        # Height bounding
        if snapshot.hits:
            row_h = 40
            content_h = min(280, max(48, len(snapshot.hits) * row_h + 6))
            self.scroll.setFixedHeight(content_h)
            self.scroll.show()
        else:
            self.scroll.setFixedHeight(0)
            self.scroll.hide()

        # Restore focus if a row or action button had focus
        if focused_rid is not None and focused_rid in self._rows:
            target_row = self._rows[focused_rid]
            if focused_role == "row":
                target_row.setFocus()
            else:
                target_btn = getattr(target_row, focused_role, None)
                if target_btn is not None:
                    target_btn.setFocus()

        # Restore scroll position
        if self.scroll.verticalScrollBar().maximum() >= scroll_val:
            self.scroll.verticalScrollBar().setValue(scroll_val)

    def _on_row_selected(self, resource_id: str) -> None:
        self.set_selected_id(resource_id)
        self.hit_selected.emit(resource_id)

    def set_selected_id(self, resource_id: Optional[str]) -> None:
        self.selected_resource_id = resource_id
        for rid, row in self._rows.items():
            row.set_selected(rid == resource_id)

    def navigate(self, delta: int) -> bool:
        """Move selection up or down. Returns False if moving above the first item."""
        if not self._row_order:
            return False
        curr_idx = -1
        if self.selected_resource_id in self._row_order:
            curr_idx = self._row_order.index(self.selected_resource_id)

        new_idx = curr_idx + delta
        if new_idx < 0:
            return False  # Return focus to composer
        new_idx = min(len(self._row_order) - 1, new_idx)
        new_id = self._row_order[new_idx]
        self.set_selected_id(new_id)
        if new_id in self._rows:
            self.scroll.ensureWidgetVisible(self._rows[new_id])
        self.hit_selected.emit(new_id)
        return True

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Down:
            self.navigate(1)
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            self.navigate(-1)
            event.accept()
            return
        super().keyPressEvent(event)

    def current_hit(self) -> Optional[SearchHit]:
        if not self.snapshot or not self.selected_resource_id:
            return None
        for h in self.snapshot.hits:
            if h.resource_id == self.selected_resource_id:
                return h
        return None

    def clear(self) -> None:
        self.snapshot = None
        self.selected_resource_id = None
        self.intent_lbl.setText("")
        self.intent_lbl.hide()
        self.notice_lbl.setText("")
        self.notice_lbl.hide()
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows.clear()
        self._row_order.clear()

    def _apply_theme(self) -> None:
        tokens = WorkbenchTokens.get()
        self.caption.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {tokens.muted_hex};")
        self.intent_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 500; color: {tokens.accent_hex}; background: transparent;"
        )
        self.notice_lbl.setStyleSheet(
            f"font-size: 11px; color: {tokens.ink_hex}; background: {tokens.soft_hex}; "
            f"border: 1px solid {tokens.line_hex}; border-radius: 6px; padding: 4px 8px;"
        )
        for row in self._rows.values():
            row._apply_theme()


# =========================================================================
# 4. WORKBENCH SCENE CONTAINER (Overview ↔ Source Detail)
# =========================================================================
class WorkbenchScene(QWidget):
    """
    Two-level Workbench scene mounted inside `WorkbenchCanvas` when
    `RAT_WORKBENCH_SCENE=1`.

    Levels:
    - `overview`: Desk overview with up to 5 primary objects (observed sources,
      attentive excerpt, grounded relations, forming/committed result) + overflow
      sources disclosure + optional secondary work trace.
    - `source_detail`: Deep inspection of a single selected source using existing
      `QtViewRenderer` / `StandardViewProvider` without invoking the model or
      reading extra files.
    """

    mode_changed = pyqtSignal(str)
    content_changed = pyqtSignal()

    def __init__(
        self,
        *,
        registry: Optional[Any] = None,
        store: Optional[ArtifactStore] = None,
        on_open_file: Optional[Callable[[str], None]] = None,
        on_open_app: Optional[Callable[[Any], None]] = None,
        on_action: Optional[Callable[[Any, dict], None]] = None,
        on_input: Optional[Callable[[str, dict], None]] = None,
        on_question: Optional[Callable[[Any], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WorkbenchScene")
        self.registry = registry
        self.store = store
        self.on_open_file = on_open_file
        self.on_open_app = on_open_app
        self.on_action = on_action
        self.on_input = on_input
        self.on_question = on_question

        self.provider = StandardViewProvider(registry)
        self.projector = WorkSceneProjector()
        self.current_snapshot: WorkSceneSnapshot = self.projector.snapshot(store=store)

        self.mode: str = "overview"  # "overview" | "source_detail"
        self.selected_source_id: Optional[str] = None
        self.is_expanded: bool = False
        self.is_narrow: bool = False
        self.overflow_expanded: bool = False
        self.trace_expanded: bool = False
        self._overview_scroll_value: int = 0
        self._transition_val: float = 1.0
        self.last_update_ms: float = 0.0

        # Single shared ArtifactPanel so renderers are never duplicated
        self.artifact_panel = ArtifactPanel(
            [],
            self.provider,
            self.registry,
            on_action=self.on_action,
            on_input=self.on_input,
            on_question=self.on_question,
        )
        # Detail renderer for sources not already inside artifact_panel.renderers
        self._detail_renderer: Optional[QtViewRenderer] = None
        self._borrowed_renderer_id: Optional[str] = None
        self._rendered_detail_source_id: Optional[str] = None
        self._rendered_detail_revision: Optional[int] = None
        self._rendered_detail_available: Optional[bool] = None

        self._source_cards: Dict[str, SourceCardWidget] = {}
        self._overflow_cards: Dict[str, SourceCardWidget] = {}

        self._scene_anim = QPropertyAnimation(self, b"sceneTransition", self)
        self._scene_anim.setDuration(180)
        self._scene_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._init_ui()
        self._apply_theme()

    @pyqtProperty(float)
    def sceneTransition(self) -> float:
        return self._transition_val

    @sceneTransition.setter
    def sceneTransition(self, val: float) -> None:
        self._transition_val = float(val)
        self.update()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        self.stack.setObjectName("WorkbenchSceneStack")
        root_layout.addWidget(self.stack, 1)

        # -----------------------------------------------------------------
        # PAGE 0: OVERVIEW
        # -----------------------------------------------------------------
        self.overview_scroll = QScrollArea(self.stack)
        self.overview_scroll.setObjectName("SceneOverviewScroll")
        self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overview_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.overview_body = QWidget(self.overview_scroll)
        self.overview_body.setObjectName("SceneOverviewBody")
        self.overview_body.setStyleSheet("background: transparent;")
        self.overview_layout = QVBoxLayout(self.overview_body)
        self.overview_layout.setContentsMargins(0, 2, 0, 4)
        self.overview_layout.setSpacing(5)

        # Progressive finder suggestions panel
        self.finder_box = FinderSuggestionsWidget(self.overview_body)
        self.finder_box.question_requested.connect(self._on_finder_question)
        self.finder_box.open_requested.connect(self._on_finder_open)
        self.finder_box.app_open_requested.connect(self._on_finder_open_app)
        self.finder_box.preview_requested.connect(lambda p: trigger_quicklook(p))
        self.finder_box.reveal_requested.connect(lambda p: reveal_in_finder(p))
        self.finder_box.hide()
        self.overview_layout.addWidget(self.finder_box)

        # Neutral grouping header when multiple unlinked sources exist
        self.group_caption = QLabel("Nguồn & dữ kiện đã quan sát", self.overview_body)
        self.group_caption.setObjectName("SceneGroupCaption")
        self.group_caption.setWordWrap(True)
        self.group_caption.hide()
        self.overview_layout.addWidget(self.group_caption)

        # Primary source cards container
        self.sources_container = QWidget(self.overview_body)
        self.sources_container.setObjectName("ScenePrimarySources")
        self.sources_layout = QVBoxLayout(self.sources_container)
        self.sources_layout.setContentsMargins(0, 0, 0, 0)
        self.sources_layout.setSpacing(5)
        self.sources_container.hide()
        self.overview_layout.addWidget(self.sources_container)

        # Overflow sources group ("+N nguồn khác")
        self.overflow_box = QWidget(self.overview_body)
        self.overflow_box.setObjectName("SceneOverflowBox")
        ov_layout = QVBoxLayout(self.overflow_box)
        ov_layout.setContentsMargins(0, 0, 0, 0)
        ov_layout.setSpacing(4)

        self.btn_overflow_toggle = QPushButton(self.overflow_box)
        self.btn_overflow_toggle.setObjectName("SceneOverflowToggle")
        self.btn_overflow_toggle.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_overflow_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_overflow_toggle.clicked.connect(self.toggle_overflow_sources)
        ov_layout.addWidget(self.btn_overflow_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.overflow_list_container = QWidget(self.overflow_box)
        self.overflow_list_layout = QVBoxLayout(self.overflow_list_container)
        self.overflow_list_layout.setContentsMargins(0, 0, 0, 0)
        self.overflow_list_layout.setSpacing(4)
        self.overflow_list_container.hide()
        ov_layout.addWidget(self.overflow_list_container)
        self.overflow_box.hide()
        self.overview_layout.addWidget(self.overflow_box)

        # Attentive excerpt card
        self.excerpt_card = ExcerptCardWidget(self.overview_body)
        self.excerpt_card.inspect_requested.connect(self.select_source)
        self.excerpt_card.hide()
        self.overview_layout.addWidget(self.excerpt_card)

        # Grounded relationship connector strip
        self.relations_widget = GroundedRelationsWidget(self.overview_body)
        self.overview_layout.addWidget(self.relations_widget)

        # Forming / committed result card
        self.result_card = ResultDeskCard(self.artifact_panel, self.overview_body)
        self.overview_layout.addWidget(self.result_card)

        # Secondary quiet trace disclosure (never primary)
        self.trace_box = QWidget(self.overview_body)
        self.trace_box.setObjectName("SceneTraceBox")
        tb_layout = QVBoxLayout(self.trace_box)
        tb_layout.setContentsMargins(0, 2, 0, 0)
        tb_layout.setSpacing(3)

        self.btn_trace_toggle = QPushButton(self.trace_box)
        self.btn_trace_toggle.setObjectName("SceneTraceToggle")
        self.btn_trace_toggle.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_trace_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trace_toggle.clicked.connect(self.toggle_trace_details)
        tb_layout.addWidget(self.btn_trace_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.trace_detail_lbl = QLabel(self.trace_box)
        self.trace_detail_lbl.setObjectName("SceneTraceDetail")
        self.trace_detail_lbl.setWordWrap(True)
        self.trace_detail_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.trace_detail_lbl.hide()
        tb_layout.addWidget(self.trace_detail_lbl)
        self.trace_box.hide()
        self.overview_layout.addWidget(self.trace_box)

        self.overview_layout.addStretch(1)
        self.overview_scroll.setWidget(self.overview_body)
        self.stack.addWidget(self.overview_scroll)

        # -----------------------------------------------------------------
        # PAGE 1: SOURCE DETAIL (Đi sâu vào một nguồn)
        # -----------------------------------------------------------------
        self.detail_page = QWidget(self.stack)
        self.detail_page.setObjectName("SceneDetailPage")
        self.detail_page_layout = QVBoxLayout(self.detail_page)
        self.detail_page_layout.setContentsMargins(0, 2, 0, 4)
        self.detail_page_layout.setSpacing(6)

        self.detail_header = QFrame(self.detail_page)
        self.detail_header.setObjectName("SceneDetailHeader")
        dh_layout = QHBoxLayout(self.detail_header)
        dh_layout.setContentsMargins(8, 6, 8, 6)
        dh_layout.setSpacing(8)

        self.btn_back_overview = QPushButton("← Tổng quan công việc", self.detail_header)
        self.btn_back_overview.setObjectName("SceneBackButton")
        self.btn_back_overview.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_back_overview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back_overview.clicked.connect(self.show_overview)
        dh_layout.addWidget(self.btn_back_overview)

        self.detail_scope_lbl = QLabel(self.detail_header)
        self.detail_scope_lbl.setObjectName("SceneDetailScope")
        self.detail_scope_lbl.setWordWrap(True)
        self.detail_scope_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_scope_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        dh_layout.addWidget(self.detail_scope_lbl, 1)

        self.btn_detail_open_file = QPushButton("Mở tệp", self.detail_header)
        self.btn_detail_open_file.setObjectName("SceneDetailOpenFileBtn")
        self.btn_detail_open_file.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_detail_open_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detail_open_file.clicked.connect(self._on_detail_open_file)
        dh_layout.addWidget(self.btn_detail_open_file)

        self.detail_page_layout.addWidget(self.detail_header)

        self.detail_scroll = QScrollArea(self.detail_page)
        self.detail_scroll.setObjectName("SceneDetailScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.detail_body = QWidget(self.detail_scroll)
        self.detail_body.setObjectName("SceneDetailBody")
        self.detail_body.setStyleSheet("background: transparent;")
        self.detail_body_layout = QVBoxLayout(self.detail_body)
        self.detail_body_layout.setContentsMargins(2, 2, 2, 4)
        self.detail_body_layout.setSpacing(6)

        self.detail_renderer_host = QWidget(self.detail_body)
        self.detail_renderer_layout = QVBoxLayout(self.detail_renderer_host)
        self.detail_renderer_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_renderer_layout.setSpacing(6)
        self.detail_body_layout.addWidget(self.detail_renderer_host)

        self.detail_fallback_lbl = QLabel(self.detail_body)
        self.detail_fallback_lbl.setObjectName("SceneDetailFallback")
        self.detail_fallback_lbl.setWordWrap(True)
        self.detail_fallback_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_fallback_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_fallback_lbl.hide()
        self.detail_body_layout.addWidget(self.detail_fallback_lbl)

        self.detail_body_layout.addStretch(1)
        self.detail_scroll.setWidget(self.detail_body)
        self.detail_page_layout.addWidget(self.detail_scroll, 1)

        self.stack.addWidget(self.detail_page)

    def is_empty(self) -> bool:
        snap = self.current_snapshot
        has_finder = bool(
            hasattr(self, "finder_box")
            and self.finder_box.isVisible()
            and self.finder_box.has_visible_content()
        )
        return (
            snap.phase == "empty"
            and not snap.primary_sources
            and not snap.overflow_sources
            and snap.active_excerpt is None
            and snap.result_node is None
            and not self.artifact_panel.renderers
            and not has_finder
        )

    def primary_object_count(self) -> int:
        snap = self.current_snapshot
        return (
            len(snap.primary_sources)
            + (1 if snap.active_excerpt is not None else 0)
            + (1 if snap.result_node is not None or self.artifact_panel.renderers else 0)
        )

    def all_sources(self) -> List[SceneSourceNode]:
        snap = self.current_snapshot
        return list(snap.primary_sources) + list(snap.overflow_sources)

    def find_source(self, node_id: str) -> Optional[SceneSourceNode]:
        for src in self.all_sources():
            if src.node_id == node_id:
                return src
        return None

    def set_presentation(self, expanded: bool, narrow: bool = False) -> None:
        self.is_expanded = bool(expanded)
        self.is_narrow = bool(narrow)
        self._apply_theme()
        for renderer in self.artifact_panel.renderers.values():
            renderer.set_compact(not self.is_expanded and self.mode == "overview")

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"QWidget {{ font-family: '{FONT_FAMILY}'; }}")
        tokens = WorkbenchTokens.get()
        self.group_caption.setStyleSheet(
            f"color: {tokens.muted_hex}; font-size: 11px; font-weight: 500; font-family: {FONT_FAMILY}; border: none;"
        )
        self.btn_overflow_toggle.setStyleSheet(
            f"""
            QPushButton#SceneOverflowToggle {{
                background-color: {tokens.soft_hex};
                color: {tokens.ink_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 7px;
                padding: 3px 9px;
                font-size: 11px;
                font-weight: 500;
                font-family: {FONT_FAMILY};
            }}
            """
        )
        self.btn_trace_toggle.setStyleSheet(
            f"""
            QPushButton#SceneTraceToggle {{
                background: transparent;
                color: {tokens.muted_hex};
                border: none;
                padding: 2px 4px;
                font-size: 11px;
                font-family: {FONT_FAMILY};
            }}
            """
        )
        self.trace_detail_lbl.setStyleSheet(
            f"color: {tokens.muted_hex}; font-size: 11px; font-family: {FONT_FAMILY}; padding-left: 8px; border: none;"
        )
        self.detail_header.setStyleSheet(
            f"""
            QFrame#SceneDetailHeader {{
                background-color: {tokens.soft_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 10px;
            }}
            QPushButton#SceneBackButton, QPushButton#SceneDetailOpenFileBtn {{
                background-color: {tokens.paper_hex};
                color: {tokens.ink_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 6px;
                padding: 3px 9px;
                font-size: 11px;
                font-weight: 500;
                font-family: {FONT_FAMILY};
            }}
            QPushButton#SceneDetailOpenFileBtn:disabled {{
                color: {tokens.error_hex};
            }}
            QLabel#SceneDetailScope {{
                color: {tokens.muted_hex};
                font-size: 11px;
                font-family: {FONT_FAMILY};
                background: transparent;
                border: none;
            }}
            """
        )
        self.detail_fallback_lbl.setStyleSheet(
            f"""
            QLabel#SceneDetailFallback {{
                background-color: {tokens.paper_hex};
                color: {tokens.ink_hex};
                border: 1px solid {tokens.line_hex};
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 13px;
                font-family: {FONT_FAMILY};
            }}
            """
        )
        for card in list(self._source_cards.values()) + list(self._overflow_cards.values()):
            card._apply_style()
        self.excerpt_card._apply_style()
        self.relations_widget.set_edges(self.current_snapshot.edges)
        self.result_card.update_result(
            self.current_snapshot.result_node,
            has_rendered_artifacts=bool(self.artifact_panel.renderers),
        )
        if hasattr(self, "artifact_panel") and hasattr(self.artifact_panel, "_apply_theme"):
            self.artifact_panel._apply_theme()
        if self._detail_renderer is not None and hasattr(self._detail_renderer, "_apply_theme"):
            self._detail_renderer._apply_theme()
        if hasattr(self, "finder_box") and hasattr(self.finder_box, "_apply_theme"):
            self.finder_box._apply_theme()

    def set_finder_snapshot(self, snapshot: SearchSnapshot, selected_id: Optional[str] = None) -> None:
        if snapshot is not None:
            self.projector.record_finder_intent(snapshot)
            self.finder_box.set_snapshot(snapshot, selected_id)
            if self.finder_box.has_visible_content():
                self.finder_box.show()
            else:
                self.finder_box.hide()
        else:
            self.projector.record_finder_intent(None)
            self.finder_box.clear()
            self.finder_box.hide()
        self.current_snapshot = self.projector.snapshot(store=self.store)
        self._sync_trace_ui(
            self.current_snapshot.trace_entries,
            reasoning_flow=self.current_snapshot.reasoning_flow,
            qa_telemetry=self.current_snapshot.qa_telemetry,
        )
        self.content_changed.emit()

    def clear_finder_snapshot(self) -> None:
        self.projector.record_finder_intent(None)
        self.finder_box.clear()
        self.finder_box.hide()
        self.current_snapshot = self.projector.snapshot(store=self.store)
        self._sync_trace_ui(
            self.current_snapshot.trace_entries,
            reasoning_flow=self.current_snapshot.reasoning_flow,
            qa_telemetry=self.current_snapshot.qa_telemetry,
        )
        self.content_changed.emit()

    def _on_finder_question(self, hit: SearchHit) -> None:
        if self.on_question:
            from rat.engine.reranker import SearchResultItem
            item = SearchResultItem(
                file_path=hit.path,
                file_name=hit.title,
                file_ext=Path(hit.path).suffix,
                file_size=0,
                modified_at=0.0,
                score=0.0,
                explanation="",
                snippet=hit.snippet,
            )
            self.on_question(item)

    def _on_finder_open(self, path: str) -> None:
        if self.on_open_file:
            self.on_open_file(path)
        else:
            open_file_default(path)

    def _on_finder_open_app(self, hit: SearchHit) -> None:
        if callable(self.on_open_app):
            self.on_open_app(hit)

    def _run_transition(self) -> None:
        if motion_enabled() and self.isVisible() and (self.window() is None or self.window().isVisible()):
            self._scene_anim.stop()
            self._scene_anim.setStartValue(0.0)
            self._scene_anim.setEndValue(1.0)
            self._scene_anim.start()
        else:
            self._scene_anim.stop()
            self._transition_val = 1.0

    def _stop_all_animations(self) -> None:
        if self._scene_anim.state() == QPropertyAnimation.State.Running:
            self._scene_anim.stop()
        self._transition_val = 1.0
        for card in list(self._source_cards.values()) + list(self._overflow_cards.values()):
            card.stop_animation()

    def hideEvent(self, event: Any) -> None:
        self._stop_all_animations()
        super().hideEvent(event)

    def toggle_overflow_sources(self) -> None:
        self.overflow_expanded = not self.overflow_expanded
        self._sync_overflow_ui(self.current_snapshot.overflow_sources)
        self.content_changed.emit()

    def toggle_trace_details(self) -> None:
        self.trace_expanded = not self.trace_expanded
        self._sync_trace_ui(
            self.current_snapshot.trace_entries,
            reasoning_flow=self.current_snapshot.reasoning_flow,
            qa_telemetry=self.current_snapshot.qa_telemetry,
        )
        self.content_changed.emit()

    def _sync_source_card_map(
        self,
        nodes: Sequence[SceneSourceNode],
        card_map: Dict[str, SourceCardWidget],
        target_layout: QVBoxLayout,
        *,
        animate: bool = True,
    ) -> None:
        wanted_ids = [n.node_id for n in nodes]
        wanted_set = set(wanted_ids)
        for old_id in list(card_map):
            if old_id not in wanted_set:
                card = card_map.pop(old_id)
                card.stop_animation()
                target_layout.removeWidget(card)
                card.hide()
                card.deleteLater()

        for idx, node in enumerate(nodes):
            card = card_map.get(node.node_id)
            if card is None:
                card = SourceCardWidget(node, self)
                card.selected.connect(self.select_source)
                card.open_file_requested.connect(self._handle_open_file)
                card_map[node.node_id] = card
                target_layout.insertWidget(idx, card)
            else:
                if target_layout.indexOf(card) != idx:
                    target_layout.removeWidget(card)
                    target_layout.insertWidget(idx, card)
                card.update_node(node, animate=animate)
            card.show()

    def _sync_overflow_ui(self, overflow_nodes: Sequence[SceneSourceNode]) -> None:
        if not overflow_nodes:
            self._sync_source_card_map([], self._overflow_cards, self.overflow_list_layout, animate=False)
            self.overflow_box.hide()
            return
        count = len(overflow_nodes)
        prefix = "▾ Ẩn bớt" if self.overflow_expanded else "▸ Mở xem"
        self.btn_overflow_toggle.setText(f"{prefix} +{count} nguồn khác")
        self._sync_source_card_map(
            overflow_nodes,
            self._overflow_cards,
            self.overflow_list_layout,
            animate=False,
        )
        self.overflow_list_container.setVisible(self.overflow_expanded)
        self.overflow_box.show()

    def _sync_trace_ui(
        self,
        entries: Sequence[TraceEntry],
        *,
        reasoning_flow: Optional[Sequence[TraceEntry]] = None,
        qa_telemetry: Optional[Dict[str, Any]] = None,
    ) -> None:
        display_entries = list(reasoning_flow) if reasoning_flow else list(entries)
        if not display_entries or (
            self.current_snapshot.phase == "empty"
            and hasattr(self, "finder_box")
            and self.finder_box.isVisible()
        ):
            self.trace_box.hide()
            return
        prefix = "▾" if self.trace_expanded else "▸"
        status_badges = {
            "proposed": "Dự định",
            "running": "Đang chạy",
            "found": "Đã tìm thấy",
            "read": "Đã đọc",
            "verified_pass": "Kiểm tra đạt",
            "verified_fail": "Chưa đạt",
            "unchecked": "Chưa kiểm tra",
            "waiting": "Chờ chọn",
            "error": "Lỗi",
            "cancelled": "Đã dừng",
            "done": "Đã xong",
        }
        flow_titles = " → ".join(e.title for e in display_entries[:4])
        if len(flow_titles) > 64:
            flow_titles = flow_titles[:61].rstrip() + "…"
        self.btn_trace_toggle.setText(
            f"{prefix} Nhật ký thao tác ({len(display_entries)} bước) · {flow_titles}"
        )
        lines = []
        for e in display_entries:
            badge = status_badges.get(e.status, e.status)
            line = f"{e.number}. [{badge}] {e.title}"
            if e.detail:
                line += f" — {e.detail}"
            lines.append(line)
        if isinstance(qa_telemetry, dict):
            ft = qa_telemetry.get("first_token_ms")
            tot = qa_telemetry.get("total_ms")
            pt = qa_telemetry.get("prompt_tokens", 0)
            ct = qa_telemetry.get("completion_tokens", 0)
            reused = qa_telemetry.get("reused_prefix_tokens", 0)
            parts = []
            if ft is not None:
                parts.append(f"token đầu {float(ft):.0f} ms")
            if tot is not None:
                parts.append(f"tổng {float(tot):.0f} ms")
            if pt or ct:
                tok_part = f"{pt}→{ct} token"
                if reused:
                    tok_part += f" (tái sử dụng {reused})"
                parts.append(tok_part)
            if parts:
                lines.append("Đo lường: " + " · ".join(parts))
        self.trace_detail_lbl.setText("\n".join(lines))
        self.trace_detail_lbl.setVisible(self.trace_expanded)
        self.trace_box.show()

    def _handle_open_file(self, file_path: str) -> None:
        if not file_path or not Path(file_path).is_file():
            self.apply_snapshot(self.projector.snapshot(store=self.store), animate=False)
            return
        if callable(self.on_open_file):
            self.on_open_file(file_path)

    def _on_detail_open_file(self) -> None:
        if not self.selected_source_id:
            return
        src = self.find_source(self.selected_source_id)
        if src is None:
            return
        src.refresh_availability()
        if src.file_path and src.available:
            self._handle_open_file(src.file_path)
        else:
            self._render_detail_for_source(src)

    def _return_borrowed_renderer(self) -> None:
        if self._borrowed_renderer_id is not None:
            renderer = self.artifact_panel.renderers.get(self._borrowed_renderer_id)
            if renderer is not None:
                self.detail_renderer_layout.removeWidget(renderer)
                renderer.set_compact(not self.is_expanded)
                if self.artifact_panel.layout.indexOf(renderer) < 0:
                    self.artifact_panel.layout.addWidget(renderer)
                renderer.show()
            self._borrowed_renderer_id = None
        if self._detail_renderer is not None:
            self.detail_renderer_layout.removeWidget(self._detail_renderer)
            self._detail_renderer.hide()
            self._detail_renderer.deleteLater()
            self._detail_renderer = None

    def _update_detail_header(self, src: SceneSourceNode) -> None:
        src.refresh_availability()
        scope_text = src.scope_label or "Đã quan sát"
        if not src.available and src.availability_note:
            scope_text = f"{scope_text} · {src.availability_note}"
        self.detail_scope_lbl.setText(scope_text)

        has_file = bool(src.file_path)
        self.btn_detail_open_file.setVisible(has_file)
        self.btn_detail_open_file.setEnabled(has_file and src.available)
        self.btn_detail_open_file.setText("Mở tệp" if src.available else "Tệp không còn trên máy")
        if src.file_path:
            self.btn_detail_open_file.setToolTip(
                src.file_path if src.available else "Tệp không còn tồn tại trên máy"
            )

    def _render_detail_for_source(
        self,
        src: SceneSourceNode,
        *,
        initial_state: Optional[Dict[str, Any]] = None,
        initial_scroll: Optional[int] = None,
    ) -> None:
        # Capture view_state and scroll value before returning or recreating renderer
        old_state = dict(initial_state) if initial_state is not None else {}
        old_scroll = initial_scroll if initial_scroll is not None else self.detail_scroll.verticalScrollBar().value()
        if not old_state:
            if self._borrowed_renderer_id is not None:
                old_ren = self.artifact_panel.renderers.get(self._borrowed_renderer_id)
                if old_ren is not None:
                    old_state = old_ren.view_state()
            elif self._detail_renderer is not None:
                old_state = self._detail_renderer.view_state()

        self._return_borrowed_renderer()
        self._update_detail_header(src)

        # Look up backing artifact in ArtifactStore or projector
        art: Optional[Artifact] = None
        if src.artifact_id:
            if self.store is not None:
                art = self.store.get(src.artifact_id, src.revision) or self.store.get(src.artifact_id)
            if art is None:
                art = self.projector._artifacts.get(src.artifact_id)

        if art is not None and art.id in self.artifact_panel.renderers:
            # Borrow the existing QtViewRenderer so we never duplicate it!
            renderer = self.artifact_panel.renderers[art.id]
            self.artifact_panel.layout.removeWidget(renderer)
            renderer.set_compact(False)
            if not old_state:
                for disc in renderer.disclosures.values():
                    disc.set_open(True, animate=False)
            else:
                renderer.restore_view_state(old_state)
                if "details" in old_state:
                    opened_set = set(old_state["details"])
                    for name, disc in renderer.disclosures.items():
                        disc.set_open(name in opened_set, animate=False)
            self.detail_renderer_layout.addWidget(renderer)
            renderer.show()
            self._borrowed_renderer_id = art.id
            self.detail_renderer_host.show()
            self.detail_fallback_lbl.hide()
            self.detail_scroll.verticalScrollBar().setValue(old_scroll)
            self._rendered_detail_source_id = src.node_id
            self._rendered_detail_revision = src.revision
            self._rendered_detail_available = src.available
            return

        if art is not None:
            spec = self.provider.provide_view(art)
            valid, _ = validate_view_spec(spec, art, self.registry)
            if not valid:
                spec = StandardViewProvider(self.registry).provide_view(art)
            renderer = QtViewRenderer(spec, artifact=art, parent=self.detail_renderer_host)
            renderer.set_compact(False)
            if not old_state:
                for disc in renderer.disclosures.values():
                    disc.set_open(True, animate=False)
            else:
                renderer.restore_view_state(old_state)
                if "details" in old_state:
                    opened_set = set(old_state["details"])
                    for name, disc in renderer.disclosures.items():
                        disc.set_open(name in opened_set, animate=False)
            if self.on_action:
                renderer.action_dispatched.connect(self.on_action)
            if self.on_input:
                renderer.input_submitted.connect(self.on_input)
            self._detail_renderer = renderer
            self.detail_renderer_layout.addWidget(renderer)
            self.detail_renderer_host.show()
            self.detail_fallback_lbl.hide()
            self.detail_scroll.verticalScrollBar().setValue(old_scroll)
            self._rendered_detail_source_id = src.node_id
            self._rendered_detail_revision = src.revision
            self._rendered_detail_available = src.available
            return

        # Source observed without an ArtifactStore entry (e.g. search metadata or tool result)
        self.detail_renderer_host.hide()
        details = [f"Nguồn: {src.title}"]
        if src.scope_label:
            details.append(f"Phạm vi đã quan sát: {src.scope_label}")
        if not src.available and src.availability_note:
            details.append(f"Trạng thái tệp: {src.availability_note}")
        if src.snippet:
            details.append(f"\nNội dung đã quan sát:\n{src.snippet}")
        elif not src.read:
            details.append("\nMới quan sát thấy tên tệp trong chỉ mục, chưa đọc nội dung bên trong.")
        self.detail_fallback_lbl.setText("\n".join(details))
        self.detail_fallback_lbl.show()
        self.detail_scroll.verticalScrollBar().setValue(old_scroll)
        self._rendered_detail_source_id = src.node_id
        self._rendered_detail_revision = src.revision
        self._rendered_detail_available = src.available

    def _capture_focus_state(self) -> Dict[str, Any]:
        fw = QApplication.focusWidget()
        win = self.window()
        composer = getattr(win, "chat_composer_input", None) if win is not None else None
        cursor_info = None
        line_sel_info = None
        if composer is not None:
            if hasattr(composer, "textCursor"):
                tc = composer.textCursor()
                cursor_info = (tc.anchor(), tc.position())
            elif hasattr(composer, "selectionStart") and hasattr(composer, "cursorPosition"):
                line_sel_info = (
                    composer.selectionStart(),
                    len(composer.selectedText() or ""),
                    composer.cursorPosition(),
                )
        return {
            "focus_widget": fw,
            "composer": composer,
            "composer_had_focus": bool(composer is not None and (fw is composer or composer.hasFocus())),
            "cursor_info": cursor_info,
            "line_sel_info": line_sel_info,
        }

    def _restore_focus_state(self, state: Dict[str, Any], *, target_mode: str) -> None:
        composer = state.get("composer")
        cursor_info = state.get("cursor_info")
        line_sel_info = state.get("line_sel_info")
        if state.get("composer_had_focus") and composer is not None:
            composer.setFocus()
        if composer is not None and cursor_info is not None and hasattr(composer, "textCursor"):
            tc = composer.textCursor()
            if (tc.anchor(), tc.position()) != cursor_info:
                tc.setPosition(cursor_info[0])
                tc.setPosition(cursor_info[1], tc.MoveMode.KeepAnchor)
                composer.setTextCursor(tc)
        elif composer is not None and line_sel_info is not None:
            sel_start, sel_len, cur_pos = line_sel_info
            if sel_start is not None and sel_start >= 0 and sel_len > 0 and hasattr(composer, "setSelection"):
                composer.setSelection(sel_start, sel_len)
            elif hasattr(composer, "setCursorPosition"):
                composer.setCursorPosition(cur_pos)
        if state.get("composer_had_focus") and composer is not None:
            return
        fw = state.get("focus_widget")
        if fw is not None and (hasattr(fw, "textCursor") or hasattr(fw, "setSelection")):
            fw.setFocus()
            return
        if target_mode == "source_detail" and isinstance(fw, (SourceCardWidget, ExcerptCardWidget)):
            self.btn_back_overview.setFocus()
        elif target_mode == "overview" and fw is self.btn_back_overview and self.selected_source_id:
            card = self._source_cards.get(self.selected_source_id) or self._overflow_cards.get(self.selected_source_id)
            if card is not None and card.isVisible():
                card.setFocus()

    def select_source(self, node_id: str) -> bool:
        """
        Switch from overview to deep view of `node_id` without calling the model,
        reading extra files, mutating task state, or disturbing composer draft/focus.
        """
        src = self.find_source(node_id)
        if src is None:
            return False
        focus_state = self._capture_focus_state()
        if self.mode == "overview":
            self._overview_scroll_value = self.overview_scroll.verticalScrollBar().value()
        if self.selected_source_id != node_id or self.mode != "source_detail":
            self._rendered_detail_source_id = None
            self._rendered_detail_revision = None
            self._rendered_detail_available = None
        self.selected_source_id = node_id
        self.mode = "source_detail"
        self._render_detail_for_source(src)
        self.stack.setCurrentWidget(self.detail_page)
        self._restore_focus_state(focus_state, target_mode="source_detail")
        self._run_transition()
        self.mode_changed.emit(self.mode)
        self.content_changed.emit()
        return True

    def show_overview(self) -> None:
        """Return from source detail to desk overview and restore reading position."""
        if self.mode == "overview":
            return
        focus_state = self._capture_focus_state()
        self._return_borrowed_renderer()
        self._rendered_detail_source_id = None
        self._rendered_detail_revision = None
        self._rendered_detail_available = None
        self.result_card.ensure_artifact_panel_attached()
        self.mode = "overview"
        self.stack.setCurrentWidget(self.overview_scroll)
        self.overview_scroll.verticalScrollBar().setValue(self._overview_scroll_value)
        self._restore_focus_state(focus_state, target_mode="overview")
        self._run_transition()
        self.mode_changed.emit(self.mode)
        self.content_changed.emit()

    def handle_navigation_command(self, text: str) -> bool:
        """
        Execute local scene navigation command if `text` matches one.
        Returns True if handled locally (caller should not submit to model).
        """
        parsed = parse_scene_command(
            text,
            self.all_sources(),
            in_source_detail=(self.mode == "source_detail"),
        )
        if parsed is None:
            return False
        action, target_id = parsed
        if action == "overview":
            self.show_overview()
            return True
        if action == "source_detail" and target_id:
            return self.select_source(target_id)
        return False

    def apply_snapshot(
        self,
        snapshot: WorkSceneSnapshot,
        *,
        artifacts: Optional[Sequence[Artifact]] = None,
        animate: bool = True,
    ) -> None:
        import time as _time

        t0 = _time.perf_counter()
        self.current_snapshot = snapshot

        if artifacts is not None:
            borrowed = self._borrowed_renderer_id
            borrowed_ren = self.artifact_panel.renderers.get(borrowed) if borrowed is not None else None
            new_borrowed_art = next((a for a in artifacts if a.id == borrowed), None) if borrowed is not None else None

            # Only genuine revision changes detach/reborrow the renderer
            borrowed_revision_changed = False
            if borrowed is not None and borrowed_ren is not None:
                if new_borrowed_art is not None:
                    current_rev = getattr(getattr(borrowed_ren, "artifact", None), "revision", None)
                    new_rev = getattr(new_borrowed_art, "revision", None)
                    if new_rev != current_rev:
                        borrowed_revision_changed = True
                else:
                    # Borrowed artifact was removed from incoming artifacts list
                    borrowed_revision_changed = True

            saved_detail_state = None
            saved_detail_scroll = None
            if borrowed_revision_changed:
                if borrowed_ren is not None:
                    saved_detail_state = borrowed_ren.view_state()
                saved_detail_scroll = self.detail_scroll.verticalScrollBar().value()
                self._return_borrowed_renderer()

            self.artifact_panel.update_artifacts(list(artifacts))

            if borrowed_revision_changed and self.mode == "source_detail" and self.selected_source_id:
                src = self.find_source(self.selected_source_id)
                if src is not None:
                    self._render_detail_for_source(
                        src,
                        initial_state=saved_detail_state,
                        initial_scroll=saved_detail_scroll,
                    )

        has_sources = bool(snapshot.primary_sources or snapshot.overflow_sources)
        self.group_caption.setVisible(has_sources and not snapshot.edges)
        self.sources_container.setVisible(bool(snapshot.primary_sources))
        self._sync_source_card_map(
            snapshot.primary_sources,
            self._source_cards,
            self.sources_layout,
            animate=animate,
        )
        self._sync_overflow_ui(snapshot.overflow_sources)
        self.excerpt_card.set_excerpt(snapshot.active_excerpt)
        self.relations_widget.set_edges(snapshot.edges)
        self.result_card.update_result(
            snapshot.result_node,
            has_rendered_artifacts=bool(self.artifact_panel.renderers),
        )
        self._sync_trace_ui(
            snapshot.trace_entries,
            reasoning_flow=snapshot.reasoning_flow,
            qa_telemetry=snapshot.qa_telemetry,
        )

        if self.mode == "source_detail" and self.selected_source_id:
            src = self.find_source(self.selected_source_id)
            if src is not None:
                src.refresh_availability()
                needs_re_render = (
                    self.selected_source_id != self._rendered_detail_source_id
                    or src.revision != self._rendered_detail_revision
                    or src.available != self._rendered_detail_available
                )
                if needs_re_render:
                    self._render_detail_for_source(src)
                else:
                    self._update_detail_header(src)
            else:
                self.show_overview()

        if animate:
            self._run_transition()
        self.last_update_ms = (_time.perf_counter() - t0) * 1000.0
        self.content_changed.emit()

    def try_handle_scene_command(self, text: str) -> bool:
        return self.handle_navigation_command(text)

    def reset(self, *, generation: Optional[int] = None) -> None:
        self._stop_all_animations()
        if self.mode != "overview":
            self.show_overview()
        self._return_borrowed_renderer()
        self.overflow_expanded = False
        self.trace_expanded = False
        snap = self.projector.reset(generation=generation)
        self.apply_snapshot(snap, artifacts=[], animate=False)

    def begin_turn(
        self,
        query: str,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
        turn_id: Optional[Any] = None,
        turn_contract: Optional[Any] = None,
        previous_sources: Optional[Sequence[Any]] = None,
        previous_artifacts: Optional[Sequence[Artifact]] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ) -> WorkSceneSnapshot:
        if artifact_store is not None:
            self.store = artifact_store
        snap = self.projector.begin_turn(
            query,
            turn_id=str(turn_id) if turn_id is not None else None,
            execution_id=execution_id,
            generation=generation,
            turn_contract=turn_contract,
        )
        self.apply_snapshot(snap, artifacts=previous_artifacts, animate=True)
        return snap

    def on_turn_contract(
        self,
        contract: Any,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        ok = self.projector.record_turn_contract(
            contract,
            generation=generation,
            execution_id=execution_id,
        )
        if ok:
            self.apply_snapshot(self.projector.snapshot(store=self.store), animate=False)
        return ok

    def on_text_streamed(
        self,
        text: str,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        ok = self.projector.record_text_stream(
            text,
            generation=generation,
            execution_id=execution_id,
        )
        if ok:
            self.apply_snapshot(self.projector.snapshot(store=self.store), animate=False)
        return ok

    def on_progress(
        self,
        status: str,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
    ) -> bool:
        ok = self.projector.record_progress(
            status,
            generation=generation,
            execution_id=execution_id,
        )
        if ok:
            self.apply_snapshot(self.projector.snapshot(store=self.store), animate=False)
        return ok

    def on_step(
        self,
        step: Any,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ) -> bool:
        if artifact_store is not None:
            self.store = artifact_store
        ok = self.projector.record_step(
            step,
            store=self.store,
            generation=generation,
            execution_id=execution_id,
        )
        if ok:
            arts = list(self.projector._artifacts.values())
            self.apply_snapshot(self.projector.snapshot(store=self.store), artifacts=arts, animate=True)
        return ok

    def on_response(
        self,
        response: Any,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
        artifact_store: Optional[ArtifactStore] = None,
        pending_input_request: Optional[Any] = None,
    ) -> bool:
        if artifact_store is not None:
            self.store = artifact_store
        ok = self.projector.record_response(
            response,
            store=self.store,
            generation=generation,
            execution_id=execution_id,
        )
        if ok:
            arts = list(self.projector._artifacts.values())
            self.apply_snapshot(self.projector.snapshot(store=self.store), artifacts=arts, animate=True)
        return ok

    def on_cancel(
        self,
        *,
        generation: Optional[int] = None,
        execution_id: Optional[str] = None,
        new_generation: Optional[int] = None,
    ) -> WorkSceneSnapshot:
        snap = self.projector.cancel(execution_id, new_generation=new_generation)
        self.apply_snapshot(snap, animate=False)
        return snap

    def on_artifact_result(
        self,
        result: DispatchResult,
        *,
        artifact_store: Optional[ArtifactStore] = None,
        generation: Optional[int] = None,
    ) -> bool:
        if artifact_store is not None:
            self.store = artifact_store
        ok = self.projector.record_artifact_result(
            result,
            store=self.store,
            generation=generation,
        )
        if ok:
            arts = list(self.projector._artifacts.values())
            self.apply_snapshot(self.projector.snapshot(store=self.store), artifacts=arts, animate=True)
        return ok

    def refresh_from_store(
        self,
        *,
        sources: Optional[Sequence[Any]] = None,
        artifacts: Optional[Sequence[Artifact]] = None,
        artifact_store: Optional[ArtifactStore] = None,
        pending_input_request: Optional[Any] = None,
        changed_artifact: Optional[Artifact] = None,
    ) -> None:
        if artifact_store is not None:
            self.store = artifact_store
        if changed_artifact is not None:
            self.projector._ingest_artifact(changed_artifact, store=self.store, is_direct=True)
        for art in artifacts or []:
            if isinstance(art, Artifact) and (changed_artifact is None or art.id != changed_artifact.id):
                prev = self.projector._artifacts.get(art.id)
                if prev is None or prev.revision != art.revision:
                    self.projector._ingest_artifact(art, store=self.store, is_direct=False)
        snap = self.projector.snapshot(store=self.store)
        all_arts = list(artifacts) if artifacts is not None else list(self.projector._artifacts.values())
        self.apply_snapshot(snap, artifacts=all_arts, animate=True)

    def _render_snapshot(self, *, animate: bool = False) -> None:
        snap = self.projector.snapshot(store=self.store)
        arts = list(self.projector._artifacts.values())
        self.apply_snapshot(snap, artifacts=arts, animate=animate)

    def active_animation_count(self) -> int:
        count = 1 if self._scene_anim.state() == QPropertyAnimation.State.Running else 0
        for card in list(self._source_cards.values()) + list(self._overflow_cards.values()):
            if card._anim.state() == QPropertyAnimation.State.Running:
                count += 1
        return count

    def preferred_height(self, max_height: int = 440) -> int:
        if self.is_empty():
            return 0
        active_body = self.detail_page if self.mode == "source_detail" else self.overview_body
        active_body.layout().activate()
        hint_h = active_body.sizeHint().height() + 12
        if (
            hasattr(self, "finder_box")
            and self.finder_box.isVisible()
            and self.finder_box.has_visible_content()
        ):
            hint_h = max(hint_h, self.finder_box.sizeHint().height() + 18)
        return max(76, min(max_height, hint_h))
