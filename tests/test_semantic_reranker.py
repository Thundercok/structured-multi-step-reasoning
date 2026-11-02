"""Tests for offline semantic and fuzzy reranker in rat/engine/semantic_reranker.py."""
import time
from pathlib import Path
import pytest

from rat.engine.semantic_reranker import (
    SemanticFuzzyReranker,
    char_trigrams,
    fold_ascii,
    trigram_similarity,
)


def test_fold_ascii():
    assert fold_ascii("Tối ưu hóa lựa chọn toán tử") == "toi uu hoa lua chon toan tu"
    assert fold_ascii("Đề án & Báo cáo 2026!") == "de an   bao cao 2026"
    assert fold_ascii("") == ""


def test_trigram_similarity():
    sim_exact = trigram_similarity("reinforcement", "reinforcement")
    assert sim_exact == 1.0

    # Typo: reinforment vs reinforcement
    sim_typo = trigram_similarity("reinforment", "reinforcement")
    assert sim_typo > 0.70

    # Distinct words
    sim_diff = trigram_similarity("calculus", "astrology")
    assert sim_diff < 0.15


def test_expand_query_topics():
    reranker = SemanticFuzzyReranker("/tmp/dummy.db")
    exp = reranker.expand_query_topics("bài toán vận tải giao hàng")
    assert any(k in exp for k in ("vrptw", "routing", "alns", "vehicle"))

    exp_rl = reranker.expand_query_topics("học tăng cường và mạng nơ ron")
    assert any(k in exp_rl for k in ("dqn", "double dqn", "reinforcement learning", "reward"))


def test_compute_fuzzy_score():
    reranker = SemanticFuzzyReranker("/tmp/dummy.db")
    score_on, reasons_on = reranker.compute_fuzzy_score(
        "lộ trình xe giao hàng",
        file_name="Optimizing_Operator_Selection_in_ALNS_for_VRPTW.pdf",
        summary="Nghiên cứu bài toán giao hàng VRPTW bằng giải thuật ALNS.",
        file_ext=".pdf",
        target_extensions=[".pdf"],
    )
    assert score_on > 20.0
    assert any("chủ đề" in r or "Tên" in r for r in reasons_on)

    score_off, _ = reranker.compute_fuzzy_score(
        "lộ trình xe giao hàng",
        file_name="Tarot_Spread_Guide.pdf",
        summary="Hướng dẫn trải bài tarot 3 lá.",
        file_ext=".pdf",
    )
    assert score_on > score_off


def test_reranker_real_db_latency():
    from rat.ui.quick_pdf_controller import QuickPDFController
    ctrl = QuickPDFController()
    db_path = ctrl._db_path
    if not Path(db_path).exists():
        pytest.skip("rat.db not found")

    reranker = SemanticFuzzyReranker(db_path)
    
    class DummyRequest:
        query = "bài toán vận tải và giao hàng"
        intent = None

    # First run (warmup)
    _ = list(reranker(DummyRequest()))

    # Second run (measured warm latency)
    t0 = time.perf_counter()
    candidates = list(reranker(DummyRequest()))
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"Semantic reranker warm elapsed: {elapsed_ms:.2f}ms, candidates: {len(candidates)}")
    assert elapsed_ms < 60.0, f"Reranker must complete in < 60ms, took {elapsed_ms:.2f}ms"
    assert len(candidates) > 0
    # Confirm VRPTW / ALNS / NAMI documents are among retrieved candidates
    joined = " ".join(candidates)
    assert "VRPTW" in joined or "ALNS" in joined or "NAMI" in joined
