"""Metacognitive Structured Reasoning Agent (MSRA) Package.

Implements Phase 2 decoupled capability routing, isolated symbolic sandbox,
epistemic verification, CBBS bottleneck search, preference pair synthesis,
interactive streaming driver, and dataset conversion.
"""

from .cbbs import CBBSController, classify_subgoal_capability
from .convert_traces import (
    convert_chatml_row,
    convert_dataset_file,
    convert_pairs_to_nodes,
    convert_trace_to_msra_xml,
    extract_subgoal,
    parse_step_calc_pairs,
)
from .harness import MetacognitiveReasoningHarness
from .intervene_msra import (
    classify_msra_outcome,
    find_eligible_intervention_step,
    plan_msra_intervention,
)
from .mlx_backend import MLXGeneratorBackend

from .preference import PreferenceSynthesizer
from .router import CapabilityRouter
from .sandbox import SymPySandbox
from .stream_driver import GeneratorBackend, MockGeneratorBackend, MSRAStepDriver

from .trace_parser import (
    compute_helper_spans,
    extract_final_answer,
    format_node_to_xml,
    format_trace_to_xml,
    parse_step,
    parse_trace,
    parse_var_dict,
)
from .types import (
    CAPABILITY_COSTS,
    CapabilityTag,
    Decision,
    PackagedQuery,
    PreferencePair,
    ReasoningNode,
    TraceValidationResult,
    VerificationStatus,
)
from .verifier import EpistemicVerifier

__all__ = [
    "CapabilityTag",
    "Decision",
    "VerificationStatus",
    "CAPABILITY_COSTS",
    "ReasoningNode",
    "PackagedQuery",
    "TraceValidationResult",
    "PreferencePair",
    "CapabilityRouter",
    "SymPySandbox",
    "EpistemicVerifier",
    "MetacognitiveReasoningHarness",
    "CBBSController",
    "classify_subgoal_capability",
    "PreferenceSynthesizer",
    "MSRAStepDriver",
    "GeneratorBackend",
    "MockGeneratorBackend",
    "MLXGeneratorBackend",
    "parse_trace",

    "parse_step",
    "parse_var_dict",
    "extract_final_answer",
    "format_node_to_xml",
    "format_trace_to_xml",
    "compute_helper_spans",
    "convert_chatml_row",
    "convert_dataset_file",
    "convert_pairs_to_nodes",
    "convert_trace_to_msra_xml",
    "extract_subgoal",
    "parse_step_calc_pairs",
    "find_eligible_intervention_step",
    "plan_msra_intervention",
    "classify_msra_outcome",
]

