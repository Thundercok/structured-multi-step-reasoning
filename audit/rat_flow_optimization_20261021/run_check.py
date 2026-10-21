"""Capture an offline validation command without modifying prior evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
name, *argv = sys.argv[1:]
record = HERE / (name + '.command.json')
if record.exists():
    raise SystemExit('Refusing to overwrite ' + str(record))
env = dict(os.environ)
env.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
            'PYINSTALLER_CONFIG_DIR': str(HERE / 'pyinstaller-cache'),
            'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
            'QT_QPA_PLATFORM': os.environ.get('QT_QPA_PLATFORM', 'offscreen'),
            'RAT_STATE_DIR': str(HERE / 'test-state'), 'RAT_LOG_DIR': str(HERE / 'test-state/logs')})
started = time.time()
with (HERE / (name + '.stdout.txt')).open('w') as out, (HERE / (name + '.stderr.txt')).open('w') as err:
    result = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
record.write_text(json.dumps({'argv': argv, 'cwd': str(ROOT), 'exit_code': result.returncode,
    'started_unix': started, 'elapsed_seconds': time.time() - started,
    'environment_overrides': {key: env[key] for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE',
         'PYINSTALLER_CONFIG_DIR', 'PIP_NO_INDEX', 'PIP_DISABLE_PIP_VERSION_CHECK', 'QT_QPA_PLATFORM')}}, indent=2) + '\n')
print(json.dumps({'name': name, 'exit_code': result.returncode,
                  'stdout': str(HERE / (name + '.stdout.txt')), 'stderr': str(HERE / (name + '.stderr.txt'))}))
raise SystemExit(result.returncode)
