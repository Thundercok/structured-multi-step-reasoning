"""
meta_controller.state — State Representation for the Reasoning Meta-Controller.
Combines query embedding, syntactic/semantic complexity signals, and internal confidence states.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from meta_controller.actions import ReasoningAction


@dataclass
class ReasoningState:
    query: str
    query_embedding: np.ndarray  # Shape: (d_emb,)
    step_index: int = 0
    max_steps: int = 5
    prev_action: Optional[ReasoningAction] = None
    confidence: float = 0.0      # Scale: [0.0, 1.0]
    entropy: float = 1.0         # Logit entropy
    accumulated_cost: float = 0.0
    candidate_answer: str = ""

    def to_feature_vector(self) -> np.ndarray:
        """
        Flattens state into a normalized 1D numpy vector for RL policy input.
        Vector layout:
        [0 : d_emb]                      -> Query embedding vector
        [d_emb : d_emb + 4]              -> Complexity features (length, digits, math ops, query type)
        [d_emb + 4 : d_emb + 5]          -> Normalized step index (step / max_steps)
        [d_emb + 5 : d_emb + 12]         -> One-hot previous action (7 dims)
        [d_emb + 12 : d_emb + 15]        -> Confidence, Entropy, Accumulated cost
        """
        # 1. Query complexity features
        q_len_norm = min(len(self.query.split()) / 100.0, 1.0)
        digits_count = len(re.findall(r"\d+", self.query))
        digits_norm = min(digits_count / 10.0, 1.0)
        has_math_ops = 1.0 if any(op in self.query for op in ["+", "-", "*", "/", "=", "%", "^", "√"]) else 0.0
        is_comparison = 1.0 if any(w in self.query.lower() for w in ["so sánh", "khác nhau", "compare", "versus", "vs", "hay là"]) else 0.0

        complexity = np.array([q_len_norm, digits_norm, has_math_ops, is_comparison], dtype=np.float32)

        # 2. Step index normalized
        step_norm = np.array([self.step_index / max(1, self.max_steps)], dtype=np.float32)

        # 3. One-hot encoding of previous action (7 dims)
        prev_act_one_hot = np.zeros(len(ReasoningAction), dtype=np.float32)
        if self.prev_action is not None:
            prev_act_one_hot[int(self.prev_action)] = 1.0

        # 4. Internal uncertainty & cost metrics
        metrics = np.array([
            float(np.clip(self.confidence, 0.0, 1.0)),
            float(np.clip(self.entropy, 0.0, 5.0) / 5.0),
            float(min(self.accumulated_cost / 15.0, 1.0)),
        ], dtype=np.float32)

        return np.concatenate([
            self.query_embedding.astype(np.float32),
            complexity,
            step_norm,
            prev_act_one_hot,
            metrics,
        ])
