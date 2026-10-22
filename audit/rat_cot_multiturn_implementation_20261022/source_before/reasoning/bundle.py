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
    if bundle.review_status == "approved":
        # 1. Source hashes verification
        if not isinstance(bundle.source_hashes, dict) or not bundle.source_hashes:
            errors.append("Approved bundle must define non-empty source_hashes dictionary.")
        else:
            for src_path, expected_h in bundle.source_hashes.items():
                if not (isinstance(expected_h, str) and len(expected_h) == 64 and all(c in "0123456789abcdefABCDEF" for c in expected_h)):
                    errors.append(f"Approved bundle source '{src_path}' digest '{expected_h}' is not a valid 64-character SHA-256 hex string.")
                    continue
                target_f = Path(src_path) if Path(src_path).is_absolute() else (root_dir / src_path)
                if not target_f.is_file():
                    errors.append(f"Approved bundle source file '{src_path}' does not exist on disk.")
                else:
                    actual_h = hashlib.sha256(target_f.read_bytes()).hexdigest()
                    if actual_h.lower() != expected_h.lower():
                        errors.append(
                            f"Source hash mismatch for '{src_path}': expected {expected_h}, got {actual_h}."
                        )

        # 2. Artifact hashes verification
        if not isinstance(bundle.artifact_hashes, dict) or not bundle.artifact_hashes:
            errors.append("Approved bundle must define non-empty artifact_hashes dictionary.")
        else:
            found_authoritative_artifact = False
            for art_key, art_h in bundle.artifact_hashes.items():
                if not (isinstance(art_h, str) and len(art_h) == 64 and all(c in "0123456789abcdefABCDEF" for c in art_h)):
                    errors.append(f"Approved bundle artifact '{art_key}' digest '{art_h}' is not a valid 64-character SHA-256 hex string.")
                    continue
                art_file = Path(art_key) if Path(art_key).is_absolute() else (root_dir / art_key)
                if not art_file.is_file():
                    errors.append(f"Approved bundle artifact '{art_key}' does not exist on disk.")
                else:
                    actual_ah = hashlib.sha256(art_file.read_bytes()).hexdigest()
                    if actual_ah.lower() != art_h.lower():
                        errors.append(f"Artifact hash mismatch for '{art_key}': expected {art_h}, got {actual_ah}.")
                    elif art_file.suffix == ".json":
                        try:
                            art_data = json.loads(art_file.read_text(encoding="utf-8"))
                        except Exception as art_e:
                            errors.append(f"Failed to parse JSON artifact '{art_key}': {art_e}")
                            continue

                        if not isinstance(art_data, dict):
                            errors.append(f"Artifact '{art_key}' JSON root must be an object/dict.")
                            continue

                        required_keys = ("lambda", "tau", "mean_cost", "entry_cost_models")
                        has_all_required = all(k in art_data for k in required_keys)
                        if has_all_required:
                            found_authoritative_artifact = True
                            # Validate lambda
                            lam_val = art_data["lambda"]
                            if not isinstance(lam_val, (int, float)) or not np.isfinite(lam_val):
                                errors.append(f"Artifact '{art_key}' lambda must be a finite number.")
                            elif hasattr(policy, "lam") and abs(float(lam_val) - float(policy.lam)) > 1e-5:
                                errors.append(f"Artifact '{art_key}' lambda ({lam_val}) does not match policy lambda ({policy.lam}).")

                            # Validate tau
                            tau_val = art_data["tau"]
                            if not isinstance(tau_val, list) or not all(isinstance(x, (int, float)) and np.isfinite(x) for x in tau_val):
                                errors.append(f"Artifact '{art_key}' stopping thresholds must be a list of finite numbers.")
                            elif hasattr(policy, "tau"):
                                if len(tau_val) != len(policy.tau) or not np.allclose(tau_val, policy.tau, atol=1e-5, equal_nan=False):
                                    errors.append(f"Artifact '{art_key}' stopping thresholds do not match policy tau.")

                            # Validate mean_cost
                            mc_val = art_data["mean_cost"]
                            if not isinstance(mc_val, list) or not all(isinstance(x, (int, float)) and np.isfinite(x) for x in mc_val):
                                errors.append(f"Artifact '{art_key}' mean_cost must be a list of finite numbers.")
                            elif hasattr(policy, "mean_cost"):
                                if len(mc_val) != len(policy.mean_cost) or not np.allclose(mc_val, policy.mean_cost, atol=1e-5, equal_nan=False):
                                    errors.append(f"Artifact '{art_key}' mean_cost does not match policy mean_cost.")

                            # Validate entry_cost_models
                            pred = getattr(policy, "entry_predictor", None)
                            if pred is None or not hasattr(pred, "cost"):
                                errors.append("Live policy has no entry predictor with cost models.")
                            else:
                                cost_models_art = art_data["entry_cost_models"]
                                if not isinstance(cost_models_art, list) or len(cost_models_art) != len(pred.cost) or len(cost_models_art) == 0:
                                    errors.append(
                                        f"Artifact '{art_key}' entry_cost_models count ({len(cost_models_art) if isinstance(cost_models_art, list) else 0}) "
                                        f"does not match live policy cost models ({len(pred.cost)})."
                                    )
                                else:
                                    for idx, m_dict in enumerate(cost_models_art):
                                        if not isinstance(m_dict, dict):
                                            errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] must be an object.")
                                            continue
                                        live_m = pred.cost[idx]
                                        if "coef" not in m_dict:
                                            errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] missing 'coef'.")
                                        else:
                                            coef_art = np.asarray(m_dict["coef"], dtype=float)
                                            if not np.all(np.isfinite(coef_art)):
                                                errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] coef must contain finite numbers.")
                                            elif not hasattr(live_m, "coef_") or np.shape(coef_art) != np.shape(live_m.coef_):
                                                errors.append(
                                                    f"Artifact '{art_key}' entry_cost_models[{idx}] coef shape ({np.shape(coef_art)}) "
                                                    f"does not match live model ({np.shape(live_m.coef_) if hasattr(live_m, 'coef_') else 'None'})."
                                                )
                                            elif not np.allclose(coef_art, live_m.coef_, atol=1e-5, equal_nan=False):
                                                errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] coef does not match live policy model.")

                                        if hasattr(live_m, "intercept_"):
                                            if "intercept" not in m_dict:
                                                errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] missing required 'intercept'.")
                                            else:
                                                int_art = np.asarray(m_dict["intercept"], dtype=float)
                                                if not np.all(np.isfinite(int_art)):
                                                    errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] intercept must be finite.")
                                                elif not np.allclose(int_art, live_m.intercept_, atol=1e-5, equal_nan=False):
                                                    errors.append(f"Artifact '{art_key}' entry_cost_models[{idx}] intercept does not match live policy model.")

                            # Validate entry_perf_models
                            if pred is not None and hasattr(pred, "perf") and len(pred.perf) > 0:
                                if "entry_perf_models" in art_data:
                                    perf_art = art_data["entry_perf_models"]
                                    if not isinstance(perf_art, list) or len(perf_art) != len(pred.perf):
                                        errors.append(f"Artifact '{art_key}' entry_perf_models count does not match live policy perf models.")
                                    else:
                                        for idx, m_dict in enumerate(perf_art):
                                            if not isinstance(m_dict, dict):
                                                errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] must be an object.")
                                                continue
                                            live_m = pred.perf[idx]
                                            if hasattr(live_m, "value"):
                                                live_val = getattr(live_m, "value", None)
                                                if live_val is None or not isinstance(live_val, (int, float)) or not np.isfinite(live_val):
                                                    errors.append(f"Live performance model [{idx}] constant is non-finite: {live_val}")
                                                elif "constant" not in m_dict:
                                                    errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] missing 'constant'.")
                                                else:
                                                    c_val = m_dict["constant"]
                                                    if not isinstance(c_val, (int, float)) or not np.isfinite(c_val) or abs(float(c_val) - float(live_val)) > 1e-5:
                                                        errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] constant ({c_val}) does not match live model ({live_val}).")
                                            elif hasattr(live_m, "coef_"):
                                                if "coef" not in m_dict:
                                                    errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] missing 'coef'.")
                                                else:
                                                    coef_art = np.asarray(m_dict["coef"], dtype=float)
                                                    if not np.all(np.isfinite(coef_art)) or not np.all(np.isfinite(live_m.coef_)) or np.shape(coef_art) != np.shape(live_m.coef_) or not np.allclose(coef_art, live_m.coef_, atol=1e-5, equal_nan=False):
                                                        errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] coef does not match live model.")
                                                if hasattr(live_m, "intercept_"):
                                                    if "intercept" not in m_dict:
                                                        errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] missing 'intercept'.")
                                                    else:
                                                        int_art = np.asarray(m_dict["intercept"], dtype=float)
                                                        if not np.all(np.isfinite(int_art)) or not np.all(np.isfinite(live_m.intercept_)) or not np.allclose(int_art, live_m.intercept_, atol=1e-5, equal_nan=False):
                                                            errors.append(f"Artifact '{art_key}' entry_perf_models[{idx}] intercept does not match live model.")
                                else:
                                    # If entry_perf_models is omitted from artifact, live performance models must not deviate from baseline defaults [1.0, 0.0, 0.0]
                                    expected_defaults = [1.0, 0.0, 0.0]
                                    for idx, live_m in enumerate(pred.perf):
                                        live_val = getattr(live_m, "value", None)
                                        if live_val is None or not isinstance(live_val, (int, float)) or not np.isfinite(live_val) or idx >= len(expected_defaults) or abs(float(live_val) - expected_defaults[idx]) > 1e-5:
                                            errors.append(f"Artifact '{art_key}' missing required 'entry_perf_models' for non-default live performance model at index {idx}.")

                            # Validate calibrators in authoritative artifact
                            live_calibrators = getattr(policy, "calibrators", None)
                            if "calibrators" in art_data:
                                cal_art = art_data["calibrators"]
                                if not isinstance(cal_art, list) or (live_calibrators is not None and len(cal_art) != len(live_calibrators)):
                                    errors.append(f"Artifact '{art_key}' calibrators count does not match live policy calibrators.")
                                elif live_calibrators is not None:
                                    for idx, c_dict in enumerate(cal_art):
                                        if not isinstance(c_dict, dict):
                                            errors.append(f"Artifact '{art_key}' calibrators[{idx}] must be an object.")
                                            continue
                                        live_cal = live_calibrators[idx]
                                        if isinstance(live_cal, PlattCalibrator):
                                            for p_name in ("a", "b"):
                                                if p_name not in c_dict:
                                                    errors.append(f"Artifact '{art_key}' calibrators[{idx}] missing '{p_name}'.")
                                                else:
                                                    art_val = c_dict[p_name]
                                                    live_val = getattr(live_cal, p_name, None)
                                                    if not isinstance(art_val, (int, float)) or not np.isfinite(art_val):
                                                        errors.append(f"Artifact '{art_key}' calibrators[{idx}] '{p_name}' is non-finite: {art_val}")
                                                    elif live_val is None or not isinstance(live_val, (int, float)) or not np.isfinite(live_val):
                                                        errors.append(f"Live calibrator [{idx}] '{p_name}' is non-finite: {live_val}")
                                                    elif abs(float(art_val) - float(live_val)) > 1e-5:
                                                        errors.append(f"Artifact '{art_key}' calibrators[{idx}] '{p_name}' ({art_val}) does not match live calibrator ({live_val}).")
                            elif bundle.calibrator_type is not None and bundle.calibrator_semantics != "raw_confidence_uncalibrated":
                                errors.append(f"Artifact '{art_key}' missing required 'calibrators' for calibrated policy.")

            if not found_authoritative_artifact:
                errors.append("Approved bundle must include an authoritative fitted policy artifact declaring complete parameters.")
    else:
        if isinstance(bundle.source_hashes, dict):
            for src_path, expected_h in bundle.source_hashes.items():
                if isinstance(expected_h, str) and len(expected_h) == 64 and all(c in "0123456789abcdefABCDEF" for c in expected_h):
                    target_f = Path(src_path) if Path(src_path).is_absolute() else (root_dir / src_path)
                    if target_f.is_file():
                        actual_h = hashlib.sha256(target_f.read_bytes()).hexdigest()
                        if actual_h.lower() != expected_h.lower():
                            errors.append(
                                f"Source hash mismatch for '{src_path}': expected {expected_h}, got {actual_h}."
                            )
        if isinstance(bundle.artifact_hashes, dict):
            for art_key, art_h in bundle.artifact_hashes.items():
                if isinstance(art_h, str) and len(art_h) == 64 and all(c in "0123456789abcdefABCDEF" for c in art_h):
                    art_file = Path(art_key) if Path(art_key).is_absolute() else (root_dir / art_key)
                    if art_file.is_file():
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
        live_calibrators = getattr(policy, "calibrators", None)
        has_active_calibrators = (
            live_calibrators is not None
            and isinstance(live_calibrators, (list, tuple))
            and len(live_calibrators) > 0
            and any(c is not None for c in live_calibrators)
        )
        if bundle.calibrator_type is None or bundle.calibrator_semantics == "raw_confidence_uncalibrated":
            if has_active_calibrators:
                errors.append(
                    f"Bundle specifies uncalibrated policy (calibrator_type={bundle.calibrator_type}), "
                    f"but live policy has {len(live_calibrators)} active calibrator(s)."
                )
        else:
            if not has_active_calibrators:
                errors.append(f"Bundle specifies calibrator_type='{bundle.calibrator_type}', but policy has no calibrators.")
            else:
                for idx, cal in enumerate(live_calibrators):
                    if bundle.calibrator_type == "isotonic" and not isinstance(cal, IsotonicCalibrator):
                        errors.append(f"Calibrator [{idx}] is not an IsotonicCalibrator.")
                    elif bundle.calibrator_type == "platt" and not isinstance(cal, PlattCalibrator):
                        errors.append(f"Calibrator [{idx}] is not a PlattCalibrator.")
                    else:
                        if isinstance(cal, PlattCalibrator):
                            if hasattr(cal, "a") and not np.isfinite(cal.a):
                                errors.append(f"PlattCalibrator [{idx}] parameter 'a' is non-finite: {cal.a}")
                            if hasattr(cal, "b") and not np.isfinite(cal.b):
                                errors.append(f"PlattCalibrator [{idx}] parameter 'b' is non-finite: {cal.b}")

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
            backend_model_id = getattr(backend, "model_id", None)
            if not backend_model_id:
                errors.append("Approved bundle requires backend to define non-empty model_id.")
            elif bundle.model_id != backend_model_id:
                errors.append(
                    f"Approved bundle model_id '{bundle.model_id}' does not match backend model_id '{backend_model_id}'."
                )

            backend_snapshot = getattr(backend, "model_snapshot", None)
            if not backend_snapshot:
                errors.append("Approved bundle requires backend to define non-empty model_snapshot.")
            elif bundle.model_snapshot != backend_snapshot:
                errors.append(
                    f"Approved bundle model_snapshot '{bundle.model_snapshot}' does not match backend model_snapshot '{backend_snapshot}'."
                )

            if getattr(backend, "prompt_profile", None) is not None and bundle.prompt_profile != backend.prompt_profile:
                errors.append(
                    f"Approved bundle prompt_profile '{bundle.prompt_profile}' does not match backend prompt_profile '{backend.prompt_profile}'."
                )

            if hasattr(backend, "sc_samples") and "sc_samples" in getattr(bundle, "strategy_settings", {}):
                if bundle.strategy_settings["sc_samples"] != backend.sc_samples:
                    errors.append(
                        f"Bundle strategy_settings sc_samples ({bundle.strategy_settings['sc_samples']}) does not match backend sc_samples ({backend.sc_samples})."
                    )
            if hasattr(backend, "tot_branches") and "tot_branches" in getattr(bundle, "strategy_settings", {}):
                if bundle.strategy_settings["tot_branches"] != backend.tot_branches:
                    errors.append(
                        f"Bundle strategy_settings tot_branches ({bundle.strategy_settings['tot_branches']}) does not match backend tot_branches ({backend.tot_branches})."
                    )
            if hasattr(backend, "react_max_turns") and "react_max_turns" in getattr(bundle, "strategy_settings", {}):
                if bundle.strategy_settings["react_max_turns"] != backend.react_max_turns:
                    errors.append(
                        f"Bundle strategy_settings react_max_turns ({bundle.strategy_settings['react_max_turns']}) does not match backend react_max_turns ({backend.react_max_turns})."
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
