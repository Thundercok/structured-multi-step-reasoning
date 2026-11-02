"""Indexing publishes metadata, full text and embeddings as one committed version."""

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from rat.crawler.db import Database
from rat.crawler.indexer import Indexer
from rat.crawler.provenance import provenance_extractor
from rat.crawler.watcher import RatFileEventHandler
from rat.engine.vector_cache import VectorCache


OLD_TEXT = "oldtopic original document content with enough text for semantic embeddings"
NEW_TEXT = "newtopic replacement document content with enough text for semantic embeddings"


def vector(axis=0):
    result = np.zeros(384, dtype=np.float32)
    result[axis] = 1
    return result


@pytest.fixture
def setup(tmp_path, monkeypatch):
    module = importlib.import_module("rat.crawler.indexer")
    path = tmp_path / "document.txt"
    path.write_text(OLD_TEXT, encoding="utf-8")
    database = Database(str(tmp_path / "index.db"))
    cache = VectorCache(database)
    indexer = Indexer(database)
    extract = Mock(side_effect=lambda location: Path(location).read_text(encoding="utf-8"))
    embed = Mock(side_effect=lambda texts: np.stack([vector(1 if "newtopic" in text else 0) for text in texts]))
    monkeypatch.setattr(module, "extract_document_content", extract)
    monkeypatch.setattr(module.embedder, "embed_texts", embed)
    monkeypatch.setattr(provenance_extractor, "get_provenance", Mock(return_value={}))
    yield SimpleNamespace(path=path, db=database, cache=cache, indexer=indexer, extract=extract, embed=embed)
    cache.close()
    database.get_connection().close()


def chunk_rows(database):
    return [tuple(row) for row in database.get_connection().execute(
        "SELECT id, doc_id, file_path, chunk_index, chunk_text, embedding FROM document_chunks ORDER BY id"
    )]


def fts_ids(database, keyword):
    return [row[0] for row in database.get_connection().execute(
        "SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?", (keyword,)
    )]


def test_reindex_replaces_complete_version_without_duplicate_cache_rows(setup):
    assert setup.indexer.index_single_file(str(setup.path), force=True)
    before = setup.cache.search(vector())[0]
    setup.path.write_text(NEW_TEXT, encoding="utf-8")

    assert setup.indexer.index_single_file(str(setup.path), force=True)

    document = setup.db.get_document_by_path(str(setup.path))
    assert document["content_text"] == NEW_TEXT
    assert document["id"] == before["doc_id"]
    assert not fts_ids(setup.db, "oldtopic")
    assert fts_ids(setup.db, "newtopic") == [document["id"]]
    results = setup.cache.search(vector(1))
    assert len(results) == 1
    assert results[0]["chunk_text"] == NEW_TEXT
    assert results[0]["chunk_id"] > 0
    assert results[0]["chunk_id"] != before["chunk_id"]
    assert results[0]["similarity_score"] == pytest.approx(1)


@pytest.mark.parametrize("short_text", ["", "brief", " \n\t "])
def test_shorter_content_clears_previous_chunks_and_cache(setup, short_text):
    assert setup.indexer.index_single_file(str(setup.path), force=True)
    assert setup.cache.search(vector())
    setup.embed.reset_mock()
    setup.path.write_text(short_text, encoding="utf-8")

    assert setup.indexer.index_single_file(str(setup.path), force=True)

    assert setup.db.get_document_by_path(str(setup.path))["content_text"] == short_text
    assert chunk_rows(setup.db) == []
    assert setup.cache.search(vector()) == []
    assert not fts_ids(setup.db, "oldtopic")
    setup.embed.assert_not_called()


@pytest.mark.parametrize("existing", [False, True])
def test_embedding_failure_preserves_complete_previous_version(setup, existing):
    if existing:
        assert setup.indexer.index_single_file(str(setup.path), force=True)
    before_doc = setup.db.get_document_by_path(str(setup.path))
    before_chunks = chunk_rows(setup.db)
    before_results = setup.cache.search(vector())
    setup.path.write_text(NEW_TEXT, encoding="utf-8")
    setup.embed.side_effect = RuntimeError("simulated embedding failure")

    assert not setup.indexer.index_single_file(str(setup.path), force=True)

    assert setup.db.get_document_by_path(str(setup.path)) == before_doc
    assert chunk_rows(setup.db) == before_chunks
    assert setup.cache.search(vector()) == before_results
    assert not fts_ids(setup.db, "newtopic")
    if existing:
        assert fts_ids(setup.db, "oldtopic") == [before_doc["id"]]


@pytest.mark.parametrize("existing", [False, True])
def test_chunk_insert_failure_rolls_back_metadata_fulltext_vectors_and_cache(setup, existing):
    if existing:
        assert setup.indexer.index_single_file(str(setup.path), force=True)
    before_doc = setup.db.get_document_by_path(str(setup.path))
    before_chunks = chunk_rows(setup.db)
    before_results = setup.cache.search(vector())
    connection = setup.db.get_connection()
    connection.execute("""
        CREATE TRIGGER reject_replacement BEFORE INSERT ON document_chunks
        WHEN NEW.chunk_text LIKE '%newtopic%'
        BEGIN SELECT RAISE(ABORT, 'simulated chunk insert failure'); END
    """)
    connection.commit()
    setup.path.write_text(NEW_TEXT, encoding="utf-8")

    assert not setup.indexer.index_single_file(str(setup.path), force=True)

    assert setup.db.get_document_by_path(str(setup.path)) == before_doc
    assert chunk_rows(setup.db) == before_chunks
    assert setup.cache.search(vector()) == before_results
    assert not fts_ids(setup.db, "newtopic")
    assert not connection.in_transaction
    if existing:
        assert fts_ids(setup.db, "oldtopic") == [before_doc["id"]]


def test_custom_database_indexing_never_mutates_global_vector_cache(setup, monkeypatch):
    module = importlib.import_module("rat.engine.vector_cache")
    global_cache = SimpleNamespace(_is_loaded=True, append_vectors=Mock(), _records=[])
    monkeypatch.setattr(module, "vector_cache", global_cache)
    setup.cache.preload()

    assert setup.indexer.index_single_file(str(setup.path), force=True)

    global_cache.append_vectors.assert_not_called()
    assert global_cache._records == []
    assert setup.cache.search(vector())[0]["chunk_text"] == OLD_TEXT


@pytest.mark.parametrize("same_timestamp", [False, True])
def test_edit_within_same_second_is_reindexed(setup, same_timestamp):
    before = OLD_TEXT.ljust(max(len(OLD_TEXT), len(NEW_TEXT)))
    after = NEW_TEXT + " extra text" if same_timestamp else NEW_TEXT.ljust(len(before))
    timestamp = 1_700_000_000.25
    setup.path.write_text(before, encoding="utf-8")
    os.utime(setup.path, (timestamp, timestamp))
    assert setup.indexer.index_single_file(str(setup.path), force=True)
    setup.path.write_text(after, encoding="utf-8")
    changed_timestamp = timestamp if same_timestamp else timestamp + 0.5
    os.utime(setup.path, (changed_timestamp, changed_timestamp))

    assert setup.indexer.index_single_file(str(setup.path), force=False)

    assert setup.db.get_document_by_path(str(setup.path))["content_text"] == after
    assert setup.cache.search(vector(1))[0]["chunk_text"] == after.strip()


def test_unchanged_file_skips_extraction_and_embedding(setup):
    assert setup.indexer.index_single_file(str(setup.path), force=True)
    before_doc = setup.db.get_document_by_path(str(setup.path))
    before_chunks = chunk_rows(setup.db)
    setup.extract.reset_mock()
    setup.embed.reset_mock()

    assert not setup.indexer.index_single_file(str(setup.path), force=False)

    setup.extract.assert_not_called()
    setup.embed.assert_not_called()
    assert setup.db.get_document_by_path(str(setup.path)) == before_doc
    assert chunk_rows(setup.db) == before_chunks


def test_move_and_delete_events_refresh_existing_cache(setup, monkeypatch):
    module = importlib.import_module("rat.crawler.watcher")
    monkeypatch.setattr(module, "set_thread_qos_background", lambda: None)
    assert setup.indexer.index_single_file(str(setup.path), force=True)
    original = setup.cache.search(vector())[0]
    destination = setup.path.with_name("renamed.txt")
    setup.path.rename(destination)
    handler = RatFileEventHandler(setup.indexer, autostart=False)
    handler._poll_interval = 60
    handler.start()
    try:
        handler.on_moved(SimpleNamespace(
            src_path=str(setup.path), dest_path=str(destination), is_directory=False,
        ))
        assert str(destination) in handler._pending_files
        assert setup.cache.search(vector()) == []
        # Exercise the queued indexing action without a real filesystem observer.
        assert setup.indexer.index_single_file(str(destination), force=False)
        results = setup.cache.search(vector())
        assert len(results) == 1
        assert results[0]["file_path"] == str(destination)
        assert results[0]["file_name"] == destination.name
        assert results[0]["doc_id"] != original["doc_id"]
        assert results[0]["chunk_text"] == OLD_TEXT
        destination.unlink()
        handler.on_deleted(SimpleNamespace(src_path=str(destination), is_directory=False))
        assert setup.cache.search(vector()) == []
        assert setup.db.get_document_by_path(str(destination)) is None
        assert chunk_rows(setup.db) == []
    finally:
        handler.stop()
