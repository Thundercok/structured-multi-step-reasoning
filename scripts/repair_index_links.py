"""Audit chunk links read-only, or repair a new SQLite backup without touching the source."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_links(connection):
    queries = {
        "documents": "SELECT COUNT(*) FROM documents",
        "chunks": "SELECT COUNT(*) FROM document_chunks",
        "orphan_chunks": """
            SELECT COUNT(*) FROM document_chunks AS chunk
            LEFT JOIN documents AS parent ON parent.id = chunk.doc_id
            WHERE parent.id IS NULL
        """,
        "mismatched_path_chunks": """
            SELECT COUNT(*) FROM document_chunks AS chunk
            JOIN documents AS parent ON parent.id = chunk.doc_id
            WHERE chunk.file_path IS NOT parent.file_path
        """,
        "recoverable_by_path": """
            SELECT COUNT(*) FROM document_chunks AS chunk
            JOIN documents AS parent ON parent.file_path = chunk.file_path
            WHERE chunk.doc_id IS NOT parent.id
        """,
        "without_document_path": """
            SELECT COUNT(*) FROM document_chunks AS chunk
            LEFT JOIN documents AS parent ON parent.file_path = chunk.file_path
            WHERE parent.id IS NULL
        """,
    }
    return {name: connection.execute(query).fetchone()[0] for name, query in queries.items()}


def audit_index(source_path):
    source = Path(source_path).resolve()
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        return dict(status="audit_only", source=str(source), counts=inspect_links(connection))


def repair_copy(source_path, output_path):
    source, output = Path(source_path).resolve(), Path(output_path).resolve()
    if source == output:
        raise ValueError("In-place repair is forbidden; choose a new output database")
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        original.execute("PRAGMA query_only=ON")
        with output.open("xb"):
            pass
        with closing(sqlite3.connect(output)) as repaired:
            original.backup(repaired)
            repaired.execute("PRAGMA journal_mode=DELETE")
            before = inspect_links(repaired)
            with repaired:
                repaired.execute("BEGIN IMMEDIATE")
                if before["without_document_path"]:
                    repaired.execute("""
                        CREATE TABLE IF NOT EXISTS quarantined_document_chunks (
                            id INTEGER PRIMARY KEY, doc_id INTEGER, file_path TEXT NOT NULL,
                            chunk_index INTEGER NOT NULL, chunk_text TEXT NOT NULL,
                            embedding BLOB, reason TEXT NOT NULL
                        )
                    """)
                    repaired.execute("""
                        INSERT INTO quarantined_document_chunks
                            (id, doc_id, file_path, chunk_index, chunk_text, embedding, reason)
                        SELECT chunk.id, chunk.doc_id, chunk.file_path, chunk.chunk_index,
                               chunk.chunk_text, chunk.embedding, 'no_document_for_path'
                        FROM document_chunks AS chunk
                        WHERE NOT EXISTS (
                            SELECT 1 FROM documents AS parent WHERE parent.file_path = chunk.file_path
                        )
                    """)
                    repaired.execute("""
                        DELETE FROM document_chunks
                        WHERE NOT EXISTS (
                            SELECT 1 FROM documents WHERE documents.file_path = document_chunks.file_path
                        )
                    """)
                repaired.execute("""
                    UPDATE document_chunks SET doc_id = (
                        SELECT id FROM documents WHERE documents.file_path = document_chunks.file_path
                    )
                    WHERE doc_id IS NOT (
                        SELECT id FROM documents WHERE documents.file_path = document_chunks.file_path
                    )
                """)
                after = inspect_links(repaired)
                if after["orphan_chunks"] or after["mismatched_path_chunks"]:
                    raise ValueError("Repaired copy still has invalid chunk links")
                if after["chunks"] + before["without_document_path"] != before["chunks"]:
                    raise ValueError("Chunk count conservation check failed")
                if repaired.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("SQLite quick_check failed on repaired copy")
    return dict(
        status="copy_repaired", source=str(source), output=str(output), output_sha256=file_hash(output),
        before=before, after=after, relinked_chunks=before["recoverable_by_path"],
        quarantined_chunks=before["without_document_path"], source_modified=False,
        assumptions="Exact stored file_path identifies the document; text freshness and embedding model are not verified.",
        activation="Not activated. Stop RAT, review the copy, and make a fresh live backup before any separate migration.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Source index; always opened read-only")
    parser.add_argument("--output-db", help="Optional new repaired copy; existing files are never overwritten")
    args = parser.parse_args()
    try:
        result = repair_copy(args.db, args.output_db) if args.output_db else audit_index(args.db)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(json.dumps(dict(status="failed", error=str(error)), ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
