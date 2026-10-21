"""Observe the remaining legacy planner probe using a synthetic two-response client."""
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rat.engine.assistant_runtime import AssistantRuntime
from rat.timetable.compositor import TimetableCompositor


plan = {"goal": "Ghi kết quả", "constraints": [], "success_criteria": ["Có note"],
        "known_facts": [], "completed": [], "remaining": ["Ghi note"], "status": "in_progress",
        "outcomes": [{"outcome_id": "save", "kind": "registered_effect", "effect_type": "record_work_note"}]}
client = MagicMock()
client.chat_with_meta.side_effect = [
    {"message": {"content": json.dumps(plan)}, "prompt_tokens": 1, "completion_tokens": 1},
    {"message": {"content": "Đã ghi"}, "prompt_tokens": 1, "completion_tokens": 1},
]
runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                           use_live_model=True, plan_tasks=True, model_client=client)
response = runtime.run("Ghi lại kết quả")
result = {
    "client_kind": "synthetic MagicMock, no network",
    "scripted_model_responses": 2,
    "attempted_model_calls": client.chat_with_meta.call_count,
    "error": response.error,
    "intent_coverage": response.reconciliation.intent_coverage,
    "unmet_outcomes": response.reconciliation.unmet_outcomes,
    "steps": [{"step_number": s.step_number, "error": s.error,
               "tool_name": s.tool_name, "tool_result": s.tool_result} for s in response.steps],
    "live_model_calls": 0,
}
Path(__file__).with_name("remaining_core_diagnostic.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({k: result[k] for k in ("attempted_model_calls", "error", "intent_coverage")}, ensure_ascii=False))
