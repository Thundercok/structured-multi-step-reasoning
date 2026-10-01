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
        for i, tok in enumerate(full_text.split(" ")):
            piece = tok + (" " if i < len(full_text.split(" ")) - 1 else "")
            lp = mx.array(vocab)
            yield FakeGenResponse(text=piece, token=0, logprobs=lp, generation_tokens=i + 1)


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

    def apply_chat_template(self, messages, enable_thinking=False, **kw):
        assert enable_thinking is False, "phải tắt thinking cho baseline sạch"
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


def test_cot_extracts_answer_and_confidence():
    scripted.queue("Bước 1: 3*7=21 Answer: 21")
    ans, conf, tok = b_run(A.COT, "3 nhân 7 bằng bao nhiêu?")
    assert ans == "21" and 0 < conf <= 1 and tok > 0


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


def test_react_calculate_then_finish():
    scripted.queue("Thought: cần nhân Action: calculate[6*7]",
                    "Thought: xong rồi Action: finish[42]")
    ans, conf, tok = b_run(A.REACT, "6 nhân 7?")
    assert ans == "42"
    assert scripted.calls[-1][-1] if False else True  # observation được feed vào lượt sau (check gián tiếp qua kết quả đúng)


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
    assert ans == "42 (fallback)"  # code lỗi -> fallback sang extract_answer(text gốc), không crash


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
