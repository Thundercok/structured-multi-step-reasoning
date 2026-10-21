"""Added-after-inspection M/D cap diagnostics from original IDs; no inference."""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
from pathlib import Path

from experiments.cot_restart_pilot import ROOT, file_sha256
import experiments.cot_restart_replay as replay
from scripts.aggregate_cot_restart_matched import ARMS, load_bundle
from scripts.analyze_cot_restart_matched import CONTRASTS, load_cpu_tokenizer, paired_summary
from scripts.prepare_cot_restart_replication import validate_replication_plan


def cap_request(record: dict, weight: int, offset: int) -> dict:
    cap = record["D_caps"][str(weight)] + offset
    return {"cap": cap, "available": 1 <= cap <= record["completion_cap"],
            "reason": ("positive cap covered by the collected trace" if 1 <= cap <= record["completion_cap"]
                       else "requested cap exceeds collection or is nonpositive; no extrapolation")}


def transition_rows(bundle: dict) -> list[dict]:
    rows = []
    for identifier in sorted(bundle["groups"]):
        for arm in ARMS:
            before = bundle["indexed"]["M", identifier, arm]
            after = bundle["indexed"]["D_w0", identifier, arm]
            rows.append({"question_id": identifier, "arm": arm,
                         "correctness_changed": before["correct"] != after["correct"],
                         "M": {key: before[key] for key in ("correct", "replay_cap", "completion_tokens", "finish_reason", "parse_status", "parsed_answer")},
                         "D_w0": {key: after[key] for key in ("correct", "replay_cap", "completion_tokens", "finish_reason", "parse_status", "parsed_answer")},
                         "M_tail": before["full_response"][-450:], "D_w0_tail": after["full_response"][-450:]})
    return rows


def review(output: Path) -> dict:
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("use a new review directory")
    paths = [(ROOT/"audit/cot_restart_matched_plan_20261013", ROOT/"audit/cot_restart_matched_real_20261013", ROOT/"audit/cot_restart_matched_analysis_20261013"),
             (ROOT/"audit/cot_restart_replication_plan_20261013", ROOT/"audit/cot_restart_replication_real_20261013", ROOT/"audit/cot_restart_replication_analysis_20261013")]
    if any(output.is_relative_to(p) for triple in paths for p in triple):
        raise ValueError("keep the review outside existing inputs")
    bundles = [load_bundle(*triple) for triple in paths]
    validate_replication_plan(bundles[0]["plan"], bundles[1]["plan"])
    original = [json.loads((triple[1]/"records.json").read_text()) for triple in paths]
    dataset = Path(bundles[0]["plan"]["historical_dir"])/"dataset.json"
    items = {item["id"]: item for item in json.loads(dataset.read_text())["items"]}
    reporting = ROOT/"audit/cot_restart_reporting_review_20261014"
    reporting_manifest = json.loads((reporting/"manifest.json").read_text())
    for name, digest in reporting_manifest["output_sha256"].items():
        if file_sha256(reporting/name) != digest:
            raise ValueError("reporting artifact changed")
    strata = json.loads((reporting/"strata.json").read_text())
    net_wrong = [{"draw_index": draw["draw_index"],
                  **next(c for table in draw["tables"] if table["point"] == "M" and table["stratum"] == "base_wrong"
                         for c in table["contrasts"] if (c["X"], c["Y"]) == ("F", "A"))} for draw in strata]
    transitions = [{"draw_index": index, "rows": transition_rows(bundle)} for index, bundle in enumerate(bundles)]
    labels = {"label": "added after inspection", "confirmatory": False,
              "plan_sha256": bundles[1]["plan"]["plan_sha256"],
              "exact_registered_keys": {
                  "/replication/analysis_spec/bootstrap_samples": bundles[1]["plan"]["replication"]["analysis_spec"]["bootstrap_samples"],
                  "/replication/analysis_spec/bootstrap_seed": bundles[1]["plan"]["replication"]["analysis_spec"]["bootstrap_seed"]},
              "added_tables": [
                  {"artifact": "audit/cot_restart_reporting_review_20261014/strata.json", "label": "added after inspection"},
                  {"artifact": "audit/cot_restart_reporting_review_20261014/null_and_boundary.json", "label": "added after inspection"},
                  {"artifact": "audit/cot_restart_reporting_review_20261014/sign_flip.json", "label": "added after inspection"},
                  {"artifact": "M_to_D_w0_transitions.json", "label": "added after inspection"},
                  {"artifact": "D_sensitivity.json", "label": "added after inspection"}]}
    tokenizer, tokenizer_source = load_cpu_tokenizer(original[0][0])
    previous_metadata = replay.runtime_metadata
    replay.runtime_metadata = lru_cache(maxsize=1)(previous_metadata)
    sensitivity = []
    try:
        for draw_index, records in enumerate(original):
            for weight in (0, 1):
                for offset in (-8, 0, 8):
                    cells = []
                    for record in records:
                        request = cap_request(record, weight, offset)
                        cell = {"draw_index": draw_index, "weight": weight, "offset": offset,
                                "question_id": record["question_id"], "arm": record["arm"], **request}
                        if request["available"]:
                            if offset == 0:
                                scored = bundles[draw_index]["indexed"][f"D_w{weight}", record["question_id"], record["arm"]]
                            else:
                                scored = replay.score_replay(record, tokenizer, request["cap"], items[record["question_id"]], prefix_text=record["prefix_text"])
                            cell.update({key: scored[key] for key in ("correct", "finish_reason", "parse_status", "parsed_answer", "completion_tokens")})
                            cell["path_token_cost"] = (record["base_completion_tokens"] + weight*record["base_prompt_tokens"]
                                                       + weight*record["prompt_tokens"] + cell["completion_tokens"])
                            if cell["path_token_cost"] > bundles[draw_index]["plan"]["T_star"]+offset:
                                raise ValueError("D sensitivity exceeds its conditional token allowance")
                        cells.append(cell)
                    available = [cell for cell in cells if cell["available"]]
                    # Never select an outcome/trace-available subset as the original 12-question contrast.
                    table = paired_summary(available, intervals=False) if len(available) == len(records) else None
                    sensitivity.append({"draw_index": draw_index, "weight": weight, "offset": offset,
                                        "label": "added after inspection; descriptive only",
                                        "available_cells": len(available), "required_cells": len(records),
                                        "all_question_table": table, "cells": cells})
    finally:
        replay.runtime_metadata = previous_metadata
    comparison = []
    aggregate_dir = ROOT/"audit/cot_restart_matched_aggregate_20261013"
    aggregate_manifest = json.loads((aggregate_dir/"manifest.json").read_text())
    if file_sha256(aggregate_dir/"summary.json") != aggregate_manifest["output_sha256"]["summary.json"]:
        raise ValueError("aggregate summary changed")
    aggregate = json.loads((aggregate_dir/"summary.json").read_text())
    flips = json.loads((reporting/"sign_flip.json").read_text())
    for point in ("M", "D_w0", "D_w1"):
        for c in aggregate["points"][point]["contrasts"]:
            flip = next(f for f in flips if (f["point"], f["X"], f["Y"]) == (point, c["X"], c["Y"]))
            comparison.append({"point": point, "X": c["X"], "Y": c["Y"], "delta": c["correct"]["delta"],
                               "descriptive_percentile_95_ci": c["correct"]["paired_group_percentile_95_ci"],
                               "sign_flip_p": flip["two_sided_p"], "sign_flip_assumption": flip["null_assumption"],
                               "sign_flip_label": "added after inspection"})
    inputs = {path: digest for b in bundles for path, digest in b["input_sha256"].items()}
    inputs.update({str(reporting/name): file_sha256(reporting/name) for name in ("manifest.json", "strata.json", "sign_flip.json")})
    inputs.update({str(aggregate_dir/name): file_sha256(aggregate_dir/name) for name in ("manifest.json", "summary.json")})
    for name, digest in inputs.items():
        if file_sha256(Path(name)) != digest:
            raise ValueError("review input changed")
    output.mkdir(parents=True, exist_ok=False)
    values = {"M_to_D_w0_transitions.json": transitions, "D_sensitivity.json": sensitivity,
              "base_wrong_item_ids.json": net_wrong, "labels_and_plan_keys.json": labels,
              "interval_and_sign_flip.json": comparison}
    for name, value in values.items():
        (output/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")
    lines = ["# M-to-D budget interpretation and retrospective sensitivity", "",
             "All tables in this review are added after inspection. No inference; original IDs, plans and per-draw artifacts verified.",
             "Draw indices 0/1 below mean first/second draw.", "",
             "| Draw | A question rescued from M to D_w0 | M cap | D_w0 cap | Completion including EOS | Finish / parse change |",
             "| --- | --- | ---: | ---: | ---: | --- |"]
    for draw in transitions:
        for row in draw["rows"]:
            if row["arm"] == "A" and row["correctness_changed"]:
                lines.append(f"| {draw['draw_index']} | {row['question_id']} | {row['M']['replay_cap']} | {row['D_w0']['replay_cap']} | {row['D_w0']['completion_tokens']} | {row['M']['finish_reason']}/{row['M']['parse_status']} -> {row['D_w0']['finish_reason']}/{row['D_w0']['parse_status']} |")
    lines.extend(["", "F correctness is unchanged item by item between M and D_w0, not merely unchanged in total. Its stop-finished completions cannot use extra cap after EOS; the remaining length-finished cases stay wrong in the observed range.",
                  "For g24_0023 in the second draw, a valid expression already appears in the M trace but its final answer is truncated. This case measures finalization under the fixed answer contract, not failure to find any solution.",
                  "M fixes new completion allowance at L_i=2048-P_i_CONT. D_w0 allows more new tokens at these items; it does not change seed/prompt or create a new draw.",
                  "Thus part of F-A at M is timely production of a scored answer under a tighter completion window. It is not evidence of a higher unconstrained correctness ceiling or isolated correction mechanism.",
                  "Keep registered M as primary; report the weaker D contrast without selecting a favorable cap. D costs remain conditional on historical base counts/EOS scope.", "",
                  "| Draw | F-A wins among base-wrong | A-F wins | Net |",
                  "| --- | --- | --- | ---: |"])
    for row in net_wrong:
        lines.append(f"| {row['draw_index']} | {', '.join(row['wins']) or 'none'} | {', '.join(row['losses']) or 'none'} | {row['b']-row['c']:+d} |")
    lines.extend(["", "The first draw's net +1 is two wins minus one loss, not one uniquely identifiable rescued item. The second draw's sole win is a different G24 item.", "",
                  "Registered configuration in replication plan SHA-256 `"+labels["plan_sha256"]+"`:",
                  "- `/replication/analysis_spec/bootstrap_samples` = 2000",
                  "- `/replication/analysis_spec/bootstrap_seed` = 20261013", "",
                  "| Draw | D weight | Offset | Available cells | All-12-question contrast |",
                  "| --- | ---: | ---: | ---: | --- |"])
    for row in sensitivity:
        status = "descriptive, available" if row["all_question_table"] else "not estimable; no extrapolation or selected subset"
        lines.append(f"| {row['draw_index']} | {row['weight']} | {row['offset']:+d} | {row['available_cells']}/{row['required_cells']} | {status} |")
    lines.extend(["", "D -8 and D_w1 +8 use original new-completion IDs. D_w0 +8 exceeds the collected caps and is not estimated under the frozen replay rule, including early-stop records. This does not validate historical base EOS counts.", "",
                  "| Point | Contrast | Delta (pp) | Descriptive percentile CI (pp) | Added-after-inspection sign-flip p |",
                  "| --- | --- | ---: | --- | ---: |"])
    for row in comparison:
        ci = row["descriptive_percentile_95_ci"]
        lines.append(f"| {row['point']} | {row['X']}-{row['Y']} | {100*row['delta']:+.1f} | [{100*ci[0]:+.1f}, {100*ci[1]:+.1f}] | {row['sign_flip_p']:.6f} |")
    lines.extend(["", "Bootstrap and sign-flip have different assumptions and small-sample calibration. Neither is used to establish a confirmatory GO from these inspected 12 groups.",
                  "Sign-flip enumeration assumes groupwise sign exchangeability, beyond a weak zero-mean null. No formal deployment/superiority/mechanistic/Stage 0 claim is enabled."])
    (output/"report.md").write_text("\n".join(lines)+"\n")
    (output/"manifest.json").write_text(json.dumps({"status": "complete", "label": "added after inspection", "new_model_calls": 0,
        "confirmatory": False, "stage_0_changed": False, "input_sha256": inputs,
        "source_sha256": {name: file_sha256(ROOT/name) for name in ("scripts/review_cot_restart_budget.py", "scripts/aggregate_cot_restart_matched.py", "scripts/analyze_cot_restart_matched.py", "experiments/cot_restart_replay.py")},
        "renderer_source_sha256": file_sha256(tokenizer_source), "output_sha256": {p.name: file_sha256(p) for p in output.iterdir()}}, indent=2)+"\n")
    return {"new_model_calls": 0, "fresh_replay_cells": sum(row["available_cells"] for row in sensitivity if row["offset"] != 0),
            "unavailable_cells": sum(row["required_cells"]-row["available_cells"] for row in sensitivity)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.output), indent=2))


if __name__ == "__main__":
    main()
