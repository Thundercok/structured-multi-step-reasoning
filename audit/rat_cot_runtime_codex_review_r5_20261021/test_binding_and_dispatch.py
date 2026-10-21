"""Ordinary unsupported artifact forms, pre-dispatch text invariance, ReAct quotas.

No MLX imports or model construction. Real Qwen strategy/stream source runs
against a scripted token provider; all fitted fixtures are authored synthetic.
"""
import hashlib, importlib.util, json, sys
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from reasoning.bundle import BundleValidationError, create_synthetic_specimen_bundle, validate_policy_bundle
from reasoning.entry_predictor import EntryChoice
from reasoning.runtime import OnlineReasoningController

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r5_r3_helpers', ROOT / 'audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.HERE = HERE
def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, allow_nan=True) + '\n')

def prompt_failure(message):
    backend, state, controller = helper.native_stream_controller('complete')
    def fail_prompt(*args, **kwargs):
        raise RuntimeError(message)
    backend.tokenizer.apply_chat_template = fail_prompt
    with pytest.raises(RuntimeError) as caught:
        controller.solve('authored synthetic fixture')
    return {'actual': state, 'ledger': asdict(caught.value.cost_ledger), 'trace': backend.last_trace}

def test_predispatch_prompt_failure_count_is_invariant_to_message():
    plain = prompt_failure('scripted prompt failure')
    phrase = prompt_failure('scripted prompt failure after dispatch')
    save('prompt_failure_message_cases.json', {'plain': plain, 'with_phrase': phrase})
    assert plain['ledger']['underlying_requests_dispatched'] == phrase['ledger']['underlying_requests_dispatched'] == 0

@pytest.mark.parametrize('budget', ['requests', 'tokens'])
def test_declared_react_turn_limit_cannot_bypass_hard_budget(budget):
    backend, state, _ = helper.native_stream_controller('complete')
    bundle, policy = create_synthetic_specimen_bundle()
    # Supported metadata accepted by bundle validation and consumed by estimator.
    bundle = replace(bundle, strategy_settings={**bundle.strategy_settings, 'react_max_turns': 1})
    for index, model in enumerate(policy.entry_predictor.perf):
        model.value = float(index == EntryChoice.REACT)
    def stream(*args, **kwargs):
        state['dispatched'] += 1
        count = kwargs['max_tokens'] if budget == 'tokens' else 1
        for index in range(1, count + 1):
            state['generated_tokens'] += 1
            text = 'Thought: Calculate the fixture.\nAction: calculate[1+1]' if index == 1 else ' '
            yield SimpleNamespace(text=text, generation_tokens=index, token=0, logprobs=None, finish_reason=None)
    backend._chat.__globals__['stream_generate'] = stream
    try:
        controller = OnlineReasoningController(backend, policy, bundle=bundle, allow_synthetic_bundle=True)
        result = controller.solve('authored arithmetic fixture', **({'max_underlying_requests': 1} if budget == 'requests' else {'max_generated_tokens': 3}))
    except (BundleValidationError, NotImplementedError, ValueError) as error:
        # Rejecting an unsupported configuration before dispatch is also safe.
        save(f'react_{budget}_budget_case.json', {'safe_rejection': str(error), 'actual': state})
        assert state['dispatched'] == 0
        return
    save(f'react_{budget}_budget_case.json', {'settings': bundle.strategy_settings, 'actual': state, 'status': result.status, 'ledger': asdict(result.cost_ledger)})
    assert state['dispatched'] <= 1 if budget == 'requests' else state['generated_tokens'] <= 3

@pytest.mark.parametrize('variant', ['missing-performance', 'missing-cost-intercept', 'multiple-untyped-json', 'non-json-only-artifact', 'nonfinite-threshold', 'learned-performance-intercept'])
def test_approved_bundle_requires_complete_binding(tmp_path, variant):
    bundle, policy, backend, artifact = helper.approved_fixture(tmp_path)
    data = json.loads(artifact.read_text())
    before = policy.entry_predictor.score(np.ones(2), np.ones(3)).tolist()
    artifacts = {str(artifact): None}
    if variant == 'missing-performance':
        policy.entry_predictor.perf[0].value = 0.0
    elif variant == 'missing-cost-intercept':
        for model in data['entry_cost_models']:
            del model['intercept']
        policy.entry_predictor.cost[0].intercept_ += 9
    elif variant == 'multiple-untyped-json':
        artifacts = {}
        for name in ('a.json', 'b.json'):
            other = tmp_path / name
            other.write_text('{}')
            artifacts[str(other)] = None
        policy.entry_predictor.cost[0].coef_ += 9
    elif variant == 'non-json-only-artifact':
        other = tmp_path / 'weights.txt'
        other.write_text('{}')
        artifacts = {str(other): None}
        policy.entry_predictor.cost[0].coef_ += 9
    elif variant == 'nonfinite-threshold':
        data['tau'] = [float('nan')] * len(policy.tau)
    else:
        classifier = LogisticRegression().fit(np.zeros((4, 5)), np.array([0, 1, 0, 1]))
        policy.entry_predictor.perf[0] = classifier
        data['entry_perf_models'] = [
            {'coef': classifier.coef_.tolist(), 'intercept': classifier.intercept_.tolist()},
            *[{'constant': model.value} for model in policy.entry_predictor.perf[1:]],
        ]
        before = policy.entry_predictor.score(np.ones(2), np.ones(3)).tolist()
        classifier.intercept_ += 10
    artifact.write_text(json.dumps(data, allow_nan=True))
    artifacts = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in artifacts}
    bundle = replace(bundle, artifact_hashes=artifacts)
    try:
        report = validate_policy_bundle(bundle, policy, backend)
    except BundleValidationError as error:
        outcome = {'accepted': False, 'error': str(error)}
    else:
        outcome = {'accepted': True, 'report': asdict(report)}
    save(f'approved_binding_{variant}.json', {
        'outcome': outcome,
        'artifacts': {Path(name).name: {'sha256': digest, 'content': Path(name).read_text()} for name, digest in artifacts.items()},
        'predictor_scores_before': before,
        'predictor_scores_after': policy.entry_predictor.score(np.ones(2), np.ones(3)).tolist(),
        'live_cost_intercept': float(policy.entry_predictor.cost[0].intercept_),
    })
    assert not outcome['accepted'], outcome

def test_control_complete_matching_artifact_validates(tmp_path):
    bundle, policy, backend, artifact = helper.approved_fixture(tmp_path)
    data = json.loads(artifact.read_text())
    data['entry_perf_models'] = [{'constant': model.value} for model in policy.entry_predictor.perf]
    artifact.write_text(json.dumps(data))
    bundle = replace(bundle, artifact_hashes={str(artifact): hashlib.sha256(artifact.read_bytes()).hexdigest()})
    assert validate_policy_bundle(bundle, policy, backend).is_valid

def test_control_plain_prompt_failure_has_no_dispatch():
    case = prompt_failure('scripted prompt failure')
    assert case['actual']['dispatched'] == case['ledger']['underlying_requests_dispatched'] == 0

def test_control_declared_react_default_estimate_prevents_too_small_budget():
    backend, state, _ = helper.native_stream_controller('complete')
    bundle, policy = create_synthetic_specimen_bundle()
    for index, model in enumerate(policy.entry_predictor.perf):
        model.value = float(index == EntryChoice.REACT)
    controller = OnlineReasoningController(backend, policy, bundle=bundle, allow_synthetic_bundle=True)
    result = controller.solve('fixture', max_underlying_requests=1)
    assert result.status == 'budget_exceeded' and state['dispatched'] == 0
