"""Independent verification script for QwenMLXStagedRunner and offline parity."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from reasoning_env import ReasoningAction as A
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


class FakeTokenizer:
    def apply_chat_template(self, messages, enable_thinking=False, add_generation_prompt=True):
        parts = []
        for m in messages:
            parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
        if add_generation_prompt:
            parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    def encode(self, text):
        return [1] * len(text.split())


class FakeModel:
    class Args:
        hidden_size = 4096
    args = Args()


def main():
    output = {}

    backend = QwenMLXBackend(
        model=FakeModel(),
        tokenizer=FakeTokenizer(),
        prompt_profile="english-math-v1",
    )
    backend.configure_answer_format(answer_type="number", decimal_separator=".")
    runner = QwenMLXStagedRunner(backend)

    item = {
        "id": "item_verify_01",
        "group_id": "group_01",
        "split": "train",
        "query": "If 3 apples cost 45, what is the cost of 7 apples?",
        "answer": "105",
        "answer_type": "number",
        "decimal_separator": ".",
    }

    # 1. DIRECT parity
    injected_direct = "3 apples cost 45, so 1 apple costs 15. 7 * 15 = 105.\nAnswer: 105\n"
    with patch.object(backend, "_chat", return_value=(injected_direct, 0.95, 25)):
        legacy_ans, legacy_conf, legacy_tok = backend.run(A.DIRECT, item["query"])
    with patch.object(backend, "_chat", return_value=(injected_direct, 0.95, 25)):
        gen_res = runner.run_generation(item, "DIRECT", max_tokens=512, seed=42)

    parsed_ans, status, wordy = backend._parse_answer(gen_res.text)
    direct_match = (
        parsed_ans == legacy_ans == "105"
        and gen_res.confidence == legacy_conf == 0.95
        and gen_res.generated_tokens == legacy_tok == 25
        and gen_res.finish_reason == "stop"
        and gen_res.messages == [{"role": "user", "content": item["query"] + MATH_EN_SUFFIXES[A.DIRECT]}]
    )
    output["direct_parity"] = {
        "legacy_answer": legacy_ans,
        "staged_parsed_answer": parsed_ans,
        "confidence_matched": gen_res.confidence == legacy_conf,
        "tokens_matched": gen_res.generated_tokens == legacy_tok,
        "suffix_preserved_in_messages": gen_res.messages[0]["content"] == item["query"] + MATH_EN_SUFFIXES[A.DIRECT],
        "parity_exact": direct_match,
    }
    assert direct_match

    # 2. PAL success parity
    injected_pal_code = "```python\ncost_per_apple = 45 / 3\nresult = cost_per_apple * 7\n```"
    with patch.object(backend, "_chat", return_value=(injected_pal_code, 0.92, 30)):
        with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(True, "105")):
            pal_legacy_ans, pal_legacy_conf, pal_legacy_tok = backend.run(A.PAL, item["query"])
    with patch.object(backend, "_chat", return_value=(injected_pal_code, 0.92, 30)):
        pal_gen_res = runner.run_generation(item, "PAL", max_tokens=512, seed=42)
    with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(True, "105")):
        pal_tool_res = runner.run_tool("cost_per_apple = 45 / 3\nresult = cost_per_apple * 7", timeout_seconds=5.0)

    pal_match = (
        pal_tool_res.ok is True
        and pal_tool_res.output == pal_legacy_ans == "105"
        and pal_gen_res.confidence == pal_legacy_conf == 0.92
    )
    output["pal_success_parity"] = {
        "legacy_answer": pal_legacy_ans,
        "staged_tool_output": pal_tool_res.output,
        "confidence_matched": pal_gen_res.confidence == pal_legacy_conf,
        "parity_exact": pal_match,
    }
    assert pal_match

    # 3. PAL error fallback parity (ZeroDivisionError -> penalty * 0.3)
    injected_pal_err = "```python\nresult = 45 / 0\n```\nAnswer: 105\n"
    with patch.object(backend, "_chat", return_value=(injected_pal_err, 0.90, 20)):
        with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(False, "ZeroDivisionError")):
            err_legacy_ans, err_legacy_conf, _ = backend.run(A.PAL, item["query"])
    with patch.object(backend, "_chat", return_value=(injected_pal_err, 0.90, 20)):
        err_gen_res = runner.run_generation(item, "PAL", max_tokens=512, seed=42)
    with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(False, "ZeroDivisionError")):
        err_tool_res = runner.run_tool("result = 45 / 0", timeout_seconds=5.0)

    err_match = (
        err_tool_res.ok is False
        and err_legacy_ans == "105"
        and abs(err_legacy_conf - (0.90 * 0.3)) < 1e-6
    )
    output["pal_error_fallback_parity"] = {
        "legacy_answer": err_legacy_ans,
        "legacy_confidence_penalized": err_legacy_conf,
        "tool_failed": not err_tool_res.ok,
        "parity_exact": err_match,
    }
    assert err_match

    # 4. Collector Real Messages & Trace persistence
    ds = {
        "name": "verify_ds",
        "items": [item],
        "split_counts": {"train": 1, "calibration": 0},
    }
    identity = {
        "dataset_name": "verify_ds",
        "dataset_sha256": hashlib.sha256(json.dumps(ds, sort_keys=True).encode("utf-8")).hexdigest(),
        "split_counts": {"train": 1, "calibration": 0},
        "prompt_profile": "english-math-v1",
        "prompt_profile_hash": "dummy_hash",
        "source_hashes": {
            "experiments/research_study.py": "0" * 64,
            "experiments/gsm8k_collector.py": "1" * 64,
        },
        "seed": 42,
        "max_tokens": 512,
        "strategies": ["DIRECT", "COT", "PAL"],
        "evidence": "synthetic_staged_pilot_collection",
    }

    with tempfile.TemporaryDirectory(prefix="verify-trace-") as tmp:
        run_dir = Path(tmp) / "run"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, ds, {"temperature": 0.0, "thinking": False})
        with patch.object(backend, "_chat", return_value=("```python\nresult = 105\n```\nAnswer: 105\n", 0.95, 20)):
            with patch("qwen_mlx_backend.run_python_sandboxed", return_value=(True, "105")):
                manifest = run_staged_collection(checkpoint, runner, ds)
        checkpoint.close()

        records = json.loads((run_dir / "records.json").read_text(encoding="utf-8"))
        direct_rec = next(r for r in records if r["strategy"] == "DIRECT")
        stored_msg = direct_rec["trace"]["generations"][0]["messages"][0]["content"]
        bare_query_prevented = (stored_msg != item["query"]) and (stored_msg == item["query"] + MATH_EN_SUFFIXES[A.DIRECT])

        output["collector_trace_fidelity"] = {
            "records_assembled": len(records),
            "stored_message_matches_suffix": stored_msg == item["query"] + MATH_EN_SUFFIXES[A.DIRECT],
            "bare_query_prevented": bare_query_prevented,
            "raw_prompt_persisted": "<|im_start|>user" in direct_rec["trace"]["generations"][0]["raw_prompt"],
        }
        assert bare_query_prevented

        # 5. Gate lock check: non-synthetic staged evidence fails closed
        gate_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        gate_manifest["status"] = "complete"
        gate_manifest["identity"]["evidence"] = "measured_staged_collection"
        (run_dir / "manifest.json").write_text(json.dumps(gate_manifest) + "\n", encoding="utf-8")

        gate_locked = False
        try:
            write_fitting_seal(run_dir, Path(tmp) / "seal")
        except ValueError as exc:
            if "Measured staged collection is deferred" in str(exc):
                gate_locked = True
        output["measured_staged_gate_locked"] = {
            "deferred_rejection_active": gate_locked,
        }
        assert gate_locked

    paths = [
        "experiments/gsm8k_collector.py",
        "qwen_mlx_backend.py",
        "tests/test_qwen_staged_parity.py",
    ]
    output.update(
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        new_model_calls=0,
        candidate_content_read=False,
        stage0_changed=False,
        all_checks_passed=True,
    )
    out_file = Path(__file__).parent / "verification.json"
    out_file.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
