#!/usr/bin/env python3
"""CPU-Only Preflight Study for Logic Ordering Task.

Evaluates Baseline Parser vs. Extended Parser on 6 canonical groups (18 items):
- Tuning Dev: Groups 1-3 (9 items: 3 baseline, 3 lexical, 3 prose)
- Held-out Dev: Groups 4-6 (9 items: 3 baseline, 3 lexical, 3 prose)

Measures:
- Parse coverage
- Constraint equivalence
- Overall accuracy (fail-closed)
- Accuracy on parsed subset
- CPU timing (parse, solve, total)
- Detailed failure taxonomy per case
"""

import itertools
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verified_pal_order import (
    OrderClue,
    OrderConstraintIR,
    parse_order_query,
    solve_order_ir,
)
from scripts.extended_order_parser import (
    parse_order_query_extended,
    _extract_runners,
    _extract_ask_rank,
    _segment_clues,
    _parse_single_clause,
)


def holds(clue_type: str, x: int, y: int, offset: int | None, pos: dict[int, int]) -> bool:
    if clue_type == "before":
        return pos[x] < pos[y]
    elif clue_type in ("immediately_before", "gap"):
        return pos[y] - pos[x] == offset
    raise ValueError(f"Unknown clue type: {clue_type}")


def get_satisfying_perms(runners: tuple[str, ...], clues: tuple[OrderClue, ...]) -> set[tuple[int, ...]]:
    n = len(runners)
    name_to_idx = {name: i for i, name in enumerate(runners)}
    norm_clues = []
    for c in clues:
        ctype, x, y, offset = c.clue_type, c.runner_x, c.runner_y, c.offset
        norm_clues.append((ctype, name_to_idx[x], name_to_idx[y], offset))

    valid = []
    for perm in itertools.permutations(range(n)):
        pos = {runner_idx: rank for rank, runner_idx in enumerate(perm)}
        if all(holds(ctype, x, y, offset, pos) for ctype, x, y, offset in norm_clues):
            valid.append(perm)
    return set(valid)


def diagnose_extended_failure(query: str) -> dict[str, str]:
    runners = _extract_runners(query)
    if runners is None:
        return {
            "stage": "runner_extraction",
            "reason": "Failed to extract valid runner names (2-8 unique known names).",
        }

    rank = _extract_ask_rank(query)
    if rank is None:
        return {
            "stage": "ask_rank_extraction",
            "reason": "Failed to extract target rank (unseen question phrasing or verb).",
        }

    clauses = _segment_clues(query)
    if not clauses:
        return {
            "stage": "clue_segmentation",
            "reason": "Failed to segment query body into constituent clue clauses.",
        }

    names_dict = {n.casefold(): n for n in runners}
    unparsed_clauses = []
    for c in clauses:
        parsed_c = _parse_single_clause(c, names_dict, len(runners))
        if parsed_c is None:
            unparsed_clauses.append(c)

    if unparsed_clauses:
        return {
            "stage": "clause_parsing",
            "reason": f"Failed to match clause patterns: {unparsed_clauses}",
        }

    return {"stage": "unknown", "reason": "All subcomponents parsed but overall failed."}


def run_preflight():
    dataset_path = ROOT / "data/order_paraphrase_dev.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing dataset at {dataset_path}")

    with open(dataset_path) as f:
        data = json.load(f)

    # Benchmark tracking
    records = []
    timings = defaultdict(lambda: {"parse_ms": [], "solve_ms": [], "total_ms": []})

    for group in data["groups"]:
        canonical_runners = tuple(group["runners"])
        canonical_clues = tuple(
            OrderClue(c[0], c[1], c[2], c[3], "") for c in group["canonical_clues"]
        )
        canonical_ask_rank = group["ask_rank"]
        gold_answer = group["answer"]
        split = group["split"]
        canonical_perms = get_satisfying_perms(canonical_runners, canonical_clues)

        for item in group["items"]:
            item_id = item["id"]
            variant_type = item["variant_type"]
            query = item["query"]

            for parser_name, parser_fn in [
                ("Baseline", parse_order_query),
                ("Extended", parse_order_query_extended),
            ]:
                # Measure timing (run 20 repeats for stability)
                repeats = 20
                t0 = time.perf_counter()
                for _ in range(repeats):
                    ir = parser_fn(query)
                t1 = time.perf_counter()
                parse_time_ms = ((t1 - t0) / repeats) * 1000.0

                solve_time_ms = 0.0
                solved_status = "unparsed"
                solved_answer = None
                constraint_equiv = False

                if ir is not None:
                    t2 = time.perf_counter()
                    for _ in range(repeats):
                        sol = solve_order_ir(ir)
                    t3 = time.perf_counter()
                    solve_time_ms = ((t3 - t2) / repeats) * 1000.0

                    solved_status = sol.status
                    solved_answer = sol.answer

                    # Check constraint equivalence across permutation space
                    parsed_perms = get_satisfying_perms(ir.runners, ir.clues)
                    constraint_equiv = (
                        parsed_perms == canonical_perms
                        and ir.ask_rank == canonical_ask_rank
                    )
                else:
                    sol = None

                total_time_ms = parse_time_ms + solve_time_ms
                timings[parser_name]["parse_ms"].append(parse_time_ms)
                timings[parser_name]["solve_ms"].append(solve_time_ms)
                timings[parser_name]["total_ms"].append(total_time_ms)

                diag = None
                if ir is None and parser_name == "Extended":
                    diag = diagnose_extended_failure(query)

                records.append({
                    "item_id": item_id,
                    "group_id": group["group_id"],
                    "canonical_id": group["canonical_id"],
                    "split": split,
                    "variant_type": variant_type,
                    "query": query,
                    "gold_answer": gold_answer,
                    "parser": parser_name,
                    "parsed": ir is not None,
                    "constraint_equiv": constraint_equiv,
                    "solved_status": solved_status,
                    "predicted_answer": solved_answer,
                    "correct": (solved_answer == gold_answer) if ir is not None else False,
                    "parse_ms": parse_time_ms,
                    "solve_ms": solve_time_ms,
                    "total_ms": total_time_ms,
                    "diagnosis": diag,
                })

    return records, timings


def compute_metrics(records, filter_fn=None):
    if filter_fn:
        filtered = [r for r in records if filter_fn(r)]
    else:
        filtered = records

    total = len(filtered)
    if total == 0:
        return {}

    parsed_count = sum(1 for r in filtered if r["parsed"])
    equiv_count = sum(1 for r in filtered if r["constraint_equiv"])
    correct_count = sum(1 for r in filtered if r["correct"])

    coverage = (parsed_count / total) * 100.0
    equiv_rate = (equiv_count / total) * 100.0
    equiv_of_parsed = (equiv_count / parsed_count * 100.0) if parsed_count > 0 else 0.0
    overall_acc = (correct_count / total) * 100.0
    parsed_acc = (correct_count / parsed_count * 100.0) if parsed_count > 0 else 0.0

    return {
        "total": total,
        "parsed": parsed_count,
        "coverage_pct": coverage,
        "equiv_count": equiv_count,
        "equiv_pct_of_total": equiv_rate,
        "equiv_pct_of_parsed": equiv_of_parsed,
        "correct": correct_count,
        "overall_acc_pct": overall_acc,
        "parsed_acc_pct": parsed_acc,
    }


def stats(values):
    if not values:
        return {"mean": 0, "median": 0, "min": 0, "max": 0}
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {"mean": mean, "median": median, "min": s[0], "max": s[-1]}


if __name__ == "__main__":
    records, timings = run_preflight()

    print("=" * 80)
    print("CPU-ONLY PREFLIGHT BENCHMARK REPORT: LOGIC ORDERING TASK")
    print("=" * 80)
    print("Protocol: 6 Canonical Groups, 18 Items Total.")
    print("  - Tuning Dev (Groups 1-3): 9 items (3 baseline, 3 lexical, 3 prose)")
    print("  - Held-out Dev (Groups 4-6): 9 items (3 baseline, 3 lexical, 3 prose)")
    print("  - Fail-closed evaluation: Unparsed queries count as 0 accuracy.")
    print("-" * 80)

    for parser in ["Baseline", "Extended"]:
        print(f"\n--- PARSER: {parser.upper()} ---")
        for split_label, split_val in [
            ("Tuning Dev (in-sample)", "tuning_dev"),
            ("Held-out Dev (out-of-sample)", "heldout_dev"),
            ("Combined Dev (all 18 items)", None),
        ]:
            if split_val:
                m = compute_metrics(records, lambda r: r["parser"] == parser and r["split"] == split_val)
            else:
                m = compute_metrics(records, lambda r: r["parser"] == parser)

            print(f"[{split_label}] (N={m['total']}):")
            print(f"  Parse Coverage:       {m['parsed']}/{m['total']} ({m['coverage_pct']:.1f}%)")
            print(f"  Constraint Equiv:     {m['equiv_count']}/{m['total']} ({m['equiv_pct_of_total']:.1f}% total, {m['equiv_pct_of_parsed']:.1f}% of parsed)")
            print(f"  Overall Accuracy:     {m['correct']}/{m['total']} ({m['overall_acc_pct']:.1f}%)")
            print(f"  Accuracy on Parsed:   {m['correct']}/{m['parsed'] if m['parsed'] > 0 else 1} ({m['parsed_acc_pct']:.1f}%)")

        print("\nBreakdown by Variant Type:")
        for vtype in ["baseline", "lexical_permutation", "natural_prose"]:
            m_v = compute_metrics(records, lambda r: r["parser"] == parser and r["variant_type"] == vtype)
            print(f"  - {vtype:<20} Coverage: {m_v['coverage_pct']:5.1f}% | Overall Acc: {m_v['overall_acc_pct']:5.1f}%")

    print("\n" + "=" * 80)
    print("CPU LATENCY BENCHMARK (ms)")
    print("=" * 80)
    for parser in ["Baseline", "Extended"]:
        p_stat = stats(timings[parser]["parse_ms"])
        s_stat = stats(timings[parser]["solve_ms"])
        t_stat = stats(timings[parser]["total_ms"])
        print(f"Parser [{parser}]:")
        print(f"  Parse Time:  Mean={p_stat['mean']:.4f} ms | Median={p_stat['median']:.4f} ms | Min={p_stat['min']:.4f} ms | Max={p_stat['max']:.4f} ms")
        print(f"  Solve Time:  Mean={s_stat['mean']:.4f} ms | Median={s_stat['median']:.4f} ms | Min={s_stat['min']:.4f} ms | Max={s_stat['max']:.4f} ms")
        print(f"  Total Time:  Mean={t_stat['mean']:.4f} ms | Median={t_stat['median']:.4f} ms | Min={t_stat['min']:.4f} ms | Max={t_stat['max']:.4f} ms")

    print("\n" + "=" * 80)
    print("FAILURE CASE AUDIT & TAXONOMY (Extended Parser on Held-out Dev)")
    print("=" * 80)
    heldout_failures = [
        r for r in records
        if r["parser"] == "Extended" and r["split"] == "heldout_dev" and not r["parsed"]
    ]
    for i, fcase in enumerate(heldout_failures, 1):
        print(f"Failure #{i}: ID={fcase['item_id']} | Type={fcase['variant_type']}")
        print(f"  Query: \"{fcase['query']}\"")
        diag = fcase["diagnosis"] or {}
        print(f"  Failure Stage: {diag.get('stage')}")
        print(f"  Diagnostic:    {diag.get('reason')}")
        print()
