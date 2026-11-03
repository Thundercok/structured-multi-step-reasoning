"""Software contracts with controlled providers. No fixtures are UI acceptance."""
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from rat.engine.local_finder import ScopePolicy, HybridFinder
from rat.engine.snippet_translation import SnippetTranslator, split_utf8
from rat.mini import MiniSession
from rat.kernel.contracts import Artifact


def settings(tmp_path):
    return dict(roots=[str(tmp_path)],provider='openai',model='gpt-4.1-mini',
                translation_provider='mymemory',free_fallback=True,target_language='vi',
                source_language='en',semantic_enabled=False)


def test_mini_import_and_composition_do_not_load_other_products(tmp_path):
    script = 'from rat.mini import MiniSession; import sys; '
    script += 's=MiniSession('+repr(settings(tmp_path))+'); '
    script += "assert {c.name for c in s.runtime.registry.list_capabilities()} == {'finder','translation','mini_setup','applications'}; "
    script += "assert {t.name for t in s.runtime.registry.to_tool_definitions()} == {'find_files','translate_text','open_application'}; "
    script += "assert not any(n.startswith(('rat.timetable','rat.crawler','rat.astrology','PyQt6','onnxruntime','mlx')) for n in sys.modules)"
    r = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
    assert r.returncode == 0,r.stderr


def test_scope_escape_and_identity_replacement_rejected(tmp_path):
    root=tmp_path/'root';root.mkdir()
    inside=root/'file.txt';inside.write_text('one')
    outside=tmp_path/'secret.txt';outside.write_text('secret')
    (root/'link.txt').symlink_to(outside)
    scope=ScopePolicy([root])
    _,_,identity=scope.verify(inside)
    with pytest.raises(ValueError,match='scope'):
        scope.verify(root/'link.txt')
    inside.unlink();inside.write_text('replacement')
    with pytest.raises(ValueError,match='stale'):
        scope.verify(inside,identity)


def test_filename_priority_filters_and_shared_dispatch(tmp_path,monkeypatch):
    first=tmp_path/'wanted.pdf';first.write_bytes(b'not a PDF: metadata contract only')
    second=tmp_path/'other.txt';second.write_text('metadata')
    monkeypatch.setattr('rat.engine.local_finder.spotlight_paths',lambda *a:[str(second),str(first)])
    s=MiniSession(settings(tmp_path))
    events=[]
    r=s.execute('find_files',{'query':'wanted.pdf','filters':{'extensions':['.pdf']}},on_event=events.append)
    assert r.error is None and r.answer_verification_status=='PASS'
    assert r.artifacts[0].payload['hits'][0]['path']==str(first)
    assert s.client.calls==0
    assert [e.type for e in events][-3:]==['checking','deciding','turn_completed']


def test_spotlight_default_scopes_start_together_and_keep_partial_hits(tmp_path, monkeypatch):
    """A blocked root must not starve the other two default roots."""
    import threading
    from rat.engine.local_finder import spotlight_scopes
    roots = [tmp_path/name for name in ('Documents','Desktop','Downloads')]
    started = threading.Barrier(3)
    def query(root, predicate, cancel, deadline):
        started.wait(timeout=2)
        if root.name == 'Documents':
            raise TimeoutError('controlled blocked root')
        return [str(root/'public.txt')]
    monkeypatch.setattr('rat.engine.local_finder.spotlight_paths', query)
    paths, errors, completed = spotlight_scopes(roots, 'query', lambda:False, 123)
    assert paths == [str(roots[1]/'public.txt'), str(roots[2]/'public.txt')]
    assert completed == 2
    assert errors == [{'provider':'spotlight','code':'TimeoutError','scope_index':0}]


def test_spotlight_cancel_kills_and_reaps_process(tmp_path, monkeypatch):
    import threading
    import time
    import rat.engine.local_finder as finder_module
    stopped = threading.Event()
    real_popen = subprocess.Popen
    children = []
    def spawn(*args, **kwargs):
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(20)'], **kwargs)
        children.append(child)
        stopped.set()
        return child
    monkeypatch.setattr(finder_module.subprocess, 'Popen', spawn)
    with pytest.raises(ValueError, match='cancelled:finder'):
        finder_module.spotlight_paths(tmp_path, 'query', stopped.is_set, time.monotonic()+2)
    assert len(children) == 1 and children[0].returncode is not None


def test_spotlight_timeout_keeps_only_complete_rows_and_verifies_hits(tmp_path, monkeypatch):
    import time
    import rat.engine.local_finder as finder_module
    real_popen = subprocess.Popen
    found=tmp_path/'public.txt';found.write_text('public contract data')
    escaped=tmp_path/'scope';escaped.mkdir()
    script='import os,time; os.write(1,'+repr(str(found).encode()+b'\0/incomplete')+'); time.sleep(20)'
    monkeypatch.setattr(finder_module.subprocess,'Popen',lambda *args,**kwargs:real_popen([sys.executable,'-c',script],**kwargs))
    with pytest.raises(finder_module.SpotlightTimeout) as raised:
        finder_module.spotlight_paths(tmp_path,'query',lambda:False,time.monotonic()+0.5)
    assert raised.value.partial_paths == [str(found)]
    def partial(*args):raise finder_module.SpotlightTimeout([str(found)])
    monkeypatch.setattr(finder_module,'spotlight_paths',partial)
    result=HybridFinder(ScopePolicy([tmp_path])).search('public.txt')
    assert result['status']=='partial' and result['hits'][0]['path']==str(found)
    # Same provider output is rejected when it is outside the selected scope.
    result=HybridFinder(ScopePolicy([escaped])).search('public.txt')
    assert result['hits']==[]


def test_hidden_operations_require_real_user_context(tmp_path):
    s=MiniSession(settings(tmp_path))
    r=s.runtime.dispatcher.execute_operation('capture_text',{'mode':'clipboard'})
    assert r.status=='error' and 'user_action' in r.error
    with pytest.raises(ValueError,match='disabled'):
        s.runtime.load_tool_pack('timetable')


@pytest.mark.parametrize('mode', ['clipboard', 'image'])
def test_ocr_correction_contract_retains_source_and_edit_chain(tmp_path, mode):
    """Dispatcher regression only; seeded source is not live OCR/UI evidence."""
    import copy
    import time
    original = {'text': 'Hello wor1d.', 'source_kind': mode,
        'source_sha256': hashlib.sha256(b'Hello wor1d.').hexdigest(),
        'captured_at': time.time(), 'language_hint': 'en'}
    if mode == 'image':
        original['input_provenance'] = {'version': 1, 'kind': 'image',
            'input_id': 'img-' + 'a' * 32, 'origin': 'clipboard_image',
            'content_sha256': 'b' * 64, 'byte_count': 100,
            'source_file_sha256': None}
    session = MiniSession(settings(tmp_path))
    parent = Artifact('contract-source', 'captured_text', 1, copy.deepcopy(original))
    session.runtime.artifact_store.put(parent)
    root_ref = {'artifact_id': parent.id, 'revision': 1}
    pin = root_ref
    for text in ('Hello world.', 'Hello world. A second edit.'):
        response = session.execute('correct_captured_text', {'source_ref': pin, 'text': text})
        assert response.error is None, response.error
        assert response.answer_verification_status == 'PASS'
        edited = next(a for a in response.artifacts if a.kind == 'captured_text')
        assert edited.id != pin['artifact_id']
        assert edited.payload['text'] == text
        assert edited.payload['correction']['parent_ref'] == pin
        assert edited.payload['correction']['root_source_ref'] == root_ref
        assert edited.payload['source_kind'] == mode
        assert edited.payload.get('input_provenance') == original.get('input_provenance')
        pin = {'artifact_id': edited.id, 'revision': edited.revision}
    assert session.runtime.artifact_store.get(parent.id).payload == original
    assert session.client.calls == 0


def test_missing_folder_keeps_input_request(tmp_path):
    conf=settings(tmp_path);conf['roots']=[]
    r=MiniSession(conf).execute('find_files',{'query':'x'})
    assert r.error is None and r.completion_status=='needs_input'
    assert r.pending_input_request is not None


def test_utf8_chunks_preserve_every_character_and_byte_budget():
    text=('Tiếng Việt 🐭\n日本語 café '*100)
    chunks=list(split_utf8(text))
    assert ''.join(t for _,_,t in chunks)==text
    cursor=0
    for start,end,piece in chunks:
        assert start==cursor and len(piece.encode())<=500
        assert text[start:end]==piece
        cursor=end


def test_translation_partial_and_service_verifier(tmp_path,monkeypatch):
    import rat.engine.local_translation as local
    calls=[]
    class Local:
        directory=tmp_path
        model_info={'id':'en-vi', 'package_sha256':'0'*64, 'device':'cpu'}
        def __init__(self, directory=None): pass
        def translate(self, text, source, target, cancelled=lambda: False):
            calls.append(text)
            if len(calls)==2: raise TimeoutError('controlled provider failure')
            return 'contract translation'
    monkeypatch.setattr(local, 'LocalTranslator', Local)
    monkeypatch.setattr(local, 'is_local_models_ready', lambda directory: True)
    s=MiniSession(settings(tmp_path))
    r=s.execute('translate_text',{'text':'a'*2500,'source_language':'en','target_language':'vi'})
    assert r.error is None and r.completion_status=='partial'
    data=r.artifacts[0].payload
    assert data['status']=='partial' and len(data['segments'])==2
    assert data['source_sha256']==hashlib.sha256(('a'*2500).encode()).hexdigest()
    assert r.answer_verification_status=='UNKNOWN'


def test_no_online_fallback_without_opt_in(tmp_path,monkeypatch):
    cfg=settings(tmp_path);cfg['free_fallback']=False
    def unexpected(*args,**kwargs): pytest.fail('unexpected online request')
    monkeypatch.setattr(SnippetTranslator,'_cloud',unexpected)
    with pytest.raises(ValueError,match='not_enabled'):
        SnippetTranslator(cfg).translate('a paragraph','en','vi')


def test_mymemory_quota_does_not_repeat_requests_for_retry(tmp_path, monkeypatch):
    calls=[]
    def exhausted(*args, **kwargs):
        calls.append(1)
        return {'quotaFinished':True, 'responseStatus':429}
    monkeypatch.setattr('rat.engine.snippet_translation.request_json', exhausted)
    translator=SnippetTranslator(settings(tmp_path))
    for _ in range(2):
        with pytest.raises(ValueError,match='translation_quota_exhausted'):
            translator.translate('Public text','en','vi')
    assert len(calls) == 1


def test_lite_never_reaches_the_model_loop(tmp_path):
    s=MiniSession(dict(settings(tmp_path), llm_enabled=True))
    assert not s.settings['llm_enabled'] and s.settings['translation_provider']=='local'
    r=s.execute(query='find wanted.txt')
    assert r.error=='mini_llm_disabled' and s.client.calls==0


def test_automatic_translation_falls_back_to_google_gtx(tmp_path, monkeypatch):
    conf = settings(tmp_path)
    conf['translation_provider'] = 'automatic'
    conf['free_fallback'] = True
    from rat.engine.local_translation import LocalTranslator
    monkeypatch.setattr(LocalTranslator, 'translate', lambda *a, **k: (_ for _ in ()).throw(ValueError('translation_local_unavailable')))
    cloud_calls = []
    def fake_cloud(self, provider, text, source, target, should_cancel, timeout):
        cloud_calls.append((provider, text, source, target))
        return 'Bản dịch thử nghiệm'
    monkeypatch.setattr(SnippetTranslator, '_cloud', fake_cloud)
    translator = SnippetTranslator(conf)
    result = translator.translate('Hello world', 'en', 'vi')
    assert result['status'] == 'complete'
    assert result['text'] == 'Bản dịch thử nghiệm'
    assert 'google_gtx' in result['provider']
    assert any('trực tuyến' in w for w in result['warnings'])
    assert len(cloud_calls) == 1
    assert cloud_calls[0][0] == 'google_gtx'


def test_finder_name_walk_fallback_when_spotlight_empty(tmp_path, monkeypatch):
    """When Spotlight returns no paths and there is no index, HybridFinder must fallback to name_walk_paths."""
    doc = tmp_path / "report_2026.txt"
    doc.write_text("unindexed test content")
    monkeypatch.setattr('rat.engine.local_finder.spotlight_paths', lambda *a: [])
    finder = HybridFinder(ScopePolicy([tmp_path]), semantic=None)
    res = finder.search("report")
    assert len(res['hits']) == 1
    assert res['hits'][0]['path'] == str(doc)
    assert res['diagnostics']['name_walk'] == 'complete'

