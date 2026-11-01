"""Data types shared by the assistant runtime loop and its callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class AgentStep:
    step_number: int
    thought: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    duration_ms: float = 0.0
    model_duration_ms: float = 0.0
    tool_duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: Optional[int] = None
    verifier_duration_ms: float = 0.0
    raw_completion: str = ""
    error: Optional[str] = None
    model_input: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Any] = field(default_factory=list)
    verification: List[Dict[str, Any]] = field(default_factory=list)
    turn_id: Optional[str] = None
    execution_id: Optional[str] = None
    note_events: List[Dict[str, Any]] = field(default_factory=list)
    context_boundary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelDecision:
    thought: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    final_answer: Optional[str] = None
    raw_completion: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: Optional[int] = None
    model_duration_ms: float = 0.0
    error: Optional[str] = None
    extra_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model_input: Dict[str, Any] = field(default_factory=dict)
    contract: Optional[Any] = None
    outcomes: Optional[List[Any]] = None
    contract_declared: bool = False
    context_boundary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    answer: str
    steps: List[AgentStep]
    total_time_ms: float
    tool_call_count: int
    token_estimate: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_time_ms: float = 0.0
    tool_time_ms: float = 0.0
    is_live_model: bool = False
    sources: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Any] = field(default_factory=list)
    error: Optional[str] = None
    token_scope: str = "prompt_and_completion"
    controller_decisions: List[Dict[str, Any]] = field(default_factory=list)
    task_state: Dict[str, Any] = field(default_factory=dict)
    task_state_updated: bool = False
    completion_status: str = "unchecked"
    pending_input_request: Optional[Any] = None
    verification_reports: List[Dict[str, Any]] = field(default_factory=list)
    answer_verification_status: str = "UNKNOWN"
    verification_time_ms: float = 0.0
    turn_id: Optional[str] = None
    execution_id: Optional[str] = None
    note_events: List[Dict[str, Any]] = field(default_factory=list)
    note_cursor: int = 0
    turn_reference: Optional[Dict[str, Any]] = None
    reconciliation: Optional[Any] = None
    turn_contract: Optional[Any] = None
    execution_journal: Optional[Any] = None
    qa_telemetry: Optional[Dict[str, Any]] = None
    cached_tokens: Optional[int] = None
    telemetry_breakdown: Dict[str, Any] = field(default_factory=dict)


def observed_sources(step: AgentStep, existing=None) -> List[Dict[str, Any]]:
    """Source cards describe observations, never claim answer verification."""
    sources = list(existing or [])
    result, name = step.tool_result, step.tool_name
    if name == "get_schedule" and isinstance(result, list):
        sources.extend({"type": "schedule", **s} for s in result)
    elif name == "search_documents" and isinstance(result, list):
        for item in result:
            if not any(s.get("path") == item.get("path") for s in sources):
                sources.append({"type": "document", **item, "read": False})
    elif name == "read_document" and isinstance(result, dict) and result.get("found"):
        sources = [s for s in sources if s.get("path") != result.get("path")]
        sources.append({"type": "document", "path": result["path"], "filename": result["filename"],
                        "snippet": result.get("content", "")[:240], "read": True})
    elif name == "search_book_pages" and isinstance(result, dict):
        for item in result.get("items", []):
            if isinstance(item, dict):
                sources.append({"type": "pdf_page", "path": result.get("path"),
                                "filename": result.get("filename"), **item, "read": False})
    elif name == "read_book_page" and isinstance(result, dict) and result.get("found"):
        sources = [s for s in sources if not (s.get("path") == result.get("path")
                   and s.get("page") == result.get("page"))]
        sources.append({"type": "pdf_page", "path": result.get("path"),
                        "filename": result.get("filename"), "page": result.get("page"),
                        "snippet": result.get("content", "")[:600],
                        "full_excerpt": result.get("content", ""), "read": True,
                        "truncated": result.get("truncated", False),
                        "read_chars": len(result.get("content", ""))})
    elif name == "read_web_page" and isinstance(result, dict) and result.get("found"):
        url = result.get("final_url") or result.get("requested_url", "")
        sources = [s for s in sources if s.get("url") != url]
        sources.append({"type": "web_page", "url": url,
                        "title": result.get("title", f"Trang web · {url}"),
                        "snippet": result.get("content", "")[:240],
                        "content_hash": result.get("content_hash", ""),
                        "read": True})

    elif name in ("create_natal_chart", "update_birth_data") and isinstance(result, dict) and result.get("chart"):
        sources = [s for s in sources if s.get("type") != "natal_chart"]
        sources.append({"type": "natal_chart", "chart": result["chart"]})
    elif name == "search_birth_places" and isinstance(result, list):
        sources.append({"type": "birth_places", "candidates": result})
    elif isinstance(result, dict) and result.get("chart"):
        sources = [s for s in sources if s.get("type") != "natal_chart"]
        sources.append({"type": "natal_chart", "chart": result["chart"]})
    elif name and name not in ("update_task_state", "calculate", "locate_room", "get_group_availability",
                              "synthesize_smart_note", "update_note_action_item", "expand_note_section",
                              "request_operation_tools") and result is not None:
        sources.append({"type": name, "result": result})
    return sources


def model_observation(value, registry=None, enable_observation_pack=False, op_name=None):
    """Format large chart or tool observations (Observation Pack) without changing the full recorded source."""
    if isinstance(value, dict) and isinstance(value.get('chart'), dict):
        try:
            from rat.astrology.chart import interpretation_context
            return {**value, 'chart': interpretation_context(value['chart'])}
        except ImportError:
            return value

    if isinstance(value, dict) and "observation" in value and "verification" in value:
        return {**value, "observation": model_observation(value["observation"], registry,
                enable_observation_pack, op_name)}

    if enable_observation_pack and isinstance(value, dict):
        if value.get("artifact_kind") == "structured_note" or value.get("_op_name") == "synthesize_smart_note":
            try:
                from rat.kernel.capabilities.smart_notes import observation_pack_formatter
                return observation_pack_formatter(value)
            except ImportError:
                pass
        target_op_name = op_name or value.get("operation_name") or value.get("_op_name") or value.get("name")
        if not target_op_name and "content" in value and "total_chars" in value and ("path" in value or "filename" in value):
            target_op_name = "read_document"
        if registry is not None and target_op_name:
            op = registry.get_operation(target_op_name)
            if op and getattr(op, "observation_formatter", None):
                return op.observation_formatter(value)
    return value
