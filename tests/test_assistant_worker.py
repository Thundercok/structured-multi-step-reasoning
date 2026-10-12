"""Qt worker responsiveness, cancellation and SQLite thread ownership."""
import threading
import time

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.timetable.compositor import TimetableCompositor
from rat.ui.assistant_worker import AssistantWorker


def test_worker_does_not_block_ui_and_cancellation_discards_inflight_answer(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(str(tmp_path / 'index.db'))
    gui_connection = db.get_connection()
    release, entered = threading.Event(), threading.Event()
    inference_threads = []

    def model(goal, steps):
        inference_threads.append(threading.get_ident())
        # A worker connection must not replace the GUI's SQLite connection.
        assert db.get_connection() is not gui_connection
        db.get_connection().execute('SELECT COUNT(*) FROM documents').fetchone()
        entered.set()
        # Keep the worker blocked until the GUI explicitly releases it. A short
        # timeout can expire while a larger Qt suite processes queued UI events.
        assert release.wait(15), 'GUI did not release the fixture inference'
        return ModelDecision('', final_answer='Late answer')

    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), model_callable=model)
    worker = AssistantWorker(runtime, 'Help')
    responses = []
    worker.response_ready.connect(responses.append)
    try:
        worker.start()
        deadline = time.monotonic() + 10
        while not entered.is_set() and time.monotonic() < deadline:
            QTest.qWait(10)
        assert entered.is_set() and worker.isRunning()
        assert inference_threads == [inference_threads[0]] and inference_threads[0] != threading.get_ident()
        assert db.get_connection() is gui_connection
        worker.requestInterruption()
        release.set()
        assert worker.wait(2500)
        app.processEvents()
        assert len(responses) == 1 and responses[0].error == 'cancelled'
        assert not responses[0].answer
        assert gui_connection.execute('SELECT COUNT(*) FROM documents').fetchone()[0] == 0
    finally:
        release.set()
        worker.wait(2500)
        worker.deleteLater()
        gui_connection.close()
        app.processEvents()
