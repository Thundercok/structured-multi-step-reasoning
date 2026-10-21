"""Recompute this saved mock-port audit without collecting or invoking models."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from scripts.audit_rat_context import analyze_request


def analyze(folder):
    captures = folder / "captures.json"
    raw = json.loads(captures.read_text())
    journal = [json.loads(line) for line in (folder / "calls.jsonl").read_text().splitlines()]
    assert journal == raw["calls"]
    assert raw["live_inference_calls"] == 0
    assert raw["source_sha256_start"] == raw["source_sha256_finish"]
    assert all(case["assertions_passed"] for case in raw["cases"])
    phases = {}
    for phase in sorted({call["phase"] for call in journal}):
        calls = [call for call in journal if call["phase"] == phase]
        chars, bytes_ = Counter(), Counter()
        for call in calls:
            assert call["measurements"] == analyze_request(call["request"])
            assert call["prompt_tokens"] is None and call["completion_tokens"] is None
            for component, value in call["measurements"]["components"].items():
                chars[component] += value["chars"]
                bytes_[component] += value["utf8_bytes"]
        total_chars, total_bytes = sum(chars.values()), sum(bytes_.values())
        phases[phase] = {"call_count": len(calls), "serialized_chars_sum": total_chars, "serialized_utf8_bytes_sum": total_bytes,
                         "components_chars_sum": dict(chars), "components_utf8_bytes_sum": dict(bytes_),
                         "tools_share_of_canonical_chars_percent": chars["tools"] / total_chars * 100,
                         "unique_first_system_hash_count": len({call["measurements"]["first_system_sha256"] for call in calls}),
                         "unique_tools_hash_count": len({call["measurements"]["tools_sha256"] for call in calls}),
                         "calls_with_exact_task_state_duplicate": sum(bool(call["measurements"]["exact_task_state_duplicates"]) for call in calls)}
    document_turns = []
    for turn in raw["turns"]:
        if turn["case"] != "C01_main_mock_native":
            continue
        calls = [journal[index - 1] for index in turn["call_indices"]]
        actor = [call for call in calls if call["phase"] == "actor"]
        planner = [call for call in calls if call["phase"] == "planner"]
        planned = json.loads(planner[0]["scripted_response"]["message"]["content"])
        assert planned["outcomes"]
        document_turns.append({"turn_id": turn["turn_id"], "actor_call_indices": [call["call_index"] for call in actor],
                               "actor_first_request_chars": actor[0]["measurements"]["total"]["chars"],
                               "actor_last_request_chars": actor[-1]["measurements"]["total"]["chars"],
                               "actor_last_request_utf8_bytes": actor[-1]["measurements"]["total"]["utf8_bytes"],
                               "planner_request_chars": planner[0]["measurements"]["total"]["chars"],
                               "planner_declared_outcomes": planned["outcomes"],
                               "actor_calls_expose_outcome_id_in_messages": [call["measurements"]["actor_messages_contain_outcome_id_key"] for call in actor],
                               "terminal_completion": turn["reconciliation"]["declared_scope_completion"]})
    last = journal[document_turns[-1]["actor_call_indices"][-1] - 1]
    quote_repetition = next(row for row in last["measurements"]["repeated_text_values"]
                            if row["raw_text_chars"] == 339 and any("source_ref.quote" in path for path in row["locations"]))
    return {"scope": "one_saved_scripted_native_port_audit_not_live_AI_evaluation",
            "captures_sha256": hashlib.sha256(captures.read_bytes()).hexdigest(),
            "journal_sha256": hashlib.sha256((folder / "calls.jsonl").read_bytes()).hexdigest(),
            "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "counts": {"cases": len(raw["cases"]), "runtime_turns": len(raw["turns"]), "port_calls": len(journal)},
            "phases": phases, "document_conversation": document_turns,
            "last_document_actor_source_quote_repetition": quote_repetition,
            "first_to_last_document_actor_request_char_ratio": document_turns[-1]["actor_last_request_chars"] / document_turns[0]["actor_first_request_chars"],
            "validated": {"call_journal_equals_raw_capture": True, "per_call_metrics_recomputed": True, "additive_size_partition": True,
                          "captured_source_stable": True, "unknown_model_metrics_remain_null": True},
            "limits": {"live_inference_calls": 0, "actual_wire_bytes_measured": False, "tokens_measured": False,
                       "speedup_measured": False, "cache_reuse_measured": False, "AI_quality_measured": False,
                       "UI_acceptance_performed": False, "all_six_acceptance_scenarios_executed": False}}


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    result = analyze(folder)
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else folder / "analysis.json"
    with target.open("x") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"counts": result["counts"], "phase_totals": {phase: {key: row[key] for key in ("call_count", "serialized_chars_sum", "serialized_utf8_bytes_sum", "tools_share_of_canonical_chars_percent")} for phase, row in result["phases"].items()},
                      "growth_ratio": result["first_to_last_document_actor_request_char_ratio"], "last_quote_copies": len(result["last_document_actor_source_quote_repetition"]["locations"])}))
