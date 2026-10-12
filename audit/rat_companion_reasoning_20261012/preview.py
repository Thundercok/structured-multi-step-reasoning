"""Actual Qt widget previews; fixture conversation, real calculation, no AI grading."""
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from rat.ui.omnibar import OmnibarWindow
from rat.engine.assistant_runtime import AgentStep, AgentResponse

out = Path(__file__).resolve().parent
app = QApplication.instance() or QApplication([])
app.setProperty('ratReduceMotion', True)
with patch('rat.ui.omnibar.Database') as db, patch('rat.ui.omnibar.SearchEngine'), \
        patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
    db.return_value.get_stats.return_value = {'total_files': 0}
    db.return_value.get_recent_documents.return_value = []
    window = OmnibarWindow()
    window.show()
    QTest.qWait(100)
    window.grab().save(str(out / 'compact_idle.png'))

    query = 'Ví dụ minh họa: Tôi có 30 phút, chỉ ôn TCP. Tính số giây giúp mình.'
    window._submit_chat_prompt(query)
    handle = window._assistant_handle
    runtime = window.assistant_runtime
    generation = runtime.notebook.begin_request(query)
    state = dict(goal='Đổi 30 phút sang giây để ôn TCP', constraints=['chỉ ôn TCP.'],
        success_criteria=['Tính đúng số giây'], known_facts=['Tôi có 30 phút'], completed=[],
        remaining=['Ghi điều người dùng dặn', 'Tính 30*60'], status='in_progress')
    plan = AgentStep(1, '', 'update_task_state', tool_result={'task_state': state})
    window._on_assistant_step(handle, plan)
    saved = runtime.execute_tool('record_work_note', {'text': 'Tôi có 30 phút, chỉ ôn TCP.',
        'source_quote': 'Tôi có 30 phút, chỉ ôn TCP.'}, notes_generation=generation)
    note_step = AgentStep(2, '', 'record_work_note', tool_result=saved)
    window._on_assistant_step(handle, note_step)
    result = runtime.execute_tool('calculate', {'expression': '30*60'})
    calculation = AgentStep(3, '', 'calculate', tool_result=result)
    window._on_assistant_step(handle, calculation)
    window._on_assistant_response(handle, AgentResponse('30 phút là **1.800 giây**. Mình đã ghi: chỉ ôn TCP.',
        [plan, note_step, calculation], 25, 2, 0))
    window.notebook_pane.set_open(True, animate=False)
    QTest.qWait(150)
    window.grab().save(str(out / 'compact_notes.png'))
    handle['work_trace'].set_open(True, animate=False)
    QTest.qWait(150)
    window.grab().save(str(out / 'compact_notes_trace.png'))
    window.set_expanded(True)
    QTest.qWait(150)
    window.grab().save(str(out / 'full_notes_trace.png'))

    window._reset_chat()
    window.set_expanded(False)
    window.open_natal_chart()
    QTest.qWait(100)
    pending = runtime.dispatcher.state.pending_input_request
    values = dict(name='Ví dụ minh họa', date='2000-06-15', time='09:30', place='Hồ Chí Minh',
        latitude=10.8231, longitude=106.6297, timezone='Asia/Ho_Chi_Minh')
    labels = {field['name']: field.get('label', field['name']) for field in pending.missing_fields}
    result = runtime.dispatcher.resume_input(pending.id, values)
    assert result.status == 'success', result.error
    window._on_artifact_result(window._chat_generation, result, note_inputs=(pending.id, labels, values))
    QTest.qWait(150)
    window.grab().save(str(out / 'compact_chart.png'))
    window.shutdown()
    window.close()
    window.deleteLater()
    app.processEvents()
print('Fixture Qt previews saved; model decisions were scripted, calculations real.')
