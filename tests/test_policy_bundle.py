"""Unit and integration tests for PolicyBundle provenance and validation.

Verifies fail-closed behavior on unreviewed bundles, mismatched dimensions,
inconsistent thresholds, missing fields, and ensures clean JSON serialization.
"""
from dataclasses import replace
import json
from pathlib import Path
import pytest
import numpy as np

from reasoning.bundle import (
    BundleValidationError,
    PolicyBundle,
    create_synthetic_specimen_bundle,
    load_policy_bundle_json,
    save_policy_bundle_json,
    validate_policy_bundle,
)
from reasoning.entry_predictor import EntryChoice, EntryPredictor, EntryTrainingData
from reasoning.optimal_stopping import CalibrationData, OptimalStoppingPolicy
from rat.engine.meta_reasoner import MetaReasonerEngine, build_composed_meta_reasoner


class MockBackend:
    def __init__(self, hidden_size: int = 2):
        self.hidden_size = hidden_size
        self.calls = []

    def embed(self, query: str) -> np.ndarray:
        return np.zeros(self.hidden_size, dtype=np.float32)

    def run(self, strategy, query: str):
        self.calls.append((strategy, query))
        return f"answer-{strategy.name}", 0.8, 42


def test_synthetic_specimen_validates_successfully_in_dev_mode():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    backend = MockBackend(hidden_size=2)
    report = validate_policy_bundle(bundle, policy, backend, allow_synthetic=True)
    assert report.is_valid
    assert report.review_status == "synthetic_development_only"
    assert not report.is_approved
    assert len(report.warnings) > 0


def test_synthetic_specimen_fails_closed_in_production_mode():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="synthetic_development_only"):
        validate_policy_bundle(bundle, policy, backend, allow_synthetic=False)


def test_pending_review_bundle_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    pending_bundle = replace(bundle, review_status="pending_review")
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="pending independent review"):
        validate_policy_bundle(pending_bundle, policy, backend, allow_synthetic=True)


def test_split_separation_unverified_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    leaky_bundle = replace(bundle, split_separation_verified=False)
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="split_separation_verified"):
        validate_policy_bundle(leaky_bundle, policy, backend, allow_synthetic=True)


def test_lambda_mismatch_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    mismatched_bundle = replace(bundle, lambda_val=0.05)
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="Lambda mismatch"):
        validate_policy_bundle(mismatched_bundle, policy, backend, allow_synthetic=True)


def test_stopping_thresholds_mismatch_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    mismatched_bundle = replace(bundle, stopping_thresholds=(0.99, 0.99))
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="Stopping threshold"):
        validate_policy_bundle(mismatched_bundle, policy, backend, allow_synthetic=True)


def test_mean_costs_mismatch_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    mismatched_bundle = replace(bundle, mean_costs=(0.5, 0.5, 0.5))
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="Mean cost"):
        validate_policy_bundle(mismatched_bundle, policy, backend, allow_synthetic=True)


def test_embedding_dimension_mismatch_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    backend_wrong_size = MockBackend(hidden_size=4)
    with pytest.raises(BundleValidationError, match="Backend hidden_size"):
        validate_policy_bundle(bundle, policy, backend_wrong_size, allow_synthetic=True)


def test_missing_required_string_fields_fails_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    empty_field_bundle = replace(bundle, model_id="")
    backend = MockBackend(hidden_size=2)
    with pytest.raises(BundleValidationError, match="model_id.*nonempty"):
        validate_policy_bundle(empty_field_bundle, policy, backend, allow_synthetic=True)


def test_json_safe_serialization_round_trip(tmp_path: Path):
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    target = tmp_path / "specimen_bundle.json"
    save_policy_bundle_json(bundle, target)

    loaded = load_policy_bundle_json(target)
    assert loaded.bundle_id == bundle.bundle_id
    assert loaded.review_status == bundle.review_status
    assert loaded.lambda_val == bundle.lambda_val
    assert loaded.stopping_thresholds == bundle.stopping_thresholds
    assert loaded.mean_costs == bundle.mean_costs
    assert loaded.source_hashes == bundle.source_hashes

    # Verify JSON content is pure text dictionary, parses with json.loads, no pickle
    with open(target, "r", encoding="utf-8") as f:
        raw_text = f.read()
    parsed = json.loads(raw_text)
    assert isinstance(parsed, dict)
    assert not target.read_bytes().startswith(b"\x80")  # no pickle PROTO byte


def test_build_composed_meta_reasoner_success_and_fail_closed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2, lam=0.02)
    backend = MockBackend(hidden_size=2)

    # Missing bundle fails closed
    with pytest.raises(ValueError, match="policy bundle is required"):
        build_composed_meta_reasoner(None, backend, policy)

    # Missing policy fails closed
    with pytest.raises(ValueError, match="fitted policy instance.*required"):
        build_composed_meta_reasoner(bundle, backend, None)

    # Synthetic bundle rejected in production mode
    with pytest.raises(BundleValidationError, match="synthetic_development_only"):
        build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=False)

    # Successful composition in dev mode
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)
    assert isinstance(engine, MetaReasonerEngine)
    assert engine._controller is not None
    assert engine._controller.bundle_id == bundle.bundle_id

    # Execution with composed engine returns online_policy result
    res = engine.solve("tính 120 * 4")
    assert res.execution_mode == "online_policy"
    assert res.bundle_id == bundle.bundle_id
    assert res.status == "completed"
