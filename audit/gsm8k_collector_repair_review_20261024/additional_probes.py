"""Additional identity, evidence and accounting probes on authored fixtures."""
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
    helper=runpy.run_path(str(ROOT/'tests/test_gsm8k_collector.py'))
    ds=helper['make_test_dataset'](2)
    identity=helper['make_test_identity'](ds,evidence='synthetic_staged_pilot_collection')
    settings={'temperature':0.0,'thinking':False}
    output={}
    with tempfile.TemporaryDirectory(prefix='gsm8k-repair-review-') as temp:
        base=Path(temp)
        cp=c.GSM8KCollectorCheckpoint(base/'dispatch',identity,ds,settings)
        runner=c.MockStagedRunner({('item_train_0','DIRECT'):{'tokens':1500}})
        state=c.run_staged_collection(cp,runner,ds,token_budget=2048,master_seed=999)
        records=json.loads((cp.directory/'records.json').read_text())
        over=next(row for row in records if row['id']=='item_train_0' and row['strategy']=='DIRECT')
        output['dispatch_identity_mismatch']={'status':state['status'],'identity_cap':identity['max_tokens'],
            'identity_seed':identity['seed'],'actual_record_cap':over['token_budget'],'actual_record_seed':over['seed'],
            'record_tokens':over['tokens'],'dispatches':runner.generation_dispatches}
        assert state['status']=='complete' and over['tokens']==1500 and over['token_budget']==2048
        cp.close()

        path=base/'bank'
        cp=c.GSM8KCollectorCheckpoint(path,identity,ds,settings)
        c.run_staged_collection(cp,c.MockStagedRunner(),ds)
        cp.close()
        seal=base/'seal'
        r.write_fitting_seal(path,seal)
        r.write_validation_evaluation(seal,base/'val')
        summary=json.loads((base/'val'/'summary.json').read_text())
        actual=json.loads((path/'summary.json').read_text())
        output['collection_cost_underreport']={'reported_full_collection':summary['full_collection'],
            'actual_generation_calls':actual['calls_completed'],'actual_generated_tokens':actual['measured_generated_tokens']}
        assert summary['full_collection']['generation_calls']==3 and actual['calls_completed']==6

        # A tiny synthetic bank is relabeled as measured with no model metadata.
        # No actual model executes; this is an adversarial evidence-label test.
        manifest=json.loads((path/'manifest.json').read_text())
        manifest['identity']['evidence']='measured_development_pilot'
        manifest['identity']['source_hashes']={'authored_unverified_source':'not-a-sha256'}
        (path/'manifest.json').write_text(json.dumps(manifest)+'\n')
        measured_seal=r.write_fitting_seal(path,base/'measured_seal')
        measured_val=r.write_validation_evaluation(base/'measured_seal',base/'measured_val')
        output['measured_gate_bypass']={'authored_items':len(ds['items']),'model_provenance_present':'model_provenance' in manifest['identity'],
            'source_hashes':manifest['identity']['source_hashes'],'seal_evidence':measured_seal['evidence'],
            'validation_status':measured_val['status'],'validation_evidence':measured_val['evidence']}
        assert measured_val['status']=='complete' and measured_val['evidence']=='measured_development_saved_output_analysis'
    paths=['experiments/gsm8k_collector.py','experiments/gsm8k_routing_baseline.py','experiments/research_study.py']
    output.update(source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                  new_model_calls=0,candidate_content_read=False,stage0_changed=False)
    (Path(__file__).parent/'additional_results.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__': main()
