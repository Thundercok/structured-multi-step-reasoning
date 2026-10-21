"""Explicit offline desktop test environment; never connect to a model service."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
state = Path(__file__).resolve().parent / 'test-state'
state.mkdir(exist_ok=True)
(state / 'config.json').write_text(json.dumps(dict(first_run_completed=True,
    indexed_directories=[], auto_watch=False, llm_provider='offline',
    document_model_path='', document_model_preload=False, memory_sentinel_enabled=False)))
(state / 'club_schedules.json').write_text('[]')
os.environ.update(RAT_STATE_DIR=str(state), RAT_DB_PATH=str(state/'fixture.db'),
    RAT_LOG_DIR=str(state/'logs'), RAT_DOCUMENT_MODEL_PATH='', RAT_DOCUMENT_MODEL_PRELOAD='0',
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', RAT_WORKBENCH_SCENE='0', RAT_WORKBENCH_FINDER='0')

def guard(event, values):
    if event == 'socket.connect':
        import socket
        if values[0].family != socket.AF_UNIX:
            raise PermissionError('network disabled for fixture tests')
    if event == 'import' and values[0].split('.')[0] in {'mlx','mlx_lm','fastembed','transformers','torch','onnxruntime'}:
        raise ImportError('real model runtimes disabled for fixture tests')
sys.addaudithook(guard)
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
