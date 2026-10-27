"""Offline parity tests comparing legacy QwenMLXBackend and QwenMLXStagedRunner with injected fixtures."""
import json
from pathlib import Path
import tempfile
import time
import sys
from unittest.mock import MagicMock, patch

import pytest

from reasoning.reasoning_env import ReasoningAction as A
from qwen_mlx_backend import (
    MATH_EN_SUFFIXES,
    QwenMLXBackend,
    QwenMLXStagedRunner,
)
from experiments.gsm8k_collector import (
    GSM8KCollectorCheckpoint,
    run_staged_collection,
)
from experiments.gsm8k_routing_baseline import write_fitting_seal


class FakeGenResponse:
    """Mock MLX generation response token."""
    def __init__(self, text: str, tokens: int, finish_reason: str = "stop"):
        self.text = text
        self.generation_tokens = tokens
        self.finish_reason = finish_reason
        self.logprobs = None
        self.token = 0


def make_stream_generate(text: str, tokens: int = 15, finish_reason: str = "stop"):
    """Fixture generator returning scripted text and token counts."""
    def _generator(*args, **kwargs):
        yield FakeGenResponse(text=text, tokens=tokens, finish_reason=finish_reason)
    return _generator


class FakeTokenizer:
    """Deterministic offline mock tokenizer implementing chat template and encoding."""

    def apply_chat_template(self, messages, enable_thinking=False, add_generation_prompt=True):
        parts = []
        for m in messages:
            parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
        if add_generation_prompt:
            parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    def encode(self, text):
        return [1] * len(text.split())

    def decode(self, token_ids):
        return " ".join(str(t) for t in token_ids)


class TokenIdTokenizer:
    """Tokenizer whose apply_chat_template returns a list of integer token IDs."""

    def apply_chat_template(self, messages, enable_thinking=False, add_generation_prompt=True):
        # Returns raw token IDs directly
        return [101, 2054, 2003, 102]

    def decode(self, token_ids):
        return "Decoded: " + " ".join(str(t) for t in token_ids)

    def encode(self, text):
        return [101, 2054, 2003, 102]


class FakeModel:
    """Mock model args for hidden size."""
    class Args:
        hidden_size = 4096
    args = Args()


import numpy as np


def make_offline_backend(tokenizer=None, seed_setter=None, sampler_factory=None, array_converter=None):
    """Create a QwenMLXBackend configured with offline fake tokenizer and model, without MLX native dependencies."""
    backend = QwenMLXBackend(
        model=FakeModel(),
        tokenizer=tokenizer or FakeTokenizer(),
        prompt_profile="english-math-v1",
        seed_setter=seed_setter or (lambda s: None),
        sampler_factory=sampler_factory or (lambda temp=0.0: None),
        array_converter=array_converter or (lambda x: np.asarray(x, dtype=np.float32)),
    )
    backend.configure_answer_format(answer_type="number", decimal_separator=".")
    return backend


@pytest.fixture
def offline_harness():
    backend = make_offline_backend()
    runner = QwenMLXStagedRunner(backend)
    item = {
        "id": "item_01",
        "group_id": "group_01",
        "split": "train",
        "query": "Janet has 16 eggs. She eats 7. How many remain?",
        "answer": "9",
        "answer_type": "number",
        "decimal_separator": ".",
    }
    return backend, runner, item


# =========================================================================
# 1. DIRECT Strategy Parity
# =========================================================================

def test_parity_direct_marker_success(offline_harness):
    backend, runner, item = offline_harness
    injected_text = "16 - 7 = 9 eggs remain.\nAnswer: 9\n"
    injected_tok = 24

    stream_gen = make_stream_generate(injected_text, injected_tok, "stop")

    # Legacy execution through real _chat
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        legacy_ans, legacy_conf, legacy_tok = backend.run(A.DIRECT, item["query"])
        legacy_trace = dict(backend.last_trace)

    # Staged execution through real _chat
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    assert gen_res.text == injected_text
    assert gen_res.confidence == legacy_conf
    assert gen_res.generated_tokens == legacy_tok
    assert gen_res.finish_reason == "stop"
    assert gen_res.messages == [{"role": "user", "content": item["query"] + MATH_EN_SUFFIXES[A.DIRECT]}]
    assert "<|im_start|>user" in gen_res.raw_prompt

    # Verify parsed answer and status equivalence
    ans, status, wordy = backend._parse_answer(gen_res.text)
    assert ans == legacy_ans == "9"
    assert status == legacy_trace["parse_status"] == "marker"
    assert wordy == legacy_trace["wordy"] is False


def test_parity_direct_fallback_no_marker(offline_harness):
    backend, runner, item = offline_harness
    injected_text = "She has exactly 9"
    injected_tok = 15

    stream_gen = make_stream_generate(injected_text, injected_tok, "stop")

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        legacy_ans, legacy_conf, legacy_tok = backend.run(A.DIRECT, item["query"])
        legacy_trace = dict(backend.last_trace)

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    ans, status, wordy = backend._parse_answer(gen_res.text)
    assert ans == legacy_ans == "She has exactly 9"
    assert status == legacy_trace["parse_status"] == "fail"
    assert wordy == legacy_trace["wordy"] is True
    assert gen_res.confidence == legacy_conf


def test_parity_direct_length_stop_boundary(offline_harness):
    backend, runner, item = offline_harness
    injected_text = "16 minus 7 is equal to 9, so the final count of remaining eggs is "
    injected_tok = 512

    stream_gen = make_stream_generate(injected_text, injected_tok, "length")

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        legacy_ans, legacy_conf, legacy_tok = backend.run(A.DIRECT, item["query"])

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    assert gen_res.finish_reason == "length"
    assert gen_res.generated_tokens == legacy_tok == 512


# =========================================================================
# 2. COT Strategy Parity
# =========================================================================

def test_parity_cot_multistep_success(offline_harness):
    backend, runner, item = offline_harness
    injected_text = "Step 1: Start with 16 eggs.\nStep 2: Eat 7 eggs.\nStep 3: 16 - 7 = 9 eggs left.\nAnswer: 9\n"
    injected_tok = 48

    stream_gen = make_stream_generate(injected_text, injected_tok, "stop")

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        legacy_ans, legacy_conf, legacy_tok = backend.run(A.COT, item["query"])
        legacy_trace = dict(backend.last_trace)

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "COT", max_tokens=512, seed=42)

    ans, status, wordy = backend._parse_answer(gen_res.text)
    assert ans == legacy_ans == "9"
    assert status == legacy_trace["parse_status"] == "marker"
    assert wordy == legacy_trace["wordy"] is False
    assert gen_res.confidence == legacy_conf
    assert gen_res.messages == [{"role": "user", "content": item["query"] + MATH_EN_SUFFIXES[A.COT]}]


# =========================================================================
# 3. PAL Strategy Parity (Success, Tool Error, Tool Timeout)
# =========================================================================

def test_parity_pal_tool_success(offline_harness):
    backend, runner, item = offline_harness
    injected_code_text = "```python\ntotal = 16\neaten = 7\nresult = total - eaten\n```"
    injected_tok = 32

    stream_gen = make_stream_generate(injected_code_text, injected_tok, "stop")

    # Legacy execution: real _chat produces code, run_python_sandboxed returns (True, "9")
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(True, "9")):
            legacy_ans, legacy_conf, legacy_tok = backend.run(A.PAL, item["query"])
            legacy_trace = dict(backend.last_trace)

    # Staged execution: generation stage first through real _chat
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "PAL", max_tokens=512, seed=42)

    # Staged execution: tool stage second
    with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(True, "9")):
        tool_res = runner.run_tool("total = 16\neaten = 7\nresult = total - eaten", timeout_seconds=5.0)

    assert tool_res.ok is True
    assert tool_res.output == "9"

    # Assemble simulated record
    att = {
        "cond_key": (item["id"], "PAL"),
        "started": {"seed": 42, "declared_max_tokens": 512},
        "generation_outcome": {
            "output_text": gen_res.text,
            "measured_generated_tokens": gen_res.generated_tokens,
            "measured_prompt_tokens": gen_res.prompt_tokens,
            "finish_reason": gen_res.finish_reason,
            "confidence": gen_res.confidence,
            "elapsed_ms": gen_res.elapsed_ms,
            "messages": gen_res.messages,
            "raw_prompt": gen_res.raw_prompt,
            "prompt_token_ids": gen_res.prompt_token_ids,
            "generation_trace": gen_res.generation_trace,
        },
        "tool_outcome": {
            "ok": tool_res.ok,
            "output": tool_res.output,
            "duration_ms": tool_res.duration_ms,
        },
    }

    checkpoint = MagicMock()
    checkpoint.dataset = {"items": [item]}
    checkpoint.identity = {"evidence": "synthetic_staged_pilot_collection"}
    from experiments.gsm8k_collector import GSM8KCollectorCheckpoint
    record = GSM8KCollectorCheckpoint._build_record_from_evidence(checkpoint, att)

    # Complete parity verification
    assert record["answer"] == legacy_ans == "9"
    assert record["confidence"] == legacy_conf
    assert record["tokens"] == legacy_tok == injected_tok
    assert record["trace"]["parse_status"] == legacy_trace["parse_status"] == "marker"
    assert record["trace"]["tools"][0]["ok"] is True
    assert record["trace"]["tools"][0]["output"] == "9"
    assert record["trace"]["generations"][0]["messages"] == [{"role": "user", "content": item["query"] + MATH_EN_SUFFIXES[A.PAL]}]


def test_parity_pal_tool_runtime_error_fallback(offline_harness):
    backend, runner, item = offline_harness
    injected_code_text = "```python\nresult = 16 / 0\n```\nAnswer: 9\n"
    injected_tok = 28

    stream_gen = make_stream_generate(injected_code_text, injected_tok, "stop")

    # Legacy execution: tool fails, falls back to text and penalizes confidence by 0.3
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(False, "ZeroDivisionError: division by zero")):
            legacy_ans, legacy_conf, legacy_tok = backend.run(A.PAL, item["query"])

    # Staged execution
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "PAL", max_tokens=512, seed=42)

    with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(False, "ZeroDivisionError: division by zero")):
        tool_res = runner.run_tool("result = 16 / 0", timeout_seconds=5.0)

    assert tool_res.ok is False
    assert "ZeroDivisionError" in tool_res.output

    att = {
        "cond_key": (item["id"], "PAL"),
        "started": {"seed": 42, "declared_max_tokens": 512},
        "generation_outcome": {
            "output_text": gen_res.text,
            "measured_generated_tokens": gen_res.generated_tokens,
            "measured_prompt_tokens": gen_res.prompt_tokens,
            "finish_reason": gen_res.finish_reason,
            "confidence": gen_res.confidence,
            "elapsed_ms": gen_res.elapsed_ms,
            "messages": gen_res.messages,
            "raw_prompt": gen_res.raw_prompt,
            "prompt_token_ids": gen_res.prompt_token_ids,
            "generation_trace": gen_res.generation_trace,
        },
        "tool_outcome": {
            "ok": tool_res.ok,
            "output": tool_res.output,
            "duration_ms": tool_res.duration_ms,
        },
    }

    checkpoint = MagicMock()
    checkpoint.dataset = {"items": [item]}
    checkpoint.identity = {"evidence": "synthetic_staged_pilot_collection"}
    from experiments.gsm8k_collector import GSM8KCollectorCheckpoint
    record = GSM8KCollectorCheckpoint._build_record_from_evidence(checkpoint, att)

    # Parity check: both fall back to text and apply * 0.3 penalty
    assert record["answer"] == legacy_ans == "9"
    assert record["confidence"] == legacy_conf
    assert record["trace"]["tools"][0]["ok"] is False


def test_parity_pal_tool_timeout_fallback(offline_harness):
    backend, runner, item = offline_harness
    injected_code_text = "```python\nwhile True: pass\n```\nAnswer: 9\n"
    injected_tok = 30

    stream_gen = make_stream_generate(injected_code_text, injected_tok, "stop")

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(False, "TimeoutError: execution exceeded 5.0s")):
            legacy_ans, legacy_conf, legacy_tok = backend.run(A.PAL, item["query"])

    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "PAL", max_tokens=512, seed=42)

    with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(False, "TimeoutError: execution exceeded 5.0s")):
        tool_res = runner.run_tool("while True: pass", timeout_seconds=5.0)

    assert tool_res.ok is False
    assert "TimeoutError" in tool_res.output

    att = {
        "cond_key": (item["id"], "PAL"),
        "started": {"seed": 42, "declared_max_tokens": 512},
        "generation_outcome": {
            "output_text": gen_res.text,
            "measured_generated_tokens": gen_res.generated_tokens,
            "measured_prompt_tokens": gen_res.prompt_tokens,
            "finish_reason": gen_res.finish_reason,
            "confidence": gen_res.confidence,
            "elapsed_ms": gen_res.elapsed_ms,
            "messages": gen_res.messages,
            "raw_prompt": gen_res.raw_prompt,
            "prompt_token_ids": gen_res.prompt_token_ids,
            "generation_trace": gen_res.generation_trace,
        },
        "tool_outcome": {
            "ok": tool_res.ok,
            "output": tool_res.output,
            "duration_ms": tool_res.duration_ms,
        },
    }

    checkpoint = MagicMock()
    checkpoint.dataset = {"items": [item]}
    checkpoint.identity = {"evidence": "synthetic_staged_pilot_collection"}
    from experiments.gsm8k_collector import GSM8KCollectorCheckpoint
    record = GSM8KCollectorCheckpoint._build_record_from_evidence(checkpoint, att)

    assert record["answer"] == legacy_ans == "9"
    assert record["confidence"] == legacy_conf


# =========================================================================
# 4. Finding 1: Seed Application at Generation Boundary
# =========================================================================

def test_staged_runner_applies_seed_before_dispatch(offline_harness):
    backend, _, item = offline_harness
    mock_seed_setter = MagicMock()
    runner = QwenMLXStagedRunner(backend, seed_setter=mock_seed_setter)

    stream_gen = make_stream_generate("Answer: 9\n", 10, "stop")
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    # 1. Exact derived seed passed to seed setter before dispatch
    mock_seed_setter.assert_called_once_with(42)
    assert runner.last_applied_seed == 42
    assert gen_res.generation_trace["applied_seed"] == 42

    # 2. Re-dispatch with different seed updates seed setter
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res2 = runner.run_generation(item, "DIRECT", max_tokens=512, seed=999)
    mock_seed_setter.assert_called_with(999)
    assert runner.last_applied_seed == 999
    assert gen_res2.generation_trace["applied_seed"] == 999

    # 3. Boolean or non-integer seed is rejected
    with pytest.raises(ValueError, match="Seed must be an integer"):
        runner.run_generation(item, "DIRECT", max_tokens=512, seed=True)
    with pytest.raises(ValueError, match="Seed must be an integer"):
        runner.run_generation(item, "DIRECT", max_tokens=512, seed="42")


# =========================================================================
# 5. Finding 2: Tokenizer Returning Token IDs & Exact Dispatched IDs Capture
# =========================================================================

def test_staged_runner_captures_token_ids_from_tokenizer():
    """Verify that when tokenizer returns token IDs list[int], IDs are captured exactly from _chat trace."""
    tok_tokenizer = TokenIdTokenizer()
    backend = make_offline_backend(tokenizer=tok_tokenizer)
    runner = QwenMLXStagedRunner(backend)

    item = {
        "id": "item_token_ids",
        "group_id": "group_01",
        "split": "train",
        "query": "Solve this equation.",
        "answer_type": "number",
        "decimal_separator": ".",
    }

    stream_gen = make_stream_generate("Answer: 42\n", 12, "stop")
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        gen_res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    # Exactly the dispatched token IDs
    assert gen_res.prompt_token_ids == [101, 2054, 2003, 102]
    assert gen_res.prompt_tokens == 4
    # Decoded view preserved as additional view
    assert gen_res.raw_prompt == "Decoded: 101 2054 2003 102"
    assert gen_res.messages == [{"role": "user", "content": item["query"] + MATH_EN_SUFFIXES[A.DIRECT]}]


# =========================================================================
# 6. Finding 3: Restrict Invented Messages & Require Real Trace Evidence
# =========================================================================

def test_collector_fails_closed_when_messages_missing_on_staged_schema(offline_harness):
    """Assert that staged record assembly strictly rejects missing messages evidence instead of inventing bare query."""
    _, _, item = offline_harness
    att = {
        "cond_key": (item["id"], "DIRECT"),
        "started": {"seed": 42, "declared_max_tokens": 512},
        "generation_outcome": {
            "output_text": "Answer: 9\n",
            "measured_generated_tokens": 10,
            "measured_prompt_tokens": 20,
            "finish_reason": "stop",
            "confidence": 0.95,
            "elapsed_ms": 15.0,
            "messages": None,  # Missing messages!
            "raw_prompt": None,
        },
        "tool_outcome": None,
    }

    checkpoint = MagicMock()
    checkpoint.dataset = {"items": [item]}
    checkpoint.identity = {"evidence": "synthetic_staged_pilot_collection"}  # Staged schema!

    from experiments.gsm8k_collector import GSM8KCollectorCheckpoint
    with pytest.raises(ValueError, match="Staged record assembly requires actual messages"):
        GSM8KCollectorCheckpoint._build_record_from_evidence(checkpoint, att)


def test_collector_labels_legacy_fallback_explicitly(offline_harness):
    """Assert that when legacy synthetic fixtures omit messages, fallback is explicitly marked as synthetic."""
    _, _, item = offline_harness
    att = {
        "cond_key": (item["id"], "DIRECT"),
        "started": {"seed": 42, "declared_max_tokens": 512},
        "generation_outcome": {
            "output_text": "Answer: 9\n",
            "measured_generated_tokens": 10,
            "measured_prompt_tokens": 20,
            "finish_reason": "stop",
            "confidence": 0.95,
            "elapsed_ms": 15.0,
            "messages": None,
            "raw_prompt": None,
        },
        "tool_outcome": None,
    }

    checkpoint = MagicMock()
    checkpoint.dataset = {"items": [item]}
    checkpoint.identity = {"evidence": "synthetic_dry_run"}  # Legacy schema

    from experiments.gsm8k_collector import GSM8KCollectorCheckpoint
    record = GSM8KCollectorCheckpoint._build_record_from_evidence(checkpoint, att)

    # Explicitly labeled provenance, never disguised as genuine trace
    assert record["trace"]["generations"][0]["messages_provenance"] == "synthetic_legacy_fallback"
    assert record["trace"]["generations"][0]["messages"] == [{"role": "user", "content": item["query"]}]


def test_interrupted_resumed_reconstruction_fails_closed_if_messages_missing_in_journal(offline_harness):
    """Assert that when generation evidence lacks messages on staged schema, collection and resume fail closed."""
    from experiments.gsm8k_collector import MockStagedRunner
    _, _, item = offline_harness
    ds = {
        "name": "test_ds",
        "items": [item],
        "split_counts": {"train": 1, "calibration": 0},
    }
    identity = {
        "dataset_name": "test_ds",
        "dataset_sha256": "dummy",
        "split_counts": {"train": 1, "calibration": 0},
        "prompt_profile": "english-math-v1",
        "prompt_profile_hash": "dummy_profile",
        "source_hashes": {
            "experiments/research_study.py": "0" * 64,
            "experiments/gsm8k_collector.py": "1" * 64,
        },
        "seed": 42,
        "max_tokens": 512,
        "strategies": ["DIRECT", "COT", "PAL"],
        "evidence": "synthetic_staged_pilot_collection",
    }
    import hashlib
    identity["dataset_sha256"] = hashlib.sha256(json.dumps(ds, sort_keys=True).encode("utf-8")).hexdigest()

    class MissingMessagesRunner(MockStagedRunner):
        def run_generation(self, item, strategy, max_tokens, seed):
            res = super().run_generation(item, strategy, max_tokens, seed)
            res.messages = None  # Intentionally omit messages
            return res

    with tempfile.TemporaryDirectory(prefix="parity-crash-missing-") as tmp:
        run_dir = Path(tmp) / "run"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False})

        # 1. Collection itself fails closed with ValueError when assembling record without messages
        with pytest.raises(ValueError, match="Staged record assembly requires actual messages"):
            run_staged_collection(checkpoint, MissingMessagesRunner(), ds)
        checkpoint.close()

        # 2. Resuming checkpoint from the journal (which recorded generation_outcome with messages=None)
        # must also fail closed with ValueError during terminal evidence recovery
        with pytest.raises(ValueError, match="Staged record assembly requires actual messages"):
            GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False}, resume=True)


def test_interrupted_resumed_reconstruction_recovers_genuine_messages(offline_harness):
    """Assert that when crash occurs after generation outcome with valid messages, resume recovers record with genuine trace."""
    from experiments.gsm8k_collector import SimulatedProcessKill, MockStagedRunner
    _, _, item = offline_harness
    ds = {
        "name": "test_ds",
        "items": [item],
        "split_counts": {"train": 1, "calibration": 0},
    }
    identity = {
        "dataset_name": "test_ds",
        "dataset_sha256": "dummy",
        "split_counts": {"train": 1, "calibration": 0},
        "prompt_profile": "english-math-v1",
        "prompt_profile_hash": "dummy_profile",
        "source_hashes": {
            "experiments/research_study.py": "0" * 64,
            "experiments/gsm8k_collector.py": "1" * 64,
        },
        "seed": 42,
        "max_tokens": 512,
        "strategies": ["DIRECT", "COT", "PAL"],
        "evidence": "synthetic_staged_pilot_collection",
    }
    import hashlib
    identity["dataset_sha256"] = hashlib.sha256(json.dumps(ds, sort_keys=True).encode("utf-8")).hexdigest()

    with tempfile.TemporaryDirectory(prefix="parity-crash-valid-") as tmp:
        run_dir = Path(tmp) / "run"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False})

        original_append = checkpoint.append_event
        def kill_before_record_assembled(kind, *args, **kwargs):
            if kind == "record_assembled":
                raise SimulatedProcessKill("crash before record assembled")
            return original_append(kind, *args, **kwargs)

        checkpoint.append_event = kill_before_record_assembled
        with pytest.raises(SimulatedProcessKill):
            run_staged_collection(checkpoint, MockStagedRunner(), ds)
        checkpoint.close()

        # Resume must succeed and recover record without redispatch
        cp_resume = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False}, resume=True)
        assert ("item_01", "DIRECT") in cp_resume.records
        rec = cp_resume.records[("item_01", "DIRECT")]
        assert rec["trace"]["generations"][0]["messages_provenance"] == "genuine_trace"
        assert rec["trace"]["generations"][0]["messages"] is not None
        cp_resume.close()


# =========================================================================
# 7. End-to-End Collection Trace & Resumed Reconstruction
# =========================================================================

def test_collector_stores_actual_messages_and_token_ids_end_to_end(offline_harness):
    backend, runner, item = offline_harness
    ds = {
        "name": "test_ds",
        "items": [item],
        "split_counts": {"train": 1, "calibration": 0},
    }
    identity = {
        "dataset_name": "test_ds",
        "dataset_sha256": "dummy",
        "split_counts": {"train": 1, "calibration": 0},
        "prompt_profile": "english-math-v1",
        "prompt_profile_hash": "dummy_profile",
        "source_hashes": {
            "experiments/research_study.py": "0" * 64,
            "experiments/gsm8k_collector.py": "1" * 64,
        },
        "seed": 42,
        "max_tokens": 512,
        "strategies": ["DIRECT", "COT", "PAL"],
        "evidence": "synthetic_staged_pilot_collection",
    }
    import hashlib
    identity["dataset_sha256"] = hashlib.sha256(json.dumps(ds, sort_keys=True).encode("utf-8")).hexdigest()

    with tempfile.TemporaryDirectory(prefix="parity-collector-") as tmp:
        run_dir = Path(tmp) / "run"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False})

        injected_text = "```python\nresult = 9\n```\nAnswer: 9\n"
        stream_gen = make_stream_generate(injected_text, 20, "stop")
        with patch("qwen_mlx_backend.stream_generate", stream_gen):
            with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(True, "9")):
                manifest = run_staged_collection(checkpoint, runner, ds)

        checkpoint.close()
        assert manifest["status"] == "complete"

        records = json.loads((run_dir / "records.json").read_text(encoding="utf-8"))
        assert len(records) == 3

        # DIRECT record
        rec_direct = next(r for r in records if r["strategy"] == "DIRECT")
        expected_direct = item["query"] + MATH_EN_SUFFIXES[A.DIRECT]
        actual_messages_direct = rec_direct["trace"]["generations"][0]["messages"]
        assert len(actual_messages_direct) == 1
        assert actual_messages_direct[0]["content"] == expected_direct
        assert actual_messages_direct[0]["content"] != item["query"]
        assert "<|im_start|>user" in rec_direct["trace"]["generations"][0]["raw_prompt"]
        assert rec_direct["trace"]["generations"][0]["messages_provenance"] == "genuine_trace"

        # PAL record
        rec_pal = next(r for r in records if r["strategy"] == "PAL")
        expected_pal = item["query"] + MATH_EN_SUFFIXES[A.PAL]
        actual_messages_pal = rec_pal["trace"]["generations"][0]["messages"]
        assert actual_messages_pal[0]["content"] == expected_pal
        assert rec_pal["trace"]["tools"][0]["ok"] is True
        assert rec_pal["trace"]["tools"][0]["output"] == "9"


def test_staged_measured_evidence_remains_locked(offline_harness):
    """Ensure that non-synthetic staged evidence is still strictly rejected as deferred."""
    _, _, item = offline_harness
    ds = {
        "name": "test_ds",
        "items": [item],
        "split_counts": {"train": 1, "calibration": 0},
    }
    identity = {
        "dataset_name": "test_ds",
        "dataset_sha256": "dummy",
        "split_counts": {"train": 1, "calibration": 0},
        "prompt_profile": "english-math-v1",
        "prompt_profile_hash": "dummy_profile",
        "source_hashes": {
            "experiments/research_study.py": "0" * 64,
            "experiments/gsm8k_collector.py": "1" * 64,
        },
        "seed": 42,
        "max_tokens": 512,
        "strategies": ["DIRECT", "COT", "PAL"],
        "evidence": "measured_staged_collection",  # Non-synthetic attempt
    }
    import hashlib
    identity["dataset_sha256"] = hashlib.sha256(json.dumps(ds, sort_keys=True).encode("utf-8")).hexdigest()

    with tempfile.TemporaryDirectory(prefix="parity-gate-") as tmp:
        run_dir = Path(tmp) / "run"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False})
        checkpoint.close()

        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "complete"
        (run_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

        # write_fitting_seal must fail closed
        with pytest.raises(ValueError, match="Measured staged collection is deferred"):
            write_fitting_seal(run_dir, Path(tmp) / "seal")


# =========================================================================
# 9. Fresh Subprocess Import Guard Verification (MLX Import-Free)
# =========================================================================

def test_parity_and_adapter_run_under_strict_forbidden_mlx_imports():
    """Verify that legacy _chat, staged runner, and collector run in a fresh subprocess whose import hook rejects mlx/mlx_lm."""
    import subprocess
    code = """
import sys, builtins
sys.path.insert(0, ".")
orig = builtins.__import__
forbidden = {'mlx', 'mlx_lm'}
def guarded_import(name, *a, **kw):
    pkg = name.split('.')[0]
    if pkg in forbidden:
        raise AssertionError(f"Forbidden MLX module {name} was imported during offline execution!")
    return orig(name, *a, **kw)
builtins.__import__ = guarded_import

import numpy as np
from reasoning.reasoning_env import ReasoningAction as A
from qwen_mlx_backend import QwenMLXBackend, QwenMLXStagedRunner
from tests.test_qwen_staged_parity import (
    FakeModel,
    FakeTokenizer,
    TokenIdTokenizer,
    make_offline_backend,
    make_stream_generate,
)
from unittest.mock import patch

# 1. Backend + StagedRunner offline instantiation without MLX imports
backend = make_offline_backend()
runner = QwenMLXStagedRunner(backend)
item = {"id": "sub_01", "group_id": "g1", "split": "train", "query": "Find 5 + 7", "answer_type": "number", "decimal_separator": "."}
stream_gen = make_stream_generate("Answer: 12\\n", 8, "stop")

with patch("qwen_mlx_backend.stream_generate", stream_gen):
    # 2. Legacy run through real _chat
    legacy_ans, legacy_conf, legacy_tok = backend.run(A.DIRECT, item["query"])
    assert legacy_ans == "12"

    # 3. Staged run_generation through real _chat for DIRECT, COT, PAL
    res_dir = runner.run_generation(item, "DIRECT", max_tokens=100, seed=42)
    assert res_dir.text == "Answer: 12\\n"

    res_cot = runner.run_generation(item, "COT", max_tokens=100, seed=42)
    assert res_cot.text == "Answer: 12\\n"

    res_pal = runner.run_generation(item, "PAL", max_tokens=100, seed=42)
    assert res_pal.text == "Answer: 12\\n"

# 4. PAL tool execution stage
tool_res = runner.run_tool("result = 12", timeout_seconds=5.0)
assert tool_res.ok is True
assert tool_res.output == "12"

# 5. Token ID tokenizer without MLX imports
tok_backend = make_offline_backend(tokenizer=TokenIdTokenizer())
tok_runner = QwenMLXStagedRunner(tok_backend)
with patch("qwen_mlx_backend.stream_generate", stream_gen):
    res_tok = tok_runner.run_generation(item, "DIRECT", max_tokens=100, seed=42)
assert res_tok.prompt_token_ids == [101, 2054, 2003, 102]

# 6. Verify neither mlx nor mlx_lm is present in sys.modules
for mod in forbidden:
    assert mod not in sys.modules, f"Forbidden module {mod} found in sys.modules!"

print("STAGED_PARITY_ZERO_MLX_SUBPROCESS_OK")
"""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-c", code], cwd=str(root), capture_output=True, text=True)
    assert result.returncode == 0, f"Subprocess failed with code {result.returncode}:\n{result.stderr}"
    assert "STAGED_PARITY_ZERO_MLX_SUBPROCESS_OK" in result.stdout

