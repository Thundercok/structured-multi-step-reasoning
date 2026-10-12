"""Read-only QA for the completed, exposed eight-train-item ordering pilot.

Run with python3.12 -B audit/order_dev8_contract_v2_replay_review_20261008.py.
Prints JSON; never collects, loads MLX, fits a policy, or writes run artifacts.
The two offline CPU timing fields are excluded from replay equality only.
"""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "audit/order_certificate_pilot_dev8_contract_v2_real_20261008"
EXPECTED_MANIFEST = "a6666054e254394fd1bc1d5cbbd516215096947f4e0e954b44cc7caa110b63fd"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    if not __debug__:
        raise RuntimeError("Run without -O: validation assertions must remain enabled")
    load = lambda name: json.loads((RUN / name).read_text())
    manifest = load("manifest.json")
    assert sha(RUN / "manifest.json") == EXPECTED_MANIFEST
    assert manifest["status"] == "complete" and manifest["confirmatory"] is False
    assert manifest["evidence"] == "measured_development_pilot"
    assert manifest["model_calls"] is True and manifest["identity"]["mock"] is False
    artifact_hashes = manifest["artifact_sha256"]
    assert set(artifact_hashes) == {
        "dataset.json", "settings.json", "calls.jsonl", "records.json",
        "records.jsonl", "summary.json", "eval_rows.json", "report.md",
    }
    assert len(manifest["identity"]["source_sha256"]) == 8
    before = {name: sha(RUN / name) for name in ("manifest.json", *artifact_hashes)}
    for name, expected in artifact_hashes.items():
        assert before[name] == expected, ("artifact", name)
    for name, expected in manifest["identity"]["source_sha256"].items():
        assert sha(ROOT / name) == expected, ("source", name)
    dataset, settings = load("dataset.json"), load("settings.json")
    assert digest(dataset) == manifest["identity"]["dataset_sha256"]
    assert digest(settings) == manifest["identity"]["settings_sha256"]
    assert len(dataset["items"]) == 8
    assert {item["split"] for item in dataset["items"]} == {"train"}
    assert len({item["id"] for item in dataset["items"]}) == 8
    assert len({item["group_id"] for item in dataset["items"]}) == 8
    assert settings["generation_seeds"] == [42]
    assert settings["thinking_max_tokens"] == 2048
    assert settings["prompt_profile"] == "order-contract-v2"
    head, cache, counts = "0" * 64, {}, Counter()
    for sequence, line in enumerate((RUN / "calls.jsonl").read_text().splitlines(keepends=True)):
        assert line.endswith("\n"), "Torn journal tail"
        entry = json.loads(line)
        body = {key: value for key, value in entry.items() if key != "sha256"}
        assert entry["sha256"] == digest(body)
        assert entry["previous"] == head and entry["sequence"] == sequence
        assert entry["evidence"] == manifest["evidence"]
        key = (entry["kind"], *entry["key"])
        assert key not in cache
        cache[key] = entry["value"]
        counts[entry["kind"]] += 1
        head = entry["sha256"]
    assert counts == {"generation": 56, "execution": 16, "record": 32}
    assert len(cache) == manifest["journal_entries"] == 104
    assert head == manifest["journal_head"]
    records = load("records.json")
    assert records == [json.loads(line) for line in (RUN / "records.jsonl").read_text().splitlines()]
    assert len(records) == 32
    for record in records:
        prefix = (record["id"], record["seed"], record["arm"])
        assert record == cache[("record", *prefix)]
        for index, call in enumerate(record["generations"]):
            assert call == cache[("generation", *prefix, index)]
        if record["execution"] is not None:
            execution = cache[("execution", *prefix, 0)]
            assert execution["generation_sha256"] == digest(record["generations"][0])
            assert execution["result"] == record["execution"]

    # Import only after every saved artifact/source hash has been checked.
    sys.path.insert(0, str(ROOT))
    from experiments.order_certificate_study import (
        METHODS, _final_answer, _selected_answer, evaluate,
        parse_selector_index, validate_records,
    )
    from experiments.research_study import check_answer
    from scripts.verified_pal_order import extract_order_certificate, verify_order_execution

    validate_records(dataset, records, evidence=manifest["evidence"],
                     settings=settings, development_pilot=True)
    saved_rows, summary = load("eval_rows.json"), load("summary.json")
    replay = evaluate(dataset, records, settings=settings)
    ignored = {"offline_verifier_ms", "offline_solver_ms"}
    normalized = lambda row: {key: value for key, value in row.items() if key not in ignored}
    assert len(saved_rows) == len(replay) == 64
    assert [normalized(row) for row in saved_rows] == [normalized(row) for row in replay]
    items = {item["id"]: item for item in dataset["items"]}
    paired = {(row["id"], row["seed"], row["arm"]): row for row in records}
    arm_cost = lambda row, field: sum(call[field] for call in row["generations"])
    metrics, gate_tables = {}, {}
    for method in METHODS:
        rows = [row for row in saved_rows if row["method"] == method]
        assert len(rows) == 8 and len({row["id"] for row in rows}) == 8
        for row in rows:
            invoked = [paired[(row["id"], row["seed"], arm)] for arm in row["path"]]
            for field in ("prompt_tokens", "completion_tokens"):
                assert row[field] == sum(arm_cost(attempt, field) for attempt in invoked)
            assert row["tokens"] == row["prompt_tokens"] + row["completion_tokens"]
            assert row["replayed_strategy_ms"] == sum(arm_cost(attempt, "wall_ms") for attempt in invoked)
        n = len(rows)
        metric = {
            "count": n, "questions": len({row["id"] for row in rows}),
            "correct_count": sum(row["correct"] for row in rows),
            "accuracy": sum(row["correct"] for row in rows) / n,
            "escalation_rate": sum(row["escalated"] for row in rows) / n,
        }
        for field in ("prompt_tokens", "completion_tokens", "tokens", "replayed_strategy_ms",
                      "offline_verifier_ms", "offline_solver_ms"):
            metric["mean_" + field] = sum(row[field] for row in rows) / n
        if method.startswith("w_") or method == "verified_certificate":
            rejected = [row for row in rows if row["escalated"]]
            initial = sum(row["initial_tokens"] for row in rows) / n
            conditional = sum(row["fallback_tokens"] for row in rejected) / len(rejected) if rejected else 0
            metric["cost_identity"] = {
                "mean_initial_tokens": initial,
                "mean_fallback_tokens_given_reject": conditional,
                "reconstructed_mean_tokens": initial + metric["escalation_rate"] * conditional,
            }
            assert metric["cost_identity"]["reconstructed_mean_tokens"] == metric["mean_tokens"]
            metric["rescue_from_initial"] = sum(not row["initial_correct"] and row["correct"] for row in rows)
            metric["harm_from_initial"] = sum(row["initial_correct"] and not row["correct"] for row in rows)
            confusion = {
                "true_accept": sum(not row["escalated"] and row["initial_correct"] for row in rows),
                "false_accept": sum(not row["escalated"] and not row["initial_correct"] for row in rows),
                "true_reject": sum(row["escalated"] and not row["initial_correct"] for row in rows),
                "false_reject": sum(row["escalated"] and row["initial_correct"] for row in rows),
            }
            assert sum(confusion.values()) == n
            gate_tables[method] = confusion
            if method == "verified_certificate":
                metric["gate_confusion_by_answer"] = confusion
        assert metric == summary[method], ("summary mismatch", method)
        metrics[method] = metric

    diagnostics, finish_counts = [], {}
    for arm in ("pal_answer", "pal_certificate", "candidate_selection", "thinking_native"):
        finish_counts[arm] = dict(Counter(call["finish_reason"] for row in records
                                        if row["arm"] == arm for call in row["generations"]))
    for item in dataset["items"]:
        arms = {arm: paired[(item["id"], 42, arm)] for arm in finish_counts}
        certificate = arms["pal_certificate"]
        verification = verify_order_execution(item["query"], certificate["execution"])
        selector = arms["candidate_selection"]["generations"][-1]
        branches = arms["candidate_selection"]["generations"][:3]
        diagnostics.append({
            "id": item["id"], "gold": item["answer"],
            "pal_answer": arms["pal_answer"]["answer"],
            "pal_answer_execution_ok": arms["pal_answer"]["execution"]["ok"],
            "pal_answer_execution_output": arms["pal_answer"]["execution"]["output"],
            "certificate_answer": certificate["answer"],
            "certificate_execution_ok": certificate["execution"]["ok"],
            "certificate_execution_output": certificate["execution"]["output"],
            "certificate_payload_decodes": extract_order_certificate(certificate["execution"]["output"]) is not None,
            "certificate_status": verification.status.value, "certificate_reason": verification.reason,
            "candidate_answers": [_final_answer(call["output"]) for call in branches],
            "candidate_last_lines": [call["output"].rstrip().splitlines()[-1] if call["output"].strip() else "" for call in branches],
            "candidate_finishes": [call["finish_reason"] for call in branches],
            "candidate_correct": [bool(call["finish_reason"] != "length" and check_answer(_final_answer(call["output"]), item)) for call in branches],
            "selector_output": selector["output"], "selector_index": parse_selector_index(selector["output"]),
            "selector_finish": selector["finish_reason"],
            "selected_answer": arms["candidate_selection"]["answer"],
            "native_answer": _selected_answer(arms["thinking_native"])[0],
            "native_finish": arms["thinking_native"]["generations"][0]["finish_reason"],
            "native_answer_marker_seen": "Answer:" in arms["thinking_native"]["generations"][0]["output"],
            "native_reasoning_closed": "</think>" in arms["thinking_native"]["generations"][0]["output"],
        })
    collection = {field: sum(call[field] for row in records for call in row["generations"])
                  for field in ("prompt_tokens", "completion_tokens", "wall_ms")}
    collection["tokens"] = collection["prompt_tokens"] + collection["completion_tokens"]
    candidate_records = [row for row in records if row["arm"] == "candidate_selection"]
    branch_calls = [call for row in candidate_records for call in row["generations"][:3]]
    format_counts = {
        "selectors_valid_single_index": sum(parse_selector_index(row["generations"][-1]["output"]) is not None
                                             and row["generations"][-1]["finish_reason"] != "length"
                                             for row in candidate_records),
        "candidate_branches": len(branch_calls),
        "candidate_branches_length": sum(call["finish_reason"] == "length" for call in branch_calls),
        "stopped_branches_without_contract_answer": sum(call["finish_reason"] != "length" and not _final_answer(call["output"])
                                                        for call in branch_calls),
        "selected_branches_length": sum(row["generations"][parse_selector_index(row["generations"][-1]["output"])]["finish_reason"] == "length"
                                        for row in candidate_records if parse_selector_index(row["generations"][-1]["output"]) is not None),
    }
    w = {row["id"]: row for row in saved_rows if row["method"] == "w_certificate"}
    v = {row["id"]: row for row in saved_rows if row["method"] == "verified_certificate"}
    paired_comparison = {
        "verified_vs_w_rescue": sum(v[key]["correct"] and not w[key]["correct"] for key in w),
        "verified_vs_w_harm": sum(w[key]["correct"] and not v[key]["correct"] for key in w),
        "verified_over_w_certificate_tokens": metrics["verified_certificate"]["mean_tokens"] / metrics["w_certificate"]["mean_tokens"],
        "verified_over_candidate_tokens": metrics["verified_certificate"]["mean_tokens"] / metrics["fixed_candidate_selection"]["mean_tokens"],
    }
    old = ROOT / "audit/order_certificate_pilot_dev2_real_20261008"
    assert sha(old / "manifest.json") == "eb96694154b2c05428777bbcfe2a9e31d02de823fdf7f48cee75a6cea11a6ad2"
    old_manifest = json.loads((old / "manifest.json").read_text())
    for name, expected in old_manifest["artifact_sha256"].items():
        assert sha(old / name) == expected, ("historical artifact", name)
    assert not any(name == "mlx" or name.startswith("mlx.") or name.startswith("mlx_lm") for name in sys.modules)
    assert before == {name: sha(RUN / name) for name in before}
    print(json.dumps({
        "assessment": "share_with_caveats_exploratory_N8_seed42",
        "manifest_sha256": EXPECTED_MANIFEST, "artifact_hashes_valid": 8,
        "source_hashes_valid": 8, "journal_counts": counts,
        "journal_chain_and_record_links_valid": True, "replay_rows_equal": 64,
        "ignored_replay_fields": sorted(ignored), "run_files_unchanged": True,
        "mlx_imported": False, "collection": collection, "metrics": metrics,
        "first_stage_confusion": gate_tables, "finish_counts": finish_counts,
        "format_counts": format_counts, "paired_comparison": paired_comparison,
        "historical_dev2_artifacts_preserved": True,
        "diagnostics": diagnostics,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
