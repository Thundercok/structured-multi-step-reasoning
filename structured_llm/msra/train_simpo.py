"""SimPO Preference Optimization Training Loop for MLX on Apple Silicon.

Trains or fine-tunes LoRA adapters directly on (prompt, chosen, rejected) pairs
using the reference-free SimPO loss without loading a secondary 8B reference model.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Dict, Iterator, List, Optional, Tuple

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as opt
from mlx.utils import tree_flatten
from mlx_lm import load
from mlx_lm.tuner.trainer import grad_checkpoint
from mlx_lm.tuner.utils import linear_to_lora_layers, load_adapters, build_schedule

from .simpo_loss import compute_simpo_loss


def build_preference_batch(
    tokenizer,
    prompt: str,
    chosen: str,
    rejected: str,
    max_length: int = 1024,
) -> Optional[Tuple[mx.array, mx.array, mx.array, mx.array, mx.array, mx.array]]:
    """Tokenize and prepare inputs, targets, and response masks for chosen and rejected."""
    prompt_ids = tokenizer.encode(prompt)
    chosen_ids = tokenizer.encode(chosen)
    rejected_ids = tokenizer.encode(rejected)

    # Full sequences
    full_chosen = prompt_ids + chosen_ids
    full_rejected = prompt_ids + rejected_ids

    if len(full_chosen) > max_length or len(full_rejected) > max_length:
        return None
    if len(chosen_ids) == 0 or len(rejected_ids) == 0:
        return None

    # Targets are next-token shifted
    # input: [x_0, ..., x_{N-2}], target: [x_1, ..., x_{N-1}]
    input_w = mx.array([full_chosen[:-1]])
    target_w = mx.array([full_chosen[1:]])
    
    # Mask is 1.0 only for response tokens in target
    # Prompt tokens occupy indices 0 to len(prompt_ids)-2 in input,
    # so in target, prompt tokens are indices 0 to len(prompt_ids)-2
    mask_w_list = [0.0] * (len(prompt_ids) - 1) + [1.0] * len(chosen_ids)
    mask_w = mx.array([mask_w_list])

    input_l = mx.array([full_rejected[:-1]])
    target_l = mx.array([full_rejected[1:]])
    mask_l_list = [0.0] * (len(prompt_ids) - 1) + [1.0] * len(rejected_ids)
    mask_l = mx.array([mask_l_list])

    return input_w, target_w, mask_w, input_l, target_l, mask_l


def iterate_dataset(
    data_path: Path,
    tokenizer,
    max_length: int = 1024,
    repeat: bool = True,
) -> Iterator[Tuple[mx.array, mx.array, mx.array, mx.array, mx.array, mx.array, Dict]]:
    """Yield tokenized preference batches."""
    while True:
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                batch = build_preference_batch(
                    tokenizer,
                    prompt=item["prompt"],
                    chosen=item["chosen"],
                    rejected=item["rejected"],
                    max_length=max_length,
                )
                if batch is not None:
                    yield (*batch, item)
        if not repeat:
            break


def train_simpo(
    model_name: str,
    data_dir: str,
    output_adapter: str,
    base_adapter: Optional[str] = None,
    iters: int = 1000,
    lr: float = 1e-5,
    beta: float = 2.0,
    gamma: float = 0.5,
    save_every: int = 50,
    steps_per_report: int = 10,
    max_length: int = 1024,
    num_layers: int = 8,
):
    """Run SimPO preference optimization loop on Apple Silicon."""
    out_dir = Path(output_adapter)
    out_dir.mkdir(parents=True, exist_ok=True)

    from .mlx_backend import DEFAULT_MODEL_ID, resolve_local_model_path
    resolved_model = resolve_local_model_path(model_name) if model_name == DEFAULT_MODEL_ID else model_name
    print(f"=== Loading model: {resolved_model} ===")
    model, tokenizer = load(resolved_model)
    model.freeze()

    lora_config = {"rank": 8, "alpha": 16, "dropout": 0.0, "scale": 20.0}
    if base_adapter and os.path.exists(os.path.join(base_adapter, "adapters.safetensors")):
        print(f"Loading pretrained base adapter: {base_adapter}")
        model = load_adapters(model, base_adapter)
    else:
        print(f"Initializing new LoRA layers (num_layers={num_layers})")
        linear_to_lora_layers(model, num_layers=num_layers, config=lora_config)

    grad_checkpoint(model.layers[0])

    adapter_cfg = {
        "adapter_path": str(out_dir),
        "fine_tune_type": "lora",
        "grad_checkpoint": True,
        "iters": iters,
        "learning_rate": lr,
        "lora_parameters": {"rank": 8, "dropout": 0.0, "scale": 20.0},
        "max_seq_length": max_length,
        "model": str(resolved_model),
        "num_layers": num_layers,
    }
    (out_dir / "adapter_config.json").write_text(json.dumps(adapter_cfg, indent=4) + "\n", encoding="utf-8")

    train_data_path = Path(data_dir) / "train.jsonl"
    if not train_data_path.exists():
        raise FileNotFoundError(f"Missing train data at {train_data_path}")

    optimizer = opt.AdamW(learning_rate=lr)

    def loss_fn(model, in_w, tgt_w, msk_w, in_l, tgt_l, msk_l):
        logits_w = model(in_w)
        logits_l = model(in_l)
        loss, metrics = compute_simpo_loss(
            logits_chosen=logits_w,
            targets_chosen=tgt_w,
            mask_chosen=msk_w,
            logits_rejected=logits_l,
            targets_rejected=tgt_l,
            mask_rejected=msk_l,
            beta=beta,
            gamma=gamma,
        )
        return loss, metrics

    loss_and_grad = nn.value_and_grad(model, loss_fn)

    print(f"=== Starting SimPO Training ({iters} steps, lr={lr}, beta={beta}, gamma={gamma}) ===")
    data_iter = iterate_dataset(train_data_path, tokenizer, max_length=max_length)
    
    start_time = time.time()
    for step in range(1, iters + 1):
        in_w, tgt_w, msk_w, in_l, tgt_l, msk_l, meta = next(data_iter)

        (loss, metrics), grads = loss_and_grad(
            model, in_w, tgt_w, msk_w, in_l, tgt_l, msk_l
        )
        optimizer.update(model, grads)
        mx.eval(model.parameters(), optimizer.state)

        if step % steps_per_report == 0:
            elapsed = time.time() - start_time
            steps_per_sec = step / max(elapsed, 1e-4)
            print(
                f"Step {step:04d}/{iters} | "
                f"Loss: {metrics['loss']:.4f} | "
                f"Margin: {metrics['reward_margin']:+.4f} | "
                f"Acc: {metrics['accuracy']:.2f} | "
                f"Speed: {steps_per_sec:.2f} it/s"
            )

        if step % save_every == 0 or step == iters:
            save_path = out_dir / f"{step:07d}_adapters.safetensors"
            current_path = out_dir / "adapters.safetensors"
            adapter_weights = dict(tree_flatten(model.trainable_parameters()))
            mx.save_safetensors(str(current_path), adapter_weights)
            mx.save_safetensors(str(save_path), adapter_weights)
            print(f"Iter {step}: Saved adapter weights to {current_path} and {save_path}.", flush=True)

    print(f"=== SimPO Training Complete at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLX SimPO Preference Trainer")
    parser.add_argument("--model", type=str, default="mlx-community/Qwen3-8B-4bit")
    parser.add_argument("--data", type=str, default="data/structured_msra_simpo_v1")
    parser.add_argument("--output-adapter", type=str, required=True)
    parser.add_argument("--base-adapter", type=str, default=None)
    parser.add_argument("--iters", type=int, default=1000)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--beta", type=float, default=2.0)
    parser.add_argument("--gamma", type=float, default=0.5)
    parser.add_argument("--save-every", type=int, default=50)
    parser.add_argument("--max-length", type=int, default=1024)
    args = parser.parse_args()

    train_simpo(
        model_name=args.model,
        data_dir=args.data,
        output_adapter=args.output_adapter,
        base_adapter=args.base_adapter,
        iters=args.iters,
        lr=args.lr,
        beta=args.beta,
        gamma=args.gamma,
        save_every=args.save_every,
        max_length=args.max_length,
    )
