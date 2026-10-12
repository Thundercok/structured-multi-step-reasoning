#!/usr/bin/env python3
"""
scripts/generate_showcase_benchmarks.py — SOTA Portability & Latency Benchmark Suite.
Compares RAT (FR-CoT & M-RRF) against macOS Spotlight (mdfind) and Ripgrep.
Generates publication-quality charts (PNG) and LaTeX tables.
"""

import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rat.config import config
from rat.crawler.db import Database
from rat.engine.embedder import embedder
from rat.engine.hybrid_search import SearchEngine
from rat.engine.vector_cache import vector_cache

DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def get_rss_mb() -> float:
    """Return memory usage in MB for current process."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss / (1024 * 1024) if sys.platform == "darwin" else usage.ru_maxrss / 1024


def benchmark_search_engine(queries: List[str], iterations: int = 15) -> Dict[str, Dict[str, float]]:
    print("🧠 Preloading RAT In-Memory Vector Cache...")
    t0 = time.time()
    vector_cache.preload()
    t_preload = time.time() - t0
    vector_count = vector_cache._matrix.shape[0] if vector_cache._matrix is not None else 0
    print(f"✅ Loaded {vector_count} vectors into RAM in {t_preload*1000:.1f}ms")

    engine = SearchEngine()
    db = Database(config.db_path)

    results = {
        "rat_vector_only": [],
        "rat_bm25_only": [],
        "rat_hybrid_rrf": [],
        "ripgrep": [],
        "spotlight": []
    }

    # Warmup
    engine.search("báo cáo tài chính", limit=10)

    test_dirs = [d for d in config.indexed_directories if os.path.exists(d)]
    search_root = test_dirs[0] if test_dirs else str(Path.home() / "Documents")

    print(f"⏱️ Running benchmark across {len(queries)} queries ({iterations} repetitions each)...")

    for q in queries:
        # 1. RAT Vector-only
        for _ in range(iterations):
            t_start = time.perf_counter()
            q_vec = embedder.embed_query(q)
            _ = vector_cache.search(q_vec, limit=15)
            results["rat_vector_only"].append((time.perf_counter() - t_start) * 1000)

        # 2. RAT BM25-only
        for _ in range(iterations):
            t_start = time.perf_counter()
            _ = db.search_candidates([q], limit=15)
            results["rat_bm25_only"].append((time.perf_counter() - t_start) * 1000)

        # 3. RAT Hybrid End-to-End
        for _ in range(iterations):
            t_start = time.perf_counter()
            _ = engine.search(q, limit=15)
            results["rat_hybrid_rrf"].append((time.perf_counter() - t_start) * 1000)

        # 4. Ripgrep
        for _ in range(iterations):
            t_start = time.perf_counter()
            try:
                subprocess.run(
                    ["rg", "-i", "-l", "--max-count=15", q, search_root],
                    capture_output=True,
                    timeout=2
                )
            except Exception:
                pass
            results["ripgrep"].append((time.perf_counter() - t_start) * 1000)

        # 5. macOS Spotlight (mdfind)
        for _ in range(iterations):
            t_start = time.perf_counter()
            try:
                subprocess.run(
                    ["mdfind", "-onlyin", search_root, q],
                    capture_output=True,
                    timeout=2
                )
            except Exception:
                pass
            results["spotlight"].append((time.perf_counter() - t_start) * 1000)

    # Compute percentiles
    summary = {}
    for name, latencies in results.items():
        arr = np.array(latencies)
        summary[name] = {
            "p50": float(np.percentile(arr, 50)),
            "p90": float(np.percentile(arr, 90)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "mean": float(np.mean(arr)),
        }

    return summary, vector_count


def generate_plot(summary: Dict[str, Dict[str, float]], vector_count: int) -> Path:
    import matplotlib.pyplot as plt

    methods = [
        ("rat_vector_only", "RAT Dense Vector\n(In-Memory Cache)", "#10b981"),
        ("rat_bm25_only", "RAT FTS5 BM25\n(SQLite WAL)", "#06b6d4"),
        ("rat_hybrid_rrf", "RAT M-RRF\n(End-to-End)", "#6366f1"),
        ("spotlight", "macOS Spotlight\n(mdfind CLI)", "#f59e0b"),
        ("ripgrep", "Ripgrep\n(rg CLI)", "#ef4444"),
    ]

    names = [m[1] for m in methods]
    colors = [m[2] for m in methods]
    p50_vals = [summary[m[0]]["p50"] for m in methods]
    p95_vals = [summary[m[0]]["p95"] for m in methods]

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

    x = np.arange(len(methods))
    width = 0.35

    rects1 = ax.bar(x - width/2, p50_vals, width, label="p50 (Median)", color=colors, alpha=0.85, edgecolor="none")
    rects2 = ax.bar(x + width/2, p95_vals, width, label="p95 (95th%)", color=colors, alpha=0.45, hatch="//", edgecolor="white", linewidth=0.5)

    ax.set_ylabel("Latency (Milliseconds - Log Scale)", fontsize=11, fontweight="bold", color="#e2e8f0")
    ax.set_title(f"Search Latency Comparison on Apple Silicon M1 (Corpus: {vector_count:,} Vectors)", fontsize=13, fontweight="bold", pad=15, color="#ffffff")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9.5, fontweight="medium", color="#cbd5e1")
    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.2, color="#94a3b8")
    ax.legend(frameon=True, facecolor="#1e293b", edgecolor="#334155", fontsize=10)

    # Value annotations on top of bars
    for i, rect in enumerate(rects1):
        h = rect.get_height()
        ax.annotate(f"{h:.1f}ms",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#f8fafc")

    plt.tight_layout()
    plot_path = DOCS_DIR / "benchmark_showcase.png"
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"📊 Saved benchmark chart: {plot_path}")
    return plot_path


def generate_latex_table(summary: Dict[str, Dict[str, float]], vector_count: int) -> Path:
    tex = f"""% Auto-generated by scripts/generate_showcase_benchmarks.py
\\begin{{table}}[htbp]
\\centering
\\caption{{Retrieval Latency Comparison on Apple Silicon M1 (Real Corpus: {vector_count:,} Embeddings)}}
\\label{{tab:retrieval_latency}}
\\begin{{tabular}}{{lrrrr}}
\\hline
\\textbf{{Method}} & \\textbf{{p50 (ms)}} & \\textbf{{p90 (ms)}} & \\textbf{{p95 (ms)}} & \\textbf{{p99 (ms)}} \\\\
\\hline
RAT Vector-Only (In-Memory) & {summary['rat_vector_only']['p50']:.2f} & {summary['rat_vector_only']['p90']:.2f} & {summary['rat_vector_only']['p95']:.2f} & {summary['rat_vector_only']['p99']:.2f} \\\\
RAT Lexical (SQLite FTS5)    & {summary['rat_bm25_only']['p50']:.2f} & {summary['rat_bm25_only']['p90']:.2f} & {summary['rat_bm25_only']['p95']:.2f} & {summary['rat_bm25_only']['p99']:.2f} \\\\
\\textbf{{RAT M-RRF Hybrid}} & \\textbf{{{summary['rat_hybrid_rrf']['p50']:.2f}}} & \\textbf{{{summary['rat_hybrid_rrf']['p90']:.2f}}} & \\textbf{{{summary['rat_hybrid_rrf']['p95']:.2f}}} & \\textbf{{{summary['rat_hybrid_rrf']['p99']:.2f}}} \\\\
macOS Spotlight (mdfind)     & {summary['spotlight']['p50']:.2f} & {summary['spotlight']['p90']:.2f} & {summary['spotlight']['p95']:.2f} & {summary['spotlight']['p99']:.2f} \\\\
Ripgrep (rg)                 & {summary['ripgrep']['p50']:.2f} & {summary['ripgrep']['p90']:.2f} & {summary['ripgrep']['p95']:.2f} & {summary['ripgrep']['p99']:.2f} \\\\
\\hline
\\end{{tabular}}
\\end{{table}}
"""
    tex_path = DOCS_DIR / "benchmark_table.tex"
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)
    print(f"📄 Saved LaTeX table: {tex_path}")
    return tex_path


def main():
    queries = [
        "báo cáo tài chính doanh thu",
        "thuật toán tối ưu hóa VRPTW",
        "hợp đồng chuyển khoản ngân hàng",
        "thời khóa biểu lịch học sinh viên",
        "deep learning neural network",
        "kế hoạch công việc quý 3"
    ]
    summary, count = benchmark_search_engine(queries, iterations=8)
    generate_plot(summary, count)
    generate_latex_table(summary, count)
    print("✅ Benchmark and reporting successfully generated!")


if __name__ == "__main__":
    main()
