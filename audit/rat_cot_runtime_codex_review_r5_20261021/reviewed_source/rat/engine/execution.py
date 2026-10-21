"""Request identity shared by desktop execution paths, without owning a model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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

    def __post_init__(self):
        if self.lane not in {"auto", "assistant", "document", "reasoning", "operation"}:
            raise ValueError("unknown_execution_lane")
        if self.document_path and self.lane in {"reasoning", "operation"}:
            raise ValueError("document_requires_qa_lane")

    def assistant_context(self):
        return {**self.context, "turn_ref": self.turn_ref, "execution_id": self.execution_id}


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
        qa_telemetry={"execution_lane": "reasoning", "execution_mode": result.execution_mode,
                      "policy_source": result.policy_source, "bundle_id": result.bundle_id,
                      "cost_ledger": ledger, "query_generation": request.generation},
    )


def execution_step(step, number=1):
    from rat.engine.assistant_runtime import AgentStep
    if isinstance(step, AgentStep):
        return step
    strategy = getattr(getattr(step, "strategy", None), "name", "strategy")
    return AgentStep(number, f"Đã thực hiện chiến lược {strategy}",
                     completion_tokens=getattr(step, "generated_tokens", 0))
