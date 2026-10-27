"""Audit/replay a completed A/F/CONT batch using a tokenizer only, never MLX.

M offsets and D weights reuse each collected draw. Score intervals are nominal
and descriptive on exposed development; no GO/NO-GO decision is enabled.
"""

from __future__ import annotations

import argparse
from functools import lru_cache, partial
from importlib import metadata, util
import json
from math import copysign, inf, sqrt
from pathlib import Path

from experiments.cot_restart_matched import ARMS, read_plan
from experiments.cot_restart_pilot import ROOT, encoded_json, file_sha256, text_sha256
import experiments.cot_restart_replay as replay_module
from reasoning.reasoning_strategies import parse_answer_details
from scripts.gen_tasks import check

Z95 = 1.959963984540054
CONTRASTS = (("CONT", "A"), ("F", "A"), ("F", "CONT"))


def _score_z(b, c, n, delta):
    numerator = b - c - n * delta
    B = -(b + c) + delta * (2 * n - b + c)
    root = sqrt(max(B * B + 8 * n * c * delta * (1 - delta), 0.0))
    q = (2 * c * delta * (1 - delta) / (B + root)) if B > 0 else (-B + root) / (4 * n)
    variance = 0.0 if abs(delta) >= 1 else n * (2 * q + delta * (1 - delta))
    if variance <= 0:
        return 0.0 if abs(numerator) < 1e-9 else copysign(inf, numerator)
    return numerator / sqrt(variance)


def nominal_tango_ci(b, c, n):
    """Score inversion from the supplied gonogo.py v2; finite-sample approximation."""
    if n < 1 or min(b, c) < 0 or b + c > n:
        raise ValueError("invalid paired binary table")
    def endpoint(target):
        lo, hi = -1.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if _score_z(b, c, n, mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    return [(-1.0 if _score_z(b, c, n, -1) <= Z95 else endpoint(Z95)),
            (1.0 if _score_z(b, c, n, 1) >= -Z95 else endpoint(-Z95))]


def load_cpu_tokenizer(record: dict):
    """Load the installed text renderer by file, avoiding mlx_lm's Metal imports."""
    from transformers import AutoTokenizer
    source = Path(metadata.distribution("mlx-lm").locate_file("mlx_lm/tokenizer_utils.py"))
    spec = util.spec_from_file_location("_cot_restart_cpu_tokenizer", source)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    snapshot = Path(record["tokenizer_name_or_path"])
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False)
    config = json.loads((snapshot / "tokenizer.json").read_text())
    decoder = config.get("decoder")
    renderer = module.NaiveStreamingDetokenizer
    if module._is_spm_decoder(decoder):
        renderer = module.SPMStreamingDetokenizer
    elif module._is_spm_decoder_no_space(decoder):
        renderer = partial(module.SPMStreamingDetokenizer, trim_space=False)
    elif module._is_bpe_decoder(decoder):
        renderer = module.BPEStreamingDetokenizer
    # Tool parsing/chat framing do not participate in completion text rendering.
    return module.TokenizerWrapper(tokenizer, renderer, eos_token_ids=record["eos_token_ids"]), source


def paired_summary(rows: list[dict], *, intervals: bool) -> dict:
    by_arm = {arm: {r["question_id"]: r for r in rows if r["arm"] == arm} for arm in ARMS}
    if any(len(values) != sum(r["arm"] == arm for r in rows) for arm, values in by_arm.items()):
        raise ValueError("paired summary rejects duplicate item/arm rows")
    ids = set(by_arm["A"])
    if not ids or any(set(values) != ids for values in by_arm.values()):
        raise ValueError("paired summary requires the same questions in every arm")
    arms = {}
    for arm, values in by_arm.items():
        arms[arm] = {"correct": sum(r["correct"] for r in values.values()), "n": len(ids),
                     "accuracy": sum(r["correct"] for r in values.values()) / len(ids),
                     "mean_new_completion_tokens": sum(r["completion_tokens"] for r in values.values()) / len(ids),
                     "mean_path_token_cost": sum(r["path_token_cost"] for r in values.values()) / len(ids)}
    contrasts = []
    for X, Y in CONTRASTS:
        b = sum(by_arm[X][i]["correct"] and not by_arm[Y][i]["correct"] for i in ids)
        c = sum(by_arm[Y][i]["correct"] and not by_arm[X][i]["correct"] for i in ids)
        contrasts.append({"X": X, "Y": Y, "n": len(ids), "b": b, "c": c,
                          "delta": (b - c) / len(ids),
                          "nominal_tango_95_ci": nominal_tango_ci(b, c, len(ids)) if intervals else None})
    return {"n": len(ids), "arms": arms, "contrasts": contrasts}


def audit_records(run: Path, plan: dict) -> tuple[dict, list[dict]]:
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["status"] != "complete" or manifest["mock"]:
        raise ValueError("analysis requires a completed real development batch")
    if manifest["plan_sha256"] != plan["plan_sha256"]:
        raise ValueError("run/plan identity mismatch")
    for name, digest in manifest["artifact_hashes"].items():
        if file_sha256(run / name) != digest:
            raise ValueError(f"run artifact hash mismatch: {name}")
    rows = json.loads((run / "records.json").read_text())
    requests = {(r["question_id"], r["arm"]): r for r in plan["requests"]}
    observed = [(r["question_id"], r["arm"]) for r in rows]
    if len(observed) != len(set(observed)) or set(observed) != set(requests):
        raise ValueError("missing/duplicate paired records")
    head, completed = "0" * 64, {}
    for number, line in enumerate((run / "calls.jsonl").read_text().splitlines()):
        entry = json.loads(line)
        body = {k: v for k, v in entry.items() if k != "sha256"}
        if (entry["sha256"] != text_sha256(encoded_json(body))
                or body["previous"] != head or body["sequence"] != number):
            raise ValueError("journal chain mismatch")
        head = entry["sha256"]
        if entry["kind"] == "matched_call":
            key = tuple(entry["key"])
            if key in completed:
                raise ValueError("duplicate completed journal call")
            completed[key] = entry["value"]
    if head != manifest["journal_head"] or set(completed) != set(requests):
        raise ValueError("journal/manifest completeness mismatch")
    for row in rows:
        key = (row["question_id"], row["arm"])
        if row != completed[key]:
            raise ValueError("record differs from raw completed journal call")
        request = requests[key]
        for field in ("prompt", "prompt_token_ids", "prompt_tokens", "completion_cap", "seed",
                      "prefix_text", "M_cap", "D_caps", "decoding_config"):
            expected = plan[field] if field == "decoding_config" else request[field]
            if row[field] != expected:
                raise ValueError(f"record/plan mismatch: {field}")
    if (manifest["executed_model_calls"] != len(rows)
            or manifest["total_completion_tokens"] != sum(r["completion_tokens"] for r in rows)
            or manifest["total_incurred_tokens"] != sum(r["total_tokens"] for r in rows)):
        raise ValueError("collection counter mismatch")
    return manifest, rows


def analyze(run: Path, plan_dir: Path, output: Path) -> dict:
    run, output = Path(run).resolve(), Path(output).resolve()
    plan = read_plan(plan_dir)
    if output.exists() or output.is_relative_to(run) or output.is_relative_to(Path(plan_dir).resolve()):
        raise ValueError("analysis requires a new isolated directory")
    manifest, rows = audit_records(run, plan)
    tokenizer, tokenizer_source = load_cpu_tokenizer(rows[0])
    original_metadata = replay_module.runtime_metadata
    replay_module.runtime_metadata = lru_cache(maxsize=1)(original_metadata)
    items = json.loads((Path(plan["historical_dir"]) / "dataset.json").read_text())["items"]
    by_id = {item["id"]: item for item in items}
    bases = json.loads((Path(plan["historical_dir"]) / "base_traces.json").read_text())
    replays = []
    try:
        for row in rows:
            for point, cap, w in [
                ("M_minus8", row["M_cap"] - 8, 1), ("M", row["M_cap"], 1),
                ("M_plus8", row["M_cap"] + 8, 1),
                ("D_w0", row["D_caps"]["0"], 0), ("D_w1", row["D_caps"]["1"], 1),
            ]:
                result = replay_module.score_replay(row, tokenizer, cap, by_id[row["question_id"]],
                                                    prefix_text=row["prefix_text"])
                result.pop("completion_token_ids")
                result.update({"point": point, "question_id": row["question_id"], "arm": row["arm"],
                               "path_token_cost": row["base_completion_tokens"] + w * row["base_prompt_tokens"]
                                                  + w * row["prompt_tokens"] + result["completion_tokens"]})
                if point.startswith("D") and result["path_token_cost"] > plan["T_star"]:
                    raise ValueError("D replay exceeds its registered token allowance")
                replays.append(result)
    finally:
        replay_module.runtime_metadata = original_metadata
    points = {point: paired_summary([r for r in replays if r["point"] == point],
                                    intervals=point in ("M", "D_w0", "D_w1"))
              for point in ("M_minus8", "M", "M_plus8", "D_w0", "D_w1")}
    sensitivity = []
    for item in items:
        selected = [r for r in replays if r["question_id"] == item["id"] and r["point"].startswith("M")]
        sensitivity.append({"question_id": item["id"],
                            "outcome_changed": any(len({r["correct"] for r in selected if r["arm"] == arm}) > 1 for arm in ARMS),
                            "finish_changed": any(len({r["finish_reason"] for r in selected if r["arm"] == arm}) > 1 for arm in ARMS)})
    rescored_bases = []
    for item in items:
        answer_type = {"arith": "number", "order": "text", "g24": "expression"}[item["family"]]
        b = bases[item["id"]]
        parsed, status, _ = parse_answer_details(b["raw_output"], answer_type=answer_type)
        rescored_bases.append({"question_id": item["id"], "historical_correct": b["correct"],
                               "retrospective_correct": bool(check(item, parsed)) if parsed is not None else False,
                               "retrospective_parse_status": status, "finish_reason": b["finish_reason"]})
    summary = {"evidence": "exposed_development_single_draw_token_replay", "confirmatory": False,
               "decision_states_enabled": False, "q_star": plan["q_star"], "W": plan["W"],
               "T_star": plan["T_star"], "n": 12, "collection": {
                   "calls": manifest["executed_model_calls"], "completion_tokens_including_eos": manifest["total_completion_tokens"],
                   "prompt_plus_completion_tokens": manifest["total_incurred_tokens"],
                   "active_collection_seconds": manifest["active_seconds"]},
               "base_cost_scope": plan["base_cost_scope"], "points": points,
               "boundary_sensitive_questions": sum(r["outcome_changed"] for r in sensitivity),
               "boundary_finish_sensitive_questions": sum(r["finish_changed"] for r in sensitivity),
               "sensitivity": sensitivity, "base_rescoring": rescored_bases}
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("replays.json", replays)):
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    lines = ["# A/F/CONT development replay review", "",
             "All 36 real records/journal entries and their original token IDs were audited. No new model calls.",
             "Exposed development, 12 questions, one draw per arm; no GO/NO-GO decision or Stage 0 change.", "",
             "| Point | A correct | F correct | CONT correct |",
             "| --- | ---: | ---: | ---: |"]
    for point, value in points.items():
        lines.append(f"| {point} | {value['arms']['A']['correct']}/12 | {value['arms']['F']['correct']}/12 | {value['arms']['CONT']['correct']}/12 |")
    lines.extend(["", "| Point | Contrast | b | c | Delta (pp) | Nominal Tango 95% CI (pp) |",
                  "| --- | --- | ---: | ---: | ---: | --- |"])
    for point, value in points.items():
        for contrast in value["contrasts"]:
            ci = contrast["nominal_tango_95_ci"]
            interval = f"[{100*ci[0]:+.1f}, {100*ci[1]:+.1f}]" if ci else "descriptive sensitivity only"
            lines.append(f"| {point} | {contrast['X']}-{contrast['Y']} | {contrast['b']} | {contrast['c']} | "
                         f"{100*contrast['delta']:+.1f} | {interval} |")
    lines.extend(["", f"M +/-8 outcome-sensitive questions: {summary['boundary_sensitive_questions']}/12.",
                  f"M +/-8 finish-sensitive questions: {summary['boundary_finish_sensitive_questions']}/12.", "",
                  "The score intervals are nominal/asymptotic, unadjusted and descriptive at n=12.",
                  "Sensitivity points reuse the same draw, remain paired, and are not pooled as independent data.",
                  "D at T*=2560 is conditional on logged historical base counts with unverified EOS convention.",
                  "Costs are sampled/prefill token counts, not measured FLOPs, billing or full inference costs.",
                  "Collection timing is from the larger collected caps; it is not online latency for M/D replay.",
                  "CONT-A measures the continuation package. F-CONT changes retained context and the restart/continuation package.",
                  "M gives every arm the same new-completion cap; D(w=1) also changes that allowance through prompt charging.",
                  "Neither contrast isolates formatting or removal of an erroneous tail. No learned locator/probe conclusion follows.", "",
                  f"Collection: {manifest['executed_model_calls']} calls, {manifest['total_completion_tokens']:,} completion tokens including EOS,",
                  f"{manifest['total_incurred_tokens']:,} prompt+completion tokens; prior base collection is excluded."])
    (output / "report.md").write_text("\n".join(lines) + "\n")
    sources = {name: file_sha256(ROOT / name) for name in (
        "scripts/analyze_cot_restart_matched.py", "experiments/cot_restart_replay.py",
        "reasoning/reasoning_strategies.py", "research_scoring.py", "scripts/gen_tasks.py",
    )}
    audit = {"plan_sha256": plan["plan_sha256"], "source_sha256": sources,
             "tokenizer_renderer_source_sha256": file_sha256(tokenizer_source),
             "run_artifact_hashes": manifest["artifact_hashes"], "journal_head": manifest["journal_head"],
             "outputs_sha256": {p.name: file_sha256(p) for p in output.iterdir()}}
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.run, args.plan, args.output)
    print(json.dumps({"n": result["n"], "collection": result["collection"],
                      "boundary_sensitive_questions": result["boundary_sensitive_questions"]}, indent=2))


if __name__ == "__main__":
    main()
