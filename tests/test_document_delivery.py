"""Delivery means an actual local file reference, never an invented path or upload."""
import hashlib

import pytest

from rat.crawler.db import Database
from rat.kernel.capabilities import build_default_registry
from rat.kernel.contracts import ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.view_spec import StandardViewProvider, validate_view_spec


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'Bài đọc thật.txt'
    path.write_text('A real local file used by the delivery test.', encoding='utf-8')
    db = Database(str(tmp_path / 'index.db'))
    db.upsert_document({'file_path': str(path), 'file_name': path.name, 'file_ext': '.txt',
                        'file_size': path.stat().st_size, 'created_at': 1, 'modified_at': 1,
                        'indexed_at': 1, 'content_text': path.read_text()})
    registry, store = build_default_registry(db=db), ArtifactStore()
    yield path, registry, store, ActionDispatcher(registry, store)
    db.get_connection().close()


def test_delivers_original_existing_file_with_observed_identity_and_no_open(env, monkeypatch):
    path, registry, store, dispatcher = env
    monkeypatch.setattr('subprocess.run', lambda *a, **k: pytest.fail('delivery must not launch an application'))
    result = dispatcher.execute_operation('deliver_document', {'file_path': str(path)})
    assert result.status == 'success', result.error
    data = result.artifact.payload
    assert result.artifact.kind == 'document_file'
    assert data['path'] == str(path) and data['filename'] == path.name
    assert data['file_size'] == data['size_bytes'] == path.stat().st_size
    assert data['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert data['delivered'] and data['delivery'] == 'local_reference'
    assert store.get(result.artifact.id).payload == data
    spec = StandardViewProvider(registry).provide_view(result.artifact)
    assert validate_view_spec(spec, result.artifact, registry) == (True, None)


def test_unindexed_and_disappeared_files_never_become_delivered(env):
    path, _, store, dispatcher = env
    other = path.with_name('unindexed.txt')
    other.write_text('Do not deliver an unobserved source.')
    assert dispatcher.execute_operation('deliver_document', {'file_path': str(other)}).status == 'error'
    path.unlink()
    assert dispatcher.execute_operation('deliver_document', {'file_path': str(path)}).status == 'error'
    assert not store.list()


def test_cancelled_delivery_cannot_publish_an_attachment(env):
    path, _, store, dispatcher = env
    checks = []
    def cancelled():
        checks.append(True)
        return len(checks) > 1
    result = dispatcher.execute_operation('deliver_document', {'file_path': str(path)},
                                         context={'should_cancel': cancelled})
    assert result.status == 'cancelled' and not store.list()
