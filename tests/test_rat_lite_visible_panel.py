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
