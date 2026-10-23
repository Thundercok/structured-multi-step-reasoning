"""Retrospective diagnostics of a saved exposed pilot; no fitting or model calls."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUN = ROOT / "audit/gsm8k-fixed-baseline-measured-20261004"
PINNED_RECORDS = "858af874dc7ba0393e0aef6a4d7ba39fc3fa2a6e67347b1bc09708ed38ddee54"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def failure_marker(row):
    trace = row["trace"]
    return (trace["parse_status"] == "fail"
            or any(g["finish_reason"] == "length" for g in trace["generations"])
            or any(t.get("ok") is False for t in trace["tools"]))


def main():
    manifest = json.loads((RUN / "manifest.json").read_text())
    assert manifest["evidence"] == "measured_development_pilot"
    assert manifest["prompt_profile"] == "english-math-v1" and manifest["seed"] == 42
    assert manifest["human_review_status"] == "pending"
    expected = manifest["artifact_sha256"]
    assert expected["records.json"] == PINNED_RECORDS
    before = {name: digest(RUN / name) for name in expected}
    assert before == expected, "Historical source artifacts do not match their manifest"
    records = json.loads((RUN / "records.json").read_text())
    assert len(records) == 69
    assert {r["split"] for r in records} <= {"train", "calibration"}
    groups, by_id = {}, {}
    for row in records:
        assert row["token_budget"] == 1024
        assert type(row["correct"]) is bool and type(row["tokens"]) is int and row["tokens"] > 0
        assert isinstance(row["confidence"], (int, float)) and 0 <= row["confidence"] <= 1
        assert row["trace"]["parse_status"] in {"marker", "fail"}
        assert row["trace"]["generations"]
        assert all(g["finish_reason"] in {"stop", "length"} for g in row["trace"]["generations"])
        assert row["strategy"] not in by_id.setdefault(row["id"], {})
        by_id[row["id"]][row["strategy"]] = row
        assert groups.setdefault(row["id"], row["group_id"]) == row["group_id"]
    assert len(by_id) == len(set(groups.values())) == 23
    assert all(set(arms) == {"DIRECT", "COT", "PAL"} for arms in by_id.values())
    strategy_summary = {}
    for strategy in ("DIRECT", "COT", "PAL"):
        rows = [r for r in records if r["strategy"] == strategy]
        wrong = [r for r in rows if not r["correct"]]
        strategy_summary[strategy] = {
            "items": len(rows), "correct": len(rows) - len(wrong),
            "generated_tokens": sum(r["tokens"] for r in rows),
            "mean_generated_tokens": sum(r["tokens"] for r in rows) / len(rows),
            "parse_failures": sum(r["trace"]["parse_status"] == "fail" for r in rows),
            "length_stops": sum(any(g["finish_reason"] == "length" for g in r["trace"]["generations"]) for r in rows),
            "tool_failure_items": sum(any(t.get("ok") is False for t in r["trace"]["tools"]) for r in rows),
            "wrong_confidence_min": min(r["confidence"] for r in wrong),
            "wrong_confidence_max": max(r["confidence"] for r in wrong),
            "wrong_above_existing_report_cutoff_0_8": sum(r["confidence"] > 0.8 for r in wrong),
        }
    transitions = Counter()
    item_rows = []
    methods = {name: {"correct": 0, "generated_tokens": 0, "generation_calls": 0}
               for name in ("fixed_COT", "fixed_PAL", "COT_then_PAL_on_failure_marker", "COT_then_PAL_always")}
    for ident, arms in sorted(by_id.items()):
        cot, pal = arms["COT"], arms["PAL"]
        transition = ("both_correct" if cot["correct"] and pal["correct"] else
                      "rescue" if not cot["correct"] and pal["correct"] else
                      "harm" if cot["correct"] and not pal["correct"] else "both_wrong")
        transitions[transition] += 1
        trigger = failure_marker(cot)
        choices = {
            "fixed_COT": [cot], "fixed_PAL": [pal],
            "COT_then_PAL_on_failure_marker": [cot, pal] if trigger else [cot],
            "COT_then_PAL_always": [cot, pal],
        }
        for method, path in choices.items():
            methods[method]["correct"] += path[-1]["correct"]
            methods[method]["generated_tokens"] += sum(r["tokens"] for r in path)
            methods[method]["generation_calls"] += sum(len(r["trace"]["generations"]) for r in path)
        item_rows.append({"id": ident, "group_id": cot["group_id"], "transition": transition,
                          "cot_correct": cot["correct"], "pal_correct": pal["correct"],
                          "cot_failure_marker": trigger, "cot_tokens": cot["tokens"], "pal_tokens": pal["tokens"]})
    for values in methods.values():
        values["items"] = 23
        values["mean_generated_tokens"] = values["generated_tokens"] / 23
    assert sum(transitions.values()) == 23
    assert transitions["rescue"] == 4 and transitions["harm"] == 2
    assert methods["fixed_COT"]["correct"] == 19 and methods["fixed_PAL"]["correct"] == 21
    assert sum(r["cot_failure_marker"] for r in item_rows) == 0
    assert all(p["ok"] is True for r in records if r["strategy"] == "PAL" for p in r["trace"]["tools"])
    assert all(len(r["trace"]["tools"]) == 1 for r in records if r["strategy"] == "PAL")
    assert before == {name: digest(RUN / name) for name in expected}
    save("diagnostics.json", {
        "kind": "retrospective_exposed_development_diagnostic", "new_model_calls": 0,
        "new_policy_fitting": False, "new_scoring": False, "held_out_data_read": False,
        "groups": 23, "observed_seeds": [42], "strategy_summary": strategy_summary,
        "cot_to_pal_transitions": dict(transitions), "conditional_saved_output_replays": methods,
        "cot_failure_markers_triggered": 0, "pal_wrong_with_successful_execution": 2,
        "publication_ready": False, "human_review_status": "pending",
        "cost_scope": "saved generated tokens summed over selected calls; excludes input/tool/router costs",
        "rule_chronology": "failure-marker rule examined after seeing historical reports; exploratory, not preregistered",
    })
    save("items.json", item_rows)
    save("provenance.json", {"run": str(RUN.relative_to(ROOT)), "run_manifest_sha256": digest(RUN / "manifest.json"),
                              "artifact_sha256": before, "analysis_script_sha256": digest(Path(__file__)),
                              "historical_inputs_unchanged": True, "real_model_calls": 0})
    print(json.dumps({"strategy_summary": strategy_summary, "transitions": dict(transitions), "replays": methods}, indent=2))


if __name__ == "__main__":
    main()
