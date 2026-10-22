"""Read received evidence; write crosscheck results only beside this script."""
from collections import Counter
from pathlib import Path
import hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
RECEIVED=HERE/'received_runtime'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
def write(name,value):(HERE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def xml_summary(path):
 root=ET.parse(path).getroot();cases=root.findall('.//testcase')
 counts={'executions':len(cases),'failures':sum(c.find('failure') is not None for c in cases),'errors':sum(c.find('error') is not None for c in cases),'skipped':sum(c.find('skipped') is not None for c in cases)}
 counts['passed']=counts['executions']-counts['failures']-counts['errors']-counts['skipped']
 counts['xml_duration_s']=sum(float(s.get('time','0')) for s in root.findall('testsuite')) if root.tag=='testsuites' else float(root.get('time','0'))
 counts['identities']=[(c.get('classname',''),c.get('name','')) for c in cases]
 return counts
commands=json.loads((RECEIVED/'commands.json').read_text());rows=[];identities=Counter()
for command in commands:
 summary=xml_summary(RECEIVED/command['junit_xml']);identities.update(summary.pop('identities'))
 log=(RECEIVED/command['raw_log']).read_text();matched=re.findall(r'(\d+) passed[^\n]*?in ([0-9.]+)s',log)
 assert matched,command['raw_log']
 stdout_passed,stdout_duration=int(matched[-1][0]),float(matched[-1][1])
 row={'name':command['name'],'xml':command['junit_xml'],**summary,'stdout_passed':stdout_passed,'stdout_duration_s':stdout_duration}
 row['metadata_matches']=(summary['executions']==command['total_tests'] and summary['passed']==command['passed']==stdout_passed and summary['failures']==command['failed'] and summary['errors']==0 and abs(summary['xml_duration_s']-command['xml_duration_s'])<.00001 and stdout_duration==command['duration_s'])
 rows.append(row)
validation=json.loads((RECEIVED/'validation.json').read_text())
accounting={'total_test_executions':sum(identities.values()),'distinct_test_identities':len(identities),'repeated_executions':sum(identities.values())-len(identities)}
assert accounting=={k:validation['test_execution_accounting'][k] for k in accounting}
assert all(row['metadata_matches'] for row in rows)
incident=json.loads((RECEIVED/'r4_baseline_xml_incident.json').read_text())
assert digest(ROOT/incident['file'])==incident['actual_sha256']
packetdir=ROOT/'audit/cot_restart_fresh_data_review_20261016';packet=json.loads((packetdir/'manifest.json').read_text())
data_entries={**packet['inputs_sha256'],**{str((packetdir/k).relative_to(ROOT)):v for k,v in packet['artifact_sha256'].items()}}
data_mismatch={k:{'expected':v,'actual':digest(ROOT/k)} for k,v in data_entries.items() if digest(ROOT/k)!=v}
assert not data_mismatch
patch_files=['qwen_mlx_backend.py','reasoning/runtime.py','reasoning/bundle.py'];replay=HERE/'patch_replay_source'
for name in patch_files:
 dst=replay/name;dst.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(ROOT/'audit/rat_cot_runtime_codex_review_r5_20261021/reviewed_source'/name,dst)
proc=subprocess.run(['patch','--batch','-p1','--input',str(RECEIVED/'repair_diff.patch')],cwd=replay,text=True,capture_output=True)
(HERE/'patch_replay.txt').write_text(proc.stdout+proc.stderr)
replayed={name:{'expected_current':digest(ROOT/name),'replayed':digest(replay/name)} for name in patch_files}
assert proc.returncode==0 and all(v['expected_current']==v['replayed'] for v in replayed.values())
local={}
for filename in ['current_contracts.xml','remaining_flow.xml','remaining_flow_v2.xml','remaining_flow_v3.xml']:
 summary=xml_summary(HERE/filename);summary.pop('identities');local[filename]=summary
result={'submitted_suites':rows,'submitted_accounting':accounting,'all_submitted_metadata_matches':True,'historical_regression':{'sha256':digest(RECEIVED/'regression.xml'),'received_as':'historical r5 baseline; not a fresh current-source regression run','rerun_in_this_review':False},'r4_incident':incident,'data_hash_check':{'entries':len(data_entries),'mismatches':data_mismatch,'heldout_content_printed':False},'patch_replay':{'exit_code':proc.returncode,'files':replayed},'independent_runs':local}
write('submitted_evidence_crosscheck.json',result)
print(json.dumps({'submitted_accounting':accounting,'all_metadata_matches':True,'patch_replay_matches':True,'data_hashes':len(data_entries),'independent_runs':local},indent=2))
