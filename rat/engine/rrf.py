"""
rat.engine.rrf — Reciprocal Rank Fusion (RRF) for true hybrid retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("rat.rrf")


class ReciprocalRankFusion:
    """
    Combines ranked candidate lists from Sparse Search (BM25 / FTS5)
    and Dense Search (Vector Embeddings) into a unified, high-precision score.
    """

    def __init__(self, k: int = 60, sparse_weight: float = 1.0, dense_weight: float = 1.2) -> None:
        self.k = k
        self.sparse_weight = sparse_weight
        self.dense_weight = dense_weight

    def fuse(
        self,
        sparse_candidates: List[Dict[str, Any]],
        dense_chunk_candidates: List[Dict[str, Any]],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Execute RRF fusion and aggregate chunk scores into parent documents.
        """
        # Map of {file_path: merged_document_record}
        doc_map: Dict[str, Dict[str, Any]] = {}
        rrf_scores: Dict[str, float] = {}
        best_chunks: Dict[str, Dict[str, Any]] = {}

        # 1. Process Sparse Ranks (FTS5 / BM25)
        for rank_idx, doc in enumerate(sparse_candidates):
            path = doc["file_path"]
            if path not in doc_map:
                doc_map[path] = dict(doc)
                rrf_scores[path] = 0.0

            # RRF Formula
            contribution = self.sparse_weight / (self.k + (rank_idx + 1))
            rrf_scores[path] += contribution
            doc_map[path]["matched_sparse"] = True
            doc_map[path]["sparse_rank"] = rank_idx + 1

        # 2. Process Dense Chunk Ranks (Cosine Similarity)
        for rank_idx, chunk in enumerate(dense_chunk_candidates):
            path = chunk["file_path"]
            if path not in doc_map:
                doc_map[path] = {
                    "id": chunk.get("doc_id"),
                    "file_path": path,
                    "file_name": chunk.get("file_name", ""),
                    "file_ext": chunk.get("file_ext", ""),
                    "file_size": chunk.get("file_size", 0),
                    "created_at": chunk.get("created_at", 0),
                    "modified_at": chunk.get("modified_at", 0),
                    "content_text": chunk.get("chunk_text", ""),
                    "summary": "",
                }
                rrf_scores[path] = 0.0

            contribution = self.dense_weight / (self.k + (rank_idx + 1))
            rrf_scores[path] += contribution
            doc_map[path]["matched_dense"] = True
            doc_map[path]["dense_rank"] = min(doc_map[path].get("dense_rank", 999), rank_idx + 1)

            # Track best semantic chunk for this document
            if path not in best_chunks or chunk["similarity_score"] > best_chunks[path]["similarity_score"]:
                best_chunks[path] = chunk

        # 3. Compile and normalize final results
        if not rrf_scores:
            return []

        # Find maximum theoretical RRF score to normalize to 0..100
        max_possible_rrf = (self.sparse_weight / (self.k + 1)) + (self.dense_weight / (self.k + 1))

        fused_results: List[Dict[str, Any]] = []
        for path, rrf_score in rrf_scores.items():
            doc = doc_map[path]
            normalized_score = min(100.0, (rrf_score / max_possible_rrf) * 100.0)

            # Attach best chunk snippet if available
            if path in best_chunks:
                b_chunk = best_chunks[path]
                doc["best_chunk_text"] = b_chunk.get("chunk_text", "")
                doc["best_chunk_index"] = b_chunk.get("chunk_index", 0)
                doc["vector_similarity"] = b_chunk.get("similarity_score", 0.0)

            doc["rrf_score"] = round(rrf_score, 5)
            doc["final_score"] = round(normalized_score, 1)
            fused_results.append(doc)

        # Sort descending by RRF score
        fused_results.sort(key=lambda x: x["final_score"], reverse=True)
        return fused_results[:top_k]


# Global RRF instance
rrf_fuser = ReciprocalRankFusion()
