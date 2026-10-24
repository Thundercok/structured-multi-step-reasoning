"""Independent authored-fixture counterexamples; no candidate/model access."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments import gsm8k_collector as c
from experiments import gsm8k_routing_baseline as r


def main():
    helpers=runpy.run_path(str(ROOT/'tests/test_gsm8k_collector.py'))
    fixture=runpy.run_path(str(ROOT/'tests/test_gsm8k_routing_baseline.py'))
    dataset=helpers['make_test_dataset'](2)
    identity=helpers['make_test_identity'](dataset)
    settings={'temperature':0.0,'thinking':False}
    result={}
    with tempfile.TemporaryDirectory(prefix='gsm8k-independent-') as temp:
        base=Path(temp)
        invalid=[]
        for index,tokens in enumerate((-100,2048,True)):
            cp=c.GSM8KCollectorCheckpoint(base/f'invalid{index}',identity,dataset,settings)
            runner=c.MockStagedRunner({('item_train_0','DIRECT'):{'tokens':tokens}})
            try:
                state=c.run_staged_collection(cp,runner,dataset)
                rows=json.loads((cp.directory/'records.json').read_text())
                row=next(x for x in rows if x['id']=='item_train_0' and x['strategy']=='DIRECT')
                invalid.append({'provided_tokens':tokens,'accepted_complete':state['status']=='complete','stored_tokens':row['tokens']})
            finally: cp.close()
        assert all(row['accepted_complete'] for row in invalid)
        result['invalid_token_outcomes']=invalid

        path=base/'orphan'
        cp=c.GSM8KCollectorCheckpoint(path,identity,dataset,settings)
        class Kill(c.MockStagedRunner):
            def run_generation(self,*args,**kwargs):
                raise c.SimulatedProcessKill('hard-stop fixture')
        try: c.run_staged_collection(cp,Kill(),dataset)
        except c.SimulatedProcessKill: pass
        finally: cp.close()
        cp=c.GSM8KCollectorCheckpoint(path,identity,dataset,settings,resume=True)
        unknown=len(cp.unknown_conditions)
        try: c.run_staged_collection(cp,c.MockStagedRunner(),dataset)
        except c.QuarantineError: pass
        finally: cp.close()
        state=json.loads((path/'manifest.json').read_text())
        result['orphan_charge']={'unknown_conditions':unknown,'status':state['status'],'calls_started':state['calls_started'],
                                 'budget_charged_tokens':state['budget_charged_tokens'],'required_reservation':1024}
        assert unknown==1 and state['budget_charged_tokens']==0

        path=base/'after_outcome'
        cp=c.GSM8KCollectorCheckpoint(path,identity,dataset,settings)
        original=cp.append_event
        def stop_before_record(kind,*args,**kwargs):
            if kind=='record_assembled': raise c.SimulatedProcessKill('after generation outcome')
            return original(kind,*args,**kwargs)
        cp.append_event=stop_before_record
        try: c.run_staged_collection(cp,c.MockStagedRunner(),dataset)
        except c.SimulatedProcessKill: pass
        finally: cp.close()
        cp=c.GSM8KCollectorCheckpoint(path,identity,dataset,settings,resume=True)
        runner=c.MockStagedRunner()
        state=c.run_staged_collection(cp,runner,dataset)
        result['lost_assembly']={'unknown_conditions':len(cp.unknown_conditions),'resume_dispatches':runner.generation_dispatches,
                                 'completed_records':len(cp.records),'expected_records':6,'returned_status':state['status']}
        assert len(cp.records)==5 and not cp.unknown_conditions and state['status']=='running'
        cp.close()

        items,records=fixture['fixture_data']()
        pilot=fixture['save_run'](base/'pilot',items,records)
        seal=base/'seal'
        r.write_fitting_seal(pilot,seal)
        sealed=json.loads((seal/'manifest.json').read_text())
        original_summary=r.write_validation_evaluation(seal,base/'validation_original')
        rows=json.loads((pilot/'records.json').read_text())
        for row in rows:
            if row['split']!='calibration': continue
            row['correct']=not row['correct']
            row['answer']='7' if row['correct'] else '8'
            if row['strategy']=='PAL': row['trace']['tools'][0]['output']=row['answer']
            else: row['trace']['generations'][0]['output']='Answer: '+row['answer']
        (pilot/'records.json').write_text(json.dumps(rows)+'\n')
        manifest=json.loads((pilot/'manifest.json').read_text())
        manifest['artifact_sha256']['records.json']=r.sha256_file(pilot/'records.json')
        (pilot/'manifest.json').write_text(json.dumps(manifest)+'\n')
        actual_manifest_hash=r.sha256_file(pilot/'manifest.json')
        changed=r.write_validation_evaluation(seal,base/'validation_changed')
        result['sealed_input_swap']={'accepted_status':changed['status'],
                                    'input_manifest_changed':actual_manifest_hash!=sealed['input_manifest_sha256'],
                                    'output_still_claims_old_input_hash':changed['input_manifest_sha256']==sealed['input_manifest_sha256'],
                                    'current_input_manifest_sha256':actual_manifest_hash,
                                    'recorded_input_manifest_sha256':changed['input_manifest_sha256']}
        assert changed['status']=='complete' and result['sealed_input_swap']['input_manifest_changed']
    paths=['experiments/gsm8k_collector.py','experiments/gsm8k_routing_baseline.py','experiments/research_study.py','tests/test_gsm8k_collector.py']
    result.update(source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                  new_model_calls=0,candidate_content_read=False,stage0_changed=False)
    (Path(__file__).parent/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
