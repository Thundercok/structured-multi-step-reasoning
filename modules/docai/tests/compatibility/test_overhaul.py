"""
Unit Tests for Overhaul: ANLS & Real-World Dataset Loader
"""

import pytest
from nesy_docai import RealWorldDatasetLoader, InvoiceBenchmarkSuite


def test_anls_calculation():
    loader = RealWorldDatasetLoader()
    assert loader.calculate_anls("104500", "104500") == 1.0
    assert loader.calculate_anls("104500", "1045000") < 1.0
    assert loader.calculate_anls("apple", "banana") == 0.0


def test_cord_real_world_samples():
    loader = RealWorldDatasetLoader()
    samples = loader.load_cord_sample_benchmark()

    assert len(samples) >= 2
    assert samples[0]["source_dataset"].startswith("CORD")
    assert samples[1]["source_dataset"].startswith("MC-OCR")


def test_overhaul_benchmark_metrics():
    suite = InvoiceBenchmarkSuite()
    metrics = suite.run_full_evaluation(num_samples=20)

    assert "mean_anls_score" in metrics
    assert metrics["mean_anls_score"] == 1.0
    assert metrics["synthetic_example_total_accuracy"] == 100.0
    assert metrics["evidence_scope"] == "synthetic_smoke"
    assert metrics["ocr_executed"] is False
    assert metrics["pure_ocr_baseline_acc"] is None
    assert metrics["stp_rate"] is None
