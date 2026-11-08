"""Capability Router for Metacognitive Structured Reasoning Agent (MSRA).

Maps orthogonal capability tags to optimal specialized helpers based on computational budget.
Eliminates hardcoded tool identities in the small base language model.
"""

from typing import Any, Callable, Dict, Optional, Tuple

from .types import CapabilityTag, CAPABILITY_COSTS, PackagedQuery


class CapabilityRouter:
    """Dynamic router mapping Capability Tags (tau_t) to specialized helpers."""

    def __init__(self):
        self._helpers: Dict[str, Tuple[Callable[[str], str], float, str]] = {}

    def register_helper(
        self,
        capability: CapabilityTag | str,
        fn: Callable[[str], str],
        cost: Optional[float] = None,
        source_id: str = "helper",
    ) -> None:
        """Register a helper function for a capability tag."""
        tag = capability.value if isinstance(capability, CapabilityTag) else capability
        if cost is None:
            # Fall back to default standard cost if tag is a known CapabilityTag
            try:
                cost = CAPABILITY_COSTS.get(CapabilityTag(tag), 0.1)
            except ValueError:
                cost = 0.1
        self._helpers[tag] = (fn, float(cost), source_id)

    def has_helper(self, capability: CapabilityTag | str) -> bool:
        tag = capability.value if isinstance(capability, CapabilityTag) else capability
        return tag in self._helpers

    def get_cost(self, capability: CapabilityTag | str) -> float:
        tag = capability.value if isinstance(capability, CapabilityTag) else capability
        if tag in self._helpers:
            return self._helpers[tag][1]
        try:
            return CAPABILITY_COSTS.get(CapabilityTag(tag), 0.1)
        except ValueError:
            return 0.1

    def pack(
        self,
        subgoal: str,
        dependencies: Dict[str, Any],
        capability: CapabilityTag | str,
        query: str,
    ) -> PackagedQuery:
        """Pack isolated query q_t = Pack(g_t, D_t) with O(1) context complexity."""
        tag = CapabilityTag(capability) if isinstance(capability, str) else capability
        return PackagedQuery(
            subgoal=subgoal.strip(),
            dependencies=dict(dependencies),
            target_capability=tag,
            raw_query=query.strip(),
        )

    def dispatch(
        self,
        capability: CapabilityTag | str,
        payload: str,
        remaining_budget: float,
    ) -> Tuple[str, float, str]:
        """Dispatch query payload to helper.

        Returns (result_string, cost_incurred, source_id).
        """
        tag = capability.value if isinstance(capability, CapabilityTag) else capability
        if tag not in self._helpers:
            return (f"[SYSTEM_ERROR: NO_HELPER_REGISTERED_FOR_{tag}]", 0.0, "router")

        fn, cost, source_id = self._helpers[tag]
        if cost > remaining_budget:
            warning = (
                f"[SYSTEM_WARNING: BUDGET_EXCEEDED] (Cost {cost:.2f} > Remaining {remaining_budget:.2f}). "
                "Falling back to local execution."
            )
            return (warning, 0.0, "budget_guard")

        try:
            result = fn(payload)
            return (str(result), cost, source_id)
        except Exception as e:
            return (f"[HELPER_EXECUTION_ERROR: {type(e).__name__}: {e}]", cost, source_id)
