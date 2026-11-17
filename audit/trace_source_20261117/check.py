"""Checks before training (docs/trace_source_prereg.md): matched rows, matching format, token counts.

Usage: check.py DATA_DIR  (holds self/train.jsonl and human/train.jsonl). Exits 1 on a mismatch.
Reads only structure and lengths, not the content of individual traces.
"""

import json
from pathlib import Path
import statistics
import sys

from transformers import AutoTokenizer

MODEL = (Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/"
         "545dc4251c05440727734bcd94334791f6ab0192")
MAX_SEQ = 512
SPLIT = "<|im_start|>assistant\n"


def rows(path):
    return [json.loads(line)["text"] for line in path.read_text().splitlines() if line.strip()]


def main():
    data = Path(sys.argv[1])
    tok = AutoTokenizer.from_pretrained(MODEL)
    sets = {name: rows(data / name / "train.jsonl") for name in ("self", "human")}
    problems = []
    if len(sets["self"]) != len(sets["human"]):
        problems.append("row counts differ")
    prompts = {name: [t.split(SPLIT, 1)[0] for t in texts] for name, texts in sets.items()}
    if prompts["self"] != prompts["human"]:
        problems.append("prompts differ or are in a different order")
    report = {"rows": {k: len(v) for k, v in sets.items()}}
    for name, texts in sets.items():
        traces = [t.split(SPLIT, 1)[1] for t in texts]
        bad = sum(not (tr.startswith("<think>\nStep 1:") and "\n</think>\n" in tr and "Answer:" in tr
                       and tr.endswith("<|im_end|>") and tr.count("<|im_end|>") == 1) for tr in traces)
        if bad:
            problems.append(f"{name}: {bad} rows off format")
        lengths = [len(tok.encode(t)) for t in texts]
        q = statistics.quantiles(lengths, n=10)
        report[name] = {"off_format": bad, "tokens_mean": round(statistics.mean(lengths), 1),
                        "tokens_median": statistics.median(lengths), "tokens_p10": q[0], "tokens_p90": q[-1],
                        "tokens_max": max(lengths), f"over_{MAX_SEQ}": sum(n > MAX_SEQ for n in lengths)}
    report["problems"] = problems
    print(json.dumps(report, indent=2))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
