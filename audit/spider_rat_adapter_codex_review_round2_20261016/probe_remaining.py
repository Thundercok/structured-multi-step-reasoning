"""Offline backend identity / deadline probes and read-only recovery verification."""
import hashlib,json,sys,tarfile,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from rat.crawler.spider_adapter import SpiderAdapter
results={}
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'spider'
    def write(version,content):
        path.write_text('#!'+sys.executable+' -S\nimport sys,json\nif "--version" in sys.argv:\n print('+repr(version)+')\nelse:\n print(json.dumps('+repr({'url':'https://example.com','status_code':200,'content':content})+'))\n')
        path.chmod(0o755)
    write('spider_cli 2.51.208','first')
    adapter=SpiderAdapter(binary_path=path)
    old_version,old_hash=adapter.verify_backend()
    write('spider_cli 99.0.0','second backend')
    actual_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    with patch.object(SpiderAdapter,'validate_url',return_value=None):
        result=adapter.scrape_page('https://example.com')
    results['binary_replaced_after_verification']={'accepted_content':result.content,'reported_version':result.engine_version,'reported_hash':result.binary_hash,'actual_hash':actual_hash,'hash_matches':result.binary_hash==actual_hash}
    # Explicitly slow mocked DNS, but no network or uncontrolled process.
    write('spider_cli 2.51.208','ok')
    adapter=SpiderAdapter(binary_path=path,timeout_seconds=.05)
    import socket
    defaults=[]
    def slow_dns(*args):
        defaults.append(socket.getdefaulttimeout());time.sleep(.3)
        return [(2,1,6,'',('93.184.216.34',443))]
    start=time.monotonic()
    with patch('socket.getaddrinfo',side_effect=slow_dns),patch.object(adapter,'verify_backend',return_value=('spider_cli 2.51.208','fake')),patch.object(adapter,'_execute_subprocess',return_value=(json.dumps({'url':'https://example.com','status_code':200,'content':'ok'}),'',0)):
        result=adapter.scrape_page('https://example.com')
    results['dns_not_bounded_by_socket_default']={'configured_timeout_seconds':.05,'elapsed_seconds':round(time.monotonic()-start,3),'global_socket_timeout_during_dns':defaults,'outcome':'accepted'}
archive=Path('scratch/spider_migration_bundle.tar.gz')
with tarfile.open(archive,'r:gz') as tar:
    mismatches=[];members={}
    for m in tar.getmembers():
        if m.isfile():
            members[m.name.removeprefix('./')]=m
    current={str(p) for p in Path('spider').rglob('*') if p.is_file()}
    for name in current:
        if name not in members:mismatches.append('missing:'+name);continue
        if hashlib.sha256(Path(name).read_bytes()).digest()!=hashlib.sha256(tar.extractfile(members[name]).read()).digest():mismatches.append('changed:'+name)
    results['recovery_archive']={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'current_files':len(current),'archive_regular_files':len(members),'mismatches':mismatches,'archive_extra_files':sorted(set(members)-current)}
Path(__file__).with_name('probe_results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
