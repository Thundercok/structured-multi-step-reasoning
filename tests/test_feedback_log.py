import sqlite3
from types import SimpleNamespace

from rat.engine.feedback_log import FeedbackLog


def candidate(path="/test.pdf", **raw):
    return SimpleNamespace(file_path=path, raw_scores=raw, score=75.0, modified_at=100.0)


def rows(log, sql):
    with sqlite3.connect(log.path) as connection:
        return connection.execute(sql).fetchall()


def test_snapshot_before_click_and_preserve_ranking_feature(tmp_path):
    log = FeedbackLog(tmp_path / "feedback.db")
    first = log.record("test", [candidate(bm25=2.5, cosine=0.7, mrrf=93)], "test")
    assert log.action(first, "open", "/test.pdf")
    log.record("test", [candidate()], "test")
    log.record("test", [candidate(prior_opens=7)], "test")
    assert rows(log, "SELECT prior_opens FROM impression_items ORDER BY rowid") == [(0,), (1,), (7,)]
    assert rows(log, "SELECT bm25, cosine, mrrf, final_score FROM impression_items LIMIT 1") == [(2.5, 0.7, 93, 75)]


def test_context_raw_score_features_and_ranker_are_snapshotted(tmp_path):
    log = FeedbackLog(tmp_path / "feedback.db")
    item = candidate(raw_score=120.0, feats={"kw_stem": 80.0, "ext_hit": 35.0})
    impression = log.record("alpha pdf", [item], "spotlight", {"keywords": ["alpha"]})
    context, ranker, git_sha, k_shown = rows(
        log, "SELECT context, ranker, git_sha, k_shown FROM impressions"
    )[0]
    assert context == '{"keywords":["alpha"]}'
    assert ranker == "static_heuristic_v1"
    assert git_sha
    assert k_shown == 1
    assert rows(log, "SELECT final_score, raw_score, feats FROM impression_items") == [
        (75.0, 120.0, '{"kw_stem":80.0,"ext_hit":35.0}')
    ]


def test_legacy_database_is_migrated_without_losing_rows(tmp_path):
    path = tmp_path / "feedback.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE impressions (iid TEXT PRIMARY KEY, ts REAL NOT NULL, query TEXT NOT NULL, surface TEXT NOT NULL);
            CREATE TABLE impression_items (
                iid TEXT, rank INTEGER, file_path TEXT, bm25 REAL, cosine REAL, mrrf REAL,
                final_score REAL, age_days REAL, prior_opens INTEGER,
                PRIMARY KEY (iid, rank), UNIQUE (iid, file_path));
            CREATE TABLE actions (id INTEGER PRIMARY KEY, iid TEXT, ts REAL, kind TEXT, file_path TEXT);
            CREATE TABLE open_counts (file_path TEXT PRIMARY KEY, count INTEGER NOT NULL);
            INSERT INTO impressions VALUES ('old', 1, 'query', 'spotlight');
            INSERT INTO impression_items VALUES ('old', 1, '/old.pdf', NULL, NULL, NULL, 60, 1, 0);
        """)
    log = FeedbackLog(path)
    new_id = log.record("new", [candidate(raw_score=70, feats={"kw_content": 65})], "omnibar")
    assert new_id
    assert rows(log, "SELECT final_score, raw_score, feats FROM impression_items WHERE iid='old'") == [
        (60.0, 5.0, "{}")
    ]
    assert rows(log, f"SELECT raw_score, feats FROM impression_items WHERE iid='{new_id}'") == [
        (70.0, '{"kw_content":65}')
    ]


def test_actions_none_and_invalid_path_are_atomic(tmp_path):
    log = FeedbackLog(tmp_path / "feedback.db")
    impression = log.record("test", [candidate()], "test")
    assert not log.action(impression, "open", "/absent.pdf")
    assert rows(log, "SELECT * FROM open_counts") == []
    assert log.action(impression, "reveal", "/test.pdf")
    assert log.action(impression, "terminal", "/test.pdf")
    assert not log.action(impression, "none")
    assert rows(log, "SELECT * FROM open_counts") == []
    dismissed = log.record("test", [candidate()], "test")
    assert log.action(dismissed, "none")
    assert not log.action(dismissed, "none")
    assert rows(log, "SELECT kind FROM actions") == [("reveal",), ("terminal",), ("none",)]


def test_virtual_entries_preserve_display_positions(tmp_path):
    log = FeedbackLog(tmp_path / "feedback.db")
    log.record("test", [candidate("rat://calc_copy/4"), candidate(), candidate()], "test")
    assert rows(log, "SELECT rank, file_path, bm25 FROM impression_items") == [(2, "/test.pdf", None)]


def test_record_rolls_back_and_failure_does_not_escape(tmp_path):
    log = FeedbackLog(tmp_path / "feedback.db")
    assert log.record("test", [candidate(), SimpleNamespace(file_path="/broken")], "test") is None
    assert rows(log, "SELECT * FROM impressions") == []
    assert rows(log, "SELECT * FROM impression_items") == []
    assert FeedbackLog(tmp_path).record("test", [candidate()], "test") is None


def test_retention_does_not_rewrite_snapshots(tmp_path):
    log = FeedbackLog(tmp_path / "feedback.db")
    first = log.record("test", [candidate()], "test")
    log.action(first, "open", "/test.pdf")
    log.record("test", [candidate()], "test")
    with sqlite3.connect(log.path) as connection:
        connection.execute("DELETE FROM actions")
    assert rows(log, "SELECT prior_opens FROM impression_items ORDER BY rowid") == [(0,), (1,)]
