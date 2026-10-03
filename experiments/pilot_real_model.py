"""
experiments/pilot_real_model.py — Pilot real Qwen MLX model on development dataset.

Checks:
1. Output parsers (extract_answer, extract_code, parse_action) on real model generation.
2. Generated token counts and token logprob confidence.
3. System resource utilization (latency, peak memory RSS).

This is a development diagnostic, not publication evidence and not a protocol
freeze. The supported main-study entry point remains
``python -m experiments.research_study``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qwen_mlx_backend import QwenMLXBackend, COT_SUFFIX, REACT_SYSTEM, PAL_SUFFIX
from reasoning_env import ReasoningAction as A
from experiments.research_study import check_answer


def select_development_items(items: List[Dict[str, Any]], sample_size: int) -> List[Dict[str, Any]]:
    """Deterministically cover categories and language variants without touching held-out splits."""
    train = [item for item in items if item["split"] == "train"]
    categories = sorted({item.get("category", "unknown") for item in train})
    suffixes = ("_en_orig", "_vi_trans", "_en_para")
    selected: List[Dict[str, Any]] = []
    used_groups = set()
    for suffix in suffixes:
        for category in categories:
            candidate = next((
                item for item in train
                if item.get("category", "unknown") == category
                and item["id"].endswith(suffix)
                and item["group_id"] not in used_groups
            ), None)
            if candidate is not None:
                selected.append(candidate)
                used_groups.add(candidate["group_id"])
                if len(selected) == sample_size:
                    return selected
    for item in train:
        if item["id"] not in {selected_item["id"] for selected_item in selected}:
            selected.append(item)
            if len(selected) == sample_size:
                break
    return selected


def run_pilot(
    dataset_path: str,
    model_repo: str = "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    sample_size: int = 6,
    strategy_names: List[str] | None = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Execute pilot evaluation on development items."""
    data = json.loads(Path(dataset_path).read_text())
    selected_items = select_development_items(data["items"], sample_size)

    print(f"Loading local MLX model: {model_repo}...")
    t0 = time.time()
    backend = QwenMLXBackend(repo=model_repo)
    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.2f}s")

    import mlx.core as mx
    mx.random.seed(seed)

    pilot_results = []
    requested = strategy_names or [
        A.COT.name, A.SELF_CONSISTENCY.name, A.TOT.name, A.REACT.name, A.PAL.name,
    ]
    known = {strategy.name: strategy for strategy in A}
    unknown = sorted(set(requested) - set(known))
    if unknown:
        raise ValueError(f"Unknown strategies: {unknown}")
    strategies_to_test = [known[name] for name in requested]

    for item in selected_items:
        query = item["query"]
        expected = item["answer"]
        item_id = item["id"]
        category = item["category"]

        print(f"\n--- Testing [{category.upper()}] Item: {item_id} ---")
        print(f"Query: {query[:80]}...")
        print(f"Gold Answer: {expected}")

        item_eval = {
            "id": item_id,
            "category": category,
            "query": query,
            "expected_answer": expected,
            "answer_type": item["answer_type"],
            "strategies": {},
        }

        for strat in strategies_to_test:
            s_name = strat.name
            t_strat = time.time()
            try:
                answer, conf, tokens = backend.run(strat, query)
                elapsed_ms = (time.time() - t_strat) * 1000.0
                is_correct = check_answer(answer, item)

                print(f"  * Strategy: {s_name:5s} | Ans: {answer!r:20s} | Correct: {str(is_correct):5s} | Conf: {conf:.3f} | Tokens: {tokens:3d} | Latency: {elapsed_ms:.1f}ms")

                item_eval["strategies"][s_name] = {
                    "raw_answer": answer,
                    "confidence": float(conf),
                    "generated_tokens": int(tokens),
                    "latency_ms": float(elapsed_ms),
                    "is_correct": bool(is_correct),
                    "error": None,
                    "trace": backend.last_trace,
                }
            except Exception as e:
                print(f"  * Strategy: {s_name:5s} | FAILED with error: {e}")
                item_eval["strategies"][s_name] = {
                    "raw_answer": "",
                    "confidence": 0.0,
                    "generated_tokens": 0,
                    "latency_ms": 0.0,
                    "is_correct": False,
                    "error": str(e),
                }

        pilot_results.append(item_eval)

    # Resource measurements
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = peak_rss / (1024 * 1024 if sys.platform == "darwin" else 1024)

    return {
        "model_repo": model_repo,
        "evidence": "development_pilot_not_publication_evidence",
        "load_time_seconds": load_time,
        "peak_rss_mb": peak_rss_mb,
        "total_dev_samples": len(selected_items),
        "seed": seed,
        "strategies": requested,
        "results": pilot_results,
        "pilot_configuration": {
            "model_snapshot": model_repo,
            "prompts": {
                "COT_SUFFIX": COT_SUFFIX,
                "REACT_SYSTEM": REACT_SYSTEM,
                "PAL_SUFFIX": PAL_SUFFIX,
            },
            "sealed_splits": ["calibration", "test"],
        }
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="data/nckh_reasoning_dataset_draft.json")
    parser.add_argument("--output", default="outputs/pilot_real_model_report.json")
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--model", default="mlx-community/Qwen2.5-0.5B-Instruct-4bit")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--strategies",
        default="COT,SELF_CONSISTENCY,TOT,REACT,PAL",
        help="Comma-separated ReasoningAction names",
    )
    args = parser.parse_args()

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    strategies = [name.strip().upper() for name in args.strategies.split(",") if name.strip()]
    summary = run_pilot(
        args.dataset,
        model_repo=args.model,
        sample_size=args.samples,
        strategy_names=strategies,
        seed=args.seed,
    )
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nPilot report successfully generated at: {out_path}")
    print(f"Peak RSS: {summary['peak_rss_mb']:.1f} MB")


if __name__ == "__main__":
    main()
