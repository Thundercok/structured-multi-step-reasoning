"""CPU-only checkpoint preparation on the hash-pinned, exposed Run 11 pool.

No generation, model loading, policy fitting, test evaluation, or generated-code
execution. This is data preparation, not a replacement research entry point.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics

from reasoning_strategies import parse_answer_details
from research_identity import problem_fingerprint
from scripts.gen_tasks import check

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "audit/run11_sweep_trace.jsonl"
DATASET = ROOT / "data/gen02_tune.json"
INPUT_HASHES = {
    "audit/run11_sweep_trace.jsonl": "3d57df7f4e81c71513a30b46a190c2d848ea020dac78adf88776620b6e67e632",
    "data/gen02_tune.json": "f3bfa9750038ecce95f31dcdd7362082c4d85487d37ff091282442874a12041c",
}
MENU = (0.0, 0.25, 0.5, 0.75)
ANSWER_TYPES = {"arith": "number", "order": "text", "g24": "expression"}
SOURCES = (
    "scripts/prepare_cot_restart.py", "research_identity.py",
    "reasoning_strategies.py", "research_scoring.py", "scripts/gen_tasks.py",
    "docs/cot_restart_preflight_protocol_20261009.md",
)
FINAL_MARKER = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?(?:final[ \t]+)?answer"
    r"(?:\*\*)?[ \t]*:[ \t]*", re.I | re.M,
)
SENTENCE_END = re.compile(r"[.!?](?:[\"'\u201d\u2019)]*)(?=\s|$)")
ABBREVIATIONS = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|vs|etc|e\.g|i\.e)\.$", re.I)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reasoning_prefix(raw: str) -> tuple[str, int, int]:
    """Remove the first explicit final-answer block and everything after it.

    Multiple answer blocks remain a review flag. No answer/gold lookup is used.
    Exact leading text is retained so every checkpoint is a source substring.
    """
    markers = list(FINAL_MARKER.finditer(raw))
    end = markers[0].start() if markers else len(raw)
    body = raw[:end].rstrip()
    return body, len(body), len(markers)


def sentence_boundaries(body: str) -> list[int]:
    """Conservative interior text boundaries, not semantic reasoning steps.

    Avoid decimals, numbered list labels, common abbreviations, and fenced or
    display-math blocks. Lines without punctuation require manual review.
    """
    blocked = [(m.start(), m.end()) for m in re.finditer(
        r"```[\s\S]*?(?:```|$)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$", body,
    )]
    boundaries = [0]
    for match in SENTENCE_END.finditer(body):
        pos, end = match.start(), match.end()
        if end >= len(body) or any(lo <= pos < hi for lo, hi in blocked):
            continue
        if body[pos] == ".":
            if (pos and body[pos - 1] == ".") or (pos + 1 < len(body) and body[pos + 1] == "."):
                continue
            if ABBREVIATIONS.search(body[:pos + 1]):
                continue
            line = body[body.rfind("\n", 0, pos) + 1:pos + 1]
            if re.fullmatch(r"\s*\d+\.", line):
                continue
        boundaries.append(end)
    return sorted(set(boundaries))


def canonical_folds(items: list[dict]) -> dict[str, tuple[str, str]]:
    """Outcome-blind grouped development halves; neither is held-out test."""
    identities = {item["id"]: problem_fingerprint(item) for item in items}
    assignment = {}
    for family in sorted({item["family"] for item in items}):
        groups = {identities[item["id"]] for item in items if item["family"] == family}
        ranked = sorted(groups, key=lambda g: text_hash("cot-restart-dev-42:" + g))
        assignment.update({g: "dev_fit" if i % 2 == 0 else "dev_eval" for i, g in enumerate(ranked)})
    return {identifier: (group, assignment[group]) for identifier, group in identities.items()}


def make_menu(raw: str, count_tokens) -> tuple[dict, list[dict]]:
    body, end, marker_count = reasoning_prefix(raw)
    length = count_tokens(body)
    candidates = [(pos, count_tokens(body[:pos])) for pos in sentence_boundaries(body)]
    menu = []
    for q in MENU:
        pos, tokens = min(candidates, key=lambda pair: (abs(pair[1] - q * length), pair[0]))
        prefix = raw[:pos]
        if FINAL_MARKER.search(prefix):
            raise ValueError("An explicit final-answer marker leaked into a checkpoint")
        menu.append({
            "q_requested": q, "cut_char": pos, "prefix": prefix,
            "prefix_sha256": text_hash(prefix), "prefix_retokenized_tokens": tokens,
            "q_actual_retokenized": tokens / length if length else 0.0,
            "remaining_body_token_proxy": max(0, length - tokens),
        })
    return {
        "reasoning_end_char": end, "reasoning_retokenized_tokens": length,
        "explicit_answer_marker_count": marker_count,
        "interior_boundary_count": len(candidates) - 1,
        "distinct_menu_prefixes": len({row["cut_char"] for row in menu}),
    }, menu


def analyze(records: list[dict], items: list[dict], count_tokens):
    by_id = {item["id"]: item for item in items}
    if len(by_id) != len(items) or not items:
        raise ValueError("Dataset IDs must be unique and nonempty")
    cot = [(line, row) for line, row in enumerate(records, 1) if row.get("arm") == "COT"]
    ids = [row["id"] for _, row in cot]
    if len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("Require exactly one COT trace per exposed dataset item")
    folds = canonical_folds(items)
    observations, checkpoints = [], []
    for line, row in cot:
        item = by_id[row["id"]]
        if any(row[key] != item[key] for key in ("group_id", "family", "level")) or row["gold"] != item["answer"]:
            raise ValueError("Trace metadata/gold disagrees with the pinned dataset")
        if not isinstance(row["raw_output"], str) or type(row["correct"]) is not bool:
            raise ValueError("Invalid raw output or recorded outcome")
        if row["finish_reason"] not in ("stop", "length"):
            raise ValueError("Unknown historical termination")
        for key in ("prompt_tokens", "completion_tokens"):
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError("Invalid recorded token count")
        raw = row["raw_output"]
        parsed, parse_status, wordy = parse_answer_details(raw, answer_type=ANSWER_TYPES[item["family"]])
        typed_correct = bool(check(item, parsed))
        info, menu = make_menu(raw, count_tokens)
        flags = []
        if row["finish_reason"] == "length":
            flags.append("source_truncated")
        if info["explicit_answer_marker_count"] != 1:
            flags.append("missing_or_multiple_final_markers")
        if parse_status != "marker" or wordy:
            flags.append("answer_format_needs_review")
        if info["interior_boundary_count"] == 0:
            flags.append("no_interior_sentence_boundary")
        if info["distinct_menu_prefixes"] < len(MENU):
            flags.append("menu_prefixes_collapsed")
        if "```" in raw or "\\[" in raw or "$$" in raw:
            flags.append("code_or_display_math_needs_review")
        candidate = not any(flag in flags for flag in (
            "source_truncated", "missing_or_multiple_final_markers",
            "answer_format_needs_review", "no_interior_sentence_boundary",
            "code_or_display_math_needs_review",
        ))
        profile = (
            "truncation" if row["finish_reason"] == "length" else
            "format_or_missing_final" if parse_status == "fail" or not parsed else
            "correct" if typed_correct else "wrong_final_answer_not_localized"
        )
        canonical_group, fold = folds[row["id"]]
        observations.append({
            "id": row["id"], "source_line": line, "family": item["family"],
            "recorded_group_id": item["group_id"], "canonical_group_id": canonical_group,
            "development_fold": fold, "obsolete_source_split": item["split"],
            "raw_output_sha256": text_hash(raw), "recorded_correct": row["correct"],
            "retrospective_typed_correct": typed_correct, "retrospective_parsed": parsed,
            "retrospective_parse_status": parse_status, "failure_profile": profile,
            "finish_reason": row["finish_reason"], "prompt_tokens_recorded": row["prompt_tokens"],
            "completion_tokens_recorded": row["completion_tokens"],
            "raw_output_retokenized_tokens": count_tokens(raw), **info,
            "review_flags": flags, "checkpoint_review_candidate": candidate,
            "actual_menu_fractions": [checkpoint["q_actual_retokenized"] for checkpoint in menu],
            "dense_matrix_completion_proxy_ms4_me4": 8 * sum(c["remaining_body_token_proxy"] for c in menu),
            "dense_matrix_input_proxy_ms4_me4": 8 * sum(row["prompt_tokens"] + c["prefix_retokenized_tokens"] for c in menu),
        })
        for checkpoint in menu:
            checkpoints.append({
                "checkpoint_id": f"{row['id']}:q{checkpoint['q_requested']:g}",
                "id": row["id"], "canonical_group_id": canonical_group,
                "development_fold": fold, "source_line": line,
                "source_raw_output_sha256": text_hash(raw),
                "preparation_status": "candidate_pending_human_review" if candidate else "diagnostic_only_needs_review",
                **{key: value for key, value in checkpoint.items() if key != "prefix"},
                "model_input": {"query": item["query"], "prefix": checkpoint["prefix"]},
            })
    summary = {
        "evidence": "CPU-only preparation of exposed legacy CoT text; not repair outcomes",
        "source_records": len(records), "cot_traces": len(observations),
        "canonical_questions": len({r["canonical_group_id"] for r in observations}),
        "checkpoint_rows": len(checkpoints), "model_calls": 0,
        "historical_correct": sum(r["recorded_correct"] for r in observations),
        "retrospective_typed_correct": sum(r["retrospective_typed_correct"] for r in observations),
        "retrospective_score_changes": sum(r["recorded_correct"] != r["retrospective_typed_correct"] for r in observations),
        "failure_profile": dict(Counter(r["failure_profile"] for r in observations)),
        "review_flags": dict(Counter(flag for r in observations for flag in r["review_flags"])),
        "checkpoint_review_candidates": sum(r["checkpoint_review_candidate"] for r in observations),
        "candidate_correct": sum(r["checkpoint_review_candidate"] and r["retrospective_typed_correct"] for r in observations),
        "candidate_wrong": sum(r["checkpoint_review_candidate"] and not r["retrospective_typed_correct"] for r in observations),
        "retokenization_count_mismatches": sum(r["raw_output_retokenized_tokens"] != r["completion_tokens_recorded"] for r in observations),
        "by_family": {}, "by_development_fold": {},
        "repair_values_measured": False, "repairability_labels_available": False,
        "oracle_or_probe_evaluated": False, "stage0_changed": False,
        "publication_ready": False,
    }
    for family in sorted(ANSWER_TYPES):
        rows = [r for r in observations if r["family"] == family]
        if not rows:
            continue
        lengths = [r["completion_tokens_recorded"] for r in rows]
        summary["by_family"][family] = {
            "n": len(rows), "historical_correct": sum(r["recorded_correct"] for r in rows),
            "retrospective_typed_correct": sum(r["retrospective_typed_correct"] for r in rows),
            "length_stops": sum(r["finish_reason"] == "length" for r in rows),
            "checkpoint_review_candidates": sum(r["checkpoint_review_candidate"] for r in rows),
            "recorded_completion_mean": statistics.mean(lengths),
            "recorded_completion_median": statistics.median(lengths),
            "recorded_completion_min": min(lengths), "recorded_completion_max": max(lengths),
        }
    for fold in ("dev_fit", "dev_eval"):
        rows = [r for r in observations if r["development_fold"] == fold]
        summary["by_development_fold"][fold] = {
            "traces": len(rows), "canonical_questions": len({r["canonical_group_id"] for r in rows}),
        }
    return summary, observations, checkpoints


def render_report(summary, observations):
    s = summary
    lines = [
        "# CoT restart: CPU-only preflight", "",
        "Assessment: share with caveats as preparation diagnostics. No model calls or repair-quality measurements.", "",
        f"The pinned Run 11 file has {s['source_records']} records, including {s['cot_traces']} CoT traces / {s['canonical_questions']} canonical questions. All are already exposed development, including obsolete source split labels. No new calibration or held-out dataset was opened.", "",
        "## Trace inventory", "",
        "| Family | Traces | Historical correct | Retyped correct | Length stops | Checkpoint candidates | Completion mean / median |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for family, row in s["by_family"].items():
        lines.append(f"| {family} | {row['n']} | {row['historical_correct']} | {row['retrospective_typed_correct']} | {row['length_stops']} | {row['checkpoint_review_candidates']} | {row['recorded_completion_mean']:.1f} / {row['recorded_completion_median']:.1f} |")
    lines += [
        "", "Retyped scores are retrospective diagnostics with the current parser/checker, not replacements for historical scores or fresh model results.", "",
        f"Failure profiles: `{json.dumps(s['failure_profile'], sort_keys=True)}`. A wrong final answer is not a localized reasoning error.", "",
        "## Checkpoint preparation", "",
        f"Prepared {s['checkpoint_rows']} rows for q = 0, .25, .5, .75. Targets are fractions of the locally retokenized reasoning body, snapped to conservative interior sentence boundaries; ties select the earlier boundary. This is a text-boundary heuristic, not identification of correct prefixes or logical steps.", "",
        "Only exact source substrings are retained. The first explicit final-answer block and everything after it are excluded. Gold/outcome annotations are in observations.json; model_input contains only query and prefix. Inspect prefixes manually before any collection.", "",
        f"Candidate traces: {s['checkpoint_review_candidates']} ({s['candidate_correct']} correct / {s['candidate_wrong']} wrong under retrospective scoring). Candidates still need human boundary and contract review. Non-candidates remain in the denominator and observation bundle.", "",
        f"Review flags (overlap allowed): `{json.dumps(s['review_flags'], sort_keys=True)}`.", "",
        "Short traces can collapse several requested q values to the same prefix. Those are not independent restart arms; deduplicate by cut_char before any future allocation, and report the actual fractions.", "",
        "## Token scope and cost warning", "",
        f"Retokenized raw-text counts disagree with saved completion counts in {s['retokenization_count_mismatches']} traces. No generated token IDs or saved KV state are available in these records. Retokenization is not reconstruction of generation tokens or exact assistant-prefix replay.", "",
        "The dense diagnostic matrix m_s=m_e=4 over four q values means 32 calls per trace. The ideal completion-only approximation is 20L; re-prefilling each saved prefix adds about 12L, plus 32 copies of the original query prompt (32P). Thus the simplified input+completion approximation is 32L+32P, before new wrappers/special tokens. Actual boundary snapping and answer removal differ; neither estimate is a measured cost or a hard cap.", "",
        "For every trace, observations.json stores a snapped-text completion proxy and an input proxy separately. They deliberately assume all four points are evaluated; evaluating only the selected point on fresh draws would be a different, cheaper allocation to preregister.", "",
        "## Development grouping", "",
        f"Outcome-blind canonical-question halves: `{json.dumps(s['by_development_fold'], sort_keys=True)}`. Both halves are exposed development, not held-out test. Keep all variants and every trace from one canonical question together; bootstrap by canonical question.", "",
        "## What this preflight does not establish", "",
        "- No V(k,m,b), rescue/harm after repair, repairability class, menu oracle C, fixed restart F, or probe performance was measured.",
        "- Boundary availability and software tests do not show that restart improves accuracy or cost.",
        "- Truncation, schema failures, and wrong stopped answers must be reviewed separately; excluding any category changes the target population.",
        "- Native thinking requires its own matched-budget baseline. Switching repairer or continuation contract invalidates reuse of value labels.",
        "- No model weights were loaded or authenticated; only the local tokenizer was loaded. Stage 0 is unchanged.", "",
        "## Next decision", "",
        "Review a small, outcome-balanced set of prefixes and freeze a continuation contract with verified token accounting. Only then propose an explicitly capped development run; no generation has been authorized by this preflight. The protocol draft is docs/cot_restart_preflight_protocol_20261009.md.", "",
        "## Reproduction", "",
        "From the repository root:", "",
        "```bash", "python3.12 -B -m scripts.prepare_cot_restart --output audit/NEW_COT_RESTART_PREFLIGHT", "```", "",
        "The command is CPU-only, reads only the pinned exposed sources/local tokenizer, and refuses an existing output directory. It does not alter the research collector, fit thresholds, or update legacy runs.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New artifact directory; never overwritten")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    for name, expected in INPUT_HASHES.items():
        if sha256_file(ROOT / name) != expected:
            raise ValueError(f"Pinned exposed input changed: {name}")
    raw_trace = TRACE.read_bytes()
    if not raw_trace.endswith(b"\n"):
        raise ValueError("Incomplete final trace line")
    records = [json.loads(line) for line in raw_trace.splitlines()]
    if len(records) != 571:
        raise ValueError("Expected the complete 571-record Run 11 file")
    cot = [row for row in records if row.get("arm") == "COT"]
    snapshots = {row["snapshot_dir"] for row in cot}
    if len(snapshots) != 1 or any(row["enable_thinking"] is not False for row in cot):
        raise ValueError("Unexpected CoT snapshot or thinking profile")
    tokenizer_path = Path(next(iter(snapshots))) / "tokenizer.json"
    tokenizer_hash = sha256_file(tokenizer_path)
    # Rust text tokenization only: no transformers, MLX, torch, downloads or weights.
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    def count_tokens(text):
        return len(tokenizer.encode(text, add_special_tokens=False).ids)

    source_hashes = {name: sha256_file(ROOT / name) for name in SOURCES}
    items = json.loads(DATASET.read_text(encoding="utf-8"))["items"]
    summary, observations, checkpoints = analyze(records, items, count_tokens)
    report = render_report(summary, observations)
    if source_hashes != {name: sha256_file(ROOT / name) for name in SOURCES}:
        raise ValueError("Analysis source changed during preparation")
    if any(sha256_file(ROOT / name) != expected for name, expected in INPUT_HASHES.items()) or sha256_file(tokenizer_path) != tokenizer_hash:
        raise ValueError("Input changed during preparation")
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("observations.json", observations)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "checkpoints.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in checkpoints), encoding="utf-8")
    (args.output / "report.md").write_text(report, encoding="utf-8")
    manifest = {
        "schema_version": 1, "status": "prepared_pending_review", "model_calls": 0,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence": summary["evidence"], "uses_held_out_data": False,
        "input_sha256": INPUT_HASHES, "source_sha256": source_hashes,
        "tokenizer_path": str(tokenizer_path), "tokenizer_sha256": tokenizer_hash,
        "tokenizer_scope": "local CPU retokenization only; no model weights or generation token IDs",
        "menu": MENU, "boundary_rule": "interior_sentence_punctuation_v1",
        "development_split_seed": 42, "human_review_status": "pending",
        "future_model_execution_authorized": False, "stage0_changed": False,
        "artifact_sha256": {name: sha256_file(args.output / name) for name in ("summary.json", "observations.json", "checkpoints.jsonl", "report.md")},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("cot_traces", "canonical_questions", "checkpoint_rows", "checkpoint_review_candidates", "candidate_wrong", "model_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
