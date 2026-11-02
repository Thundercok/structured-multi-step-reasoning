"""Runtime boundary checks; construction evidence, not live model acceptance."""
import ast
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_production_python_does_not_import_qtwidgets():
    for path in (ROOT / 'rat').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('PyQt6.QtWidgets'), path
            elif isinstance(node, ast.Import):
                assert all(not a.name.startswith('PyQt6.QtWidgets') for a in node.names), path


def test_production_desk_and_native_action_model_with_widgets_import_blocked(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               RAT_STATE_DIR=str(tmp_path), RAT_DB_PATH=str(tmp_path / 'index.db'),
               RAT_LOG_DIR=str(tmp_path / 'logs'))
    code = '''
import importlib.abc, sys
class NoWidgets(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('PyQt6.QtWidgets'):
            raise AssertionError('production imported QtWidgets')
sys.meta_path.insert(0, NoWidgets())
from PyQt6.QtCore import QCoreApplication, QEvent, QUrl
from PyQt6.QtGui import QGuiApplication, QAction
from rat.ui.quick_app import create_quick_desk
from rat.os.native_menu import NativeMenu, NativeStatusItem
from rat.os.app import ResidentApplication
app = QGuiApplication([])
view, controller = create_quick_desk()
assert view is not None
menu = NativeMenu()
action = QAction('Open', menu)
called = []
action.triggered.connect(lambda: called.append(True))
menu.addAction(action)
tray = NativeStatusItem()
tray.setContextMenu(menu)
tray.show()
menu.actions()[0].trigger()
assert called == [True]
assert 'PyQt6.QtWidgets' not in sys.modules
view._resize_timer.stop()
view._close_timer.stop()
controller.close()
tray.hide()
view.setSource(QUrl())
view.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
