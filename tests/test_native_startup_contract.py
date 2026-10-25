"""Native startup invariants; no models, real event taps or personal files."""
from unittest.mock import Mock


def test_quick_controller_construction_does_not_block_or_load_heavy_models():
    from rat.ui.quick_pdf_controller import QuickPDFController
    runtime = Mock()
    controller = QuickPDFController(assistant_runtime=runtime, auto_init_finder=False)
    assert controller.assistant_runtime is runtime
    controller.close()


def test_permission_menu_refreshes_after_grant(monkeypatch):
    from PyQt6.QtGui import QGuiApplication
    from rat.os import hotkey, menu_bar
    app = QGuiApplication.instance() or QGuiApplication([])
    database = Mock()
    database.get_stats.return_value = {'total_files': 0, 'total_chunks': 0, 'total_size_bytes': 0}
    monkeypatch.setattr(menu_bar, 'Database', Mock(return_value=database))
    trusted = [False]
    monkeypatch.setattr(hotkey, 'is_accessibility_trusted', lambda: trusted[0])
    tray = menu_bar.SystemTrayManager()
    menu = tray.tray_icon.contextMenu()
    action = next(a for a in menu.actions() if 'Accessibility' in a.text())
    assert action.isVisible()
    trusted[0] = True
    menu.aboutToShow.emit()
    assert not action.isVisible()
    tray.tray_icon.hide()
    tray.shutdown()
