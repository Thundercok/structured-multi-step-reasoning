"""Software safety contracts; temporary fixture files are not live acceptance."""
import json
from pathlib import Path
import pytest
from rat.engine.folder_organization import FolderOrganizer
from rat.engine.local_finder import ScopePolicy
from rat.engine.mini_settings import DEFAULTS
from rat.mini import MiniSession


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('RAT_MINI_STATE_DIR', str(tmp_path/'state'))
    root = tmp_path/'Downloads'
    root.mkdir()
    return root, MiniSession(dict(DEFAULTS, roots=[str(root)]))


def result(response, kind):
    assert not response.error, response.error
    return next(a for a in response.artifacts if a.kind == kind)


def approve(session, operation, artifact):
    pin = {'artifact_id':artifact.id,'revision':artifact.revision}
    return session.execute(operation, pin, input_context={'organization_approval':pin})


def test_real_exclusive_moves_via_dispatcher_and_undo(tmp_path, monkeypatch):
    root, session = setup(tmp_path, monkeypatch)
    (root/'one.pdf').write_bytes(b'software fixture, not PDF acceptance')
    (root/'two.png').write_bytes(b'software fixture, not image acceptance')
    (root/'.hidden').write_text('keep')
    (root/'nested').mkdir()
    (root/'nested'/'stay.txt').write_text('keep')
    (root/'link.pdf').symlink_to(root/'one.pdf')
    plan = result(session.submit('Dọn Downloads theo loại file'), 'organization_plan')
    assert [m['name'] for m in plan.payload['moves']] == ['one.pdf','two.png']
    assert (root/'one.pdf').exists() and not (root/'Documents').exists()
    denied = session.execute('apply_folder_organization', {'artifact_id':plan.id,'revision':plan.revision})
    assert denied.error and (root/'one.pdf').exists()
    receipt = result(approve(session, 'apply_folder_organization', plan), 'organization_receipt')
    assert receipt.payload['status'] == 'applied'
    assert (root/'Documents/one.pdf').read_bytes().startswith(b'software fixture')
    assert (root/'Images/two.png').exists() and not (root/'two.png').exists()
    assert result(approve(session, 'apply_folder_organization', plan), 'organization_receipt').payload == receipt.payload
    undone = result(approve(session, 'undo_folder_organization', receipt), 'organization_receipt')
    assert undone.payload['status'] == 'undone' and (root/'one.pdf').exists() and (root/'two.png').exists()
    assert session.client.calls == 0
    assert {'apply_folder_organization','undo_folder_organization'}.isdisjoint(session.router.operations)


def test_source_change_collision_and_symlink_destination_never_overwrite(tmp_path, monkeypatch):
    root, session = setup(tmp_path, monkeypatch)
    for name in ('a.pdf','b.pdf','c.png'):
        (root/name).write_text('original')
    plan = result(session.submit('Sắp xếp Downloads'), 'organization_plan')
    (root/'a.pdf').write_text('changed after preview')
    (root/'Documents').mkdir()
    (root/'Documents/b.pdf').write_text('destination keep')
    outside = tmp_path/'outside'; outside.mkdir()
    (root/'Images').symlink_to(outside)
    receipt = result(approve(session,'apply_folder_organization',plan),'organization_receipt')
    assert receipt.payload['status'] == 'partial'
    assert all(x['state']=='skipped' for x in receipt.payload['entries'])
    assert (root/'a.pdf').read_text() == 'changed after preview'
    assert (root/'Documents/b.pdf').read_text() == 'destination keep'
    assert (root/'b.pdf').read_text() == 'original' and not list(outside.iterdir())


def test_undo_conflict_and_recovery_from_durable_intent(tmp_path, monkeypatch):
    root, session = setup(tmp_path, monkeypatch)
    (root/'a.txt').write_text('original')
    plan = result(session.submit('Dọn Downloads theo thời gian'),'organization_plan')
    receipt = result(approve(session,'apply_folder_organization',plan),'organization_receipt')
    (root/'a.txt').write_text('new file, keep')
    undone = result(approve(session,'undo_folder_organization',receipt),'organization_receipt')
    assert undone.payload['status']=='undo_partial'
    assert (root/'a.txt').read_text()=='new file, keep'
    (root/'a.txt').unlink()
    journal = tmp_path/'state/organization'/f"{plan.payload['plan_id']}.json"
    data=json.loads(journal.read_text()); data['entries'][0]['state']='move_pending'
    journal.write_text(json.dumps(data))
    recovered=result(session.execute('get_last_organization',{}),'organization_receipt')
    assert result(approve(session,'undo_folder_organization',recovered),'organization_receipt').payload['status']=='undone'
    assert (root/'a.txt').read_text()=='original'


def test_preview_bounds_scope_and_modified_destination(tmp_path, monkeypatch):
    root, session=setup(tmp_path, monkeypatch)
    outside=tmp_path/'outside';outside.mkdir()
    assert session.execute('plan_folder_organization', {'folder':str(outside)}).error
    for n in range(105): (root/f'{n:03}.txt').write_text('fixture')
    plan=result(session.submit('Dọn Downloads'),'organization_plan')
    assert len(plan.payload['moves'])==100 and plan.payload['limited']
    receipt=result(approve(session,'apply_folder_organization',plan),'organization_receipt')
    (root/'Documents/000.txt').write_text('edited, keep here')
    undone=result(approve(session,'undo_folder_organization',receipt),'organization_receipt')
    assert undone.payload['status']=='undo_partial'
    assert (root/'Documents/000.txt').read_text()=='edited, keep here' and not (root/'000.txt').exists()


def test_readiness_and_router_clarification_use_tools(tmp_path, monkeypatch):
    root, session=setup(tmp_path, monkeypatch)
    ask=session.submit('Dọn thư mục theo tháng')
    assert ask.pending_input_request
    assert result(session.submit('Downloads'),'organization_plan').payload['rule']=='month'
    check=result(session.execute('check_mini_readiness',{}),'mini_readiness')
    assert check.payload['checks'] and session.client.calls==0
    assert next(x for x in check.payload['checks'] if x['key']=='screen')['state']=='not_required'
