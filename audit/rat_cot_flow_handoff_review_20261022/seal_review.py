"""Record final integrity without mutating received or historical evidence."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
INCOMING=ROOT/'audit/rat_cot_runtime_acceptance_20261020'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def write(n,d):(HERE/n).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def load(n):return json.loads((HERE/n).read_text())
def differences(expected,base):return {name:{'expected':value,'actual':digest(base/name)} for name,value in expected.items() if digest(base/name)!=value}
initial=load('integrity_initial.json');start=load('source_start.json')['files']
end={name:digest(ROOT/name) for name in start};source_drift=differences(start,ROOT)
write('source_end.json',{'collected_at_utc':datetime.now(timezone.utc).isoformat(),'files':end,'drift_from_review_start':source_drift})
prior={}
for folder,record in initial['prior_reviews'].items():
 base=ROOT/'audit'/folder
 manifest=base/('manifest.json' if folder=='rat_cot_runtime_codex_review_20261020' else 'artifact_manifest.json')
 # r1 uses manifest.json; retain each actual manifest identity from the initial record.
 if digest(manifest)!=record['manifest_sha256']:
  matches=[p for p in base.glob('*manifest*.json') if digest(p)==record['manifest_sha256']]
  if matches:manifest=matches[0]
 prior[folder]={'entries':record['entries'],'original_manifest_mismatches':record['mismatches'],'changes_since_review_start':differences(record['current_files'],base),'manifest':str(manifest.relative_to(ROOT)),'manifest_unchanged':digest(manifest)==record['manifest_sha256']}
submitted_source=load('received_runtime/source_end.json')['files'];submitted_artifacts=load('received_runtime/artifact_manifest.json')
ledger=digest(INCOMING/'calls.jsonl')
status=subprocess.run(['git','status','--short'],cwd=ROOT,text=True,capture_output=True,check=True).stdout
(HERE/'git_status_final.txt').write_text(status)
branch=subprocess.run(['git','branch','--show-current'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
external='/Users/thundercock2/.gemini/antigravity/brain/2dfc111c-d39a-43cf-a703-6e242225c43a/rat_cot_end_to_end_preparation_20261022.md'
receipts=[]
for path,label in [('/Users/thundercock2/.codex/attachments/771e8a58-9b51-41f4-9b75-50c6b524191a/Văn bản đã dán.txt','runtime_handoff.txt'),('/Users/thundercock2/.codex/attachments/7d0c7602-363e-406c-a335-6205a13c0dce/Văn bản đã dán.txt','flow_handoff.txt')]:
 dest=HERE/'received_messages'/label;dest.parent.mkdir(exist_ok=True);shutil.copyfile(path,dest)
 receipts.append({'original_path':path,'copy':str(dest.relative_to(HERE)),'sha256':digest(dest),'original_matches_copy':digest(Path(path))==digest(dest)})
receipts.append({'original_path':external,'copy':'received_flow_preparation.md','sha256':digest(HERE/'received_flow_preparation.md'),'original_matches_copy':digest(Path(external))==digest(HERE/'received_flow_preparation.md')})
write('input_receipts.json',receipts)
extra=['rat/ui/chat_session.py','rat/engine/work_notes.py','rat/kernel/contracts.py','rat/kernel/dispatcher.py']
extra_hashes={name:digest(ROOT/name) for name in extra}
for name in extra:
 dest=HERE/'reviewed_source'/name;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(ROOT/name,dest)
write('additional_reviewed_source.json',{'scope':'Static source inspection for revision semantics; collected after tests, not retroactively a start snapshot','files':extra_hashes})
final={'review_source_entries':len(start),'review_source_drift':source_drift,'submitted_source_entries':len(submitted_source),'submitted_source_mismatches':differences(submitted_source,ROOT),'submitted_artifact_entries':len(submitted_artifacts),'submitted_artifact_mismatches':differences(submitted_artifacts,INCOMING),'incoming_changes_since_review_start':differences(initial['incoming_files'],INCOMING),'received_snapshot_changes_since_review_start':differences(initial['incoming_files'],HERE/'received_runtime'),'prior_reviews':prior,'ledger_sha256':ledger,'ledger_unchanged':ledger==initial['ledger_sha256'],'branch':branch,'input_receipts_match':all(r['original_matches_copy'] for r in receipts)}
assert not source_drift and not final['submitted_source_mismatches'] and not final['submitted_artifact_mismatches'] and not final['incoming_changes_since_review_start'] and not final['received_snapshot_changes_since_review_start']
assert all(not v['changes_since_review_start'] and v['manifest_unchanged'] for v in prior.values())
assert final['ledger_unchanged'] and branch=='main' and final['input_receipts_match']
write('integrity_final.json',final)
cross=load('submitted_evidence_crosscheck.json')
base='.venv/bin/python -m pytest audit/rat_cot_flow_handoff_review_20261022/test_remaining_flow_contracts.py -q --junitxml='
commands=[{'command':'.venv/bin/python audit/rat_cot_flow_handoff_review_20261022/run_checks.py','environment':{'QT_QPA_PLATFORM':'offscreen (set by runner)'},'sandbox_permissions':'require_escalated','network_or_model_calls':0,'exit_code':0,'stdout':'current_contracts.txt','junit_xml':'current_contracts.xml','result':cross['independent_runs']['current_contracts.xml']}]
for suffix,note in [('', 'Initial targeted probes; exact history marker assertion.'),('_v2','Relaxed prompt-format assertion and recorded kwargs; context case failed during callback serialization in the review instrument. Not used as product-failure evidence.'),('_v3','Final probes; callback serialization fixed; two assertion failures reproduce finite-calibration binding and missing context.')]:
 commands.append({'command':base+'audit/rat_cot_flow_handoff_review_20261022/remaining_flow'+suffix+'.xml','environment':{'QT_QPA_PLATFORM':'offscreen','PYTHONDONTWRITEBYTECODE':'1'},'sandbox_permissions':'require_escalated','network_or_model_calls':0,'exit_code':1,'stdout':'remaining_flow'+suffix+'.txt','junit_xml':'remaining_flow'+suffix+'.xml','result':cross['independent_runs']['remaining_flow'+suffix+'.xml'],'note':note})
commands.append({'command':'python audit/rat_cot_flow_handoff_review_20261022/check_submitted_evidence.py','exit_code':0,'scope':'Received XML/log metadata, 13 data hashes without printing contents, patch replay on copied source only.'})
write('commands.json',commands)
write('validation.json',{'verdict':'runtime_repair_partially_accepted_and_flow_implementation_handoff_ready','date_local':'2026-10-22','r3':'closed_within_reviewed_contracts','r5':'open_P1_finite_calibration_state_not_bound_to_authoritative_artifact','r10':'closed_within_crosschecked_metadata_and_lineage','r12':'resolved_with_historical_r4_XML_loss_recorded_not_full_original_integrity','context_transport':'confirmed_planned_integration_gap_not_implemented_by_preparation_handoff','flow_preparation':'specification_only_not_full_7_step_acceptance','decisions':{'turn4':'new_chat_turn_references_source_artifact_revision_then_commits_new_revision','target_revision':'source_revision_not_preassigned_output_revision','postdispatch_failure_cost':'retain_actual_dispatched_requests_and_partial_generated_tokens','public_verification_without_DSA_checker':'UNKNOWN'},'current_contracts':cross['independent_runs']['current_contracts.xml'],'final_targeted_probes':cross['independent_runs']['remaining_flow_v3.xml'],'probe_instrumentation_incident':'v2 callback JSON TypeError retained; final v3 supports the conclusion','independent_full_checkout_regression':False,'submitted_504_tests_are_not_504_distinct':cross['submitted_accounting'],'incoming_source_hashes_verified':61,'incoming_artifact_entries_verified':91,'review_start_source_entries_unchanged':len(start),'fresh_data_hashes_verified':13,'production_edits_by_this_review':0,'new_real_model_calls':0,'model_weights_loaded':False,'model_quality_evidence':'none_from_this_review','tokens':'synthetic authored generated-token counts; not full inference cost','timing':'pytest elapsed durations; not measured online model latency','stage_0_changed':False,'human_data_review_completed_by_this_review':False,'git_commits_branches_remote_mutations':0,'ledger_unchanged':True})
manifest={str(path.relative_to(HERE)):digest(path) for path in sorted(HERE.rglob('*')) if path.is_file() and path!=HERE/'artifact_manifest.json' and '__pycache__' not in path.parts and '.pytest_cache' not in path.parts and path.suffix!='.pyc'}
write('artifact_manifest.json',manifest)
assert not differences(load('artifact_manifest.json'),HERE)
print(json.dumps({'manifest_entries':len(manifest),'review_start_source_entries':len(start),'source_drift':source_drift,'incoming_drift':final['incoming_changes_since_review_start'],'historical_new_changes':{k:v['changes_since_review_start'] for k,v in prior.items()},'ledger_unchanged':True,'branch':branch}))
