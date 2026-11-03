"""Select the checkable part of MATH train and split it.

Run: python -m structured_llm.math_data

A problem qualifies if its reference solution, at level 3 to 5, has at least two equations
SymPy confirms and they reach its boxed answer. Selection uses reference solutions only, never
model outputs, and splits are assigned by hash rank. The subset is easier to check by construction
and does not represent all of MATH. Problem text isn't committed; only this manifest is.
"""

import argparse
import collections
import hashlib
import json
import warnings
from pathlib import Path

from .math_check import HARD_LEVELS, SOURCE, boxed_answer, check_text, is_covered

OUTPUT = Path("data/math_source/structured_math_v1")
REVISION_FILE = Path("data/math_source/REVISION")
SEED = "structured-math-v1"
N_DEV = 500


def rank_key(problem):
    return hashlib.sha256(f"{SEED}:{' '.join(problem.lower().split())}".encode()).hexdigest()


def select(rows):
    """Return the qualifying rows in rank order."""
    kept = [row for row in rows if row["level"] in HARD_LEVELS and is_covered(check_text(row["solution"]))]
    return sorted(kept, key=lambda row: rank_key(row["problem"]))


def as_item(row):
    return {"id": row["id"], "question": row["problem"], "answer": boxed_answer(row["solution"]),
            "answer_format": "latex", "subject": row["subject"], "level": row["level"]}


def build(source=SOURCE, output=OUTPUT):
    rows = [json.loads(line) for line in Path(source).read_text().splitlines()]
    kept = select(rows)
    dev, train = kept[:N_DEV], kept[N_DEV:]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "dev.jsonl").write_text("".join(json.dumps(as_item(row), ensure_ascii=False) + "\n" for row in dev))
    (output / "train_source.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in train))
    count = lambda items, key: dict(sorted(collections.Counter(item[key] for item in items).items()))
    return {
        "source_revision": REVISION_FILE.read_text().strip() if REVISION_FILE.exists() else None,
        "source_rows": len(rows),
        "hard_rows": sum(row["level"] in HARD_LEVELS for row in rows),
        "qualifying_rows": len(kept),
        "test_split_read": False,
        "seed": SEED,
        "dev": len(dev),
        "train": len(train),
        "dev_by_subject": count(dev, "subject"),
        "dev_by_level": count(dev, "level"),
        "sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                   for name in ("dev.jsonl", "train_source.jsonl")},
    }


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="audit/math_coverage_20261103/subset_manifest.json")
    args = parser.parse_args()
    manifest = build()
    Path(args.manifest).write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
