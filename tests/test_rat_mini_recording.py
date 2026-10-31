"""Opt-in observability; real tools, no native acceptance claim."""
import os
import subprocess
import sys
import pytest


@pytest.mark.parametrize('blocked', [False, True])
def test_recording_never_replaces_real_translation_result(tmp_path, blocked):
    script = r'''
from pathlib import Path
import json,os
from PyQt6.QtCore import QCoreApplication
from rat.engine.mini_settings import DEFAULTS
from rat.mini import MiniSession
from rat.ui.mini_worker import MiniJob
app=QCoreApplication([])
root=Path(os.environ['QA_RECORD_ROOT'])
if os.environ['QA_BLOCKED']=='1': root.write_text('Recording target is a file')
os.environ['RAT_MINI_ACCEPTANCE_DIR']=str(root)
session=MiniSession(dict(DEFAULTS,roots=[],source_language='en',target_language='vi',free_fallback=False))
values=[]
job=MiniJob(session,'capture_translate',dict(mode='clipboard',clipboard_text='Hello world.',source_language='en',target_language='vi'),'',1)
job.result.connect(values.append);job.run()
assert len(values)==1 and values[0].get('response') is not None,values
response=values[0]['response']
assert not response.error and response.answer and session.client.calls==0
if os.environ['QA_BLOCKED']=='1':
 assert values[0].get('recording_error')
else:
 state=json.loads((root/'execution-status.json').read_text())
 assert state['state']=='finished' and state['receipt_written'] and not state['tool_error']
 receipt=json.loads((root/(response.execution_id+'.json')).read_text())
 assert receipt['llm_calls']==0 and receipt['capture_artifacts']
 assert state['execution_id']==receipt['events'][-1]['execution_id'] or state['execution_id']==response.execution_id
'''
    env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QA_RECORD_ROOT=str(tmp_path/'recording'), QA_BLOCKED='1' if blocked else '0')
    result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr


def test_ui_diagnostic_contains_metadata_without_draft_or_clipboard(tmp_path):
    script=r'''
from pathlib import Path
import json,os
from PyQt6.QtGui import QGuiApplication
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_diagnostics import BUILD
from rat.ui.mini_quick_controller import MiniQuickController
app=QGuiApplication([])
c=MiniQuickController(dict(DEFAULTS,roots=[],setup_completed=True))
private='PRIVATE_DIAGNOSTIC_BOUNDARY_STRING'
c.setComposerDraft(private)
c.update()
p=Path(os.environ['RAT_MINI_ACCEPTANCE_DIR'])/'ui-state.json'
text=p.read_text();d=json.loads(text)
assert not d['busy'] and d['pid'] and d['build']==BUILD
assert private not in text and 'text' not in d and 'draft' not in d
'''
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',RAT_MINI_ACCEPTANCE_DIR=str(tmp_path/'qa'),RAT_MINI_STATE_DIR=str(tmp_path/'state'))
    result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
