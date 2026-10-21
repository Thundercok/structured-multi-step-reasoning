"""General counterexamples for repair R1-R9. Doubles only; no model loading.

Approved metadata below is test data, never an approval of a production policy.
"""
import ast
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
import numpy as np
import pytest
from PyQt6.QtCore import QCoreApplication
from reasoning.bundle import BundleValidationError,create_synthetic_specimen_bundle,validate_policy_bundle
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.ui.reasoning_worker import OnlineReasoningWorker

ROOT=Path(__file__).resolve().parents[2]

class LegacyBackend:
    hidden_size=2
    model_id='fixture-repository-A'
    model_snapshot='fixture-revision-A'
    prompt_profile='legacy'
    def __init__(self,callback=None):
        self.calls=[];self.actual_tokens=0;self.callback=callback
        self.last_trace={'generations':[]}
    def embed(self,query):return np.zeros(2,dtype=np.float32)
    def run(self,strategy,query):
        self.calls.append((strategy.name,query))
        if self.callback:self.callback()
        self.actual_tokens+=40
        self.last_trace={'generations':[{'tokens':40}]}
        return 'generic fixture answer',0.99,40


def make(backend=None):
    bundle,policy=create_synthetic_specimen_bundle()
    backend=backend or LegacyBackend()
    return bundle,policy,backend,OnlineReasoningController(backend,policy,bundle=bundle,allow_synthetic_bundle=True)


def nominal_approved(bundle):
    # Fixture flags only, with values that do not contain the old test's blacklist words.
    return replace(bundle,review_status='approved',is_production_approved=True,
                   review_scope='independent-review-contract-fixture',
                   model_id=LegacyBackend.model_id,model_snapshot=LegacyBackend.model_snapshot,
                   prompt_profile=LegacyBackend.prompt_profile)


def run_worker(worker):
    app=QCoreApplication.instance() or QCoreApplication([])
    results=[];statuses=[]
    worker.response_ready.connect(results.append)
    worker.status_changed.connect(statuses.append)
    worker.start();assert worker.wait(5000);app.processEvents()
    assert len(results)==1
    return results[0],statuses


def test_token_ledger_preserves_tokens_actually_generated():
    _,_,backend,controller=make()
    result=controller.solve('offline synthetic query',max_generated_tokens=1)
    assert result.cost_ledger.generated_tokens==backend.actual_tokens, {'actually_generated':backend.actual_tokens,'reported':result.cost_ledger.generated_tokens,'status':result.status}


def test_unsupported_hard_cap_rejected_before_generation():
    _,_,backend,controller=make()
    with pytest.raises((TypeError,ValueError,NotImplementedError)):
        controller.solve('offline synthetic query',max_generated_tokens=1)
    assert not backend.calls


class PerGenerationCapBackend(LegacyBackend):
    sc_samples=5
    def run(self,strategy,query,*,max_tokens=None,should_cancel=None,deadline_monotonic=None):
        self.calls.append((strategy.name,query))
        per_generation=2 if strategy.name=='COT' else min(40,max_tokens if max_tokens is not None else 40)
        count=1 if strategy.name=='COT' else 5
        raw_tokens=per_generation*count
        self.actual_tokens+=raw_tokens
        self.last_trace={'generations':[{'tokens':per_generation} for _ in range(count)]}
        return 'fixture result',0.1,raw_tokens


def test_remaining_cap_not_multiplied_across_sc_generations():
    _,_,backend,controller=make(PerGenerationCapBackend())
    result=controller.solve('offline synthetic query',max_generated_tokens=6)
    assert backend.actual_tokens<=6, {'actually_generated':backend.actual_tokens,'reported':result.generated_tokens,'ledger':result.cost_ledger}


class QwenSchemaFailureBackend(LegacyBackend):
    """Qwen _chat records only completed generations, using tokens and no status."""
    def run(self,strategy,query):
        self.calls.append((strategy.name,query))
        if strategy.name=='COT':
            self.last_trace={'generations':[{'tokens':20}]}
            return 'cot result',0.1,20
        self.last_trace={'generations':[{'tokens':20},{'tokens':20}]}
        raise RuntimeError('third SC generation failed after dispatch')


def test_failure_accounting_accepts_actual_qwen_trace_schema():
    _,_,_,controller=make(QwenSchemaFailureBackend())
    with pytest.raises(RuntimeError) as caught:
        controller.solve('offline synthetic query')
    ledger=caught.value.cost_ledger
    assert (ledger.underlying_requests_dispatched,ledger.underlying_requests_succeeded,ledger.underlying_requests_failed,ledger.generated_tokens)==(4,3,1,60),ledger


def test_invalid_observation_preserves_dispatched_request_ledger():
    backend=LegacyBackend()
    def invalid(strategy,query):
        backend.calls.append((strategy.name,query));backend.actual_tokens+=40
        backend.last_trace={'generations':[{'tokens':40}]}
        return 'fixture output',float('nan'),40
    backend.run=invalid
    _,_,_,controller=make(backend)
    with pytest.raises(ValueError) as caught:controller.solve('offline synthetic query')
    ledger=getattr(caught.value,'cost_ledger',None)
    assert ledger is not None, 'Observation validation discarded an already-dispatched request'
    assert ledger.generated_tokens==40


class CooperativeStopBackend(LegacyBackend):
    def __init__(self,event):super().__init__();self.event=event;self.worker=None
    def run(self,strategy,query,*,should_cancel=None,deadline_monotonic=None):
        self.calls.append((strategy.name,query))
        if self.event=='cancel':
            self.worker.requestInterruption()
            self.last_trace={'generations':[{'status':'cancelled','completion_tokens':7}]}
            assert should_cancel is not None and should_cancel()
            raise RuntimeError('cooperative cancellation during decode')
        time.sleep(0.03)
        self.last_trace={'generations':[{'status':'timeout','completion_tokens':7}]}
        assert deadline_monotonic is not None and time.monotonic()>=deadline_monotonic
        raise TimeoutError('cooperative deadline during decode')


@pytest.mark.parametrize('event,expected',[('cancel','cancelled'),('deadline','timeout')])
def test_worker_classifies_cooperative_stop_exception(event,expected):
    backend=CooperativeStopBackend(event)
    bundle,policy,_,_=make(backend)
    engine=build_composed_meta_reasoner(bundle,backend,policy,allow_synthetic=True)
    worker=OnlineReasoningWorker(engine,'offline synthetic query',timeout_s=0.02 if event=='deadline' else None)
    backend.worker=worker
    result,statuses=run_worker(worker)
    assert result.status==expected, {'status':result.status,'signals':statuses,'ledger':result.cost_ledger}
    assert result.cost_ledger['generated_tokens']==7


def test_qwen_strategy_entrypoint_exposes_claimed_execution_controls():
    # Inspect the actual native class without importing mlx or loading model weights.
    tree=ast.parse((ROOT/'qwen_mlx_backend.py').read_text())
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='QwenMLXBackend')
    run=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='run')
    names={x.arg for x in run.args.args+run.args.kwonlyargs}
    assert run.args.kwarg is not None or {'should_cancel','deadline_monotonic','max_tokens'}<=names, {'actual_run_parameters':sorted(names)}


@pytest.mark.parametrize('field,value',[
    ('model_id','fixture-repository-B'),
    ('model_snapshot','fixture-revision-B'),
    ('prompt_profile','english-math-v1'),
    ('source_hashes',{'reasoning/runtime.py':'0'*64}),
    ('artifact_hashes',{'fitted-policy.json':'f'*64}),
    ('strategy_settings',{'sc_samples':99,'tot_branches':99}),
    ('predictor_kind','DifferentPredictor.v2'),
    ('budget_token_semantics','full_inference_cost'),
])
def test_approved_metadata_mismatch_is_not_just_a_literal_blacklist(field,value):
    bundle,policy,backend,_=make()
    approved=nominal_approved(bundle)
    with pytest.raises(BundleValidationError):
        validate_policy_bundle(replace(approved,**{field:value}),policy,backend)


def test_existing_document_is_used_or_explicitly_rejected(tmp_path):
    document=tmp_path/'fixture.txt';document.write_text('Unique document fact: violet_marker_814.')
    bundle,policy,backend,_=make()
    engine=build_composed_meta_reasoner(bundle,backend,policy,allow_synthetic=True)
    result,_=run_worker(OnlineReasoningWorker(engine,'What is the unique marker?',document_path=str(document)))
    assert result.status=='unresolved' or any('violet_marker_814' in query for _,query in backend.calls), {'status':result.status,'answer':result.answer,'queries_received_by_backend':backend.calls}


def test_same_size_and_mtime_document_mutation_is_still_detected(tmp_path):
    document=tmp_path/'fixture.txt';document.write_text('version AAA')
    st=document.stat()
    def mutate():
        document.write_text('version BBB')
        os.utime(document,ns=(st.st_atime_ns,st.st_mtime_ns))
    backend=LegacyBackend(mutate)
    bundle,policy,_,_=make(backend)
    engine=build_composed_meta_reasoner(bundle,backend,policy,allow_synthetic=True)
    result,_=run_worker(OnlineReasoningWorker(engine,'question about document',document_path=str(document)))
    assert result.status=='unresolved', {'status':result.status,'document_after':document.read_text()}


spec=importlib.util.spec_from_file_location('submitted_power',ROOT/'scripts/calculate_power_sensitivity.py')
power=importlib.util.module_from_spec(spec);spec.loader.exec_module(power)

@pytest.mark.parametrize('delta,key',[(0.10,'sample_size_needed_for_delta_0.10_at_80pct_power'),(0.05,'sample_size_needed_for_delta_0.05_at_80pct_power')])
def test_claimed_power_sample_size_reaches_its_own_target(delta,key):
    summary=json.loads((ROOT/'audit/rat_cot_runtime_acceptance_20261020/power_sensitivity.json').read_text())['target_pool_n70_summary']
    n=summary[key]
    observed=power.calculate_mcnemar_power(n,delta,p_disc_ratio=summary['assumed_p_discordant'])
    assert observed>=0.80, {'claimed_required_n':n,'delta':delta,'power_under_submitted_function':observed}


def test_control_matching_fixture_and_no_cap():
    bundle,policy,backend,controller=make()
    assert validate_policy_bundle(nominal_approved(bundle),policy,backend).is_valid
    result=controller.solve('offline synthetic query')
    assert result.generated_tokens==40 and result.status=='completed'


def test_control_zero_quota_and_terminal_stop_fixes():
    _,_,backend,controller=make()
    assert controller.solve('offline synthetic query',max_underlying_requests=0).status=='budget_exceeded'
    assert not backend.calls
    flag=False
    def cancel():
        nonlocal flag
        flag=True
    backend.callback=cancel
    result=controller.solve('offline synthetic query',is_cancelled=lambda:flag)
    assert result.status=='cancelled'
