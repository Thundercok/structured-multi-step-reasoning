"""Request identity shared by desktop execution paths, without owning a model."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, Optional

CONTEXT_ADAPTER_SCHEMA_VERSION = "rat.context_adapter/v1"


def build_execution_context_snapshot(
    query: str,
    *,
    turn_ref: Any = None,
    execution_id: Optional[str] = None,
    generation: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compile an immutable, hash-pinned context snapshot at submission time.

    Independent of future mutations to ConversationHistory or WorkNotebook.
    """
    ctx = context or {}
    history = copy.deepcopy(ctx.get("history") or [])
    turn_references = copy.deepcopy(ctx.get("turn_references") or [])
    task_state = copy.deepcopy(ctx.get("task_state") or {})
    previous_sources = copy.deepcopy(ctx.get("previous_sources") or [])
    artifact_refs = copy.deepcopy(ctx.get("artifact_refs") or [])

    turn_ref_dict = None
    if turn_ref is not None:
        if hasattr(turn_ref, "to_dict"):
            turn_ref_dict = turn_ref.to_dict()
        elif hasattr(turn_ref, "__dict__"):
            turn_ref_dict = {
                "conversation_id": getattr(turn_ref, "conversation_id", None),
                "turn_id": getattr(turn_ref, "turn_id", None),
                "kind": getattr(turn_ref, "kind", "chat"),
                "turn_number": getattr(turn_ref, "turn_number", None),
                "target_turn_id": getattr(turn_ref, "target_turn_id", None),
                "target_artifact_id": getattr(turn_ref, "target_artifact_id", None),
                "target_revision": getattr(turn_ref, "target_revision", None),
            }
        elif isinstance(turn_ref, dict):
            turn_ref_dict = copy.deepcopy(turn_ref)

    snapshot = {
        "schema_version": CONTEXT_ADAPTER_SCHEMA_VERSION,
        "query": str(query),
        "execution_id": execution_id,
        "generation": generation,
        "turn_ref": turn_ref_dict,
        "history": history,
        "turn_references": turn_references,
        "task_state": task_state,
        "previous_sources": previous_sources,
        "artifact_refs": artifact_refs,
    }

    canonical_bytes = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    snapshot["snapshot_hash"] = hashlib.sha256(canonical_bytes).hexdigest()
    return snapshot


def render_backend_input(query: str, snapshot: Optional[Dict[str, Any]] = None) -> str:
    """Format the backend input snapshot for reasoning execution while keeping query clean for UI."""
    clean_q = str(query).strip()
    if not snapshot:
        return clean_q

    has_history = bool(snapshot.get("history"))
    has_refs = bool(snapshot.get("turn_references"))
    has_task = bool(snapshot.get("task_state"))
    has_artifacts = bool(snapshot.get("artifact_refs"))
    t_ref = snapshot.get("turn_ref") or {}
    has_target = bool(t_ref.get("target_turn_id") or t_ref.get("target_artifact_id"))

    if not (has_history or has_refs or has_task or has_artifacts or has_target):
        return clean_q

    sections = [f"[Conversation Context (schema: {snapshot.get('schema_version', CONTEXT_ADAPTER_SCHEMA_VERSION)})]"]

    if has_target:
        target_info = f"Referenced Prior Turn: {t_ref.get('target_turn_id')}"
        if t_ref.get("target_artifact_id"):
            target_info += f" | Target Artifact: {t_ref.get('target_artifact_id')}@v{t_ref.get('target_revision')}"
        sections.append(target_info)

    if has_refs:
        sections.append("Prior Turn References:")
        refs = snapshot["turn_references"]
        pinned = [ref for ref in refs[:-4] if ref.get("turn_id") == t_ref.get("target_turn_id")]
        for ref in pinned + refs[-4:]:
            tid = ref.get("turn_id", "")
            q = ref.get("user_query", "")
            ans = ref.get("assistant_summary", "")
            sections.append(f"- Turn {tid}: User: '{q}' -> Assistant: '{ans}'")
    if has_history:
        sections.append("Recent Dialogue:")
        for msg in snapshot["history"][-4:]:
            sections.append(f"- {msg.get('role', 'user')}: {msg.get('content', '')}")

    if has_task and snapshot["task_state"]:
        sections.append(f"Active Task State: {json.dumps(snapshot['task_state'], ensure_ascii=False)}")

    if has_artifacts and snapshot["artifact_refs"]:
        art_summaries = []
        artifacts = snapshot["artifact_refs"]
        pinned = [a for a in artifacts[:-4]
                  if (a.get("id") or a.get("artifact_id")) == t_ref.get("target_artifact_id")
                  and a.get("revision") == t_ref.get("target_revision")]
        for a in pinned + artifacts[-4:]:
            aid = a.get("id") or a.get("artifact_id")
            rev = a.get("revision")
            inputs = a.get("inputs") or {}
            art_summaries.append(f"{aid}@v{rev} inputs={inputs}")
        sections.append(f"Artifact State: {'; '.join(art_summaries)}")

    sections.append("\n[Current Request]")
    sections.append(clean_q)
    return "\n".join(sections)


def validate_referenced_context(snapshot):
    """Explicit references are required inputs, rather than hints to guess at."""
    target = snapshot.get("turn_ref") or {}
    turn_id = target.get("target_turn_id")
    if turn_id and not any(ref.get("turn_id") == turn_id
                           for ref in snapshot.get("turn_references", []) + snapshot.get("history", [])):
        raise ValueError("missing_referenced_turn")
    artifact_id = target.get("target_artifact_id")
    if artifact_id and not any(
        (ref.get("id") or ref.get("artifact_id")) == artifact_id
        and ref.get("revision") == target.get("target_revision")
        for ref in snapshot.get("artifact_refs", [])
    ):
        raise ValueError("missing_referenced_artifact_revision")


@dataclass(frozen=True)
class ExecutionRequest:
    query: str
    execution_id: str | None = None
    generation: int | None = None
    turn_ref: Any = None
    document_path: str | None = None
    lane: str = "auto"
    context: dict = field(default_factory=dict)
    timeout_s: float | None = None
    max_strategy_invocations: int | None = None
    max_underlying_requests: int | None = None
    max_generated_tokens: int | None = None
    _submitted_context: dict = field(init=False, repr=False, compare=False)
    _snapshot: dict = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if self.lane not in {"auto", "assistant", "document", "reasoning", "operation"}:
            raise ValueError("unknown_execution_lane")
        if self.document_path and self.lane in {"reasoning", "operation"}:
            raise ValueError("document_requires_qa_lane")
        submitted = copy.deepcopy(self.context)
        object.__setattr__(self, "_submitted_context", submitted)
        object.__setattr__(self, "_snapshot", build_execution_context_snapshot(
            self.query, turn_ref=self.turn_ref, execution_id=self.execution_id,
            generation=self.generation, context=submitted,
        ))

    def assistant_context(self):
        return {**copy.deepcopy(self._submitted_context), "turn_ref": self.turn_ref,
                "execution_id": self.execution_id}

    def context_snapshot(self) -> Dict[str, Any]:
        """Produce the immutable, hash-pinned context snapshot for this request."""
        return copy.deepcopy(self._snapshot)


def execution_response(request, result):
    """Adapt a strategy result for the existing conversation consumer.

    A completed generation is not proof of a verified answer or tool effect.
    No strategy internals/private reasoning are copied to public step traces.
    """
    from rat.engine.assistant_runtime import AgentResponse
    observed_id = getattr(result, "execution_id", None)
    observed_generation = getattr(result, "query_generation", None)
    if ((request.execution_id and observed_id and request.execution_id != observed_id)
            or (request.generation is not None and observed_generation is not None
                and request.generation != observed_generation)):
        return AgentResponse("", [], 0, 0, 0, error="stale_execution_result",
                             execution_id=request.execution_id)
    if isinstance(result, AgentResponse):
        result.execution_id = request.execution_id or result.execution_id
        result.turn_id = getattr(request.turn_ref, "turn_id", None) or result.turn_id
        return result
    ledger = dict(result.cost_ledger or {})
    prompt_tokens = ledger.get("prompt_tokens")
    generated_tokens = ledger.get("generated_tokens", result.tokens)
    snap = getattr(result, "context_snapshot", None) or request.context_snapshot()
    t_ref = getattr(request, "turn_ref", None)
    target_turn_id = getattr(t_ref, "target_turn_id", None) if hasattr(t_ref, "target_turn_id") else (t_ref.get("target_turn_id") if isinstance(t_ref, dict) else None)
    target_artifact_id = getattr(t_ref, "target_artifact_id", None) if hasattr(t_ref, "target_artifact_id") else (t_ref.get("target_artifact_id") if isinstance(t_ref, dict) else None)
    target_revision = getattr(t_ref, "target_revision", None) if hasattr(t_ref, "target_revision") else (t_ref.get("target_revision") if isinstance(t_ref, dict) else None)

    return AgentResponse(
        answer=result.answer, steps=[], total_time_ms=result.latency_ms,
        tool_call_count=0, token_estimate=generated_tokens,
        prompt_tokens=prompt_tokens or 0, completion_tokens=generated_tokens,
        total_tokens=(prompt_tokens or 0) + generated_tokens,
        sources=list(result.citations),
        error=None if result.status == "completed" else result.status,
        token_scope="generated_tokens" if prompt_tokens is None else "prompt_and_completion",
        execution_id=request.execution_id, turn_id=getattr(request.turn_ref, "turn_id", None),
        completion_status="unchecked", answer_verification_status="UNKNOWN",
        qa_telemetry={
            "execution_lane": "reasoning",
            "execution_mode": result.execution_mode,
            "policy_source": result.policy_source,
            "bundle_id": result.bundle_id,
            "bundle_review_status": getattr(result, "bundle_review_status", None),
            "cost_ledger": ledger,
            "query_generation": request.generation,
            "context_snapshot_schema": snap.get("schema_version") if snap else None,
            "context_snapshot_hash": snap.get("snapshot_hash") if snap else None,
            "backend_input": getattr(result, "backend_input", None),
            "user_displayed_query": request.query,
            "target_turn_id": target_turn_id,
            "target_artifact_id": target_artifact_id,
            "target_revision": target_revision,
        },
    )


def execution_step(step, number=1):
    from rat.engine.assistant_runtime import AgentStep
    if isinstance(step, AgentStep):
        return step
    strategy = getattr(getattr(step, "strategy", None), "name", "strategy")
    return AgentStep(number, f"Đã thực hiện chiến lược {strategy}",
                     completion_tokens=getattr(step, "generated_tokens", 0))
