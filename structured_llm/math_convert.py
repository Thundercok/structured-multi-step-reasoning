"""Convert MATH train source solutions into structured traces with SymPy verified steps.

Run: python -m structured_llm.math_convert

Reads the 801 checkable training problems from data/math_source/structured_math_v1/train_source.jsonl,
converts each solution into Step and Calc blocks, verifies that calculations hold,
and exports ChatML training rows for model fine-tuning.
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from .gsm8k import chatml_prompt
from .math_check import boxed_answer, equations, is_trivial
from .trace import Step, calc_is_correct, parse, render

SOURCE = Path("data/math_source/structured_math_v1/train_source.jsonl")
OUTPUT_DIR = Path("data/math_source/structured_math_v1")


def clean_prose(text):
    """Clean markdown and LaTeX formatting for human-readable step text."""
    text = re.sub(r"\$\s*\\boxed\{[^{}]*\}\s*\$", "", text)
    text = re.sub(r"\\boxed\{[^{}]*\}", "", text)
    text = re.sub(r"\$\s*\$", "", text)
    return " ".join(text.split()).strip()


def convert_math_solution(row):
    """Return (trace text, None) or (None, reason) if the row cannot be structured."""
    sol = row.get("solution", "")
    ans = boxed_answer(sol)
    if not ans:
        return None, "no_boxed_answer"

    # Split solution into paragraph-level logical reasoning blocks
    paras = [p.strip() for p in re.split(r"\n\s*\n", sol) if p.strip()]
    steps = []
    for p in paras:
        p_clean_eq = re.sub(r"\\boxed\{([^{}]*)\}", r"\1", p)
        eqs = list(equations(p_clean_eq))
        calcs = []
        for l, r in eqs:
            if not is_trivial(l, r) and calc_is_correct(l, r):
                calcs.append((l.strip(), r.strip()))
        prose = clean_prose(p)
        if prose or calcs:
            steps.append(Step(prose or "Simplify and calculate.", calcs))

    if not steps:
        return None, "no_steps"
    if not any(step.calcs for step in steps):
        return None, "no_calcs"

    trace_text = render(steps, ans)
    parsed = parse(trace_text)
    if parsed.errors:
        return None, f"grammar_errors_{'_'.join(parsed.errors)}"
    return trace_text, None


def training_row(row, trace):
    return {"id": row["id"], "text": f"{chatml_prompt(row['problem'])}{trace}<|im_end|>"}


def build(source_path=SOURCE, output_dir=OUTPUT_DIR):
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(line) for line in source_path.read_text().splitlines()]
    converted_rows = []
    rejections = collections.Counter()

    for row in rows:
        trace, reason = convert_math_solution(row)
        if trace:
            converted_rows.append(training_row(row, trace))
        else:
            rejections[reason] += 1

    train_rows = []
    valid_rows = []
    for r in converted_rows:
        h = int(hashlib.sha256(r["id"].encode()).hexdigest(), 16)
        if h % 10 == 0:
            valid_rows.append(r)
        else:
            train_rows.append(r)

    train_out = output_dir / "train.jsonl"
    valid_out = output_dir / "valid.jsonl"
    train_out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in train_rows))
    valid_out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in valid_rows))

    manifest = {
        "source": str(source_path),
        "source_rows": len(rows),
        "converted": len(converted_rows),
        "conversion_rate": round(len(converted_rows) / max(len(rows), 1), 4),
        "split_rows": {"train": len(train_rows), "valid": len(valid_rows)},
        "rejections": dict(sorted(rejections.items())),
        "sha256": {
            "train.jsonl": hashlib.sha256(train_out.read_bytes()).hexdigest(),
            "valid.jsonl": hashlib.sha256(valid_out.read_bytes()).hexdigest(),
        },
    }
    manifest_out = output_dir / "manifest_converted.json"
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    manifest = build(args.source, args.output)
    print(json.dumps(manifest, indent=2))
