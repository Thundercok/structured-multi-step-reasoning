"""Visible Cocoa UI fixture; no model, watcher, personal index or network.

Run from the repository root with its Python environment. All user interaction
is performed separately through native computer-use controls. The file card is
seeded; selected-file reads, runtime receipts and UI worker execution are real.
Only inference and search startup warmup are replaced for this UI-only check.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ['QT_QPA_PLATFORM'] = 'cocoa'
os.environ['RAT_DB_PATH'] = str(OUT / 'fixture.db')
os.environ['RAT_REDUCE_MOTION'] = '1'
os.environ.pop('RAT_DEBUG_UI', None)

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication
from rat.config import config
from rat.crawler.db import Database
from rat.engine.reranker import SearchResultItem
from rat.ui.omnibar import OmnibarWindow, SearchWorker

config.db_path = str(OUT / 'fixture.db')
config.indexed_directories = []
config.auto_watch = False
config.use_slm = False
config.llm_provider = 'offline'

path = OUT / 'ui-fixture.txt'
path.write_text('Tài liệu giả lập kiểm tra giao diện.\nMã xác nhận: LOTUS-7319.\n')
db = Database(config.db_path)
db.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext='.txt',
    file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
    content_text=path.read_text()))

observations = dict(scope='Native Cocoa UI fixture, scripted inference; not model quality or latency evidence.',
                    pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
                    network_calls=0, inference_calls=[], selections=[], responses=[])


def no_warmup(self, engine):
    QObject.__init__(self)
    self.engine = engine
    self._latest_id = 0
    self._lock = threading.Lock()


def scripted_chat(self, messages, tools, **kwargs):
    observations['inference_calls'].append(dict(model=self.model, messages=messages,
                                                tools=tools, options=kwargs,
                                                evidence='scripted UI fixture'))
    return dict(message={'role': 'assistant', 'content': 'LOTUS-7319'},
                prompt_tokens=100, completion_tokens=8, done_reason='stop', error=None)


def deny_network(*args, **kwargs):
    observations['network_calls'] += 1
    raise AssertionError('Network disabled in this offline UI fixture')


original_select = OmnibarWindow._select_document_question
original_response = OmnibarWindow._on_assistant_response


def observe_selection(self, item):
    original_select(self, item)
    observations['selections'].append(dict(path=self._selected_document_path,
        placeholder=self.chat_composer_input.placeholderText()))


def observe_response(self, handle, response):
    observations['responses'].append(dict(selected_path=handle.get('selected_document_path'),
                                          response=asdict(response)))
    original_response(self, handle, response)


with patch.object(SearchWorker, '__init__', no_warmup), \
     patch('rat.ui.feedback.FeedbackLog'), \
     patch('rat.engine.slm.SLMEngine.chat_with_meta', scripted_chat), \
     patch('rat.engine.slm.SLMEngine.is_service_running', return_value=False), \
     patch('urllib.request.urlopen', deny_network), \
     patch.object(OmnibarWindow, '_select_document_question', observe_selection), \
     patch.object(OmnibarWindow, '_on_assistant_response', observe_response):
    app = QApplication([])
    app.setApplicationName('RAT UI validation')
    app.setQuitOnLastWindowClosed(False)
    app.setProperty('ratReduceMotion', True)
    window = OmnibarWindow()
    window.setWindowTitle('rat — kiểm thử UI offline')
    window.show()
    window.activateWindow()
    item = SearchResultItem(str(path), path.name, '.txt', path.stat().st_size,
                            time.time(), 1, 'Tệp giả lập kiểm tra UI', path.read_text())
    window._deliver_assistant_reply('Tệp giả lập để kiểm tra thao tác Hỏi.',
                                    strategy='UI fixture', inline_files=[item])

    def record():
        observations['platform'] = app.platformName()
        observations['window_visible'] = window.isVisible()
        observations['title'] = window.workbench_canvas.title_lbl.text()
        observations['badge'] = dict(text=window.workbench_canvas.duration_badge.text(),
                                     visible=window.workbench_canvas.duration_badge.isVisible())
        observations['selected_path'] = window._selected_document_path
        observations['answer_display'] = window.workbench_speech_bubble.text()
        observations['composer_placeholder'] = window.chat_composer_input.placeholderText()
        observations['composer_text'] = window.chat_composer_input.text()
        observations['expanded'] = window.is_expanded
        observations['footers'] = {key: dict(text=getattr(window.workbench_user_lane, key).text(),
            width=getattr(window.workbench_user_lane, key).width(),
            visible=getattr(window.workbench_user_lane, key).isVisible())
            for key in ('input_state_lbl', 'kbd_hint_lbl')}
        (OUT / 'native_observations.json').write_text(json.dumps(observations, ensure_ascii=False, indent=2))
        if (OUT / 'stop-native').exists():
            window.shutdown()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(record)
    timer.start(300)
    QTimer.singleShot(300000, lambda: (window.shutdown(), app.quit()))
    print(json.dumps({'pid': os.getpid(), 'platform': app.platformName(), 'scope': observations['scope']}), flush=True)
    app.exec()
    observations['closed_utc'] = datetime.now(timezone.utc).isoformat()
    (OUT / 'native_observations.json').write_text(json.dumps(observations, ensure_ascii=False, indent=2))
    db.get_connection().close()
