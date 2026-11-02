"""Convert GSM8K train solutions into structured traces and split them.

Run: python -m structured_llm.gsm8k

The official GSM8K test file is never read. The 120 questions already used for
development are excluded. Splits are assigned by hash rank before any filtering,
so the held-out sets do not depend on labels or on whether conversion succeeds.
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from .trace import Step, calc_is_correct, check, render

SOURCE = Path("data/gsm8k_source/train.jsonl")
SOURCE_SHA256 = "17f347dc51477c50d4efb83959dbb7c56297aba886e5544ee2aaed3024813465"
USED_FOR_DEVELOPMENT = (
    "data/gsm8k_development_v1/dataset.json",
    "data/gsm8k_development_validation_candidate_v1/dataset.json",
)
OUTPUT = Path("data/structured_gsm8k_v1")
SEED = "structured-gsm8k-v1"
N_VALID, N_DEV = 100, 100

_ANNOTATION = re.compile(r"<<(.*?)>>")
_FINAL = re.compile(r"####\s*(.+)")


def normalize(question):
    return " ".join(question.lower().split())


def rank_key(question):
    return hashlib.sha256(f"{SEED}:{normalize(question)}".encode()).hexdigest()


def gold_answer(solution):
    return _FINAL.search(solution)[1].strip().replace(",", "").replace("$", "")


def convert(row):
    """Return (trace text, None), or (None, reason) if the solution doesn't qualify."""
    steps = []
    for line in row["answer"].split("\n"):
        if line.startswith("####"):
            continue
        calcs = []
        for annotation in _ANNOTATION.findall(line):
            expr, _, result = annotation.rpartition("=")
            calcs.append((expr.strip(), result.strip()))
        prose = " ".join(_ANNOTATION.sub("", line).split())
        if prose:
            steps.append(Step(prose, calcs))
        elif calcs:
            return None, "calc_without_prose"
    if not any(step.calcs for step in steps):
        return None, "no_annotations"
    if not all(calc_is_correct(*calc) for step in steps for calc in step.calcs):
        return None, "wrong_or_unparsable_annotation"
    text = render(steps, gold_answer(row["answer"]))
    if check(text, row["question"])["errors"]:
        return None, "fails_own_grammar"
    return text, None


def chatml_prompt(user):
    """Qwen3 chat template with thinking enabled, so the trace is its thinking."""
    return f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"


def training_row(row, trace):
    return {"text": f"{chatml_prompt(row['question'])}{trace}<|im_end|>"}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else None


def used_questions():
    used = set()
    for path in USED_FOR_DEVELOPMENT:
        used |= {normalize(item["query"]) for item in json.loads(Path(path).read_text())["items"]}
    return used


def load_splits(source=SOURCE):
    """Return (train, valid, dev) source rows, with all excluded questions removed."""
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise SystemExit(f"{source} does not match the pinned SHA-256")
    rows = [json.loads(line) for line in raw.decode().splitlines()]

    used = used_questions()
    pool = sorted((row for row in rows if normalize(row["question"]) not in used),
                  key=lambda row: rank_key(row["question"]))
    excluded = len(rows) - len(pool)
    if excluded != len(used):
        raise SystemExit(f"excluded {excluded} rows for {len(used)} development questions")

    return pool[N_VALID + N_DEV:], pool[:N_VALID], pool[N_VALID:N_VALID + N_DEV]


def build(source=SOURCE, output=OUTPUT):
    train, valid, dev = load_splits(source)
    rows = len(train) + len(valid) + len(dev)

    dropped = collections.Counter()
    def converted(split):
        kept = []
        for row in split:
            trace, reason = convert(row)
            if trace is None:
                dropped[reason] += 1
            else:
                kept.append((row, trace))
        return kept

    train_kept, valid_kept = converted(train), converted(valid)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    hashes = {
        "train.jsonl": write_jsonl(output / "train.jsonl", [training_row(*pair) for pair in train_kept]),
        "valid.jsonl": write_jsonl(output / "valid.jsonl", [training_row(*pair) for pair in valid_kept]),
        "dev.jsonl": write_jsonl(output / "dev.jsonl", [
            {"id": rank_key(row["question"])[:16], "question": row["question"],
             "answer": gold_answer(row["answer"])} for row in dev]),
    }

    # What a perfect gold trace scores: the ceiling for the soft metrics.
    gold = [check(trace, row["question"], gold_answer(row["answer"])) for row, trace in train_kept]
    manifest = {
        "source_sha256": SOURCE_SHA256,
        "source_rows": rows + len(used_questions()),
        "excluded_development_questions": len(used_questions()),
        "official_test_read": False,
        "seed": SEED,
        "split_rows": {"train": len(train), "valid": len(valid), "dev": len(dev)},
        "converted_rows": {"train": len(train_kept), "valid": len(valid_kept)},
        "dropped": dict(dropped),
        "gold_ceiling": {
            "calc_accuracy": _mean(item["calc_accuracy"] for item in gold),
            "grounded_rate": _mean(item["grounded_rate"] for item in gold),
            "answer_from_last_calc": _mean(float(item["answer_from_last_calc"]) for item in gold),
            "correct": _mean(float(item["correct"]) for item in gold),
        },
        "sha256": hashes,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))
