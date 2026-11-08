"""Aggregate metrics across multiple random seeds (s0, s1, s2) for GSM8K Enriched LoRA.

Computes Mean ± Std for:
- Dev-100 zero-prefill accuracy
- Format validity rate
- Causal following rate under intervention
Outputs summary JSON and updates Markdown reports.
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics
from typing import Dict, List, Any

DIR = Path(__file__).parent

SEEDS = ["s0", "s1", "s2"]
EVAL_DIRS = {
    "s0": DIR / "eval_cf",
    "s1": DIR / "eval_cf_s1",
    "s2": DIR / "eval_cf_s2",
}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def summarize_seed(eval_dir: Path) -> Dict[str, Any]:
    tuned_file = eval_dir / "tuned.jsonl"
    int_file = eval_dir / "interventions_summary.json"
    if not tuned_file.exists():
        return {}

    rows = read_jsonl(tuned_file)
    n = len(rows)
    if n == 0:
        return {}

    correct = sum(bool(r.get("check", {}).get("correct")) for r in rows)
    format_valid = sum(bool(r.get("check", {}).get("format_valid")) for r in rows)

    following_rate = None
    if int_file.exists():
        try:
            int_data = json.loads(int_file.read_text(encoding="utf-8"))
            eligible = int_data.get("tuned", {}).get("eligible", {})
            n_el = eligible.get("n", 0)
            if n_el > 0:
                fol = eligible.get("follows", 0) + eligible.get("follows_rounded", 0)
                following_rate = (fol / n_el) * 100.0
        except Exception:
            pass

    return {
        "n": n,
        "correct": correct,
        "accuracy": (correct / n) * 100.0,
        "format_valid": format_valid,
        "format_valid_rate": (format_valid / n) * 100.0,
        "following_rate": following_rate,
    }


def main():
    seed_stats = {}
    for s, p in EVAL_DIRS.items():
        st = summarize_seed(p)
        if st:
            seed_stats[s] = st

    print(f"Available evaluated seeds: {list(seed_stats.keys())}")
    if not seed_stats:
        print("No seed evaluation data found.")
        return

    accs = [st["accuracy"] for st in seed_stats.values()]
    fmts = [st["format_valid_rate"] for st in seed_stats.values()]
    fols = [st["following_rate"] for st in seed_stats.values() if st["following_rate"] is not None]

    mean_acc = statistics.mean(accs)
    std_acc = statistics.stdev(accs) if len(accs) > 1 else 0.0

    mean_fmt = statistics.mean(fmts)
    std_fmt = statistics.stdev(fmts) if len(fmts) > 1 else 0.0

    mean_fol = statistics.mean(fols) if fols else 0.0
    std_fol = statistics.stdev(fols) if len(fols) > 1 else 0.0

    summary = {
        "seeds": seed_stats,
        "num_seeds": len(accs),
        "accuracy_mean": round(mean_acc, 2),
        "accuracy_std": round(std_acc, 2),
        "format_valid_mean": round(mean_fmt, 2),
        "format_valid_std": round(std_fmt, 2),
        "following_rate_mean": round(mean_fol, 2),
        "following_rate_std": round(std_fol, 2),
    }

    out_file = DIR / "multiseed_summary.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Multi-seed summary written to {out_file}:")
    print(f"  Accuracy: {mean_acc:.1f}% ± {std_acc:.2f}%")
    print(f"  Format Valid: {mean_fmt:.1f}% ± {std_fmt:.2f}%")
    if fols:
        print(f"  Causal Following: {mean_fol:.1f}% ± {std_fol:.2f}%")


if __name__ == "__main__":
    main()
