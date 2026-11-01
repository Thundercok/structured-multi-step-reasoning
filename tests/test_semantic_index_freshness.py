"""Tests for semantic index freshness and query non-interference."""
import time
from pathlib import Path
import pytest
from rat.engine.semantic_index import SemanticIndex, file_identity


class DummyEmbedder:
    def __init__(self):
        self.load_count = 0
        self.texts_embedded = []

    def embed_texts(self, texts, batch_size=8):
        import numpy as np
        self.load_count += 1
        self.texts_embedded.extend(texts)
        return np.ones((len(texts), 384), dtype=np.float32)

    def embed_query(self, query):
        import numpy as np
        return np.ones(384, dtype=np.float32)

    def evict(self):
        pass


def test_cheap_identity_check_does_not_call_embedder_when_unchanged(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    doc = root / "sample.txt"
    doc.write_text("Hello world this is a test document.")

    embedder = DummyEmbedder()
    db_path = tmp_path / "test-index.sqlite"
    index = SemanticIndex(db_path, embedder=embedder)

    # First pass: indexes the file
    assert index.start([root]) is True
    index._thread.join(timeout=5)
    assert embedder.load_count > 0
    assert index.count() == 1

    # Second pass: nothing changed, identity matches
    embedder.load_count = 0
    assert index.start([root]) is True
    index._thread.join(timeout=5)
    # Embedder must not have been called because file identity did not change!
    assert embedder.load_count == 0
    progress = index.progress()
    assert progress['state'] == 'ready'


def test_index_does_not_start_while_query_is_active(tmp_path):
    db_path = tmp_path / "test-index.sqlite"
    embedder = DummyEmbedder()
    index = SemanticIndex(db_path, embedder=embedder)

    with index._lock:
        index._active_queries += 1
    try:
        assert index.start([tmp_path]) is False
    finally:
        with index._lock:
            index._active_queries -= 1

    assert index.start([tmp_path]) is True
    index._thread.join(timeout=5)


def test_controller_panel_open_throttles_indexing(tmp_path, monkeypatch):
    from rat.ui.mini_quick_controller import MiniQuickController
    from rat.engine.mini_settings import DEFAULTS

    monkeypatch.setenv("RAT_MINI_STATE_DIR", str(tmp_path / "state"))
    root = tmp_path / "files"
    root.mkdir()

    controller = MiniQuickController(dict(DEFAULTS, roots=[str(root)]))
    # First panel_open starts indexing
    started = controller.start_indexing(reason='panel_open')
    assert started is True

    # Immediate second panel_open is throttled (cheap identity, avoids thrashing)
    second = controller.start_indexing(reason='panel_open')
    assert second is False
