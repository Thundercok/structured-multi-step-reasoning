"""
rat.crawler.db — SQLite database storage with FTS5 for fast full-text search.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("rat.db")


def remove_vietnamese_accents(text: str) -> str:
    """Normalize and remove Vietnamese accents/diacritics for insensitive search."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower()


_GLOBAL_DB_LOCK = threading.RLock()


class Database:
    """Thread-safe SQLite database manager for rat search index."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._local = threading.local()
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode and busy_timeout for high concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=60000;")
            self._local.conn = conn
        return self._local.conn

    def init_db(self) -> None:
        """Initialize tables and FTS5 index."""
        with _GLOBAL_DB_LOCK:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Main metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_ext TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    modified_at REAL NOT NULL,
                    md5_hash TEXT,
                    content_text TEXT,
                    summary TEXT,
                    normalized_text TEXT,
                    indexed_at REAL NOT NULL
                );
            """)

            # Schema migration: ensure normalized_text exists in existing documents table
            cursor.execute("PRAGMA table_info(documents);")
            existing_cols = [row["name"] for row in cursor.fetchall()]
            if "normalized_text" not in existing_cols:
                try:
                    cursor.execute("ALTER TABLE documents ADD COLUMN normalized_text TEXT;")
                except Exception as e:
                    logger.debug(f"Migration note for normalized_text: {e}")

            # Fast compound indexes for instantaneous collection filtering & deduplication
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_ext ON documents(file_ext);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_modified ON documents(modified_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_size ON documents(file_size);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_ext_mod ON documents(file_ext, modified_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_md5_size ON documents(md5_hash, file_size);")

            # Document Chunks table for Dense Vector search
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER,
                    file_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding BLOB,
                    FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_path ON document_chunks(file_path);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_doc_id ON document_chunks(doc_id);")

            # FTS5 Virtual table for full-text search
            try:
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                        file_name,
                        content_text,
                        normalized_text,
                        content='documents',
                        content_rowid='id',
                        tokenize='unicode61'
                    );
                """)

                # Refresh triggers to keep FTS5 synchronized with real normalized_text
                cursor.execute("DROP TRIGGER IF EXISTS docs_ai;")
                cursor.execute("DROP TRIGGER IF EXISTS docs_ad;")
                cursor.execute("DROP TRIGGER IF EXISTS docs_au;")

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
                        INSERT INTO documents_fts(rowid, file_name, content_text, normalized_text)
                        VALUES (
                            new.id,
                            new.file_name,
                            new.content_text,
                            coalesce(new.normalized_text, new.file_name || ' ' || new.content_text)
                        );
                    END;
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, file_name, content_text, normalized_text)
                        VALUES ('delete', old.id, old.file_name, old.content_text, coalesce(old.normalized_text, old.file_name || ' ' || old.content_text));
                    END;
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, file_name, content_text, normalized_text)
                        VALUES ('delete', old.id, old.file_name, old.content_text, coalesce(old.normalized_text, old.file_name || ' ' || old.content_text));
                        INSERT INTO documents_fts(rowid, file_name, content_text, normalized_text)
                        VALUES (
                            new.id,
                            new.file_name,
                            new.content_text,
                            coalesce(new.normalized_text, new.file_name || ' ' || new.content_text)
                        );
                    END;
                """)
            except Exception as e:
                logger.warning(f"FTS5 setup note: {e}")

            conn.commit()

    def upsert_document(self, doc: Dict[str, Any]) -> int:
        """Insert or update a document in the index."""
        with _GLOBAL_DB_LOCK:
            conn = self.get_connection()
            cursor = conn.cursor()

            content = doc.get("content_text", "") or ""
            norm_text = remove_vietnamese_accents(f"{doc['file_name']} {content}")

            cursor.execute("""
                INSERT INTO documents (
                    file_path, file_name, file_ext, file_size,
                    created_at, modified_at, md5_hash, content_text,
                    summary, normalized_text, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_name = excluded.file_name,
                    file_ext = excluded.file_ext,
                    file_size = excluded.file_size,
                    created_at = excluded.created_at,
                    modified_at = excluded.modified_at,
                    md5_hash = excluded.md5_hash,
                    content_text = excluded.content_text,
                    summary = excluded.summary,
                    normalized_text = excluded.normalized_text,
                    indexed_at = excluded.indexed_at
            """, (
                doc["file_path"],
                doc["file_name"],
                doc["file_ext"].lower(),
                doc["file_size"],
                doc["created_at"],
                doc["modified_at"],
                doc.get("md5_hash", ""),
                content,
                doc.get("summary", ""),
                norm_text,
                doc["indexed_at"],
            ))
            doc_id = cursor.lastrowid
            conn.commit()
            return doc_id

    def delete_document(self, file_path: str) -> None:
        """Delete document by file path."""
        with _GLOBAL_DB_LOCK:
            conn = self.get_connection()
            conn.execute("DELETE FROM documents WHERE file_path = ?", (file_path,))
            conn.commit()

    def get_document_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document record by path."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def list_all_paths(self) -> Dict[str, float]:
        """Return dict of {file_path: modified_at} for all indexed files."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, modified_at FROM documents")
        return {row["file_path"]: row["modified_at"] for row in cursor.fetchall()}

    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_files, SUM(file_size) as total_size FROM documents")
        row = cursor.fetchone()
        total_files = row["total_files"] if row else 0
        total_size = row["total_size"] if row and row["total_size"] else 0

        cursor.execute("SELECT file_ext, COUNT(*) as count FROM documents GROUP BY file_ext ORDER BY count DESC LIMIT 10")
        ext_counts = {r["file_ext"]: r["count"] for r in cursor.fetchall()}

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "extensions": ext_counts
        }

    def get_total_documents(self) -> int:
        """Return total number of indexed files."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM documents")
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_recent_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return most recently modified documents."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_path, file_name, file_ext, file_size, modified_at, category "
            "FROM documents ORDER BY modified_at DESC LIMIT ?",
            (limit,)
        )
        return [dict(r) for r in cursor.fetchall()]

    def search_candidates(
        self,
        keywords: List[str],
        extensions: Optional[List[str]] = None,
        excluded_extensions: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Multi-tier candidate retrieval using FTS5 BM25 search & metadata filters.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        where_clauses = []
        params: List[Any] = []

        if extensions:
            ext_placeholders = ",".join(["?"] * len(extensions))
            where_clauses.append(f"d.file_ext IN ({ext_placeholders})")
            params.extend([e.lower() for e in extensions])

        if excluded_extensions:
            ex_placeholders = ",".join(["?"] * len(excluded_extensions))
            where_clauses.append(f"d.file_ext NOT IN ({ex_placeholders})")
            params.extend([e.lower() for e in excluded_extensions])

        if date_min is not None:
            where_clauses.append("d.modified_at >= ?")
            params.append(date_min)

        if date_max is not None:
            where_clauses.append("d.modified_at <= ?")
            params.append(date_max)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Case 1: Keywords provided -> Full-text Search
        if keywords:
            clean_keywords = [k.strip() for k in keywords if k.strip()]
            # FTS5 term formatting: clean alphanumeric terms
            fts_terms = []
            for k in clean_keywords:
                safe_k = re.sub(r"[^\w]+", "", k)
                if not safe_k:
                    continue
                k_unaccent = remove_vietnamese_accents(safe_k)
                fts_terms.append(f"{safe_k}*")
                if k_unaccent != safe_k.lower():
                    fts_terms.append(f"{k_unaccent}*")

            fts_query = " OR ".join(fts_terms) if fts_terms else "*"

            sql_fts = f"""
                SELECT 
                    d.id, d.file_path, d.file_name, d.file_ext, d.file_size,
                    d.created_at, d.modified_at, d.content_text, d.summary,
                    bm25(documents_fts, 15.0, 1.0, 1.0) as rank
                FROM documents_fts
                JOIN documents d ON documents_fts.rowid = d.id
                {where_sql if where_sql else ''}
                {"AND" if where_sql else "WHERE"} documents_fts MATCH ?
                ORDER BY rank ASC
                LIMIT ?
            """
            exec_params = list(params) + [fts_query, limit]
            fts_results = []
            try:
                cursor.execute(sql_fts, exec_params)
                rows = cursor.fetchall()
                fts_results = [dict(r) for r in rows]
                for candidate in fts_results:
                    candidate["bm25"] = -candidate["rank"]
            except Exception as e:
                logger.warning(f"FTS5 query failed: {e}")

            # Also query direct filename matches (guaranteed inclusion)
            name_likes = []
            name_params = []
            for k in clean_keywords:
                name_likes.append("d.file_name LIKE ?")
                name_params.append(f"%{k}%")
                k_unaccent = remove_vietnamese_accents(k)
                if k_unaccent != k.lower():
                    name_likes.append("d.file_name LIKE ?")
                    name_params.append(f"%{k_unaccent}%")

            if name_likes:
                name_where = " OR ".join(name_likes)
                combined_where = f"({name_where})"
                if where_clauses:
                    combined_where += " AND " + " AND ".join(where_clauses)
                sql_name = f"""
                    SELECT 
                        d.id, d.file_path, d.file_name, d.file_ext, d.file_size,
                        d.created_at, d.modified_at, d.content_text, d.summary,
                        -100.0 as rank
                    FROM documents d
                    WHERE {combined_where}
                    LIMIT 20
                """
                try:
                    cursor.execute(sql_name, name_params + params)
                    name_rows = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    name_rows = []
            else:
                name_rows = []

            # Merge name matches (first) with FTS matches
            seen_ids = set()
            merged_results = []
            bm25_by_id = {candidate["id"]: candidate["bm25"] for candidate in fts_results}
            for r in name_rows:
                r["bm25"] = bm25_by_id.get(r["id"])
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    merged_results.append(r)

            for r in fts_results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    merged_results.append(r)

            if merged_results:
                return merged_results[:limit]

            # Fallback to LIKE if FTS fails or returns 0 matches
            like_clauses = []
            like_params = []
            for k in clean_keywords:
                like_clauses.append("(d.file_name LIKE ? OR d.content_text LIKE ?)")
                like_params.extend([f"%{k}%", f"%{k}%"])

            like_sql_where = " AND ".join(like_clauses)
            final_where = f"{where_sql} {'AND' if where_sql else 'WHERE'} ({like_sql_where})"

            sql_like = f"""
                SELECT 
                    d.id, d.file_path, d.file_name, d.file_ext, d.file_size,
                    d.created_at, d.modified_at, d.content_text, d.summary,
                    0.0 as rank
                FROM documents d
                {final_where}
                ORDER BY d.modified_at DESC
                LIMIT ?
            """
            cursor.execute(sql_like, params + like_params + [limit])
            return [dict(r) for r in cursor.fetchall()]

        # Case 2: No keywords -> Return recent files matching metadata
        sql_recent = f"""
            SELECT 
                d.id, d.file_path, d.file_name, d.file_ext, d.file_size,
                d.created_at, d.modified_at, d.content_text, d.summary,
                0.0 as rank
            FROM documents d
            {where_sql}
            ORDER BY d.modified_at DESC
            LIMIT ?
        """
        cursor.execute(sql_recent, params + [limit])
        return [dict(r) for r in cursor.fetchall()]

    def save_document_chunks(
        self,
        doc_id: int,
        file_path: str,
        chunks: List[Any],
        embeddings: np.ndarray,
    ) -> None:
        """Store semantic chunks and their vector embeddings for a document."""
        if not chunks or len(chunks) == 0 or embeddings.size == 0:
            return

        with _GLOBAL_DB_LOCK:
            conn = self.get_connection()
            # First remove existing chunks for this document
            conn.execute("DELETE FROM document_chunks WHERE file_path = ?", (file_path,))

            rows_to_insert = []
            for idx, chunk in enumerate(chunks):
                if idx < len(embeddings):
                    emb_bytes = embeddings[idx].astype(np.float32).tobytes()
                    text = chunk.text if hasattr(chunk, "text") else str(chunk)
                    chunk_idx = chunk.chunk_index if hasattr(chunk, "chunk_index") else idx
                    rows_to_insert.append((doc_id, file_path, chunk_idx, text, emb_bytes))

            if rows_to_insert:
                conn.executemany("""
                    INSERT INTO document_chunks (doc_id, file_path, chunk_index, chunk_text, embedding)
                    VALUES (?, ?, ?, ?, ?)
                """, rows_to_insert)
                conn.commit()

    def search_vector_candidates(
        self,
        query_vector: np.ndarray,
        extensions: Optional[List[str]] = None,
        excluded_extensions: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Execute Cosine Similarity search over chunk embeddings matrix in RAM.
        """
        if query_vector.size == 0:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        where_clauses = ["c.embedding IS NOT NULL"]
        params: List[Any] = []

        if extensions:
            ext_placeholders = ",".join(["?"] * len(extensions))
            where_clauses.append(f"d.file_ext IN ({ext_placeholders})")
            params.extend([e.lower() for e in extensions])

        if excluded_extensions:
            ex_placeholders = ",".join(["?"] * len(excluded_extensions))
            where_clauses.append(f"d.file_ext NOT IN ({ex_placeholders})")
            params.extend([e.lower() for e in excluded_extensions])

        if date_min is not None:
            where_clauses.append("d.modified_at >= ?")
            params.append(date_min)

        if date_max is not None:
            where_clauses.append("d.modified_at <= ?")
            params.append(date_max)

        where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = f"""
            SELECT 
                c.id as chunk_id, c.doc_id, c.file_path, c.chunk_index, c.chunk_text, c.embedding,
                d.file_name, d.file_ext, d.file_size, d.created_at, d.modified_at
            FROM document_chunks c
            JOIN documents d ON c.doc_id = d.id
            {where_sql}
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if not rows:
            return []

        chunk_records = []
        embedding_list = []
        dim = len(query_vector)

        for row in rows:
            emb_blob = row["embedding"]
            if not emb_blob:
                continue
            emb_vec = np.frombuffer(emb_blob, dtype=np.float32)
            if len(emb_vec) != dim:
                continue

            embedding_list.append(emb_vec)
            chunk_records.append({
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "file_path": row["file_path"],
                "file_name": row["file_name"],
                "file_ext": row["file_ext"],
                "file_size": row["file_size"],
                "created_at": row["created_at"],
                "modified_at": row["modified_at"],
                "chunk_index": row["chunk_index"],
                "chunk_text": row["chunk_text"],
            })

        if not embedding_list:
            return []

        matrix = np.vstack(embedding_list)
        # Cosine similarity via Dot Product
        similarities = np.dot(matrix, query_vector)

        # Pair similarities with records
        for idx, sim in enumerate(similarities):
            chunk_records[idx]["similarity_score"] = float(sim)

        # Sort descending by similarity
        chunk_records.sort(key=lambda x: x["similarity_score"], reverse=True)
        return chunk_records[:limit]

    def clean_deleted_files(self) -> int:
        """Remove indexed documents whose files no longer exist on disk."""
        paths = self.list_all_paths()
        deleted_count = 0
        with _GLOBAL_DB_LOCK:
            conn = self.get_connection()
            for path in paths:
                if not os.path.exists(path):
                    conn.execute("DELETE FROM documents WHERE file_path = ?", (path,))
                    conn.execute("DELETE FROM document_chunks WHERE file_path = ?", (path,))
                    deleted_count += 1
            if deleted_count > 0:
                conn.commit()
        return deleted_count

    def search_by_provenance(
        self,
        source_app: Optional[str] = None,
        source_domain: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        limit: int = 40
    ) -> List[Dict[str, Any]]:
        """Search documents matching OS provenance metadata (Safari, Chrome, Telegram, domain)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []

        if source_app:
            clauses.append("d.content_text LIKE ?")
            params.append(f"%{source_app}%")

        if source_domain:
            clauses.append("d.content_text LIKE ?")
            params.append(f"%{source_domain}%")

        if not clauses:
            return []

        if extensions:
            ext_placeholders = ",".join(["?"] * len(extensions))
            clauses.append(f"d.file_ext IN ({ext_placeholders})")
            params.extend([e.lower() for e in extensions])

        if date_min is not None:
            clauses.append("d.modified_at >= ?")
            params.append(date_min)

        if date_max is not None:
            clauses.append("d.modified_at <= ?")
            params.append(date_max)

        where_sql = "WHERE " + " AND ".join(clauses)
        sql = f"""
            SELECT d.id, d.file_path, d.file_name, d.file_ext, d.file_size,
                   d.created_at, d.modified_at, d.content_text, d.summary,
                   -50.0 as rank
            FROM documents d
            {where_sql}
            ORDER BY d.modified_at DESC
            LIMIT ?
        """
        params.append(limit)
        try:
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"search_by_provenance error: {e}")
            return []

    def search_by_vision_tags(
        self,
        tags: List[str],
        extensions: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        limit: int = 40
    ) -> List[Dict[str, Any]]:
        """Search documents matching Apple Vision OCR & image classification taxonomy tags."""
        if not tags:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []

        tag_clauses = []
        for t in tags:
            tag_clauses.append("d.content_text LIKE ?")
            params.append(f"%{t}%")

        clauses.append(f"({' OR '.join(tag_clauses)})")

        if extensions:
            ext_placeholders = ",".join(["?"] * len(extensions))
            clauses.append(f"d.file_ext IN ({ext_placeholders})")
            params.extend([e.lower() for e in extensions])

        if date_min is not None:
            clauses.append("d.modified_at >= ?")
            params.append(date_min)

        if date_max is not None:
            clauses.append("d.modified_at <= ?")
            params.append(date_max)

        where_sql = "WHERE " + " AND ".join(clauses)
        sql = f"""
            SELECT d.id, d.file_path, d.file_name, d.file_ext, d.file_size,
                   d.created_at, d.modified_at, d.content_text, d.summary,
                   -40.0 as rank
            FROM documents d
            {where_sql}
            ORDER BY d.modified_at DESC
            LIMIT ?
        """
        params.append(limit)
        try:
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"search_by_vision_tags error: {e}")
            return []

