"""Matched training sets for the trace-source factor: the base model's own traces vs converted human solutions.

Both sets use the same questions: those where the base model (`base_prefill`) wrote a trace that `keep` accepts.
Only the trace differs, so a difference between the two adapters is about where the trace came from.

    python -m structured_llm.self_traces items N OUT.jsonl      # first N train questions, for evaluate
    python -m structured_llm.self_traces build EVAL.jsonl OUT_DIR  # after evaluate --modes base_prefill
"""

import collections
import json
from pathlib import Path
import shutil
import sys

from structured_llm import gsm8k

VALID = Path("data/structured_gsm8k_enriched_v1/valid.jsonl")


def train_items(n):
    """First n train questions (rank_key order) that also have a converted human trace."""
    items = []
    for row in gsm8k.load_splits()[0]:
        if gsm8k.convert(row, enrich_step1=True)[0] is None:
            continue
        items.append({"id": gsm8k.rank_key(row["question"])[:16], "question": row["question"],
                      "answer": gsm8k.gold_answer(row["answer"])})
        if len(items) == n:
            break
    return items


def keep(record):
    """Return None if this base_prefill record is usable as a training trace, else a short reason."""
    check = record["check"]
    if record["truncated"]:
        return "truncated"
    if not check["format_valid"] or check["errors"]:
        return "bad_format"
    if not check["correct"]:
        return "wrong_answer"
    if check["calc_accuracy"] != 1.0:
        return "wrong_calc"  # strict: a right answer reached through a wrong Calc would teach ignoring steps
    return None


def build(eval_path, out_dir, valid=VALID):
    records = [json.loads(line) for line in Path(eval_path).read_text().splitlines() if line.strip()]
    rows = {gsm8k.rank_key(row["question"])[:16]: row for row in gsm8k.load_splits()[0]}
    reasons, self_rows, human_rows = collections.Counter(), [], []
    for record in records:
        reason = keep(record)
        if reason:
            reasons[reason] += 1
            continue
        row = rows[record["id"]]
        human, _ = gsm8k.convert(row, enrich_step1=True)
        self_rows.append(gsm8k.training_row(row, record["output"].strip()))
        human_rows.append(gsm8k.training_row(row, human))

    out = Path(out_dir)
    manifest = {"eval": str(eval_path), "records": len(records), "kept": len(self_rows), "dropped": dict(reasons)}
    for name, train in (("self", self_rows), ("human", human_rows)):
        (out / name).mkdir(parents=True, exist_ok=True)
        manifest[f"{name}_train_sha256"] = gsm8k.write_jsonl(out / name / "train.jsonl", train)
        shutil.copyfile(valid, out / name / "valid.jsonl")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv):
    if argv[:1] == ["items"]:
        items = train_items(int(argv[1]))
        Path(argv[2]).write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items))
        print(json.dumps({"items": len(items)}))
    elif argv[:1] == ["build"]:
        print(json.dumps(build(argv[1], argv[2])))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
