import math
from types import SimpleNamespace
import pytest

from rat.engine.adaptive_reranker import AdaptiveE2Reranker
from rat.engine.context_parser import ContextParser


def test_e2_feature_invariant_and_clamping():
    reranker = AdaptiveE2Reranker()
    context = ContextParser.parse_query("slides calculus")

    doc = {
        "file_name": "slides.pptx",
        "file_ext": ".pptx",
        "content_text": "VRPTW research content without any math",
        "modified_at": 100.0,
        "vector_similarity": 0.20,
    }

    score, reasons = reranker.compute_heuristic_score(doc, context)
    assert 5.0 <= score <= 100.0
    assert abs(5.0 + sum(doc["_feats"].values()) - doc["_raw_score"]) < 1e-9
    assert doc["_ranker_version"] == "adaptive_e2"
    assert len(doc["_feats"]) == 20


def test_e2_prevents_format_stem_hijacking():
    reranker = AdaptiveE2Reranker()
    context = ContextParser.parse_query("slides calculus")

    # Off-topic file named slides.pptx (content is VRPTW)
    off_topic_doc = {
        "file_name": "slides.pptx",
        "file_ext": ".pptx",
        "content_text": "Student research conference on vehicle routing problems",
        "modified_at": 100.0,
        "vector_similarity": 0.15,
    }

    # On-topic file: MA1521Chap2.pdf (Calculus lecture notes)
    on_topic_doc = {
        "file_name": "MA1521Chap2.pdf",
        "file_ext": ".pdf",
        "content_text": "MA1521 Calculus for Computing Chapter 2 Derivatives with Applications",
        "modified_at": 100.0,
        "vector_similarity": 0.65,
    }

    score_off, _ = reranker.compute_heuristic_score(off_topic_doc, context)
    score_on, _ = reranker.compute_heuristic_score(on_topic_doc, context)

    # In E2, on-topic lecture notes must score HIGHER than the off-topic file named slides.pptx!
    assert score_on > score_off, f"Expected on-topic {score_on} > off-topic {score_off}"


def test_e2_full_bonus_when_both_topic_and_format_match():
    reranker = AdaptiveE2Reranker()
    context = ContextParser.parse_query("slides vrptw")

    doc = {
        "file_name": "Trình Bày Slides VRPTW Light Mode Comprehensive.pptx",
        "file_ext": ".pptx",
        "content_text": "Vehicle Routing Problem with Time Windows ALNS and Double DQN",
        "modified_at": 100.0,
        "vector_similarity": 0.85,
    }

    score, reasons = reranker.compute_heuristic_score(doc, context)
    assert score > 80.0
    assert doc["_feats"]["kw_word"] > 50.0  # VRPTW in name
