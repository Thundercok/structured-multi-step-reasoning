"""XML Parser, Validator, and Serializer for MSRA Structured Reasoning Traces."""

import re
from typing import Any, Dict, List, Optional, Tuple

from .types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    TraceValidationResult,
    VerificationStatus,
)

_STEP_BLOCK_RE = re.compile(r'<step\s+id=["\'](\d+)["\'](?:\s+budget_remaining=["\']([^"\']+)["\'])?\s*>(.*?)</step>', re.DOTALL)
_TAG_RE = {
    "subgoal": re.compile(r"<subgoal>(.*?)</subgoal>", re.DOTALL),
    "deps": re.compile(r"<deps>(.*?)</deps>", re.DOTALL),
    "capability": re.compile(r"<capability>(.*?)</capability>", re.DOTALL),
    "decision": re.compile(r"<decision>(.*?)</decision>", re.DOTALL),
    "execution": re.compile(r"<execution>(.*?)</execution>", re.DOTALL),
    "query_payload": re.compile(r"<query_payload>(.*?)</query_payload>", re.DOTALL),
    "helper_response": re.compile(r'<helper_response(?:\s+source=["\']([^"\']+)["\'])?\s*>(.*?)</helper_response>', re.DOTALL),
    "verification": re.compile(r'<verification(?:\s+status=["\']([^"\']+)["\'])?\s*>(.*?)</verification>', re.DOTALL),
    "output_var": re.compile(r"<output_var>(.*?)</output_var>", re.DOTALL),
}
_FINAL_ANSWER_RE = re.compile(r"<final_answer>(.*?)</final_answer>", re.DOTALL)
_HELPER_RESPONSE_SPAN_RE = re.compile(r"<helper_response(?:\s+source=[\"'][^\"']+[\"'])?\s*>.*?</helper_response>", re.DOTALL)


def parse_var_dict(text: str) -> Dict[str, str]:
    """Parse comma or newline separated assignments like 'x = 5, y = 10' or 'x: 5'."""
    text = text.strip()
    if not text or text.lower() == "none":
        return {}
    res: Dict[str, str] = {}
    for part in re.split(r"[,;\n]", text):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            res[k.strip()] = v.strip()
        elif ":" in part:
            k, v = part.split(":", 1)
            res[k.strip()] = v.strip()
        else:
            res[part] = "true"
    return res


def parse_step(step_id_str: str, content: str, budget_str: Optional[str] = None) -> Tuple[Optional[ReasoningNode], List[str]]:
    """Parse a single <step> block into a ReasoningNode, returning any validation errors."""
    errors: List[str] = []
    try:
        step_id = int(step_id_str)
    except ValueError:
        return None, [f"Invalid step_id '{step_id_str}'"]

    # Extract tags
    m_subgoal = _TAG_RE["subgoal"].search(content)
    m_deps = _TAG_RE["deps"].search(content)
    m_cap = _TAG_RE["capability"].search(content)
    m_dec = _TAG_RE["decision"].search(content)
    m_exec = _TAG_RE["execution"].search(content)
    m_qp = _TAG_RE["query_payload"].search(content)
    m_hr = _TAG_RE["helper_response"].search(content)
    m_ver = _TAG_RE["verification"].search(content)
    m_out = _TAG_RE["output_var"].search(content)

    if not m_subgoal:
        errors.append(f"Step {step_id}: Missing <subgoal>")
        subgoal = ""
    else:
        subgoal = m_subgoal.group(1).strip()

    deps_raw = m_deps.group(1).strip() if m_deps else ""
    deps = parse_var_dict(deps_raw)

    # Capability tag
    cap_raw = m_cap.group(1).strip() if m_cap else "CAP:DECOMPOSE"
    try:
        capability = CapabilityTag(cap_raw)
    except ValueError:
        errors.append(f"Step {step_id}: Invalid capability tag '{cap_raw}'")
        capability = CapabilityTag.DECOMPOSE

    # Decision tag
    dec_raw = m_dec.group(1).strip() if m_dec else "SOLVE_LOCAL"
    try:
        decision = Decision(dec_raw)
    except ValueError:
        errors.append(f"Step {step_id}: Invalid decision '{dec_raw}'")
        decision = Decision.SOLVE_LOCAL

    # Execution / Helper response
    execution_result = ""
    helper_source = None
    query_payload = None

    if decision == Decision.ASK_HELP:
        if not m_qp:
            errors.append(f"Step {step_id}: ASK_HELP chosen but <query_payload> is missing")
        else:
            query_payload = m_qp.group(1).strip()
        if m_hr:
            helper_source = m_hr.group(1) or "helper"
            execution_result = m_hr.group(2).strip()
        elif m_exec:
            execution_result = m_exec.group(1).strip()
    else:
        if m_exec:
            execution_result = m_exec.group(1).strip()

    # Verification status
    ver_status = VerificationStatus.PENDING
    critique = ""
    if m_ver:
        status_attr = (m_ver.group(1) or "COMMIT").upper().strip()
        try:
            ver_status = VerificationStatus(status_attr)
        except ValueError:
            errors.append(f"Step {step_id}: Invalid verification status '{status_attr}'")
        critique = m_ver.group(2).strip()
        if ver_status == VerificationStatus.REJECT and not critique:
            errors.append(f"Step {step_id}: REJECT status requires critique justification in <verification>")
    else:
        errors.append(f"Step {step_id}: Missing <verification>")

    out_raw = m_out.group(1).strip() if m_out else ""
    output_var = parse_var_dict(out_raw)

    cost = 0.0
    if budget_str:
        try:
            cost = float(budget_str)
        except ValueError:
            cost = 0.0

    node = ReasoningNode(
        step_id=step_id,
        subgoal=subgoal,
        capability_tag=capability,
        decision=decision,
        deps=deps,
        query_payload=query_payload,
        execution_result=execution_result,
        verification_status=ver_status,
        critique=critique,
        output_var=output_var,
        helper_source=helper_source,
        cost=cost,
    )
    return node, errors


def parse_trace(text: str) -> TraceValidationResult:
    """Parse complete multi-step XML reasoning trace and validate DAG dependencies."""
    errors: List[str] = []
    nodes: List[ReasoningNode] = []
    available_vars: Dict[str, Any] = {}

    matches = list(_STEP_BLOCK_RE.finditer(text))
    if not matches:
        return TraceValidationResult(is_valid=False, errors=["No <step> blocks found in trace"], nodes=[])

    expected_id = 1
    for match in matches:
        step_id_str, budget_str, step_body = match.groups()
        node, step_errors = parse_step(step_id_str, step_body, budget_str)
        errors.extend(step_errors)
        if node is None:
            continue

        # Sequential ID check
        if node.step_id != expected_id:
            errors.append(f"Non-sequential step id: expected {expected_id}, got {node.step_id}")
        expected_id = node.step_id + 1

        # Check DAG variable dependencies
        for dep_var in node.deps:
            if dep_var not in available_vars:
                errors.append(
                    f"Step {node.step_id}: Dependency variable '{dep_var}' referenced in <deps> "
                    f"was not produced by any preceding step's <output_var>"
                )

        # Register committed output variables
        if node.verification_status == VerificationStatus.COMMIT:
            for k, v in node.output_var.items():
                available_vars[k] = v

        nodes.append(node)

    is_valid = len(errors) == 0
    return TraceValidationResult(is_valid=is_valid, errors=errors, nodes=nodes)


_ANSWER_LINE_RE = re.compile(r"(?:^|\n)Answer:\s*([^\n<]+)")


def extract_final_answer(text: str) -> Optional[str]:
    """Extract content inside <final_answer>...</final_answer> or trailing Answer: line."""
    m = _FINAL_ANSWER_RE.search(text)
    if m:
        return m.group(1).strip()
    matches = list(_ANSWER_LINE_RE.finditer(text))
    if matches:
        ans = matches[-1].group(1).strip()
        return ans[:-1].strip() if ans.endswith(".") else ans
    return None


def format_node_to_xml(node: ReasoningNode, budget_remaining: float = 2.0) -> str:
    """Serialize a single ReasoningNode to XML string."""
    deps_str = ", ".join(f"{k} = {v}" for k, v in node.deps.items()) if node.deps else "None"
    out_str = ", ".join(f"{k} = {v}" for k, v in node.output_var.items()) if node.output_var else "None"

    lines = [
        f'<step id="{node.step_id}" budget_remaining="{budget_remaining:.2f}">',
        f"  <subgoal>{node.subgoal}</subgoal>",
        f"  <deps>{deps_str}</deps>",
        f"  <capability>{node.capability_tag.value}</capability>",
        f"  <decision>{node.decision.value}</decision>",
    ]

    if node.decision == Decision.ASK_HELP:
        if node.query_payload:
            lines.append(f"  <query_payload>{node.query_payload}</query_payload>")
        src = f' source="{node.helper_source}"' if node.helper_source else ' source="h_sym"'
        lines.append(f"  <helper_response{src}>{node.execution_result}</helper_response>")
    else:
        lines.append(f"  <execution>{node.execution_result}</execution>")

    lines.append(f'  <verification status="{node.verification_status.value}">{node.critique}</verification>')
    lines.append(f"  <output_var>{out_str}</output_var>")
    lines.append("</step>")
    return "\n".join(lines)


def format_trace_to_xml(nodes: List[ReasoningNode], final_answer: Optional[str] = None, initial_budget: float = 2.0) -> str:
    """Serialize entire reasoning DAG to canonical XML format."""
    remaining_budget = initial_budget
    steps_xml: List[str] = []
    for node in nodes:
        steps_xml.append(format_node_to_xml(node, remaining_budget))
        remaining_budget = max(0.0, remaining_budget - node.cost)

    res = "\n\n".join(steps_xml)
    if final_answer is not None:
        res += f"\n\n<final_answer>{final_answer}</final_answer>"
    return res


def compute_helper_spans(text: str) -> List[Tuple[int, int]]:
    """Return character start and end offsets of all <helper_response> blocks for SFT loss masking."""
    spans: List[Tuple[int, int]] = []
    for m in _HELPER_RESPONSE_SPAN_RE.finditer(text):
        spans.append((m.start(), m.end()))
    return spans
