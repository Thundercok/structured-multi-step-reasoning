"""Analyze DAG structural complexity and capability distributions of MSRA datasets.

Run: python -m structured_llm.msra.analyze_dag data/structured_msra_coldstart_v1/train.jsonl
"""

import collections
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

from .trace_parser import parse_trace
from .types import CapabilityTag, Decision, VerificationStatus


def analyze_dataset_dag(file_path: Path) -> Dict[str, Any]:
    """Compute empirical DAG statistics on an MSRA dataset file."""
    file_path = Path(file_path)
    total_problems = 0
    total_nodes = 0
    steps_distribution = collections.Counter()
    capability_distribution = collections.Counter()
    decision_distribution = collections.Counter()
    dep_count_distribution = collections.Counter()
    verification_distribution = collections.Counter()
    char_lengths = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_problems += 1
            data = json.loads(line)
            text = data.get("text", "")
            char_lengths.append(len(text))

            res = parse_trace(text)
            if not res.is_valid:
                continue

            num_steps = len(res.nodes)
            steps_distribution[num_steps] += 1
            total_nodes += num_steps

            for node in res.nodes:
                capability_distribution[node.capability_tag.value] += 1
                decision_distribution[node.decision.value] += 1
                verification_distribution[node.verification_status.value] += 1
                num_deps = len(node.deps)
                dep_count_distribution[num_deps] += 1

    char_lengths.sort()
    mean_chars = sum(char_lengths) / max(1, len(char_lengths))
    p50_chars = char_lengths[len(char_lengths) // 2] if char_lengths else 0
    p90_chars = char_lengths[int(len(char_lengths) * 0.9)] if char_lengths else 0

    return {
        "file": str(file_path),
        "total_problems": total_problems,
        "total_nodes": total_nodes,
        "mean_steps_per_problem": round(total_nodes / max(1, total_problems), 2),
        "steps_per_problem_distribution": dict(sorted(steps_distribution.items())),
        "capability_distribution": {
            k: {
                "count": v,
                "percentage": round(v / max(1, total_nodes) * 100, 2),
            }
            for k, v in capability_distribution.items()
        },
        "dependency_in_degree_distribution": {
            f"{k}_deps": {
                "count": v,
                "percentage": round(v / max(1, total_nodes) * 100, 2),
            }
            for k, v in sorted(dep_count_distribution.items())
        },
        "decision_distribution": dict(decision_distribution),
        "verification_distribution": dict(verification_distribution),
        "text_length_stats": {
            "mean_chars": round(mean_chars, 1),
            "p50_chars": p50_chars,
            "p90_chars": p90_chars,
            "max_chars": char_lengths[-1] if char_lengths else 0,
        },
    }


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/structured_msra_coldstart_v1/train.jsonl")
    report = analyze_dataset_dag(target)
    print(json.dumps(report, indent=2))
