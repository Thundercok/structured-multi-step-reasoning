"""Verify current native startup code and final signing metadata without launching."""
from pathlib import Path
import hashlib
import json
import plistlib
import subprocess
from types import CodeType

from PyInstaller.archive.readers import CArchiveReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
bundle = Path('/private/tmp/rat-flow-20261021-dist/rat.app')
executable = bundle / 'Contents/MacOS/rat'

def signature(code):
    def value(item):
        if isinstance(item, CodeType):
            return signature(item)
        if isinstance(item, tuple):
            return tuple(value(v) for v in item)
        return item
    return (code.co_code, code.co_names, code.co_varnames, code.co_flags, code.co_freevars,
            code.co_cellvars, code.co_argcount, code.co_kwonlyargcount,
            tuple(value(v) for v in code.co_consts))

archive = CArchiveReader(str(executable)).open_embedded_archive('PYZ.pyz')
checks = {}
for name in ('rat.main', 'rat.config', 'rat.os.permissions', 'rat.os.hotkey',
             'rat.os.diagnostics', 'rat.os.crash_shield', 'rat.os.menu_bar',
             'rat.ui.onboarding_dialog', 'rat.ui.omnibar', 'rat.timetable.data',
             'rat.engine.execution', 'rat.ui.assistant_worker', 'rat.ui.workbench_scene', 'rat.ui.surface_layout',
             'reasoning.runtime', 'reasoning.bundle'):
    source = ROOT / (name.replace('.', '/') + '.py')
    checks[name] = signature(archive.extract(name)) == signature(compile(source.read_bytes(), str(source), 'exec'))
verify = subprocess.run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(bundle)], capture_output=True, text=True)
display = subprocess.run(['codesign', '-d', '--xml', '--entitlements', '-', '--verbose=4', str(bundle)], capture_output=True)
entitlements = plistlib.loads(display.stdout)
expected = plistlib.loads((ROOT / 'entitlements.plist').read_bytes())
info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
checks['signature_valid'] = verify.returncode == 0
checks['entitlements_preserved'] = entitlements == expected
checks['bundle_id'] = info['CFBundleIdentifier'] == 'com.thundercock.rat'
if 'rfc3987_syntax' in archive.toc:
    checks['uri_grammar_resource'] = (bundle / 'Contents/Resources/rfc3987_syntax/syntax_rfc3987.lark').is_file()
value = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
         'bundle': str(bundle), 'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
         'entitlements': entitlements, 'codesign_description': display.stderr.decode(),
         'verify_stderr': verify.stderr, 'model_calls': 0}
(HERE / 'bundle_check.json').write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps(value, indent=2))
raise SystemExit(not all(checks.values()))
