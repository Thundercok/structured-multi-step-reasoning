from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from rat.crawler.db import Database
from scripts.repair_index_links import audit_index, inspect_links, repair_copy


@pytest.fixture
def corrupt_index(tmp_path):
    path = tmp_path / "source.db"
    database = Database(str(path))
    parents = {}
    for name in ("first", "second", "third"):
        parents[name] = database.upsert_document(dict(
            file_path=f"/{name}.pdf", file_name=f"{name}.pdf", file_ext=".pdf",
            file_size=1, created_at=1, modified_at=1, indexed_at=1, content_text=name,
        ))
    connection = database.get_connection()
    connection.executemany(
        "INSERT INTO document_chunks (doc_id, file_path, chunk_index, chunk_text, embedding) VALUES (?,?,?,?,?)",
        [(parents["second"], "/first.pdf", 0, "first text", b"first vector"),
         (parents["second"], "/second.pdf", 0, "second text", b"second vector"),
         (99999, "/third.pdf", 0, "third text", b"third vector"),
         (None, "/removed.pdf", 0, "missing parent text", b"preserve vector")],
    )
    connection.commit()
    connection.close()
    return path


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(connection, table):
    return connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()


def test_audit_is_read_only_and_classifies_corruption(corrupt_index):
    before = fingerprint(corrupt_index)
    report = audit_index(corrupt_index)
    assert report["status"] == "audit_only"
    assert report["counts"] == dict(
        documents=3, chunks=4, orphan_chunks=2, mismatched_path_chunks=1,
        recoverable_by_path=2, without_document_path=1,
    )
    assert fingerprint(corrupt_index) == before


def test_copy_repairs_links_and_preserves_all_text_and_vectors(corrupt_index, tmp_path):
    before = fingerprint(corrupt_index)
    output = tmp_path / "repaired.db"
    report = repair_copy(corrupt_index, output)
    assert report["relinked_chunks"] == 2
    assert report["quarantined_chunks"] == 1
    assert report["after"]["orphan_chunks"] == report["after"]["mismatched_path_chunks"] == 0
    assert report["output_sha256"] == fingerprint(output)
    assert fingerprint(corrupt_index) == before
    with closing(sqlite3.connect(corrupt_index)) as original, closing(sqlite3.connect(output)) as repaired:
        assert rows(original, "documents") == rows(repaired, "documents")
        fields = "id, file_path, chunk_index, chunk_text, embedding"
        source_payload = original.execute(f"SELECT {fields} FROM document_chunks ORDER BY id").fetchall()
        repaired_payload = repaired.execute(
            f"SELECT {fields} FROM document_chunks UNION ALL SELECT {fields} FROM quarantined_document_chunks ORDER BY id"
        ).fetchall()
        assert source_payload == repaired_payload
        assert repaired.execute("SELECT doc_id, reason FROM quarantined_document_chunks").fetchall() == [(None, "no_document_for_path")]


@pytest.mark.parametrize("destination", ["source", "existing", "symlink"])
def test_never_overwrites_source_or_existing_output(corrupt_index, tmp_path, destination):
    before = fingerprint(corrupt_index)
    output = tmp_path / "existing.db"
    if destination == "source":
        output = corrupt_index
    elif destination == "symlink":
        output.symlink_to(corrupt_index)
    else:
        output.write_bytes(b"keep this file")
    with pytest.raises((ValueError, FileExistsError)):
        repair_copy(corrupt_index, output)
    assert fingerprint(corrupt_index) == before
    if destination == "existing":
        assert output.read_bytes() == b"keep this file"


def test_repair_is_logically_idempotent(corrupt_index, tmp_path):
    first, second = tmp_path / "first.db", tmp_path / "second.db"
    repair_copy(corrupt_index, first)
    report = repair_copy(first, second)
    assert report["relinked_chunks"] == report["quarantined_chunks"] == 0
    with closing(sqlite3.connect(first)) as left, closing(sqlite3.connect(second)) as right:
        for table in ("documents", "document_chunks", "quarantined_document_chunks"):
            assert rows(left, table) == rows(right, table)


def test_failure_rolls_back_all_changes_in_copy(corrupt_index, tmp_path):
    with closing(sqlite3.connect(corrupt_index)) as connection:
        connection.execute("""
            CREATE TRIGGER reject_repair BEFORE UPDATE ON document_chunks
            BEGIN SELECT RAISE(ABORT, 'reject repair'); END
        """)
        connection.commit()
    before = fingerprint(corrupt_index)
    output = tmp_path / "failed.db"
    with pytest.raises(sqlite3.IntegrityError, match="reject repair"):
        repair_copy(corrupt_index, output)
    assert fingerprint(corrupt_index) == before
    with closing(sqlite3.connect(output)) as connection:
        assert inspect_links(connection) == audit_index(corrupt_index)["counts"]
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='quarantined_document_chunks'").fetchone() is None


def test_backup_includes_committed_wal_rows(corrupt_index, tmp_path):
    with closing(sqlite3.connect(corrupt_index)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE document_chunks SET chunk_text='committed WAL text' WHERE file_path='/first.pdf'")
        writer.commit()
        output = tmp_path / "wal-copy.db"
        repair_copy(corrupt_index, output)
        with closing(sqlite3.connect(output)) as connection:
            assert connection.execute("SELECT chunk_text FROM document_chunks WHERE file_path='/first.pdf'").fetchone()[0] == "committed WAL text"


def test_cli_defaults_to_audit_without_application_startup(corrupt_index):
    before = fingerprint(corrupt_index)
    script = Path(__file__).resolve().parents[1] / "scripts/repair_index_links.py"
    result = subprocess.run([sys.executable, str(script), "--db", str(corrupt_index)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["status"] == "audit_only"
    assert result.stderr == ""
    assert fingerprint(corrupt_index) == before
