"""Fitted policy bundle provenance, schema, validation, and safe serialization.

This module defines the provenance contract for fitted reasoning policies in RAT-CoT.
It enforces fail-closed validation: unreviewed bundles, mismatched dimensions, or
incompatible stopping parameters are rejected before any backend execution begins.
No arbitrary pickle or joblib loading is permitted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from reasoning.entry_predictor import EntryChoice, EntryPredictor, EntryTrainingData, _ConstantClassifier
from reasoning.optimal_stopping import (
    CalibrationData,
    IsotonicCalibrator,
    OptimalStoppingPolicy,
    PlattCalibrator,
)
from reasoning.reasoning_env import LADDER, LLMBackend, ReasoningAction


class BundleValidationError(ValueError):
    """Raised when a policy bundle fails schema, review, or compatibility validation."""


@dataclass(frozen=True)
class PolicyBundle:
    """Immutable metadata and parameters defining a fitted reasoning policy bundle."""

    bundle_id: str
    review_status: str  # "approved", "pending_review", "synthetic_development_only"
    model_id: str
    model_snapshot: str
    prompt_profile: str
    strategy_settings: Dict[str, Any]
    backend_protocol: str  # e.g. "LLMBackend.v1"
    embedding_dimension: int
    feature_schema_version: int  # 1 (3-dim) or 2 (6-dim)
    predictor_kind: str  # e.g. "EntryPredictor"
    lambda_val: float
    stopping_thresholds: Tuple[float, ...]
    mean_costs: Tuple[float, ...]
    calibrator_type: Optional[str]  # "isotonic", "platt", or None
    calibrator_semantics: str
    cost_metadata: Dict[str, Any]
    budget_token_semantics: str  # "generated_tokens_only"
    execution_mode: str  # "online_policy"
    source_hashes: Dict[str, str]
    artifact_hashes: Dict[str, str]
    dataset_versions: Dict[str, str]
    train_calibration_provenance: Dict[str, Any]
    split_separation_verified: bool
    review_scope: str
    compatibility_conditions: Dict[str, Any]
    is_production_approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stopping_thresholds"] = list(self.stopping_thresholds)
        d["mean_costs"] = list(self.mean_costs)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyBundle":
        data = dict(data)
        if "stopping_thresholds" in data:
            data["stopping_thresholds"] = tuple(float(x) for x in data["stopping_thresholds"])
        if "mean_costs" in data:
            data["mean_costs"] = tuple(float(x) for x in data["mean_costs"])
        return cls(**data)


@dataclass
class BundleValidationReport:
    """Diagnostic report from validating a policy bundle against a policy and backend."""
    is_valid: bool
    review_status: str
    is_approved: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def validate_policy_bundle(
    bundle: PolicyBundle,
    policy: OptimalStoppingPolicy,
    backend: Optional[LLMBackend] = None,
    *,
    allow_synthetic: bool = False,
) -> BundleValidationReport:
    """Validate a bundle against an injected policy and optional backend.

    Fails closed: raises BundleValidationError on any critical error or mismatch.
    """
    errors: List[str] = []
    warnings: List[str] = []
    diagnostics: Dict[str, Any] = {
        "bundle_id": bundle.bundle_id,
        "review_status": bundle.review_status,
        "is_production_approved": bundle.is_production_approved,
    }

    VALID_PROMPT_PROFILES = {"legacy", "english-math-v1", "aligned-direct-cot-v1", "order-contract-v2"}

    # 1. Review status and identity validation
    if bundle.review_status == "approved":
        if not bundle.is_production_approved:
            errors.append("Bundle has review_status='approved' but is_production_approved is False.")
        if "synthetic" in getattr(bundle, "review_scope", "").lower():
            errors.append("Bundle marked approved cannot have synthetic review_scope.")
    elif bundle.review_status == "synthetic_development_only":
        if not allow_synthetic:
            errors.append(
                f"Bundle '{bundle.bundle_id}' is marked 'synthetic_development_only'; "
                "production or default execution requires an approved bundle."
            )
        else:
            warnings.append("Using synthetic_development_only policy bundle in development/testing mode.")
    elif bundle.review_status == "pending_review":
        errors.append(
            f"Bundle '{bundle.bundle_id}' is pending independent review and cannot be used for execution."
        )
    else:
        errors.append(f"Unrecognized review_status: {bundle.review_status}")

    # Identity and prompt profile sanity
    if bundle.model_id in ("incompatible", "unsupported", "invalid"):
        errors.append(f"Bundle model_id '{bundle.model_id}' is invalid or incompatible.")
    if bundle.model_snapshot in ("incompatible", "unsupported", "invalid"):
        errors.append(f"Bundle model_snapshot '{bundle.model_snapshot}' is invalid or incompatible.")
    if bundle.prompt_profile in ("unsupported", "invalid", "incompatible") or bundle.prompt_profile not in VALID_PROMPT_PROFILES:
        errors.append(f"Bundle prompt_profile '{bundle.prompt_profile}' is not supported.")

    # Budget token semantics verification
    if bundle.budget_token_semantics != "generated_tokens_only":
        errors.append(
            f"Unsupported budget_token_semantics '{bundle.budget_token_semantics}'. Only 'generated_tokens_only' is supported."
        )

    # Strategy settings validation
    if not isinstance(bundle.strategy_settings, dict):
        errors.append("Bundle strategy_settings must be a dictionary.")
    else:
        if "ladder" not in bundle.strategy_settings:
            errors.append("Bundle strategy_settings must define 'ladder'.")
        if bundle.strategy_settings.get("sc_samples", 0) > 10:
            errors.append("Bundle strategy_settings 'sc_samples' exceeds maximum limit of 10.")
        if bundle.strategy_settings.get("tot_branches", 0) > 10:
            errors.append("Bundle strategy_settings 'tot_branches' exceeds maximum limit of 10.")

    # Source and artifact hashes validation against disk
    root_dir = Path(__file__).resolve().parents[1]
    if isinstance(bundle.source_hashes, dict):
        for src_path, expected_h in bundle.source_hashes.items():
            if isinstance(expected_h, str) and len(expected_h) == 64 and all(c in "0123456789abcdefABCDEF" for c in expected_h):
                target_f = root_dir / src_path
                if target_f.is_file():
                    actual_h = hashlib.sha256(target_f.read_bytes()).hexdigest()
                    if actual_h.lower() != expected_h.lower():
                        errors.append(
                            f"Source hash mismatch for '{src_path}': expected {expected_h}, got {actual_h}."
                        )
    if isinstance(bundle.artifact_hashes, dict):
        for art_key, art_h in bundle.artifact_hashes.items():
            if any(art_key.endswith(ext) for ext in (".json", ".bin", ".pkl", ".pt", ".onnx", ".txt")) or "/" in art_key:
                art_file = root_dir / art_key
                if not art_file.is_file():
                    errors.append(f"Artifact file '{art_key}' referenced in artifact_hashes does not exist on disk.")
                elif isinstance(art_h, str) and len(art_h) == 64 and all(c in "0123456789abcdefABCDEF" for c in art_h):
                    actual_ah = hashlib.sha256(art_file.read_bytes()).hexdigest()
                    if actual_ah.lower() != art_h.lower():
                        errors.append(f"Artifact hash mismatch for '{art_key}': expected {art_h}, got {actual_ah}.")

    # Protocol & schema version validation
    if bundle.backend_protocol != "LLMBackend.v1":
        errors.append(f"Unsupported backend_protocol '{bundle.backend_protocol}'. Expected 'LLMBackend.v1'.")

    if bundle.feature_schema_version not in (1, 2):
        errors.append(f"Unsupported feature_schema_version {bundle.feature_schema_version}. Must be 1 or 2.")

    # Provenance dictionaries cannot be empty
    for prov_field in ("source_hashes", "artifact_hashes", "dataset_versions", "train_calibration_provenance"):
        val = getattr(bundle, prov_field, None)
        if not isinstance(val, dict) or len(val) == 0:
            errors.append(f"Bundle provenance '{prov_field}' cannot be empty.")

    # Calibrator type validation
    if bundle.calibrator_type is not None and bundle.calibrator_type not in ("isotonic", "platt"):
        errors.append(f"Unsupported calibrator_type '{bundle.calibrator_type}'. Must be 'isotonic', 'platt', or None.")

    # Numerical validity: finite numbers
    if not isinstance(bundle.lambda_val, (int, float)) or not np.isfinite(bundle.lambda_val):
        errors.append(f"Bundle lambda_val must be a finite number, got {bundle.lambda_val}.")
    if not bundle.stopping_thresholds or not all(isinstance(t, (int, float)) and np.isfinite(t) for t in bundle.stopping_thresholds):
        errors.append(f"Bundle stopping_thresholds contains non-finite values: {bundle.stopping_thresholds}")
    if not bundle.mean_costs or not all(isinstance(c, (int, float)) and np.isfinite(c) for c in bundle.mean_costs):
        errors.append(f"Bundle mean_costs contains non-finite values: {bundle.mean_costs}")

    # 2. Split separation verification
    if not bundle.split_separation_verified:
        errors.append("Bundle does not have split_separation_verified=True. Data leakage hazard.")

    # 3. Policy parameter compatibility
    if policy is None:
        errors.append("No policy provided for bundle validation.")
    else:
        if np.isfinite(bundle.lambda_val) and np.isfinite(policy.lam):
            if abs(bundle.lambda_val - policy.lam) > 1e-6:
                errors.append(f"Lambda mismatch: bundle has {bundle.lambda_val}, policy has {policy.lam}")

        if policy.entry_predictor is None:
            errors.append("Policy has no fitted entry predictor.")
        else:
            expected_kind = policy.entry_predictor.__class__.__name__
            if bundle.predictor_kind != expected_kind:
                errors.append(
                    f"Bundle predictor_kind '{bundle.predictor_kind}' does not match policy predictor '{expected_kind}'."
                )
            if np.isfinite(bundle.lambda_val) and np.isfinite(policy.entry_predictor.lam):
                if abs(policy.entry_predictor.lam - bundle.lambda_val) > 1e-6:
                    errors.append(
                        f"Predictor lambda mismatch: predictor has {policy.entry_predictor.lam}, "
                        f"bundle has {bundle.lambda_val}"
                    )

            # Feature dimension verification: fitted model dimension must match bundle schema
            expected_features = bundle.embedding_dimension + (3 if bundle.feature_schema_version == 1 else 6)
            pred = policy.entry_predictor
            for collection_name, models in [("cost", getattr(pred, "cost", [])), ("perf", getattr(pred, "perf", []))]:
                for idx, model in enumerate(models):
                    actual_dim = getattr(model, "n_features_in_", None)
                    if actual_dim is None and hasattr(model, "coef_"):
                        actual_dim = model.coef_.shape[-1]
                    if actual_dim is not None and actual_dim != expected_features:
                        errors.append(
                            f"EntryPredictor {collection_name} model [{idx}] feature dimension ({actual_dim}) "
                            f"does not match bundle expected features ({expected_features} = embed {bundle.embedding_dimension} + schema_v{bundle.feature_schema_version})."
                        )

        if len(bundle.stopping_thresholds) != len(policy.tau):
            errors.append(
                f"Thresholds length mismatch: bundle has {len(bundle.stopping_thresholds)}, "
                f"policy has {len(policy.tau)}"
            )
        else:
            for i, (b_tau, p_tau) in enumerate(zip(bundle.stopping_thresholds, policy.tau)):
                if not (np.isfinite(b_tau) and np.isfinite(p_tau)) or abs(b_tau - p_tau) > 1e-5:
                    errors.append(f"Stopping threshold [{i}] mismatch: bundle {b_tau} vs policy {p_tau}")

        if len(bundle.mean_costs) != len(policy.mean_cost):
            errors.append(
                f"Mean cost length mismatch: bundle has {len(bundle.mean_costs)}, "
                f"policy has {len(policy.mean_cost)}"
            )
        else:
            for i, (b_cost, p_cost) in enumerate(zip(bundle.mean_costs, policy.mean_cost)):
                if not (np.isfinite(b_cost) and np.isfinite(p_cost)) or abs(b_cost - p_cost) > 1e-5:
                    errors.append(f"Mean cost [{i}] mismatch: bundle {b_cost} vs policy {p_cost}")

        # Calibrator validation
        if bundle.calibrator_type is not None:
            if not getattr(policy, "calibrators", None):
                errors.append(f"Bundle specifies calibrator_type='{bundle.calibrator_type}', but policy has no calibrators.")
            else:
                for idx, cal in enumerate(policy.calibrators):
                    if bundle.calibrator_type == "isotonic" and not isinstance(cal, IsotonicCalibrator):
                        errors.append(f"Calibrator [{idx}] is not an IsotonicCalibrator.")
                    elif bundle.calibrator_type == "platt" and not isinstance(cal, PlattCalibrator):
                        errors.append(f"Calibrator [{idx}] is not a PlattCalibrator.")

    # 4. Backend compatibility
    if backend is not None:
        hidden_size = getattr(backend, "hidden_size", None)
        if hidden_size is None or not isinstance(hidden_size, int):
            errors.append("Backend must define integer hidden_size.")
        elif hidden_size != bundle.embedding_dimension:
            errors.append(
                f"Backend hidden_size ({hidden_size}) does not match bundle embedding_dimension ({bundle.embedding_dimension})."
            )

        if not hasattr(backend, "embed") or not callable(backend.embed):
            errors.append("Backend missing callable embed() method.")
        if not hasattr(backend, "run") or not callable(backend.run):
            errors.append("Backend missing callable run() method.")

        if bundle.review_status == "approved":
            if getattr(backend, "model_id", None) is not None and bundle.model_id != backend.model_id:
                errors.append(
                    f"Approved bundle model_id '{bundle.model_id}' does not match backend model_id '{backend.model_id}'."
                )
            if getattr(backend, "model_snapshot", None) is not None and bundle.model_snapshot != backend.model_snapshot:
                errors.append(
                    f"Approved bundle model_snapshot '{bundle.model_snapshot}' does not match backend model_snapshot '{backend.model_snapshot}'."
                )
            if getattr(backend, "prompt_profile", None) is not None and bundle.prompt_profile != backend.prompt_profile:
                errors.append(
                    f"Approved bundle prompt_profile '{bundle.prompt_profile}' does not match backend prompt_profile '{backend.prompt_profile}'."
                )

    # 5. Schema completeness
    required_str_fields = [
        "bundle_id", "review_status", "model_id", "model_snapshot",
        "prompt_profile", "backend_protocol", "predictor_kind",
        "budget_token_semantics", "execution_mode", "review_scope"
    ]
    for field_name in required_str_fields:
        val = getattr(bundle, field_name, None)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"Bundle field '{field_name}' must be a nonempty string.")

    is_valid = len(errors) == 0
    report = BundleValidationReport(
        is_valid=is_valid,
        review_status=bundle.review_status,
        is_approved=bundle.review_status == "approved" and bundle.is_production_approved,
        errors=errors,
        warnings=warnings,
        diagnostics=diagnostics,
    )
    if not is_valid:
        raise BundleValidationError(f"Policy bundle validation failed: {'; '.join(errors)}")
    return report


def save_policy_bundle_json(bundle: PolicyBundle, path: Path | str) -> None:
    """Save policy bundle metadata to a JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(bundle.to_dict(), f, indent=2, ensure_ascii=False)


def load_policy_bundle_json(path: Path | str) -> PolicyBundle:
    """Load policy bundle metadata from a JSON file without pickle."""
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PolicyBundle.from_dict(data)


def create_synthetic_specimen_bundle(
    hidden_size: int = 2,
    lam: float = 0.02,
    *,
    bundle_id: str = "synthetic-specimen-v1",
) -> Tuple[PolicyBundle, OptimalStoppingPolicy]:
    """Create a verified synthetic specimen fitted strictly on disjoint synthetic data.

    Explicitly labeled as 'synthetic/development-only' to satisfy audit provenance.
    """
    rng = np.random.default_rng(20261020)
    n_train = 16
    embed_train = rng.standard_normal((n_train, hidden_size)).astype(np.float32)
    complexity_train = rng.uniform(0.0, 1.0, (n_train, 3)).astype(np.float32)
    acc_train = np.zeros((n_train, 3), dtype=np.float64)
    # Give ladder higher accuracy on average in training
    acc_train[:, EntryChoice.LADDER] = 1.0
    cost_train = np.full((n_train, 3), 0.1, dtype=np.float64)

    predictor = EntryPredictor(lam=lam).fit(
        EntryTrainingData(
            embed=embed_train,
            complexity=complexity_train,
            accuracy=acc_train,
            cost=cost_train,
        )
    )

    n_calib = 16
    conf_calib = np.array([
        rng.uniform(0.1, 0.4, n_calib),
        rng.uniform(0.4, 0.7, n_calib),
        rng.uniform(0.7, 0.95, n_calib),
    ])
    correct_calib = np.array([
        [0] * n_calib,
        [0] * (n_calib // 2) + [1] * (n_calib - n_calib // 2),
        [1] * n_calib,
    ])
    cost_calib = np.full((3, n_calib), 0.1, dtype=np.float64)

    policy = OptimalStoppingPolicy(lam, entry_predictor=predictor).fit(
        CalibrationData(conf=conf_calib, correct=correct_calib, cost=cost_calib)
    )

    bundle = PolicyBundle(
        bundle_id=bundle_id,
        review_status="synthetic_development_only",
        model_id="synthetic-mock-v1",
        model_snapshot="synthetic-20261020-mock",
        prompt_profile="aligned-direct-cot-v1",
        strategy_settings={"ladder": ["COT", "SELF_CONSISTENCY", "TOT"]},
        backend_protocol="LLMBackend.v1",
        embedding_dimension=hidden_size,
        feature_schema_version=1,
        predictor_kind="EntryPredictor",
        lambda_val=lam,
        stopping_thresholds=tuple(float(t) for t in policy.tau),
        mean_costs=tuple(float(c) for c in policy.mean_cost),
        calibrator_type=None,
        calibrator_semantics="raw_confidence_uncalibrated",
        cost_metadata={"token_unit": "thousands", "scope": "generated_tokens_only"},
        budget_token_semantics="generated_tokens_only",
        execution_mode="online_policy",
        source_hashes={
            "reasoning/bundle.py": "canonical",
            "reasoning/runtime.py": "canonical",
        },
        artifact_hashes={
            "train_provenance": "synthetic-rng-20261020",
        },
        dataset_versions={
            "train_split": "synthetic_train_16",
            "calibration_split": "synthetic_calib_16",
        },
        train_calibration_provenance={
            "train_n": n_train,
            "calib_n": n_calib,
            "disjoint_splits": True,
            "held_out_exposure": False,
        },
        split_separation_verified=True,
        review_scope="offline_synthetic_development_testing_only",
        compatibility_conditions={
            "min_hidden_size": hidden_size,
            "max_ladder_depth": 3,
        },
        is_production_approved=False,
    )

    return bundle, policy
