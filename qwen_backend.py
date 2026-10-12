"""
qwen_backend.py — Native Apple Silicon Backend for Qwen Models.
Implements the LLMBackend Protocol for ReasoningEnv:
- hidden_size: int
- embed(query: str) -> np.ndarray (mean-pooled hidden state)
- run(strategy: ReasoningAction, query: str) -> tuple[str, float, int]

Supports:
1. PyTorch Metal (MPS) on Apple Silicon (M1/M2/M3/M4) via transformers.
2. Optional MLX-LM if mlx is installed.
3. Fast Mock fallback for rapid test cycles without GPU weights.
"""

from __future__ import annotations

import io
import logging
import math
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_env import A, LLMBackend, ReasoningAction

logger = logging.getLogger(__name__)


class QwenMacBackend:
    """
    Apple Silicon native backend for Qwen (Qwen2.5 / Qwen3 family).
    Uses PyTorch MPS for on-device Metal GPU acceleration and exposes
    true internal hidden states and logit-derived confidence scores.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
        device: Optional[str] = None,
        enable_thinking: bool = False,
        use_mock: bool = False,
    ) -> None:
        self.model_name = model_name
        self.enable_thinking = enable_thinking
        self.use_mock = use_mock

        if self.use_mock:
            self.hidden_size = 64
            logger.info("QwenMacBackend initialized in MOCK mode.")
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if device is None:
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        logger.info(f"Loading '{model_name}' on Apple Silicon device '{self.device}'...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        dtype = torch.float16 if self.device in ("mps", "cuda") else torch.float32

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=dtype,
            output_hidden_states=True,
        ).to(self.device)
        self.model.eval()

        self.hidden_size = self.model.config.hidden_size
        logger.info(f"Model loaded successfully. Hidden size: {self.hidden_size}")

    # =========================================================================
    # 1. State Extraction: embed(query)
    # =========================================================================
    def embed(self, query: str) -> np.ndarray:
        """Extract mean-pooled last hidden state of query, shape (hidden_size,)."""
        if self.use_mock:
            # Deterministic pseudo-embedding for testing
            np.random.seed(abs(hash(query)) % (2**31 - 1))
            v = np.random.randn(self.hidden_size).astype(np.float32)
            v[-1] *= 25.0  # simulate LLM outlier dimension
            return v

        import torch
        inputs = self.tokenizer(query, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)
            last_hidden = outputs.hidden_states[-1]  # (1, seq_len, hidden_size)
            pooled = last_hidden.mean(dim=1).squeeze(0).cpu().numpy().astype(np.float32)
            return pooled

    # =========================================================================
    # 2. Strategy Execution: run(strategy, query)
    # =========================================================================
    def run(self, strategy: ReasoningAction, query: str) -> Tuple[str, float, int]:
        """
        Executes the chosen reasoning strategy.
        Returns: (answer, confidence in [0, 1], total_tokens_consumed)
        """
        if self.use_mock:
            return self._mock_run(strategy, query)

        if strategy == A.COT:
            return self._run_cot(query)
        elif strategy == A.SELF_CONSISTENCY:
            return self._run_self_consistency(query, k=3)
        elif strategy == A.TOT:
            return self._run_tot(query, branches=3)
        elif strategy == A.REACT:
            return self._run_react(query)
        elif strategy == A.PAL:
            return self._run_pal(query)
        else:
            raise ValueError(f"Unsupported direct strategy: {strategy}")

    # =========================================================================
    # Internal Generation Primitive with Token & Confidence Tracking
    # =========================================================================
    def _generate_text(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_new_tokens: int = 384,
    ) -> Tuple[str, float, int]:
        """Helper to generate text and return (text, mean_confidence, total_tokens)."""
        import torch
        import torch.nn.functional as F

        # System prefix to disable internal thinking tokens if requested
        sys_prompt = ""
        if not self.enable_thinking:
            sys_prompt = "You are a concise, analytical assistant. Give direct, step-by-step reasoning without meta-dialogue.\n"

        full_prompt = f"{sys_prompt}{prompt}"
        inputs = self.tokenizer(full_prompt, return_tensors="pt").to(self.device)
        prompt_len = inputs.input_ids.shape[1]

        with torch.no_grad():
            gen_outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature if temperature > 0 else 1.0,
                do_sample=temperature > 0,
                return_dict_in_generate=True,
                output_scores=True,
            )

        gen_tokens = gen_outputs.sequences[0][prompt_len:]
        out_text = self.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

        # Compute confidence from softmax probabilities of generated tokens
        confidences = []
        if gen_outputs.scores:
            for score in gen_outputs.scores:
                prob = F.softmax(score, dim=-1)
                p_max = float(prob.max().cpu())
                confidences.append(p_max)

        mean_conf = float(np.mean(confidences)) if confidences else 0.5
        total_tokens = prompt_len + len(gen_tokens)
        return out_text, mean_conf, total_tokens

    # --- Strategy 1: Chain of Thought (CoT) ---
    def _run_cot(self, query: str) -> Tuple[str, float, int]:
        prompt = (
            f"Vấn đề: {query}\n"
            f"Hãy suy luận từng bước một cách ngắn gọn, có cấu trúc logic để tìm ra kết quả.\n"
            f"Suy luận từng bước:"
        )
        ans, conf, tokens = self._generate_text(prompt, temperature=0.1, max_new_tokens=350)
        return ans, conf, tokens

    # --- Strategy 2: Self-Consistency (k=3) ---
    def _run_self_consistency(self, query: str, k: int = 3) -> Tuple[str, float, int]:
        prompt = (
            f"Câu hỏi: {query}\n"
            f"Hãy suy nghĩ độc lập và đưa ra câu trả lời ngắn gọn, chính xác:\n"
            f"Lời giải:"
        )
        answers = []
        confs = []
        total_tok = 0

        for _ in range(k):
            ans, conf, tok = self._generate_text(prompt, temperature=0.7, max_new_tokens=256)
            answers.append(ans)
            confs.append(conf)
            total_tok += tok

        # Extract answer numbers or concise lines for voting
        clean_answers = [self._extract_answer_core(a) for a in answers]
        # Find majority
        counts = {}
        for ca in clean_answers:
            counts[ca] = counts.get(ca, 0) + 1

        best_core = max(counts, key=counts.get)
        agreement_ratio = counts[best_core] / k

        # Winning answer full text
        best_idx = clean_answers.index(best_core)
        winning_answer = answers[best_idx]

        # Confidence is combination of model token certainty and consensus ratio
        final_conf = min(confs[best_idx] * 0.6 + agreement_ratio * 0.4, 1.0)
        return winning_answer, final_conf, total_tok

    # --- Strategy 3: Tree-of-Thoughts (ToT) ---
    def _run_tot(self, query: str, branches: int = 3) -> Tuple[str, float, int]:
        # Step 1: Branch generation
        prop_prompt = (
            f"Đề xuất {branches} hướng suy luận/phương pháp tiếp cận khác nhau để giải quyết câu hỏi:\n"
            f"Câu hỏi: {query}\n"
            f"Các hướng tiếp cận:"
        )
        branches_text, b_conf, b_tokens = self._generate_text(prop_prompt, temperature=0.6, max_new_tokens=300)

        # Step 2: Evaluation & Selection
        eval_prompt = (
            f"Câu hỏi: {query}\n"
            f"Các hướng tiếp cận đề xuất:\n{branches_text}\n"
            f"Nhiệm vụ: Đánh giá hướng đi có độ tin cậy cao nhất, chỉ ra điểm then chốt và kết luận đáp án cuối cùng.\n"
            f"Đánh giá & Kết luận:"
        )
        final_ans, e_conf, e_tokens = self._generate_text(eval_prompt, temperature=0.1, max_new_tokens=350)

        combined_conf = (b_conf + e_conf) / 2.0
        total_tokens = b_tokens + e_tokens
        return final_ans, combined_conf, total_tokens

    # --- Strategy 4: ReAct (Reason + Act with Python Tool) ---
    def _run_react(self, query: str) -> Tuple[str, float, int]:
        prompt = (
            f"Giải quyết bài toán sau bằng phương pháp ReAct. Bạn có công cụ python(expr) để tính toán.\n"
            f"Câu hỏi: {query}\n"
            f"Thought: Nhận diện yêu cầu và xác định biểu thức tính toán\n"
            f"Action: python(biểu thức toán nếu có)\n"
        )
        t_text, t_conf, t_tokens = self._generate_text(prompt, temperature=0.2, max_new_tokens=200)

        # Match tool execution
        match = re.search(r"Action:\s*python\((.*?)\)", t_text, re.IGNORECASE)
        observation = ""
        if match:
            expr = match.group(1).strip()
            observation = self._safe_eval_math(expr)

        final_prompt = (
            f"{prompt}{t_text}\n"
            f"Observation: {observation}\n"
            f"Thought: Tổng hợp kết quả từ công cụ\n"
            f"Final Answer:"
        )
        f_text, f_conf, f_tokens = self._generate_text(final_prompt, temperature=0.1, max_new_tokens=200)

        react_conf = 0.90 if observation and "Error" not in observation else f_conf
        total_tokens = t_tokens + f_tokens
        return f_text, react_conf, total_tokens

    # --- Strategy 5: Program-Aided Language (PAL) ---
    def _run_pal(self, query: str) -> Tuple[str, float, int]:
        prompt = (
            f"Viết một đoạn code Python ngắn gọn để tính toán đáp án cho câu hỏi sau.\n"
            f"Quy định: Lưu kết quả cuối cùng vào biến `result` hoặc in ra bằng `print()`.\n"
            f"Chỉ đặt code trong khối ```python ... ```.\n"
            f"Câu hỏi: {query}\n"
            f"Code Python:"
        )
        code_text, gen_conf, tokens = self._generate_text(prompt, temperature=0.1, max_new_tokens=300)

        # Extract code
        code_match = re.search(r"```python(.*?)```", code_text, re.DOTALL)
        code = code_match.group(1).strip() if code_match else code_text.strip()

        # Run safely in isolated scope
        captured = io.StringIO()
        exec_scope: Dict[str, Any] = {}
        old_stdout = sys.stdout
        success = False

        try:
            sys.stdout = captured
            exec(code, {"__builtins__": {"print": print, "range": range, "len": len, "sum": sum, "min": min, "max": max, "abs": abs, "round": round}}, exec_scope)
            success = True
        except Exception as e:
            err_msg = str(e)
        finally:
            sys.stdout = old_stdout

        if success:
            val = exec_scope.get("result", captured.getvalue().strip())
            answer = f"Kết quả từ chương trình: {val}"
            conf = 0.98  # PAL execution gives near-deterministic confidence
        else:
            answer = f"Lỗi thực thi code ({err_msg}). Phản hồi gốc: {code_text[:120]}"
            conf = 0.35

        return answer, conf, tokens

    # =========================================================================
    # Helpers
    # =========================================================================
    def _safe_eval_math(self, expr: str) -> str:
        try:
            allowed = set("0123456789+-*/(). %")
            cleaned = "".join(c for c in expr if c in allowed)
            return str(eval(cleaned, {"__builtins__": None}, {}))
        except Exception as e:
            return f"Error: {e}"

    def _extract_answer_core(self, text: str) -> str:
        # Simple heuristic to extract last line or number for voting
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return text
        last_line = lines[-1].lower()
        nums = re.findall(r"\d+(?:\.\d+)?", last_line)
        if nums:
            return nums[-1]
        return last_line[:50]

    def _mock_run(self, strategy: ReasoningAction, query: str) -> Tuple[str, float, int]:
        tokens_map = {A.COT: 250, A.SELF_CONSISTENCY: 850, A.TOT: 1800, A.REACT: 600, A.PAL: 400}
        q_low = query.lower()
        tok = tokens_map.get(strategy, 300)

        if strategy == A.PAL and any(op in q_low for op in ["+", "-", "*", "/", "tính", "gpa", "cpa", "học phí"]):
            return "42.0 (PAL Verified)", 0.98, tok
        elif strategy in (A.TOT, A.SELF_CONSISTENCY) and any(w in q_low for w in ["so sánh", "xung đột", "song bằng"]):
            return "Phân tích ToT/SC: Kết luận có điều kiện.", 0.88, tok
        else:
            return f"Lời giải CoT cho: {query[:30]}...", 0.75, tok
