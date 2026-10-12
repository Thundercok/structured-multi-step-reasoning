"""
scripts/label_pool.py — Assign ground-truth relevance judgments to the candidate pool.

Relevance Scale:
3 = Highly relevant / Exact target document (e.g., actual lecture slides / presentation deck on the query topic)
2 = Relevant / Substantive material on the topic (e.g., related slide deck, paper, code directly solving it)
1 = Marginally relevant (e.g., poster, assignment, related topic context)
0 = Irrelevant (e.g., survey xlsx, unrelated code, false lexical match)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict


def label_benchmark_queries(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Populate ground_truth mappings for key benchmark queries based on ground truth inspection."""
    queries = dataset.get("queries", {})

    # 1. slides vrptw
    if "slides vrptw" in queries:
        q = queries["slides vrptw"]
        gt = {}
        for c in q["candidate_pool"]:
            p = c["file_path"].lower()
            name = c["file_name"].lower()
            if "trình bày slides vrptw" in name or "tối ưu hóa alns bằng double dqn cho vrptw.pptx" in name or "hybrid ddqn-alns for vrptw-2.pptx" in name:
                gt[c["file_path"]] = 3
            elif name in ("slides.pptx", "slides_v2.pptx", "slides.html"):
                gt[c["file_path"]] = 2
            elif "poster_vrptw" in name or "poster" in name:
                gt[c["file_path"]] = 1
            elif "optimizing_operator_selection" in name or "phản biện học thuật" in name or "vrptw_v" in name:
                gt[c["file_path"]] = 1
            else:
                gt[c["file_path"]] = 0
        q["ground_truth"] = gt

    # 2. slides calculus
    if "slides calculus" in queries:
        q = queries["slides calculus"]
        gt = {}
        for c in q["candidate_pool"]:
            name = c["file_name"]
            if name.startswith("MA1521Chap") and name.endswith(".pdf"):
                gt[c["file_path"]] = 3  # Actual Calculus lecture slide chapters from NUS
            elif "[CALCULUS] Assignment" in name:
                gt[c["file_path"]] = 1  # Assignment, not lecture slides
            elif name in ("slides.pptx", "slides.html", "slides_v2.pptx"):
                # Note: These are VRPTW slides, NOT Calculus! They matched purely on the word 'slides'
                gt[c["file_path"]] = 0
            else:
                gt[c["file_path"]] = 0
        q["ground_truth"] = gt

    # 3. slides giải tích
    if "slides giải tích" in queries:
        q = queries["slides giải tích"]
        gt = {}
        for c in q["candidate_pool"]:
            name = c["file_name"]
            # Any MA1521 or calculus material in this candidate pool
            if name.startswith("MA1521Chap"):
                gt[c["file_path"]] = 3
            elif "giai tich" in name.lower() or "giải tích" in name.lower():
                gt[c["file_path"]] = 3
            elif name in ("slides.pptx", "output_day_du_50_slides.pptx", "slides_v2.pptx"):
                # None of these are Giải Tích slides (they are VRPTW or Sociology)
                gt[c["file_path"]] = 0
            else:
                gt[c["file_path"]] = 0
        q["ground_truth"] = gt

    # 4. kế hoạch
    if "kế hoạch" in queries:
        q = queries["kế hoạch"]
        gt = {}
        for c in q["candidate_pool"]:
            name = c["file_name"].lower()
            if "kế hoạch" in name:
                gt[c["file_path"]] = 3
            elif "roadmap" in name or "plan" in name:
                gt[c["file_path"]] = 2
            elif "estimated" in name:
                gt[c["file_path"]] = 1
            else:
                gt[c["file_path"]] = 0
        q["ground_truth"] = gt

    # 5. machine learning
    if "machine learning" in queries:
        q = queries["machine learning"]
        gt = {}
        for c in q["candidate_pool"]:
            name = c["file_name"].lower()
            if "interpretable_machine_learning_book.pdf" in name:
                gt[c["file_path"]] = 3
            elif "lecture - svm" in name or "lecture 3b" in name:
                gt[c["file_path"]] = 3
            elif "hierarchical_reinforcement_learning" in name:
                gt[c["file_path"]] = 2
            elif "labs_learningsummaryreport" in name:
                gt[c["file_path"]] = 1
            else:
                gt[c["file_path"]] = 0
        q["ground_truth"] = gt

    # 6. báo cáo pdf
    if "báo cáo pdf" in queries:
        q = queries["báo cáo pdf"]
        gt = {}
        for c in q["candidate_pool"]:
            name = c["file_name"].lower()
            ext = c["file_name"].lower().split(".")[-1]
            if ext == "pdf" and ("báo cáo" in name or "phản biện" in name or "report" in name or "paper" in name):
                gt[c["file_path"]] = 3
            elif ext == "pdf":
                gt[c["file_path"]] = 1
            else:
                gt[c["file_path"]] = 0
        q["ground_truth"] = gt

    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-file", default="outputs/candidate_pool.json", help="Path to candidate pool JSON")
    parser.add_argument("--output", help="Output path (default overwrites pool-file)")
    args = parser.parse_args()

    pool_path = Path(args.pool_file).resolve()
    if not pool_path.exists():
        print(f"Error: {pool_path} does not exist", file=sys.stderr)
        return 1

    data = json.loads(pool_path.read_text())
    labeled = label_benchmark_queries(data)

    out_path = Path(args.output).resolve() if args.output else pool_path
    out_path.write_text(json.dumps(labeled, indent=2, ensure_ascii=False))
    print(f"Labeled ground truth for benchmark queries in {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
