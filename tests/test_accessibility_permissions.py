"""Permission/shortcut contracts with API doubles; never prompt or grant macOS access."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rat.os import permissions


@pytest.fixture
def api(monkeypatch):
    bridge = SimpleNamespace(AXIsProcessTrusted=Mock(return_value=False),
                             AXIsProcessTrustedWithOptions=Mock(return_value=False),
                             kAXTrustedCheckOptionPrompt='actual-exported-constant')
    monkeypatch.setattr(permissions.sys, 'platform', 'darwin')
    monkeypatch.setitem(sys.modules, 'ApplicationServices', bridge)
    return bridge


def test_check_does_not_prompt(api):
    assert permissions.accessibility_status().state == 'not_granted'
    api.AXIsProcessTrustedWithOptions.assert_not_called()


def test_prompt_is_dispatched_not_claimed_as_granted(api):
    result = permissions.request_accessibility_permission()
    assert result.prompt_requested and not result.trusted
    assert result.state == 'not_granted'
    api.AXIsProcessTrustedWithOptions.assert_called_once_with({'actual-exported-constant': True})


def test_granted_check(api):
    api.AXIsProcessTrusted.return_value = True
    assert permissions.is_accessibility_trusted()


def test_bridge_failure_is_distinct_and_logged(api, caplog):
    api.AXIsProcessTrustedWithOptions.side_effect = RuntimeError('fixture bridge failure')
    result = permissions.request_accessibility_permission()
    assert result.state == 'unavailable' and not result.prompt_requested
    assert 'RuntimeError' in result.error and 'fixture bridge failure' in caplog.text


def test_open_settings_failure_is_reported(api, monkeypatch):
    monkeypatch.setattr(permissions.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=1, stderr='fixture launch error'))
    assert permissions.open_accessibility_settings() is False


def test_reset_stale_accessibility_entry(monkeypatch):
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stderr='')
    monkeypatch.setattr(permissions.sys, 'platform', 'darwin')
    monkeypatch.setattr(permissions.subprocess, 'run', fake_run)
    assert permissions.reset_stale_accessibility_entry('vn.rat.mini') is True
    assert calls == [['/usr/bin/tccutil', 'reset', 'Accessibility', 'vn.rat.mini']]


def test_open_accessibility_settings_resets_stale_when_untrusted(api, monkeypatch):
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stderr='')
    monkeypatch.setattr(permissions, 'is_accessibility_trusted', lambda: False)
    monkeypatch.setattr(permissions.subprocess, 'run', fake_run)
    assert permissions.open_accessibility_settings() is True
    assert ['/usr/bin/tccutil', 'reset', 'Accessibility', 'vn.rat.mini'] in calls
    assert ['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'] in calls


@pytest.fixture
def hotkeys(monkeypatch):
    from rat.os import hotkey
    manager = hotkey.GlobalHotkeyManager()
    manager._start_permission_monitor = Mock()
    factory = Mock()
    factory.return_value.start = Mock()
    factory.return_value.stop = Mock()
    monkeypatch.setitem(sys.modules, 'pynput', SimpleNamespace(keyboard=SimpleNamespace(GlobalHotKeys=factory)))
    return hotkey, manager, factory


def test_denied_permission_starts_no_listener(hotkeys, monkeypatch):
    module, manager, factory = hotkeys
    monkeypatch.setattr(module, 'is_accessibility_trusted', lambda: False)
    monkeypatch.setattr(module, 'request_accessibility_permission', lambda: permissions.AccessibilityStatus(False, 'not_granted', True))
    assert manager.start() is False
    assert manager.status == 'waiting_permission' and not manager._running
    factory.assert_not_called()
    manager._start_permission_monitor.assert_called_once()


def test_permission_error_is_exposed(hotkeys, monkeypatch):
    module, manager, factory = hotkeys
    monkeypatch.setattr(module, 'is_accessibility_trusted', lambda: False)
    monkeypatch.setattr(module, 'request_accessibility_permission', lambda: permissions.AccessibilityStatus(False, 'unavailable', error='fixture'))
    assert manager.start() is False
    assert manager.status == 'permission_error' and manager.last_error == 'fixture'
    factory.assert_not_called()


def test_granted_listener_and_failure_cleanup(hotkeys, monkeypatch):
    module, manager, factory = hotkeys
    monkeypatch.setattr(module, 'is_accessibility_trusted', lambda: True)
    assert manager.start()
    assert manager.status == 'listener_started'
    manager.stop()
    factory.return_value.start.side_effect = RuntimeError('fixture event tap failure')
    assert manager.start() is False
    assert manager.status == 'listener_error' and manager._listener is None
    assert 'fixture event tap failure' in manager.last_error


def test_revoked_permission_stops_previous_listener(hotkeys, monkeypatch):
    module, manager, factory = hotkeys
    monkeypatch.setattr(module, 'is_accessibility_trusted', lambda: True)
    assert manager.start()
    monkeypatch.setattr(module, 'is_accessibility_trusted', lambda: False)
    monkeypatch.setattr(module, 'request_accessibility_permission', lambda: permissions.AccessibilityStatus(False, 'not_granted', True))
    assert not manager.start()
    factory.return_value.stop.assert_called_once()
    assert manager._listener is None and not manager._running


def test_new_monitor_does_not_reuse_stopped_event(monkeypatch):
    from rat.os import hotkey
    manager = hotkey.GlobalHotkeyManager()
    old_event = manager._stop_monitor_event
    old_event.set()
    manager._monitor_thread = Mock(is_alive=lambda: True)
    factory = Mock()
    monkeypatch.setattr(hotkey.threading, 'Thread', factory)
    manager._start_permission_monitor()
    assert manager._stop_monitor_event is not old_event
    assert not manager._stop_monitor_event.is_set() and old_event.is_set()
    assert factory.call_args.kwargs['args'] == (manager._stop_monitor_event,)


def test_monitor_retries_after_grant_without_blocking_main_thread(hotkeys, monkeypatch):
    module, manager, factory = hotkeys
    manager.restart = Mock()
    monkeypatch.setattr(module, 'is_accessibility_trusted', lambda: True)
    stop_event = Mock(wait=Mock(return_value=False))
    manager._monitor_permission_loop(stop_event)
    manager.restart.assert_called_once()
    factory.assert_not_called()


def test_diagnostic_configuration_is_isolated_without_gui_or_models(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = '''
import json, sys
from rat.os.diagnostics import prepare_session
path = prepare_session(sys.argv[1])
from rat.config import config, RAT_DIR, CONFIG_FILE
from rat.timetable import data
from rat.os import crash_shield
assert not config.auto_watch and config.first_run_completed
assert config.indexed_directories == [] and config.document_model_path == ''
assert not config.document_model_preload and not config.memory_sentinel_enabled
assert data.DATA_DIR == RAT_DIR and data.load_club_members() == []
assert crash_shield.CRASH_LOG_DIR == path / 'logs'
assert not any(x in sys.modules for x in ('PyQt6','mlx','mlx_lm','fastembed'))
print(json.dumps({'state_dir': str(RAT_DIR), 'config': str(CONFIG_FILE)}))
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], cwd=root,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert Path(json.loads(result.stdout)['state_dir']).is_relative_to(tmp_path)


def test_diagnostic_help_loads_no_gui_or_configuration():
    root = Path(__file__).resolve().parents[1]
    code = '''
import sys
sys.argv = ['rat.main', '--diagnostics', '--help']
from rat.main import main
try:
    main()
except SystemExit as exc:
    assert exc.code == 0
assert not any(name in sys.modules for name in ('PyQt6', 'rat.config', 'mlx', 'fastembed'))
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--seconds' in result.stdout
