"""Build the two 131-row MATH datasets for the clean one-step ablation.

Both come from data/structured_math_term_v1, where no training row is cut at 512 tokens.
The treatment keeps every row with >= 2 steps; the control is a random sample of the
same size that still contains one-step rows. Both then get the same number of passes.
"""

import json
from pathlib import Path
import random

from build_math_multistep_dataset import count_steps_in_think

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data/structured_math_term_v1"
TREATMENT_DIR = ROOT / "data/structured_math_term_multistep131_v1"
CONTROL_DIR = ROOT / "data/structured_math_term_random131_v1"
SEED = "structured-math-term-random131-v1"


def write_dataset(directory, rows, source_rows, rule):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "train.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    valid = (SRC_DIR / "valid.jsonl").read_text()
    (directory / "valid.jsonl").write_text(valid)
    one_step = sum(count_steps_in_think(row["text"]) == 1 for row in rows)
    manifest = {
        "source_dir": str(SRC_DIR.relative_to(ROOT)),
        "rule": rule,
        "source_train": source_rows,
        "train": len(rows),
        "train_one_step": one_step,
        "valid": len(valid.splitlines()),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


def main():
    rows = [json.loads(line) for line in (SRC_DIR / "train.jsonl").read_text().splitlines() if line.strip()]
    treatment = [row for row in rows if count_steps_in_think(row["text"]) >= 2]
    control = random.Random(SEED).sample(rows, len(treatment))
    write_dataset(TREATMENT_DIR, treatment, len(rows), "steps >= 2")
    write_dataset(CONTROL_DIR, control, len(rows), f"random sample, seed {SEED}")


if __name__ == "__main__":
    main()
