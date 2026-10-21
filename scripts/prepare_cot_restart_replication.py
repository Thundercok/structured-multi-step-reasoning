"""Freeze a new draw from verified prompts without changing the collector.

CPU only: no tokenizer, weights, MLX import or inference. Collection continues
through experiments.research_study using its existing exact-plan mode.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from experiments.cot_restart_matched import ARMS, read_plan
from experiments.cot_restart_pilot import ROOT, atomic_save_json, encoded_json, file_sha256, text_sha256
from experiments.cot_restart_replay import derive_cap_sweep_seed
from scripts.analyze_cot_restart_matched import audit_records

PREPARATION_SOURCES = (
    "scripts/prepare_cot_restart_replication.py",
    "scripts/analyze_cot_restart_matched.py",
    "docs/cot_restart_replication_protocol_20261013.md",
)


def _checksum(plan: dict) -> str:
    return text_sha256(encoded_json({k: v for k, v in plan.items() if k != "plan_sha256"}))


def _check_parent(parent: dict) -> int:
    if parent.get("plan_sha256") != _checksum(parent):
        raise ValueError("parent plan checksum mismatch")
    requests = parent["requests"]
    keys = {(r["question_id"], r["arm"]) for r in requests}
    ids = {key[0] for key in keys}
    if len(ids) != 12 or len(requests) != 36 or keys != {(i, a) for i in ids for a in ARMS}:
        raise ValueError("replication requires the complete 12-question A/F/CONT plan")
    draw_index = parent.get("draw_index", 0)
    if isinstance(draw_index, bool) or not isinstance(draw_index, int) or draw_index < 0:
        raise ValueError("invalid parent draw index")
    for r in requests:
        if (r.get("call_index", draw_index) != draw_index
                or r["seed"] != derive_cap_sweep_seed(parent["base_seed"], r["question_id"], r["arm"], draw_index)):
            raise ValueError("parent seed does not match its item/arm/draw identity")
    return draw_index


def build_replication_plan(parent: dict, *, draw_index: int = 1) -> dict:
    previous_index = _check_parent(parent)
    if isinstance(draw_index, bool) or not isinstance(draw_index, int) or draw_index <= previous_index:
        raise ValueError("replication draw index must be a new increasing integer")
    plan = copy.deepcopy(parent)
    plan.pop("plan_sha256")
    plan["draw_index"] = draw_index
    plan["replication"] = {
        "parent_plan_sha256": parent["plan_sha256"],
        "parent_draw_index": previous_index,
        "preparation_method": "copy_verified_frozen_prompt_ids_and_caps; change_draw_seed_only",
        "analysis_scope": "exposed_development; conditional_on_fixed_historical_bases_and_observed_draws",
        "analysis_spec": {
            "points": ["M", "D_w0", "D_w1"],
            "contrasts": [["CONT", "A"], ["F", "A"], ["F", "CONT"]],
            "aggregation": "average_within_question_over_draws_then_question_weighted_mean",
            "bootstrap_unit": "original_problem_group; retain_all_group_members_and_draws",
            "bootstrap_samples": 2000, "bootstrap_seed": 20261013,
            "interval": "descriptive_paired_percentile_95; no_binary_Tango_on_fractional_means",
            "M_offsets": "paired_sensitivity_only; never_add_independent_observations",
            "decision_states_enabled": False,
        },
    }
    for request in plan["requests"]:
        request["call_index"] = draw_index
        request["seed"] = derive_cap_sweep_seed(plan["base_seed"], request["question_id"], request["arm"], draw_index)
    old_seeds = {r["seed"] for r in parent["requests"]}
    new_seeds = {r["seed"] for r in plan["requests"]}
    if len(new_seeds) != 36 or old_seeds & new_seeds:
        raise ValueError("draw seeds collide; do not collect this plan")
    plan["plan_sha256"] = _checksum(plan)
    validate_replication_plan(parent, plan)
    return plan


def validate_replication_plan(parent: dict, plan: dict) -> None:
    previous_index = _check_parent(parent)
    _check_parent(plan)
    if plan["draw_index"] <= previous_index:
        raise ValueError("replication must use a new draw")
    if plan["replication"]["parent_plan_sha256"] != parent["plan_sha256"]:
        raise ValueError("replication parent identity mismatch")
    restored = copy.deepcopy(plan)
    restored.pop("plan_sha256")
    restored.pop("replication")
    restored.pop("draw_index")
    for r, old in zip(restored["requests"], parent["requests"]):
        r["seed"] = old["seed"]
        r.pop("call_index")
        if "call_index" in old:
            r["call_index"] = old["call_index"]
    if "draw_index" in parent:
        restored["draw_index"] = parent["draw_index"]
    if "replication" in parent:
        restored["replication"] = parent["replication"]
    original = {k: v for k, v in parent.items() if k != "plan_sha256"}
    if restored != original:
        raise ValueError("replication changed frozen fields beyond draw seeds/metadata")
    old_seeds = {r["seed"] for r in parent["requests"]}
    new_seeds = {r["seed"] for r in plan["requests"]}
    if len(new_seeds) != 36 or old_seeds & new_seeds:
        raise ValueError("draw seeds collide")


def prepare_replication(parent_directory: Path, parent_run: Path, output: Path) -> dict:
    parent_directory, parent_run, output = (Path(p).resolve() for p in (parent_directory, parent_run, output))
    parent = read_plan(parent_directory)
    if parent["evidence"] == "synthetic_preparation":
        raise ValueError("real replication preparation requires a real parent plan")
    protected = (parent_directory, parent_run, Path(parent["historical_dir"]).resolve())
    if output.exists() or any(output.is_relative_to(p) for p in protected):
        raise ValueError("replication preparation requires a new isolated directory")
    manifest, records = audit_records(parent_run, parent)
    plan = build_replication_plan(parent, draw_index=1)
    items = json.loads((Path(parent["historical_dir"]) / "dataset.json").read_text())["items"]
    groups = {item["id"]: item["group_id"] for item in items}
    plan["replication"].update({
        "parent_plan_directory": str(parent_directory), "parent_run_directory": str(parent_run),
        "parent_plan_file_sha256": file_sha256(parent_directory / "plan.json"),
        "parent_run_artifact_sha256": {name: file_sha256(parent_run / name)
                                       for name in ("manifest.json", "records.json", "calls.jsonl")},
        "parent_completed_calls": manifest["executed_model_calls"],
        "parent_journal_head": manifest["journal_head"],
        "original_problem_groups": groups,
        "unique_question_count": len(groups), "unique_group_count": len(set(groups.values())),
        "preparation_source_sha256": {name: file_sha256(ROOT / name) for name in PREPARATION_SOURCES},
        "prior_collection_seconds_descriptive_only": manifest["active_seconds"],
        "prior_completion_tokens_descriptive_only": sum(r["completion_tokens"] for r in records),
        "real_model_calls_during_preparation": 0,
    })
    plan["plan_sha256"] = _checksum(plan)
    validate_replication_plan(parent, plan)
    output.mkdir(parents=True, exist_ok=False)
    atomic_save_json(output / "plan.json", plan)
    read_plan(output)  # Existing supported collector accepts exactly this frozen plan.
    limits = plan["limits"]
    lines = ["# Second matched A/F/CONT draw: frozen development plan", "",
             "Status: prepared. No real-model calls were made during preparation.",
             "This plan copies verified first-draw prompts/IDs/caps and freezes new draw seeds.", "",
             f"- 12 exposed questions, {len(set(groups.values()))} original groups, q={plan['q_star']:.2f}.",
             "- Draw index 1; base seed 42; seed = f(item, arm, call=1), independent of budget.",
             "- All 36 seeds are distinct and disjoint from the first draw's seed set.",
             f"- At most {limits['max_attempted_calls']} attempted calls; failed attempts consume their allowance.",
             f"- Completion ceiling: {limits['max_completion_tokens']:,} sampled tokens including EOS.",
             f"- Prompt allowance: {limits['max_prompt_tokens']:,}; combined ceiling: {limits['max_prompt_plus_completion_tokens']:,} tokens.",
             f"- Largest per-call prompt+completion allowance: {limits['max_per_call_prompt_plus_completion_tokens']:,} tokens.",
             "- Refuse a new call after eight active hours; this is not a mid-call timeout.",
             f"- M: W={plan['W']}, same per-item caps and -8/0/+8 sensitivity. D: T*={plan['T_star']}, w=0/1.",
             "- Model snapshot, sampling, prompt order, cache settings and generation source hashes are unchanged.", "",
             "The first draw used approximately 32 minutes of active collection. That observation is",
             "not a runtime guarantee or replay online-latency measurement. The exact token ceilings",
             "above, rather than the first draw's observed completion length, bound the new run.", "",
             "Freeze per-draw reporting and within-question averaging before paired group bootstrap",
             "(2,000 samples, bootstrap seed 20261013). Two draws still contain 12 questions.",
             "Do not apply a binary paired-table interval to fractional seed-averaged outcomes.",
             "Sensitivity caps reuse each draw and remain descriptive. No fitted utility threshold",
             "or formal superiority decision is introduced. D retains the historical base-count",
             "EOS limitation. Stage 0 and publication review remain unchanged.", "",
             f"Plan SHA-256: `{plan['plan_sha256']}`", "",
             "| Item | Arm | First seed | New seed | Collected cap |",
             "| --- | --- | ---: | ---: | ---: |"]
    for old, new in zip(parent["requests"], plan["requests"]):
        lines.append(f"| {new['question_id']} | {new['arm']} | {old['seed']} | {new['seed']} | {new['completion_cap']} |")
    (output / "report.md").write_text("\n".join(lines) + "\n")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-plan", type=Path, required=True)
    parser.add_argument("--parent-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare_replication(args.parent_plan, args.parent_run, args.output)
    print(json.dumps({"status": plan["status"], "plan_sha256": plan["plan_sha256"],
                      "limits": plan["limits"], "real_model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
