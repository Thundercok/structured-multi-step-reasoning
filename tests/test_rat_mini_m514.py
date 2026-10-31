"""Placement/state contracts only. Fixtures are not real UI/model acceptance."""
import os
import subprocess
import sys
import pytest
from rat.ui.mini_placement import Rect, place_look, LOOK_WIDTH, LOOK_HEIGHT
from rat.engine.local_translation import sentence_units, token_batches


@pytest.mark.parametrize('area', [Rect(0,0,1920,1080), Rect(-1440,0,1440,900), Rect(0,0,640,600)])
@pytest.mark.parametrize('edge', ['left','right','middle'])
def test_rat_never_resizes_or_overlaps_and_stays_on_screen(area, edge):
    x = area.x if edge == 'left' else area.right-LOOK_WIDTH if edge == 'right' else area.x+area.width//2-LOOK_WIDTH//2
    home = (x, area.bottom-LOOK_HEIGHT-32)
    idle = place_look(area, home)
    small = place_look(area, home, 380, 180, 'B')
    large = place_look(area, home, 580, 500, 'B', small.side)
    for placement in (idle, small, large):
        assert (placement.rat.width,placement.rat.height) == (LOOK_WIDTH,LOOK_HEIGHT)
        assert placement.bounds.x >= area.x and placement.bounds.right <= area.right
        assert placement.bounds.y >= area.y and placement.bounds.bottom <= area.bottom
    assert (small.panel.right <= small.rat.x or small.panel.x >= small.rat.right
            or small.panel.bottom <= small.rat.y + 4)
    assert large.side == small.side


def test_collapse_restores_user_home_instead_of_temporary_dock():
    area, home = Rect(0,0,1440,900), (300,600)
    collapsed = place_look(area,home)
    expanded = place_look(area,home,580,500,'B')
    assert place_look(area,home) == collapsed
    assert (collapsed.rat.x,collapsed.rat.y) == (expanded.rat.x,expanded.rat.y)


def test_local_sentence_preprocessing_preserves_all_input_and_abbreviations():
    source = 'Dr. Smith arrived.  Hello world! This is a short public text for translation.'
    units = list(sentence_units(source))
    assert ''.join(sentence+separator for sentence,separator in units) == source
    assert units[0][0] == 'Dr. Smith arrived.'
    assert units[1][0] == 'Hello world!'
    tokens = ['▁word']*620
    batches = list(token_batches(tokens))
    assert [token for batch in batches for token in batch] == tokens
    assert all(0 < len(batch) <= 256 for batch in batches)


def test_spotlight_retries_timeout_only_within_same_scope_and_deadline(monkeypatch):
    import time
    from rat.engine import local_finder as finder
    calls=[]
    deadline=time.monotonic()+12
    def query(root,predicate,cancel,budget):
        calls.append((root,predicate,budget))
        if len(calls)==1:
            raise finder.SpotlightTimeout(['/selected/partial.pdf'])
        return ['/selected/found.pdf']
    monkeypatch.setattr(finder,'spotlight_paths',query)
    rows,errors,complete=finder.spotlight_scopes(['/selected'],'exact query',lambda:False,deadline)
    assert rows==['/selected/partial.pdf','/selected/found.pdf'] and not errors and complete==1
    assert all(root=='/selected' and predicate=='exact query' and budget<=deadline for root,predicate,budget in calls)
    calls.clear()
    def denied(*args):
        calls.append(args)
        raise finder.SpotlightFailure('spotlight_permission_denied')
    monkeypatch.setattr(finder,'spotlight_paths',denied)
    _,errors,complete=finder.spotlight_scopes(['/selected'],'exact query',lambda:False,deadline)
    assert len(calls)==1 and complete==0 and errors[0]['code']=='spotlight_permission_denied'


def test_qml_edit_replaces_result_and_dismiss_keeps_draft(tmp_path):
    script = r'''
from PyQt6.QtCore import QObject, qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.ui.mini_quick import create_mini_desk
from rat.engine.mini_settings import DEFAULTS
messages=[]
qInstallMessageHandler(lambda kind,ctx,msg: messages.append(msg))
app=QGuiApplication([])
view,c=create_mini_desk(dict(DEFAULTS,roots=[__import__('sys').argv[1]],setup_completed=True,permission_hello_version=1))
root=view.rootObject()
editor=root.findChild(QObject,'miniEditor')
translation=root.findChild(QObject,'translationText')
ocr=root.findChild(QObject,'ocrSourceEditor')
editor.setProperty('text','Unsent software-contract draft')
c.update(phase='result',busy=False,expanded=True,hasWorkbench=True,view='translation',
    text='Synthetic layout only',requestText='Contract fixture',hasOcrSource=True,
    ocrText='Source draft',ocrCommittedText='Source draft',ocrOriginalText='Original source')
for _ in range(20):app.processEvents()
rat=root.findChild(QObject,'mascotCrop')
assert (rat.property('width'),rat.property('height')) == (144,144)
c.showSurface('ocr')
for _ in range(10):app.processEvents()
assert ocr.property('visible') and not translation.property('visible')
c.backSurface()
for _ in range(10):app.processEvents()
assert translation.property('visible') and not ocr.property('visible')
shell=view._refs[3]
shell.present()
shell.native_activation_changed(False)
QTest.qWait(220)
assert not view.isVisible()
shell.present()
shell.dismiss()
assert not view.isVisible()
c.update(text='Late synthetic completion')
for _ in range(10):app.processEvents()
assert not view.isVisible()
assert editor.property('text') == 'Unsent software-contract draft'
assert c.snapshot['ocrText'] == 'Source draft'
errors=[m for m in messages if any(s in m for s in ('ReferenceError','TypeError','Binding loop','Cannot assign','is not a function'))]
assert not errors, errors
'''
    result = subprocess.run([sys.executable,'-c',script,str(tmp_path)],
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr


def test_production_paper_gutter_keeps_mascot_clear_of_result():
    area, home = Rect(0, 0, 1440, 900), (650, 600)
    for side in ('left', 'right'):
        placed = place_look(area, home, 580, 500, 'B', side)
        assert placed.panel.right <= placed.rat.x or placed.panel.x >= placed.rat.right
        assert (placed.rat.width, placed.rat.height) == (LOOK_WIDTH, LOOK_HEIGHT)
        assert area.x <= placed.bounds.x and placed.bounds.right <= area.right
        assert placed.panel.width == 580
