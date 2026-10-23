"""Reproduce the received bridge gap; synthetic only, no model or held-out parsing."""
from __future__ import annotations

import hashlib
from io import StringIO
import json
from pathlib import Path
import runpy
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np
from experiments.research_study import collect_records, evaluate_records, source_hashes
from reasoning.entry_predictor import EntryPredictor, EntryTrainingData
from reasoning.optimal_stopping import CalibrationData, OptimalStoppingPolicy
from reasoning.reasoning_env import complexity_features
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import MetaReasonerEngine

OUT = Path(__file__).resolve().parent
BRIDGE = OUT.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def normalization_case():
    query = "Authored synthetic routing question"

    class VectorBackend:
        hidden_size = 2

        def __init__(self):
            self.calls = []

        def embed(self, query):
            return np.array([3.0, 4.0])

        def run(self, strategy, query, **kwargs):
            self.calls.append(strategy.name)
            return str(int(strategy)), 0.95, 10

    # Only the offline collector sees this authored numeric reference.
    item = dict(id="synthetic-normalization", group_id="authored-normalization",
                split="test", query=query, answer="0", answer_type="number")
    records = collect_records(VectorBackend(), [item], 42, lambda seed: None, StringIO())
    x = np.linspace(-1.0, 1.0, 100)
    # Unit-length training embeddings, as produced by the real collector.
    embeddings = np.column_stack((x, np.sqrt(1 - x * x)))
    predictor = EntryPredictor(lam=0.02).fit(EntryTrainingData(
        embed=embeddings,
        complexity=np.tile(complexity_features(query), (len(x), 1)),
        accuracy=np.ones((len(x), 3)),
        cost=np.column_stack((6 + x, np.full(len(x), 6.8), np.full(len(x), 20.0))),
    ))
    policy = OptimalStoppingPolicy(0.02, entry_predictor=predictor).fit(CalibrationData(
        conf=np.array([[0.2] * 8, [0.6] * 8, [0.9] * 8]),
        correct=np.array([[0] * 8, [0] * 8, [1] * 8]), cost=np.full((3, 8), 0.1),
    ))
    row = next(r for r in evaluate_records(records, policy, predictor, predictor)
               if r["method"] == "full_policy")
    backend = VectorBackend()
    result = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, policy, policy_source="synthetic-review",
    )).solve(query)
    return {
        "evidence": "synthetic software counterexample", "model_calls": 0,
        "raw_embedding": [3.0, 4.0], "harness_embedding": records[0]["embedding"],
        "harness_path": row["path"], "runtime_path": result.strategy_path,
        "harness_tokens": row["tokens"], "runtime_tokens": result.tokens,
        "synthetic_fitting_rows": len(x), "training_embeddings_unit_normalized": True,
        "route_mismatch": row["path"] != result.strategy_path,
    }


def main():
    current_sources = source_hashes()
    source_files = ["tests/test_online_reasoning.py", "docs/research_protocol.md",
                    "reasoning/runtime.py", "reasoning/bundle.py",
                    "experiments/research_study.py", "qwen_mlx_backend.py"]
    snapshot = {name: digest(ROOT / name) for name in source_files}
    outcome = normalization_case()
    write("normalization_counterexample.json", outcome)
    parity = {}
    for name in ("results.json", "summary.json", "policy.json"):
        left, right = BRIDGE / "smoke" / name, BRIDGE / "replay" / name
        parity[name] = {"byte_match": left.read_bytes() == right.read_bytes(),
                        "sha256": digest(left)}
    runs = {}
    for mode in ("smoke", "replay"):
        path = BRIDGE / mode
        manifest = json.loads((path / "manifest.json").read_text())
        runs[mode] = {
            "evidence": manifest["evidence"], "status": manifest["status"],
            "sources_match_current": manifest["source_sha256"] == current_sources,
            "declared_artifact_hashes_match": {
                name: digest(path / name) == expected
                for name, expected in manifest["artifact_sha256"].items()
            },
        }
    candidate = ROOT / "data/procedural_research_v1"
    manifest = json.loads((candidate / "manifest.json").read_text())
    # Hash bytes only; do not parse candidate questions, golds or test rows.
    candidate_hashes = {name: digest(candidate / name) == expected
                        for name, expected in manifest["artifact_sha256"].items()}
    suites = {}
    for name, path in (("received_parity", BRIDGE / "parity_suite.xml"),
                       ("received_research", BRIDGE / "research_study_suite.xml"),
                       ("codex_regression", OUT / "received_regression.xml")):
        cases = list(ET.parse(path).getroot().iter("testcase"))
        suites[name] = {"cases": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                        "errors": sum(c.find("error") is not None for c in cases),
                        "skips": sum(c.find("skipped") is not None for c in cases),
                        "sha256": digest(path)}
    ns = runpy.run_path(str(ROOT / "tests/test_online_reasoning.py"))
    _, record, *_ = ns["make_synthetic_parity_setup"]()
    fixture = ns["AuthoredRecordBackend"](record)
    fixture_label_exposure = {
        "gold_in_backend_record": "gold" in fixture.record,
        "correctness_flags_in_backend_record": any("correct" in a for a in fixture.record["attempts"].values()),
        "scope": "synthetic test fixture; not evidence of real-backend label leakage",
    }
    write("checks.json", {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": snapshot, "script_sha256": digest(Path(__file__)),
        "replay_parity": parity, "run_integrity": runs, "candidate_bytes_match_manifest": candidate_hashes,
        "suites": suites, "normalization_counterexample": outcome,
        "synthetic_fixture_label_exposure": fixture_label_exposure,
        "model_calls": 0, "held_out_content_parsed": False,
        "reviewed_sources_unchanged_during_probe": snapshot == {n: digest(ROOT / n) for n in source_files},
    })
    print(json.dumps({"normalization_counterexample": outcome, "suites": suites,
                      "replay_parity": parity, "candidate_hashes_match": candidate_hashes,
                      "fixture_label_exposure": fixture_label_exposure}, indent=2))


if __name__ == "__main__":
    main()
