from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch

import pytest

from rat.crawler.db import Database


def test_constructor_defers_filesystem_and_schema_creation(tmp_path):
    path = tmp_path / "not_created" / "index.db"
    database = Database(str(path))
    assert not path.parent.exists()
    connection = database.get_connection()
    assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
    connection.close()


def test_concurrent_first_use_initializes_once(tmp_path):
    database = Database(str(tmp_path / "index.db"))

    def count_documents(unused):
        connection = database.get_connection()
        try:
            return connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        finally:
            connection.close()
            database._local.conn = None

    with patch.object(database, "init_db", wraps=database.init_db) as initialize:
        with ThreadPoolExecutor(max_workers=4) as workers:
            assert list(workers.map(count_documents, range(8))) == [0] * 8
        assert initialize.call_count == 1


@pytest.mark.parametrize("existing", [False, True])
def test_import_does_not_create_or_migrate_configured_database(tmp_path, existing):
    home = tmp_path / "home"
    home.mkdir()
    path = tmp_path / "selected.db"
    if existing:
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE sentinel (value TEXT)")
            connection.execute("INSERT INTO sentinel VALUES ('preserve')")
        before = hashlib.sha256(path.read_bytes()).hexdigest()
    environment = dict(os.environ, HOME=str(home), RAT_DB_PATH=str(path), PYTHONDONTWRITEBYTECODE="1")
    program = """
import json
from rat.config import config
from rat.crawler.db import Database
from rat.engine.vector_cache import vector_cache
from rat.crawler.dedup import dedup_engine
from rat.engine.hybrid_search import SearchEngine
Database(config.db_path)
SearchEngine()
print(json.dumps([config.db_path, vector_cache.db.db_path, dedup_engine.db.db_path]))
"""
    result = subprocess.run([sys.executable, "-c", program], cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [str(path)] * 3
    assert not (home / ".rat").exists()
    if existing:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    else:
        assert not path.exists()


def test_config_save_creates_directory_only_on_explicit_save(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    environment = dict(os.environ, HOME=str(home), RAT_DB_PATH=str(tmp_path / "selected.db"), PYTHONDONTWRITEBYTECODE="1")
    program = """
from pathlib import Path
from rat.config import config
assert not (Path.home() / '.rat').exists()
config.save()
assert (Path.home() / '.rat/config.json').is_file()
assert not Path(config.db_path).exists()
"""
    subprocess.run([sys.executable, "-c", program], cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, check=True)


def test_read_only_database_never_initializes_or_writes(tmp_path):
    path = tmp_path / "snapshot.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('preserve')")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    database = Database(str(path), read_only=True)
    with patch.object(database, "init_db", side_effect=AssertionError("no migration")):
        connection = database.get_connection()
        assert connection.execute("SELECT value FROM sentinel").fetchone()[0] == "preserve"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM sentinel")
    with pytest.raises(PermissionError, match="read-only"):
        database.init_db()
    connection.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_read_only_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing" / "index.db"
    database = Database(str(path), read_only=True)
    with pytest.raises(sqlite3.OperationalError):
        database.get_connection()
    assert not path.parent.exists()
