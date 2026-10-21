"""Resident warmup guards; no windows, threads, indexing or model calls."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('reason', ['disabled', 'empty', 'quitting', 'running'])
def test_blocked_warmup_does_not_start_worker(monkeypatch, reason):
    from rat.os import app as resident
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'auto_watch', reason != 'disabled')
    monkeypatch.setattr(config, 'indexed_directories', [] if reason == 'empty' else ['/synthetic/HK242'])
    thread = Mock()
    monkeypatch.setattr(QtCore, 'QThread', thread)
    state = SimpleNamespace(app=SimpleNamespace(_is_quitting=reason == 'quitting'),
                            warmup_thread=Mock(isRunning=lambda: reason == 'running'))
    resident.ResidentApplication._start_semester_warmup(state)
    thread.assert_not_called()


def test_permitted_warmup_starts_one_worker(monkeypatch):
    from rat.os import app as resident
    from rat.crawler import warmup
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'auto_watch', True)
    monkeypatch.setattr(config, 'indexed_directories', ['/synthetic/HK242'])
    thread = Mock()
    worker = Mock()
    monkeypatch.setattr(QtCore, 'QThread', thread)
    monkeypatch.setattr(warmup, 'SemesterWarmupWorker', worker)
    state = SimpleNamespace(app=SimpleNamespace(_is_quitting=False), warmup_thread=None)
    resident.ResidentApplication._start_semester_warmup(state)
    worker.return_value.moveToThread.assert_called_once_with(thread.return_value)
    thread.return_value.start.assert_called_once()
