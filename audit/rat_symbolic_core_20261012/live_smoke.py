"""One real-model development smoke through the default RAT runtime, no indexing."""
import json
import hashlib
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import slm_engine
from rat.timetable.compositor import TimetableCompositor


class BoundedClient:
    def chat_with_meta(self, messages, tools, **kwargs):
        return slm_engine.chat_with_meta(messages, tools, timeout=40, **kwargs)


if __name__ == '__main__':
    output = Path(__file__).with_name(sys.argv[1] if len(sys.argv) > 1 else 'live_smoke.json')
    if output.exists():
        raise SystemExit('Use a new output name; existing smoke artifacts are preserved.')
    source_hashes = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in
                     ['rat/engine/verification.py', 'rat/engine/assistant_runtime.py', 'rat/kernel/registry.py',
                      'rat/kernel/capabilities/__init__.py', 'rat/engine/slm.py']}
    with tempfile.TemporaryDirectory(prefix='rat-symbolic-smoke-') as temporary:
        db = Database(str(Path(temporary) / 'empty.db'))
        runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]),
                                   model_client=BoundedClient(), plan_tasks=True)
        response = runtime.run('47 * 83', max_steps=8)
        result = {'evidence_scope': 'single_real_model_development_smoke',
                  'model': slm_engine.model, 'query': '47 * 83',
                  'synthetic_fallback': False, 'personal_file_indexing': False,
                  'source_sha256_before_import_run': source_hashes,
                  'response': asdict(response)}
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n')
        print(json.dumps({'model': slm_engine.model, 'answer': response.answer, 'error': response.error,
                          'verification': response.answer_verification_status, 'total_tokens': response.total_tokens,
                          'model_time_ms': response.model_time_ms, 'verification_time_ms': response.verification_time_ms,
                          'steps': len(response.steps)}, ensure_ascii=False), flush=True)
        db.get_connection().close()
