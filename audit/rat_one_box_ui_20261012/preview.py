"""Actual QWidget previews with fixtures; no model or personal-file indexing."""
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from rat.ui.omnibar import OmnibarWindow
from rat.ui.assistant_presenter import source_panel

out = Path(__file__).resolve().parent
app = QApplication.instance() or QApplication([])
app.setProperty('ratReduceMotion', True)
with patch('rat.ui.omnibar.Database') as db, patch('rat.ui.omnibar.SearchEngine'), patch('rat.ui.feedback.FeedbackLog'):
    db.return_value.get_stats.return_value = {'total_files': 0}
    db.return_value.get_recent_documents.return_value = []
    window = OmnibarWindow()
window.show()
QTest.qWait(180)
window.grab().save(str(out/'compact_empty.png'))
window.open_natal_chart()
QTest.qWait(200)
print('Pending content height:', window.chat_stream.container.sizeHint(), window.chat_stream.container.minimumSizeHint(), 'window', window.size())
window.grab().save(str(out/'compact_inputs.png'))
pending = window.assistant_runtime.dispatcher.state.pending_input_request
result = window.assistant_runtime.dispatcher.resume_input(pending.id, dict(name='Ví dụ minh họa', date='2000-06-15', time='09:30', place='Hồ Chí Minh', latitude=10.8231, longitude=106.6297, timezone='Asia/Ho_Chi_Minh'))
assert result.status == 'success', result.error
window._on_artifact_result(window._chat_generation, result)
QTest.qWait(220)
renderer = window._latest_assistant_handle['sources_widget'].artifact_panel.renderers[result.artifact.id]
wheel = renderer._resources[0]
print('Compact wheel geometry:', wheel.geometry(), 'canvas', wheel.canvas.geometry(), 'detail', wheel.detail.geometry(), 'minimum', wheel.minimumSizeHint(), wheel.minimumHeight())
print('Compact renderer', renderer.geometry(), renderer.sizeHint())
print('Renderer minimum:', renderer.minimumSizeHint(), renderer.minimumSize(), renderer.layout.minimumSize())
for idx in range(renderer.layout.count()):
    item = renderer.layout.itemAt(idx)
    print('Renderer item', idx, item.geometry(), item.minimumSize(), item.sizeHint())
window.grab().save(str(out/'compact_chart.png'))
window.set_expanded(True)
QTest.qWait(220)
window.grab().save(str(out/'full_chart.png'))
print('Preview dimensions:', window.size().width(), window.size().height())
window.shutdown()
window.close()
window.deleteLater()
app.processEvents()
