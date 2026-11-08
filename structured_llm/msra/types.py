"""Type definitions and data structures for Metacognitive Structured Reasoning Agent (MSRA)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapabilityTag(str, Enum):
    DECOMPOSE = "CAP:DECOMPOSE"
    SYMBOLIC_CALC = "CAP:SYMBOLIC_CALC"
    DOMAIN_FACT = "CAP:DOMAIN_FACT"
    DEEP_DEDUCTION = "CAP:DEEP_DEDUCTION"
    SANITY_CHECK = "CAP:SANITY_CHECK"


class Decision(str, Enum):
    SOLVE_LOCAL = "SOLVE_LOCAL"
    ASK_HELP = "ASK_HELP"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    COMMIT = "COMMIT"
    REJECT = "REJECT"


# Standard normalized costs for each capability helper
CAPABILITY_COSTS: Dict[CapabilityTag, float] = {
    CapabilityTag.DECOMPOSE: 0.0,
    CapabilityTag.SYMBOLIC_CALC: 0.1,
    CapabilityTag.DOMAIN_FACT: 0.2,
    CapabilityTag.DEEP_DEDUCTION: 1.0,
    CapabilityTag.SANITY_CHECK: 0.05,
}


@dataclass
class ReasoningNode:
    """An encapsulated reasoning unit v_t = <g_t, tau_t, D_t, y_t, sigma_t>."""
    step_id: int
    subgoal: str
    capability_tag: CapabilityTag
    decision: Decision
    deps: Dict[str, Any] = field(default_factory=dict)
    query_payload: Optional[str] = None
    execution_result: str = ""
    verification_status: VerificationStatus = VerificationStatus.PENDING
    critique: str = ""
    output_var: Dict[str, Any] = field(default_factory=dict)
    helper_source: Optional[str] = None
    cost: float = 0.0


@dataclass
class PackagedQuery:
    """Isolated query payload q_t = Pack(g_t, D_t) with O(1) context complexity."""
    subgoal: str
    dependencies: Dict[str, Any]
    target_capability: CapabilityTag
    raw_query: str


@dataclass
class TraceValidationResult:
    """Result of structural and semantic validation of a reasoning DAG."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    nodes: List[ReasoningNode] = field(default_factory=list)


@dataclass
class PreferencePair:
    """A contrastive preference pair for SimPO / DPO alignment."""
    prompt: str
    chosen: str
    rejected: str
    category: str  # 'anti_laziness', 'anti_conservatism', 'adversarial_verification'
    step_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)

