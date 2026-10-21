"""r4 counterexamples: configured native budgets, dispatch accounting, fitted artifact schema.
All Qwen logic runs with native imports removed and scripted token provider.
"""
import importlib.util,json,hashlib,sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r3_contract_helpers',ROOT/'audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);helper.HERE=HERE
from reasoning.bundle import BundleValidationError,validate_policy_bundle
from reasoning.reasoning_env import ReasoningAction as A


def native(sc_samples=5,tot_branches=3,cap_stream=False):
    backend,state,ctrl=helper.native_stream_controller('complete')
    backend.sc_samples=sc_samples;backend.tot_branches=tot_branches
    if cap_stream:
        def stream(*args,**kwargs):
            state['dispatched']+=1
            count=1 if state['dispatched']==1 else max(0,int(kwargs['max_tokens']))
            for i in range(1,count+1):
                state['generated_tokens']+=1
                yield SimpleNamespace(text='x',generation_tokens=i,token=0,logprobs=None,finish_reason=None)
        backend._chat.__globals__['stream_generate']=stream
    return backend,state,ctrl


def test_native_sc_configuration_controls_actual_sample_count():
    backend,state,_=native(sc_samples=2)
    backend.run(A.SELF_CONSISTENCY,'authored fixture')
    assert state['dispatched']==backend.sc_samples,{'actual_generations':state['dispatched'],'configured_samples':backend.sc_samples}


def test_native_tot_configuration_controls_actual_branch_count():
    backend,state,_=native(tot_branches=1)
    backend.run(A.TOT,'authored fixture')
    assert state['dispatched']==backend.tot_branches+1,{'actual_generations':state['dispatched'],'configured_branches':backend.tot_branches}


def test_native_request_budget_uses_actual_configured_strategy():
    _,state,ctrl=native(sc_samples=2)
    result=ctrl.solve('authored fixture',max_underlying_requests=3)
    evidence={'actual':state,'status':result.status,'ledger':result.cost_ledger.__dict__}
    (HERE/'configured_request_budget.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert state['dispatched']<=3,evidence


def test_native_token_cap_holds_with_nondefault_supported_configuration():
    _,state,ctrl=native(sc_samples=2,cap_stream=True)
    result=ctrl.solve('authored fixture',max_generated_tokens=5)
    evidence={'actual':state,'status':result.status,'ledger':result.cost_ledger.__dict__}
    (HERE/'configured_token_budget.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert state['generated_tokens']<=5,evidence


def fail_stream_case(message):
    backend,state,ctrl=native()
    def failing_stream(*args,**kwargs):
        state['dispatched']+=1
        for i in (1,2):
            state['generated_tokens']+=1
            yield SimpleNamespace(text='x',generation_tokens=i,token=0,logprobs=None,finish_reason=None)
        raise RuntimeError(message)
    backend._chat.__globals__['stream_generate']=failing_stream
    with pytest.raises(RuntimeError) as caught:ctrl.solve('authored fixture')
    return {'actual':state,'ledger':caught.value.cost_ledger.__dict__,'trace':backend.last_trace}


def test_failure_message_does_not_change_recorded_dispatch_count():
    ordinary=fail_stream_case('scripted transport fault')
    with_phrase=fail_stream_case('scripted transport fault after dispatch')
    evidence={'ordinary_message':ordinary,'message_with_phrase':with_phrase}
    (HERE/'error_message_dispatch_cases.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert ordinary['ledger']['underlying_requests_dispatched']==with_phrase['ledger']['underlying_requests_dispatched']==1,evidence


def test_native_predispatch_cancel_is_not_charged_as_dispatched_generation():
    backend,state,ctrl=native()
    checks=0
    def stop_at_native_guard():
        nonlocal checks
        checks+=1
        # Initial controller guard and rung guard pass; native _chat guard cancels.
        return checks>=3
    with pytest.raises(RuntimeError) as caught:
        ctrl.solve('authored fixture',is_cancelled=stop_at_native_guard)
    evidence={'actual':state,'polls':checks,'ledger':caught.value.cost_ledger.__dict__,'trace':backend.last_trace}
    (HERE/'predispatch_cancel_case.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert caught.value.cost_ledger.underlying_requests_dispatched==state['dispatched']==0,evidence


@pytest.mark.parametrize('variant',['malformed-json','missing-parameters','empty-cost-models','wrong-coefficient-shape','changed-performance-model'])
def test_approved_fitted_artifact_cannot_skip_parameter_validation(tmp_path,variant):
    bundle,policy,backend,artifact=helper.approved_fixture(tmp_path)
    data=json.loads(artifact.read_text())
    if variant=='malformed-json':raw='{not valid json'
    elif variant=='missing-parameters':raw='{}'
    elif variant=='empty-cost-models':
        data['entry_cost_models']=[];policy.entry_predictor.cost[0].coef_+=9;raw=json.dumps(data)
    elif variant=='wrong-coefficient-shape':
        data['entry_cost_models'][0]['coef']=[1,2];raw=json.dumps(data)
    else:
        data['entry_perf_models']=[{'constant':m.value} for m in policy.entry_predictor.perf]
        policy.entry_predictor.perf[0].value=0.0
        raw=json.dumps(data)
    artifact.write_text(raw)
    bundle=replace(bundle,artifact_hashes={str(artifact):hashlib.sha256(artifact.read_bytes()).hexdigest()})
    with pytest.raises(BundleValidationError):validate_policy_bundle(bundle,policy,backend)


def test_control_valid_approved_artifact_validates(tmp_path):
    bundle,policy,backend,_=helper.approved_fixture(tmp_path)
    assert validate_policy_bundle(bundle,policy,backend).is_valid


def test_control_default_native_configuration_matches_count():
    backend,state,_=native()
    backend.run(A.SELF_CONSISTENCY,'authored fixture')
    assert state['dispatched']==backend.sc_samples==5


def test_control_failed_generation_records_partial_tokens():
    case=fail_stream_case('scripted transport fault')
    assert case['ledger']['generated_tokens']==case['actual']['generated_tokens']==2
    assert case['ledger']['underlying_requests_dispatched']==1
