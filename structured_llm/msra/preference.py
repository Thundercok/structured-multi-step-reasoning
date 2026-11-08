"""SimPO and DPO Contrastive Preference Pair Synthesizer for MSRA.

Generates 3 categories of training pairs:
1. Anti-Laziness (Anti-Overdelegation): Prefer SOLVE_LOCAL over ASK_HELP on easy steps.
2. Anti-Conservatism (Anti-Underdelegation): Prefer ASK_HELP over SOLVE_LOCAL on bottleneck steps.
3. Adversarial Epistemic Verification: Prefer REJECT over COMMIT when helper or execution output is flawed.
"""

from typing import Any, Dict, List, Optional

from .trace_parser import format_node_to_xml
from .types import (
    CapabilityTag,
    Decision,
    PreferencePair,
    ReasoningNode,
    VerificationStatus,
)


class PreferenceSynthesizer:
    """Synthesizes contrastive preference pairs (chosen vs. rejected) for preference fine-tuning."""

    @staticmethod
    def create_anti_laziness_pair(
        prefix_context: str,
        step_id: int,
        subgoal: str,
        deps: Dict[str, str],
        correct_local_exec: str,
        critique: str,
        output_var: Dict[str, str],
        unnecessary_query: str,
        budget_remaining: float = 2.0,
    ) -> PreferencePair:
        """Category 1: Prevent over-delegation on subgoals that can be easily solved locally."""
        deps_str = ", ".join(f"{k} = {v}" for k, v in deps.items()) if deps else "None"
        out_str = ", ".join(f"{k} = {v}" for k, v in output_var.items()) if output_var else "None"

        step_prompt = (
            f"{prefix_context}"
            f'<step id="{step_id}" budget_remaining="{budget_remaining:.2f}">\n'
            f"  <subgoal>{subgoal}</subgoal>\n"
            f"  <deps>{deps_str}</deps>\n"
            f"  <capability>CAP:DECOMPOSE</capability>\n"
            f"  <decision>"
        )

        chosen = (
            f"SOLVE_LOCAL</decision>\n"
            f"  <execution>{correct_local_exec}</execution>\n"
            f'  <verification status="COMMIT">{critique}</verification>\n'
            f"  <output_var>{out_str}</output_var>\n"
            f"</step>"
        )

        rejected = (
            f"ASK_HELP</decision>\n"
            f"  <query_payload>{unnecessary_query}</query_payload>\n"
            f'  <helper_response source="h_sym">{correct_local_exec}</helper_response>\n'
            f'  <verification status="COMMIT">{critique}</verification>\n'
            f"  <output_var>{out_str}</output_var>\n"
            f"</step>"
        )

        return PreferencePair(
            prompt=step_prompt,
            chosen=chosen,
            rejected=rejected,
            category="anti_laziness",
            step_id=step_id,
            metadata={"subgoal": subgoal},
        )

    @staticmethod
    def create_anti_conservatism_pair(
        prefix_context: str,
        step_id: int,
        subgoal: str,
        capability: CapabilityTag,
        deps: Dict[str, str],
        query_payload: str,
        failed_local_exec: str,
        budget_remaining: float = 2.0,
    ) -> PreferencePair:
        """Category 2: Encourage seeking help on hard computational/algebraic bottlenecks."""
        deps_str = ", ".join(f"{k} = {v}" for k, v in deps.items()) if deps else "None"

        step_prompt = (
            f"{prefix_context}"
            f'<step id="{step_id}" budget_remaining="{budget_remaining:.2f}">\n'
            f"  <subgoal>{subgoal}</subgoal>\n"
            f"  <deps>{deps_str}</deps>\n"
            f"  <capability>{capability.value}</capability>\n"
            f"  <decision>"
        )

        chosen = (
            f"ASK_HELP</decision>\n"
            f"  <query_payload>{query_payload}</query_payload>"
        )

        rejected = (
            f"SOLVE_LOCAL</decision>\n"
            f"  <execution>{failed_local_exec}</execution>"
        )

        return PreferencePair(
            prompt=step_prompt,
            chosen=chosen,
            rejected=rejected,
            category="anti_conservatism",
            step_id=step_id,
            metadata={"subgoal": subgoal, "capability": capability.value},
        )

    @staticmethod
    def create_adversarial_verification_pair(
        prefix_context: str,
        step_id: int,
        subgoal: str,
        flawed_execution_or_helper: str,
        valid_critique_of_flaw: str,
        blind_commit_critique: str,
        budget_remaining: float = 2.0,
    ) -> PreferencePair:
        """Category 3: Train model to reject invalid or corrupted results in Phase 2 verification."""
        step_prompt = (
            f"{prefix_context}"
            f'<step id="{step_id}" budget_remaining="{budget_remaining:.2f}">\n'
            f"  <subgoal>{subgoal}</subgoal>\n"
            f"  <decision>SOLVE_LOCAL</decision>\n"
            f"  <execution>{flawed_execution_or_helper}</execution>\n"
            f"  <verification "
        )

        chosen = f'status="REJECT">{valid_critique_of_flaw}</verification>\n</step>'
        rejected = f'status="COMMIT">{blind_commit_critique}</verification>\n</step>'

        return PreferencePair(
            prompt=step_prompt,
            chosen=chosen,
            rejected=rejected,
            category="adversarial_verification",
            step_id=step_id,
            metadata={"flawed_text": flawed_execution_or_helper},
        )
