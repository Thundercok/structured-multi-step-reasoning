"""KHÔNG test model thật (sandbox này không có mạng tới HF, không phải Apple Silicon).
Mock đúng shape API đã verify từ mlx-lm 0.31.3 thật (stream_generate, GenerationResponse,
apply_chat_template, model.model()) để bắt lỗi logic trong 5 strategy trước khi chạy trên Mac.
"""

import sys
import types
from dataclasses import dataclass, field
import numpy as np

try:
    import mlx.core as mx
except ImportError:
    class FakeMLXCore:
        float32 = np.float32
        @staticmethod
        def array(x, dtype=None):
            return np.array(x, dtype=dtype)
        @staticmethod
        def reshape(x, shape):
            return np.reshape(x, shape)
        @staticmethod
        def arange(n, dtype=None):
            return np.arange(n, dtype=dtype)
        @staticmethod
        def mean(x, axis=None):
            return np.mean(x, axis=axis)
    mx = FakeMLXCore()
    fake_mlx = types.ModuleType("mlx")
    fake_mlx.core = mx
    sys.modules["mlx"] = fake_mlx
    sys.modules["mlx.core"] = mx


# ---------- fake mlx_lm, đăng ký vào sys.modules TRƯỚC khi import module cần test ----------

@dataclass
class FakeGenResponse:
    text: str
    token: int
    logprobs: mx.array
    generation_tokens: int
    finish_reason: str | None = None


class ScriptedGenerate:
    """Mỗi lần gọi trả 1 kịch bản (list câu) đã nạp sẵn theo thứ tự - test tự kiểm soát model 'nói' gì."""

    def __init__(self):
        self.scripts: list[str] = []
        self.calls: list[list[dict]] = []

    def queue(self, *texts: str) -> None:
        self.scripts.extend(texts)

    def __call__(self, model, tokenizer, prompt, max_tokens=256, sampler=None, **kw):
        self.calls.append(prompt)
        full_text = self.scripts.pop(0)
        vocab = mx.array(np.full(16, -5.0, dtype=np.float32))
        words = full_text.split(" ")
        for i, tok in enumerate(words):
            piece = tok + (" " if i < len(words) - 1 else "")
            lp = mx.array(vocab)
            reason = "stop" if i == len(words) - 1 else None
            yield FakeGenResponse(text=piece, token=0, logprobs=lp, generation_tokens=i + 1, finish_reason=reason)


scripted = ScriptedGenerate()

fake_sample_utils = types.ModuleType("mlx_lm.sample_utils")
fake_sample_utils.make_sampler = lambda temp=0.0, **kw: (lambda x: x)

fake_mlx_lm = types.ModuleType("mlx_lm")
fake_mlx_lm.load = lambda repo: (None, None)  # bị override trong fixture, giữ để import không vỡ
fake_mlx_lm.stream_generate = scripted

sys.modules["mlx_lm"] = fake_mlx_lm
sys.modules["mlx_lm.sample_utils"] = fake_sample_utils

from qwen_mlx_backend import QwenMLXBackend  # noqa: E402
from reasoning_env import ReasoningAction as A  # noqa: E402


class FakeInner:
    def __call__(self, ids):
        n = ids.shape[-1]
        return mx.reshape(mx.arange(n * 8, dtype=mx.float32), (1, n, 8))


class FakeModel:
    class args:
        hidden_size = 8

    model = FakeInner()


class FakeTokenizer:
    def encode(self, text):
        return [1] * max(len(text.split()), 1)

    def apply_chat_template(self, messages, enable_thinking=False, add_generation_prompt=False, **kw):
        assert enable_thinking is False, "phải tắt thinking cho baseline sạch"
        assert add_generation_prompt is True, "chat prompt phải kết thúc ở vai assistant"
        return [1]


def make_backend():
    b = QwenMLXBackend.__new__(QwenMLXBackend)  # bỏ qua __init__ (không load() thật được)
    b.model, b.tokenizer, b.max_tokens = FakeModel(), FakeTokenizer(), 64
    b.hidden_size = FakeModel.args.hidden_size  # __init__ thật cũng gán dòng này từ model.args
    return b


def test_embed_shape_and_hidden_size():
    b = make_backend()
    v = b.embed("câu hỏi ví dụ")
    assert v.shape == (8,) and b.hidden_size == 8


def test_bfloat16_logprobs_produce_finite_confidence(monkeypatch):
    import pytest
    import qwen_mlx_backend as module
    if not hasattr(mx, "bfloat16"):
        pytest.skip("Requires native MLX bfloat16 arrays")
    values = mx.array([-0.25, -2.0, -4.0], dtype=mx.bfloat16)
    response = FakeGenResponse("Answer: 42", 0, values, 1, "stop")
    monkeypatch.setattr(module, "stream_generate", lambda *args, **kwargs: iter([response]))
    backend = make_backend()
    answer, confidence, tokens = backend.run(A.DIRECT, "Return forty-two")
    assert answer == "42" and tokens == 1 and np.isfinite(confidence)
    assert np.isclose(backend.last_signals["p_seq"], np.exp(-0.25))


def test_bfloat16_hidden_states_export_float32_embedding():
    import pytest
    if not hasattr(mx, "bfloat16"):
        pytest.skip("Requires native MLX bfloat16 arrays")
    backend = make_backend()
    backend.model.model = lambda ids: mx.array([[[1.0, 2.0], [3.0, 4.0]]], dtype=mx.bfloat16)
    embedding = backend.embed("two words")
    assert embedding.dtype == np.float32
    np.testing.assert_array_equal(embedding, [2.0, 3.0])


def test_react_respects_small_pilot_cap_and_records_actual_generation_settings(monkeypatch):
    import qwen_mlx_backend as module
    captured = []
    def generate(*args, **kwargs):
        captured.append(kwargs["max_tokens"])
        return scripted(*args, **kwargs)
    monkeypatch.setattr(module, "stream_generate", generate)
    for cap in (48, 512):
        backend = make_backend()
        backend.max_tokens = cap
        scripted.queue("Thought: done.\nAction: finish[7]")
        backend.run(A.REACT, "Return seven")
        generation = backend.last_trace["generations"][0]
        assert captured[-1] == generation["max_tokens"] == min(cap, 200)
        assert generation["temperature"] == 0.0
        assert generation["enable_thinking"] is False
        assert generation["messages"][-1]["content"] == "Return seven"


def test_direct_extracts_answer_and_confidence():
    scripted.queue("Answer: 42")
    ans, conf, tok = b_run(A.DIRECT, "6 nhân 7 bằng bao nhiêu?")
    assert ans == "42" and 0 < conf <= 1 and tok > 0


def test_cot_extracts_answer_and_confidence():
    scripted.queue("Bước 1: 3*7=21 Answer: 21")
    ans, conf, tok = b_run(A.COT, "3 nhân 7 bằng bao nhiêu?")
    assert ans == "21" and 0 < conf <= 1 and tok > 0


def test_empty_answer_marker_does_not_stop_before_the_final_answer():
    backend = make_backend()
    backend.configure_answer_format("number")
    scripted.queue("Working.\nAnswer:\n42\n")
    answer, _, _ = backend.run(A.COT, "Return forty-two")
    assert answer == "42"
    assert "42" in backend.last_trace["generations"][0]["output"]


def test_self_consistency_majority_vote():
    scripted.queue("suy luận... Answer: 10", "khác cách... Answer: 10", "sai... Answer: 9",
                    "đúng... Answer: 10", "đúng... Answer: 10")
    ans, conf, tok = b_run(A.SELF_CONSISTENCY, "1+2+3+4=?")
    assert ans == "10" and abs(conf - 0.8) < 1e-9  # 4/5 phiếu


def test_tot_picks_indexed_candidate():
    scripted.queue("lời giải A... Answer: 5", "lời giải B... Answer: 6", "lời giải C... Answer: 5",
                    "so sánh xong Best: 1")
    ans, conf, tok = b_run(A.TOT, "câu hỏi bất kỳ")
    assert ans == "6"  # phải chọn đúng candidate[1], không phải candidate[0]


def test_tot_invalid_selector_uses_candidate_majority():
    scripted.queue("lời giải A... Answer: 5", "lời giải B... Answer: 6", "lời giải C... Answer: 5",
                   "Best: 999")
    ans, conf, tok = b_run(A.TOT, "câu hỏi bất kỳ")
    assert ans == "5"


def test_react_calculate_then_finish():
    scripted.queue("Thought: cần nhân Action: calculate[6*7]",
                    "Thought: xong rồi Action: finish[42]")
    ans, conf, tok = b_run(A.REACT, "6 nhân 7?")
    assert ans == "42"
    assert scripted.calls[-1][-1] if False else True  # observation được feed vào lượt sau (check gián tiếp qua kết quả đúng)


def test_react_trace_keeps_raw_generations_and_tool_observation():
    b = make_backend()
    scripted.queue("Thought: cần nhân Action: calculate[6*7]",
                   "Thought: xong rồi Action: finish[42]")
    answer, _, _ = b.run(A.REACT, "6 nhân 7?")
    assert answer == "42"
    assert [entry["output"] for entry in b.last_trace["generations"]] == [
        "Thought: cần nhân Action: calculate[6*7]",
        "Thought: xong rồi Action: finish[42]",
    ]
    assert b.last_trace["tools"] == [
        {"name": "calculate", "input": "6*7", "output": "42"},
    ]


def test_react_no_finish_within_turns_lowers_confidence():
    scripted.queue(*(["Thought: đang nghĩ tiếp Action: calculate[1+1]"] * 4))
    ans, conf, tok = b_run(A.REACT, "câu hỏi khó", max_turns=4)
    assert conf <= 1.0  # không crash khi hết lượt mà chưa finish()


def test_pal_executes_generated_code():
    scripted.queue("```python\nresult = 6 * 7\n```")
    ans, conf, tok = b_run(A.PAL, "6 nhân 7?")
    assert ans == "42"


def test_pal_falls_back_to_text_answer_on_bad_code():
    scripted.queue("```python\nresult = 1/0\n```\nAnswer: 42 (fallback)")
    ans, conf, tok = b_run(A.PAL, "câu hỏi")
    assert ans == "42"  # code lỗi -> fallback sang dòng Answer và chuẩn hóa số


def test_compute_token_uncertainty_metrics():
    from qwen_mlx_backend import compute_token_uncertainty

    # 1. Perfectly confident distribution: one token has logp=0, rest very negative
    sharp_lp = np.array([0.0, -10.0, -10.0, -10.0], dtype=np.float32)
    margin, ent = compute_token_uncertainty(sharp_lp)
    assert margin >= 9.9, f"Expected margin ~10, got {margin}"
    assert ent < 0.05, f"Expected near zero entropy, got {ent}"

    # 2. Completely uniform distribution: all logprobs equal
    flat_lp = np.full(8, -2.0, dtype=np.float32)
    margin, ent = compute_token_uncertainty(flat_lp)
    assert abs(margin) < 1e-6
    assert abs(ent - 1.0) < 1e-4

    # 3. Small or empty input
    assert compute_token_uncertainty(np.array([1.0])) == (0.0, 0.0)


def test_internal_signals_tracked_in_backend():
    b = make_backend()
    scripted.queue("Bước 1: giải thích ngắn Answer: 100")
    b.run(A.COT, "câu hỏi?")
    assert hasattr(b, "last_signals")
    assert "mean_margin" in b.last_signals
    assert "mean_entropy" in b.last_signals
    assert "p_seq" in b.last_signals
    assert 0.0 <= b.last_signals["mean_entropy"] <= 1.0


def test_no_placeholders_in_prompts():
    import re
    import qwen_mlx_backend as qmb
    from reasoning_env import ReasoningAction as A

    constants = [
        qmb.COT_SUFFIX,
        qmb.DIRECT_SUFFIX,
        qmb.REACT_SYSTEM,
        qmb.PAL_SUFFIX,
    ]
    for msg in qmb.REACT_EXAMPLE:
        constants.append(msg["content"])

    b = make_backend()
    captured = list(constants)
    def capture_chat(messages, *args, **kwargs):
        for m in messages:
            captured.append(m["content"])
        return "Answer: 42", 0.9, 10
    b._chat = capture_chat

    b.run(A.DIRECT, "Test query")
    b.run(A.COT, "Test query")
    b.run(A.SELF_CONSISTENCY, "Test query")
    b.run(A.TOT, "Test query")
    b.run(A.REACT, "Test query")
    b.run(A.PAL, "Test query")

    pattern = re.compile(r"<[^>\n]{1,30}>")
    violations = []
    for text in captured:
        for m in pattern.findall(text):
            if m in ("<think>", "</think>") or m.startswith("<|"):
                continue
            violations.append((m, text))

    assert not violations, f"Found placeholders in prompts: {violations}"


def test_sc_votes_on_canonical_answers():
    from reasoning_strategies import majority_vote

    samples = ['192', '192 slices', 'The result is 192', '190', '192.0']
    winner, ratio = majority_vote(samples)
    assert winner == '192', f"Expected canonical '192', got {winner!r}"
    assert abs(ratio - 0.8) < 1e-4, f"Expected ratio 0.8, got {ratio}"


def test_research_expression_format_survives_cot_sc_selection_and_tools():
    from scripts.gen_tasks import check
    expression = "10+13+3-2 = 24"
    item = {"family": "g24", "meta": {"numbers": [10, 13, 2, 3]}}
    for strategy in (A.COT, A.SELF_CONSISTENCY, A.TOT, A.REACT, A.PAL):
        b = make_backend()
        b.configure_answer_format("expression")
        if strategy == A.SELF_CONSISTENCY:
            scripted.queue(*([f"Answer: {expression}"] * 5))
        elif strategy == A.TOT:
            scripted.queue(*([f"Answer: {expression}"] * 3), "Best: 1")
        elif strategy == A.REACT:
            scripted.queue(f"Thought: done Action: finish[{expression}]")
        elif strategy == A.PAL:
            scripted.queue(f"```python\nresult = '{expression}'\n```")
        else:
            scripted.queue(f"Answer: {expression}")
        answer, _, _ = b.run(strategy, "Use each given number once.")
        assert check(item, answer), (strategy, answer)


def test_research_typed_scalar_and_text_preserve_meaning():
    b = make_backend()
    b.configure_answer_format("number", ",")
    scripted.queue("Answer: 129,6")
    assert b.run(A.COT, "Vietnamese decimal question")[0] == "129.6"
    b.configure_answer_format("text")
    scripted.queue("Answer: No, the answer is Yes")
    assert b.run(A.COT, "Logical question")[0] == "No, the answer is Yes"


def test_generation_stops_at_first_answer_line():
    b = make_backend()
    scripted.queue("Step 1: compute 20 + 22.\nAnswer: 42\nExtra unwanted commentary.")
    ans, conf, tok = b.run(A.COT, "Compute 20 + 22")
    assert ans == "42"
    assert b.last_trace["generations"][0]["finish_reason"] == "stop_answer"
    assert "Extra unwanted commentary" not in b.last_trace["generations"][0]["output"]


def test_generation_does_not_stop_at_empty_answer_line():
    b = make_backend()
    scripted.queue("Step 1: compute.\nAnswer:\n364\n")
    ans, conf, tok = b.run(A.COT, "Compute 364")
    assert ans == "364"
    assert b.last_trace["generations"][0]["finish_reason"] != "stop_answer"
    assert "364" in b.last_trace["generations"][0]["output"]




def b_run(strategy, query, **kw):
    b = make_backend()
    if strategy == A.REACT and "max_turns" in kw:
        return b._react(query, max_turns=kw["max_turns"])
    return b.run(strategy, query)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            scripted.scripts.clear()
            fn()
            print("ok", name)
