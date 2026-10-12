"""Review the fixture preview only; never call a model or change production state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from rat.ui.turn_notes_preview import TurnNotesPreviewWindow

app = QApplication.instance() or QApplication([])
app.setProperty('ratReduceMotion', True)
window = TurnNotesPreviewWindow()
window.show()
QTest.qWait(30)
old = window.turn_widgets[1].notes_pane.rows['note-tcp-time']
current = window.turn_widgets[2].notes_pane.rows['note-tcp-time-v2']

QTest.mouseClick(old.btn_edit, Qt.MouseButton.LeftButton)
QTest.qWait(20)
print(json.dumps({'case': 'edit_new_version_from_old', 'expected_editor_open': True,
    'actual_editor_open': current.editing}))

current._start_edit()
current.editor.setPlainText('Có 35 phút · Chỉ ôn TCP.')
current.editor.setFocus()
QTest.qWait(20)
window.toggle_expanded()
QTest.qWait(20)
print(json.dumps({'case': 'compact_during_edit',
    'draft_preserved': current.editor.toPlainText() == 'Có 35 phút · Chỉ ôn TCP.',
    'editor_visible': current.editor.isVisible(),
    'editor_focused': app.focusWidget() is current.editor}))

window.toggle_expanded()
QTest.qWait(20)
current._save_edit()
print(json.dumps({'case': 'revision_link_after_edit', 'current_text': current.note.text,
    'old_forward_label': old.btn_nav_link.text()}, ensure_ascii=False))

current.trigger_highlight()
QTest.qWait(20)
print(json.dumps({'case': 'reduced_motion', 'reduce_motion': bool(app.property('ratReduceMotion')),
    'highlight_animation_running': current.anim.state() == current.anim.State.Running}))

window.close()
window.deleteLater()
app.processEvents()
