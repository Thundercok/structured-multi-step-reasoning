"""Native Cocoa fixture host. Model calls and real app/file launch are disabled."""
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rat.os import diagnostics

original_prepare = diagnostics.prepare_session
session = None
native_app = None
blocked = []

def guard(event, values):
    if event == 'import' and values[0].split('.')[0] in {'mlx','mlx_lm','fastembed','torch','transformers','onnxruntime'}:
        blocked.append(event)
        raise RuntimeError('native fixture: real model imports disabled')
    if event == 'socket.connect':
        import socket
        if values[0].family != socket.AF_UNIX:
            blocked.append(event)
            raise PermissionError('native fixture: network disabled')
sys.addaudithook(guard)

def record(kind, **values):
    with (session/'fixture_events.jsonl').open('a') as f:
        f.write(json.dumps({'time_monotonic':time.monotonic(),'kind':kind,**values})+'\n')

def prepare(output):
    global session, native_app
    session = original_prepare(output)
    from rat.crawler.db import Database
    db = Database(str(session/'state/fixture.db'))
    for name in ('flow-first.txt','flow-second.txt'):
        path = session/name
        path.write_text('Authored native interaction fixture. Never personal content.\n')
        db.upsert_document(dict(file_path=str(path),file_name=name,file_ext='.txt',
            file_size=path.stat().st_size,created_at=1,modified_at=1,indexed_at=1,
            content_text='Authored fixture',summary='Synthetic native flow fixture'))
    db.get_connection().close()
    from PyQt6.QtWidgets import QApplication
    native_app = QApplication.instance() or QApplication(sys.argv)
    native_app.setProperty('ratReduceMotion',True)
    from rat.engine.meta_reasoner import build_composed_meta_reasoner
    from reasoning.bundle import create_synthetic_specimen_bundle
    import numpy as np
    class Backend:
        hidden_size = 2
        def embed(self, query):
            record('synthetic_embed')
            return np.zeros(2)
        def run(self, strategy, query):
            record('synthetic_strategy',strategy=strategy.name)
            return 'Đây là kết quả fixture synthetic; không gọi model thật.',.9,7
    bundle,policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle,Backend(),policy,allow_synthetic=True)
    native_app.setProperty('ratReasoningEngine',engine)
    native_app.setProperty('ratAllowSyntheticPolicy',True)
    from rat.os.hotkey import GlobalHotkeyManager
    GlobalHotkeyManager.start = lambda self: False  # No event tap or permission prompt.
    from rat.ui import omnibar
    omnibar.open_file_default = lambda path: record('open_double',file=Path(path).name)
    omnibar.trigger_quicklook = lambda path: record('preview_double',file=Path(path).name)
    return session

diagnostics.prepare_session = prepare
try:
    raise SystemExit(diagnostics.run_session([str(Path(__file__).resolve().parent/'native-sessions'),'--seconds','600']))
finally:
    if session:
        (session/'fixture_guard.json').write_text(json.dumps({'blocked_operations':blocked,
            'real_model_calls':0,'real_file_or_app_launches':0,
            'scope':'Cocoa fixture interaction; opening and preview are doubles; hotkey disabled'},indent=2)+'\n')
