"""Real runtime check events render in the existing conversation disclosure."""
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.timetable.compositor import TimetableCompositor
from rat.ui.work_context import WorkTracePane


def test_rejected_and_repaired_answer_share_existing_work_trace(monkeypatch):
    monkeypatch.setenv('RAT_DEBUG_UI', '1')
    app = QApplication.instance() or QApplication([])
    runtime = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)
    decisions = iter([ModelDecision('PRIVATE THOUGHT', final_answer='999', raw_completion='PRIVATE RAW'),
                      ModelDecision('PRIVATE THOUGHT', final_answer='4')])
    runtime.model_callable = lambda goal, steps: next(decisions)
    pane = WorkTracePane()
    response = runtime.run('2 + 2', on_step=pane.add_step)
    pane.finish(response)
    assert response.answer == '4' and len(pane.entries) == 2
    assert pane.entries[1].status == 'error' and pane.entries[2].status == 'done'
    assert all(entry.title == 'Đối chiếu kết luận' for entry in pane.entries.values())
    assert '999' in pane.entries[1].detail and '4' in pane.entries[2].detail
    assert 'PRIVATE' not in pane.preview.text()
    assert all('PRIVATE' not in entry.detail for entry in pane.entries.values())
    assert not pane.isHidden()
    pane.close()
    app.processEvents()
