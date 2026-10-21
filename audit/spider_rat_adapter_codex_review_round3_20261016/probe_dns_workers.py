"""Offline resolver resource probe. All simulated blocked work is released."""
import concurrent.futures
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from rat.crawler.spider_adapter import SpiderAdapter,SpiderTimeoutError
release=threading.Event()
started=[]
def blocked_dns(*args):
    started.append(threading.current_thread())
    release.wait(3)
    return [(2,1,6,'',('93.184.216.34',443))]
try:
    with patch('socket.getaddrinfo',side_effect=blocked_dns):
        count=0
        for i in range(6):
            try:SpiderAdapter.resolve_dns_bounded('example.com',443,deadline=time.monotonic()+.04)
            except SpiderTimeoutError:count+=1
        result={'timeouts':count,'workers_still_running_after_timeouts':sum(t.is_alive() for t in started),'network_requests':False}
finally:
    release.set()
    for t in started:t.join(timeout=2)
result['workers_running_after_probe_release']=sum(t.is_alive() for t in started)
print(json.dumps(result,indent=2))
Path(__file__).with_name('dns_worker_results.json').write_text(json.dumps(result,indent=2))
