"""Build the filtered multi-step MATH dataset (>= 2 steps only).

Filters data/math_source/structured_math_v1/train.jsonl to retain only
items with >= 2 explicit Step headers inside <think>.
Outputs to data/math_source/structured_math_multistep_v1/.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data/math_source/structured_math_v1"
DST_DIR = ROOT / "data/math_source/structured_math_multistep_v1"


def count_steps_in_think(text: str) -> int:
    start = text.find("<think>")
    end = text.find("</think>")
    if start == -1 or end == -1:
        return 0
    think_text = text[start:end]
    return sum(1 for line in think_text.splitlines() if line.strip().startswith("Step "))


def build_multistep_dataset():
    DST_DIR.mkdir(parents=True, exist_ok=True)

    src_train = SRC_DIR / "train.jsonl"
    dst_train = DST_DIR / "train.jsonl"

    all_train = [json.loads(line) for line in src_train.read_text().splitlines() if line.strip()]
    multistep_train = [row for row in all_train if count_steps_in_think(row["text"]) >= 2]

    with dst_train.open("w", encoding="utf-8") as f:
        for row in multistep_train:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Copy valid.jsonl directly
    src_valid = SRC_DIR / "valid.jsonl"
    dst_valid = DST_DIR / "valid.jsonl"
    dst_valid.write_text(src_valid.read_text())

    # Write manifest
    manifest = {
        "dataset_name": "structured_math_multistep_v1",
        "description": "Filtered MATH Level 3-5 dataset containing strictly >=2 steps",
        "source_control": str(SRC_DIR),
        "total_source_train": len(all_train),
        "filtered_train_samples": len(multistep_train),
        "filtered_out_1step_samples": len(all_train) - len(multistep_train),
        "valid_samples": len(src_valid.read_text().splitlines()),
        "rationale": "Ablation test against the Flat-Trace Bottleneck & Step 1 monologue truncation loop",
    }
    (DST_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"[Ablation Data] Created {DST_DIR}")
    print(f"[Ablation Data] Filtered: {len(all_train)} -> {len(multistep_train)} train rows (252 expected)")
    print(f"[Ablation Data] Valid rows: {manifest['valid_samples']} (identical to control)")
    print(f"[Ablation Data] Saved manifest.json")


if __name__ == "__main__":
    build_multistep_dataset()
