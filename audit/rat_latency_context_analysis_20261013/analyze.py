"""Offline diagnostic of two historical RAT development conversations.

Reads saved artifacts only. No runtime imports, inference, or network access.
Character sizes use canonical compact JSON, not model tokenization/wire bytes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[2]
RUNS = (
    ("qwen2.5:1.5b", "rat_calculation_live_20261013_1p5"),
    ("qwen3:4b-instruct", "rat_calculation_live_20261013_4b_instruct"),
)
REVIEW = ROOT / "audit/rat_post_r5_handoff_review_20261013/calculation_model_review.json"


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def common_prefix(a, b):
    for index, (left, right) in enumerate(zip(a, b)):
        if left != right:
            return index
    return min(len(a), len(b))


def category(message, query):
    content = message.get("content", "")
    if message["role"] == "system":
        return "system"
    if "turn_id" in message:
        return "chat_history"
    if message["role"] == "tool":
        return "tool_observations"
    if "tool_calls" in message:
        return "assistant_tool_calls"
    prefixes = {
        "Previous model-authored task state": "task_state_context",
        "Prior turn references": "turn_references",
        "Session work notes": "active_notes",
        "Historical work notes": "historical_notes",
        "Replaced work notes": "historical_notes",
        "Prior replaced note versions": "historical_notes",
        "Current result references": "artifact_references",
    }
    for prefix, label in prefixes.items():
        if content.startswith(prefix):
            return label
    if content == query and message["role"] == "user":
        return "current_query"
    if content.startswith('{"observation":'):
        return "runtime_observation"
    return "other"


def analyze_run(model, directory, previous_review):
    raw = ROOT / "audit" / directory / "live_calculation_smoke_plan_tasks_true.json"
    journal = raw.with_name("raw_calls_plan_tasks_true.jsonl")
    start_hashes = {str(p.relative_to(ROOT)): sha(p) for p in (raw, journal)}
    data = json.loads(raw.read_text())
    turns = data["turns"]
    rows = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
    flattened = [call for turn in turns for call in turn["raw_model_calls"]]
    assert rows == flattened, "Journal and per-turn calls differ"
    assert [r["call_index"] for r in rows] == list(range(1, len(rows) + 1))
    assert len(turns) == 7
    assert data["provenance"]["model"] == model
    assert data["provenance"]["plan_tasks"] is True
    assert data["provenance"]["source_changed_during_run"] == []
    assert data["provenance"]["source_sha256"] == data["provenance"]["source_sha256_end"]
    assert data["provenance"]["journal_errors"] == []
    assert sha(raw) == previous_review["artifact_sha256"]
    cancelled = [t for t in turns if t["error"] == "cancelled"]
    normal = [t for t in turns if t["error"] is None]
    assert len(cancelled) == 1 and len(normal) == 6

    call_metrics, turn_metrics = [], []
    for turn in turns:
        for call in turn["raw_model_calls"]:
            request, response = call["request"], call.get("raw_response") or {}
            phase = "planner" if isinstance(request.get("format"), dict) else "actor"
            content_sizes, message_sizes = Counter(), Counter()
            task_objects = []
            for message in request["messages"]:
                label = category(message, turn["query"])
                content = message.get("content", "")
                assert isinstance(content, str)
                content_sizes[label] += len(content)
                message_sizes[label] += len(compact(message))
                if label == "task_state_context":
                    task_objects.append(json.loads(content.split(": ", 1)[1]))
                if label == "runtime_observation":
                    observation = json.loads(content).get("observation", {})
                    if "task_state" in observation:
                        task_objects.append(observation["task_state"])
            if phase == "planner":
                payload = json.loads(request["messages"][-1]["content"])
                planner_fields = {k: len(compact(v)) for k, v in payload.items()}
            else:
                planner_fields = None
            server = {}
            for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
                value = response.get(key)
                assert value is None or value >= 0
                server[key.removesuffix("_duration") + "_seconds"] = (
                    value / 1e9 if value is not None else None
                )
            tool_schemas = request.get("tools")
            call_metrics.append({
                "turn_index": turn["turn_index"], "call_index": call["call_index"],
                "phase": phase, "error": call["error"],
                "client_seconds": call["duration_ms"] / 1000,
                "token_usage_known": call["token_usage_known"],
                "prompt_tokens_reported": call["prompt_tokens"],
                "completion_tokens_reported": call["completion_tokens"],
                "cached_prompt_count_reported": response.get("prompt_eval_cached_count"),
                "server": server,
                "request_compact_json_chars": len(compact(request)),
                "request_compact_json_utf8_bytes": len(compact(request).encode("utf-8")),
                "tools_compact_json_chars": len(compact(tool_schemas)) if tool_schemas else 0,
                "tools_sha256_canonical": hashlib.sha256(compact(tool_schemas).encode()).hexdigest() if tool_schemas else None,
                "tool_names": [tool["function"]["name"] for tool in tool_schemas or []],
                "message_content_chars_by_category": dict(content_sizes),
                "message_object_compact_json_chars_by_category": dict(message_sizes),
                "planner_payload_field_value_compact_json_chars": planner_fields,
                "format_schema_compact_json_chars": len(compact(request["format"])) if phase == "planner" else 0,
                "task_state_representations": len(task_objects),
                "task_state_representations_identical": len(task_objects) > 1 and all(obj == task_objects[0] for obj in task_objects[1:]),
            })
        calls = [c for c in call_metrics if c["turn_index"] == turn["turn_index"]]
        client = sum(c["client_seconds"] for c in calls)
        wall = turn["total_time_ms"] / 1000
        assert wall + 0.001 >= client
        turn_metrics.append({
            "turn_index": turn["turn_index"], "label": turn["label"], "error": turn["error"],
            "wall_seconds": wall, "model_client_seconds": client,
            "wall_less_model_client_seconds": wall - client,
            "planner_client_seconds": sum(c["client_seconds"] for c in calls if c["phase"] == "planner"),
            "actor_calls": sum(c["phase"] == "actor" for c in calls),
            "actor_first_call_prompt_tokens_reported": next((c["prompt_tokens_reported"] for c in calls if c["phase"] == "actor"), None),
            "note_event_count": len(turn["note_events"]),
        })

    known = [c for c in call_metrics if c["token_usage_known"]]
    unknown = [c for c in call_metrics if not c["token_usage_known"]]
    assert len(unknown) == 1 and unknown[0]["turn_index"] == cancelled[0]["turn_index"]
    for call in known:
        assert call["prompt_tokens_reported"] >= 0 and call["completion_tokens_reported"] >= 0
        assert all(value is not None for value in call["server"].values())
    assert all(c["prompt_tokens_reported"] is None and c["completion_tokens_reported"] is None for c in unknown)
    server_sums = {key: sum(c["server"][key] for c in known) for key in known[0]["server"]}
    prompt = sum(c["prompt_tokens_reported"] for c in known)
    completion = sum(c["completion_tokens_reported"] for c in known)
    actor = [c for c in call_metrics if c["phase"] == "actor"]
    planner = [c for c in call_metrics if c["phase"] == "planner"]
    normal_turn_metrics = [t for t in turn_metrics if t["error"] is None]
    systems = [call["request"]["messages"][0]["content"] for call in flattened if not isinstance(call["request"].get("format"), dict)]
    prefix = systems[0]
    for system in systems[1:]:
        prefix = prefix[:common_prefix(prefix, system)]
    categories = Counter()
    for call in actor:
        categories.update(call["message_content_chars_by_category"])
    aggregates = {
        "call_count": len(rows), "known_usage_call_count": len(known), "unknown_usage_call_count": len(unknown),
        "planner_call_count": len(planner), "actor_call_count": len(actor),
        "known_prompt_tokens_partial_sum": prompt, "known_completion_tokens_partial_sum": completion,
        "whole_run_token_total_known": False,
        "prompt_share_of_known_reported_prompt_plus_completion_percent": percent(prompt, prompt + completion),
        "server_seconds_partial_sums": server_sums,
        "prompt_share_of_reported_server_total_percent": percent(server_sums["prompt_eval_seconds"], server_sums["total_seconds"]),
        "prompt_share_of_reported_prompt_plus_generation_percent": percent(server_sums["prompt_eval_seconds"], server_sums["prompt_eval_seconds"] + server_sums["eval_seconds"]),
        "server_total_less_load_prompt_generation_seconds": server_sums["total_seconds"] - sum(server_sums[k] for k in ("load_seconds", "prompt_eval_seconds", "eval_seconds")),
        "normal_turn_wall_seconds_sum": sum(t["wall_seconds"] for t in normal_turn_metrics),
        "normal_turn_wall_seconds_median": statistics.median(t["wall_seconds"] for t in normal_turn_metrics),
        "planner_client_seconds_all_calls": sum(c["client_seconds"] for c in planner),
        "planner_client_seconds_normal_turns": sum(t["planner_client_seconds"] for t in normal_turn_metrics),
        "planner_share_of_normal_turn_wall_percent": percent(sum(t["planner_client_seconds"] for t in normal_turn_metrics), sum(t["wall_seconds"] for t in normal_turn_metrics)),
        "actor_tools_chars_per_call": sorted({c["tools_compact_json_chars"] for c in actor}),
        "actor_tool_schema_unique_hash_count": len({c["tools_sha256_canonical"] for c in actor}),
        "actor_tools_chars_sum": sum(c["tools_compact_json_chars"] for c in actor),
        "actor_tools_share_of_compact_request_chars_percent": percent(sum(c["tools_compact_json_chars"] for c in actor), sum(c["request_compact_json_chars"] for c in actor)),
        "actor_message_content_chars_by_category_sum": dict(categories),
        "actor_system_unique_text_count": len(set(systems)),
        "actor_system_common_prefix_chars": len(prefix),
        "actor_static_contract_chars_before_timestamp": sorted({len(system.split("Current time: ")[0]) for system in systems}),
        "actor_system_has_dynamic_timestamp_every_call": all("Current time: " in system for system in systems) and len(set(systems)) == len(systems),
        "actor_cache_reported_counts": dict(Counter(str(c["cached_prompt_count_reported"]) for c in actor)),
        "actor_calls_with_identical_task_state_in_two_messages": sum(c["task_state_representations_identical"] for c in actor),
        "normal_turns": len(normal), "cancelled_turns": len(cancelled),
    }
    assert prompt == previous_review["known_prompt_tokens_partial_sum"]
    assert completion == previous_review["known_completion_tokens_partial_sum"]
    assert len(rows) == previous_review["model_calls"]
    assert abs(aggregates["planner_client_seconds_all_calls"] - previous_review["planner_client_seconds"]) < 1e-5
    assert abs(server_sums["prompt_eval_seconds"] - previous_review["server_prompt_eval_seconds"]) < 1e-6
    assert abs(server_sums["eval_seconds"] - previous_review["server_generation_seconds"]) < 1e-6
    assert all(sha(ROOT / path) == value for path, value in start_hashes.items())
    return {
        "model": model, "generated_at_utc_of_historical_run": data["generated_at_utc"],
        "input_sha256": start_hashes, "historical_source_sha256": data["provenance"]["source_sha256"],
        "aggregates": aggregates, "turns": turn_metrics, "calls": call_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("analysis.json"))
    args = parser.parse_args()
    review_sha = sha(REVIEW)
    prior = json.loads(REVIEW.read_text())
    results = {model: analyze_run(model, directory, prior["runs"][model]) for model, directory in RUNS}
    assert sha(REVIEW) == review_sha
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "offline_diagnostic_of_two_historical_exposed_development_conversations",
        "live_model_calls_in_this_analysis": 0, "product_source_modified_by_this_analysis": False,
        "not_publication_evidence": True, "not_controlled_model_or_planner_comparison": True,
        "not_measured_current_runtime_performance": True,
        "cost_scope": "reported_prompt_and_completion_counts_partial_sums_not_full_inference_cost",
        "cache_scope": "server_reported_counts_only_not_verified_cache_savings_or_exclusive_bottleneck",
        "character_scope": "canonical_compact_JSON_and_raw_content_lengths_not_model_token_counts_or_actual_wire_size",
        "timing_scope": "measured_historical_turn_and_client_call_wall_times_plus_reported_server_durations_no_replay_latency",
        "prior_review_sha256": review_sha, "analyzer_sha256": sha(Path(__file__)),
        "validation": {
            "journal_matches_per_turn_records": True, "call_indices_contiguous": True,
            "one_unknown_cancel_call_per_run": True, "historical_review_totals_reproduced": True,
            "inputs_unchanged_during_analysis": True,
        },
        "runs": results,
    }
    with args.output.open("x") as handle:
        handle.write(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({model: result["aggregates"] for model, result in results.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
