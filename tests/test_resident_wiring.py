"""
Tests for Resident Application wiring, hide-on-close, single-instance routing,
and Carbon-based hotkey manager.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QGuiApplication

from rat.config import config
from rat.os.app import ResidentApplication
from rat.os.hotkey import GlobalHotkeyManager, CarbonHotkeyRegistration


@pytest.fixture(scope="module")
def qapp():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([sys.argv[0], "-platform", "offscreen"])
    return app


def test_main_default_launches_resident_app(monkeypatch):
    """Confirm python -m rat.main with no arguments targets run_resident_app(mode='desk')."""
    import rat.main as main_mod

    mock_run_resident = Mock()
    monkeypatch.setattr(main_mod, "run_resident_app", mock_run_resident)
    monkeypatch.setattr(sys, "argv", ["rat.main"])

    main_mod.main()
    mock_run_resident.assert_called_once_with(mode="desk")


def test_hotkey_display_symbols():
    """Verify macOS symbols for the default chords."""
    cfg = config
    old_hotkey = cfg.global_hotkey
    old_ql = getattr(cfg, "quicklook_hotkey", None)
    try:
        cfg.global_hotkey = "control_option_space"
        cfg.quicklook_hotkey = "option_shift_r"
        assert cfg.get_hotkey_display() == "⌃⌥Space"
        assert cfg.get_quicklook_hotkey_display() == "⌥⇧R"
    finally:
        cfg.global_hotkey = old_hotkey
        if old_ql is not None:
            cfg.quicklook_hotkey = old_ql


def test_resident_hide_on_close_event(qapp):
    """Closing the desk window in resident mode must hide the view without quitting."""
    resident = ResidentApplication(mode="desk")
    mock_view = Mock()
    mock_view.hide = Mock()
    resident.desk_view = mock_view

    close_event = QEvent(QEvent.Type.Close)
    # Filter close event on the desk view
    filtered = resident.eventFilter(mock_view, close_event)
    assert filtered is True
    assert close_event.isAccepted() is False
    mock_view.hide.assert_called_once()
    assert not resident.is_quitting


def test_resident_single_instance_quicklook_command(qapp):
    """Relayed 'quicklook' or 'selection' single instance command summons quickLookSelection."""
    resident = ResidentApplication(mode="desk")
    mock_view = Mock()
    mock_ctrl = Mock()
    resident.desk_view = mock_view
    resident.desk_controller = mock_ctrl

    resident._on_single_instance_command("quicklook")
    # Execute pending queued Qt events
    qapp.processEvents()

    mock_view.show.assert_called()
    mock_ctrl.quickLookSelection.assert_called_once()


def test_carbon_hotkey_manager_wiring_with_fakes(qapp, monkeypatch):
    """
    Test wiring of GlobalHotkeyManager callbacks with fakes.
    Note: In offscreen/headless environments, the native Carbon event loop does not receive
    physical hardware keystrokes; registration and callback dispatch are verified directly.
    """
    triggered = []
    quicklooked = []

    manager = GlobalHotkeyManager(
        on_trigger=lambda: triggered.append(True),
        on_quicklook=lambda: quicklooked.append(True),
        toggle_chord="control_option_space",
        quicklook_chord="option_shift_r",
        backend="carbon",
    )

    # Fake the low-level CarbonHotkeyRegistration start to simulate success
    fake_toggle = Mock(spec=CarbonHotkeyRegistration)
    fake_toggle.start.return_value = True
    fake_ql = Mock(spec=CarbonHotkeyRegistration)
    fake_ql.start.return_value = True

    with patch("rat.os.hotkey.CarbonHotkeyRegistration") as mock_reg_cls:
        mock_reg_cls.side_effect = [fake_toggle, fake_ql]
        with patch("rat.os.hotkey.Path.is_file", return_value=True):
            ok = manager.start()
            assert ok is True
            assert manager.status == "started"

    # Simulate trigger callbacks
    manager.on_trigger()
    manager.on_quicklook()
    assert triggered == [True]
    assert quicklooked == [True]

    manager.stop()
    assert manager.status == "stopped"
    fake_toggle.close.assert_called_once()
    fake_ql.close.assert_called_once()
