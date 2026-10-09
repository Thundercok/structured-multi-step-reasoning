"""Watcher regressions using fake observers and temporary files only."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from watchdog.observers.api import BaseObserver, EventEmitter

from rat.crawler import watcher as watcher_module


class FakeObserver:
    def __init__(self, *, block_start=False, fail_start=False):
        self.start_entered = threading.Event()
        self.release_start = threading.Event()
        if not block_start:
            self.release_start.set()
        self.fail_start = fail_start
        self.start_calls = 0
        self.stop_calls = 0
        self.scheduled = []
        self._alive = False

    def schedule(self, handler, path, recursive):
        self.scheduled.append((handler, path, recursive))

    def start(self):
        self.start_calls += 1
        self.start_entered.set()
        assert self.release_start.wait(5), "test did not release observer startup"
        # Simulate an observer becoming active after an earlier stop request.
        self._alive = True
        if self.fail_start:
            raise RuntimeError("simulated observer startup failure")

    def stop(self):
        self.stop_calls += 1
        self._alive = False

    def join(self, timeout):
        pass

    def is_alive(self):
        return self._alive


@pytest.fixture
def indexer():
    return SimpleNamespace(
        is_ignored=lambda path: False,
        index_single_file=Mock(return_value=True),
        db=SimpleNamespace(delete_document=Mock()),
    )


@pytest.fixture(autouse=True)
def disable_platform_services(monkeypatch):
    monkeypatch.setattr(watcher_module, "set_thread_qos_background", lambda: None)
    monkeypatch.setattr(watcher_module, "is_on_battery", lambda: False)


def assert_stopped(watcher):
    assert not watcher.is_running
    assert not watcher.observer.is_alive()
    assert watcher.handler._stop_event.is_set()
    worker = watcher.handler._worker_thread
    assert worker is None or not worker.is_alive()
    assert watcher._startup_thread is None or not watcher._startup_thread.is_alive()


def test_stop_before_start_does_not_leave_a_queue_thread(monkeypatch, indexer):
    observer = FakeObserver()
    monkeypatch.setattr(watcher_module, "Observer", lambda: observer)
    watcher = watcher_module.FolderWatcher(indexer)
    assert watcher.handler._worker_thread is None
    watcher.stop()
    watcher.stop()
    assert_stopped(watcher)
    assert observer.start_calls == 0


def test_start_after_stop_before_first_start_uses_live_watchdog_observer(monkeypatch, indexer):
    observers = []

    def make_observer():
        # No watches are scheduled: exercise watchdog's thread lifecycle only.
        observer = BaseObserver(EventEmitter, timeout=0.1)
        observers.append(observer)
        return observer

    monkeypatch.setattr(watcher_module, "Observer", make_observer)
    watcher = watcher_module.FolderWatcher(indexer)
    try:
        watcher.stop()
        watcher.start([])
        watcher._startup_thread.join(2)
        assert watcher.is_running
        assert len(observers) == 2
        assert watcher.observer.is_alive()
        assert watcher.handler._worker_thread.is_alive()
    finally:
        watcher.stop()
    assert_stopped(watcher)


def test_stop_during_startup_cleans_up_observer_and_queue(monkeypatch, indexer, tmp_path):
    observer = FakeObserver(block_start=True)
    monkeypatch.setattr(watcher_module, "Observer", lambda: observer)
    watcher = watcher_module.FolderWatcher(indexer)
    watcher.start([str(tmp_path)])
    assert observer.start_entered.wait(2)
    stopped = threading.Event()

    def stop_watcher():
        watcher.stop()
        stopped.set()

    stop_thread = threading.Thread(target=stop_watcher)
    stop_thread.start()
    try:
        assert watcher._stop_event.wait(2)
        observer.release_start.set()
        assert stopped.wait(2)
        assert_stopped(watcher)
    finally:
        observer.release_start.set()
        stop_thread.join(3)
        watcher.stop()


def test_duplicate_start_calls_share_one_startup(monkeypatch, indexer, tmp_path):
    observer = FakeObserver(block_start=True)
    monkeypatch.setattr(watcher_module, "Observer", lambda: observer)
    watcher = watcher_module.FolderWatcher(indexer)
    try:
        watcher.start([str(tmp_path)])
        assert observer.start_entered.wait(2)
        startup = watcher._startup_thread
        watcher.start([str(tmp_path)])
        assert watcher._startup_thread is startup
        assert observer.start_calls == 1
        assert len(observer.scheduled) == 1
        observer.release_start.set()
        startup.join(2)
        assert watcher.is_running
        watcher.start([str(tmp_path)])
        assert observer.start_calls == 1
    finally:
        observer.release_start.set()
        watcher.stop()
    assert_stopped(watcher)


def test_stop_during_scheduling_does_not_start_background_services(monkeypatch, indexer, tmp_path):
    observer = FakeObserver()
    scheduling = threading.Event()
    release_schedule = threading.Event()

    def schedule(handler, path, recursive):
        scheduling.set()
        assert release_schedule.wait(5)

    observer.schedule = schedule
    monkeypatch.setattr(watcher_module, "Observer", lambda: observer)
    watcher = watcher_module.FolderWatcher(indexer)
    watcher.start([str(tmp_path)])
    assert scheduling.wait(2)
    stop_thread = threading.Thread(target=watcher.stop)
    stop_thread.start()
    try:
        assert watcher._stop_event.wait(2)
        watcher.start([str(tmp_path)])
        release_schedule.set()
        stop_thread.join(2)
        assert not stop_thread.is_alive()
        assert_stopped(watcher)
        assert observer.start_calls == 0
        assert watcher.handler._worker_thread is None
    finally:
        release_schedule.set()
        stop_thread.join(3)
        watcher.stop()


def test_start_failure_stops_partial_observer_and_queue(monkeypatch, indexer, tmp_path, caplog):
    observer = FakeObserver(fail_start=True)
    monkeypatch.setattr(watcher_module, "Observer", lambda: observer)
    watcher = watcher_module.FolderWatcher(indexer)
    try:
        watcher.start([str(tmp_path)])
        watcher._startup_thread.join(2)
        assert_stopped(watcher)
        assert observer.stop_calls >= 1
        assert "simulated observer startup failure" in caplog.text
    finally:
        watcher.stop()


@pytest.mark.parametrize("fail_first", [False, True])
def test_restart_uses_a_fresh_observer(monkeypatch, indexer, tmp_path, fail_first):
    observers = []

    def make_observer():
        observer = FakeObserver(fail_start=fail_first and not observers)
        observers.append(observer)
        return observer

    monkeypatch.setattr(watcher_module, "Observer", make_observer)
    watcher = watcher_module.FolderWatcher(indexer)
    try:
        watcher.start([str(tmp_path)])
        watcher._startup_thread.join(2)
        first_worker = watcher.handler._worker_thread
        watcher.stop()
        assert_stopped(watcher)
        watcher.start([str(tmp_path)])
        watcher._startup_thread.join(2)
        assert watcher.is_running
        assert len(observers) == 2
        assert observers[0].start_calls == observers[1].start_calls == 1
        assert watcher.handler._worker_thread is not first_worker
    finally:
        watcher.stop()
    assert_stopped(watcher)


def test_explicit_empty_directories_do_not_watch_configured_folders(monkeypatch, indexer, tmp_path):
    observer = FakeObserver()
    monkeypatch.setattr(watcher_module, "Observer", lambda: observer)
    monkeypatch.setattr(watcher_module.config, "indexed_directories", [str(tmp_path)])
    watcher = watcher_module.FolderWatcher(indexer)
    try:
        watcher.start([])
        watcher._startup_thread.join(2)
        assert observer.scheduled == []
    finally:
        watcher.stop()


def test_queue_survives_one_file_error_and_indexes_the_next(indexer, tmp_path, caplog):
    first, second = tmp_path / "broken.txt", tmp_path / "next.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    processed = threading.Event()

    def index_file(path, force):
        if path == str(first):
            raise RuntimeError("simulated individual file failure")
        processed.set()
        return True

    indexer.index_single_file.side_effect = index_file
    handler = watcher_module.RatFileEventHandler(indexer, debounce_seconds=0, autostart=False)
    handler._poll_interval = 0.01
    try:
        handler.start()
        handler._queue_file(str(first))
        handler._queue_file(str(second))
        assert processed.wait(2)
        assert handler._worker_thread.is_alive()
        assert "simulated individual file failure" in caplog.text
    finally:
        handler.stop()
    assert not handler._worker_thread.is_alive()


def test_stop_interrupts_queue_wait_and_rejects_late_events(indexer, tmp_path):
    handler = watcher_module.RatFileEventHandler(indexer, autostart=False)
    handler._poll_interval = 60
    handler.start()
    handler._queue_file(str(tmp_path / "before.txt"))
    worker = handler._worker_thread
    handler.stop(timeout=0.5)
    assert not worker.is_alive()
    assert handler._pending_files == {}
    handler._queue_file(str(tmp_path / "after.txt"))
    event = SimpleNamespace(src_path=str(tmp_path / "before.txt"), dest_path=str(tmp_path / "after.txt"), is_directory=False)
    handler.on_deleted(event)
    handler.on_moved(event)
    assert handler._pending_files == {}
    indexer.index_single_file.assert_not_called()
    indexer.db.delete_document.assert_not_called()


def test_moved_file_delete_error_does_not_drop_destination(indexer, tmp_path, caplog):
    handler = watcher_module.RatFileEventHandler(indexer, autostart=False)
    handler._poll_interval = 60
    indexer.db.delete_document.side_effect = RuntimeError("simulated delete failure")
    handler.start()
    destination = str(tmp_path / "destination.txt")
    try:
        handler.on_moved(SimpleNamespace(src_path=str(tmp_path / "source.txt"), dest_path=destination, is_directory=False))
        assert destination in handler._pending_files
        assert "simulated delete failure" in caplog.text
    finally:
        handler.stop()
