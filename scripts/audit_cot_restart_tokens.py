"""Audit historical text/count compatibility with a pinned local tokenizer only.

No network, MLX import, model weights, or historical writes. Reconstructed IDs
are diagnostics, never promoted to original generated IDs.
"""

from __future__ import annotations

import argparse
from collections import Counter
from importlib.metadata import version
import hashlib
import json
from pathlib import Path

from experiments.cot_restart_addendum import DEFAULT_HISTORICAL_DIR, verify_historical_run
from experiments.cot_restart_pilot import MODEL_FILE_HASHES, MODEL_REVISION, file_sha256


def audit_rows(rows: list[dict], tokenizer) -> dict:
    observations = []
    for row in rows:
        text = row["raw_output"]
        ids = tokenizer.encode(text, add_special_tokens=False).ids
        recorded = row["completion_tokens"]
        # Installed MLX-LM 0.31.3 counts terminal EOS, but its text omits EOS.
        # Historical backend version is absent; this remains an explicit assumption.
        eos_adjustment = int(row["finish_reason"] == "stop")
        decoded = tokenizer.decode(ids, skip_special_tokens=False)
        observations.append({
            "key": row["key"],
            "finish_reason": row["finish_reason"],
            "recorded_completion_tokens": recorded,
            "retokenized_visible_tokens": len(ids),
            "eos_adjustment": eos_adjustment,
            "literal_count_match": len(ids) == recorded,
            "eos_adjusted_count_match": len(ids) + eos_adjustment == recorded,
            "roundtrip_match": decoded == text,
            "raw_output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        })
    total = len(observations)
    literal = sum(r["literal_count_match"] for r in observations)
    adjusted = sum(r["eos_adjusted_count_match"] for r in observations)
    roundtrip = sum(r["roundtrip_match"] for r in observations)
    return {
        "rows": total,
        "literal_count_matches": literal,
        "eos_adjusted_count_matches": adjusted,
        "roundtrip_matches": roundtrip,
        "T5_eos_aware_pass": total > 0 and adjusted == total and roundtrip == total,
        "historical_backend_version_verified": False,
        "original_token_identity_verified": False,
        "recorded_minus_retokenized_counts": dict(Counter(
            str(r["recorded_completion_tokens"] - r["retokenized_visible_tokens"])
            for r in observations
        )),
        "observations": observations,
    }


def run_audit(historical_dir: Path, tokenizer_dir: Path, output_dir: Path) -> dict:
    historical_dir, tokenizer_dir, output_dir = (
        Path(p).resolve() for p in (historical_dir, tokenizer_dir, output_dir)
    )
    if output_dir == historical_dir or output_dir.is_relative_to(historical_dir):
        raise ValueError("audit output must be outside the historical directory")
    if output_dir.exists():
        raise FileExistsError("use a new audit output directory")
    manifest = verify_historical_run(historical_dir)
    tokenizer_hashes = {}
    for name in ("tokenizer.json", "tokenizer_config.json"):
        digest = file_sha256(tokenizer_dir / name)
        if digest != MODEL_FILE_HASHES[name]:
            raise ValueError(f"pinned tokenizer hash mismatch: {name}")
        tokenizer_hashes[name] = digest
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
    rows = []
    for line in (historical_dir / "calls.jsonl").read_text().splitlines():
        entry = json.loads(line)
        value = entry["value"]
        if "raw_output" in value and value.get("finish_reason") in ("stop", "length"):
            rows.append({"key": [entry["kind"], *entry["key"]], **value})
    result = {
        "evidence": "exposed_development_tokenizer_audit",
        "model_calls": 0,
        "network_downloads": 0,
        "tokenizer_loader": "tokenizers.Tokenizer.from_file",
        "tokenizers_version": version("tokenizers"),
        "tokenizer_dir": str(tokenizer_dir),
        "tokenizer_hashes": tokenizer_hashes,
        "historical_dir": str(historical_dir),
        "historical_journal_head": manifest["journal_head"],
        "source_sha256": file_sha256(Path(__file__)),
        "eos_counting_assumption": "one omitted EOS for finish_reason=stop; zero for length",
        **audit_rows(rows, tokenizer),
    }
    result["legacy_replay_status"] = (
        "requires_original_id_provenance_review" if result["T5_eos_aware_pass"]
        else "blocked_count_or_roundtrip_mismatch"
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "token_audit.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    mismatches = [r for r in result["observations"]
                  if not r["eos_adjusted_count_match"] or not r["roundtrip_match"]]
    report = [
        "# CoT restart legacy token audit", "",
        "Exposed development; tokenizer only, no model calls or downloads. Stage 0 unchanged.", "",
        f"- Completions: {result['rows']} (including smoke calls).",
        f"- Literal token-count matches: {result['literal_count_matches']}/{result['rows']}.",
        f"- EOS-adjusted token-count matches: {result['eos_adjusted_count_matches']}/{result['rows']}.",
        f"- Text roundtrips: {result['roundtrip_matches']}/{result['rows']}.",
        f"- T5 EOS-aware gate: {'PASS' if result['T5_eos_aware_pass'] else 'FAIL'}.", "",
        "The EOS adjustment assumes the installed MLX-LM 0.31.3 convention. The historical",
        "backend version was not recorded. Matching counts and text would still not prove",
        "original token identity. No reconstructed sequence is stored as original IDs.", "",
        "Legacy arms remain at their collected caps. M/D paired replay is unavailable until",
        "every compared arm has an accepted token record. An ID-bearing addendum alone does",
        "not make the historical A/F arms eligible. +/-8 sensitivity cannot repair a failed T5.", "",
        "| Journal key | Finish | Recorded | Visible re-encode | EOS adjustment |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in mismatches:
        report.append(f"| {' / '.join(row['key'])} | {row['finish_reason']} | "
                      f"{row['recorded_completion_tokens']} | {row['retokenized_visible_tokens']} | "
                      f"{row['eos_adjustment']} |")
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL_DIR)
    parser.add_argument("--tokenizer-dir", type=Path, default=Path.home() / ".cache/huggingface/hub"
                        / "models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots" / MODEL_REVISION)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_audit(args.historical, args.tokenizer_dir, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "observations"}, indent=2))


if __name__ == "__main__":
    main()
