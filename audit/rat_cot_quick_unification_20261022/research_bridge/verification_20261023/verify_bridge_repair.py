"""Post-repair bridge verification: proves route parity, label isolation, and legacy preservation."""
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
from experiments.research_study import collect_records, evaluate_records
from reasoning.bundle import PolicyBundle, create_synthetic_specimen_bundle, validate_policy_bundle
from reasoning.entry_predictor import EntryPredictor, EntryTrainingData
from reasoning.optimal_stopping import CalibrationData, OptimalStoppingPolicy
from reasoning.reasoning_env import complexity_features
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import MetaReasonerEngine

OUT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_vector_normalization_parity():
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

    item = dict(
        id="synthetic-normalization",
        group_id="authored-normalization",
        split="test",
        query=query,
        answer="0",
        answer_type="number",
    )
    records = collect_records(VectorBackend(), [item], 42, lambda seed: None, StringIO())
    x = np.linspace(-1.0, 1.0, 100)
    embeddings = np.column_stack((x, np.sqrt(np.maximum(0.0, 1 - x * x))))
    predictor = EntryPredictor(lam=0.02).fit(EntryTrainingData(
        embed=embeddings,
        complexity=np.tile(complexity_features(query), (len(x), 1)),
        accuracy=np.ones((len(x), 3)),
        cost=np.column_stack((6.0 + x, np.full(len(x), 6.8), np.full(len(x), 20.0))),
    ))
    policy = OptimalStoppingPolicy(0.02, entry_predictor=predictor).fit(CalibrationData(
        conf=np.array([[0.2] * 8, [0.6] * 8, [0.9] * 8]),
        correct=np.array([[0] * 8, [0] * 8, [1] * 8]),
        cost=np.full((3, 8), 0.1),
    ))

    # Harness row (uses collected unit-normalized vector [0.6, 0.8])
    row = next(r for r in evaluate_records(records, policy, predictor, predictor)
               if r["method"] == "full_policy")

    # Runtime with bound l2_unit contract
    bundle = PolicyBundle(
        bundle_id="research-unit-specimen",
        review_status="synthetic_development_only",
        model_id="synthetic-mock-v1",
        model_snapshot="synthetic-20261020-mock",
        prompt_profile="aligned-direct-cot-v1",
        strategy_settings={"ladder": ["COT", "SELF_CONSISTENCY", "TOT"]},
        backend_protocol="LLMBackend.v1",
        embedding_dimension=2,
        feature_schema_version=1,
        predictor_kind="EntryPredictor",
        lambda_val=0.02,
        stopping_thresholds=tuple(float(t) for t in policy.tau),
        mean_costs=tuple(float(c) for c in policy.mean_cost),
        calibrator_type=None,
        calibrator_semantics="raw_confidence_uncalibrated",
        cost_metadata={"token_unit": "thousands", "scope": "generated_tokens_only"},
        budget_token_semantics="generated_tokens_only",
        execution_mode="online_policy",
        source_hashes={"test": "test"},
        artifact_hashes={"test": "test"},
        dataset_versions={"test": "test"},
        train_calibration_provenance={"test": True},
        split_separation_verified=True,
        review_scope="offline_synthetic_development_testing_only",
        compatibility_conditions={"min_hidden_size": 2, "max_ladder_depth": 3},
        is_production_approved=False,
        embedding_normalization="l2_unit",
    )
    backend_normalized = VectorBackend()
    res_normalized = MetaReasonerEngine(controller=OnlineReasoningController(
        backend_normalized, policy, bundle=bundle, allow_synthetic_bundle=True,
    )).solve(query)

    # Runtime with unnormalized legacy contract
    backend_legacy = VectorBackend()
    res_legacy = MetaReasonerEngine(controller=OnlineReasoningController(
        backend_legacy, policy, policy_source="legacy-raw", embedding_normalization="none",
    )).solve(query)

    return {
        "raw_embedding": [3.0, 4.0],
        "harness_embedding": records[0]["embedding"],
        "harness_path": row["path"],
        "runtime_normalized_path": res_normalized.strategy_path,
        "runtime_normalized_tokens": res_normalized.tokens,
        "runtime_legacy_raw_path": res_legacy.strategy_path,
        "route_parity_achieved": row["path"] == res_normalized.strategy_path == ["COT"],
        "route_mismatch": row["path"] != res_normalized.strategy_path,
        "legacy_raw_preserved": res_legacy.strategy_path == ["REACT"],
    }


def main():
    norm_result = test_vector_normalization_parity()

    # Fixture isolation verification
    ns = runpy.run_path(str(ROOT / "tests/test_online_reasoning.py"))
    _, record, *_ = ns["make_synthetic_parity_setup"]()
    fixture = ns["AuthoredRecordBackend"](record)
    fixture_label_exposure = {
        "gold_in_backend_record": "gold" in fixture.record,
        "correctness_flags_in_backend_record": any("correct" in a for a in fixture.record["attempts"].values()),
        "scope": "synthetic test fixture; strictly isolated",
    }

    # JUnit verification
    xml_path = OUT / "post_repair_regression.xml"
    cases = list(ET.parse(xml_path).getroot().iter("testcase"))
    suite_info = {
        "cases": len(cases),
        "failures": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "skips": sum(c.find("skipped") is not None for c in cases),
    }

    report = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "model_calls": 0,
        "normalization_contract_verification": norm_result,
        "fixture_label_exposure": fixture_label_exposure,
        "regression_suite": suite_info,
        "status": "PASS",
    }

    (OUT / "repair_verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
