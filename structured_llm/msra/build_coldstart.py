"""Build the complete MSRA Stage 1 Structural Cold-Start SFT dataset.

Combines verified traces from structured GSM8K and MATH checkable subsets,
validating 100% DAG correctness and producing deterministic train/valid splits.

Run: python -m structured_llm.msra.build_coldstart
"""

import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .convert_traces import convert_chatml_row
from .trace_parser import parse_trace

GSM8K_TRAIN = Path("data/structured_gsm8k_enriched_v1/train.jsonl")
GSM8K_VALID = Path("data/structured_gsm8k_enriched_v1/valid.jsonl")
MATH_TRAIN = Path("data/math_source/structured_math_v1/train.jsonl")
MATH_VALID = Path("data/math_source/structured_math_v1/valid.jsonl")
OUTPUT_DIR = Path("data/structured_msra_coldstart_v1")


def process_file(file_path: Path, source_label: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Convert and strictly validate rows from a source JSONL file."""
    if not file_path.exists():
        return [], {"error_file_not_found": 1}

    rows: List[Dict[str, Any]] = []
    stats = collections.Counter()

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats["total_read"] += 1
            data = json.loads(line)
            row_text = data.get("text", "")
            converted_text = convert_chatml_row(row_text)

            if converted_text is None:
                stats["skipped_conversion"] += 1
                continue

            # Strict validation
            validation = parse_trace(converted_text)
            if not validation.is_valid:
                stats["rejected_dag_validation"] += 1
                continue

            row_id = data.get("id") or hashlib.sha256(row_text.encode()).hexdigest()[:16]
            rows.append({
                "id": f"{source_label}_{row_id}",
                "source": source_label,
                "text": converted_text,
                "steps": len(validation.nodes),
            })
            stats["converted_valid"] += 1

    return rows, dict(stats)


def build(output_dir: Path = OUTPUT_DIR) -> Dict[str, Any]:
    """Build the merged MSRA Cold-Start SFT dataset."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Process GSM8K
    gsm8k_train_rows, gsm8k_train_stats = process_file(GSM8K_TRAIN, "gsm8k")
    gsm8k_valid_rows, gsm8k_valid_stats = process_file(GSM8K_VALID, "gsm8k")

    # 2. Process MATH checkable
    math_train_rows, math_train_stats = process_file(MATH_TRAIN, "math")
    math_valid_rows, math_valid_stats = process_file(MATH_VALID, "math")

    # Combine
    all_train = gsm8k_train_rows + math_train_rows
    all_valid = gsm8k_valid_rows + math_valid_rows

    train_out = output_dir / "train.jsonl"
    valid_out = output_dir / "valid.jsonl"

    with open(train_out, "w", encoding="utf-8") as f:
        for r in all_train:
            f.write(json.dumps({"id": r["id"], "source": r["source"], "text": r["text"]}, ensure_ascii=False) + "\n")

    with open(valid_out, "w", encoding="utf-8") as f:
        for r in all_valid:
            f.write(json.dumps({"id": r["id"], "source": r["source"], "text": r["text"]}, ensure_ascii=False) + "\n")

    # Compute sha256
    train_hash = hashlib.sha256(train_out.read_bytes()).hexdigest()
    valid_hash = hashlib.sha256(valid_out.read_bytes()).hexdigest()

    manifest = {
        "dataset_name": "structured_msra_coldstart_v1",
        "description": "Stage 1 Structural Cold-Start SFT dataset combining GSM8K and MATH checkable in MSRA XML format",
        "counts": {
            "train_total": len(all_train),
            "train_gsm8k": len(gsm8k_train_rows),
            "train_math": len(math_train_rows),
            "valid_total": len(all_valid),
            "valid_gsm8k": len(gsm8k_valid_rows),
            "valid_math": len(math_valid_rows),
        },
        "stats": {
            "gsm8k_train": gsm8k_train_stats,
            "gsm8k_valid": gsm8k_valid_stats,
            "math_train": math_train_stats,
            "math_valid": math_valid_stats,
        },
        "sha256": {
            "train.jsonl": train_hash,
            "valid.jsonl": valid_hash,
        },
    }

    manifest_out = output_dir / "manifest.json"
    manifest_out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


if __name__ == "__main__":
    report = build()
    print(json.dumps(report, indent=2))
