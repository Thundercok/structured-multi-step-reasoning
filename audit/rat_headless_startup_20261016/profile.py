"""Bounded CLI startup observations; no GUI window, inference or indexing.

Crash-shield installation is replaced in both phases to avoid modifying the
user's log directory. Imports and command behavior are otherwise unchanged.
Fresh subprocesses use the same installed Python; OS caches are uncontrolled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PROGRAM = r'''
import contextlib, io, json, resource, runpy, sys, time
from rat.os import crash_shield
crash_shield.install_crash_shield = lambda: None
def audit(event, args):
    if event in ('socket.connect', 'subprocess.Popen'):
        raise AssertionError('CLI startup observation must not contact a service or start a process')
sys.addaudithook(audit)
case = json.loads(sys.argv[1])
sys.argv = case['argv']
output = io.StringIO()
start = time.perf_counter()
code = 0
with contextlib.redirect_stdout(output):
    try:
        if case['kind'] == 'file':
            runpy.run_path('main.py', run_name='__main__')
        else:
            runpy.run_module(case['module'], run_name='__main__')
    except SystemExit as exc:
        code = exc.code or 0
elapsed = time.perf_counter()-start
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform != 'darwin':
    rss *= 1024
prefixes = ('PyQt6', 'rat.ui', 'rat.os.app', 'numpy', 'fastembed', 'onnxruntime',
            'mlx', 'torch', 'rat.crawler.indexer', 'rat.engine.hybrid_search')
print(json.dumps(dict(exit_code=code, command_wall_s=elapsed, peak_rss_bytes=rss,
    dependency_modules=sorted(n for n in sys.modules if any(n == p or n.startswith(p+'.') for p in prefixes)),
    stdout=output.getvalue()), ensure_ascii=False))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['before', 'after'], required=True)
    args = parser.parse_args()
    cases = [dict(id='rat_help', kind='module', module='rat.main', argv=['rat.main', '--help']),
             dict(id='cli_help', kind='module', module='rat.cli', argv=['rat.cli', '--help']),
             dict(id='launcher_help', kind='file', argv=['main.py', '--help'])]
    manifest = dict(phase=args.phase, repetitions=3, source_hashes={},
                    scope='Instrumented CLI startup, not GUI latency or model quality')
    for name in ['main.py', 'rat/main.py', 'rat/cli.py']:
        data = (ROOT / name).read_bytes()
        manifest['source_hashes'][name] = hashlib.sha256(data).hexdigest()
        target = OUT / args.phase / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    with tempfile.TemporaryDirectory(prefix='rat-startup-') as temporary:
        environment = dict(os.environ, RAT_DB_PATH=str(Path(temporary) / 'unused.db'),
                           PYTHONDONTWRITEBYTECODE='1', QT_QPA_PLATFORM='offscreen')
        rows = []
        for repetition in range(3):
            for case in cases:
                started = time.perf_counter()
                result = subprocess.run([sys.executable, '-c', PROGRAM, json.dumps(case)],
                    cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                if result.returncode:
                    raise RuntimeError(f"{case['id']}: {result.stderr[-2000:]}")
                row = dict(case=case['id'], repetition=repetition,
                           process_wall_s=time.perf_counter()-started, **json.loads(result.stdout))
                assert row['exit_code'] == 0 and 'usage:' in row['stdout'].lower()
                rows.append(row)
        assert not Path(environment['RAT_DB_PATH']).exists()
    manifest['source_changed'] = [n for n,h in manifest['source_hashes'].items()
                                  if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != h]
    (OUT / f'{args.phase}.json').write_text(json.dumps(dict(manifest=manifest, rows=rows),
                                                     indent=2, ensure_ascii=False))
    print(json.dumps(dict(phase=args.phase, rows=len(rows), source_changed=manifest['source_changed'])))


if __name__ == '__main__':
    main()
