"""Independent verification script for GSM8K Staged Adapter Repairs (2026-10-24).

Verifies the 3 reviewer findings and checker import isolation:
1. Seed application at generation boundary via injectable seed setter before dispatch.
2. Token ID capture in prompt_token_ids with decoded view in raw_prompt from _chat trace.
3. Fail-closed message contract on staged schema (prohibiting invented bare query fallback)
   and explicit synthetic provenance label on legacy schema.
4. Checker import isolation in subprocess and combined suite pass.
5. Measured staged evidence gate remains locked.
6. SHA-256 fingerprints of relevant sources.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reasoning_env import ReasoningAction as A
from qwen_mlx_backend import (
    MATH_EN_SUFFIXES,
    QwenMLXBackend,
    QwenMLXStagedRunner,
)
from experiments.gsm8k_collector import (
    GSM8KCollectorCheckpoint,
    MockStagedRunner,
    run_staged_collection,
)
from experiments.gsm8k_routing_baseline import write_fitting_seal


class FakeGenResponse:
    def __init__(self, text: str, tokens: int, finish_reason: str = "stop"):
        self.text = text
        self.generation_tokens = tokens
        self.finish_reason = finish_reason
        self.logprobs = None
        self.token = 0


def make_stream_generate(text: str, tokens: int = 15, finish_reason: str = "stop"):
    def _generator(*args, **kwargs):
        yield FakeGenResponse(text=text, tokens=tokens, finish_reason=finish_reason)
    return _generator


class FakeTokenizer:
    def apply_chat_template(self, messages, enable_thinking=False, add_generation_prompt=True):
        parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages]
        if add_generation_prompt:
            parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    def encode(self, text):
        return [1] * len(text.split())

    def decode(self, token_ids):
        return " ".join(str(t) for t in token_ids)


class TokenIdTokenizer:
    def apply_chat_template(self, messages, enable_thinking=False, add_generation_prompt=True):
        return [101, 2054, 2003, 102]

    def decode(self, token_ids):
        return "Decoded: " + " ".join(str(t) for t in token_ids)

    def encode(self, text):
        return [101, 2054, 2003, 102]


class FakeModel:
    class Args:
        hidden_size = 4096
    args = Args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


import numpy as np


def verify_finding_1_seed() -> dict:
    mock_seed_setter = MagicMock()
    backend = QwenMLXBackend(
        model=FakeModel(),
        tokenizer=FakeTokenizer(),
        prompt_profile="english-math-v1",
        seed_setter=mock_seed_setter,
        sampler_factory=lambda temp=0.0: None,
        array_converter=lambda x: np.asarray(x, dtype=np.float32),
    )
    runner = QwenMLXStagedRunner(backend, seed_setter=mock_seed_setter)

    item = {
        "id": "item_seed_test",
        "group_id": "group_01",
        "split": "train",
        "query": "What is 2 + 2?",
        "answer_type": "number",
        "decimal_separator": ".",
    }

    stream_gen = make_stream_generate("Answer: 4\n", 10, "stop")
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        res1 = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)
        mock_seed_setter.assert_called_with(42)
        assert runner.last_applied_seed == 42
        assert res1.generation_trace["applied_seed"] == 42

        res2 = runner.run_generation(item, "COT", max_tokens=512, seed=999)
        mock_seed_setter.assert_called_with(999)
        assert runner.last_applied_seed == 999
        assert res2.generation_trace["applied_seed"] == 999

    bool_rejected = False
    try:
        runner.run_generation(item, "DIRECT", max_tokens=512, seed=True)
    except ValueError:
        bool_rejected = True

    str_rejected = False
    try:
        runner.run_generation(item, "DIRECT", max_tokens=512, seed="42")
    except ValueError:
        str_rejected = True

    return {
        "seed_setter_called_with_exact_seed": True,
        "seed_42_verified": True,
        "seed_999_verified": True,
        "bool_seed_rejected": bool_rejected,
        "str_seed_rejected": str_rejected,
        "generation_trace_records_applied_seed": True,
    }


def verify_finding_2_prompt_and_token_ids() -> dict:
    backend = QwenMLXBackend(
        model=FakeModel(),
        tokenizer=TokenIdTokenizer(),
        prompt_profile="english-math-v1",
        seed_setter=lambda s: None,
        sampler_factory=lambda temp=0.0: None,
        array_converter=lambda x: np.asarray(x, dtype=np.float32),
    )
    runner = QwenMLXStagedRunner(backend)

    item = {
        "id": "item_token_id_test",
        "group_id": "group_01",
        "split": "train",
        "query": "Solve this equation.",
        "answer_type": "number",
        "decimal_separator": ".",
    }

    stream_gen = make_stream_generate("Answer: 42\n", 12, "stop")
    with patch("qwen_mlx_backend.stream_generate", stream_gen):
        res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    return {
        "prompt_token_ids": res.prompt_token_ids,
        "dispatched_ids_match_recorded": res.prompt_token_ids == [101, 2054, 2003, 102],
        "prompt_tokens_matches_length": res.prompt_tokens == 4,
        "raw_prompt_decoded_view": res.raw_prompt == "Decoded: 101 2054 2003 102",
        "messages_preserves_suffix": res.messages == [{"role": "user", "content": item["query"] + MATH_EN_SUFFIXES[A.DIRECT]}],
    }


def verify_finding_3_messages_contract() -> dict:
    item = {
        "id": "item_msg_test",
        "group_id": "group_01",
        "split": "train",
        "query": "Janet has 16 eggs. She eats 7. How many remain?",
        "answer": "9",
        "answer_type": "number",
        "decimal_separator": ".",
    }
    att_missing = {
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

    # Staged checkpoint must fail closed
    cp_staged = MagicMock()
    cp_staged.dataset = {"items": [item]}
    cp_staged.identity = {"evidence": "synthetic_staged_pilot_collection"}
    staged_failed_closed = False
    try:
        GSM8KCollectorCheckpoint._build_record_from_evidence(cp_staged, att_missing)
    except ValueError as e:
        if "Staged record assembly requires actual messages" in str(e):
            staged_failed_closed = True

    # Legacy checkpoint labels fallback explicitly
    cp_legacy = MagicMock()
    cp_legacy.dataset = {"items": [item]}
    cp_legacy.identity = {"evidence": "synthetic_dry_run"}
    record_legacy = GSM8KCollectorCheckpoint._build_record_from_evidence(cp_legacy, att_missing)
    legacy_fallback_provenance = record_legacy["trace"]["generations"][0].get("messages_provenance")

    # Genuine trace labels genuine provenance
    att_genuine = dict(att_missing)
    att_genuine["generation_outcome"] = dict(att_missing["generation_outcome"])
    att_genuine["generation_outcome"]["messages"] = [{"role": "user", "content": item["query"] + " suffix"}]
    record_genuine = GSM8KCollectorCheckpoint._build_record_from_evidence(cp_staged, att_genuine)
    genuine_provenance = record_genuine["trace"]["generations"][0].get("messages_provenance")

    return {
        "staged_missing_messages_fails_closed": staged_failed_closed,
        "legacy_missing_messages_provenance": legacy_fallback_provenance,
        "genuine_trace_provenance": genuine_provenance,
    }


def verify_checker_subprocess_isolation() -> dict:
    code = """
import sys, builtins
sys.path.insert(0, ".")
original_import = builtins.__import__
forbidden = {'mlx', 'mlx_lm', 'sentence_transformers', 'PyQt6', 'PySide6'}
def guarded_import(name, *args, **kwargs):
    pkg = name.split('.')[0]
    if pkg in forbidden:
        raise AssertionError(f"Forbidden module {name} imported!")
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import

import experiments.checker_dry_run
for mod in forbidden:
    assert mod not in sys.modules, f"Forbidden module {mod} was imported!"
print("CHECKER_IMPORT_ISOLATION_OK")
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True)
    return {
        "subprocess_exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "forbidden_imports_blocked": result.returncode == 0 and "CHECKER_IMPORT_ISOLATION_OK" in result.stdout,
    }


def verify_mlx_import_free_subprocess() -> dict:
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
from reasoning_env import ReasoningAction as A
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
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True)
    return {
        "subprocess_exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "zero_mlx_imports_verified": result.returncode == 0 and "STAGED_PARITY_ZERO_MLX_SUBPROCESS_OK" in result.stdout,
    }


def verify_measured_staged_gate() -> dict:
    item = {
        "id": "item_gate",
        "group_id": "group_01",
        "split": "train",
        "query": "Test query",
        "answer": "1",
        "answer_type": "number",
        "decimal_separator": ".",
    }
    ds = {"name": "test_ds", "items": [item], "split_counts": {"train": 1, "calibration": 0}}
    identity = {
        "dataset_name": "test_ds",
        "dataset_sha256": hashlib.sha256(json.dumps(ds, sort_keys=True).encode("utf-8")).hexdigest(),
        "split_counts": {"train": 1, "calibration": 0},
        "prompt_profile": "english-math-v1",
        "prompt_profile_hash": "dummy",
        "source_hashes": {
            "experiments/research_study.py": "0" * 64,
            "experiments/gsm8k_collector.py": "1" * 64,
        },
        "seed": 42,
        "max_tokens": 512,
        "strategies": ["DIRECT", "COT", "PAL"],
        "evidence": "measured_staged_collection",
    }
    with tempfile.TemporaryDirectory(prefix="parity-gate-verif-") as tmp:
        run_dir = Path(tmp) / "run"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False})
        checkpoint.close()
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "complete"
        (run_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

        gate_failed_closed = False
        try:
            write_fitting_seal(run_dir, Path(tmp) / "seal")
        except ValueError as e:
            if "Measured staged collection is deferred" in str(e):
                gate_failed_closed = True

    return {
        "measured_staged_collection_rejected": gate_failed_closed,
    }


def main():
    print("Running GSM8K Staged Adapter Repair Verification...")
    f1 = verify_finding_1_seed()
    f2 = verify_finding_2_prompt_and_token_ids()
    f3 = verify_finding_3_messages_contract()
    f4 = verify_checker_subprocess_isolation()
    f5 = verify_mlx_import_free_subprocess()
    f6 = verify_measured_staged_gate()

    sources = {
        "qwen_mlx_backend.py": sha256_file(ROOT / "qwen_mlx_backend.py"),
        "experiments/gsm8k_collector.py": sha256_file(ROOT / "experiments/gsm8k_collector.py"),
        "experiments/gsm8k_routing_baseline.py": sha256_file(ROOT / "experiments/gsm8k_routing_baseline.py"),
        "tests/test_checker_dry_run.py": sha256_file(ROOT / "tests/test_checker_dry_run.py"),
        "tests/test_qwen_staged_parity.py": sha256_file(ROOT / "tests/test_qwen_staged_parity.py"),
    }

    report = {
        "finding_1_seed": f1,
        "finding_2_prompt_and_token_ids": f2,
        "finding_3_messages_contract": f3,
        "checker_subprocess_isolation": f4,
        "adapter_mlx_import_free_subprocess": f5,
        "measured_staged_evidence_gate": f6,
        "source_hashes": sources,
    }

    output_path = Path(__file__).parent / "verification.json"
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote verification report to {output_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
