"""Frozen, development-only replay of Run 11 think-on-demand policies.

This module never calls a model.  It accepts only the exact tracked Run 11
trace and its exposed ``gen02_tune`` dataset, revalidates both hashes and row
identity, and makes the reconstructed adaptive policy executable.  The replay
is explicitly post-hoc; it is not a held-out evaluation or a replacement for
the preregistered cascade.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from scripts.gen_tasks import check as check_answer
from scripts.verifiers import (
    VerificationStatus,
    arith_verifier,
    order_verifier,
    verify_order_rationale,
)


ROOT = Path(__file__).resolve().parents[1]
RUN11_TRACE_SHA256 = "3d57df7f4e81c71513a30b46a190c2d848ea020dac78adf88776620b6e67e632"
GEN02_TUNE_SHA256 = "f3bfa9750038ecce95f31dcdd7362082c4d85487d37ff091282442874a12041c"
CASCADE_PREREG_SHA256 = "8b8cd86c19c6b843a80d643211761ea6afa5edf59b801236f105f6ccd60ed3c4"
CASCADE_PREREG = ROOT / "prereg" / "decision_rule_cascade.md"
SCOPE_FAMILIES = ("arith", "order")
FULL_ARMS = ("COT", "SC", "TOT", "REACT", "PAL")
DIRECT_ARM = "DIRECT-v2"
DECISION_LAMBDA = 0.02
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 20261006
ANALYSIS_SOURCE_FILES = (
    "experiments/think_on_demand_replay.py",
    "experiments/research_study.py",
    "scripts/gen_tasks.py",
    "scripts/verifiers.py",
)
METHOD_ORDER = (
    "fixed_direct",
    "fixed_cot",
    "fixed_tot",
    "posthoc_metadata_pal_tot",
    "frozen_policy_v_recorded",
    "frozen_policy_v_checker_rescore",
    "posthoc_think_on_demand_fail_open",
    "posthoc_think_on_demand_fail_closed",
)


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git_value(*arguments: str) -> str | None:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analysis_source_hashes() -> dict[str, str]:
    return {name: sha256_file(ROOT / name) for name in ANALYSIS_SOURCE_FILES}


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Run 11 trace contains a blank line at {line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid Run 11 JSONL at line {line_number}") from error
            if not isinstance(row, dict):
                raise ValueError(f"Run 11 row {line_number} is not an object")
            rows.append(row)
    return rows


def load_frozen_run11(trace_path: Path, dataset_path: Path) -> dict:
    """Validate and load the exact exposed Run 11 artifacts."""
    trace_path = trace_path.resolve()
    dataset_path = dataset_path.resolve()
    trace_hash = sha256_file(trace_path)
    dataset_hash = sha256_file(dataset_path)
    prereg_hash = sha256_file(CASCADE_PREREG)
    if trace_hash != RUN11_TRACE_SHA256:
        raise ValueError(
            "Think-on-demand replay accepts only the frozen Run 11 trace "
            f"({RUN11_TRACE_SHA256}); got {trace_hash}"
        )
    if dataset_hash != GEN02_TUNE_SHA256:
        raise ValueError(
            "Think-on-demand replay accepts only the frozen exposed gen02_tune dataset "
            f"({GEN02_TUNE_SHA256}); got {dataset_hash}"
        )
    if prereg_hash != CASCADE_PREREG_SHA256:
        raise ValueError("The frozen cascade preregistration changed; do not reinterpret Policy V")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    items = dataset.get("items") if isinstance(dataset, dict) else None
    if not isinstance(items, list) or len(items) != 100:
        raise ValueError("Frozen gen02_tune must contain exactly 100 items")
    by_id: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Every frozen dataset item requires a string id")
        if item["id"] in by_id:
            raise ValueError(f"Duplicate dataset id: {item['id']}")
        if item.get("family") not in ("arith", "order", "g24"):
            raise ValueError(f"Unknown family for {item['id']}")
        by_id[item["id"]] = item

    rows = _load_jsonl(trace_path)
    if len(rows) != 571:
        raise ValueError(f"Frozen Run 11 trace must contain 571 rows, got {len(rows)}")
    by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        identifier, arm = row.get("id"), row.get("arm")
        if identifier not in by_id or not isinstance(arm, str):
            raise ValueError("Run 11 row has an unknown id or arm")
        key = (identifier, arm)
        if key in by_key:
            raise ValueError(f"Duplicate Run 11 condition: {key}")
        item = by_id[identifier]
        for field in ("group_id", "family", "level"):
            if row.get(field) != item.get(field):
                raise ValueError(f"Run 11 {field} differs from dataset for {key}")
        if str(row.get("gold")) != str(item.get("answer")):
            raise ValueError(f"Run 11 gold differs from dataset for {key}")
        if type(row.get("correct")) is not bool:
            raise ValueError(f"Run 11 correctness is not boolean for {key}")
        if not isinstance(row.get("raw_output"), str) or not isinstance(row.get("parsed"), str):
            raise ValueError(f"Run 11 output/parsed fields are not strings for {key}")
        for field in ("prompt_tokens", "completion_tokens", "n_tokens"):
            if type(row.get(field)) is not int or row[field] < 0:
                raise ValueError(f"Run 11 {field} is invalid for {key}")
        if row["completion_tokens"] != row["n_tokens"]:
            raise ValueError(f"Run 11 completion token fields disagree for {key}")
        if not isinstance(row.get("wall_ms"), (int, float)) or not math.isfinite(row["wall_ms"]) or row["wall_ms"] < 0:
            raise ValueError(f"Run 11 wall time is invalid for {key}")
        by_key[key] = row

    expected = set()
    for item in items:
        expected.update((item["id"], arm) for arm in FULL_ARMS)
        if item["family"] in SCOPE_FAMILIES:
            expected.add((item["id"], DIRECT_ARM))
    missing, extra = expected - by_key.keys(), by_key.keys() - expected
    if missing or extra:
        raise ValueError(
            f"Run 11 factorial is incomplete: {len(missing)} missing, {len(extra)} unexpected"
        )

    invariant_fields = (
        "model_id", "snapshot_hash", "safetensors_blobs", "enable_thinking",
        "commit", "dirty", "tag", "branch", "eos_token_ids",
    )
    provenance = {}
    for field in invariant_fields:
        encoded = {json.dumps(row.get(field), sort_keys=True) for row in rows}
        if len(encoded) != 1:
            raise ValueError(f"Run 11 provenance field varies across rows: {field}")
        provenance[field] = rows[0].get(field)
    if provenance["dirty"] is not False or provenance["enable_thinking"] is not False:
        raise ValueError("Run 11 must record dirty=false and enable_thinking=false")
    if provenance["model_id"] != "mlx-community/Qwen3-8B-4bit":
        raise ValueError("Unexpected Run 11 model identity")

    checker_disagreements = []
    for key, row in by_key.items():
        rescored = bool(check_answer(by_id[key[0]], row["parsed"]))
        if rescored != row["correct"]:
            checker_disagreements.append({
                "id": key[0], "arm": key[1], "finish_reason": row.get("finish_reason"),
                "recorded_correct": row["correct"], "checker_correct": rescored,
            })
    if any(row["arm"] != "SC" for row in checker_disagreements):
        raise ValueError("Unexpected checker disagreement outside the known SC runner issue")

    return {
        "trace_path": trace_path,
        "dataset_path": dataset_path,
        "trace_sha256": trace_hash,
        "dataset_sha256": dataset_hash,
        "prereg_sha256": prereg_hash,
        "dataset": dataset,
        "items": by_id,
        "rows": rows,
        "by_key": by_key,
        "provenance": provenance,
        "checker_disagreements": checker_disagreements,
    }


def _recorded_cost(records: list[dict]) -> dict[str, float | int]:
    prompt = sum(row["prompt_tokens"] for row in records)
    completion = sum(row["completion_tokens"] for row in records)
    return {
        "recorded_prompt_tokens": prompt,
        "completion_tokens": completion,
        "logged_token_proxy": prompt + completion,
        "recorded_wall_ms_sum": float(sum(row["wall_ms"] for row in records)),
    }


def _legacy_verification(item: dict, cot: dict) -> tuple[bool, str]:
    if item["family"] == "arith":
        return arith_verifier(cot["raw_output"])
    return order_verifier(cot["raw_output"], item["meta"], flag_unextractable=False)


def _outcome_row(
    *, method: str, item: dict, selected: dict, invoked: list[dict], lam: float,
    correctness_basis: str = "recorded_runner", trigger_reasons: list[str] | None = None,
    verification_status: str | None = None, verification_reason: str | None = None,
) -> dict:
    if correctness_basis == "frozen_checker_rescore":
        correct = bool(check_answer(item, selected["parsed"]))
    else:
        correct = selected["correct"]
    cost = _recorded_cost(invoked)
    return {
        "method": method,
        "id": item["id"],
        "group_id": item["group_id"],
        "family": item["family"],
        "level": item["level"],
        "selected_arm": selected["arm"],
        "invoked_arms": [row["arm"] for row in invoked],
        "correct": correct,
        "correctness_basis": correctness_basis,
        **cost,
        "utility": float(correct) - lam * cost["logged_token_proxy"] / 1000,
        "escalated": len(invoked) > 1,
        "trigger_reasons": trigger_reasons or [],
        "verification_status": verification_status,
        "verification_reason": verification_reason,
    }


def replay_rows(source: dict, lam: float = DECISION_LAMBDA) -> list[dict]:
    """Replay frozen and post-hoc policies on arithmetic and ordering only."""
    if not math.isfinite(lam) or lam < 0:
        raise ValueError("lambda must be finite and nonnegative")
    by_key, items = source["by_key"], source["items"]
    results = []
    for item in sorted(
        (entry for entry in items.values() if entry["family"] in SCOPE_FAMILIES),
        key=lambda entry: entry["id"],
    ):
        identifier, family = item["id"], item["family"]
        direct = by_key[(identifier, DIRECT_ARM)]
        cot = by_key[(identifier, "COT")]
        pal = by_key[(identifier, "PAL")]
        sc = by_key[(identifier, "SC")]
        tot = by_key[(identifier, "TOT")]
        for method, selected in (
            ("fixed_direct", direct),
            ("fixed_cot", cot),
            ("fixed_tot", tot),
            ("posthoc_metadata_pal_tot", pal if family == "arith" else tot),
        ):
            results.append(_outcome_row(
                method=method, item=item, selected=selected, invoked=[selected], lam=lam,
                trigger_reasons=[f"dataset_family={family}"] if method == "posthoc_metadata_pal_tot" else [],
            ))

        legacy_flag, legacy_reason = _legacy_verification(item, cot)
        length = cot.get("finish_reason") == "length"
        legacy_triggers = (["legacy_verifier_flag"] if legacy_flag else []) + (["length"] if length else [])
        fallback = pal if family == "arith" else sc
        frozen_selected = fallback if legacy_triggers else cot
        frozen_invoked = [cot, fallback] if legacy_triggers else [cot]
        for method, basis in (
            ("frozen_policy_v_recorded", "recorded_runner"),
            ("frozen_policy_v_checker_rescore", "frozen_checker_rescore"),
        ):
            results.append(_outcome_row(
                method=method, item=item, selected=frozen_selected, invoked=frozen_invoked,
                lam=lam, correctness_basis=basis, trigger_reasons=legacy_triggers,
                verification_status="invalid" if legacy_flag else "legacy_pass",
                verification_reason=legacy_reason,
            ))

        if family == "arith":
            fail_open_selected, fail_open_invoked = pal, [pal]
            fail_open_triggers = ["dataset_family=arith", "direct_to_pal"]
            fail_open_status, fail_open_reason = None, None
            fail_closed_selected, fail_closed_invoked = pal, [pal]
            fail_closed_triggers = list(fail_open_triggers)
            fail_closed_status, fail_closed_reason = None, None
        else:
            fail_open_escalate = bool(legacy_triggers)
            fail_open_selected = tot if fail_open_escalate else cot
            fail_open_invoked = [cot, tot] if fail_open_escalate else [cot]
            fail_open_triggers = list(legacy_triggers)
            fail_open_status = "invalid" if legacy_flag else "legacy_pass"
            fail_open_reason = legacy_reason

            verification = verify_order_rationale(cot["raw_output"], item["meta"])
            fail_closed_escalate = verification.status != VerificationStatus.VALID or length
            fail_closed_selected = tot if fail_closed_escalate else cot
            fail_closed_invoked = [cot, tot] if fail_closed_escalate else [cot]
            fail_closed_triggers = (
                ([f"verifier_{verification.status.value}"] if verification.status != VerificationStatus.VALID else [])
                + (["length"] if length else [])
            )
            fail_closed_status, fail_closed_reason = verification.status.value, verification.reason

        results.append(_outcome_row(
            method="posthoc_think_on_demand_fail_open", item=item,
            selected=fail_open_selected, invoked=fail_open_invoked, lam=lam,
            trigger_reasons=fail_open_triggers, verification_status=fail_open_status,
            verification_reason=fail_open_reason,
        ))
        results.append(_outcome_row(
            method="posthoc_think_on_demand_fail_closed", item=item,
            selected=fail_closed_selected, invoked=fail_closed_invoked, lam=lam,
            trigger_reasons=fail_closed_triggers, verification_status=fail_closed_status,
            verification_reason=fail_closed_reason,
        ))
    return results


def _bootstrap_group_means(
    rows: list[dict], field: str, repetitions: int, seed: int,
) -> list[float]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["group_id"]].append(float(row[field]))
    group_values = np.array(
        [np.mean(grouped[group]) for group in sorted(grouped)], dtype=float,
    )
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(group_values), size=(repetitions, len(group_values)))
    return np.mean(group_values[draws], axis=1).tolist()


def _ci95(values: list[float]) -> list[float]:
    low, high = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
    return [float(low), float(high)]


def summarize(
    results: list[dict], lam: float, repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict:
    if type(repetitions) is not int or repetitions <= 0:
        raise ValueError("bootstrap repetitions must be a positive integer")
    by_method = defaultdict(list)
    for row in results:
        by_method[row["method"]].append(row)
    if set(by_method) != set(METHOD_ORDER):
        raise ValueError("Replay did not produce the expected method set")
    baseline = {row["id"]: row for row in by_method["fixed_cot"]}
    summary = {}
    for method_index, method in enumerate(METHOD_ORDER):
        rows = by_method[method]
        for row in rows:
            cot_correct = baseline[row["id"]]["correct"]
            row["rescue_vs_cot"] = bool(not cot_correct and row["correct"])
            row["harm_vs_cot"] = bool(cot_correct and not row["correct"])
            row["accuracy_delta_vs_cot"] = float(row["correct"]) - float(cot_correct)
            row["utility_delta_vs_cot"] = row["utility"] - baseline[row["id"]]["utility"]
        accuracy_draws = _bootstrap_group_means(
            rows, "correct", repetitions, BOOTSTRAP_SEED + method_index * 17,
        )
        accuracy_delta_draws = _bootstrap_group_means(
            rows, "accuracy_delta_vs_cot", repetitions, BOOTSTRAP_SEED + method_index * 17 + 1,
        )
        utility_delta_draws = _bootstrap_group_means(
            rows, "utility_delta_vs_cot", repetitions, BOOTSTRAP_SEED + method_index * 17 + 2,
        )
        summary[method] = {
            "n": len(rows),
            "correct": sum(row["correct"] for row in rows),
            "accuracy": float(np.mean([row["correct"] for row in rows])),
            "accuracy_group_bootstrap_ci95": _ci95(accuracy_draws),
            "mean_recorded_prompt_tokens": float(np.mean([row["recorded_prompt_tokens"] for row in rows])),
            "mean_completion_tokens": float(np.mean([row["completion_tokens"] for row in rows])),
            "mean_logged_token_proxy": float(np.mean([row["logged_token_proxy"] for row in rows])),
            "mean_utility": float(np.mean([row["utility"] for row in rows])),
            "mean_recorded_wall_ms_sum": float(np.mean([row["recorded_wall_ms_sum"] for row in rows])),
            "escalations": sum(row["escalated"] for row in rows),
            "escalation_rate": float(np.mean([row["escalated"] for row in rows])),
            "rescues_vs_cot": sum(row["rescue_vs_cot"] for row in rows),
            "harms_vs_cot": sum(row["harm_vs_cot"] for row in rows),
            "accuracy_delta_vs_cot": float(np.mean([row["accuracy_delta_vs_cot"] for row in rows])),
            "accuracy_delta_vs_cot_group_bootstrap_ci95": _ci95(accuracy_delta_draws),
            "utility_delta_vs_cot": float(np.mean([row["utility_delta_vs_cot"] for row in rows])),
            "utility_delta_vs_cot_group_bootstrap_ci95": _ci95(utility_delta_draws),
        }
    return {
        "evidence_status": "exposed_development_posthoc_replay_only",
        "decision": "requires_fresh_preregistered_development_replication",
        "scope": {"families": list(SCOPE_FAMILIES), "n": 71, "g24_excluded": 29},
        "lambda": lam,
        "bootstrap": {
            "unit": "group_id", "repetitions": repetitions, "seed": BOOTSTRAP_SEED,
            "interval": "percentile_95",
        },
        "methods": summary,
    }


def render_report(manifest: dict, summary: dict, source: dict) -> str:
    lines = [
        "# Run 11 think-on-demand replay (development only)", "",
        "**Evidence status:** exposed development, post-hoc replay only. This is not a held-out result, a confirmatory run, or evidence that Stage 0 passed.", "",
        "The replay covers 71 arithmetic/ordering items. Game-of-24 is excluded from the reconstructed policy. `CoT` means a prompt-elicited visible rationale with `enable_thinking=false`; it is not hidden chain-of-thought access.", "",
        "| Method | Correct | Accuracy [group-bootstrap 95% CI] | Logged token proxy | Utility | Escalations | Rescue / harm vs CoT |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in METHOD_ORDER:
        row = summary["methods"][method]
        ci = row["accuracy_group_bootstrap_ci95"]
        lines.append(
            f"| `{method}` | {row['correct']}/{row['n']} | {row['accuracy']:.3f} "
            f"[{ci[0]:.3f}, {ci[1]:.3f}] | {row['mean_logged_token_proxy']:.1f} | "
            f"{row['mean_utility']:.3f} | {row['escalations']} | "
            f"{row['rescues_vs_cot']} / {row['harms_vs_cot']} |"
        )
    headline = summary["methods"]["posthoc_think_on_demand_fail_open"]
    closed = summary["methods"]["posthoc_think_on_demand_fail_closed"]
    lines.extend([
        "", "## What the 87.3% number means", "",
        f"The tracked reconstruction reproduces **{headline['correct']}/{headline['n']} = {headline['accuracy']:.3%}**, "
        f"{headline['mean_logged_token_proxy']:.1f} logged tokens/item, utility {headline['mean_utility']:.3f}, "
        f"and {headline['rescues_vs_cot']} rescues with {headline['harms_vs_cot']} harm. It routes arithmetic directly to PAL and routes ordering through CoT, escalating to the legacy `TOT` arm when the legacy verifier flags or CoT hits its cap.", "",
        "That rule was reconstructed after inspecting Run 11. It differs from frozen Policy V, which uses PAL for arithmetic and SC for ordering after a CoT flag. It also uses dataset family labels and canonical structured ordering metadata, so routing/parsing errors are not measured.", "",
        f"The fail-closed tri-state variant counts unextractable ordering rationales as escalation-worthy and obtains **{closed['correct']}/{closed['n']} = {closed['accuracy']:.3%}** with a logged proxy of {closed['mean_logged_token_proxy']:.1f} tokens/item. This is a safety-oriented exploratory replay, not a newly validated policy.", "",
        "## Measurement limitations", "",
        "- The trace was generated in one warm model session, not as 571 independent cold starts.",
        "- SC and the legacy `TOT` arm used nonzero-temperature sampling without a recorded generation seed. Raw replay is deterministic; identical regeneration is not guaranteed.",
        "- `prompt_tokens` is recorded once for SC (five calls) and legacy `TOT` (three candidates plus a selector). Therefore the table's prompt+completion quantity is an **incomplete logged token proxy**, not full inference cost. Selector input tokens cannot be reconstructed from the trace.",
        "- `wall_ms` values are saved arm timings replayed from the historical run. Their sums are not measured online controller latency.",
        f"- Frozen checker rescoring disagrees with {len(source['checker_disagreements'])} SC rows because the runner invalidated the whole SC result when any branch hit length. Both recorded and rescored Policy V variants are shown; neither is confirmatory.",
        "- A symbolic verifier checks consistency of a visible trace. It does not establish causal rationale faithfulness.", "",
        "## Provenance", "",
        f"- Run 11 trace SHA-256: `{manifest['source_trace_sha256']}`",
        f"- Exposed dataset SHA-256: `{manifest['source_dataset_sha256']}`",
        f"- Cascade preregistration SHA-256: `{manifest['cascade_prereg_sha256']}`",
        f"- Model recorded by every row: `{source['provenance']['model_id']}`",
        f"- Historical source commit recorded by every row: `{source['provenance']['commit']}`",
        "", "Next evidence step: freeze a prospective policy and corrected telemetry before collecting a fresh, non-overlapping development replication. Do not promote this replay into a paper claim.",
    ])
    return "\n".join(lines) + "\n"


def write_analysis(
    trace_path: Path,
    dataset_path: Path,
    output: Path,
    lam: float = DECISION_LAMBDA,
    *,
    _bootstrap_repetitions: int = BOOTSTRAP_REPETITIONS,
) -> dict:
    """Write a new, hashed replay directory without modifying source artifacts."""
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    source = load_frozen_run11(trace_path, dataset_path)
    results = replay_rows(source, lam)
    summary = summarize(results, lam, _bootstrap_repetitions)
    manifest = {
        "schema_version": 1,
        "status": "running",
        "mode": "run11_think_on_demand_posthoc_replay",
        "evidence": "exposed_development_posthoc_replay_only",
        "model_calls": False,
        "uses_held_out_data": False,
        "policy_fitted_or_selected_after_outcome_inspection": True,
        "source_trace": str(source["trace_path"]),
        "source_trace_sha256": source["trace_sha256"],
        "source_dataset": str(source["dataset_path"]),
        "source_dataset_sha256": source["dataset_sha256"],
        "cascade_prereg_sha256": source["prereg_sha256"],
        "analysis_source_sha256": analysis_source_hashes(),
        "token_scope": "recorded prompt_tokens + completion_tokens; undercounts multi-call prompts for SC/TOT/ReAct",
        "latency_scope": "sum of replayed historical arm wall_ms; not online policy latency",
        "lambda": lam,
        "bootstrap_repetitions": _bootstrap_repetitions,
        "git_sha": git_value("rev-parse", "HEAD"),
        "git_status_before_output": git_value("status", "--porcelain"),
        "python": sys.version,
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "manifest.json", manifest)
    try:
        write_json(output / "policy.json", {
            "scope": ["arith", "order"],
            "frozen_policy_v": {
                "status": "preregistered_but_in_sample_verifier",
                "rule": "COT; on legacy verifier flag or COT length: PAL for arith, SC for order",
            },
            "posthoc_think_on_demand_fail_open": {
                "status": "reconstructed_posthoc_not_deployable_evidence",
                "rule": "arith -> PAL; order -> COT, then TOT on legacy verifier flag or COT length",
                "unextractable_ordering": "legacy pass (unsafe)",
            },
            "posthoc_think_on_demand_fail_closed": {
                "status": "exploratory_safety_variant_not_deployable_evidence",
                "rule": "arith -> PAL; order -> COT, then TOT unless tri-state verifier is valid",
                "unextractable_ordering": "escalate",
            },
            "runtime_metadata_assumptions": [
                "perfect dataset family label",
                "canonical structured order metadata",
            ],
            "uses_gold_at_runtime": False,
        })
        write_json(output / "source_validation.json", {
            "row_count": len(source["rows"]),
            "unique_conditions": len(source["by_key"]),
            "provenance": source["provenance"],
            "sc_checker_disagreements": source["checker_disagreements"],
        })
        write_json(output / "results.json", results)
        write_json(output / "summary.json", summary)
        (output / "report.md").write_text(render_report(manifest, summary, source), encoding="utf-8")
        manifest["artifact_sha256"] = {
            path.name: sha256_file(path)
            for path in sorted(output.iterdir())
            if path.is_file() and path.name != "manifest.json"
        }
        manifest.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "manifest.json", manifest)
    except BaseException as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        write_json(output / "manifest.json", manifest)
        raise
    return summary
