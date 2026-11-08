"""Build the complete MSRA Stage 3 SimPO / DPO Contrastive Preference Dataset.

Synthesizes 3 orthogonal categories of preference pairs:
1. Anti-Laziness (Anti-Overdelegation): Prefer SOLVE_LOCAL on elementary subgoals.
2. Anti-Conservatism (Anti-Underdelegation): Prefer ASK_HELP on critical calculations.
3. Adversarial Epistemic Verification: Prefer REJECT over COMMIT on perturbed/corrupted outputs.

Run: python -m structured_llm.msra.build_preference_dataset
"""

import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .preference import PreferenceSynthesizer
from .trace_parser import parse_trace
from .types import CapabilityTag, Decision, PreferencePair, ReasoningNode, VerificationStatus

SOURCE_TRAIN = Path("data/structured_msra_coldstart_v1/train.jsonl")
SOURCE_VALID = Path("data/structured_msra_coldstart_v1/valid.jsonl")
OUTPUT_DIR = Path("data/structured_msra_simpo_v1")


def perturb_calculation(exec_text: str) -> Tuple[str, str]:
    """Perturb a numeric calculation result to create an adversarial candidate.

    Returns (perturbed_execution_string, critique_explaining_discrepancy).
    """
    # Find last number in equation: "A * B = C"
    m = re.search(r"=\s*(-?\d+(?:\.\d+)?)", exec_text)
    if not m:
        return f"{exec_text} + 1", "Arithmetic discrepancy: extraneous addition term found"

    orig_val_str = m.group(1)
    try:
        val = float(orig_val_str)
        # Perturb by adding 1 or 10%
        offset = 1 if val.is_integer() else 0.5
        perturbed_val = val + offset
        if val.is_integer():
            perturbed_str = str(int(perturbed_val))
        else:
            perturbed_str = f"{perturbed_val:.2f}"
    except ValueError:
        perturbed_str = orig_val_str + "1"

    perturbed_exec = exec_text[:m.start(1)] + perturbed_str + exec_text[m.end(1):]
    critique = f"Discrepancy detected in execution: computed result {perturbed_str} does not match exact premise ({orig_val_str})"
    return perturbed_exec, critique


def generate_pairs_for_problem(row_data: Dict[str, Any]) -> List[PreferencePair]:
    """Generate 3 contrastive preference pairs from a single structured problem."""
    text = row_data.get("text", "")
    row_id = row_data.get("id", "item")

    # Extract user prompt
    m_user = re.search(r"<\|im_start\|>user\n(.*?)(?:<\|im_end\|>|$)", text, re.DOTALL)
    if not m_user:
        return []
    user_prompt = m_user.group(1).strip()
    prefix_header = f"<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n<think>\n"

    parsed = parse_trace(text)
    if not parsed.is_valid or not parsed.nodes:
        return []

    nodes = parsed.nodes
    pairs: List[PreferencePair] = []

    # 1. Anti-Laziness Pair (Category 1) on Step 1
    node1 = nodes[0]
    p1 = PreferenceSynthesizer.create_anti_laziness_pair(
        prefix_context=prefix_header,
        step_id=1,
        subgoal=node1.subgoal,
        deps=node1.deps,
        correct_local_exec=node1.execution_result,
        critique=node1.critique or "Verified exact arithmetic",
        output_var=node1.output_var,
        unnecessary_query=f"Calculate {node1.subgoal}",
        budget_remaining=2.0,
    )
    p1.metadata["problem_id"] = row_id
    pairs.append(p1)

    # 2. Anti-Conservatism Pair (Category 2)
    # Choose step 2 if available, else step 1
    target_idx = 1 if len(nodes) > 1 else 0
    node_hard = nodes[target_idx]

    # Build context prefix up to target step
    prefix_mid = prefix_header
    for prev_idx in range(target_idx):
        prev_node = nodes[prev_idx]
        deps_str = ", ".join(f"{k} = {v}" for k, v in prev_node.deps.items()) if prev_node.deps else "None"
        out_str = ", ".join(f"{k} = {v}" for k, v in prev_node.output_var.items()) if prev_node.output_var else "None"
        prefix_mid += (
            f'<step id="{prev_node.step_id}" budget_remaining="2.00">\n'
            f"  <subgoal>{prev_node.subgoal}</subgoal>\n"
            f"  <deps>{deps_str}</deps>\n"
            f"  <capability>{prev_node.capability_tag.value}</capability>\n"
            f"  <decision>SOLVE_LOCAL</decision>\n"
            f"  <execution>{prev_node.execution_result}</execution>\n"
            f'  <verification status="COMMIT">{prev_node.critique}</verification>\n'
            f"  <output_var>{out_str}</output_var>\n"
            f"</step>\n\n"
        )

    p2 = PreferenceSynthesizer.create_anti_conservatism_pair(
        prefix_context=prefix_mid,
        step_id=node_hard.step_id,
        subgoal=node_hard.subgoal,
        capability=node_hard.capability_tag,
        deps=node_hard.deps,
        query_payload=f"Solve exact calculation: {node_hard.subgoal}",
        failed_local_exec=f"{node_hard.execution_result} (unverified estimate with potential error)",
        budget_remaining=2.0,
    )
    p2.metadata["problem_id"] = row_id
    pairs.append(p2)

    # 3. Adversarial Epistemic Verification Pair (Category 3)
    perturbed_exec, flaw_critique = perturb_calculation(node_hard.execution_result)
    p3 = PreferenceSynthesizer.create_adversarial_verification_pair(
        prefix_context=prefix_mid,
        step_id=node_hard.step_id,
        subgoal=node_hard.subgoal,
        flawed_execution_or_helper=perturbed_exec,
        valid_critique_of_flaw=flaw_critique,
        blind_commit_critique="Verified valid, proceeding to next step",
        budget_remaining=2.0,
    )
    p3.metadata["problem_id"] = row_id
    pairs.append(p3)

    return pairs


def build_preference_dataset(
    source_train: Path = SOURCE_TRAIN,
    source_valid: Path = SOURCE_VALID,
    output_dir: Path = OUTPUT_DIR,
) -> Dict[str, Any]:
    """Build train and valid preference pair datasets for SimPO / DPO."""
    source_train = Path(source_train)
    source_valid = Path(source_valid)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def process_source(src_path: Path, out_path: Path) -> Tuple[int, Dict[str, int]]:
        count = 0
        cat_counts = collections.Counter()
        with open(src_path, "r", encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                pairs = generate_pairs_for_problem(row)
                for p in pairs:
                    record = {
                        "prompt": p.prompt,
                        "chosen": p.chosen,
                        "rejected": p.rejected,
                        "category": p.category,
                        "step_id": p.step_id,
                        "metadata": p.metadata,
                    }
                    fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1
                    cat_counts[p.category] += 1
        return count, dict(cat_counts)

    train_out = output_dir / "train.jsonl"
    valid_out = output_dir / "valid.jsonl"

    train_count, train_cats = process_source(source_train, train_out)
    valid_count, valid_cats = process_source(source_valid, valid_out)

    manifest = {
        "dataset_name": "structured_msra_simpo_v1",
        "description": "Contrastive preference dataset for MSRA SimPO/DPO training (3 balanced categories)",
        "train_pairs": train_count,
        "train_distribution": train_cats,
        "valid_pairs": valid_count,
        "valid_distribution": valid_cats,
        "sha256": {
            "train.jsonl": hashlib.sha256(train_out.read_bytes()).hexdigest(),
            "valid.jsonl": hashlib.sha256(valid_out.read_bytes()).hexdigest(),
        },
    }

    manifest_out = output_dir / "manifest.json"
    manifest_out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


if __name__ == "__main__":
    rep = build_preference_dataset()
    print(json.dumps(rep, indent=2))
