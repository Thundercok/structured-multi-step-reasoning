"""
meta_controller.actions — Discrete Action Space for Dynamic Reasoning Meta-Controller.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Dict


class ReasoningAction(IntEnum):
    """
    Action space:
    0-4: Direct reasoning strategies
    5: ESCALATE (boost search depth / switch to heavier strategy if confidence is low)
    6: STOP (terminate episode and commit to current best answer)
    """
    COT = 0                # Chain of Thought (Linear step-by-step)
    SELF_CONSISTENCY = 1   # Self-Consistency (k=3 paths + Majority Vote)
    TOT = 2                # Tree of Thoughts (Branching + Node Evaluation)
    REACT = 3              # ReAct (Thought -> Tool/Search Action -> Observation)
    PAL = 4                # Program-Aided Language (Python Code Execution)
    ESCALATE = 5           # Escalate complexity / budget
    STOP = 6               # Finalize and return answer


# Relative compute/token cost multiplier for each action
ACTION_BASE_COSTS: Dict[ReasoningAction, float] = {
    ReasoningAction.COT: 1.0,
    ReasoningAction.SELF_CONSISTENCY: 3.0,
    ReasoningAction.TOT: 4.5,
    ReasoningAction.REACT: 2.5,
    ReasoningAction.PAL: 1.8,
    ReasoningAction.ESCALATE: 0.3,
    ReasoningAction.STOP: 0.0,
}

ACTION_NAMES: Dict[ReasoningAction, str] = {
    ReasoningAction.COT: "Chain-of-Thought (CoT)",
    ReasoningAction.SELF_CONSISTENCY: "Self-Consistency (k=3)",
    ReasoningAction.TOT: "Tree-of-Thoughts (ToT)",
    ReasoningAction.REACT: "ReAct (Tool-Augmented)",
    ReasoningAction.PAL: "Program-Aided Language (PAL)",
    ReasoningAction.ESCALATE: "Escalate Strategy",
    ReasoningAction.STOP: "Stop & Return",
}
