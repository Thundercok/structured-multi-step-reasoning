"""Regression: primary setup and Finder surfaces must have usable height."""
import os
import subprocess
import sys


def test_setup_and_finder_panels_have_height(tmp_path):
    script = r'''
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
app = QGuiApplication([])
view, c = create_mini_desk(dict(DEFAULTS, roots=[], setup_completed=False))
view.show()
QTest.qWait(150)
panel = view.rootObject().findChild(QObject, 'taskPanel')
assert panel.property('height') >= 300, panel.property('height')
c.presentation.open('result')
c.presentation.compose()
c.update(setupCompleted=True, hasWorkbench=True, phase='result', view='finder', finderHits=[{'title':'sample.txt','path':'/tmp/sample.txt'}])
QTest.qWait(150)
assert 200 <= panel.property('height') <= view.rootObject().property('maxCornerSpeechHeight'), panel.property('height')
assert view.rootObject().findChild(QObject, 'mascotCrop').property('visible')
assert view.rootObject().findChild(QObject, 'composer').property('visible')
view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_compact_panel_width_remains_440_when_busy(tmp_path):
    script = r'''
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
app = QGuiApplication([])
view, c = create_mini_desk(dict(DEFAULTS, roots=[], setup_completed=True))
view.show()
c.presentation.open('result')
c.presentation.compose()
c.presentation.resize(False)
QTest.qWait(100)
root = view.rootObject()
assert root.property('preferredPanelWidth') == 440, root.property('preferredPanelWidth')
c.update(busy=True, phase='working')
QTest.qWait(100)
assert root.property('preferredPanelWidth') == 440, root.property('preferredPanelWidth')
view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_translate_selected_hit_runs_real_file_translation(tmp_path):
    sample_file = tmp_path / 'sample_note.md'
    sample_file.write_text('Hello world. This is a short note for file translation.', encoding='utf-8')
    script = f'''
from pathlib import Path
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.kernel.contracts import Artifact
from rat.ui.mini_quick import create_mini_desk

sample_file = Path({str(sample_file)!r})
assert sample_file.is_file()

app = QGuiApplication([])
view, c = create_mini_desk(dict(DEFAULTS, roots=[str(sample_file.parent)], setup_completed=True,
                                source_language='en', target_language='vi', free_fallback=False))
view.show()
for _ in range(200):
    QTest.qWait(50)
    if not c.snapshot['busy'] and c.job is None:
        break
c.presentation.open('result')
c.presentation.compose()

# Inject finder artifact
art = Artifact(id='art-finder-test', kind='finder_results', revision=1,
               payload={{'status':'complete', 'hits':[{{'resource_id':'res-1', 'title':sample_file.name, 'path':str(sample_file)}}]}})
c.finder_artifact = art
c.update(hasWorkbench=True, view='finder', finderHits=[{{'title':sample_file.name,'path':str(sample_file)}}])
QTest.qWait(100)

c.translateSelectedHit(0)
for _ in range(300):
    QTest.qWait(50)
    if c.snapshot['phase'] in ('result', 'error'):
        break

snap = c.snapshot
assert snap['phase'] == 'result', (snap['phase'], snap.get('status'))
assert snap['view'] == 'translation', snap['view']
assert snap['text'].strip(), "Expected translation text"
view.hide()
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path),
               PYTHONPATH=os.environ.get('PYTHONPATH', ''))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
