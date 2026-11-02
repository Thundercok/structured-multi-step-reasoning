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


def _wait_idle(index):
    import time
    index._thread.join(timeout=10)
    assert not index._thread.is_alive()


def test_ocr_pass_reads_scanned_pdfs_once(tmp_path, monkeypatch):
    import rat.engine.semantic_index as module
    root = tmp_path / 'docs'; root.mkdir()
    (root / 'scan_0012.pdf').write_bytes(b'%PDF-1.4 scanned')
    calls = []

    def fake_read(path, limit=1800, ocr=False):
        calls.append(ocr)
        return 'Lịch thi học kỳ một, môn Giải tích, phòng A305, thứ Hai ngày mười hai.' if ocr else ''

    monkeypatch.setattr(module, 'read_document_text', fake_read)
    monkeypatch.setattr(module, 'OCR_PAUSE_S', 0)
    index = module.SemanticIndex(tmp_path / 'index.sqlite', embedder=DummyEmbedder())
    index.start([root]); _wait_idle(index)
    assert calls == [False, True]
    with index._connect() as db:
        texts = [r[0] for r in db.execute('SELECT chunk_text FROM chunks ORDER BY chunk_index')]
    assert len(texts) == 2 and 'Giải tích' in texts[1]
    index.start([root]); _wait_idle(index)
    assert calls == [False, True]


def test_startup_indexing_retries_while_a_job_is_running(tmp_path, monkeypatch):
    monkeypatch.setenv('RAT_MINI_STATE_DIR', str(tmp_path))
    from PyQt6.QtCore import QCoreApplication, QTimer
    from rat.engine.mini_settings import DEFAULTS
    from rat.ui.mini_quick_controller import MiniQuickController
    app = QCoreApplication.instance() or QCoreApplication([])
    controller = MiniQuickController(dict(DEFAULTS, roots=[]))
    scheduled = []
    monkeypatch.setattr(QTimer, 'singleShot', lambda ms, fn: scheduled.append(ms))
    controller.job = object()
    assert controller.start_indexing() is False
    assert scheduled == [2000]
    scheduled.clear()
    assert controller.start_indexing(reason='panel_open') is False
    assert scheduled == []
    controller.job = None

