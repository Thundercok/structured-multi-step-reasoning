"""Cached dense retrieval must follow committed index changes without a restart."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import numpy as np
import pytest

from rat.crawler.db import Database
from rat.engine.vector_cache import VectorCache


def vector(axis=0):
    result = np.zeros(384, dtype=np.float32)
    result[axis] = 1
    return result


def document(name="first", **updates):
    result = dict(
        file_path=f"/synthetic/{name}.pdf", file_name=f"{name}.pdf",
        file_ext=".pdf", file_size=100, created_at=1, modified_at=1,
        indexed_at=1, content_text=f"content for {name}",
    )
    result.update(updates)
    return result


def store(database, entry, text, axis=0):
    doc_id = database.upsert_document(entry)
    database.save_document_chunks(doc_id, entry["file_path"], [text], vector(axis)[None, :])
    return doc_id


@pytest.fixture
def resources(tmp_path):
    databases, caches = [], []

    def create(name="index"):
        database = Database(str(tmp_path / f"{name}.db"))
        databases.append(database)
        cache = VectorCache(database)
        caches.append(cache)
        return database, cache

    yield create
    for cache in caches:
        cache.close()
    for database in databases:
        database.get_connection().close()


def test_replacement_refreshes_vectors_snippets_and_persisted_chunk_ids(resources):
    database, cache = resources()
    entry = document()
    doc_id = store(database, entry, "old chunk")
    original = cache.search(vector())[0]

    database.save_document_chunks(doc_id, entry["file_path"], ["new chunk"], vector(1)[None, :])
    results = cache.search(vector(1))

    assert len(results) == 1
    assert results[0]["chunk_text"] == "new chunk"
    assert results[0]["similarity_score"] == pytest.approx(1)
    assert results[0]["chunk_id"] > 0
    assert results[0]["chunk_id"] != original["chunk_id"]
    assert results[0]["doc_id"] == doc_id
    assert cache.search(vector())[0]["similarity_score"] == pytest.approx(0)


def test_insert_after_empty_preload_and_delete_are_visible(resources):
    database, cache = resources()
    cache.preload()
    assert cache.search(vector()) == []
    entry = document()
    store(database, entry, "newly indexed chunk")

    result = cache.search(vector())[0]
    assert result["file_path"] == entry["file_path"]
    assert result["chunk_text"] == "newly indexed chunk"
    assert result["chunk_id"] > 0

    database.delete_document(entry["file_path"])
    assert cache.search(vector()) == []


def test_another_database_instance_updates_existing_cache(resources):
    database, cache = resources()
    entry = document()
    store(database, entry, "before")
    cache.preload()
    other = Database(database.db_path)
    try:
        store(other, entry, "after", axis=1)
        result = cache.search(vector(1))[0]
        assert result["chunk_text"] == "after"
        assert result["similarity_score"] == pytest.approx(1)
        other.delete_document(entry["file_path"])
        assert cache.search(vector()) == []
    finally:
        other.get_connection().close()


def test_committed_sqlite_writes_from_another_thread_refresh_cache(resources):
    database, cache = resources()
    entry = document()
    store(database, entry, "before")
    cache.preload()

    def update():
        with sqlite3.connect(database.db_path) as connection:
            connection.execute(
                "UPDATE document_chunks SET chunk_text = ?, embedding = ? WHERE file_path = ?",
                ("cross-thread replacement", vector(1).tobytes(), entry["file_path"]),
            )

    with ThreadPoolExecutor(max_workers=1) as workers:
        workers.submit(update).result(timeout=10)
        result = workers.submit(cache.search, vector(1)).result(timeout=10)[0]

    assert result["chunk_text"] == "cross-thread replacement"
    assert result["similarity_score"] == pytest.approx(1)
    assert cache.search(vector(1))[0]["chunk_text"] == "cross-thread replacement"


def test_metadata_refresh_changes_cached_extension_and_date_filters(resources):
    database, cache = resources()
    entry = document()
    store(database, entry, "unchanged vector")
    assert cache.search(vector(), extensions=[".pdf"], date_max=2)
    changed = {**entry, "file_name": "renamed.txt", "file_ext": ".txt", "modified_at": 20, "file_size": 250}
    database.upsert_document(changed)

    assert cache.search(vector(), extensions=[".pdf"]) == []
    assert cache.search(vector(), date_max=2) == []
    assert cache.search(vector(), excluded_extensions=[".txt"]) == []
    result = cache.search(vector(), extensions=[".txt"], date_min=20)[0]
    assert result["file_name"] == "renamed.txt"
    assert result["file_size"] == 250
    assert result["modified_at"] == 20


def test_separate_databases_never_share_cached_results(resources):
    first, first_cache = resources("first")
    second, second_cache = resources("second")
    first_entry, second_entry = document("first"), document("second")
    store(first, first_entry, "first database")
    store(second, second_entry, "second database")
    first_cache.preload()
    second_cache.preload()

    store(first, first_entry, "updated first database", axis=1)
    first_results = first_cache.search(vector(1))
    second_results = second_cache.search(vector())
    assert [r["file_path"] for r in first_results] == [first_entry["file_path"]]
    assert first_results[0]["chunk_text"] == "updated first database"
    assert [r["file_path"] for r in second_results] == [second_entry["file_path"]]
    assert second_results[0]["chunk_text"] == "second database"


def test_unchanged_search_reuses_loaded_matrix(resources):
    database, cache = resources()
    store(database, document(), "stable content")
    cache.preload()
    loaded_matrix = cache._matrix

    assert cache.search(vector())[0]["chunk_text"] == "stable content"
    assert cache.search(vector(), extensions=[".pdf"])[0]["chunk_text"] == "stable content"
    assert cache._matrix is loaded_matrix


def test_rolled_back_external_write_never_replaces_committed_cache(resources):
    database, cache = resources()
    entry = document()
    store(database, entry, "committed")
    cache.preload()
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE document_chunks SET chunk_text = ?, embedding = ? WHERE file_path = ?",
            ("uncommitted", vector(1).tobytes(), entry["file_path"]),
        )
        assert cache.search(vector())[0]["chunk_text"] == "committed"
        connection.rollback()

    result = cache.search(vector())[0]
    assert result["chunk_text"] == "committed"
    assert result["similarity_score"] == pytest.approx(1)


def test_write_during_search_cannot_mix_old_vector_with_new_chunk_text(resources, monkeypatch):
    database, cache = resources()
    entry = document()
    store(database, entry, "before concurrent replacement")
    cache.preload()
    dot = np.dot
    replaced = False

    def commit_during_scoring(*args, **kwargs):
        nonlocal replaced
        result = dot(*args, **kwargs)
        if not replaced:
            replaced = True
            with sqlite3.connect(database.db_path) as connection:
                connection.execute(
                    "UPDATE document_chunks SET chunk_text = ?, embedding = ? WHERE file_path = ?",
                    ("after concurrent replacement", vector(1).tobytes(), entry["file_path"]),
                )
        return result

    monkeypatch.setattr(np, "dot", commit_during_scoring)
    first_result = cache.search(vector())[0]
    assert replaced
    assert first_result["chunk_text"] == "before concurrent replacement"
    assert first_result["similarity_score"] == pytest.approx(1)
    next_result = cache.search(vector(1))[0]
    assert next_result["chunk_text"] == "after concurrent replacement"
    assert next_result["similarity_score"] == pytest.approx(1)


def test_empty_chunk_replacement_clears_persisted_and_cached_vectors(resources):
    database, cache = resources()
    entry = document()
    doc_id = store(database, entry, "old chunk")
    cache.preload()

    database.save_document_chunks(doc_id, entry["file_path"], [], np.empty((0, 384), dtype=np.float32))

    assert database.get_document_by_path(entry["file_path"]) is not None
    assert database.search_vector_candidates(vector()) == []
    assert cache.search(vector()) == []


def test_cache_close_is_idempotent(resources):
    database, cache = resources()
    entry = document()
    store(database, entry, "content")
    cache.preload()
    cache.close()
    cache.close()
    store(database, entry, "content after close", axis=1)
    result = cache.search(vector(1))[0]
    assert result["chunk_text"] == "content after close"
    assert result["similarity_score"] == pytest.approx(1)
