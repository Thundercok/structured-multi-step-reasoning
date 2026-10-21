"""Repeatable offscreen fixture timing; not a native UI or model benchmark."""
from pathlib import Path
import gc
import hashlib
import importlib.abc
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'startup_final'
OUT.mkdir(exist_ok=True)

if len(sys.argv) == 1:
    rows = []
    for repetition in range(3):
        for revision in ('baseline', 'candidate'):
            result = subprocess.run([sys.executable, __file__, revision], cwd=ROOT,
                                    text=True, capture_output=True)
            (OUT/f'startup-{revision}-{repetition}.stdout.txt').write_text(result.stdout)
            (OUT/f'startup-{revision}-{repetition}.stderr.txt').write_text(result.stderr)
            if result.returncode:
                raise SystemExit(f'{revision}: exit {result.returncode}; see raw logs')
            rows.append(json.loads(result.stdout.splitlines()[-1]))
    value = {'scope':'offscreen authored DB/catalog doubles; imports + constructor + first event processing; '
                     'fresh Python processes with OS caches uncontrolled; 3 alternating pairs; '
                     'not native hotkey latency or model inference', 'runs':rows,
        'candidate_source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('rat/ui/omnibar.py','rat/ui/assistant_worker.py','rat/ui/surface_layout.py',
                         'rat/ui/workbench_scene.py','rat/engine/execution.py')},
        'medians':{revision:{metric:statistics.median(r[metric] for r in rows if r['revision']==revision)
            for metric in ('import_ms','constructor_ms','show_and_events_ms','widgets_after_construct')}
            for revision in ('baseline','candidate')}}
    (OUT/'startup_probe.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value,indent=2))
    raise SystemExit(0)

revision = sys.argv[1]
sys.path.insert(0,str(ROOT))
state = HERE/'test-state'/f'probe-{revision}'
state.mkdir(parents=True,exist_ok=True)
(state/'config.json').write_text(json.dumps({'first_run_completed':True,'indexed_directories':[],
    'auto_watch':False,'document_model_path':'','document_model_preload':False}))
(state/'club_schedules.json').write_text('[]')
os.environ.update(QT_QPA_PLATFORM='offscreen',RAT_STATE_DIR=str(state),RAT_LOG_DIR=str(state/'logs'),
                  RAT_DB_PATH=str(state/'fixture.db'),RAT_DOCUMENT_MODEL_PATH='',RAT_DOCUMENT_MODEL_PRELOAD='0',
                  RAT_REDUCE_MOTION='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
os.environ.pop('RAT_WORKBENCH_SCENE',None)
os.environ.pop('RAT_WORKBENCH_FINDER',None)

def guard(event, values):
    if event=='import' and values[0].split('.')[0] in {'mlx','mlx_lm','fastembed','torch','transformers','onnxruntime'}:
        raise ImportError('model runtimes disabled in startup fixture')
    if event=='socket.connect':
        import socket
        if values[0].family!=socket.AF_UNIX:raise PermissionError('network disabled in startup fixture')
sys.addaudithook(guard)

if revision=='baseline':
    class SnapshotImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {'rat.ui.omnibar','rat.ui.assistant_worker','rat.ui.surface_layout','rat.ui.workbench_scene'}:
                return importlib.util.spec_from_file_location(fullname,HERE/'source_start'/(fullname.replace('.','/')+'.py'))
    sys.meta_path.insert(0,SnapshotImports())

from PyQt6.QtWidgets import QApplication, QWidget
from unittest.mock import Mock
app=QApplication([])
started=time.perf_counter()
from rat.ui import omnibar
import_ms=(time.perf_counter()-started)*1000
database=Mock()
database.get_stats.return_value={'total_files':0}
database.get_recent_documents.return_value=[]
database._local.conn=None
omnibar.Database=Mock(return_value=database)
omnibar.SearchEngine=Mock()
omnibar.load_club_members=lambda:[]
from rat.ui import feedback
feedback.FeedbackLog=Mock()
from rat.engine.app_resolver import ApplicationCatalog
ApplicationCatalog.scan=classmethod(lambda cls,*a,**k:cls())
from rat.engine.slm import slm_engine
slm_engine.is_service_running=lambda:False
slm_engine.list_installed_models=lambda:[]
gc.collect()
started=time.perf_counter()
window=omnibar.OmnibarWindow()
constructor_ms=(time.perf_counter()-started)*1000
widgets=len(window.findChildren(QWidget))
started=time.perf_counter()
window.show_omnibar()
app.processEvents()
show_ms=(time.perf_counter()-started)*1000
window.shutdown()
window.hide()
print(json.dumps({'revision':revision,'import_ms':import_ms,'constructor_ms':constructor_ms,
                  'show_and_events_ms':show_ms,'widgets_after_construct':widgets}))
