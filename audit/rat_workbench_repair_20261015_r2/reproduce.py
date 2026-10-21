import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RAT_REDUCE_MOTION'] = '1'
os.environ.pop('RAT_DEBUG_UI', None)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QFont
from rat.ui.omnibar import OmnibarWindow
from rat.ui.chat_stream import InlineFileCard
from rat.engine.assistant_runtime import AgentResponse
from rat.kernel.contracts import Artifact

out = Path('audit/rat_workbench_repair_20261015_r2')
out.mkdir(parents=True, exist_ok=True)
app = QApplication.instance() or QApplication([])
app.setProperty('ratReduceMotion', True)

observations = {'scope': 'Integrated OmnibarWindow, deterministic fixture replay; no model call; Qt offscreen, not Cocoa smoke.'}

def settle():
    app.processEvents()
    QTest.qWait(100)
    app.processEvents()

def record(w, name):
    settle()
    widgets = dict(window=w, canvas=w.workbench_canvas, dialogue=w.workbench_dialogue,
                   actor=w.companion_avatar_btn, user_lane=w.workbench_user_lane,
                   composer=w.chat_composer_input, speech=w.workbench_speech_bubble,
                   canvas_content=w.content_stack)
    data = {}
    for key, widget in widgets.items():
        pos = widget.mapToGlobal(widget.rect().topLeft())
        data[key] = dict(x=pos.x(), y=pos.y(), width=widget.width(), height=widget.height(),
                         visible=widget.isVisible())
    data['title'] = w.workbench_canvas.title_lbl.text()
    data['footer'] = w.workbench_user_lane.input_state_lbl.text()
    data['speech_text'] = w.workbench_speech_bubble.dialogue.text()
    data['visible_buttons'] = {key: getattr(w.workbench_speech_bubble, key).isVisible() for key in ['btn_copy', 'btn_hist']}
    data['narrow'] = w.workbench_dialogue.is_narrow
    data['badge'] = {'text': w.workbench_canvas.duration_badge.text(), 'visible': w.workbench_canvas.duration_badge.isVisible()}
    data['composer_region'] = [w.chat_composer_input.visibleRegion().boundingRect().width(), w.chat_composer_input.visibleRegion().boundingRect().height()]
    data['footers'] = {key: {'text': getattr(w.workbench_user_lane,key).text(), 'width': getattr(w.workbench_user_lane,key).width(), 'height': getattr(w.workbench_user_lane,key).height(), 'visible': getattr(w.workbench_user_lane,key).isVisible()} for key in ['input_state_lbl','kbd_hint_lbl']}
    data['fonts'] = {key: widget.font().family() for key,widget in [('title', w.workbench_canvas.title_lbl), ('composer', w.chat_composer_input)]}

    observations[name] = data
    w.grab().save(str(out / (name + '.png')))

with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
     patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'), \
     patch('rat.engine.slm.slm_engine.is_service_running', return_value=False):
    database.return_value.get_stats.return_value = {'total_files': 0}
    database.return_value.get_recent_documents.return_value = []
    w = OmnibarWindow()
    w.show()
    w.activateWindow()
    record(w, 'integrated-empty')

    # Character counter check at 1750 chars on empty
    w.chat_composer_input.setText("A" * 1750)
    settle()
    observations['character_counter_1750'] = {
        'text': w.workbench_user_lane.input_state_lbl.text(),
        'width': w.workbench_user_lane.input_state_lbl.width(),
        'visible': w.workbench_user_lane.input_state_lbl.isVisible(),
    }
    w.chat_composer_input.clear()
    settle()

    w._deliver_assistant_reply('2 + 2 = 4', strategy='Math')
    record(w, 'integrated-calculation')
    editor = w.chat_composer_input
    editor.setText('Bản nháp tiếng Việt')
    editor.setSelection(4, 7)
    editor.setFocus()
    before = editor.mapToGlobal(editor.rect().bottomLeft()).y()
    w.set_expanded(True)
    record(w, 'integrated-expanded')
    observations['composer_anchor'] = dict(before=before, expanded=editor.mapToGlobal(editor.rect().bottomLeft()).y(),
        draft=editor.text(), selection=editor.selectedText(), same_editor=editor is w.full_chat_input)
    w.set_expanded(False)
    w._resize_overlay(440, 400)
    record(w, 'integrated-narrow')

    # Screen constraint breakpoint verification: available width 490 yields outer 466, content 450
    screen_mock = MagicMock()
    available_geo = QRect(0, 0, 490, 800)
    screen_mock.availableGeometry.return_value = available_geo
    with patch('rat.ui.omnibar.QGuiApplication.screenAt', return_value=screen_mock):
        w._resize_overlay(620, 245)
        settle()
        observations['screen_constraint_490'] = {
            'outer_width': w.width(),
            'content_width': w.workbench_canvas.width(),
            'is_narrow': w.workbench_dialogue.is_narrow,
            'actor_width': w.companion_avatar_btn.width(),
        }

    # Restore normal desktop width 620
    w._resize_overlay(620, 245)
    settle()

    w._submit_chat_prompt('Một yêu cầu fixture')
    handle = w._assistant_handle
    w.chat_composer_input.setText('Bản nháp giữ khi đổi chế độ')
    generation = w._chat_generation
    w._submit_chat_prompt('xem chi tiết')
    observations['view_command_while_busy'] = dict(same_handle=w._assistant_handle is handle, same_generation=w._chat_generation == generation, draft=w.chat_composer_input.text(), expanded=w.is_expanded)
    w._submit_chat_prompt('thu gọn')
    w._on_reasoning_token(handle, 'Xin')
    observations['first_token'] = dict(stream=handle['full_text'], bubble=w.workbench_speech_bubble.text())
    w._on_reasoning_token(handle, ' chào')
    observations['second_token'] = dict(stream=handle['full_text'], bubble=w.workbench_speech_bubble.text())
    w._cancel_assistant()
    record(w, 'integrated-cancelled')
    stopped = (w.workbench_speech_bubble.text(), w.workbench_canvas.title_lbl.text(), w.workbench_user_lane.phase)
    w._on_reasoning_token(handle, 'LATE TOKEN')
    w._on_assistant_progress(handle, 'LATE PROGRESS')
    w._on_assistant_response(handle, AgentResponse('LATE RESPONSE', [], 0, 0, 0))
    observations['late_callbacks'] = {'visible_state_unchanged': stopped == (w.workbench_speech_bubble.text(), w.workbench_canvas.title_lbl.text(), w.workbench_user_lane.phase)}
    w._submit_chat_prompt('Đưa README của dự án')
    actual_file = Path('README.md').resolve()
    artifact = Artifact('review-readme', 'document_file', payload={'path': str(actual_file), 'filename': actual_file.name})
    w.assistant_runtime.artifact_store.put(artifact)
    response = AgentResponse('Đây là README của dự án.', [], 0, 0, 0, artifacts=[artifact])
    w._on_assistant_response(w._assistant_handle, response)
    record(w, 'integrated-file-compact')
    cards = w.chat_stream.findChildren(InlineFileCard)
    observations['file_card_compact'] = [dict(exists=actual_file.is_file(), path_matches=c.item.file_path == str(actual_file),
        visible=c.isVisible(), visible_region=[c.visibleRegion().boundingRect().width(), c.visibleRegion().boundingRect().height()]) for c in cards]
    with patch('rat.ui.chat_stream.open_file_default') as opened:
        if cards:
            cards[0].setFocus()
            QTest.keyClick(cards[0], Qt.Key.Key_Return)
            QTest.mouseClick(cards[0].name_label, Qt.MouseButton.LeftButton)
        observations['file_activation'] = dict(calls=opened.call_count, exact_target=all(call.args == (str(actual_file),) for call in opened.call_args_list))
    w.set_expanded(True)
    record(w, 'integrated-file-expanded')
    observations['file_card_expanded'] = [dict(visible=c.isVisible(), visible_region=[c.visibleRegion().boundingRect().width(), c.visibleRegion().boundingRect().height()]) for c in cards]
    w._reset_chat()
    record(w, 'integrated-reset')
    w.shutdown()
    w.close()
    w.deleteLater()
    app.processEvents()

(out / 'observations.json').write_text(json.dumps(observations, ensure_ascii=False, indent=2))
print("Independent replay completed. Observations saved to:", out / 'observations.json')
