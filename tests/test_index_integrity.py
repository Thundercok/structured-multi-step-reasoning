import sqlite3

import numpy as np
import pytest

from rat.crawler.db import Database
from rat.engine.vector_cache import VectorCache


@pytest.fixture
def database(tmp_path):
    instance = Database(str(tmp_path / "index.db"))
    yield instance
    instance.get_connection().close()


def document(name):
    return dict(
        file_path=f"/documents/{name}.pdf", file_name=f"{name}.pdf", file_ext=".pdf",
        file_size=100, created_at=1, modified_at=1, indexed_at=1,
        content_text=f"Content for {name}",
    )


def embeddings(count=1):
    vectors = np.zeros((count, 384), dtype=np.float32)
    vectors[:, 0] = 1
    return vectors


def test_upsert_returns_existing_id_after_other_inserts(database):
    first = document("first")
    original_id = database.upsert_document(first)
    other_id = database.upsert_document(document("other"))
    updated_id = database.upsert_document({**first, "content_text": "updated content"})
    assert updated_id == original_id
    assert updated_id != other_id
    database.save_document_chunks(updated_id, first["file_path"], ["updated content"], embeddings())
    result = VectorCache(database).search(embeddings()[0])[0]
    assert result["doc_id"] == original_id
    assert result["file_path"] == first["file_path"]
    assert result["file_name"] == first["file_name"]
    assert result["chunk_text"] == "updated content"


def test_upsert_returns_existing_id_on_new_connection(database):
    first = document("first")
    original_id = database.upsert_document(first)
    reopened = Database(database.db_path)
    try:
        assert reopened.upsert_document(first) == original_id
    finally:
        reopened.get_connection().close()


@pytest.mark.parametrize("invalid_parent", ["other", "missing"])
def test_chunk_write_rejects_wrong_parent_without_erasing_old_chunks(database, invalid_parent):
    first = document("first")
    original_id = database.upsert_document(first)
    other_id = database.upsert_document(document("other"))
    database.save_document_chunks(original_id, first["file_path"], ["original"], embeddings())
    wrong_id = other_id if invalid_parent == "other" else 999999
    with pytest.raises(ValueError, match="document"):
        database.save_document_chunks(wrong_id, first["file_path"], ["replacement"], embeddings())
    rows = database.get_connection().execute("SELECT doc_id, chunk_text FROM document_chunks").fetchall()
    assert [tuple(row) for row in rows] == [(original_id, "original")]


def test_chunk_count_mismatch_leaves_previous_chunks_unchanged(database):
    first = document("first")
    doc_id = database.upsert_document(first)
    database.save_document_chunks(doc_id, first["file_path"], ["original"], embeddings())
    with pytest.raises(ValueError, match="embedding"):
        database.save_document_chunks(doc_id, first["file_path"], ["one", "two"], embeddings())
    row = database.get_connection().execute("SELECT chunk_text FROM document_chunks").fetchone()
    assert row["chunk_text"] == "original"


def test_failed_chunk_insert_rolls_back_replacement(database):
    first = document("first")
    doc_id = database.upsert_document(first)
    database.save_document_chunks(doc_id, first["file_path"], ["original"], embeddings())
    connection = database.get_connection()
    connection.execute("""
        CREATE TRIGGER reject_boom BEFORE INSERT ON document_chunks
        WHEN NEW.chunk_text = 'boom'
        BEGIN SELECT RAISE(ABORT, 'simulated chunk failure'); END
    """)
    connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="simulated chunk failure"):
        database.save_document_chunks(doc_id, first["file_path"], ["new", "boom"], embeddings(2))
    assert [row[0] for row in connection.execute("SELECT chunk_text FROM document_chunks")] == ["original"]
    assert not connection.in_transaction


def test_delete_document_removes_its_chunks_only(database):
    first, other = document("first"), document("other")
    for entry in (first, other):
        doc_id = database.upsert_document(entry)
        database.save_document_chunks(doc_id, entry["file_path"], [entry["content_text"]], embeddings())
    database.delete_document(first["file_path"])
    assert database.get_document_by_path(first["file_path"]) is None
    assert [row[0] for row in database.get_connection().execute("SELECT file_path FROM document_chunks")] == [other["file_path"]]


@pytest.mark.parametrize("backend", ["sql", "cache"])
def test_dense_retrieval_ignores_corrupt_legacy_chunk_links(database, backend):
    first, other = document("first"), document("other")
    database.upsert_document(first)
    other_id = database.upsert_document(other)
    database.save_document_chunks(other_id, other["file_path"], ["valid"], embeddings())
    connection = database.get_connection()
    connection.executemany(
        "INSERT INTO document_chunks (doc_id,file_path,chunk_index,chunk_text,embedding) VALUES (?,?,?,?,?)",
        [(other_id, first["file_path"], 0, "mismatched", embeddings()[0].tobytes()),
         (999999, "/documents/orphan.pdf", 0, "orphan", embeddings()[0].tobytes())],
    )
    connection.commit()
    search = database.search_vector_candidates if backend == "sql" else VectorCache(database).search
    results = search(embeddings()[0])
    assert [(row["file_path"], row["doc_id"]) for row in results] == [(other["file_path"], other_id)]
