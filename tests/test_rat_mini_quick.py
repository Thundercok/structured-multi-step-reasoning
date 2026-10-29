"""Synthetic layout/contract checks only; live acceptance is recorded separately."""
import os
import subprocess
import sys
from pathlib import Path


def test_mini_quick_layout_and_import_boundary():
    script = r'''
import sys
from PyQt6.QtCore import qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from rat.ui.mini_quick import create_mini_desk
messages=[]
qInstallMessageHandler(lambda kind,ctx,msg: messages.append(msg))
app=QGuiApplication([])
view,controller=create_mini_desk()
view.show()
root=view.rootObject()
for _ in range(10): app.processEvents()
compact=view.height()
# Synthetic layout data: deliberately not a backend/model acceptance run.
hits=[dict(title='Tài liệu kiểm thử '+str(i),path='/synthetic/'+('thư mục dài/'*8)+str(i)+'.pdf',
 kind='file',is_pdf=True,display_path='/synthetic/'+str(i)+'.pdf',match_reason='Layout fixture') for i in range(8)]
controller.update(phase='working',busy=True,expanded=True,hasWorkbench=True)
controller.update(phase='result',busy=False,view='finder',finderHits=hits,status='Synthetic layout only')
for _ in range(25): app.processEvents()
assert root.property('selectedFinderIndex') == -1  # Composer retains Enter ownership.
assert view.height() >= compact
assert 'PyQt6.QtWidgets' not in sys.modules
assert 'rat.ui.quick_pdf_controller' not in sys.modules
assert 'rat.engine.mini_semantic' not in sys.modules
controller.setExpanded(False)
for _ in range(15): app.processEvents()
assert not root.property('paperVisible')
controller.update(view='translation',finderHits=[],text='Văn bản dài\n'*100,meta='Synthetic layout',expanded=True)
for _ in range(25): app.processEvents()
assert view.height() <= view.screen().availableGeometry().height()-32
errors=[m for m in messages if any(s in m for s in ('ReferenceError','TypeError','Binding loop','Cannot assign','is not a function'))]
assert not errors, errors
view.hide()
print('Synthetic QML layout passed; no live acceptance claim')
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_settings_invalid_roots_preserve_session(tmp_path):
    from rat.ui.mini_quick_controller import MiniQuickController
    from rat.engine.mini_settings import DEFAULTS
    controller = MiniQuickController(dict(DEFAULTS, roots=[str(tmp_path)]))
    previous = controller.session
    error = controller.savePreferences({'roots': [str(tmp_path/'does-not-exist')]})
    assert error
    assert controller.session is previous
    assert controller.settings['roots'] == [str(tmp_path)]


def test_settings_key_goes_only_to_keychain_and_keeps_captured_source(tmp_path, monkeypatch):
    from rat.ui.mini_quick_controller import MiniQuickController
    from rat.engine.mini_settings import DEFAULTS
    saved, secrets = [], []
    monkeypatch.setattr('rat.ui.mini_quick_controller.save_settings', lambda data:saved.append(dict(data)))
    monkeypatch.setattr('rat.ui.mini_quick_controller.keychain_key', lambda provider,key:secrets.append((provider,key)))
    controller = MiniQuickController(dict(DEFAULTS, roots=[str(tmp_path)]))
    store = controller.session.runtime.artifact_store
    controller.update(hasOcrSource=True, ocrText='Public draft', ocrOriginalText='Original')
    assert controller.savePreferences({'translation_provider':'llm','provider':'deepseek','model':'configured-model','llm_enabled':True}, 'contract-only-key') == ''
    assert secrets == [('deepseek','contract-only-key')]
    assert saved[0]['model'] == 'configured-model'
    assert 'contract-only-key' not in repr(saved) + repr(controller.snapshot) + repr(controller.preferences)
    assert controller.session.runtime.artifact_store is store
    assert controller.snapshot['ocrText'] == 'Public draft'
    # Blank key preserves the existing credential; no second write.
    assert controller.savePreferences({'translation_provider':'llm'}) == ''
    assert len(secrets) == 1


def test_selected_image_uses_shared_capture_workflow(tmp_path, monkeypatch):
    """Image transport contract only; synthetic PNG is not live OCR acceptance."""
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QImage
    from rat.ui.mini_quick_controller import MiniQuickController
    from rat.engine.mini_settings import DEFAULTS
    picture = QImage(20,20,QImage.Format.Format_RGB32)
    picture.fill(0xffffff)
    path=tmp_path/'image.png'
    assert picture.save(str(path))
    controller=MiniQuickController(dict(DEFAULTS,roots=[str(tmp_path)]))
    dispatched=[]
    monkeypatch.setattr(controller,'enqueue',lambda *args:dispatched.append(args))
    assert controller.chooseImageFile(QUrl.fromLocalFile(str(path)), 'dịch sang tiếng Anh')
    operation,arguments,instruction=dispatched[0]
    assert operation == 'capture_translate' and arguments['mode'] == 'image'
    assert arguments['image_input'].origin == 'selected_file'
    assert arguments['image_input'].source_file_sha256
    assert instruction == 'dịch sang tiếng Anh'
    assert not controller.chooseImageFile(QUrl('https://example.com/private.png'), '')
    assert len(dispatched) == 1


def test_build_packages_only_mini_qml_dependencies():
    build = Path('tools/build_rat_mini_app.sh').read_text()
    for name in ('MiniDesk','FinderResultsView','QuietButton','DeskIcon','KeycapBadge'):
        assert f'{name}.qml:rat/ui/quick' in build
    assert 'PyQt6.QtWidgets rat.ui.mini_floaty' in build
