"""Offline checks of the actual classifier/reporting block; no real backend load.

Path counterexamples are labeled synthetic fixtures derived from a captured fake
request. They do not change historical evidence or represent new model calls.
"""
import ast
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def output_root():
    return Path(os.environ.get("RAT_REVIEW_R6_OUTPUT_DIR") or HERE)


def completed(path):
    return [r for line in path.read_text().splitlines()
            if (r := json.loads(line)).get("event") == "request_complete"
            or ("completion_tokens" in r and "event" not in r)]


@pytest.fixture(scope="module")
def source_blocks():
    source = ROOT / "scripts/run_native_performance_session.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    classifier = next(n for n in main.body if isinstance(n, ast.FunctionDef)
                      and n.name == "classify_record_backend")
    first = next(i for i, n in enumerate(main.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "ledger_real_records" for t in n.targets))
    branch = next(i for i in range(first, len(main.body)) if isinstance(main.body[i], ast.If)
                  and isinstance(main.body[i].test, ast.Attribute)
                  and main.body[i].test.attr == "fake_backend")
    classifier_code = compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(classifier)], type_ignores=[])), str(source), "exec")
    summary_code = compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(main.body[first:branch + 1]), type_ignores=[])), str(source), "exec")
    return classifier_code, summary_code


@pytest.mark.parametrize("variant", ["same-document", "real-checkpoint-path", "untagged-control", "explicit-fake-control"])
def test_path_text_cannot_turn_fake_evidence_into_verified_real(variant, source_blocks):
    record = completed(HERE / "legacy_fake_calls.jsonl")[0].copy()
    if variant == "same-document":
        record["document_path"] = completed(HERE / "received_artifacts/calls.jsonl")[0]["document_path"]
    elif variant == "real-checkpoint-path":
        record["model_path"] = "/fixture/mlx-community/Qwen3.5-4B-MLX-4bit"
    elif variant == "explicit-fake-control":
        record.update(backend_type="fake", model_path="/fixture/mlx-community/Qwen3.5-4B-MLX-4bit")
    ns = {}
    exec(source_blocks[0], ns)
    actual = ns["classify_record_backend"](record)
    assert actual in {"fake", "unknown"}, {"fixture_variant": variant, "backend": actual, "record": record}


def test_same_document_fake_guard_replay_remains_unverified():
    root = output_root()
    perf = json.loads((root / "same_document_legacy_fake/native_performance.json").read_text())
    assert "No new requests will be dispatched" in (root / "same_document_legacy_fake.txt").read_text()
    assert perf["historical_ledger_totals"]["real_records"] == 0, perf["scope_classification"]


@pytest.mark.parametrize("mode,expected_real,expected_fake", [
    ("real-history-halt", 0, 0),
    ("new-real-control", 1, 0),
    ("fake-history-control", 0, 0),
])
def test_current_run_counters_and_warm_scope_apply_to_real_mode_too(mode, expected_real, expected_fake, source_blocks):
    # Explicit provenance isolates counting from the separate legacy classifier issue.
    history = [dict(r, backend_type="real", session_id="historical-reviewed-session")
               for r in completed(HERE / "received_artifacts/calls.jsonl")]
    current = []
    if mode == "new-real-control":
        current = [dict(history[0], request_id="synthetic-current-request", session_id="current-fixture-session")]
        history = history + current
    elif mode == "fake-history-control":
        history = [dict(history[0], backend_type="fake")]
    ns = dict(args=SimpleNamespace(fake_backend=mode == "fake-history-control"),
              completed_records=history, current_run_dispatched=current)
    exec(source_blocks[0], ns)
    exec(source_blocks[1], ns)
    assert (ns["real_calls_count"], ns["fake_calls_count"]) == (expected_real, expected_fake), {
        "mode": mode, "new_requests": len(current), "reported_real": ns["real_calls_count"],
        "scope": ns["scope_status"], "warm_records": len(ns["relevant_for_warm"])}
    if not current:
        assert ns["relevant_for_warm"] == [], "Guard process must not borrow historical session warm samples"
