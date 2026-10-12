"""Finish auditing a complete measured development run; never collect model output."""
import ast
import json
import math
import runpy
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from experiments.research_pilot import sha256_file, verify_replay
from experiments.research_study import source_hashes
suffixes = {}
for node in ast.parse(Path("qwen_mlx_backend.py").read_text()).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ("DIRECT_SUFFIX", "COT_SUFFIX"):
                suffixes[target.id] = ast.literal_eval(node.value)
DIRECT_SUFFIX, COT_SUFFIX = suffixes["DIRECT_SUFFIX"], suffixes["COT_SUFFIX"]

ROOT = Path("/Users/thundercock2/Documents/Github/multi-step-structured-reasoning")
RUN = ROOT / "audit/development-pilot-measured-20261004-runtimefix"
REPLAY = ROOT / "audit/development-pilot-measured-replay-20261004"
ANALYSIS = ROOT / "audit/development-pilot-measured-review-20261004"
PREFLIGHT = ROOT / "audit/development-pilot-preflight-20261004-runtimefix"
ANALYZER = Path("/private/tmp/development-pilot-495dec2-zm1p4vgl/summarize_development_pilot.py")
COMMIT = "05a93cfd352b56a693ab50050fa44fc212cb4702"

manifest = json.loads((RUN / "manifest.json").read_text())
assert manifest["status"] == "complete", manifest
assert manifest["git_sha"] == COMMIT and manifest["git_status"] == ""
assert manifest["evidence"] == "measured_development_pilot"
assert manifest["model_revision_verified"] is True
assert manifest["model_revision"] == "545dc4251c05440727734bcd94334791f6ab0192"
assert manifest["human_review_status"] == "pending" and manifest["publication_ready"] is False
assert manifest["policy_fitted"] is False and manifest["stage0_reevaluated"] is False
preflight_manifest = json.loads((PREFLIGHT / "manifest.json").read_text())
assert source_hashes() == manifest["source_sha256"] == preflight_manifest["source_sha256"]
assert manifest["input_dataset_sha256"] == preflight_manifest["input_dataset_sha256"]
assert (RUN / "dataset.json").read_bytes() == (PREFLIGHT / "selected_dataset.json").read_bytes()
assert (RUN / "selection.json").read_bytes() == (PREFLIGHT / "selection.json").read_bytes()
assert (RUN / "model_provenance.json").read_bytes() == (PREFLIGHT / "model_provenance.json").read_bytes()
dataset, records, selection = verify_replay(RUN, manifest)
assert len(dataset["items"]) == len(selection["selected_group_ids"]) == 24
assert len(records) == 96
assert records == [json.loads(line) for line in (RUN / "attempts.jsonl").read_text().splitlines()]
items = {item["id"]: item for item in dataset["items"]}
for row in records:
    item = items[row["id"]]
    assert row["split"] in ("train", "calibration") and row["family"] == item["family"]
    assert row["level"] == str(item["level"])
    assert row["answer_format"] == {"answer_type": "expression" if item["family"] == "g24" else item["answer_type"], "decimal_separator": item.get("decimal_separator", ".")}
    assert math.isfinite(row["confidence"]) and 0 <= row["confidence"] <= 1
    assert "embedding" not in row
    generation, = row["trace"]["generations"]
    assert generation["messages"] == [{"role": "user", "content": item["query"] + (DIRECT_SUFFIX if row["strategy"] == "DIRECT" else COT_SUFFIX)}]
    assert generation["temperature"] == 0.0 and generation["enable_thinking"] is False
    assert generation["max_tokens"] == row["token_budget"]
    assert isinstance(generation["prompt_tokens"], int) and generation["prompt_tokens"] > 0
    assert row["trace"]["tools"] == []
assert sum(row["tokens"] for row in records) <= 53760
assert sha256_file(ANALYZER) == "1df0c183f42a504df5f1b8090ce11c6c41a6b264186655a21cfc6706925aa86b"
subprocess.run([sys.executable, "-m", "experiments.research_study", "--replay", str(RUN), "--output", str(REPLAY)], check=True)
for name in ("dataset.json", "selection.json", "records.json", "summary.json", "report.md", "model_provenance.json"):
    assert (RUN / name).read_bytes() == (REPLAY / name).read_bytes(), name
namespace = runpy.run_path(str(ANALYZER))
namespace["main"](["--run", str(RUN), "--output", str(ANALYSIS)])
validation = {
    "kind": "measured_development_pilot_verification",
    "status": "complete", "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "collection_commit": COMMIT, "collection_local_branch": "codex/development-pilot-runtime",
    "collection_manifest_sha256": sha256_file(RUN / "manifest.json"),
    "preflight_manifest_sha256": sha256_file(PREFLIGHT / "manifest.json"),
    "source_sha256": source_hashes(), "analysis_source_sha256": sha256_file(ANALYZER),
    "verifier_source_sha256": sha256_file(Path(__file__)),
    "selected_questions": 24, "original_groups": 24, "completed_evaluations": len(records),
    "successful_single_call_generations": len(records),
    "conditions": dict(Counter(f"{row['strategy']}/{row['token_budget']}" for row in records)),
    "generated_tokens": sum(row["tokens"] for row in records),
    "prompt_tokens": sum(row["trace"]["generations"][0]["prompt_tokens"] for row in records),
    "collection_strategy_ms_sum": sum(row["strategy_ms"] for row in records),
    "held_out_test_evaluations": 0,
    "raw_attempts_equal_records": True,
    "selected_content_and_provenance_equal_review_packet": True,
    "exact_item_strategy_cap_coverage": True,
    "raw_messages_match_query_plus_frozen_suffix": True,
    "tokens_caps_answers_and_gold_scores_reverified": len(records),
    "replay_data_selection_records_summary_report_provenance_byte_identical": True,
    "replay_and_analysis_model_calls": 0, "policy_fitted": False,
    "analysis_manifest_sha256": sha256_file(ANALYSIS / "manifest.json"),
    "replay_manifest_sha256": sha256_file(REPLAY / "manifest.json"),
    "prior_failed_attempt": "audit/development-pilot-measured-20261004",
    "prior_failed_attempt_completed_evaluations": 0,
    "human_review_status": "pending", "procedural_ownership_confirmation": "pending",
    "prompt_language_confound": "DIRECT Vietnamese; CoT English",
    "token_scope": "generated tokens; prompt tokens separately recorded, not full inference costs",
    "timing_scope": "measured per-strategy generation duration; replay retains those values, not online controller latency",
    "stage0_changed": False, "publication_ready": False
}
(ANALYSIS / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(validation, ensure_ascii=False, indent=2))
