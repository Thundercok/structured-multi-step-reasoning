"""Local impression snapshots and actions, isolated from the search index."""

from __future__ import annotations

import logging
import json
import sqlite3
import subprocess
import time
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("rat.feedback")
RANKER_VERSION = "static_heuristic_v1"


@lru_cache(maxsize=1)
def _git_sha():
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=0.5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


class FeedbackLog:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path.home() / ".rat" / "feedback.db"

    @contextmanager
    def _connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=0.1)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS impressions (
                    iid TEXT PRIMARY KEY, ts REAL NOT NULL,
                    query TEXT NOT NULL, surface TEXT NOT NULL,
                    context TEXT NOT NULL DEFAULT '{}',
                    ranker TEXT NOT NULL DEFAULT 'static_heuristic_v1',
                    git_sha TEXT NOT NULL DEFAULT 'unknown',
                    k_shown INTEGER NOT NULL DEFAULT 0,
                    latency_ms REAL
                );
                CREATE TABLE IF NOT EXISTS impression_items (
                    iid TEXT REFERENCES impressions(iid) ON DELETE CASCADE,
                    rank INTEGER NOT NULL, file_path TEXT NOT NULL,
                    bm25 REAL, cosine REAL, mrrf REAL, final_score REAL,
                    age_days REAL, prior_opens INTEGER NOT NULL,
                    raw_score REAL NOT NULL DEFAULT 5.0,
                    feats TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (iid, rank), UNIQUE (iid, file_path)
                );
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY, iid TEXT NOT NULL REFERENCES impressions(iid),
                    ts REAL NOT NULL, kind TEXT NOT NULL
                        CHECK(kind IN ('open', 'reveal', 'terminal', 'none')),
                    file_path TEXT,
                    FOREIGN KEY (iid, file_path) REFERENCES impression_items(iid, file_path)
                );
                CREATE INDEX IF NOT EXISTS actions_impression ON actions(iid);
                CREATE TABLE IF NOT EXISTS open_counts (
                    file_path TEXT PRIMARY KEY, count INTEGER NOT NULL
                );
            """)
            self._ensure_column(connection, "impressions", "context", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(connection, "impressions", "ranker", "TEXT NOT NULL DEFAULT 'static_heuristic_v1'")
            self._ensure_column(connection, "impressions", "git_sha", "TEXT NOT NULL DEFAULT 'unknown'")
            self._ensure_column(connection, "impressions", "k_shown", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "impressions", "latency_ms", "REAL")
            self._ensure_column(connection, "impression_items", "raw_score", "REAL NOT NULL DEFAULT 5.0")
            self._ensure_column(connection, "impression_items", "feats", "TEXT NOT NULL DEFAULT '{}'")
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _ensure_column(connection, table, column, declaration):
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def record(self, query, candidates, surface, context=None, latency_ms=None):
        """Snapshot displayed order before any action; preserve supplied ranking features."""
        try:
            timestamp = time.time()
            impression_id = uuid.uuid4().hex
            if context is None:
                context_data = {}
            elif hasattr(context, "to_dict"):
                context_data = context.to_dict()
            elif isinstance(context, dict):
                context_data = context
            else:
                context_data = vars(context)
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO impressions "
                    "(iid, ts, query, surface, context, ranker, git_sha, k_shown, latency_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (impression_id, timestamp, query, surface,
                     json.dumps(context_data, ensure_ascii=False, default=str, separators=(",", ":")),
                     RANKER_VERSION, _git_sha(), len(candidates), latency_ms),
                )
                rows = []
                seen = set()
                for rank, candidate in enumerate(candidates, 1):
                    path = candidate.file_path
                    if not path or path.startswith("rat://") or path in seen:
                        continue
                    seen.add(path)
                    raw = getattr(candidate, "raw_scores", {})
                    prior_opens = raw.get("prior_opens")
                    if prior_opens is None:
                        previous = connection.execute(
                            "SELECT count FROM open_counts WHERE file_path=?", (path,)
                        ).fetchone()
                        prior_opens = previous[0] if previous else 0
                    rows.append((
                        impression_id, rank, path, raw.get("bm25"), raw.get("cosine"),
                        raw.get("mrrf"), candidate.score, (timestamp - candidate.modified_at) / 86400.0,
                        prior_opens, raw.get("raw_score", candidate.score),
                        json.dumps(raw.get("feats", {}), ensure_ascii=False,
                                   separators=(",", ":")),
                    ))
                connection.executemany(
                    "INSERT INTO impression_items "
                    "(iid, rank, file_path, bm25, cosine, mrrf, final_score, age_days, prior_opens, raw_score, feats) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows,
                )
            return impression_id
        except Exception:
            logger.warning("Could not record feedback impression", exc_info=True)
            return None

    def action(self, impression_id, kind, file_path=None):
        if not impression_id:
            return False
        try:
            if kind not in {"open", "reveal", "terminal", "none"}:
                raise ValueError("Unknown feedback action")
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if kind == "none":
                    file_path = None
                    if connection.execute("SELECT 1 FROM actions WHERE iid=?", (impression_id,)).fetchone():
                        return False
                elif not file_path:
                    return False
                connection.execute("INSERT INTO actions(iid, ts, kind, file_path) VALUES (?, ?, ?, ?)",
                                   (impression_id, time.time(), kind, file_path))
                if kind == "open":
                    connection.execute("""
                        INSERT INTO open_counts VALUES (?, 1)
                        ON CONFLICT(file_path) DO UPDATE SET count=count+1
                    """, (file_path,))
            return True
        except Exception:
            logger.warning("Could not record feedback action", exc_info=True)
            return False
