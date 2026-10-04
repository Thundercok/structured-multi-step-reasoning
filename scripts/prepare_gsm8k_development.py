"""Freeze a label-independent GSM8K training-only development sample; no inference."""

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from experiments.research_pilot import sha256_file
from experiments.research_study import normalized_text, validate_dataset, write_json


def parse_gold(solution):
    parts = solution.split("####")
    if len(parts) != 2:
        raise ValueError("Expected exactly one GSM8K final-answer delimiter")
    value = parts[1].strip()
    if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", value):
        raise ValueError("Expected a complete numeric GSM8K gold")
    return format(Decimal(value.replace(",", "")).normalize(), "f")


def build_items(rows, revision, count=24, seed=42):
    if count < 2 or count % 2:
        raise ValueError("Use a positive even count for equal development splits")
    unique = {}
    for index, row in enumerate(rows, 1):
        if not isinstance(row.get("question"), str) or not row["question"].strip():
            raise ValueError("Source row has no question")
        identity = hashlib.sha256(normalized_text(row["question"]).encode()).hexdigest()
        unique.setdefault(identity, (index, row))
    if len(unique) < count:
        raise ValueError("Not enough distinct training questions")
    ranked = sorted(unique, key=lambda identity: (
        hashlib.sha256(f"{seed}:gsm8k-development:{identity}".encode()).hexdigest(), identity))[:count]
    items, review = [], []
    for position, identity in enumerate(ranked):
        index, row = unique[identity]
        item = {"id": f"gsm8k-dev-{index:05d}", "group_id": f"gsm8k-train-{identity}",
            "split": "train" if position % 2 == 0 else "calibration", "category": "gsm8k",
            "query": row["question"], "answer": parse_gold(row["answer"]),
            "answer_type": "number", "tolerance": 0,
            "source_provenance": {"repository": "openai/grade-school-math", "revision": revision,
                "original_split": "train", "path": "grade_school_math/data/train.jsonl",
                "line_1based": index, "question_sha256": hashlib.sha256(row["question"].encode()).hexdigest()}}
        items.append(item)
        review.append({"id": item["id"], "source_solution": row["answer"], "human_review_status": "pending"})
    return items, review, {"seed": seed, "selection": "SHA-256 ranking of normalized question identity; no labels or outcomes",
        "grouping": "exact normalized question identity; semantic duplicates require review",
        "source_rows": len(rows), "unique_normalized_queries": len(unique), "selected_groups": count,
        "split_assignment": "alternate rank positions: equal train/calibration; both exposed development"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    source = json.loads((args.source / "manifest.json").read_text())
    if source["repository"] != "openai/grade-school-math" or source["official_test_downloaded"] is not False:
        raise ValueError("Expected official training-only source")
    if source["files"]["train.jsonl"]["remote_path"] != "grade_school_math/data/train.jsonl":
        raise ValueError("Only the official training file may enter this pilot")
    for name, metadata in source["files"].items():
        if name not in ("train.jsonl", "LICENSE", "README.md") or sha256_file(args.source / name) != metadata["sha256"]:
            raise ValueError("Source file changed or includes an unexpected path")
    rows = [json.loads(line) for line in (args.source / "train.jsonl").read_text().splitlines()]
    items, review, selection = build_items(rows, source["revision"], args.count, args.seed)
    dataset = {"name": "gsm8k-training-development", "version": "1", "role": "development_tuning",
        "source": f"https://github.com/openai/grade-school-math/tree/{source['revision']}",
        "license": "MIT; upstream LICENSE preserved in the source audit", "human_review_status": "pending",
        "official_test_used": False, "items": items}
    validate_dataset(dataset, pilot=True)
    args.output.mkdir(parents=True)
    write_json(args.output / "dataset.json", dataset)
    write_json(args.output / "review.json", review)
    write_json(args.output / "manifest.json", {"kind": "gsm8k_training_only_development_preparation",
        "source_manifest_sha256": sha256_file(args.source / "manifest.json"),
        "source_revision": source["revision"], "source_sha256": sha256_file(Path(__file__)),
        "dataset_sha256": sha256_file(args.output / "dataset.json"), "selection": selection,
        "new_model_calls": 0, "official_test_used": False, "human_review_status": "pending", "publication_ready": False})
    print(args.output / "dataset.json")


if __name__ == "__main__":
    main()
