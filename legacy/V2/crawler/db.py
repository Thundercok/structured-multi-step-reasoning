"""
db.py — thread-safe SQLite persistence layer.

Each thread gets its own connection via threading.local so SQLite's
check_same_thread constraint is never violated. Writes are serialised
through a single lock so concurrent inserts don't interleave.
"""

import csv
import json
import sqlite3
import threading

DB_FILE = "crawler_results.db"

_local = threading.local()
_write_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    """Return (or create) a thread-local SQLite connection."""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_FILE, check_same_thread=True)
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                url   TEXT UNIQUE,
                title TEXT,
                depth INTEGER,
                ts    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _local.conn.commit()
    return _local.conn


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert(url: str, title: str, depth: int) -> None:
    """Insert or replace a crawled URL record."""
    with _write_lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO results (url, title, depth) VALUES (?, ?, ?)",
            (url, title, depth),
        )
        c.commit()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_csv(path: str) -> int:
    """Write all results to *path* as CSV. Returns the row count."""
    rows = _conn().execute(
        "SELECT url, title, depth, ts FROM results ORDER BY id"
    ).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "title", "depth", "timestamp"])
        writer.writerows(rows)
    return len(rows)


def export_json(path: str) -> int:
    """Write all results to *path* as JSON. Returns the record count."""
    rows = _conn().execute(
        "SELECT url, title, depth, ts FROM results ORDER BY id"
    ).fetchall()
    data = [
        {"url": r[0], "title": r[1], "depth": r[2], "timestamp": r[3]}
        for r in rows
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return len(data)
