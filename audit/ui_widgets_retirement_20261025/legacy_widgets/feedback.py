"""Shared list visibility and file-action feedback for desktop search surfaces."""

from PyQt6.QtCore import QEvent, QObject, Qt

from rat.engine.feedback_log import FeedbackLog


class SearchFeedback(QObject):
    def __init__(self, window, surface, lists, log=None):
        super().__init__(window)
        self.window = window
        self.surface = surface
        self.lists = lists
        self.log = log or FeedbackLog()
        self.impressions = {}
        self.queries = {}
        for widget in lists:
            widget.installEventFilter(self)

    def refresh(self, widget, query, context=None, latency_ms=None):
        self.dismiss(widget)
        self.queries[widget] = query
        if widget.isVisible():
            candidates = [widget.item(row).data(Qt.ItemDataRole.UserRole)
                          for row in range(widget.count())]
            self.impressions[widget] = self.log.record(
                query, candidates, self.surface, context, latency_ms
            )

    def dismiss(self, widget):
        impression_id = self.impressions.pop(widget, None)
        if impression_id:
            self.log.action(impression_id, "none")

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show:
            self.refresh(watched, self.queries.get(watched, ""))
        elif event.type() == QEvent.Type.Hide:
            self.dismiss(watched)
        return False

    def perform(self, kind, item, callback):
        path = item.file_path
        if not path or path.startswith("rat://"):
            return
        for widget in self.lists:
            if widget.isVisible() and any(
                widget.item(row).data(Qt.ItemDataRole.UserRole) is item
                for row in range(widget.count())
            ):
                self.log.action(self.impressions.get(widget), kind, path)
                break
        callback(path)
