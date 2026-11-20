"""Pre-training check for trace-source dose datasets (0, 25, 50, 75, 100%).

Verifies exact prompt/order alignment, strict nesting of human-trace indices, exact counts,
zero off-format rows, and zero rows over 512 tokens. Exits 1 on any mismatch.
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
EXPECTED_COUNTS = {"0": 0, "25": 57, "50": 114, "75": 172, "100": 229}


def rows(path):
    return [json.loads(line)["text"] for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    src_dir = Path(sys.argv[1])
    mix_dir = Path(sys.argv[2])
    tok = AutoTokenizer.from_pretrained(MODEL)

    sets = {
        "0": rows(src_dir / "self/train.jsonl"),
        "25": rows(mix_dir / "mix25/train.jsonl"),
        "50": rows(mix_dir / "mix50/train.jsonl"),
        "75": rows(mix_dir / "mix75/train.jsonl"),
        "100": rows(src_dir / "human/train.jsonl"),
    }
    problems = []
    n = len(sets["0"])
    if any(len(v) != n for v in sets.values()):
        problems.append("row counts differ across ratios")

    base_prompts = [t.split(SPLIT, 1)[0] for t in sets["0"]]
    for k, texts in sets.items():
        if [t.split(SPLIT, 1)[0] for t in texts] != base_prompts:
            problems.append(f"ratio {k}: prompts differ or out of order")

    prev_human = set()
    report = {"n_rows": n, "ratios": {}}
    for k in ("0", "25", "50", "75", "100"):
        texts = sets[k]
        human_idx = set()
        for i, t in enumerate(texts):
            if t == sets["100"][i]:
                human_idx.add(i)
            elif t != sets["0"][i]:
                problems.append(f"ratio {k} row {i}: matches neither self nor human")
        if len(human_idx) != EXPECTED_COUNTS[k]:
            problems.append(f"ratio {k}: human count {len(human_idx)} != {EXPECTED_COUNTS[k]}")
        if not prev_human.issubset(human_idx):
            problems.append(f"ratio {k}: nesting invariant broken")
        prev_human = human_idx

        traces = [t.split(SPLIT, 1)[1] for t in texts]
        bad = sum(not (tr.startswith("<think>\nStep 1:") and "\n</think>\n" in tr and "Answer:" in tr
                       and tr.endswith("<|im_end|>") and tr.count("<|im_end|>") == 1) for tr in traces)
        if bad:
            problems.append(f"ratio {k}: {bad} rows off format")
        lengths = [len(tok.encode(t)) for t in texts]
        q = statistics.quantiles(lengths, n=10)
        over = sum(m > MAX_SEQ for m in lengths)
        if over:
            problems.append(f"ratio {k}: {over} rows over {MAX_SEQ} tokens")
        report["ratios"][k] = {
            "human_count": len(human_idx),
            "off_format": bad,
            "tokens_mean": round(statistics.mean(lengths), 1),
            "tokens_median": statistics.median(lengths),
            "tokens_p10": q[0],
            "tokens_p90": q[-1],
            "tokens_max": max(lengths),
            f"over_{MAX_SEQ}": over,
        }

    report["problems"] = problems
    print(json.dumps(report, indent=2))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
