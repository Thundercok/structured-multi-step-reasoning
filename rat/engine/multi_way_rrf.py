"""
rat.engine.multi_way_rrf — Adaptive Multi-Way Reciprocal Rank Fusion (M-RRF).
Fuses candidate streams across orthogonal OS facets:
M-RRF(d) = sum_{f in F_active} [w_f / (k + Rank_f(d))]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("rat.rrf")


@dataclass
class FacetResult:
    """Ranked candidate stream returned by an individual OS facet retriever."""
    facet_name: str         # "lexical" | "semantic" | "provenance" | "visual" | "temporal"
    candidates: List[Dict[str, Any]]
    weight: float = 1.0
    is_chunk_level: bool = False


class MultiWayRRF:
    """
    Generalized Reciprocal Rank Fusion across N arbitrary facet retrieval streams.
    Provides candidate deduplication, chunk-to-document rollup, and facet contribution tracking.
    """

    def __init__(self, k: int = 60) -> None:
        self.k = k

    def fuse(
        self,
        facet_streams: List[FacetResult],
        top_k: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Fuse multiple facet candidate streams into a single ranked candidate list.
        """
        if not facet_streams:
            return []

        doc_scores: Dict[str, float] = {}
        doc_data: Dict[str, Dict[str, Any]] = {}
        doc_facet_hits: Dict[str, Set[str]] = {}
        doc_facet_ranks: Dict[str, Dict[str, int]] = {}

        # Max theoretical score across all active streams (for 0-100 normalization)
        theoretical_max = sum(stream.weight / (self.k + 1) for stream in facet_streams if stream.candidates)
        if theoretical_max <= 0:
            theoretical_max = 1.0

        for stream in facet_streams:
            if not stream.candidates:
                continue

            seen_paths_in_stream: Set[str] = set()
            rank = 1

            for item in stream.candidates:
                path = item.get("file_path", "")
                if not path:
                    continue

                # If chunk-level (from dense vector cache), rollup to document
                if stream.is_chunk_level:
                    if path in seen_paths_in_stream:
                        # Update best chunk text or max similarity if applicable
                        if path in doc_data:
                            curr_sim = doc_data[path].get("vector_similarity", 0.0)
                            new_sim = item.get("similarity_score", 0.0)
                            if new_sim > curr_sim:
                                doc_data[path]["vector_similarity"] = new_sim
                                doc_data[path]["best_chunk_text"] = item.get("chunk_text", "")
                        continue

                seen_paths_in_stream.add(path)

                # RRF addition: w_f / (k + rank)
                rrf_increment = stream.weight / (self.k + rank)
                doc_scores[path] = doc_scores.get(path, 0.0) + rrf_increment

                # Record base document metadata
                if path not in doc_data:
                    doc_data[path] = {
                        "id": item.get("id", item.get("doc_id", 0)),
                        "file_path": path,
                        "file_name": item.get("file_name", ""),
                        "file_ext": item.get("file_ext", ""),
                        "file_size": item.get("file_size", 0),
                        "created_at": item.get("created_at", 0.0),
                        "modified_at": item.get("modified_at", 0.0),
                        "content_text": item.get("content_text", ""),
                        "summary": item.get("summary", ""),
                        "best_chunk_text": item.get("chunk_text", ""),
                        "vector_similarity": item.get("vector_similarity", item.get("similarity_score", 0.0)),
                        "bm25": item.get("bm25"),
                    }
                else:
                    # Enrich with content if missing
                    if not doc_data[path].get("content_text") and item.get("content_text"):
                        doc_data[path]["content_text"] = item["content_text"]
                    if stream.is_chunk_level and item.get("similarity_score", 0.0) > doc_data[path].get("vector_similarity", 0.0):
                        doc_data[path]["vector_similarity"] = item.get("similarity_score", 0.0)
                        doc_data[path]["best_chunk_text"] = item.get("chunk_text", "")

                # Track facet contribution
                if doc_data[path].get("bm25") is None and item.get("bm25") is not None:
                    doc_data[path]["bm25"] = item.get("bm25")
                if path not in doc_facet_hits:
                    doc_facet_hits[path] = set()
                    doc_facet_ranks[path] = {}

                doc_facet_hits[path].add(stream.facet_name)
                doc_facet_ranks[path][stream.facet_name] = rank
                rank += 1

        # Assemble and normalize
        fused_list: List[Dict[str, Any]] = []
        for path, score in doc_scores.items():
            entry = dict(doc_data[path])
            # Normalized score [0.0 - 100.0]
            normalized_score = min(100.0, (score / theoretical_max) * 100.0)
            entry["rrf_score"] = normalized_score
            entry["matched_facets"] = sorted(list(doc_facet_hits.get(path, set())))
            entry["facet_ranks"] = doc_facet_ranks.get(path, {})
            fused_list.append(entry)

        # Sort descending by fused RRF score
        fused_list.sort(key=lambda x: x["rrf_score"], reverse=True)
        return fused_list[:top_k]


# Global singleton instance
multi_way_rrf = MultiWayRRF()
