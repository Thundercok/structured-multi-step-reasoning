"""Experimental learned RAT stopping predictor; independent of the NCKH study.

An unfitted controller passes model decisions through. Fitting requires reviewed
paired continuation outcomes and disjoint train/calibration/test groups. Presence
of a tool call is not a quality label.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ControllerIntervention(str, Enum):
    ALLOW = "ALLOW"
    FORCE_STOP = "FORCE_STOP"


@dataclass
class ControllerDecision:
    intervention: ControllerIntervention
    reason: str
    predicted_gain: Optional[float] = None


@dataclass
class AgentStateTracker:
    has_schedule: bool = False
    target_course: str = ""
    target_date: str = ""
    doc_paths: list[str] = field(default_factory=list)
    doc_contents: list[str] = field(default_factory=list)
    called_actions: set[str] = field(default_factory=set)
    empty_results: int = 0
    total_tokens: int = 0
    step_number: int = 0

    def update_with_tool_result(self, tool_name: str, args: dict, result: Any) -> None:
        self.called_actions.add(f"{tool_name}:{json.dumps(args, sort_keys=True)}")
        if tool_name == "get_schedule" and isinstance(result, list) and result:
            self.has_schedule = True
            self.target_course = result[0].get("course_name", "")
            self.target_date = result[0].get("day", "")
        elif tool_name == "search_documents" and isinstance(result, list):
            self.doc_paths = list(dict.fromkeys(self.doc_paths + [r["path"] for r in result if r.get("path")]))
        elif tool_name == "read_document" and isinstance(result, dict) and result.get("found"):
            if result.get("content"):
                self.doc_contents.append(result["content"])
        if not result or (isinstance(result, dict) and (result.get("error") or result.get("found") is False)):
            self.empty_results += 1


FEATURE_NAMES = (
    "step", "tokens_k", "has_schedule", "documents_found", "documents_read",
    "content_kchars", "empty_results", "repeated_action", "schedule_action",
    "search_action", "read_action",
)


def state_features(state: AgentStateTracker, action: str, args: Optional[dict] = None) -> list[float]:
    signature = f"{action}:{json.dumps(args or {}, sort_keys=True)}"
    return [
        float(state.step_number), state.total_tokens / 1000, float(state.has_schedule),
        float(len(state.doc_paths)), float(len(state.doc_contents)),
        sum(map(len, state.doc_contents)) / 1000, float(state.empty_results),
        float(signature in state.called_actions), float(action == "get_schedule"),
        float(action == "search_documents"), float(action == "read_document"),
    ]


class AgentStoppingController:
    """Ridge prediction of quality gain minus paired inference-token cost difference.

    Calibration chooses a threshold. Test outcomes never enter fitting. This is
    an experimental estimate, not calibrated confidence or a proof of optimality.
    """
    def __init__(self, cost_penalty_lambda: float = 0.05) -> None:
        if not math.isfinite(cost_penalty_lambda) or cost_penalty_lambda < 0:
            raise ValueError("lambda must be finite and nonnegative")
        self.cost_penalty_lambda = cost_penalty_lambda
        self.weights: Optional[list[float]] = None
        self.threshold = 0.0
        self.metadata: dict = {}

    @staticmethod
    def validate_rows(rows: list[dict]) -> None:
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Paired outcomes must be a list of objects")
        groups, ids = {}, set()
        for row in rows:
            split, group = row.get("split"), row.get("group_id")
            if split not in {"train", "calibration", "test"} or not isinstance(group, str) or not group:
                raise ValueError("Each row needs a group_id and train/calibration/test split")
            if group in groups and groups[group] != split:
                raise ValueError("A problem group crosses splits")
            groups[group] = split
            if not isinstance(row.get("id"), str) or not row["id"] or row["id"] in ids:
                raise ValueError("Each paired outcome needs a unique id")
            ids.add(row["id"])
            features = row.get("features", [])
            if not isinstance(features, list) or len(features) != len(FEATURE_NAMES) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in features):
                raise ValueError("Invalid state features")
            if split == "test":
                continue  # Deliberately do not inspect held-out outcome labels.
            if row.get("reviewed") is not True:
                raise ValueError("Training and calibration require reviewed paired outcomes")
            gain, cost = row.get("quality_gain"), row.get("delta_tokens")
            if not isinstance(gain, (int, float)) or isinstance(gain, bool) or not math.isfinite(gain) or not -1 <= gain <= 1:
                raise ValueError("quality_gain must be a reviewed difference in [-1, 1]")
            if not isinstance(cost, int) or isinstance(cost, bool):
                raise ValueError("delta_tokens must be the signed paired inference-token difference")
            if row.get("evidence") == "measured_paired_continuation":
                validate_pair_cost(row)
        if set(groups.values()) != {"train", "calibration", "test"}:
            raise ValueError("All three grouped splits are required")
        for split in ("train", "calibration"):
            if sum(value == split for value in groups.values()) < 2:
                raise ValueError("At least two development groups per fitting split are required")

    def fit(self, rows: list[dict], *, evidence: str = "measured_development") -> "AgentStoppingController":
        import numpy as np
        if evidence not in {"synthetic_smoke", "measured_development"}:
            raise ValueError("Unknown evidence type")
        self.validate_rows(rows)
        train = [r for r in rows if r["split"] == "train"]
        calibration = [r for r in rows if r["split"] == "calibration"]
        if evidence == "measured_development" and any(r.get("evidence") != "measured_paired_continuation" for r in train + calibration):
            raise ValueError("Measured fitting requires paired continuation provenance")
        utility = lambda r: r["quality_gain"] - self.cost_penalty_lambda * r["delta_tokens"] / 1000
        x = np.array([[1.0, *r["features"]] for r in train])
        y = np.array([utility(r) for r in train])
        penalty = np.eye(x.shape[1])
        penalty[0, 0] = 0
        self.weights = np.linalg.solve(x.T @ x + penalty, x.T @ y).tolist()
        scores = [self.predict(r["features"]) for r in calibration]
        candidates = [min(scores) - 1.0, *sorted(set(scores))]
        self.threshold = max(candidates, key=lambda t: (
            sum(utility(r) for r, score in zip(calibration, scores) if score > t), t,
        ))
        fitted_rows = train + calibration
        self.metadata = {
            "evidence": evidence, "feature_names": list(FEATURE_NAMES),
            "token_scope": "paired_delta_reported_prompt_and_completion_tokens",
            "fitted_groups": sorted({r["group_id"] for r in fitted_rows}),
            "development_sha256": hashlib.sha256(json.dumps(fitted_rows, sort_keys=True).encode()).hexdigest(),
            "publication_review_required": True,
        }
        return self

    def predict(self, features: list[float]) -> float:
        if self.weights is None:
            raise ValueError("Controller has not been fitted")
        if len(features) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in features):
            raise ValueError("Invalid prediction features")
        return self.weights[0] + sum(w * v for w, v in zip(self.weights[1:], features))

    def evaluate_step(self, state: AgentStateTracker, proposed_action: Optional[str], proposed_args: Optional[dict], goal: str = "") -> ControllerDecision:
        if self.weights is None or proposed_action not in {"get_schedule", "search_documents", "read_document"}:
            return ControllerDecision(ControllerIntervention.ALLOW, "No learned intervention")
        score = self.predict(state_features(state, proposed_action, proposed_args))
        if score <= self.threshold:
            return ControllerDecision(ControllerIntervention.FORCE_STOP, "Learned continuation value is below the calibrated threshold", score)
        return ControllerDecision(ControllerIntervention.ALLOW, "Learned continuation value exceeds the calibrated threshold", score)

    def to_dict(self) -> dict:
        if self.weights is None:
            raise ValueError("Cannot save an unfitted controller")
        return {"version": 2, "lambda": self.cost_penalty_lambda, "weights": self.weights, "threshold": self.threshold, "metadata": self.metadata}

    @classmethod
    def from_dict(cls, data: dict, *, allow_synthetic: bool = False) -> "AgentStoppingController":
        if data.get("version") != 2 or data.get("metadata", {}).get("feature_names") != list(FEATURE_NAMES):
            raise ValueError("Unsupported controller artifact")
        if data["metadata"].get("evidence") == "synthetic_smoke" and not allow_synthetic:
            raise ValueError("Synthetic controllers cannot be deployed")
        if data["metadata"].get("evidence") not in {"synthetic_smoke", "measured_development"}:
            raise ValueError("Unknown evidence type")
        controller = cls(data["lambda"])
        weights = data["weights"]
        if not isinstance(weights, list) or len(weights) != len(FEATURE_NAMES) + 1 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in weights) or not isinstance(data["threshold"], (int, float)) or not math.isfinite(data["threshold"]):
            raise ValueError("Invalid learned parameters")
        controller.weights = list(weights)
        controller.threshold = data["threshold"]
        controller.metadata = dict(data["metadata"])
        return controller


def validate_pair_cost(row):
    """Both counterfactual branches include selection and final synthesis calls."""
    for key in ('stop_tokens', 'continue_tokens'):
        if not isinstance(row.get(key), int) or isinstance(row[key], bool) or row[key] < 0:
            raise ValueError('Measured pairs need both branch token totals')
    if row['delta_tokens'] != row['continue_tokens'] - row['stop_tokens']:
        raise ValueError('Paired token difference does not match branch totals')
    trace_hash = row.get('pair_trace_sha256', '')
    if not isinstance(trace_hash, str) or len(trace_hash) != 64 or any(c not in '0123456789abcdef' for c in trace_hash):
        raise ValueError('Measured pairs need a raw-trace hash')
