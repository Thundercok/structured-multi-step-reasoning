"""Audit model-port context using scripted decisions and native-client mocks only.

No model weights, personal index, Qt window or network call. Sizes describe a
canonical JSON serialization of the runtime/client arguments, not wire bytes,
tokenization, cache savings, online latency or model quality.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = datetime(2026, 10, 14, 9, tzinfo=timezone(timedelta(hours=7)))
FIXTURES = (
    "test_omitted_outcome_model_claims_saved_without_tool_execution",
    "test_wrong_source_producer_consumer_calculate_324_save_126_fails",
    "test_cross_execution_receipt_cannot_satisfy_new_mutation",
    "test_contract_freeze_prevents_downgrade_or_obligation_deletion",
    "test_pending_input_reconciles_to_needs_input_and_unresolved",
    "test_cancel_after_calculate_commit_preserves_artifact_and_resumes_in_new_exec",
    "test_cancel_during_waiting_probe_has_zero_artifacts",
    "test_conversational_response_without_tools",
    "test_proposed_note_does_not_satisfy_confirmed_obligation",
    "test_note_created_then_removed_in_same_execution_fails_boundary_check",
    "test_stale_revision_update_is_unmet",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def size(value):
    text = canonical(value)
    return {"chars": len(text), "utf8_bytes": len(text.encode("utf-8"))}


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def category(message):
    content = message.get("content", "")
    if "turn_id" in message:
        return "chat_history"
    if message["role"] == "tool":
        return "tool_observation"
    if "tool_calls" in message:
        return "assistant_tool_calls"
    prefixes = {
        "Runtime context:": "runtime_context",
        "Runtime verification feedback": "verification_feedback",
        "Session work notes": "active_notes",
        "Prior replaced note versions": "historical_notes",
        "Previous model-authored task state": "task_proposal",
        "Previously retrieved source metadata": "previous_sources",
        "Prior turn references": "turn_references",
        "Current result references": "artifact_references",
    }
    for prefix, label in prefixes.items():
        if content.startswith(prefix):
            return label
    if content.startswith('{"observation":'):
        return "trajectory_observation"
    if message["role"] == "system":
        return "system_instruction"
    if message["role"] == "assistant":
        return "assistant_candidate"
    return "query_or_planner_payload"


def structured_content(message):
    text = message.get("content", "")
    if category(message) in {"active_notes", "historical_notes", "task_proposal", "previous_sources", "turn_references", "artifact_references", "verification_feedback"}:
        indices = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        text = text[min(indices):] if indices else ""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def text_leaves(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from text_leaves(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from text_leaves(item, f"{path}[{index}]")
    elif isinstance(value, str) and len(value) >= 40:
        yield value, path


def analyze_request(request):
    """Additive serialized-size accounting plus exact repeated data locations."""
    groups = defaultdict(lambda: {"chars": 0, "utf8_bytes": 0})
    task_states, leaves = [], defaultdict(list)
    messages = request["messages"]
    for index, message in enumerate(messages):
        label = category(message)
        serialized = size(message)
        for unit in serialized:
            groups[label][unit] += serialized[unit]
        structured = structured_content(message)
        if label == "task_proposal":
            task_states.append((f"messages[{index}].task_proposal", structured))
        if label == "trajectory_observation" and isinstance(structured, dict):
            observation = structured.get("observation") or {}
            if isinstance(observation, dict) and "task_state" in observation:
                task_states.append((f"messages[{index}].observation.task_state", observation["task_state"]))
        if structured is not None:
            for value, path in text_leaves(structured, f"messages[{index}].{label}"):
                leaves[value].append(path)
    # Field values and JSON punctuation/key overhead partition the whole request.
    components = dict(groups)
    for key, value in request.items():
        if key != "messages":
            components[key] = size(value)
    total = size(request)
    components["serialization_overhead"] = {
        unit: total[unit] - sum(item[unit] for item in components.values()) for unit in total
    }
    assert all(value >= 0 for value in components["serialization_overhead"].values())
    assert all(sum(item[unit] for item in components.values()) == total[unit] for unit in total)
    repeated_states = []
    for index, (path, state) in enumerate(task_states):
        earlier = next((previous for previous, obj in task_states[:index] if obj == state), None)
        if earlier:
            repeated_states.append({"first_path": earlier, "repeated_path": path, "state_size": size(state), "authority": "model_proposed_not_execution_proof"})
    repeated_text = [{"sha256": hashlib.sha256(value.encode()).hexdigest(), "raw_text_chars": len(value), "locations": paths,
                      "repeated_raw_text_chars_proxy": len(value) * (len(paths) - 1),
                      "removal_safe_without_provenance_review": False}
                     for value, paths in leaves.items() if len(paths) > 1]
    return {
        "total": total, "components": components, "exact_task_state_duplicates": repeated_states,
        "repeated_text_values": sorted(repeated_text, key=lambda row: row["repeated_raw_text_chars_proxy"], reverse=True),
        "first_system_sha256": digest(messages[0]) if messages and messages[0]["role"] == "system" else None,
        "tools_sha256": digest(request.get("tools", [])), "tools_count": len(request.get("tools", [])),
        "actor_messages_contain_outcome_id_key": any('"outcome_id"' in message.get("content", "") for message in messages),
    }


def decision_message(decision):
    message = {"content": decision.final_answer or ""}
    if decision.tool_name:
        message["tool_calls"] = [{"function": {"name": decision.tool_name, "arguments": decision.tool_args}}]
        message["tool_calls"].extend({"function": call} for call in decision.extra_tool_calls)
    if decision.contract is not None:
        message["contract"] = decision.contract.to_dict() if hasattr(decision.contract, "to_dict") else decision.contract
    elif decision.outcomes is not None:
        message["outcomes"] = decision.outcomes
    return {"message": message, **({"error": decision.error} if decision.error else {})}


class CaptureClient:
    def __init__(self, audit, runtime, provider, phase):
        self.audit, self.runtime, self.provider, self.phase = audit, runtime, provider, phase

    def chat_with_meta(self, messages, tools, **kwargs):
        request = copy.deepcopy({"messages": messages, "tools": tools, **kwargs})
        record = {"call_index": len(self.audit.calls) + 1, "case": self.audit.case, "phase": self.phase,
                  "conversation_id": self.runtime.notebook.conversation_id, "request": request,
                  "registry_names": [operation.name for operation in self.runtime.registry.list_operations()],
                  "measurements": analyze_request(request), "prompt_tokens": None, "completion_tokens": None,
                  "server_durations": None, "cache_reuse": None}
        self.audit.calls.append(record)
        raw = self.provider()
        record["scripted_response"] = copy.deepcopy(raw)
        # Runtime fixture bookkeeping needs numeric counters. They are synthetic
        # placeholders and never enter audit token/cost metrics.
        return {**raw, "request": request, "prompt_tokens": 0, "completion_tokens": 0}


class Audit:
    def __init__(self):
        self.calls, self.turns, self.cases = [], [], []
        self.case = ""

    def native_fixture_call(self, original, runtime, goal, trajectory, **context):
        if runtime.model_callable is None:
            return original(runtime, goal, trajectory, **context)
        callback = runtime.model_callable
        before = runtime.model_callable, runtime.model_client, runtime.use_live_model
        phase = "verified_finish" if context.get("answer_schema") else "actor"
        runtime.model_callable = None
        runtime.model_client = CaptureClient(self, runtime, lambda: decision_message(callback(goal, trajectory)), phase)
        runtime.use_live_model = True
        context.setdefault("now_dt", FIXED_NOW)
        if context["now_dt"] is None:
            context["now_dt"] = FIXED_NOW
        try:
            return original(runtime, goal, trajectory, **context)
        finally:
            runtime.model_callable, runtime.model_client, runtime.use_live_model = before

    def run_fixture_turn(self, original, runtime, goal, *args, **kwargs):
        first = len(self.calls)
        provided = kwargs.get("contract")
        response = original(runtime, goal, *args, **kwargs)
        self.turns.append({"case": self.case, "query": goal, "turn_id": response.turn_id,
                           "execution_id": response.execution_id, "call_indices": [r["call_index"] for r in self.calls[first:]],
                           "contract_supplied_before_execution": provided is not None,
                           "contract": response.turn_contract.to_dict() if response.turn_contract else None,
                           "reconciliation": response.reconciliation.to_dict(), "error": response.error,
                           "notes": runtime.notebook.snapshot(), "historical_notes": runtime.notebook.historical_context()})
        return response


def collect_core_fixtures(audit):
    from tests import test_rat_completion_reconciliation as fixtures
    for name in FIXTURES:
        audit.case = name
        first = len(audit.calls)
        getattr(fixtures, name)()
        audit.cases.append({"case": name, "assertions_passed": True, "call_count": len(audit.calls) - first, "scope": "existing_core_fixture_scripted_through_native_mock_port"})


def collect_document_conversation(audit):
    from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
    from rat.engine.completion import OutcomeSpec, TurnContract
    from rat.timetable.compositor import TimetableCompositor
    from rat.ui.chat_session import ConversationHistory
    pack_root = ROOT / "data/rat_conversation_acceptance_v1"
    pack = json.loads((pack_root / "scenarios.json").read_text())
    scenario = next(row for row in pack["scenarios"] if row["id"] == "C01_main")
    paths = [pack_root / "sources/binary-search-basics.md", pack_root / "sources/binary-search-recursion.md"]
    database = MagicMock()
    database.search_candidates.return_value = [{"file_path": str(path), "file_name": path.name, "file_ext": ".md", "summary": "Tài liệu fixture tự soạn", "rank": 1.0} for path in paths]
    database.get_document_by_path.side_effect = lambda path: {"file_path": path} if Path(path) in paths else None
    runtime = AssistantRuntime(db=database, compositor=TimetableCompositor([]), use_live_model=True, plan_tasks=True)
    history = ConversationHistory("conv-context-audit-document")
    previous_sources, task_state = [], {}
    source = None
    def action(name, **args):
        return ModelDecision("", tool_name=name, tool_args=args)
    for index, turn in enumerate(scenario["turns"], start=1):
        audit.case = "C01_main_mock_native"
        goal = turn["user"]
        proposed_outcomes = [{"outcome_id": f"C01.t{index}.response", "kind": "response"}]
        if index == 1:
            decisions = [action("search_documents", query="binary search"), ModelDecision("", final_answer=turn["reply_example"])]
        elif index == 2:
            decisions = [action("read_document", file_path=str(paths[0])), ModelDecision("", final_answer=turn["reply_example"])]
        elif index in (4, 5):
            proposed_outcomes.insert(0, {"outcome_id": f"C01.t{index}.draft", "kind": "registered_effect", "effect_type": "record_work_note", "allow_proposal": True,
                                                "source_ref": {"artifact_id": source.id, "revision": source.revision, "field": "content"}})
            text = pack["specimen_notes"]["v1" if index == 4 else "v2"]
            args = {"text": text, "source_result": {"artifact_id": source.id, "revision": source.revision, "field": "content"}}
            if index == 5:
                note = runtime.notebook.snapshot()[0]
                args.update(replace_note_id=note["id"], revision=note["revision"])
            decisions = [action("record_work_note", **args), ModelDecision("", final_answer=turn["reply_example"])]
        elif index == 6:
            original = runtime.notebook.historical_context()[0]["text"]
            decisions = [ModelDecision("", final_answer="Bản trước:\n" + original)]
        else:
            decisions = [ModelDecision("", final_answer=turn["reply_example"])]
        plan = {"goal": goal, "constraints": ["Giữ đúng nguồn và lịch sử phiên bản", "Chưa đưa code"], "success_criteria": [], "known_facts": [],
                "completed": [], "remaining": [goal], "status": "in_progress", "outcomes": proposed_outcomes}
        runtime.model_client = CaptureClient(audit, runtime, lambda plan=plan: {"message": {"content": json.dumps(plan, ensure_ascii=False)}}, "planner")
        stream = iter(decisions)
        runtime.model_callable = lambda goal, steps: next(stream)
        prior_messages, prior_refs = history.messages_with_turn_ids(), history.turn_references()
        snap = history.begin_turn(goal)
        response = runtime.run(goal, history=prior_messages, turn_references=prior_refs, previous_sources=previous_sources,
                               task_state=task_state, conversation_id=history.conversation_id, turn_ref=snap.turn_ref,
                               execution_id=snap.execution_id, now_dt=FIXED_NOW, max_steps=6)
        assert response.error is None
        assert response.reconciliation.declared_scope_completion == "satisfied"
        history.complete_turn(snap.turn_id, response.answer, execution_id=response.execution_id,
                              artifact_refs=[{"artifact_id": artifact.id, "revision": artifact.revision} for artifact in response.artifacts],
                              note_ids=[event["note_id"] for event in response.note_events], note_event_ids=[event["event_id"] for event in response.note_events],
                              task_state=response.task_state, reconciliation=response.reconciliation)
        previous_sources.extend(response.sources)
        task_state = response.task_state
        if index == 2:
            source = next(artifact for artifact in response.artifacts if artifact.kind == "document_content")
            assert source.payload["content"] == paths[0].read_text().strip()
        if index == 4:
            assert len(response.note_events) == 1 and not runtime.notebook.snapshot()[0]["confirmed"]
        if index == 5:
            assert runtime.notebook.snapshot()[0]["revision"] == 2
            assert runtime.notebook.historical_context()[0]["text"] == pack["specimen_notes"]["v1"]
        if index in (6, 7):
            assert not response.note_events
            assert runtime.notebook.snapshot()[0]["text"] == pack["specimen_notes"]["v2"]
    audit.cases.append({"case": "C01_main_mock_native", "turn_count": 7, "assertions_passed": True,
                        "scope": "one_authored_acceptance_scenario_scripted_not_AI_or_UI_acceptance"})


def collect():
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.engine.slm import SLMEngine
    audit = Audit()
    original_call, original_run = AssistantRuntime._call_model, AssistantRuntime.run
    def denied(*args, **kwargs):
        raise RuntimeError("context_audit_disallows_network_and_live_inference")
    with ExitStack() as stack:
        stack.enter_context(patch.object(SLMEngine, "chat_with_meta", denied))
        stack.enter_context(patch("urllib.request.urlopen", denied))
        stack.enter_context(patch("socket.create_connection", denied))
        stack.enter_context(patch.object(AssistantRuntime, "_call_model", lambda runtime, *args, **kwargs: audit.native_fixture_call(original_call, runtime, *args, **kwargs)))
        stack.enter_context(patch.object(AssistantRuntime, "run", lambda runtime, *args, **kwargs: audit.run_fixture_turn(original_run, runtime, *args, **kwargs)))
        collect_core_fixtures(audit)
        collect_document_conversation(audit)
    return audit


def source_manifest():
    paths = ["rat/engine/assistant_runtime.py", "rat/engine/completion.py", "rat/engine/persona.py", "rat/engine/task_state.py", "rat/engine/work_notes.py",
             "rat/engine/verification.py", "rat/engine/slm.py", "rat/kernel/registry.py", "rat/kernel/dispatcher.py", "rat/kernel/capabilities/documents.py",
             "rat/ui/chat_session.py", "tests/test_rat_completion_reconciliation.py", "scripts/audit_rat_context.py", "data/rat_conversation_acceptance_v1/scenarios.json"]
    paths.extend(str(path.relative_to(ROOT)) for path in (ROOT / "data/rat_conversation_acceptance_v1/sources").glob("*.md"))
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)  # Gate before fixtures execute.
    start = source_manifest()
    audit = collect()
    finish = source_manifest()
    if start != finish:
        raise RuntimeError("Source changed during context audit")
    raw = {"schema_version": "1.0", "scope": "scripted_native_model_port_context_only", "live_inference_calls": 0,
           "token_and_server_costs_measured": False, "mock_counter_placeholders": 0, "native_ui_acceptance": False,
           "runtime_clock": FIXED_NOW.isoformat(), "source_sha256_start": start, "source_sha256_finish": finish,
           "cases": audit.cases, "turns": audit.turns, "calls": audit.calls}
    (args.output / "captures.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    with (args.output / "calls.jsonl").open("x") as handle:
        for call in audit.calls:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")
    summary = {"case_count": len(audit.cases), "turn_count": len(audit.turns), "mock_port_call_count": len(audit.calls),
               "phases": dict(Counter(call["phase"] for call in audit.calls)),
               "calls_with_exact_task_state_duplicate": sum(bool(call["measurements"]["exact_task_state_duplicates"]) for call in audit.calls),
               "all_fixture_assertions_passed": all(case["assertions_passed"] for case in audit.cases), "live_inference_calls": 0}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
