"""
tests/test_benchmark_reasoning.py — Tests for Academic Benchmark Pipeline.
Validates dataset integrity, simulator stability, strategy evaluation,
and LaTeX / Markdown export validity.
"""

import os
import unittest
from pathlib import Path

import numpy as np

from experiments.benchmark_reasoning import (
    ACADEMIC_BENCHMARK_ITEMS,
    CalibratedReasoningBackend,
    eval_direct,
    get_expanded_benchmark,
    summarize_method_results,
)
from reasoning_env import ReasoningAction as A


class TestBenchmarkReasoning(unittest.TestCase):
    def setUp(self):
        self.dataset = get_expanded_benchmark()
        self.gt_map = {item["query"]: item["ground_truth"] for item in self.dataset}
        self.backend = CalibratedReasoningBackend(self.gt_map, seed=123)

    def test_benchmark_dataset_loaded(self):
        self.assertGreaterEqual(len(self.dataset), 40)
        for item in self.dataset:
            self.assertIn("query", item)
            self.assertIn("ground_truth", item)
            self.assertIn("target_type", item)

    def test_calibrated_backend_embed_and_run(self):
        q = "Sinh viên tích lũy 64 tín chỉ có CPA 7.20"
        emb = self.backend.embed(q)
        self.assertEqual(emb.shape, (128,))
        self.assertAlmostEqual(float(np.linalg.norm(emb)), 1.0, places=4)

        ans, conf, tok = self.backend.run(A.COT, q)
        self.assertIsInstance(ans, str)
        self.assertTrue(0.0 <= conf <= 1.0)
        self.assertGreater(tok, 0)

    def test_summarize_results_computation(self):
        results = eval_direct(self.dataset[:10], self.backend)
        summary = summarize_method_results(results, baseline_cot_tokens=300.0)
        self.assertEqual(summary["method"], "Direct (Zero-Shot)")
        self.assertTrue(0.0 <= summary["accuracy"] <= 100.0)
        self.assertGreater(summary["mean_tokens"], 0)
        self.assertGreater(summary["efficiency"], 0)

    def test_latex_and_markdown_exports_exist(self):
        docs_dir = Path(__file__).resolve().parent.parent / "docs"
        tex_path = docs_dir / "reasoning_benchmark_table.tex"
        md_path = docs_dir / "reasoning_benchmark_results.md"
        self.assertTrue(tex_path.exists())
        self.assertTrue(md_path.exists())
        with open(tex_path, "r", encoding="utf-8") as f:
            tex = f.read()
            self.assertIn(r"\begin{table*}", tex)
            self.assertIn("Wilcoxon", tex)
        with open(md_path, "r", encoding="utf-8") as f:
            md = f.read()
            self.assertIn("Pareto", md)


if __name__ == "__main__":
    import numpy as np
    unittest.main()
