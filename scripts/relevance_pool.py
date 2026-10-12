"""
scripts/relevance_pool.py — Candidate pooling across multiple retrievers & IR relevance metrics.

Supports:
1. Multi-retriever candidate extraction (BM25, Lexical Sparse, Vector/Dense, Hybrid RRF + Reranker).
2. Content/Path-based candidate pooling and deduplication for multi-file relevance evaluation.
3. Information Retrieval (IR) evaluation metrics:
   - Precision@K (P@1, P@3, P@5)
   - Recall@K (R@5, R@10)
   - nDCG@K (nDCG@5, nDCG@10) with graded relevance support (2^rel - 1)
   - Mean Reciprocal Rank (MRR)
   - Mean Average Precision (MAP)
4. Strict read-only database access, zero LLM calls, fail-closed embeddings.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_EVAL_QUERIES = [
    "slides vrptw",
    "slides giải tích",
    "slides calculus",
    "kế hoạch",
    "báo cáo pdf",
    "machine learning",
    "quy chế đào tạo",
    "lịch học",
    "học phí",
    "đồ án",
]


# ==============================================================================
# 1. Information Retrieval (IR) Evaluation Metrics
# ==============================================================================

def precision_at_k(ranked_paths: List[str], ground_truth: Dict[str, int], k: int = 5) -> float:
    """Compute Precision@K."""
    if k <= 0:
        return 0.0
    top_k = ranked_paths[:k]
    if not top_k:
        return 0.0
    relevant_count = sum(1 for path in top_k if ground_truth.get(path, 0) > 0)
    return relevant_count / k


def recall_at_k(ranked_paths: List[str], ground_truth: Dict[str, int], k: int = 10) -> float:
    """Compute Recall@K given total relevant items in ground truth."""
    total_relevant = sum(1 for grade in ground_truth.values() if grade > 0)
    if total_relevant == 0:
        return 1.0  # Vacuously true if there are no relevant items
    top_k = ranked_paths[:k]
    relevant_retrieved = sum(1 for path in top_k if ground_truth.get(path, 0) > 0)
    return relevant_retrieved / total_relevant


def dcg_at_k(ranked_paths: List[str], ground_truth: Dict[str, int], k: int = 10) -> float:
    """Compute Discounted Cumulative Gain at K with exponential gain (2^rel - 1)."""
    dcg = 0.0
    for rank_idx, path in enumerate(ranked_paths[:k]):
        grade = ground_truth.get(path, 0)
        gain = (2.0 ** grade) - 1.0
        discount = math.log2(rank_idx + 2)  # rank 1 has discount log2(2) = 1
        dcg += gain / discount
    return dcg


def ndcg_at_k(ranked_paths: List[str], ground_truth: Dict[str, int], k: int = 10) -> float:
    """Compute Normalized Discounted Cumulative Gain at K."""
    actual_dcg = dcg_at_k(ranked_paths, ground_truth, k)
    if actual_dcg <= 0.0:
        return 0.0
    # Ideal DCG: sort ground truth grades descending
    ideal_grades = sorted([g for g in ground_truth.values() if g > 0], reverse=True)[:k]
    if not ideal_grades:
        return 0.0
    idcg = sum(((2.0 ** g) - 1.0) / math.log2(idx + 2) for idx, g in enumerate(ideal_grades))
    return actual_dcg / idcg if idcg > 0 else 0.0


def reciprocal_rank(ranked_paths: List[str], ground_truth: Dict[str, int]) -> float:
    """Compute Reciprocal Rank (1 / rank of first relevant item)."""
    for rank_idx, path in enumerate(ranked_paths):
        if ground_truth.get(path, 0) > 0:
            return 1.0 / (rank_idx + 1)
    return 0.0


def average_precision(ranked_paths: List[str], ground_truth: Dict[str, int]) -> float:
    """Compute Average Precision (AP) for a single query."""
    total_relevant = sum(1 for grade in ground_truth.values() if grade > 0)
    if total_relevant == 0:
        return 0.0
    running_relevant = 0
    score_sum = 0.0
    for rank_idx, path in enumerate(ranked_paths):
        if ground_truth.get(path, 0) > 0:
            running_relevant += 1
            precision = running_relevant / (rank_idx + 1)
            score_sum += precision
    return score_sum / total_relevant


def evaluate_retrievers(
    eval_dataset: Dict[str, Any]
) -> Dict[str, Dict[str, float]]:
    """
    Compute aggregate IR metrics across all queries for each retriever in the dataset.
    Returns:
        {
            retriever_name: {
                "P@1": float, "P@3": float, "P@5": float,
                "R@5": float, "R@10": float,
                "nDCG@5": float, "nDCG@10": float,
                "MRR": float, "MAP": float
            }
        }
    """
    queries_data = eval_dataset.get("queries", {})
    if not queries_data:
        return {}

    # Identify all available retrievers
    all_retrievers: Set[str] = set()
    for q_entry in queries_data.values():
        all_retrievers.update(q_entry.get("retrievers", {}).keys())

    metrics_by_retriever: Dict[str, Dict[str, List[float]]] = {
        r: {"P@1": [], "P@3": [], "P@5": [], "R@5": [], "R@10": [], "nDCG@5": [], "nDCG@10": [], "MRR": [], "MAP": []}
        for r in all_retrievers
    }

    for query_text, q_data in queries_data.items():
        ground_truth = q_data.get("ground_truth", {})
        # If ground_truth is not labeled, skip query for metric computation
        if not ground_truth or all(v == 0 for v in ground_truth.values()):
            continue

        for r_name in all_retrievers:
            ranked_results = q_data.get("retrievers", {}).get(r_name, [])
            ranked_paths = [
                item["file_path"] if isinstance(item, dict) else str(item)
                for item in ranked_results
            ]
            m = metrics_by_retriever[r_name]
            m["P@1"].append(precision_at_k(ranked_paths, ground_truth, 1))
            m["P@3"].append(precision_at_k(ranked_paths, ground_truth, 3))
            m["P@5"].append(precision_at_k(ranked_paths, ground_truth, 5))
            m["R@5"].append(recall_at_k(ranked_paths, ground_truth, 5))
            m["R@10"].append(recall_at_k(ranked_paths, ground_truth, 10))
            m["nDCG@5"].append(ndcg_at_k(ranked_paths, ground_truth, 5))
            m["nDCG@10"].append(ndcg_at_k(ranked_paths, ground_truth, 10))
            m["MRR"].append(reciprocal_rank(ranked_paths, ground_truth))
            m["MAP"].append(average_precision(ranked_paths, ground_truth))

    summary: Dict[str, Dict[str, float]] = {}
    for r_name, metric_dict in metrics_by_retriever.items():
        summary[r_name] = {
            metric_name: float(np.mean(values)) if values else 0.0
            for metric_name, values in metric_dict.items()
        }
        summary[r_name]["judged_queries"] = len(metric_dict["P@1"])

    return summary


# ==============================================================================
# 2. Candidate Pooling Engine
# ==============================================================================

def execute_bm25_stream(database: Any, plan: Any, filters: Dict[str, Any], limit: int = 30) -> List[Dict[str, Any]]:
    """Query pure FTS5 BM25 matches."""
    from rat.crawler.db import build_fts_query
    fts_query = build_fts_query(plan.lexical_keywords)
    if not fts_query:
        return []

    conditions = ["documents_fts MATCH ?"]
    parameters: List[Any] = [fts_query]
    for name, operator, values in (
        ("file_ext", "IN", plan.extensions),
        ("file_ext", "NOT IN", plan.excluded_extensions),
    ):
        if values:
            conditions.append(f"d.{name} {operator} ({','.join('?' for _ in values)})")
            parameters.extend(value.lower() for value in values)

    for name, operator in (("date_min", ">="), ("date_max", "<=")):
        if filters.get(name) is not None:
            conditions.append(f"d.modified_at {operator} ?")
            parameters.append(filters[name])

    query_sql = (
        "SELECT d.id, d.file_path, d.file_name, d.file_ext, d.file_size, "
        "d.created_at, d.modified_at, d.content_text, d.summary, "
        "bm25(documents_fts, 15.0, 1.0, 1.0) AS rank "
        "FROM documents_fts JOIN documents d ON documents_fts.rowid=d.id WHERE "
        + " AND ".join(conditions)
        + f" ORDER BY rank ASC LIMIT {int(limit)}"
    )

    rows = database.get_connection().execute(query_sql, parameters).fetchall()
    return [dict(row) for row in rows]


def build_candidate_pool_for_query(
    query: str,
    database: Any,
    vectors: Any,
    encoder: Any,
    fuser: Any,
    reranker: Any,
    top_k: int = 15,
) -> Dict[str, Any]:
    """Execute all retrievers for a single query and construct a pooled candidate list."""
    from rat.engine.context_parser import ContextParser
    from rat.engine.embedder import DEFAULT_EMBED_MODEL
    from rat.engine.multi_way_rrf import FacetResult
    from rat.engine.query_decomposer import query_decomposer
    from fastembed import TextEmbedding

    plan = query_decomposer.decompose(query, allow_slm=False)
    context = ContextParser.parse_query(query)
    context.source_app = plan.source_app
    context.source_domain = plan.source_domain
    context.visual_concepts = plan.visual_tags

    filters = dict(
        extensions=plan.extensions or None,
        date_min=plan.date_min - 15 * 86400 if plan.date_min is not None else None,
        date_max=plan.date_max + 15 * 86400 if plan.date_max is not None else None,
    )

    # 1. BM25 Stream
    bm25_raw = execute_bm25_stream(database, plan, filters, limit=top_k * 2)

    # 2. Lexical Sparse Stream (includes fallback like / substring)
    lexical_raw = database.search_candidates(
        keywords=plan.lexical_keywords,
        excluded_extensions=plan.excluded_extensions or None,
        limit=top_k * 2,
        **filters,
    )

    # 3. Vector / Dense Stream
    if encoder._model is None:
        encoder._model = TextEmbedding(model_name=DEFAULT_EMBED_MODEL, local_files_only=True)
    embed_target = plan.semantic_text or query
    matrix = np.asarray(list(encoder._model.embed([embed_target])), dtype=np.float32)
    if matrix.shape != (1, 384) or not np.isfinite(matrix).all():
        raise RuntimeError(f"Invalid query embedding generated for {query!r}")
    norm = float(np.linalg.norm(matrix[0]))
    if norm <= 0:
        raise RuntimeError("Zero norm query embedding")
    query_vector = matrix[0] / norm

    dense_raw = vectors.search(
        query_vector,
        excluded_extensions=plan.excluded_extensions or None,
        limit=top_k * 2,
        **filters,
    )

    # 4. Hybrid Fusion + Heuristic Reranker
    streams = [
        FacetResult("lexical", lexical_raw, 1.0),
        FacetResult("semantic", dense_raw, 1.2, is_chunk_level=True),
    ]
    if "provenance" in plan.active_facets:
        prov = database.search_by_provenance(
            source_app=plan.source_app,
            source_domain=plan.source_domain,
            limit=top_k,
            **filters,
        )
        streams.append(FacetResult("provenance", prov, 1.5))
    if "visual" in plan.active_facets and plan.visual_tags:
        vis = database.search_by_vision_tags(tags=plan.visual_tags, limit=top_k, **filters)
        streams.append(FacetResult("visual", vis, 1.4))

    from rat.engine.adaptive_reranker import AdaptiveE2Reranker
    adaptive_reranker = AdaptiveE2Reranker()

    fused_candidates = fuser.fuse(streams, top_k=top_k * 2)
    hybrid_reranked = reranker.rerank(query, context, fused_candidates, top_k=top_k, use_llm=False)
    hybrid_e2_reranked = adaptive_reranker.rerank(query, context, fused_candidates, top_k=top_k, use_llm=False)

    # Extract ranked paths per retriever
    def extract_ranked_info(items: List[Any]) -> List[Dict[str, Any]]:
        extracted = []
        for rank, item in enumerate(items, 1):
            if hasattr(item, "file_path"):  # SearchResultItem
                extracted.append({
                    "rank": rank,
                    "file_path": item.file_path,
                    "file_name": item.file_name,
                    "score": getattr(item, "score", 0.0),
                    "snippet": getattr(item, "snippet", ""),
                })
            elif isinstance(item, dict):
                extracted.append({
                    "rank": rank,
                    "file_path": item.get("file_path", ""),
                    "file_name": item.get("file_name", Path(item.get("file_path", "")).name),
                    "score": item.get("rank") or item.get("score") or item.get("vector_similarity", 0.0),
                    "snippet": (item.get("content_text") or "")[:200],
                })
        return extracted

    retrievers_ranked = {
        "bm25": extract_ranked_info(bm25_raw[:top_k]),
        "lexical": extract_ranked_info(lexical_raw[:top_k]),
        "dense": extract_ranked_info(dense_raw[:top_k]),
        "hybrid_rrf_v1": extract_ranked_info(hybrid_reranked[:top_k]),
        "hybrid_e2": extract_ranked_info(hybrid_e2_reranked[:top_k]),
    }

    # Pool candidate documents across all streams
    candidate_map: Dict[str, Dict[str, Any]] = {}

    for r_name, ranked_list in retrievers_ranked.items():
        for item in ranked_list:
            path = item["file_path"]
            if not path:
                continue
            if path not in candidate_map:
                candidate_map[path] = {
                    "file_path": path,
                    "file_name": item["file_name"],
                    "retrievers": {},
                    "snippet": item.get("snippet", ""),
                    "relevance_judgment": 0,  # Default unjudged (0=irrelevant, 1=marginal, 2=relevant, 3=perfect)
                }
            candidate_map[path]["retrievers"][r_name] = {
                "rank": item["rank"],
                "score": item["score"],
            }

    return {
        "query": query,
        "retrievers": retrievers_ranked,
        "candidate_pool": list(candidate_map.values()),
        "total_unique_candidates": len(candidate_map),
        "ground_truth": {},  # Will hold path -> grade mapping once labeled
    }


def generate_pool_dataset(
    db_path: str,
    queries: List[str],
    top_k: int = 15,
) -> Dict[str, Any]:
    """Build candidate pools for all queries against a read-only database."""
    from rat.crawler.db import Database
    from rat.engine.embedder import LocalEmbedder
    from rat.engine.vector_cache import VectorCache
    from rat.engine.multi_way_rrf import MultiWayRRF
    from rat.engine.reranker import Reranker

    db = Database(db_path, read_only=True)
    encoder = LocalEmbedder()
    vectors = VectorCache(db)
    fuser = MultiWayRRF()
    reranker = Reranker()

    # Preload vectors safely
    vectors.preload()

    dataset: Dict[str, Any] = {
        "metadata": {
            "db_path": str(Path(db_path).resolve()),
            "total_queries": len(queries),
            "top_k_per_stream": top_k,
            "generated_at": str(np.datetime64("now")),
        },
        "queries": {},
    }

    for query in queries:
        query_entry = build_candidate_pool_for_query(
            query=query,
            database=db,
            vectors=vectors,
            encoder=encoder,
            fuser=fuser,
            reranker=reranker,
            top_k=top_k,
        )
        dataset["queries"][query] = query_entry

    return dataset


# ==============================================================================
# 3. CLI & Formatting
# ==============================================================================

def print_metrics_table(metrics_summary: Dict[str, Dict[str, float]]) -> None:
    """Print a clean Markdown table comparing all retrieval methods."""
    headers = ["Retriever", "P@1", "P@3", "P@5", "R@5", "R@10", "nDCG@5", "nDCG@10", "MRR", "MAP", "Judged Qs"]
    rows = []
    for r_name, scores in metrics_summary.items():
        rows.append([
            r_name,
            f"{scores.get('P@1', 0.0):.3f}",
            f"{scores.get('P@3', 0.0):.3f}",
            f"{scores.get('P@5', 0.0):.3f}",
            f"{scores.get('R@5', 0.0):.3f}",
            f"{scores.get('R@10', 0.0):.3f}",
            f"{scores.get('nDCG@5', 0.0):.3f}",
            f"{scores.get('nDCG@10', 0.0):.3f}",
            f"{scores.get('MRR', 0.0):.3f}",
            f"{scores.get('MAP', 0.0):.3f}",
            str(scores.get("judged_queries", 0)),
        ])

    col_widths = [max(len(str(item)) for item in col) for col in zip(headers, *rows)]
    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "-|-".join("-" * col_widths[i] for i in range(len(headers)))
    print("\n" + header_line)
    print(separator)
    for row in rows:
        print(" | ".join(str(item).ljust(col_widths[i]) for i, item in enumerate(row)))
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(Path.home() / ".rat" / "rat_index.db"), help="Path to SQLite index (read-only)")
    parser.add_argument("--queries", nargs="*", default=DEFAULT_EVAL_QUERIES, help="List of query strings to pool")
    parser.add_argument("--queries-file", help="Optional JSON file containing a list of query strings")
    parser.add_argument("--top-k", type=int, default=15, help="Candidates to fetch per retriever stream")
    parser.add_argument("--output", help="Optional output JSON path for the candidate pool")
    parser.add_argument("--eval-dataset", help="Path to a labeled candidate pool JSON to evaluate IR metrics")

    args = parser.parse_args()

    if args.eval_dataset:
        data = json.loads(Path(args.eval_dataset).read_text())
        summary = evaluate_retrievers(data)
        print_metrics_table(summary)
        return 0

    queries = args.queries
    if args.queries_file:
        queries = json.loads(Path(args.queries_file).read_text())

    print(f"Building candidate pool for {len(queries)} queries on {args.db} (top_k={args.top_k})...")
    dataset = generate_pool_dataset(args.db, queries, top_k=args.top_k)

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False))
        print(f"Saved candidate pool dataset to {out_path}")
    else:
        # Print summary of pooled candidate counts
        print("\nCandidate Pool Summary:")
        for q_text, q_data in dataset["queries"].items():
            print(f"- Query: '{q_text}' -> {q_data['total_unique_candidates']} unique candidates across all retrievers")
            for r_name, r_items in q_data["retrievers"].items():
                top1_name = r_items[0]["file_name"] if r_items else "None"
                print(f"    * [{r_name:10s}] retrieved {len(r_items):2d} items (Top 1: {top1_name})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
