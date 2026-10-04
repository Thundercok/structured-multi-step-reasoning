"""Chạy trên máy Mac thật (cần Apple Silicon + mạng tới Hugging Face) - sandbox này build code
không có 2 thứ đó nên phần load/generate KHÔNG được test end-to-end ở đây, chỉ verify signature
đúng với mlx-lm 0.31.3 (xem ghi chú cuối file). Trước khi train, tự chạy sanity check ở __main__.
"""

import re

import numpy as np

from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

from reasoning_env import ReasoningAction as A
from reasoning_strategies import (
    extract_answer,
    extract_code,
    majority_vote,
    parse_action,
    parse_answer_details,
    run_python_sandboxed,
    safe_calculate,
)

COT_SUFFIX = "\nWrite concise steps in plain text without markdown or LaTeX. End with exactly one line 'Answer: ' followed only by the final answer."
DIRECT_SUFFIX = "\nTrả lời trực tiếp, kết thúc bằng đúng 1 dòng 'Answer: ' rồi chỉ đáp án cuối (một số không đơn vị, một từ/tên, hoặc một biểu thức), không thêm câu chữ."
REACT_SYSTEM = (
    "Solve the problem with ReAct. Every response must contain exactly two lines: "
    "one Thought line and one Action line. The action must be calculate[...] or "
    "finish[...]. Put only a concrete arithmetic expression inside calculate and "
    "only the final answer inside finish. Never write an Observation; the system "
    "provides it after calculate."
)
PAL_SUFFIX = "\nViết 1 đoạn code Python giải bài này, gán kết quả cuối vào biến `result`. Chỉ trả code, trong 1 khối ```python```."

REACT_EXAMPLE = [
    {"role": "user", "content": "What is (12 + 8) * 3?"},
    {"role": "assistant", "content": "Thought: I should calculate the expression.\nAction: calculate[(12+8)*3]"},
    {"role": "user", "content": "Observation: 60"},
    {"role": "assistant", "content": "Thought: The calculation gives the final answer.\nAction: finish[60]"},
]


class QwenMLXBackend:
    """LLMBackend cho ReasoningEnv, dùng mlx-lm + Qwen3-8B chạy local trên Apple Silicon."""

    supported = frozenset({A.DIRECT, A.COT, A.SELF_CONSISTENCY, A.TOT, A.REACT, A.PAL})

    def __init__(self, repo: str = "mlx-community/Qwen3-8B-4bit", max_tokens: int = 512):
        self.model, self.tokenizer = load(repo)
        self.hidden_size = self.model.args.hidden_size
        self.max_tokens = max_tokens

    # ---- LLMBackend protocol ----

    def configure_answer_format(self, answer_type: str, decimal_separator: str = ".") -> None:
        """Use item format metadata only; the backend never receives gold labels."""
        if answer_type not in ("number", "text", "expression") or decimal_separator not in (".", ","):
            raise ValueError("Invalid research answer format")
        self.answer_format = {"answer_type": answer_type, "decimal_separator": decimal_separator}

    def _parse_answer(self, text: str) -> tuple[str, str, bool]:
        return parse_answer_details(text, **getattr(self, "answer_format", {}))

    def _extract_answer(self, text: str) -> str:
        return extract_answer(text, **getattr(self, "answer_format", {}))

    def _vote(self, answers: list[str], return_tie: bool = False):
        return majority_vote(answers, return_tie=return_tie, **getattr(self, "answer_format", {}))

    def embed(self, query: str) -> np.ndarray:
        import mlx.core as mx

        ids = mx.array(self.tokenizer.encode(query))[None]
        hidden = self.model.model(ids)  # (1, seq, hidden) - trước lm_head, đúng ý "dùng chính LLM"
        return np.array(mx.mean(hidden[0], axis=0))

    def run(self, strategy: A, query: str) -> tuple[str, float, int]:
        self.last_trace = {"strategy": strategy.name, "generations": [], "tools": []}
        if hasattr(self, "answer_format"):
            self.last_trace["answer_format"] = dict(self.answer_format)
        return {
            A.DIRECT: self._direct,
            A.COT: self._cot,
            A.SELF_CONSISTENCY: self._self_consistency,
            A.TOT: self._tot,
            A.REACT: self._react,
            A.PAL: self._pal,
        }[strategy](query)

    def _record_tool(self, event: dict) -> None:
        trace = getattr(self, "last_trace", None)
        if trace is not None:
            trace["tools"].append(event)

    # ---- strategies ----

    def _record_status(self, ans: str, raw_text: str | None = None) -> None:
        if hasattr(self, "last_trace") and self.last_trace:
            _, status, wordy = self._parse_answer(raw_text if raw_text is not None else f"Answer: {ans}")
            self.last_trace["parse_status"] = status
            self.last_trace["wordy"] = wordy

    def _direct(self, query: str) -> tuple[str, float, int]:
        text, conf, n_tok = self._chat([{"role": "user", "content": query + DIRECT_SUFFIX}], temp=0.0)
        ans, status, wordy = self._parse_answer(text)
        if hasattr(self, "last_trace") and self.last_trace:
            self.last_trace["parse_status"] = status
            self.last_trace["wordy"] = wordy
        return ans, conf, n_tok

    def _cot(self, query: str) -> tuple[str, float, int]:
        text, conf, n_tok = self._chat([{"role": "user", "content": query + COT_SUFFIX}], temp=0.0)
        ans, status, wordy = self._parse_answer(text)
        if hasattr(self, "last_trace") and self.last_trace:
            self.last_trace["parse_status"] = status
            self.last_trace["wordy"] = wordy
        return ans, conf, n_tok

    def _self_consistency(self, query: str, k: int = 5) -> tuple[str, float, int]:
        msgs = [{"role": "user", "content": query + COT_SUFFIX}]
        answers, total_tok = [], 0
        for _ in range(k):
            text, _, n_tok = self._chat(msgs, temp=0.7)
            answers.append(self._extract_answer(text))
            total_tok += n_tok
        vote, ratio, is_tie = self._vote(answers, return_tie=True)
        self._record_status(vote)
        if hasattr(self, "last_trace") and self.last_trace:
            self.last_trace["tie"] = is_tie
        return vote, ratio, total_tok

    def _tot(self, query: str, branches: int = 3) -> tuple[str, float, int]:
        msgs = [{"role": "user", "content": query + COT_SUFFIX}]
        candidates, total_tok = [], 0
        for _ in range(branches):
            text, _, n_tok = self._chat(msgs, temp=0.8)
            candidates.append(text)
            total_tok += n_tok
        listing = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(candidates))
        eval_prompt = (
            f"Câu hỏi: {query}\n\nCác lời giải ứng viên:\n{listing}\n\n"
            f"Chọn lời giải đúng nhất. Chỉ trả về một trong các dòng: "
            + ", ".join(f"Best: {index}" for index in range(branches))
            + "."
        )
        eval_text, eval_conf, eval_tok = self._chat([{"role": "user", "content": eval_prompt}], temp=0.0)
        total_tok += eval_tok
        answers = [self._extract_answer(candidate) for candidate in candidates]
        idx = extract_best_index(eval_text, branches)
        if idx is None:
            answer, _ = self._vote(answers)
            selection = "majority_fallback"
        else:
            answer = answers[idx]
            selection = "model_index"
        self._record_tool({
            "name": "candidate_selector",
            "candidate_answers": answers,
            "selector_output": eval_text,
            "selected_index": idx,
            "selection": selection,
        })
        self._record_status(answer)
        return answer, eval_conf, total_tok

    def _react(self, query: str, max_turns: int = 4) -> tuple[str, float, int]:
        msgs = [
            {"role": "system", "content": REACT_SYSTEM},
            *REACT_EXAMPLE,
            {"role": "user", "content": query},
        ]
        total_tok, last_conf = 0, 0.0
        for _ in range(max_turns):
            text, conf, n_tok = self._chat(msgs, temp=0.0, max_tokens=min(200, self.max_tokens))
            total_tok, last_conf = total_tok + n_tok, conf
            msgs.append({"role": "assistant", "content": text})
            parsed = parse_action(text)
            if parsed is None:
                break
            act, arg = parsed
            if act == "finish":
                self._record_status(arg, f"Answer: {arg}")
                answer = self._extract_answer(f"Answer: {arg}") if hasattr(self, "answer_format") else arg
                return answer, last_conf, total_tok
            if act == "calculate":
                observation = safe_calculate(arg)
                self._record_tool({
                    "name": "calculate", "input": arg, "output": observation,
                })
                msgs.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                break
        ans = self._extract_answer(msgs[-1]["content"])
        self._record_status(ans, msgs[-1]["content"])
        return ans, last_conf * 0.7, total_tok

    def _pal(self, query: str) -> tuple[str, float, int]:
        text, conf, n_tok = self._chat([{"role": "user", "content": query + PAL_SUFFIX}], temp=0.0)
        code = extract_code(text)
        ok, result = run_python_sandboxed(code)
        self._record_tool({
            "name": "python", "input": code, "ok": ok, "output": result,
        })
        answer = self._extract_answer(result) if ok else self._extract_answer(text)
        self._record_status(answer, f"Answer: {result}" if ok else text)
        return answer, (conf if ok else conf * 0.3), n_tok

    # ---- shared generation ----

    def _chat(self, messages: list[dict], temp: float = 0.0, max_tokens: int | None = None) -> tuple[str, float, int]:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            enable_thinking=False,
            add_generation_prompt=True,
        )
        p_tok = len(prompt) if isinstance(prompt, list) else len(self.tokenizer.encode(prompt))
        sampler = make_sampler(temp=temp)
        text, n_tok = "", 0
        finish_reason = None
        logps, margins, entropies = [], [], []
        for r in stream_generate(self.model, self.tokenizer, prompt, max_tokens=max_tokens or self.max_tokens, sampler=sampler):
            text += r.text
            n_tok = r.generation_tokens
            if getattr(r, "finish_reason", None) is not None:
                finish_reason = r.finish_reason
            if getattr(r, "logprobs", None) is not None:
                lp_arr = np.asarray(r.logprobs, dtype=np.float32)
                if len(lp_arr) > r.token:
                    logps.append(float(lp_arr[r.token]))
                m, h = compute_token_uncertainty(lp_arr)
                margins.append(m)
                entropies.append(h)
            # Only stop when Answer: is followed by non-whitespace content on the same line
            m_stop = re.search(r"(?:^|\n)Answer:[ \t]*\S[^\r\n]*\r?\n", text)
            if m_stop:
                text = text[:m_stop.end()]
                finish_reason = "stop_answer"
                break

        p_seq = float(np.clip(np.exp(np.mean(logps)), 0.0, 1.0)) if logps else 0.0
        mean_margin = float(np.mean(margins)) if margins else 0.0
        mean_entropy = float(np.mean(entropies)) if entropies else 1.0

        # Sigmoidal scaling for margin gap
        margin_factor = float(1.0 / (1.0 + np.exp(-1.0 * (mean_margin - 1.0))))
        conf = float(np.clip(0.5 * p_seq + 0.3 * margin_factor + 0.2 * (1.0 - mean_entropy), 0.0, 1.0)) if logps else 0.0

        self.last_signals = {
            "p_seq": p_seq,
            "mean_margin": mean_margin,
            "mean_entropy": mean_entropy,
            "confidence": conf,
        }
        if hasattr(self, "last_trace"):
            self.last_trace["generations"].append({
                "messages": [dict(message) for message in messages],
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temp,
                "enable_thinking": False,
                "prompt_tokens": p_tok,
                "output": text,
                "tokens": n_tok,
                "finish_reason": finish_reason,
                "signals": dict(self.last_signals),
            })
        return text, conf, n_tok


def compute_token_uncertainty(logprobs: np.ndarray, top_k: int = 10) -> tuple[float, float]:
    """Computes top-2 margin and normalized top-k Shannon entropy.
    margin: logp_(1) - logp_(2) >= 0. Large margin means decisive continuation.
    entropy: normalized Shannon entropy in [0, 1]. Near 0 means peaked certainty.
    """
    if len(logprobs) < 2:
        return 0.0, 0.0

    # 1. Top-2 margin
    top2 = np.partition(logprobs, -2)[-2:]
    top2.sort()
    margin = float(max(0.0, top2[1] - top2[0]))

    # 2. Top-k normalized entropy
    k = min(top_k, len(logprobs))
    topk = np.partition(logprobs, -k)[-k:]
    max_lp = np.max(topk)
    probs = np.exp(topk - max_lp)
    probs /= (np.sum(probs) + 1e-12)
    ent = -float(np.sum(probs * np.log(probs + 1e-12)))
    max_ent = np.log(k) if k > 1 else 1.0
    norm_ent = float(np.clip(ent / max_ent, 0.0, 1.0))
    return margin, norm_ent


def extract_best_index(text: str, branches: int) -> int | None:
    import re

    match = re.search(r"\bBest\s*:\s*\[?([0-9]+)\]?", text, re.IGNORECASE)
    if match is None:
        return None
    index = int(match.group(1))
    return index if 0 <= index < branches else None


if __name__ == "__main__":
    # Sanity check thật - chỉ chạy được trên Mac (cần mạng HF + Apple Silicon). Sandbox build code
    # này không có 2 điều kiện đó nên KHÔNG tự chạy được ở đây.
    backend = QwenMLXBackend()
    print("hidden_size:", backend.hidden_size)
    for strat in [A.COT, A.PAL, A.REACT]:
        ans, conf, tok = backend.run(strat, "Nếu 3 quả táo giá 45000 đồng, 7 quả táo giá bao nhiêu?")
        print(strat.name, "->", ans, f"(conf={conf:.2f}, tokens={tok})")
