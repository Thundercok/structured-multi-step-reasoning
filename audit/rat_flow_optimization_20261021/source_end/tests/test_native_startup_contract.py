"""Native startup invariants; no models, real event taps or personal files."""
from unittest.mock import Mock


def test_search_worker_construction_does_not_load_embeddings_or_vectors():
    from rat.ui.omnibar import SearchWorker
    engine = Mock()
    worker = SearchWorker(engine)
    engine.embedder.embed_query.assert_not_called()
    engine.vector_cache.preload.assert_not_called()
    assert worker.engine is engine


def test_permission_menu_refreshes_after_grant(monkeypatch):
    from PyQt6.QtWidgets import QApplication
    from rat.os import hotkey, menu_bar
    app = QApplication.instance() or QApplication([])
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
