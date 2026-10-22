"""
rat.kernel.contracts — Shared headless contracts for the RAT interaction kernel.

Defines:
- InputRequest: pending operation input requirements (natural language & direct input)
- Artifact: versioned, typed output objects independent of UI widgets
- ArtifactStore: in-memory store preserving active deliverables and revision history
- ArtifactAction: declared operations bound to specific artifact revisions
- DispatchResult & ExecutionEvent: truthful runtime state and action results

Zero Qt dependencies. Zero personal file indexing. Safe for headless execution.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import threading
import time
from uuid import uuid4
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SourceEvidence:
    """Immutable evidence binding a claim or reasoning step to an authoritative source."""

    source_id: str
    kind: str  # "pdf_page" | "file_excerpt" | "artifact" | "turn"
    path: str = ""
    page_num: Optional[int] = None
    char_span: Optional[Tuple[int, int]] = None
    excerpt: str = ""
    sha256: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "path": self.path,
            "page_num": self.page_num,
            "char_span": list(self.char_span) if self.char_span else None,
            "excerpt": self.excerpt,
            "sha256": self.sha256,
            "provenance": copy.deepcopy(self.provenance),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceEvidence:
        span = data.get("char_span")
        char_span = tuple(span) if isinstance(span, (list, tuple)) and len(span) == 2 else None
        return cls(
            source_id=data.get("source_id", ""),
            kind=data.get("kind", "file_excerpt"),
            path=data.get("path", ""),
            page_num=data.get("page_num"),
            char_span=char_span,
            excerpt=data.get("excerpt", ""),
            sha256=data.get("sha256", ""),
            provenance=dict(data.get("provenance", {})),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class InputRequest:
    """Carries validated supplied inputs and fields/choices still needed for a task."""

    operation_name: str
    supplied_inputs: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[Dict[str, Any]] = field(default_factory=list)
    candidate_choices: Optional[List[Dict[str, Any]]] = None
    target_artifact_id: Optional[str] = None
    target_revision: Optional[int] = None
    prompt: str = ""
    id: str = field(default_factory=lambda: "input-" + uuid4().hex)

    def is_complete(self) -> bool:
        """Returns True if no missing fields or choices remain."""
        if self.candidate_choices:
            return False
        required_missing = [f for f in self.missing_fields if f.get("required", True)]
        return len(required_missing) == 0

    def merge(self, values: Dict[str, Any]) -> InputRequest:
        """Create a new InputRequest updating supplied inputs and recalculating missing fields."""
        new_supplied = dict(self.supplied_inputs)
        new_supplied.update({k: v for k, v in values.items() if v is not None and v != ""})

        new_missing = []
        for mf in self.missing_fields:
            name = mf.get("name")
            if name not in new_supplied:
                new_missing.append(copy.deepcopy(mf))

        # If candidates were provided and user selected one
        new_candidates = self.candidate_choices
        if "selected_candidate" in values or (
            new_candidates
            and any(
                new_supplied.get("name") == c.get("name")
                or new_supplied.get("place") == c.get("name")
                for c in new_candidates
            )
        ):
            new_candidates = None

        return InputRequest(
            operation_name=self.operation_name,
            supplied_inputs=new_supplied,
            missing_fields=new_missing,
            candidate_choices=new_candidates,
            target_artifact_id=self.target_artifact_id,
            target_revision=self.target_revision,
            prompt=self.prompt,
            id=self.id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_name": self.operation_name,
            "supplied_inputs": copy.deepcopy(self.supplied_inputs),
            "missing_fields": copy.deepcopy(self.missing_fields),
            "candidate_choices": copy.deepcopy(self.candidate_choices),
            "target_artifact_id": self.target_artifact_id,
            "target_revision": self.target_revision,
            "prompt": self.prompt,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InputRequest:
        return cls(
            id=data.get("id") or "input-" + uuid4().hex,
            operation_name=data.get("operation_name", ""),
            supplied_inputs=dict(data.get("supplied_inputs", {})),
            missing_fields=list(data.get("missing_fields", [])),
            candidate_choices=data.get("candidate_choices"),
            target_artifact_id=data.get("target_artifact_id"),
            target_revision=data.get("target_revision"),
            prompt=data.get("prompt", ""),
        )


@dataclass
class Artifact:
    """Versioned data deliverable produced by an operation."""

    id: str
    kind: str
    revision: int = 1
    payload: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    title: str = ""
    status: str = "ready"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "revision": self.revision,
            "payload": copy.deepcopy(self.payload),
            "inputs": copy.deepcopy(self.inputs),
            "provenance": copy.deepcopy(self.provenance),
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Artifact:
        return cls(
            id=data.get("id", ""),
            kind=data.get("kind", ""),
            revision=data.get("revision", 1),
            payload=dict(data.get("payload", {})),
            inputs=dict(data.get("inputs", {})),
            provenance=dict(data.get("provenance", {})),
            title=data.get("title", ""),
            status=data.get("status", "ready"),
            created_at=data.get("created_at", time.time()),
        )


class ArtifactStore:
    """Preserves artifacts and historical revisions in memory with thread safety."""

    def __init__(self, max_artifacts: int = 100, max_history_per_artifact: int = 20) -> None:
        self._max_artifacts = max_artifacts
        self._max_history = max_history_per_artifact
        self._artifacts: Dict[str, Artifact] = {}
        self._history: Dict[str, List[Artifact]] = {}
        # Retain committed revisions after delete/eviction until this epoch ends.
        self._revision_high_water: Dict[str, int] = {}
        self._lock = threading.RLock()
        self._generation = 0

    @property
    def generation(self):
        with self._lock:
            return self._generation

    def next_revision(self, artifact_id: str, *, expected_generation=None) -> int:
        """Suggest the next revision; put still validates it under the lock."""
        with self._lock:
            if expected_generation is not None and expected_generation != self._generation:
                raise ValueError("cancelled:conversation_reset")
            previous = self._artifacts.get(artifact_id)
            last_revision = max(self._revision_high_water.get(artifact_id, 0),
                                previous.revision if previous is not None else 0)
            return last_revision + 1

    def put(self, artifact: Artifact, *, expected_revision=None, expected_generation=None) -> Artifact:
        with self._lock:
            if expected_generation is not None and expected_generation != self._generation:
                raise ValueError("cancelled:conversation_reset")
            previous = self._artifacts.get(artifact.id)
            if expected_revision is not None and (previous is None or previous.revision != expected_revision):
                raise ValueError("stale_revision")
            last_revision = max(self._revision_high_water.get(artifact.id, 0),
                                previous.revision if previous is not None else 0)
            if artifact.revision <= last_revision:
                raise ValueError("non_monotonic_revision")
            # Complete fallible copying before eviction or ledger mutation.
            stored = copy.deepcopy(artifact)
            history_entry = copy.deepcopy(stored)
            returned = copy.deepcopy(stored)
            # Bound total active artifacts
            if artifact.id not in self._artifacts and len(self._artifacts) >= self._max_artifacts:
                # Evict oldest
                oldest_id = min(self._artifacts.keys(), key=lambda k: self._artifacts[k].created_at)
                self.delete(oldest_id)

            self._artifacts[artifact.id] = stored
            if artifact.id not in self._history:
                self._history[artifact.id] = []

            # Append revision to history, bounding history size
            self._history[artifact.id].append(history_entry)
            if len(self._history[artifact.id]) > self._max_history:
                self._history[artifact.id].pop(0)

            self._revision_high_water[artifact.id] = artifact.revision
            return returned

    def get(self, artifact_id: str, revision: Optional[int] = None) -> Optional[Artifact]:
        with self._lock:
            if revision is None:
                art = self._artifacts.get(artifact_id)
                return copy.deepcopy(art) if art else None

            revisions = self._history.get(artifact_id, [])
            for art in revisions:
                if art.revision == revision:
                    return copy.deepcopy(art)
            return None

    def get_history(self, artifact_id: str) -> List[Artifact]:
        with self._lock:
            return copy.deepcopy(self._history.get(artifact_id, []))

    def list(self, kind: Optional[str] = None) -> List[Artifact]:
        with self._lock:
            arts = list(self._artifacts.values())
            if kind:
                arts = [a for a in arts if a.kind == kind]
            return sorted(copy.deepcopy(arts), key=lambda a: a.created_at)

    def find_by_kind(self, kind: str) -> List[Artifact]:
        return self.list(kind=kind)

    def delete(self, artifact_id: str) -> bool:
        with self._lock:
            existed = artifact_id in self._artifacts
            self._artifacts.pop(artifact_id, None)
            self._history.pop(artifact_id, None)
            return existed

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._artifacts.clear()
            self._history.clear()
            self._revision_high_water.clear()


@dataclass
class ArtifactAction:
    """Action that can be executed on a specific artifact revision."""

    id: str
    label: str
    target_artifact_id: str
    target_revision: int
    operation_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    input_schema: Optional[Dict[str, Any]] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "target_artifact_id": self.target_artifact_id,
            "target_revision": self.target_revision,
            "operation_name": self.operation_name,
            "params": copy.deepcopy(self.params),
            "input_schema": copy.deepcopy(self.input_schema),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactAction:
        return cls(
            id=data.get("id", ""),
            label=data.get("label", ""),
            target_artifact_id=data.get("target_artifact_id", ""),
            target_revision=data.get("target_revision", 1),
            operation_name=data.get("operation_name", ""),
            params=dict(data.get("params", {})),
            input_schema=data.get("input_schema"),
            description=data.get("description", ""),
        )


@dataclass
class DispatchResult:
    """Outcome of an action or operation dispatch."""

    status: str  # "success" | "needs_input" | "stale_revision" | "ambiguous_target" | "error"
    artifact: Optional[Artifact] = None
    input_request: Optional[InputRequest] = None
    result: Any = None
    error: Optional[str] = None
    action_id: Optional[str] = None


@dataclass
class ExecutionEvent:
    """Runtime execution event distinct from model-authored descriptions."""

    type: str  # "waiting_input", "operation_started", "operation_progress", "operation_completed", "operation_failed", "artifact_created", "artifact_updated", "turn_completed"
    operation_name: Optional[str] = None
    artifact_id: Optional[str] = None
    payload: Any = None
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    turn_id: Optional[str] = None
    execution_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "operation_name": self.operation_name,
            "artifact_id": self.artifact_id,
            "payload": copy.deepcopy(self.payload) if isinstance(self.payload, dict) else self.payload,
            "timestamp": self.timestamp,
            "error": self.error,
            "turn_id": self.turn_id,
            "execution_id": self.execution_id,
        }


@dataclass
class ExecutionState:
    """Tracks current pending input request, active artifacts, and execution events."""

    pending_input_request: Optional[InputRequest] = None
    active_artifacts: List[str] = field(default_factory=list)
    events: List[ExecutionEvent] = field(default_factory=list)

    def record_event(self, event: ExecutionEvent) -> None:
        self.events.append(event)
        if event.type == "waiting_input" and isinstance(event.payload, InputRequest):
            self.pending_input_request = event.payload
        elif event.type in ("artifact_created", "artifact_updated") and event.artifact_id:
            if event.artifact_id not in self.active_artifacts:
                self.active_artifacts.append(event.artifact_id)
