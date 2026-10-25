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
    origin: Optional[str] = None,
    goal: Optional[str] = None,
    requested_action: Optional[Dict[str, Any]] = None,
    resource_bindings: Optional[list] = None,
    expected_outcomes: Optional[list] = None,
    budget: Optional[Dict[str, Any]] = None,
    continuation: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
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
    source_evidence = copy.deepcopy(ctx.get("source_evidence") or [])
    requires_grounding = bool(ctx.get("requires_grounding", False))

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
        "source_evidence": source_evidence,
        "requires_grounding": requires_grounding,
        "origin": origin or ctx.get("origin", "chat"),
        "goal": goal or ctx.get("goal") or str(query),
        "requested_action": copy.deepcopy(requested_action if requested_action is not None else ctx.get("requested_action")),
        "resource_bindings": copy.deepcopy(resource_bindings if resource_bindings is not None else ctx.get("resource_bindings", [])),
        "expected_outcomes": copy.deepcopy(expected_outcomes if expected_outcomes is not None else ctx.get("expected_outcomes", [])),
        "budget": copy.deepcopy(budget if budget is not None else ctx.get("budget", {})),
        "continuation": copy.deepcopy(continuation if continuation is not None else ctx.get("continuation")),
        "idempotency_key": idempotency_key or ctx.get("idempotency_key"),
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
    has_evidence = bool(snapshot.get("source_evidence"))
    t_ref = snapshot.get("turn_ref") or {}
    has_target = bool(t_ref.get("target_turn_id") or t_ref.get("target_artifact_id"))

    if not (has_history or has_refs or has_task or has_artifacts or has_target or has_evidence):
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

    if has_evidence:
        sections.append("Authoritative Source Evidence (Grounding):")
        for ev in snapshot["source_evidence"]:
            ev_id = ev.get("source_id", "src")
            kind = ev.get("kind", "source")
            loc = []
            if ev.get("path"):
                loc.append(str(ev.get("path")))
            if ev.get("page_num"):
                loc.append(f"Page {ev.get('page_num')}")
            loc_str = f" [{', '.join(loc)}]" if loc else ""
            sha = f" sha256:{ev.get('sha256')[:8]}" if ev.get("sha256") else ""
            excerpt = (ev.get("excerpt") or "").strip()
            if excerpt:
                sections.append(f"- [{ev_id}] ({kind}{loc_str}{sha}): \"{excerpt}\"")
            else:
                sections.append(f"- [{ev_id}] ({kind}{loc_str}{sha})")

    sections.append("\n[Current Request]")
    sections.append(clean_q)
    return "\n".join(sections)


def validate_referenced_context(snapshot):
    """Explicit references are required inputs, rather than hints to guess at."""
    if snapshot.get("requires_grounding") and not snapshot.get("source_evidence"):
        raise ValueError("missing_grounding_evidence")
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
    # Envelope extensions (rat.agent_request/v1)
    conversation_id: str | None = None
    turn_id: str | None = None
    origin: str = "chat"
    goal: str | None = None
    requested_action: dict | None = None
    resource_bindings: list[dict] = field(default_factory=list)
    expected_outcomes: list[dict] = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    continuation: dict | None = None
    idempotency_key: str | None = None
    _submitted_context: dict = field(init=False, repr=False, compare=False)
    _snapshot: dict = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if self.lane not in {"auto", "assistant", "document", "reasoning", "operation"}:
            raise ValueError("unknown_execution_lane")
        if self.document_path and self.lane in {"reasoning", "operation"}:
            raise ValueError("document_requires_qa_lane")

        if self.goal is None:
            object.__setattr__(self, "goal", self.query)
        if self.turn_id is None and self.turn_ref is not None:
            t_id = getattr(self.turn_ref, "turn_id", None) or (self.turn_ref.get("turn_id") if isinstance(self.turn_ref, dict) else None)
            if t_id:
                object.__setattr__(self, "turn_id", str(t_id))
        if self.conversation_id is None and self.turn_ref is not None:
            c_id = getattr(self.turn_ref, "conversation_id", None) or (self.turn_ref.get("conversation_id") if isinstance(self.turn_ref, dict) else None)
            if c_id:
                object.__setattr__(self, "conversation_id", str(c_id))

        merged_bindings = list(self.resource_bindings)
        if self.document_path and not any(r.get("path") == self.document_path or r.get("file_path") == self.document_path for r in merged_bindings):
            merged_bindings.append({"kind": "document", "path": self.document_path})
            object.__setattr__(self, "resource_bindings", merged_bindings)

        merged_budget = dict(self.budget)
        if self.timeout_s is not None and "deadline_s" not in merged_budget:
            merged_budget["deadline_s"] = self.timeout_s
        if self.max_generated_tokens is not None and "max_generated_tokens" not in merged_budget:
            merged_budget["max_generated_tokens"] = self.max_generated_tokens
        if self.max_strategy_invocations is not None and "max_strategy_invocations" not in merged_budget:
            merged_budget["max_strategy_invocations"] = self.max_strategy_invocations
        if self.max_underlying_requests is not None and "max_underlying_requests" not in merged_budget:
            merged_budget["max_underlying_requests"] = self.max_underlying_requests
        object.__setattr__(self, "budget", merged_budget)

        submitted = copy.deepcopy(self.context)
        object.__setattr__(self, "_submitted_context", submitted)
        object.__setattr__(self, "_snapshot", build_execution_context_snapshot(
            self.query, turn_ref=self.turn_ref, execution_id=self.execution_id,
            generation=self.generation, context=submitted,
            origin=self.origin, goal=self.goal, requested_action=self.requested_action,
            resource_bindings=self.resource_bindings, expected_outcomes=self.expected_outcomes,
            budget=self.budget, continuation=self.continuation, idempotency_key=self.idempotency_key,
        ))

    def assistant_context(self) -> Dict[str, Any]:
        ctx = {**copy.deepcopy(self._submitted_context), "turn_ref": self.turn_ref,
               "execution_id": self.execution_id, "conversation_id": self.conversation_id}
        if self.document_path:
            ctx["selected_document_path"] = self.document_path
        valid_keys = {
            "history", "previous_sources", "member_id", "task_state",
            "turn_ref", "execution_id", "turn_references", "conversation_id",
            "contract", "selected_document_path", "now_dt", "max_tokens",
            "initial_steps", "initial_decision", "stop_before_tool",
            "max_verification_repairs", "decision_callable",
        }
        return {k: v for k, v in ctx.items() if k in valid_keys}

    def context_snapshot(self) -> Dict[str, Any]:
        """Produce the immutable, hash-pinned context snapshot for this request."""
        return copy.deepcopy(self._snapshot)

    def to_agent_request_dict(self) -> Dict[str, Any]:
        """Serialize into rat.agent_request/v1 schema."""
        return {
            "schema_version": "rat.agent_request/v1",
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "execution_id": self.execution_id,
            "generation": self.generation,
            "origin": self.origin,
            "goal": self.goal,
            "requested_action": copy.deepcopy(self.requested_action),
            "resource_bindings": copy.deepcopy(self.resource_bindings),
            "expected_outcomes": copy.deepcopy(self.expected_outcomes),
            "budget": copy.deepcopy(self.budget),
            "continuation": copy.deepcopy(self.continuation),
            "idempotency_key": self.idempotency_key,
            "context_snapshot": self.context_snapshot(),
        }


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
            "contradiction_report": getattr(result, "contradiction_report", None),
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
