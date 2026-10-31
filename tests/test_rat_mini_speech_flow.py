"""Focused software contracts; native acceptance is a separate recorded run."""
import os
from pathlib import Path
import subprocess
import sys


def run_qt(script, tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', RAT_MINI_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_settings_error_recovers_on_same_source_without_llm(tmp_path):
    run_qt(r'''
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.ui.mini_quick import create_mini_desk
from rat.engine.mini_settings import DEFAULTS
app=QGuiApplication([])
view,c=create_mini_desk(dict(DEFAULTS, roots=[], setup_completed=True, permission_hello_version=1,
 source_language='en', target_language='vi', translation_provider='mymemory', free_fallback=False))
app.clipboard().setText('Hello world.')
c.pasteLook()
for _ in range(300):
 QTest.qWait(30)
 if c.job is None: break
assert c.snapshot['phase']=='error',c.snapshot['status']
assert 'MyMemory' in c.snapshot['status'] and c.snapshot['translationSettingsSuggested']
source=dict(c._ocr_source_ref); store=c.session.runtime.artifact_store
assert c.session.client.calls==0
assert c.savePreferences({'translation_provider':'automatic','roots':[]})=='',c.snapshot
assert c.session.runtime.artifact_store is store and c._ocr_source_ref==source
assert not c.snapshot['translationSettingsSuggested']
c.retryRequest()
for _ in range(300):
 QTest.qWait(30)
 if c.job is None: break
assert c.snapshot['phase']=='result',c.snapshot['status']
assert c._ocr_source_ref==source and c.snapshot['text'].strip()
assert c.session.client.calls==0 and not c.settings['llm_enabled']
view.hide()
''', tmp_path)


def test_reader_restores_scroll_selection_and_pending_does_not_resize(tmp_path):
    run_qt(r'''
from PyQt6.QtCore import QObject,qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk
app=QGuiApplication([]);messages=[]
qInstallMessageHandler(lambda kind,ctx,message:messages.append(message))
view,c=create_mini_desk(dict(DEFAULTS,roots=[],setup_completed=True,permission_hello_version=1))
c.presentation.read()
# Presentation fixture only: not a backend/model or native acceptance result.
c.update(hasWorkbench=True,phase='result',view='translation',text='Public layout paragraph for reading.\n\n'*80)
view.show();QTest.qWait(100)
root=view.rootObject(); viewport=root.findChild(QQuickItem,'resultPaper'); speech=root.findChild(QQuickItem,'translationText')
assert viewport and speech
end=viewport.property('contentHeight')-viewport.property('height')
viewport.setProperty('contentY',end)
QTest.qWait(30)
from PyQt6.QtQml import QQmlExpression,QQmlEngine
QQmlExpression(QQmlEngine.contextForObject(speech),speech,'select(4, 20)').evaluate()
QTest.qWait(30)
# Selecting text may scroll to its line. Retain a deliberate final reading position.
viewport.setProperty('contentY',end);QTest.qWait(30)
saved=c.presentation.scroll[c.presentation.scroll_key]
selected=c.presentation.selections[c.presentation.task_id]
assert saved>0 and selected==(4,20),(saved,selected)
c.dismissLookResult();QTest.qWait(30);c.recallLookResult();QTest.qWait(100)
assert abs(viewport.property('contentY')-saved)<2,(viewport.property('contentY'),saved)
assert (speech.property('selectionStart'),speech.property('selectionEnd'))==selected
assert root.findChild(QObject,'composer').metaObject().className().startswith('SpeechSurface')
c.summonLook();QTest.qWait(30)
errors=[m for m in messages if any(x in m for x in ('ReferenceError','TypeError','Binding loop','Cannot assign','is not a function'))]
assert not errors,errors
view.hide()
''', tmp_path)


def test_visual_shell_is_reused_and_packaged():
    composer=Path('rat/ui/quick/MiniDesk.qml').read_text()
    assert 'SpeechSurface {\n            id: panelSkin' in composer
    assert 'SpeechSurface {\n            id: composer' in composer
    assert 'Mini · Speech source' not in composer
    build=Path('tools/build_rat_mini_app.sh').read_text()
    for name in ('SpeechSurface','MascotPose'):
        assert f'{name}.qml:rat/ui/quick' in build


def test_activation_bridge_only_routes_explicit_presentation(tmp_path):
    run_qt(r'''
from pathlib import Path
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QTest
from rat.ui.mini_instance import MiniInstanceBridge,present_running_mini
import os
app=QCoreApplication([]); root=Path(os.environ['RAT_MINI_STATE_DIR']); bridge=MiniInstanceBridge(root)
seen=[]
bridge.showRequested.connect(lambda:seen.append('show'))
bridge.lookRequested.connect(lambda:seen.append('look'))
bridge.minimalRequested.connect(lambda:seen.append('minimal'))
for mode in ('look','minimal','show'):
 assert present_running_mini(root,mode)
 QTest.qWait(30)
 assert seen[-1]==mode,seen
try:
 present_running_mini(root,'translate')
 raise AssertionError('Bridge must not execute business operations')
except ValueError: pass
bridge.close()
''', tmp_path)
