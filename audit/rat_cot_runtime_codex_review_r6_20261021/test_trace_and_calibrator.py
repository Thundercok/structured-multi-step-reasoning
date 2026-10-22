"""Ordinary native error boundaries and complete approved-policy state checks.

Qwen strategy and stream source is unchanged; MLX imports/model loading are
excluded by the r3 AST helper. Every stream and policy input is authored synthetic.
"""
import hashlib, importlib.util, json, sys
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
import pytest
from reasoning.bundle import BundleValidationError, validate_policy_bundle
from reasoning.optimal_stopping import PlattCalibrator

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r6_r3_helpers', ROOT/'audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.HERE = HERE
def save(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, allow_nan=True)+'\n')

def interrupted_native_stage(stage):
    backend, actual, controller = helper.native_stream_controller('complete')
    backend.sc_samples = 2
    if stage == 'between-samples':
        calls = 0
        def format_prompt(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:  # COT completes, SC sample 1 completes, sample 2 never starts.
                raise RuntimeError('scripted prompt preprocessing failure')
            return 'fixture prompt'
        backend.tokenizer.apply_chat_template = format_prompt
    else:
        def status_failure(*args, **kwargs):
            raise RuntimeError('scripted strategy result formatting failure')
        # COT parses inline; SC calls this only after both samples completed.
        backend._record_status = status_failure
    with pytest.raises(RuntimeError) as caught:
        controller.solve('authored synthetic fixture')
    return {'stage': stage, 'actual': actual, 'ledger': asdict(caught.value.cost_ledger), 'trace': backend.last_trace}

@pytest.mark.parametrize('stage', ['between-samples', 'after-samples'])
def test_no_new_dispatch_is_invented_for_native_non_generation_error(stage):
    case = interrupted_native_stage(stage)
    save(f'native_stage_error_{stage}.json', case)
    assert case['ledger']['underlying_requests_dispatched'] == case['actual']['dispatched'], case
    assert case['ledger']['underlying_requests_failed'] == 0, case

def approved(tmp_path):
    bundle, policy, backend, artifact = helper.approved_fixture(tmp_path)
    data = json.loads(artifact.read_text())
    data['entry_perf_models'] = [{'constant': model.value} for model in policy.entry_predictor.perf]
    artifact.write_text(json.dumps(data))
    bundle = replace(bundle, artifact_hashes={str(artifact): hashlib.sha256(artifact.read_bytes()).hexdigest()})
    return bundle, policy, backend, artifact

@pytest.mark.parametrize('variant', ['live-nonfinite-constant', 'undeclared-active-calibrator'])
def test_approved_full_artifact_rejects_unbound_live_state(tmp_path, variant):
    bundle, policy, backend, artifact = approved(tmp_path)
    before_scores = policy.entry_predictor.score(np.ones(2), np.ones(3)).tolist()
    before_stop = policy.should_escalate(0, 0.0)
    if variant == 'live-nonfinite-constant':
        policy.entry_predictor.perf[0].value = float('nan')
    else:
        calibrator = PlattCalibrator().fit(np.array([0.0, 0.2, 0.8, 1.0]), np.array([0, 0, 1, 1]))
        calibrator.a = 0.0
        calibrator.b = 20.0
        policy.calibrators = [calibrator]
    try:
        report = validate_policy_bundle(bundle, policy, backend)
    except BundleValidationError as error:
        result = {'accepted': False, 'error': str(error)}
    else:
        result = {'accepted': True, 'report': asdict(report)}
    save(f'approved_state_{variant}.json', {
        'result': result,
        'artifact': artifact.read_text(), 'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'declared_artifact_sha256': bundle.artifact_hashes[str(artifact)],
        'calibrator_type': bundle.calibrator_type, 'calibrator_semantics': bundle.calibrator_semantics,
        'live_calibrators': [vars(c) for c in policy.calibrators],
        'scores_before': before_scores,
        'scores_after': policy.entry_predictor.score(np.ones(2), np.ones(3)).tolist(),
        'should_escalate_at_zero_before': before_stop, 'should_escalate_at_zero_after': policy.should_escalate(0, 0.0),
    })
    assert not result['accepted'], result

def test_control_matching_complete_artifact_and_live_state(tmp_path):
    bundle, policy, backend, _ = approved(tmp_path)
    assert validate_policy_bundle(bundle, policy, backend).is_valid

def test_control_native_normal_completion_has_no_phantom_requests():
    _, actual, controller = helper.native_stream_controller('complete')
    result = controller.solve('fixture')
    assert result.cost_ledger.underlying_requests_dispatched == actual['dispatched']
    assert result.cost_ledger.underlying_requests_failed == 0

def test_control_native_plain_predispatch_failure_costs_zero():
    backend, actual, controller = helper.native_stream_controller('complete')
    def fail_prompt(*args, **kwargs):
        raise RuntimeError('scripted prompt preprocessing failure')
    backend.tokenizer.apply_chat_template = fail_prompt
    with pytest.raises(RuntimeError) as caught:
        controller.solve('fixture')
    assert caught.value.cost_ledger.underlying_requests_dispatched == actual['dispatched'] == 0
