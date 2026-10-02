"""
rat.engine.vector_cache — High-speed In-Memory Vector Cache for sub-millisecond retrieval.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np

from rat.config import config
from rat.crawler.db import Database

logger = logging.getLogger("rat.vector_cache")


class VectorCache:
    """
    Maintains all document chunk embeddings in RAM for instant (1ms) vector dot-product search.
    """

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database(config.db_path)
        self._matrix: np.ndarray = np.empty((0, 384), dtype=np.float32)
        self._records: List[Dict[str, Any]] = []
        self._is_loaded = False
        self._lock = threading.RLock()

    def preload(self) -> None:
        """Load all chunk vectors from SQLite into contiguous RAM memory without text payload bloat."""
        with self._lock:
            t0 = time.time()
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    c.id as chunk_id, c.doc_id, c.file_path, c.chunk_index, c.embedding,
                    d.file_name, d.file_ext, d.file_size, d.created_at, d.modified_at
                FROM document_chunks c
                JOIN documents d ON c.doc_id = d.id AND c.file_path = d.file_path
                WHERE c.embedding IS NOT NULL
            """)
            rows = cursor.fetchall()

            records = []
            emb_list = []

            for row in rows:
                blob = row["embedding"]
                if not blob:
                    continue
                vec = np.frombuffer(blob, dtype=np.float32)
                emb_list.append(vec)
                records.append({
                    "chunk_id": row["chunk_id"],
                    "doc_id": row["doc_id"],
                    "file_path": row["file_path"],
                    "file_name": row["file_name"],
                    "file_ext": row["file_ext"],
                    "file_size": row["file_size"],
                    "created_at": row["created_at"],
                    "modified_at": row["modified_at"],
                    "chunk_index": row["chunk_index"],
                })

            if emb_list:
                self._matrix = np.vstack(emb_list)
                self._records = records
                self._is_loaded = True
                logger.info(f"VectorCache preloaded {len(records)} chunks in {time.time()-t0:.3f}s (RAM optimized)")
            else:
                self._matrix = np.empty((0, 384), dtype=np.float32)
                self._records = []
                self._is_loaded = True

    def search(
        self,
        query_vector: np.ndarray,
        extensions: Optional[List[str]] = None,
        excluded_extensions: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Execute instant in-memory Cosine Similarity search (< 1.5ms) with lazy text enrichment.
        """
        if not self._is_loaded:
            self.preload()

        with self._lock:
            if self._matrix.size == 0 or len(self._records) == 0 or query_vector.size == 0:
                return []

            # Filter indices by extension, excluded_extension, and date if specified
            if extensions or excluded_extensions or date_min is not None or date_max is not None:
                ext_set = set(e.lower() for e in extensions) if extensions else None
                ex_set = set(e.lower() for e in excluded_extensions) if excluded_extensions else None
                valid_indices = []
                for idx, r in enumerate(self._records):
                    r_ext = r["file_ext"].lower()
                    if ext_set and r_ext not in ext_set:
                        continue
                    if ex_set and r_ext in ex_set:
                        continue
                    if date_min is not None and r["modified_at"] < date_min:
                        continue
                    if date_max is not None and r["modified_at"] > date_max:
                        continue
                    valid_indices.append(idx)

                if not valid_indices:
                    return []

                sub_matrix = self._matrix[valid_indices]
                similarities = np.dot(sub_matrix, query_vector)

                results = []
                for idx_in_sub, global_idx in enumerate(valid_indices):
                    rec = dict(self._records[global_idx])
                    rec["similarity_score"] = float(similarities[idx_in_sub])
                    results.append(rec)
            else:
                # Fast full matrix dot product
                similarities = np.dot(self._matrix, query_vector)
                results = []
                for idx, sim in enumerate(similarities):
                    rec = dict(self._records[idx])
                    rec["similarity_score"] = float(sim)
                    results.append(rec)

            # Sort descending by similarity
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            top_results = results[:limit]

            # Lazy-enrich chunk_text from SQLite only for the top-k results
            chunk_ids = [r["chunk_id"] for r in top_results if r.get("chunk_id") and r["chunk_id"] > 0]
            if chunk_ids:
                try:
                    placeholders = ",".join(["?"] * len(chunk_ids))
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT id, chunk_text FROM document_chunks WHERE id IN ({placeholders})", chunk_ids)
                    text_map = {row["id"]: row["chunk_text"] for row in cursor.fetchall()}
                    for r in top_results:
                        r["chunk_text"] = text_map.get(r.get("chunk_id"), "")
                except Exception as e:
                    logger.debug(f"Failed to lazy-enrich chunk_text: {e}")
                    for r in top_results:
                        r.setdefault("chunk_text", "")
            else:
                for r in top_results:
                    r.setdefault("chunk_text", "")

            return top_results

    def append_vectors(self, new_records: List[Dict[str, Any]], embeddings: np.ndarray) -> None:
        """
        Dynamically append newly indexed chunks and embeddings to RAM matrix without full reload.
        Strips chunk_text payload to maintain minimal RAM footprint.
        """
        if not new_records or embeddings is None or len(embeddings) == 0:
            return

        with self._lock:
            # If not yet loaded, preload handles it
            if not self._is_loaded:
                self.preload()
                return

            # Ensure 2D float32 array
            if len(embeddings.shape) == 1:
                embeddings = embeddings.reshape(1, -1)
            embeddings = embeddings.astype(np.float32)

            lean_records = []
            for r in new_records:
                rec_copy = dict(r)
                rec_copy.pop("chunk_text", None)
                lean_records.append(rec_copy)

            if self._matrix.size == 0:
                self._matrix = embeddings
                self._records = lean_records
            else:
                self._matrix = np.vstack([self._matrix, embeddings])
                self._records.extend(lean_records)

            logger.debug(f"VectorCache dynamically appended {len(new_records)} chunks. Total: {len(self._records)}")

    def remove_by_path(self, file_path: str) -> None:
        """Remove file records and vectors from in-memory cache upon file deletion."""
        with self._lock:
            if not self._is_loaded or len(self._records) == 0:
                return

            keep_indices = [i for i, r in enumerate(self._records) if r["file_path"] != file_path]
            if len(keep_indices) == len(self._records):
                return

            if not keep_indices:
                self._matrix = np.empty((0, 384), dtype=np.float32)
                self._records = []
            else:
                self._matrix = self._matrix[keep_indices]
                self._records = [self._records[i] for i in keep_indices]

            logger.debug(f"VectorCache removed {file_path}. Remaining chunks: {len(self._records)}")


# Global singleton instance
vector_cache = VectorCache()
