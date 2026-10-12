import math
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

from scripts.relevance_pool import (
    precision_at_k,
    recall_at_k,
    dcg_at_k,
    ndcg_at_k,
    reciprocal_rank,
    average_precision,
    evaluate_retrievers,
    build_candidate_pool_for_query,
)


def test_precision_and_recall_at_k():
    ground_truth = {
        "/path/doc1.pdf": 1,
        "/path/doc2.pdf": 2,
        "/path/doc3.pdf": 1,
        "/path/doc4.pdf": 0,
    }
    ranked = ["/path/doc1.pdf", "/path/doc4.pdf", "/path/doc2.pdf", "/path/doc5.pdf", "/path/doc6.pdf"]

    assert precision_at_k(ranked, ground_truth, k=1) == 1.0
    assert precision_at_k(ranked, ground_truth, k=2) == 0.5
    assert precision_at_k(ranked, ground_truth, k=3) == 2 / 3
    assert precision_at_k(ranked, ground_truth, k=5) == 2 / 5

    # Total relevant = 3 (doc1, doc2, doc3)
    assert recall_at_k(ranked, ground_truth, k=1) == 1 / 3
    assert recall_at_k(ranked, ground_truth, k=3) == 2 / 3
    assert recall_at_k(ranked, ground_truth, k=5) == 2 / 3

    # Edge cases
    assert precision_at_k([], ground_truth, k=5) == 0.0
    assert recall_at_k([], ground_truth, k=5) == 0.0
    assert recall_at_k(ranked, {}, k=5) == 1.0


def test_ndcg_graded_relevance():
    ground_truth = {
        "A": 3,
        "B": 2,
        "C": 1,
        "D": 0,
    }

    # Ideal order: A (3), B (2), C (1)
    ideal_ranked = ["A", "B", "C"]
    assert math.isclose(ndcg_at_k(ideal_ranked, ground_truth, k=3), 1.0, rel_tol=1e-5)

    # Reversed order: C (1), B (2), A (3)
    reversed_ranked = ["C", "B", "A"]
    dcg_ideal = ((2**3 - 1) / math.log2(2)) + ((2**2 - 1) / math.log2(3)) + ((2**1 - 1) / math.log2(4))
    dcg_rev = ((2**1 - 1) / math.log2(2)) + ((2**2 - 1) / math.log2(3)) + ((2**3 - 1) / math.log2(4))
    expected_ndcg = dcg_rev / dcg_ideal

    assert math.isclose(ndcg_at_k(reversed_ranked, ground_truth, k=3), expected_ndcg, rel_tol=1e-5)

    # Empty / completely irrelevant
    assert ndcg_at_k(["D", "E"], ground_truth, k=2) == 0.0
    assert ndcg_at_k([], ground_truth, k=5) == 0.0


def test_reciprocal_rank_and_average_precision():
    ground_truth = {
        "docA": 1,
        "docB": 1,
    }

    # First relevant at rank 2
    ranked1 = ["docX", "docA", "docY", "docB"]
    assert reciprocal_rank(ranked1, ground_truth) == 0.5
    # AP: docA at rank 2 (P=1/2), docB at rank 4 (P=2/4). Total relevant=2 -> AP = (0.5 + 0.5)/2 = 0.5
    assert average_precision(ranked1, ground_truth) == 0.5

    # First relevant at rank 1
    ranked2 = ["docA", "docB", "docX"]
    assert reciprocal_rank(ranked2, ground_truth) == 1.0
    # AP: docA at rank 1 (P=1/1), docB at rank 2 (P=2/2). AP = (1.0 + 1.0)/2 = 1.0
    assert average_precision(ranked2, ground_truth) == 1.0

    # No relevant items retrieved
    assert reciprocal_rank(["docX", "docY"], ground_truth) == 0.0
    assert average_precision(["docX", "docY"], ground_truth) == 0.0


def test_evaluate_retrievers_aggregation():
    dataset = {
        "queries": {
            "query 1": {
                "ground_truth": {"docA": 2, "docB": 1},
                "retrievers": {
                    "bm25": [{"file_path": "docA"}, {"file_path": "docX"}],
                    "vector": [{"file_path": "docX"}, {"file_path": "docA"}],
                }
            },
            "query 2": {
                "ground_truth": {"docB": 1},
                "retrievers": {
                    "bm25": [{"file_path": "docB"}],
                    "vector": [{"file_path": "docB"}],
                }
            }
        }
    }

    summary = evaluate_retrievers(dataset)
    assert "bm25" in summary
    assert "vector" in summary
    assert summary["bm25"]["judged_queries"] == 2
    assert summary["vector"]["judged_queries"] == 2

    # Query 1: bm25 P@1=1.0, Query 2: bm25 P@1=1.0 -> mean P@1 = 1.0
    assert summary["bm25"]["P@1"] == 1.0
    # Query 1: vector P@1=0.0, Query 2: vector P@1=1.0 -> mean P@1 = 0.5
    assert summary["vector"]["P@1"] == 0.5


def test_build_candidate_pool_for_query_mocked(tmp_path):
    # Setup a mock DB, VectorCache, Encoder, Fuser, Reranker
    mock_db = MagicMock()
    mock_db.search_candidates.return_value = [
        {"file_path": "/path/lexical1.pdf", "file_name": "lexical1.pdf", "score": 80.0, "content_text": "text1"}
    ]
    mock_db.get_connection.return_value.execute.return_value.fetchall.return_value = [
        {"id": 1, "file_path": "/path/bm25_1.pdf", "file_name": "bm25_1.pdf", "rank": -10.5, "content_text": "text2"}
    ]

    mock_vectors = MagicMock()
    mock_vectors.search.return_value = [
        {"file_path": "/path/dense1.pdf", "file_name": "dense1.pdf", "vector_similarity": 0.88, "content_text": "text3"}
    ]

    mock_encoder = MagicMock()
    mock_encoder._model.embed.return_value = [np.ones(384, dtype=np.float32)]

    mock_fuser = MagicMock()
    mock_fuser.fuse.return_value = [
        {"file_path": "/path/lexical1.pdf", "file_name": "lexical1.pdf"},
        {"file_path": "/path/dense1.pdf", "file_name": "dense1.pdf"},
    ]

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = [
        SimpleNamespace(file_path="/path/lexical1.pdf", file_name="lexical1.pdf", score=90.0, snippet="preview")
    ]

    res = build_candidate_pool_for_query(
        query="test query",
        database=mock_db,
        vectors=mock_vectors,
        encoder=mock_encoder,
        fuser=mock_fuser,
        reranker=mock_reranker,
        top_k=5,
    )

    assert res["query"] == "test query"
    assert "retrievers" in res
    assert "bm25" in res["retrievers"]
    assert "lexical" in res["retrievers"]
    assert "dense" in res["retrievers"]
    assert "hybrid_rrf_v1" in res["retrievers"]
    assert "hybrid_e2" in res["retrievers"]
    assert res["total_unique_candidates"] >= 3
