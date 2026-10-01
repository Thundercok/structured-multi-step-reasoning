"""
meta_controller.backend — Open-Weight Model Backend for Mac Apple Silicon & Linux.
Supports PyTorch MPS (Metal Performance Shaders), HuggingFace Transformers,
and Mock simulation for rapid test cycles.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    text: str
    confidence: float          # [0.0, 1.0] derived from max softmax / sequence prob
    entropy: float             # Logit entropy measuring uncertainty
    token_count: int
    prompt_tokens: int
    hidden_embedding: np.ndarray  # Last-layer mean-pooled vector


class BaseReasoningBackend(ABC):
    """Abstract base class for LLM backends capable of exposing internal signals."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> GenerationResult:
        """Generate text and compute internal confidence & entropy signals."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """Extract dense vector representation from the model's hidden states."""
        pass


class MockReasoningBackend(BaseReasoningBackend):
    """
    High-speed deterministic mock backend for instant unit testing,
    RL policy validation, and debugging without GPU requirements.
    """

    def __init__(self, embedding_dim: int = 64) -> None:
        self.embedding_dim = embedding_dim
        self.call_history: List[Dict[str, Any]] = []

    def embed_query(self, query: str) -> np.ndarray:
        # Deterministic pseudo-embedding based on string hash
        np.random.seed(abs(hash(query)) % (2**31 - 1))
        vec = np.random.randn(self.embedding_dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> GenerationResult:
        self.call_history.append({"prompt": prompt, "temp": temperature, "max_tokens": max_tokens})

        # Synthetic response and uncertainty signals
        p_lower = prompt.lower()
        if "calculate" in p_lower or "cộng" in p_lower or "tính" in p_lower or "+" in p_lower:
            text = "Kết quả tính toán: 42 (Code execution verified)"
            conf = 0.95
            ent = 0.15
        elif "xung đột" in p_lower or "so sánh" in p_lower:
            text = "Phân tích đa chiều: Các nhánh cho thấy sự tương quan có điều kiện."
            conf = 0.72
            ent = 0.85
        else:
            text = f"Phản hồi phân tích cho câu hỏi: '{prompt[:40]}...'"
            conf = 0.82
            ent = 0.45

        emb = self.embed_query(prompt)
        return GenerationResult(
            text=text,
            confidence=conf,
            entropy=ent,
            token_count=len(text.split()),
            prompt_tokens=len(prompt.split()),
            hidden_embedding=emb,
        )


class PyTorchMPSBackend(BaseReasoningBackend):
    """
    Apple Silicon Metal Performance Shaders (MPS) / CUDA native backend
    using HuggingFace Transformers for Qwen models. Exposes hidden states and logits.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
        device: Optional[str] = None,
        embedding_dim: int = 1536,
    ) -> None:
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

        logger.info(f"Initializing PyTorchMPSBackend with model '{model_name}' on device '{self.device}'...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        dtype = torch.float16 if self.device in ("mps", "cuda") else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=dtype,
            output_hidden_states=True,
        ).to(self.device)
        self.model.eval()
        self.embedding_dim = embedding_dim

    def embed_query(self, query: str) -> np.ndarray:
        import torch
        inputs = self.tokenizer(query, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)
            # Last hidden layer mean-pooling
            last_hidden = outputs.hidden_states[-1]  # (1, seq_len, hidden_dim)
            pooled = last_hidden.mean(dim=1).squeeze(0).cpu().numpy()
            norm = np.linalg.norm(pooled)
            return pooled / (norm + 1e-9)

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> GenerationResult:
        import torch
        import torch.nn.functional as F

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        prompt_len = inputs.input_ids.shape[1]

        with torch.no_grad():
            gen_outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if temperature > 0 else 1.0,
                do_sample=temperature > 0,
                return_dict_in_generate=True,
                output_scores=True,
                output_hidden_states=True,
            )

        gen_tokens = gen_outputs.sequences[0][prompt_len:]
        out_text = self.tokenizer.decode(gen_tokens, skip_special_tokens=True)

        # 1. Compute entropy and confidence from token logit scores
        scores = gen_outputs.scores  # Tuple of tensors of shape (1, vocab_size)
        entropies = []
        max_probs = []

        for step_logits in scores:
            probs = F.softmax(step_logits, dim=-1)
            p_max = float(probs.max().cpu())
            max_probs.append(p_max)
            # Shannon entropy: -sum(p * log(p))
            log_probs = F.log_softmax(step_logits, dim=-1)
            step_entropy = float(-(probs * log_probs).sum().cpu())
            entropies.append(step_entropy)

        avg_confidence = float(np.mean(max_probs)) if max_probs else 0.5
        avg_entropy = float(np.mean(entropies)) if entropies else 1.0

        # Query embedding
        emb = self.embed_query(prompt)

        return GenerationResult(
            text=out_text,
            confidence=avg_confidence,
            entropy=avg_entropy,
            token_count=len(gen_tokens),
            prompt_tokens=prompt_len,
            hidden_embedding=emb,
        )
