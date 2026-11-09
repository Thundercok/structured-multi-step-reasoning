"""Unit tests for MLX SimPO Trainer batch builder and dataset iterator."""

import json
from pathlib import Path
import pytest

mx = pytest.importorskip("mlx.core", reason="MLX is required on Apple Silicon")
from structured_llm.msra.train_simpo import build_preference_batch, iterate_dataset

# Run CPU
mx.set_default_device(mx.cpu)


class MockTokenizer:
    def encode(self, text: str):
        # Character-based token representation for fast deterministic testing
        return [ord(c) % 50 + 1 for c in text]


def test_build_preference_batch():
    tok = MockTokenizer()
    prompt = "Problem: Solve 2+2"
    chosen = "SOLVE_LOCAL 4"
    rejected = "ASK_HELP help"

    batch = build_preference_batch(tok, prompt, chosen, rejected, max_length=100)
    assert batch is not None
    in_w, tgt_w, msk_w, in_l, tgt_l, msk_l = batch

    p_len = len(tok.encode(prompt))
    c_len = len(tok.encode(chosen))
    r_len = len(tok.encode(rejected))

    # in_w length should be p_len + c_len - 1
    assert in_w.shape[1] == p_len + c_len - 1
    assert tgt_w.shape[1] == p_len + c_len - 1
    assert msk_w.shape[1] == p_len + c_len - 1

    # Check mask: prompt targets must be 0.0, response targets must be 1.0
    mask_w_np = list(msk_w[0])
    assert sum(mask_w_np[: p_len - 1]) == 0.0
    assert sum(mask_w_np[p_len - 1 :]) == float(c_len)


def test_iterate_dataset(tmp_path: Path):
    tok = MockTokenizer()
    test_jsonl = tmp_path / "train.jsonl"
    with open(test_jsonl, "w", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": "A", "chosen": "B", "rejected": "C"}) + "\n")
        f.write(json.dumps({"prompt": "D", "chosen": "E", "rejected": "F"}) + "\n")

    items = list(iterate_dataset(test_jsonl, tok, max_length=50, repeat=False))
    assert len(items) == 2
    assert items[0][6]["prompt"] == "A"
    assert items[1][6]["prompt"] == "D"
