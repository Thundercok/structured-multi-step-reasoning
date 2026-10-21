"""Lightweight commands work when GUI and inference dependencies are absent."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROGRAM = r'''
import contextlib, importlib.abc, io, json, runpy, sys, threading
blocked = ('PyQt6', 'rat.ui', 'rat.os.app', 'numpy', 'fastembed', 'onnxruntime',
           'torch', 'mlx', 'mlx_lm', 'rat.engine.hybrid_search', 'rat.crawler.indexer')
class NoHeavyDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == p or fullname.startswith(p+'.') for p in blocked):
            raise AssertionError('Unneeded dependency: '+fullname)
sys.meta_path.insert(0, NoHeavyDependencies())
def audit(event, args):
    if event in ('socket.connect', 'subprocess.Popen'):
        raise AssertionError('Lightweight command attempted '+event)
sys.addaudithook(audit)
case = json.loads(sys.argv[1])
before = (sys.excepthook, threading.excepthook)
sys.argv = case['argv']
output = io.StringIO()
code = 0
with contextlib.redirect_stdout(output):
    try:
        if case['kind'] == 'file':
            runpy.run_path('main.py', run_name='__main__')
        elif case['kind'] == 'import':
            import rat.main
        else:
            runpy.run_module(case['module'], run_name='__main__')
    except SystemExit as exc:
        code = exc.code or 0
assert (sys.excepthook, threading.excepthook) == before
assert not any(n == p or n.startswith(p+'.') for n in sys.modules for p in blocked)
print(json.dumps({'exit_code': code, 'stdout': output.getvalue()}))
'''


@pytest.mark.parametrize('case,expected', [
    ({'kind': 'import', 'argv': ['rat.main']}, ''),
    ({'kind': 'module', 'module': 'rat.main', 'argv': ['rat.main', '--help']}, 'usage:'),
    ({'kind': 'module', 'module': 'rat.cli', 'argv': ['rat.cli', '--help']}, 'usage:'),
    ({'kind': 'file', 'argv': ['main.py', '--help']}, 'usage:'),
    *[({'kind': 'module', 'module': 'rat.main', 'argv': ['rat.main', command, '--help']}, 'usage:')
      for command in ('search', 'index', 'ask', 'ask-file', 'dedup', 'status')],
    ({'kind': 'module', 'module': 'rat.main', 'argv': ['rat.main', 'init-shell']}, 'rat()'),
    ({'kind': 'module', 'module': 'rat.main', 'argv': ['rat.main', '2+2']}, '4'),
    ({'kind': 'module', 'module': 'rat.main', 'argv': ['rat.main', 'B203']}, 'B203'),
])
def test_lightweight_command_needs_no_gui_model_or_service(tmp_path, case, expected):
    # A sentinel database must not be opened, migrated or replaced by help and
    # direct commands, even when configured at the normal application boundary.
    database = tmp_path / 'unused.db'
    database.write_bytes(b'preserve this uninitialized database')
    environment = dict(os.environ, RAT_DB_PATH=str(database), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-c', PROGRAM, json.dumps(case)],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response['exit_code'] == 0
    assert expected in response['stdout']
    assert database.read_bytes() == b'preserve this uninitialized database'


@pytest.mark.parametrize('command,mode', [('spotlight', 'spotlight'), ('--daemon', 'daemon'),
                                         ('finder', 'finder'), ('widget', 'widget')])
def test_gui_route_keeps_exception_hooks_before_launch(monkeypatch, command, mode):
    from types import ModuleType
    from rat import main as entry
    from rat.os import crash_shield

    events = []
    monkeypatch.setattr(crash_shield, 'install_crash_shield', lambda: events.append('shield'))
    backend = ModuleType('rat.os.app')
    backend.run_resident_app = lambda mode: events.append(('launch', mode))
    monkeypatch.setitem(sys.modules, 'rat.os.app', backend)
    monkeypatch.setattr(sys, 'argv', ['rat.main', command])
    entry.main()
    assert events == ['shield', ('launch', mode)]


@pytest.mark.parametrize('command', ['astrology', 'natal', 'la-so'])
def test_standalone_gui_keeps_exception_hooks_before_launch(monkeypatch, command):
    from types import ModuleType
    from rat import main as entry
    from rat.os import crash_shield

    events = []
    monkeypatch.setattr(crash_shield, 'install_crash_shield', lambda: events.append('shield'))
    backend = ModuleType('rat.astrology.__main__')
    backend.main = lambda: events.append('launch')
    monkeypatch.setitem(sys.modules, 'rat.astrology.__main__', backend)
    monkeypatch.setattr(sys, 'argv', ['rat.main', command])
    entry.main()
    assert events == ['shield', 'launch']
