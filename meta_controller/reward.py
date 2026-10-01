"""
meta_controller.reward — Multi-Objective Reward Function for Accuracy vs Cost Tradeoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from meta_controller.actions import ReasoningAction


@dataclass
class RewardBreakdown:
    total_reward: float
    accuracy_reward: float
    cost_penalty: float
    shaping_bonus: float


class ReasoningRewardCalculator:
    """
    Computes dense shaped rewards during intermediate reasoning steps,
    and terminal accuracy rewards minus accumulated compute cost upon STOP.
    """

    def __init__(self, cost_penalty_lambda: float = 0.01, confidence_shaping_beta: float = 0.5) -> None:
        self.cost_lambda = cost_penalty_lambda
        self.shaping_beta = confidence_shaping_beta

    def compute_reward(
        self,
        action: ReasoningAction,
        confidence_before: Optional[float],
        confidence_after: Optional[float],
        step_cost: float,
        is_correct: Optional[bool] = None,
        total_cost: Optional[float] = None,
    ) -> RewardBreakdown:
        accuracy_reward = 0.0
        shaping_bonus = 0.0

        if action == ReasoningAction.STOP:
            # Terminal outcome
            accuracy_reward = 1.0 if is_correct else -1.0
            cost_penalty = -self.cost_lambda * (total_cost if total_cost is not None else step_cost)
            total = accuracy_reward + cost_penalty
            return RewardBreakdown(
                total_reward=total,
                accuracy_reward=accuracy_reward,
                cost_penalty=cost_penalty,
                shaping_bonus=0.0,
            )

        # Intermediate step: penalize compute consumption
        cost_penalty = -self.cost_lambda * step_cost

        # Dense potential-based shaping reward: encourage actions that increase internal certainty
        if confidence_before is not None and confidence_after is not None:
            delta_conf = confidence_after - confidence_before
            shaping_bonus = self.shaping_beta * delta_conf

        total = cost_penalty + shaping_bonus
        return RewardBreakdown(
            total_reward=total,
            accuracy_reward=0.0,
            cost_penalty=cost_penalty,
            shaping_bonus=shaping_bonus,
        )
