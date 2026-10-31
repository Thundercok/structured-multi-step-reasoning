"""Small, headless Look contracts; not live/model/UI acceptance evidence."""
from rat.ui.mini_placement import Rect, place_look, LOOK_WIDTH, LOOK_HEIGHT
from rat.ui.mini_presentation import MiniPresentation


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


def test_extent_and_surfaces_preserve_presentation_session():
    presentation = MiniPresentation()
    presentation.open('ocr')
    presentation.scroll['0:ocr'] = 42
    for expanded in (True, False):
        presentation.resize(expanded)
        assert presentation.surface == 'ocr'
        assert presentation.scroll['0:ocr'] == 42
        assert presentation.snapshot()['interactionExtent'] == ('expanded' if expanded else 'compact')


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
view, controller=create_mini_desk(dict(DEFAULTS, roots=[], setup_completed=True, permission_hello_version=1))
view.show()
controller.setComposerDraft('Draft survives Look')
controller.summonLook()
for _ in range(30): app.processEvents()
QTest.qWait(150)
root=view.rootObject()
mascot=root.findChild(QObject, 'mascotCrop')
composer=root.findChild(QObject, 'composer')
assert root.property('lookActive')
assert mascot.property('visible') and mascot.property('width') == 144 and mascot.property('height') == 144
assert not composer.property('visible')
assert controller.snapshot['draftText'] == 'Draft survives Look'
assert view.width() < 650
errors=[m for m in messages if any(x in m for x in ('ReferenceError', 'TypeError', 'Binding loop', 'Cannot assign', 'is not a function'))]
assert not errors, errors
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
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
app=QGuiApplication([])
settings=dict(DEFAULTS, roots=[], setup_completed=True, permission_hello_version=1, source_language='en', target_language='vi', free_fallback=False)
view, controller=create_mini_desk(settings)
view.show(); controller.summonLook(); QTest.qWait(200)
app.clipboard().setText('Hello world.')
controller.pasteLook()
for _ in range(200):
    QTest.qWait(50)
    if controller.snapshot['phase'] in ('result', 'error'): break
snapshot=controller.snapshot
assert snapshot['phase'] == 'result', (snapshot['phase'], snapshot['status'])
assert snapshot['view'] == 'translation' and snapshot['text'].strip()
assert not snapshot['draftText']
view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
