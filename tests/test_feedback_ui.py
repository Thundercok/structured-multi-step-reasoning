import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from rat.ui.feedback import SearchFeedback


def test_visibility_replacement_and_action_routing():
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    layout = QVBoxLayout(window)
    widget = QListWidget()
    layout.addWidget(widget)
    log = Mock()
    log.record.side_effect = ["first", "second", "third"]
    feedback = SearchFeedback(window, "test", [widget], log)
    candidate = SimpleNamespace(file_path="/test.pdf")
    item = QListWidgetItem(widget)
    item.setData(Qt.ItemDataRole.UserRole, candidate)
    feedback.refresh(widget, "old query")
    log.record.assert_not_called()
    window.show()
    app.processEvents()
    log.record.assert_called_once_with("old query", [candidate], "test", None, None)
    feedback.refresh(widget, "new query")
    log.action.assert_called_with("first", "none")
    callback = Mock()
    feedback.perform("open", candidate, callback)
    log.action.assert_called_with("second", "open", "/test.pdf")
    callback.assert_called_once_with("/test.pdf")
    feedback.perform("open", SimpleNamespace(file_path="rat://calc_copy/4"), callback)
    assert callback.call_count == 1
    window.hide()
    app.processEvents()
    log.action.assert_called_with("second", "none")
    window.show()
    app.processEvents()
    assert log.record.call_count == 3
    window.close()
