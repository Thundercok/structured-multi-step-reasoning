"""SQLite-backed in-memory chunk vectors with commit-aware refresh."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import sqlite3
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

import numpy as np

from rat.config import config
from rat.crawler.db import Database

logger = logging.getLogger("rat.vector_cache")


class VectorCache:
    """Cache persisted chunk vectors, keeping text in SQLite until retrieval."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database(config.db_path)
        self._matrix: np.ndarray = np.empty((0, 384), dtype=np.float32)
        self._records: List[Dict[str, Any]] = []
        self._is_loaded = False
        self._lock = threading.RLock()
        self._read_connection: Optional[sqlite3.Connection] = None
        self._data_version: Optional[int] = None

    @contextmanager
    def _snapshot(self) -> Iterator[tuple[sqlite3.Connection, int]]:
        """Use one dedicated connection so data_version stays comparable.

        All access is serialized by _lock. PRAGMA data_version starts the read
        snapshot; vectors, metadata and lazy text reads then see the same commit.
        """
        if self._read_connection is None:
            self.db.get_connection()  # Preserve lazy schema initialization.
            reader = Database(self.db.db_path, read_only=True)
            self._read_connection = reader.get_connection()
        connection = self._read_connection
        connection.execute("BEGIN")
        try:
            version = connection.execute("PRAGMA data_version").fetchone()[0]
            yield connection, version
        finally:
            connection.rollback()

    def _load_snapshot(self, connection: sqlite3.Connection, version: int) -> None:
        started = time.monotonic()
        rows = connection.execute("""
            SELECT c.id AS chunk_id, c.doc_id, c.file_path, c.chunk_index, c.embedding,
                   d.file_name, d.file_ext, d.file_size, d.created_at, d.modified_at
            FROM document_chunks c
            JOIN documents d ON c.doc_id = d.id AND c.file_path = d.file_path
            WHERE c.embedding IS NOT NULL
            ORDER BY c.id
        """).fetchall()
        records = []
        vectors = []
        for row in rows:
            if not row["embedding"]:
                continue
            vectors.append(np.frombuffer(row["embedding"], dtype=np.float32))
            records.append({key: row[key] for key in row.keys() if key != "embedding"})

        matrix = np.vstack(vectors) if vectors else np.empty((0, 384), dtype=np.float32)
        self._matrix = matrix
        self._records = records
        self._data_version = version
        self._is_loaded = True
        logger.debug("VectorCache loaded %s chunks in %.3fs", len(records), time.monotonic() - started)

    def preload(self) -> None:
        """Load committed chunk vectors without retaining chunk text in RAM."""
        with self._lock, self._snapshot() as (connection, version):
            self._load_snapshot(connection, version)

    def search(
        self,
        query_vector: np.ndarray,
        extensions: Optional[List[str]] = None,
        excluded_extensions: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Rank cached vectors and enrich results from the same SQLite snapshot."""
        if query_vector.size == 0 or limit <= 0:
            return []
        with self._lock, self._snapshot() as (connection, version):
            if not self._is_loaded or self._data_version != version:
                self._load_snapshot(connection, version)
            if self._matrix.size == 0 or not self._records:
                return []

            ext_set = {ext.lower() for ext in extensions} if extensions else None
            excluded_set = {ext.lower() for ext in excluded_extensions} if excluded_extensions else None
            valid_indices = []
            for index, record in enumerate(self._records):
                extension = record["file_ext"].lower()
                if ext_set and extension not in ext_set:
                    continue
                if excluded_set and extension in excluded_set:
                    continue
                if date_min is not None and record["modified_at"] < date_min:
                    continue
                if date_max is not None and record["modified_at"] > date_max:
                    continue
                valid_indices.append(index)
            if not valid_indices:
                return []

            matrix = self._matrix if len(valid_indices) == len(self._records) else self._matrix[valid_indices]
            similarities = np.dot(matrix, query_vector)
            ranked = [
                {**self._records[index], "similarity_score": float(score)}
                for index, score in zip(valid_indices, similarities)
            ]
            ranked.sort(key=lambda record: record["similarity_score"], reverse=True)
            top_results = ranked[:limit]
            placeholders = ",".join("?" for _ in top_results)
            rows = connection.execute(f"""
                SELECT c.id, c.doc_id, c.file_path, c.chunk_text
                FROM document_chunks c
                JOIN documents d ON c.doc_id = d.id AND c.file_path = d.file_path
                WHERE c.id IN ({placeholders})
            """, [record["chunk_id"] for record in top_results]).fetchall()
            text_by_identity = {
                (row["id"], row["doc_id"], row["file_path"]): row["chunk_text"]
                for row in rows
            }
            results = []
            for record in top_results:
                identity = (record["chunk_id"], record["doc_id"], record["file_path"])
                if identity in text_by_identity:
                    record["chunk_text"] = text_by_identity[identity]
                    results.append(record)
            return results

    def append_vectors(self, new_records: List[Dict[str, Any]], embeddings: np.ndarray) -> None:
        """Compatibility hook: invalidate after committing new vectors to SQLite."""
        with self._lock:
            self._is_loaded = False

    def remove_by_path(self, file_path: str) -> None:
        """Compatibility hook: invalidate after deleting the path from SQLite."""
        with self._lock:
            self._is_loaded = False

    def close(self) -> None:
        """Release the owned read connection and cached arrays; allow later reuse."""
        with self._lock:
            if self._read_connection is not None:
                self._read_connection.close()
                self._read_connection = None
            self._matrix = np.empty((0, 384), dtype=np.float32)
            self._records = []
            self._data_version = None
            self._is_loaded = False


vector_cache = VectorCache()
