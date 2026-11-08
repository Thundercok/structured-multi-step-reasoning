#!/usr/bin/env python3
"""MSRA Graph Visualizer and Diagnostic Trace Auditor.

Converts MSRA XML reasoning traces into:
1. ASCII DAG tree representation in terminal
2. Publication-ready Mermaid diagrams (`graph TD`)
3. Graphviz DOT digraph format (`digraph G { ... }`)

Usage:
    python tools/visualize_dag.py --input "<trace_string_or_file>"
    python tools/visualize_dag.py --file data/structured_msra_coldstart_v1/valid.jsonl --index 0
"""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from structured_llm.msra.trace_parser import extract_final_answer, parse_trace
from structured_llm.msra.types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    TraceValidationResult,
    VerificationStatus,
)


def render_ascii_dag(parsed: TraceValidationResult, final_answer: Optional[str] = None) -> str:
    """Render a terminal-friendly ASCII Directed Acyclic Graph."""
    if not parsed.nodes:
        return "[Empty or Invalid DAG]"

    lines = []
    lines.append("MSRA Encapsulated DAG Trace:")
    lines.append(f"  Valid XML: {parsed.is_valid} | Acyclic: {len(parsed.errors) == 0}")
    if parsed.errors:
        lines.append(f"  Errors: {', '.join(parsed.errors)}")
    lines.append("-" * 50)

    for idx, node in enumerate(parsed.nodes):
        dec_tag = "[LOCAL]" if node.decision == Decision.SOLVE_LOCAL else "[HELPER]"
        verif_tag = f"[{node.verification_status.value}]"
        deps_str = ", ".join(f"{k}={v}" for k, v in node.deps.items()) if node.deps else "None"
        out_str = ", ".join(f"{k}={v}" for k, v in node.output_var.items()) if node.output_var else "None"

        prefix = "├──" if idx < len(parsed.nodes) - 1 else "└──"
        lines.append(f"{prefix} Step {node.step_id} {dec_tag} {verif_tag}")
        lines.append(f"│     Subgoal:    {node.subgoal}")
        lines.append(f"│     Capability: {node.capability_tag.value}")
        lines.append(f"│     Deps (In):  {deps_str}")
        lines.append(f"│     Execution:  {node.execution_result}")
        lines.append(f"│     Output (Out): {out_str}")
        if idx < len(parsed.nodes) - 1:
            lines.append("│")

    if final_answer:
        lines.append(f"└── Final Answer: {final_answer}")
    return "\n".join(lines)


def render_mermaid(parsed: TraceValidationResult, final_answer: Optional[str] = None) -> str:
    """Render Mermaid flowchart graph TD syntax."""
    lines = ["graph TD"]

    for node in parsed.nodes:
        nid = f"step_{node.step_id}"
        dec_label = "SOLVE_LOCAL" if node.decision == Decision.SOLVE_LOCAL else "ASK_HELP"
        clean_subgoal = node.subgoal.replace('"', "'")
        
        lines.append(f'    {nid}["Step {node.step_id}: {dec_label}<br/><b>{node.capability_tag.value}</b><br/>{clean_subgoal}"]:::nodeStyle')
        
        # Draw dependency edges
        if node.deps:
            for dep_var in node.deps:
                for prior in parsed.nodes:
                    if prior.step_id < node.step_id and dep_var in prior.output_var:
                        lines.append(f"    step_{prior.step_id} -->|{dep_var}| {nid}")

    if final_answer and parsed.nodes:
        last_id = f"step_{parsed.nodes[-1].step_id}"
        lines.append(f'    ans["<b>Final Answer: {final_answer}</b>"]:::ansStyle')
        lines.append(f"    {last_id} --> ans")

    lines.append("    classDef nodeStyle fill:#e1f5fe,stroke:#0288d1,stroke-width:1.5px;")
    lines.append("    classDef ansStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;")
    return "\n".join(lines)


def render_dot(parsed: TraceValidationResult, final_answer: Optional[str] = None) -> str:
    """Render Graphviz DOT digraph format."""
    lines = [
        "digraph MSRA_DAG {",
        '    node [fontname="Helvetica", shape=box, style="rounded,filled", fillcolor="#f0f4f8"];',
        '    edge [fontname="Helvetica", fontsize=10];',
    ]

    for node in parsed.nodes:
        nid = f"step_{node.step_id}"
        color = "#e1f5fe" if node.decision == Decision.SOLVE_LOCAL else "#f3e5f5"
        label = f"Step {node.step_id} ({node.decision.value})\\n{node.capability_tag.value}\\n{node.subgoal[:35]}..."
        lines.append(f'    {nid} [label="{label}", fillcolor="{color}"];')

        if node.deps:
            for dep_var in node.deps:
                for prior in parsed.nodes:
                    if prior.step_id < node.step_id and dep_var in prior.output_var:
                        lines.append(f'    step_{prior.step_id} -> {nid} [label="{dep_var}"];')

    if final_answer and parsed.nodes:
        last_id = f"step_{parsed.nodes[-1].step_id}"
        lines.append(f'    ans [label="Final Answer: {final_answer}", fillcolor="#c8e6c9", shape=ellipse];')
        lines.append(f"    {last_id} -> ans;")

    lines.append("}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="MSRA DAG Trace Visualizer")
    parser.add_argument("--input", "-i", type=str, help="Raw XML or ChatML trace string")
    parser.add_argument("--file", "-f", type=str, help="Path to JSONL dataset file")
    parser.add_argument("--index", type=int, default=0, help="Line index if reading from JSONL file")
    parser.add_argument("--format", choices=["ascii", "mermaid", "dot", "all"], default="all")
    args = parser.parse_args()

    trace_text = ""
    if args.input:
        trace_text = args.input
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"File not found: {file_path}")
            sys.exit(1)
        lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.index >= len(lines):
            print(f"Index {args.index} out of range (max {len(lines)-1})")
            sys.exit(1)
        row = json.loads(lines[args.index])
        trace_text = row.get("text", "") or row.get("output", "") or row.get("trace", "")
    else:
        # Default sample trace
        trace_text = (
            '<step id="1" budget_remaining="2.00">\n'
            "  <subgoal>Calculate clips sold in May</subgoal>\n"
            "  <deps>None</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>48 / 2 = 24</execution>\n"
            '  <verification status="COMMIT">Exact half</verification>\n'
            "  <output_var>v1 = 24</output_var>\n"
            "</step>\n\n"
            '<step id="2" budget_remaining="2.00">\n'
            "  <subgoal>Calculate total clips sold altogether</subgoal>\n"
            "  <deps>v1 = 24</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>48 + 24 = 72</execution>\n"
            '  <verification status="COMMIT">Exact sum</verification>\n'
            "  <output_var>v2 = 72</output_var>\n"
            "</step>\n\n"
            "Answer: 72"
        )

    parsed = parse_trace(trace_text)
    final_ans = extract_final_answer(trace_text)

    if args.format in ("ascii", "all"):
        print("=== ASCII DAG ===")
        print(render_ascii_dag(parsed, final_ans))
        print()

    if args.format in ("mermaid", "all"):
        print("=== MERMAID FLOWCHART ===")
        print("```mermaid")
        print(render_mermaid(parsed, final_ans))
        print("```")
        print()

    if args.format in ("dot", "all"):
        print("=== GRAPHVIZ DOT ===")
        print(render_dot(parsed, final_ans))
        print()


if __name__ == "__main__":
    main()
