"""Command-line entrypoint for GSM8K staged development collection.

Supports both deterministic offline mock (0 model calls) and real-model execution
via QwenMLXStagedRunner on Apple Silicon under strict Stage 0 envelopes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import gsm8k_collector as collector
from experiments.research_pilot import sha256_file
from experiments.research_study import source_hashes, validate_dataset


def build_identity(
    dataset: dict,
    dataset_path: Path,
    evidence: str,
    model_name: str | None,
    seed: int,
    prompt_profile: str,
    max_tokens: int,
) -> dict:
    dataset_bytes = json.dumps(dataset, sort_keys=True).encode("utf-8")
    dataset_sha = hashlib.sha256(dataset_bytes).hexdigest()
    return {
        "evidence": evidence,
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_sha,
        "model": model_name,
        "seed": seed,
        "prompt_profile": prompt_profile,
        "strategies": list(collector.ACTIONS),
        "max_tokens": max_tokens,
        "source_hashes": source_hashes(),
    }


def main():
    parser = argparse.ArgumentParser(description="GSM8K staged collector runner")
    parser.add_argument("--mock", action="store_true", help="Run with deterministic offline mock runner (0 model calls)")
    parser.add_argument("--model", type=str, default="mlx-community/Qwen3-8B-4bit", help="Pinned local or hub MLX model identifier")
    parser.add_argument("--dataset", type=Path, default=Path("data/gsm8k_development_validation_reviewed_v1/dataset.json"), help="Dataset JSON file")
    parser.add_argument("--output", type=Path, required=True, help="Output run directory")
    parser.add_argument("--seed", type=int, default=42, help="Master generation seed")
    parser.add_argument("--prompt-profile", type=str, default="english-math-v1", choices=["english-math-v1"], help="Prompt profile")
    parser.add_argument("--max-tokens", type=int, default=1024, help="Per-call generated token ceiling")
    parser.add_argument("--max-calls", type=int, default=279, help="Total call ceiling envelope (default: 93 items * 3 strategies = 279)")
    parser.add_argument("--max-tokens-total", type=int, default=285696, help="Total generated tokens ceiling (default: 279 * 1024 = 285696)")

    args = parser.parse_args()

    if args.output.exists() and not (args.output / "checkpoint.json").is_file():
        parser.error(f"Output directory {args.output} exists and is not an existing resumable checkpoint")

    if not args.dataset.is_file():
        parser.error(f"Dataset file {args.dataset} not found")

    with open(args.dataset, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # Validate dataset contracts
    validate_dataset(dataset, pilot=True)
    num_items = len(dataset["items"])
    expected_calls = num_items * len(collector.ACTIONS)
    if args.max_calls < expected_calls:
        parser.error(f"max_calls ({args.max_calls}) is smaller than required calls ({expected_calls} = {num_items} items * {len(collector.ACTIONS)} actions)")

    evidence = "synthetic_staged_pilot_collection" if args.mock else "measured_staged_pilot_collection"
    model_name = None if args.mock else args.model
    settings = {"temperature": 0.0, "thinking": False}

    identity = build_identity(
        dataset=dataset,
        dataset_path=args.dataset,
        evidence=evidence,
        model_name=model_name,
        seed=args.seed,
        prompt_profile=args.prompt_profile,
        max_tokens=args.max_tokens,
    )

    print(f"Initializing checkpoint in: {args.output}")
    checkpoint = collector.GSM8KCollectorCheckpoint(args.output, identity, dataset, settings)

    if args.mock:
        print("Starting offline mock staged runner (0 model calls)...")
        runner = collector.MockStagedRunner()
    else:
        print(f"Loading QwenMLXBackend with model '{args.model}' (prompt_profile={args.prompt_profile})...")
        from qwen_mlx_backend import QwenMLXBackend, QwenMLXStagedRunner
        backend = QwenMLXBackend(
            repo=args.model,
            strict_telemetry=True,
            prompt_profile=args.prompt_profile,
        )
        runner = QwenMLXStagedRunner(backend)

    print(f"Executing staged collection: {num_items} items, {len(collector.ACTIONS)} strategies, {expected_calls} calls planned...")
    start_time = time.time()
    manifest = collector.run_staged_collection(
        checkpoint=checkpoint,
        runner=runner,
        dataset=dataset,
        strategies=list(collector.ACTIONS),
        token_budget=args.max_tokens,
        master_seed=args.seed,
        max_total_calls=args.max_calls,
        max_total_tokens=args.max_tokens_total,
    )
    checkpoint.close()
    elapsed = time.time() - start_time

    print(f"\nCollection {manifest['status']} in {elapsed:.2f}s!")
    print(f"  Calls completed: {manifest['calls_completed']} / {expected_calls}")
    print(f"  Measured tokens: {manifest['measured_tokens']}")
    print(f"  Artifacts saved in: {args.output}")


if __name__ == "__main__":
    main()
