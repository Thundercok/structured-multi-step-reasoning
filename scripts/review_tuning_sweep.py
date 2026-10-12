"""Offline review of the completed H4 trace; no generation, fitting or freezing."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import types

from reasoning_strategies import parse_answer_details
from research_identity import problem_fingerprint
from scripts.audit_development_data import solve_procedural_query
from scripts.gen_tasks import check

ROOT = Path(__file__).resolve().parents[1]
LEGACY_COMMIT = "76d311b"
ARM_LIMITS = {"DIRECT": 96, "COT": 1024}
ANSWER_TYPES = {"arith": "number", "order": "text", "g24": "expression"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy_implementation():
    modules, hashes = {}, {}
    for name in ("reasoning_strategies.py", "scripts/gen_tasks.py"):
        source = subprocess.check_output(["git", "show", f"{LEGACY_COMMIT}:{name}"], cwd=ROOT)
        module = types.ModuleType("h4_legacy_" + name.replace("/", "_"))
        # Trusted, pinned repository code. These modules define helpers only.
        exec(compile(source, name, "exec"), module.__dict__)
        modules[name] = module
        hashes[name] = hashlib.sha256(source).hexdigest()
    return modules["reasoning_strategies.py"].parse_answer_details, modules["scripts/gen_tasks.py"].check, hashes


def analyze(records, items, legacy_parser, legacy_checker):
    by_id = {item["id"]: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("Duplicate dataset IDs")
    expected = {(identifier, arm) for identifier in by_id for arm in ARM_LIMITS}
    keys = [(record["id"], record["arm"]) for record in records]
    if len(set(keys)) != len(keys) or set(keys) != expected:
        raise ValueError("Trace requires exactly one record per item/arm")
    proofs = []
    for item in items:
        answer, proof = solve_procedural_query(item)
        if answer != item["answer"] or not check(item, answer):
            raise ValueError("Tuning gold failed independent query-based check")
        proofs.append({"id": item["id"], "original_split": item["split"], "expected_answer": answer, "proof": proof})
    outcomes = []
    for line, record in enumerate(records, 1):
        item = by_id[record["id"]]
        if any(record[field] != item[field] for field in ("group_id", "family", "level")) or record["gold"] != item["answer"]:
            raise ValueError("Trace item metadata/gold differs from dataset")
        old = legacy_parser(record["raw_output"])
        if old != (record["parsed"], record["parse_status"], record["wordy"]) or legacy_checker(item, old[0]) != record["correct"]:
            raise ValueError("Recorded legacy parsing/scoring cannot be reproduced")
        for field in ("prompt_tokens", "completion_tokens"):
            value = record[field]
            if type(value) is not int or value < 0:
                raise ValueError("Invalid token count")
        tokens = record["completion_tokens"]
        if tokens == 0 or tokens > ARM_LIMITS[record["arm"]] or record["finish_reason"] not in ("stop", "length"):
            raise ValueError("Token count or finish reason violates declared arm")
        if record["finish_reason"] == "length" and tokens != ARM_LIMITS[record["arm"]]:
            raise ValueError("Length termination must agree with the arm token limit")
        if not math.isfinite(record["wall_ms"]) or record["wall_ms"] < 0:
            raise ValueError("Invalid wall time")
        parsed, status, wordy = parse_answer_details(record["raw_output"], answer_type=ANSWER_TYPES[item["family"]])
        strict_old = bool(check(item, old[0]))
        typed_correct = bool(check(item, parsed))
        category = "correct" if typed_correct else "incorrect_at_token_limit" if record["finish_reason"] == "length" else "unaccepted_answer_format" if status == "fail" else "incorrect_final_answer"
        outcomes.append({
            "id": record["id"], "arm": record["arm"], "family": item["family"], "level": item["level"],
            "source_line": line, "problem_fingerprint": problem_fingerprint(item),
            "legacy": {"parsed": old[0], "parse_status": old[1], "wordy": old[2], "correct": record["correct"]},
            "strict_checker_on_legacy_parse": strict_old,
            "typed": {"parsed": parsed, "parse_status": status, "wordy": wordy, "correct": typed_correct},
            "finish_reason": record["finish_reason"], "generated_tokens": tokens,
            "prompt_tokens": record["prompt_tokens"], "observed_arm_wall_ms": record["wall_ms"],
            "failure_profile": category,
            "raw_output_sha256": hashlib.sha256(record["raw_output"].encode()).hexdigest(),
        })

    def metrics(rows):
        return {
            "n": len(rows), "canonical_groups": len({row["problem_fingerprint"] for row in rows}),
            "legacy_correct": sum(row["legacy"]["correct"] for row in rows),
            "strict_checker_on_legacy_parse_correct": sum(row["strict_checker_on_legacy_parse"] for row in rows),
            "typed_correct": sum(row["typed"]["correct"] for row in rows),
            "typed_accuracy": sum(row["typed"]["correct"] for row in rows) / len(rows),
            "length_terminations": sum(row["finish_reason"] == "length" for row in rows),
            "typed_parse_status": dict(Counter(row["typed"]["parse_status"] for row in rows)),
            "failure_profile": dict(Counter(row["failure_profile"] for row in rows)),
            "mean_generated_tokens": statistics.mean(row["generated_tokens"] for row in rows),
            "total_generated_tokens": sum(row["generated_tokens"] for row in rows),
            "mean_prompt_tokens": statistics.mean(row["prompt_tokens"] for row in rows),
            "mean_observed_arm_wall_ms": statistics.mean(row["observed_arm_wall_ms"] for row in rows),
        }

    family_levels = sorted({(row["family"], row["level"]) for row in outcomes})
    summary = {
        "overall": {arm: metrics([row for row in outcomes if row["arm"] == arm]) for arm in ARM_LIMITS},
        "families": [{"family": family, "arm": arm, **metrics([row for row in outcomes if row["family"] == family and row["arm"] == arm])} for family in sorted(ANSWER_TYPES) if any(row["family"] == family for row in outcomes) for arm in ARM_LIMITS],
        "family_levels": [{"family": family, "level": level, "arm": arm, **metrics([row for row in outcomes if (row["family"], row["level"], row["arm"]) == (family, level, arm)])} for family, level in family_levels for arm in ARM_LIMITS],
        "legacy_records_reproduced": len(outcomes), "tuning_gold_items_verified": len(proofs),
        "changed_correctness": sum(row["legacy"]["correct"] != row["typed"]["correct"] for row in outcomes),
        "changed_parsed_answer": sum(row["legacy"]["parsed"] != row["typed"]["parsed"] for row in outcomes),
        "parse_recoveries_from_strict_legacy_parse": sum(not row["strict_checker_on_legacy_parse"] and row["typed"]["correct"] for row in outcomes),
        "presentation_cases_recovered_from_strict_legacy_parse": sum(
            not row["strict_checker_on_legacy_parse"] and row["typed"]["correct"] and (
                row["legacy"]["parsed"].strip("* ") == row["typed"]["parsed"]
                or row["legacy"]["parsed"].casefold().removeprefix("answer:").strip() == row["typed"]["parsed"].casefold()
            ) for row in outcomes
        ),
        "g24_parser_score_gains": sum(row["family"] == "g24" and not row["legacy"]["correct"] and row["typed"]["correct"] for row in outcomes),
        "paired_arm_outcomes": dict(Counter(
            "both_correct" if pair["DIRECT"] and pair["COT"] else "cot_only_correct" if pair["COT"] else "direct_only_correct" if pair["DIRECT"] else "both_wrong"
            for pair in ({row["arm"]: row["typed"]["correct"] for row in outcomes if row["id"] == identifier} for identifier in by_id)
        )),
        "parameters_frozen": False, "stage0_changed": False, "new_model_calls": 0,
    }
    return summary, outcomes, proofs


def render_report(summary, outcomes):
    lines = [
        "# Offline review of the Qwen3-8B H4 tuning sweep", "",
        "Assessment: share with caveats as development diagnostics. Human review and publication claims remain pending. No parameters were frozen and Stage 0 is unchanged.", "",
        f"Reproduced all {summary['legacy_records_reproduced']} recorded parser/scorer outcomes from Git 76d311b. Independently checked all {summary['tuning_gold_items_verified']} tuning questions and reference answers using query-parsed arithmetic, exhaustive ordering and exact rational expression evaluation. This is agent review of an exposed tuning pool, including its obsolete test labels; no main-study held-out content was reviewed.", "",
        "## Arm-separated results", "",
        "Typed scores reparse these same historical raw outputs with the current strict parser/checker. They are retrospective rescoring, not newly generated or held-out results.", "",
        "| Family | Arm | N | Legacy correct | Typed correct | Typed accuracy | Length stops | Mean generated tokens |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["families"]:
        lines.append(f"| {row['family']} | {row['arm']} | {row['n']} | {row['legacy_correct']} | {row['typed_correct']} | {row['typed_accuracy']:.1%} | {row['length_terminations']} | {row['mean_generated_tokens']:.1f} |")
    for arm, row in summary["overall"].items():
        lines.append(f"| All | {arm} | {row['n']} | {row['legacy_correct']} | {row['typed_correct']} | {row['typed_accuracy']:.1%} | {row['length_terminations']} | {row['mean_generated_tokens']:.1f} |")
    lines.extend([
        "", "## Parsing findings", "",
        f"Correctness changes: {summary['changed_correctness']}; parsed-answer changes: {summary['changed_parsed_answer']}. Presentation normalization recovers {summary['presentation_cases_recovered_from_strict_legacy_parse']} correct answers rejected by the strict checker on the legacy parse. The original trace and summary are unchanged.", "",
        "Balanced bold around a whole answer/label and contiguous repeated Answer: prefixes are normalized. The entire remaining answer is retained; negation, alternatives, wrong ordinals, disallowed expressions and contradictory equalities remain rejected. These presentation rules apply by format rather than by gold label.", "",
        "The legacy DIRECT arithmetic answer arith_0011_en_orig extracted 1196 from a reasoning tail at the token cap. Its arithmetic is correct, but it lacks the requested bare final answer. The typed contract rejects that explanatory tail. This score change is a format-contract difference, not evidence of an arithmetic error.", "",
        "Correct CoT ordering answers with **Answer: Frank** and a Final Answer:/Answer: sequence were susceptible to strict format rejection before the presentation fix. Existing permissive name matching had accepted these strings; the repaired typed parser now handles their presentation explicitly without searching the answer for a gold name.", "",
        f"Game-of-24 parser score gains: {summary['g24_parser_score_gains']}. Failure includes incomplete/repeated attempts at the token cap and invalid final expressions; attributing these failures to parser error alone is unsupported.", "",
        "## Difficulty bands and measurement limits", "",
        "DIRECT uses temperature 0 and a 96-token cap; CoT uses temperature 0 and a 1,024-token cap, with different prompt suffixes. Budget and instruction effects are confounded; the observed gap does not isolate the effect of the reasoning instruction. There is one greedy output per question/arm, no logged generation-seed series or original runtime manifest, and each family/level has only 7–8 questions.", "",
        "The historical summary pools token counts, truncation and parser diagnostics across both arms. The tables here separate arms. Costs are recorded generated-token counts, with prompt counts shown separately in summary.json; they omit loading, embeddings and other full inference costs. Recorded wall_ms measures each historical arm generation call; it is descriptive across interrupted sessions, not online controller latency or a replay latency estimate.", "",
        "Arithmetic CoT levels 1–3 saturate at 8/8, while level 4 is 4/8. Ordering CoT is not monotonic with declared level; level 4 is 8/8. Game-of-24 has a low-accuracy floor and many CoT length terminations. Generator levels therefore do not yet establish calibrated difficulty or useful accuracy spread for all strategies.", "",
        "Canonical groups number 91 for 94 tuning questions; renamed ordering variants are dependent. Scores here are question-weighted descriptions. No confidence interval, significance, population superiority or statistical-power claim is made.", "",
        "The runner records a snapshot name from cache inspection but loads the model by repository ID. The recorded checkpoint field is not independent proof of the loaded weight identity. Fresh supported runs should supply an explicitly pinned local snapshot. Parser/checker source is reproducible; the full historical generation environment is not reconstructed by this review.", "",
        "## Decision before parameter freeze", "",
        "1. Keep the existing dataset levels, prompts and budgets unfrozen as publication choices. Preserve this run as exposed-development evidence.",
        "2. Retain the presentation parsing repair and verify it with regression/smoke checks. New collection must record the updated parser source hash.",
        "3. Before another real-model pilot, complete human/source review and the applicable Stage 0 review, then record model path/revision, prompts, budgets and generation settings. Compare common token caps or a declared budget grid on development if isolating instruction effects is a research goal.",
        "4. Use a supported headless development collection workflow for any further pilot, without exposing main-study test items or labeling an all-split runner execution as development-only. Review family/level floors and ceilings there before fixing sample counts and preregistering the main study.", "",
        "## Family/level detail", "",
        "| Family | Level | Arm | N | Typed correct | Accuracy | Length stops | Mean generated tokens |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in summary["family_levels"]:
        lines.append(f"| {row['family']} | {row['level']} | {row['arm']} | {row['n']} | {row['typed_correct']} | {row['typed_accuracy']:.1%} | {row['length_terminations']} | {row['mean_generated_tokens']:.1f} |")
    lines.extend(["", "## Score/format transitions", "", "| Item | Arm | Legacy parsed | Typed parsed | Legacy correct | Typed correct |", "| --- | --- | --- | --- | --- | --- |"])
    for row in outcomes:
        if row["legacy"]["correct"] != row["typed"]["correct"] or (not row["strict_checker_on_legacy_parse"] and row["typed"]["correct"]):
            old = row["legacy"]["parsed"].replace("|", "\\|")
            new = row["typed"]["parsed"].replace("|", "\\|")
            lines.append(f"| {row['id']} | {row['arm']} | {old} | {new} | {row['legacy']['correct']} | {row['typed']['correct']} |")
    lines.extend(["", "Detailed outcomes record original trace line numbers and raw-output hashes. The manifest pins input, historical and current analysis sources. No model was loaded and no policy was fitted."])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; never overwritten")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    trace, dataset_path = ROOT / "audit/G_sweep_trace.jsonl", ROOT / "data/gen_tune.json"
    verification_path = ROOT / "audit/G_completion_verification.json"
    verification = json.loads(verification_path.read_text())
    for name, expected in verification["artifact_sha256"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError("Historical artifact changed since completion verification")
    if sha256(dataset_path) != verification["dataset_sha256"]:
        raise ValueError("Historical tuning input changed")
    raw = trace.read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("Trace has an incomplete trailing line")
    records = [json.loads(line) for line in raw.splitlines()]
    if len(records) != 188:
        raise ValueError("Expected completed 188-record H4 sweep")
    for record in records:
        if record["commit"] != LEGACY_COMMIT or record["snapshot_hash"] != verification["snapshot_hash"] or record["model_id"] != verification["model_id"] or record["enable_thinking"] is not False:
            raise ValueError("Trace provenance differs from the verified H4 run")
    legacy_parser, legacy_checker, legacy_hashes = legacy_implementation()
    summary, outcomes, proofs = analyze(records, json.loads(dataset_path.read_text())["items"], legacy_parser, legacy_checker)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("outcomes.json", outcomes), ("tuning_gold_checks.json", proofs)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "report.md").write_text(render_report(summary, outcomes), encoding="utf-8")
    source_names = ("scripts/review_tuning_sweep.py", "scripts/audit_development_data.py", "scripts/gen_tasks.py", "reasoning_strategies.py", "research_scoring.py", "research_identity.py", "experiments/research_study.py")
    inputs = (trace, dataset_path, verification_path, ROOT / "audit/G_summary.txt", ROOT / "audit/qwen3-8b-tuning-checkpoint-20261003/run_sweep_g.py.snapshot")
    manifest = {
        "status": "complete", "kind": "retrospective_tuning_trace_review", "model_calls": 0,
        "legacy_commit": LEGACY_COMMIT, "legacy_source_sha256": legacy_hashes,
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "source_sha256": {name: sha256(ROOT / name) for name in source_names},
        "artifact_sha256": {name: sha256(args.output / name) for name in ("summary.json", "outcomes.json", "tuning_gold_checks.json", "report.md")},
        "sampling": {"temperature": 0, "max_tokens": ARM_LIMITS, "thinking": False, "generation_seed_series_logged": False},
        "evidence": "Retrospective rescoring of historical real-model outputs; exposed tuning pool only",
        "reviewer": "Codex AI agent", "human_review_status": "pending", "publication_ready": False,
        "parameters_frozen": False, "stage0_changed": False,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"correctness_changes": summary["changed_correctness"], "presentation_cases": summary["presentation_cases_recovered_from_strict_legacy_parse"], "typed_correct": {arm: row["typed_correct"] for arm, row in summary["overall"].items()}, "parameters_frozen": False}))


if __name__ == "__main__":
    main()
