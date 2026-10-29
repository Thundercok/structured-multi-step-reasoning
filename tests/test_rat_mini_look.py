"""Small, headless Look contracts; not live/model/UI acceptance evidence."""
from rat.ui.mini_placement import Rect, place_look, LOOK_WIDTH, LOOK_HEIGHT
from rat.ui.mini_presentation import MiniPresentation, look_projection


def test_idle_work_and_result_select_look_variant():
    state = dict(hasWorkbench=False, busy=False, phase='idle', view='translation')
    assert look_projection(state)['lookVariant'] == 'standby'
    state.update(hasWorkbench=True, busy=True, text='One old result.')
    assert look_projection(state)['lookVariant'] == 'standby'
    state.update(busy=False, phase='result', text='Xin chào thế giới.')
    assert look_projection(state)['lookVariant'] == 'C'
    state['text'] = 'Đây là một đoạn văn. Đây là câu tiếp theo.'
    assert look_projection(state)['lookVariant'] == 'B'
    state.update(phase='partial', text='Xin chào.')
    assert look_projection(state)['lookText'].startswith('Chưa hoàn tất.')


def test_edited_ocr_cannot_present_old_translation_as_current():
    state = dict(hasWorkbench=True, busy=False, phase='result', view='translation',
                 text='Bản dịch cũ.', hasOcrSource=True, ocrText='Chữ đã sửa',
                 ocrCommittedText='Chữ cũ')
    assert look_projection(state)['lookText'].startswith('Bản dịch trước khi sửa chữ.')


def test_look_stays_on_screen_and_keeps_the_original_sprite_anchor():
    for area in (Rect(0, 0, 1440, 900), Rect(-640, 0, 640, 600)):
        for x in (area.x, area.right - LOOK_WIDTH):
            home = (x, area.y + 60)
            idle = place_look(area, home)
            for variant, width in (('C', 244), ('B', 320)):
                result = place_look(area, home, width, 150, variant)
                assert result.rat.x == idle.rat.x
                assert result.rat.y == idle.rat.y
                assert result.panel.right <= result.rat.x or result.panel.x >= result.rat.right
                assert area.x <= result.bounds.x and result.bounds.right <= area.right
                assert area.y <= result.bounds.y and result.bounds.bottom <= area.bottom
                assert result.bounds.width < 650


def test_modes_preserve_presentation_session():
    presentation = MiniPresentation()
    presentation.open('ocr')
    presentation.scroll['0:ocr'] = 42
    for mode in ('look', 'minimal', 'single', 'full'):
        presentation.set_mode(mode)
        assert presentation.surface == 'ocr'
        assert presentation.scroll['0:ocr'] == 42
        assert presentation.snapshot()['workspaceMode'] == mode


def test_look_standby_hides_composer_and_preserves_draft(tmp_path):
    import os
    import subprocess
    import sys
    script = r'''
from PyQt6.QtCore import QObject, qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
messages=[]
qInstallMessageHandler(lambda kind, context, message: messages.append(message))
app=QGuiApplication([])
view, controller=create_mini_desk(dict(DEFAULTS, roots=[], setup_completed=True))
view.show()
controller.setComposerDraft('Draft survives Look')
controller.summonLook()
controller.look.pause(); controller.update()  # Offscreen has no native clipboard watcher.
for _ in range(30): app.processEvents()
QTest.qWait(150)
root=view.rootObject()
mascot=root.findChild(QObject, 'lookMascot')
composer=root.findChild(QObject, 'composer')
assert root.property('lookActive') and root.property('lookVariant') == 'standby'
assert mascot.property('visible') and mascot.property('width') == 176 and mascot.property('height') == 176
assert not composer.property('visible')
assert controller.snapshot['draftText'] == 'Draft survives Look'
assert root.property('draftText') == ''
assert view.width() < 650
assert root.findChild(QObject, 'lookFocus') is not None
controller.look.pause(); controller.update()
for _ in range(10): app.processEvents()
speech=root.findChild(QObject, 'speechText')
assert speech.property('contentHeight') < 25, (speech.property('contentHeight'), speech.property('width'))
errors=[m for m in messages if any(x in m for x in ('ReferenceError', 'TypeError', 'Binding loop', 'Cannot assign', 'is not a function'))]
assert not errors, errors
QTest.qWait(5200)
assert not view.isVisible(), 'Passive Look should hide its entire window, not only the bubble'
view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_look_paste_runs_real_offline_translation(tmp_path):
    """Qt offscreen with a real local translator; not native UI acceptance."""
    import os
    import subprocess
    import sys
    script = r'''
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
app=QGuiApplication([])
settings=dict(DEFAULTS, roots=[], setup_completed=True, source_language='en', target_language='vi', free_fallback=False)
view, controller=create_mini_desk(settings)
view.show(); controller.summonLook(); controller.look.pause(); controller.update(); QTest.qWait(200)
app.clipboard().setText('Hello world.')
QTest.keyClick(view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
for _ in range(200):
    QTest.qWait(50)
    if controller.snapshot['phase'] in ('result', 'error'): break
snapshot=controller.snapshot
assert snapshot['phase'] == 'result', (snapshot['phase'], snapshot['status'])
assert snapshot['view'] == 'translation' and snapshot['text'].strip()
assert snapshot['lookVariant'] in ('B', 'C')
assert not snapshot['draftText']
controller.presentRequested.emit()
QTest.qWait(50)
assert controller.snapshot['lookClicked']
assert not view._refs[3].look_hide_timer.isActive()
# Explicit reopen during work must retain the reading intent too.
controller.look.close(); controller.update(busy=True)
controller.presentRequested.emit()
QTest.qWait(50)
assert controller.snapshot['lookClicked']
controller.update(busy=False)
view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_copy_only_queues_and_explicit_open_uses_real_workflow(tmp_path):
    """Adapter delivery simulated; capture/translation are real offline tools."""
    import os
    import subprocess
    import sys
    script = r'''
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
app=QGuiApplication([])
view, c=create_mini_desk(dict(DEFAULTS, roots=[], setup_completed=True,
    source_language='en', target_language='vi', free_fallback=False))
# Offscreen has no macOS pasteboard. Deliver its callback without fabricating tool output.
c.look_clipboard.start=lambda: None
c.look_clipboard.timer.isActive=lambda: True
c.setWorkspaceMode('look'); c.look.close(); c.update()
shown=[]
c.lookRequested.connect(lambda: shown.append(True))
generation=c.generation
c.receiveLookClipboard('Hello world.', None)
assert c.generation == generation and c.job is None and not shown
assert c.snapshot['lookSurface']=='hidden'
c.openPendingLook()
assert c.job is not None and c.look.surface=='reading'
# Copy B during A must neither cancel A nor replace A's source/task.
job=c.job; generation=c.generation; task_id=c.presentation.task_id
c.receiveLookClipboard('Good morning.', None)
assert c.job is job and not job.stop.is_set() and c.generation==generation
assert c.presentation.task_id==task_id
for _ in range(240):
    QTest.qWait(50)
    if c.job is None: break
assert c.snapshot['phase']=='result', c.snapshot['status']
assert c.snapshot['text'].strip() and c.snapshot['lookHasQueued']
assert c.look.pending.text=='Good morning.' and c.presentation.task_id==task_id
text=c.snapshot['text']; source=c._ocr_source_ref
c.dismissLookResult(); c.recallLookResult()
assert c.snapshot['text']==text and c._ocr_source_ref==source and c.snapshot['lookHasQueued']
c.openPendingLook()
assert c.presentation.task_id!=task_id
for _ in range(240):
    QTest.qWait(50)
    if c.job is None: break
assert c.snapshot['phase']=='result', c.snapshot['status']
assert not c.snapshot['lookHasQueued'] and c.snapshot['text'].strip()
c.disableLook(); view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
