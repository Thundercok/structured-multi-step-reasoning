"""
meta_controller.environment — Gymnasium-Compatible Environment for Reasoning Meta-Controller.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from meta_controller.actions import ReasoningAction
from meta_controller.backend import BaseReasoningBackend, MockReasoningBackend
from meta_controller.reward import ReasoningRewardCalculator, RewardBreakdown
from meta_controller.state import ReasoningState
from meta_controller.strategies import StrategyExecutionResult, StrategyExecutor

logger = logging.getLogger(__name__)


class ReasoningEnv:
    """
    RL Environment where an agent (Meta-Controller) observes query features
    and internal confidence signals, then decides which reasoning strategy to execute
    or when to stop and return the answer.
    """

    def __init__(
        self,
        dataset: List[Dict[str, Any]],
        backend: Optional[BaseReasoningBackend] = None,
        max_steps: int = 5,
        cost_lambda: float = 0.01,
        shaping_beta: float = 0.5,
    ) -> None:
        self.dataset = dataset
        self.backend = backend or MockReasoningBackend()
        self.executor = StrategyExecutor(self.backend)
        self.reward_calc = ReasoningRewardCalculator(cost_lambda, shaping_beta)
        self.max_steps = max_steps

        self.current_idx = 0
        self.current_sample: Optional[Dict[str, Any]] = None
        self.state: Optional[ReasoningState] = None
        self.history: List[ReasoningAction] = []
        self.total_cost = 0.0

    @property
    def action_space_n(self) -> int:
        return len(ReasoningAction)

    @property
    def observation_dim(self) -> int:
        dummy_state = ReasoningState(
            query="test",
            query_embedding=np.zeros(getattr(self.backend, "embedding_dim", 64), dtype=np.float32),
            max_steps=self.max_steps,
        )
        return len(dummy_state.to_feature_vector())

    def reset(self, sample_idx: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment to a new query."""
        if sample_idx is not None:
            self.current_idx = sample_idx % len(self.dataset)
        else:
            self.current_idx = np.random.randint(0, len(self.dataset))

        self.current_sample = self.dataset[self.current_idx]
        query = self.current_sample["query"]
        emb = self.backend.embed_query(query)

        self.state = ReasoningState(
            query=query,
            query_embedding=emb,
            step_index=0,
            max_steps=self.max_steps,
            prev_action=None,
            confidence=0.0,
            entropy=1.0,
            accumulated_cost=0.0,
            candidate_answer="",
        )
        self.history = []
        self.total_cost = 0.0

        obs = self.state.to_feature_vector()
        info = {
            "query": query,
            "ground_truth": self.current_sample.get("ground_truth", ""),
            "domain": self.current_sample.get("domain", "general"),
        }
        return obs, info

    def step(self, action: ReasoningAction) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one action in the reasoning loop.
        Returns: (observation, reward, terminated, truncated, info)
        """
        if self.state is None or self.current_sample is None:
            raise RuntimeError("Environment must be reset() before calling step().")

        self.history.append(action)
        conf_before = self.state.confidence

        # Case 1: STOP action
        if action == ReasoningAction.STOP:
            is_correct = self._evaluate_accuracy(self.state.candidate_answer, self.current_sample.get("ground_truth", ""))
            reward_breakdown: RewardBreakdown = self.reward_calc.compute_reward(
                action=ReasoningAction.STOP,
                confidence_before=conf_before,
                confidence_after=conf_before,
                step_cost=0.0,
                is_correct=is_correct,
                total_cost=self.total_cost,
            )
            obs = self.state.to_feature_vector()
            info = {
                "terminated_reason": "STOP_ACTION",
                "is_correct": is_correct,
                "final_answer": self.state.candidate_answer,
                "total_cost": self.total_cost,
                "steps": self.state.step_index,
                "history": [a.name for a in self.history],
                "reward_breakdown": reward_breakdown,
            }
            return obs, reward_breakdown.total_reward, True, False, info

        # Case 2: Reasoning Strategy Action (CoT, SC, ToT, ReAct, PAL, Escalate)
        exec_res: StrategyExecutionResult = self.executor.execute(
            action=action,
            query=self.state.query,
            context=self.state.candidate_answer,
        )

        step_cost = exec_res.compute_cost
        self.total_cost += step_cost

        # Update state with internal signals
        self.state.step_index += 1
        self.state.prev_action = action
        self.state.candidate_answer = exec_res.answer
        self.state.confidence = exec_res.confidence
        self.state.entropy = exec_res.entropy
        self.state.accumulated_cost = self.total_cost

        conf_after = self.state.confidence

        # Check step limit
        truncated = self.state.step_index >= self.max_steps
        terminated = False

        if truncated:
            # Reached max steps without explicit stop -> evaluate current candidate
            is_correct = self._evaluate_accuracy(self.state.candidate_answer, self.current_sample.get("ground_truth", ""))
            reward_breakdown = self.reward_calc.compute_reward(
                action=ReasoningAction.STOP,
                confidence_before=conf_before,
                confidence_after=conf_after,
                step_cost=step_cost,
                is_correct=is_correct,
                total_cost=self.total_cost,
            )
            info = {
                "terminated_reason": "MAX_STEPS_TRUNCATED",
                "is_correct": is_correct,
                "final_answer": self.state.candidate_answer,
                "total_cost": self.total_cost,
                "steps": self.state.step_index,
                "history": [a.name for a in self.history],
                "reward_breakdown": reward_breakdown,
            }
            return self.state.to_feature_vector(), reward_breakdown.total_reward, True, True, info

        # Intermediate step reward
        reward_breakdown = self.reward_calc.compute_reward(
            action=action,
            confidence_before=conf_before,
            confidence_after=conf_after,
            step_cost=step_cost,
        )

        obs = self.state.to_feature_vector()
        info = {
            "step_cost": step_cost,
            "confidence": self.state.confidence,
            "entropy": self.state.entropy,
            "reward_breakdown": reward_breakdown,
        }
        return obs, reward_breakdown.total_reward, terminated, truncated, info

    def _evaluate_accuracy(self, candidate: str, ground_truth: str) -> bool:
        if not ground_truth:
            return True
        c_clean = candidate.strip().lower()
        g_clean = ground_truth.strip().lower()
        return g_clean in c_clean or c_clean in g_clean
