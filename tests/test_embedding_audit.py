import sqlite3

import numpy as np
import pytest

from scripts.audit_embedding_drift import compare_embeddings


@pytest.fixture
def connection():
    database = sqlite3.connect(":memory:")
    database.executescript("""
        CREATE TABLE documents(id INTEGER PRIMARY KEY, file_path TEXT, indexed_at REAL);
        CREATE TABLE document_chunks(id INTEGER PRIMARY KEY, doc_id INTEGER, file_path TEXT, chunk_text TEXT, embedding BLOB);
    """)
    yield database
    database.close()


def insert(database, chunk_id, vector, timestamp=1788220800):
    path = f"/{chunk_id}.pdf"
    database.execute("INSERT INTO documents VALUES (?,?,?)", (chunk_id, path, timestamp))
    database.execute("INSERT INTO document_chunks VALUES (?,?,?,?,?)", (chunk_id, chunk_id, path, str(chunk_id), np.asarray(vector, dtype=np.float32).tobytes()))


def encode(texts):
    return np.tile([1.0, 0.0], (len(texts), 1))


def test_cosine_and_week_groups_detect_disagreement(connection):
    insert(connection, 1, [2, 0])
    insert(connection, 2, [0, 1], timestamp=1790035200)
    result = compare_embeddings(connection, encode)
    assert [row["cosine"] for row in result["records"]] == [1, 0]
    assert result["summary"]["below_threshold"] == 1
    assert len(result["by_indexed_week"]) == 2
    assert result["records"][0]["stored_norm"] == 2


def test_sampling_is_reproducible_without_global_random_state(connection):
    for chunk_id in range(1, 51):
        insert(connection, chunk_id, [1, 0])
    first = compare_embeddings(connection, encode, sample_size=10, seed=42)
    second = compare_embeddings(connection, encode, sample_size=10, seed=42)
    assert first["records"] == second["records"]
    assert len({row["chunk_id"] for row in first["records"]}) == 10


def test_malformed_stored_vectors_are_counted_not_hidden(connection):
    for chunk_id, vector in enumerate(([0, 0], [float("nan"), 0], [1, 0, 0], [1, 0]), 1):
        insert(connection, chunk_id, vector)
    result = compare_embeddings(connection, encode)
    assert result["summary"]["invalid_stored"] == 3
    assert result["summary"]["compared"] == 1


def test_bad_parent_links_are_excluded(connection):
    insert(connection, 1, [1, 0])
    insert(connection, 2, [1, 0])
    connection.execute("UPDATE document_chunks SET doc_id=1 WHERE id=2")
    result = compare_embeddings(connection, encode)
    assert result["eligible_chunks"] == 1
    assert result["records"][0]["chunk_id"] == 1


@pytest.mark.parametrize("encoder", [lambda texts: np.zeros((len(texts), 2)), lambda texts: np.full((len(texts), 2), np.nan)])
def test_invalid_fresh_output_fails_audit(connection, encoder):
    insert(connection, 1, [1, 0])
    with pytest.raises(RuntimeError, match="fresh embedding"):
        compare_embeddings(connection, encoder)


def test_empty_index_fails_explicitly(connection):
    with pytest.raises(ValueError, match="No validly linked"):
        compare_embeddings(connection, encode)
