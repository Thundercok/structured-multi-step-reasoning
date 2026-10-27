"""Explicit frozen-bundle smoke, never used as UI/model-quality acceptance."""
import json
from pathlib import Path
import ssl
import sys


def main():
    import certifi
    from rat.mini import MiniSession
    settings = dict(roots=[],provider='openai',model='gpt-4.1-mini',translation_provider='apple',
                    free_fallback=False,source_language='auto',target_language='vi',semantic_enabled=False)
    session = MiniSession(settings)
    reply = session.execute('find_files',{'query':'bundle smoke: no filesystem search'})
    assert reply.pending_input_request and not reply.error
    ssl.create_default_context(cafile=certifi.where())
    forbidden = [name for name in ('onnxruntime','torch','fastembed','apsw','sqlite_vec','rat.timetable','rat.crawler.db')
                 if name in sys.modules]
    assert not forbidden, forbidden
    report = {'kind':'bundle_smoke_not_ui_acceptance','status':'passed',
        'capabilities':[c.name for c in session.runtime.registry.list_capabilities()],
        'model_tools':[t.name for t in session.runtime.registry.to_tool_definitions()],
        'ca_bundle_present':Path(certifi.where()).is_file(), 'forbidden_imports':forbidden,
        'model_loaded':False,'cloud_calls':session.client.calls}
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
