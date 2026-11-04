"""The status line says how far the meaning index has read, and hides when it is done."""
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtTest import QTest

from tests.test_quick_unified_flow import app, quick_env, wait_for  # noqa: F401


class FakeIndex:
    def __init__(self, env):
        self.state = {"state": "idle", "done": 0, "total": 0}
        env.controller._finder_semantic = self

    def progress(self):
        return dict(self.state)


def status_text(env):
    QTest.qWait(30)
    return env.root.findChild(QQuickItem, "composerDropStatus").property("text")


def test_status_follows_scanning_then_reading_then_hides(quick_env):
    control = quick_env.controller
    index = FakeIndex(quick_env)

    index.state = {"state": "scanning", "done": 0, "total": 0}
    control.refresh_index_progress()
    assert "xem qua các thư mục" in status_text(quick_env)

    index.state = {"state": "indexing", "done": 120, "total": 327}
    control.refresh_index_progress()
    assert "120/327" in status_text(quick_env)

    index.state = {"state": "ready", "done": 327, "total": 327}
    control.refresh_index_progress()
    assert control.snapshot["indexStatus"] == ""
    assert "327" not in status_text(quick_env)


def test_a_failed_index_does_not_stay_on_screen(quick_env):
    control = quick_env.controller
    index = FakeIndex(quick_env)
    index.state = {"state": "indexing", "done": 1, "total": 2}
    control.refresh_index_progress()
    index.state = {"state": "unavailable", "done": 0, "total": 0}
    control.refresh_index_progress()
    assert control.snapshot["indexStatus"] == ""


def test_unchanged_progress_does_not_rebuild_the_desk(quick_env):
    control = quick_env.controller
    index = FakeIndex(quick_env)
    index.state = {"state": "indexing", "done": 1, "total": 2}
    control.refresh_index_progress()
    emitted = []
    control.changed.connect(lambda: emitted.append(True))
    control.refresh_index_progress()
    assert emitted == []


def test_progress_shows_beside_search_hints_but_not_over_an_answer(quick_env):
    control = quick_env.controller
    index = FakeIndex(quick_env)
    index.state = {"state": "indexing", "done": 5, "total": 9}
    control.refresh_index_progress()
    control._last_assistant_answer = "câu trả lời"
    control._view = "answer"
    control.changed.emit()
    assert "5/9" in status_text(quick_env)

    control._view = "none"
    control._finder_feedback = "Không tìm thấy gì"
    control.changed.emit()
    assert "Không tìm thấy" in status_text(quick_env)
