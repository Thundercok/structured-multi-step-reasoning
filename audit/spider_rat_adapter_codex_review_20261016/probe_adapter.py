"""Offline repros using local fake binaries only; no network requests."""
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from rat.crawler.spider_adapter import SpiderAdapter

results=[]
with tempfile.TemporaryDirectory() as directory:
    for name, payload, version in [
        ('large_valid_output', {'url':'https://example.com','status_code':200,'content':'x'*200000}, 'spider_cli 2.51.208'),
        ('wrong_version', {'url':'https://example.com','status_code':200,'content':'hello'}, 'spider_cli 99.0.0'),
        ('invalid_schema', {'url':'http://127.0.0.1/private','status_code':0,'content':{'unexpected':'object'}}, 'broken-version'),
    ]:
        path=Path(directory)/name
        path.write_text('#!'+sys.executable+' -S\nimport sys,json\nif "--version" in sys.argv:\n print('+repr(version)+')\nelse:\n print(json.dumps('+repr(payload)+'))\n')
        path.chmod(0o755)
        adapter=SpiderAdapter(binary_path=path,timeout_seconds=3)
        processes=[]
        import subprocess
        real_popen=subprocess.Popen
        def track(*args,**kwargs):
            p=real_popen(*args,**kwargs);processes.append(p);return p
        started=time.monotonic()
        with patch.object(SpiderAdapter,'validate_url',return_value=None),patch('rat.crawler.spider_adapter.subprocess.Popen',side_effect=track):
            try:
                result=adapter.scrape_page('https://example.com',max_chars=250000)
                row={'case':name,'outcome':'accepted','content':result.content[:100],'final_url':result.final_url,'status_code':result.status_code,'engine_version':result.engine_version}
            except Exception as exc:
                row={'case':name,'outcome':type(exc).__name__,'error':str(exc)}
            finally:
                for p in processes:
                    if p.poll() is None:p.kill()
                    p.communicate(timeout=3)
        row['elapsed_seconds']=round(time.monotonic()-started,3)
        results.append(row)
print(json.dumps(results,ensure_ascii=False,indent=2))
Path(__file__).with_name('probe_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
