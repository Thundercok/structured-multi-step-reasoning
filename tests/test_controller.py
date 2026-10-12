"""Learning/split integrity checks using explicitly synthetic outcomes."""
import copy

import pytest

from rat.engine.controller import AgentStoppingController, AgentStateTracker, ControllerIntervention, FEATURE_NAMES


def smoke_rows():
    rows = []
    for split, count in [('train', 20), ('calibration', 8), ('test', 6)]:
        for i in range(count):
            useful = i % 2 == 0
            features = [0.0] * len(FEATURE_NAMES)
            features[4] = float(not useful)
            features[10] = 1.0
            rows.append(dict(id=f'{split}-{i}', group_id=f'{split}-group-{i}', split=split,
                             features=features, reviewed=True, quality_gain=0.8 if useful else -0.5,
                             delta_tokens=100))
    return rows


def test_unfitted_controller_has_no_keyword_policy():
    controller = AgentStoppingController()
    state = AgentStateTracker(has_schedule=True)
    for goal in ['prepare materials', 'hello', 'tìm tài liệu']:
        assert controller.evaluate_step(state, None, {}, goal).intervention == ControllerIntervention.ALLOW
        assert controller.evaluate_step(state, 'get_schedule', {}, goal).intervention == ControllerIntervention.ALLOW


def test_actual_fit_and_calibration_without_test_label_access():
    rows = smoke_rows()
    controller = AgentStoppingController().fit(rows, evidence='synthetic_smoke')
    altered = copy.deepcopy(rows)
    for row in altered:
        if row['split'] == 'test':
            row['quality_gain'] = 'UNREADABLE GOLD'
            row['delta_tokens'] = None
    other = AgentStoppingController().fit(altered, evidence='synthetic_smoke')
    assert other.to_dict() == controller.to_dict()
    assert controller.predict(rows[0]['features']) > controller.threshold
    assert controller.predict(rows[1]['features']) <= controller.threshold


def test_groups_must_be_disjoint_and_labels_reviewed():
    rows = smoke_rows()
    rows[-1]['group_id'] = rows[0]['group_id']
    with pytest.raises(ValueError, match='crosses splits'):
        AgentStoppingController().fit(rows)
    rows = smoke_rows()
    rows[0]['reviewed'] = False
    with pytest.raises(ValueError, match='reviewed'):
        AgentStoppingController().fit(rows)


def test_synthetic_artifact_cannot_be_deployed():
    controller = AgentStoppingController().fit(smoke_rows(), evidence='synthetic_smoke')
    with pytest.raises(ValueError, match='Synthetic'):
        AgentStoppingController.from_dict(controller.to_dict())
    restored = AgentStoppingController.from_dict(controller.to_dict(), allow_synthetic=True)
    assert restored.predict(smoke_rows()[0]['features']) == controller.predict(smoke_rows()[0]['features'])


def test_legacy_automatic_utility_labels_are_not_training_outcomes():
    with pytest.raises(ValueError):
        AgentStoppingController().fit([{'utility_class': 'PRODUCTIVE', 'scenario_id': 'old'}])


def test_fit_bundle_and_replay_require_matching_development_data(tmp_path):
    from scripts.fit_agent_controller import fit_bundle
    from scripts.eval_controlled_agent import evaluate
    rows = smoke_rows()
    fit_bundle(rows, tmp_path / 'bundle', evidence='synthetic_smoke')
    controller = AgentStoppingController().fit(rows, evidence='synthetic_smoke')
    report = evaluate(controller, rows)
    assert report['scope'] == 'paired_one_step_replay'
    assert report['online_latency_measured'] is False
    changed = copy.deepcopy(rows)
    changed[0]['quality_gain'] = -0.8
    with pytest.raises(ValueError, match='do not match'):
        evaluate(controller, changed)
    with pytest.raises(ValueError, match='new directory'):
        fit_bundle(rows, tmp_path / 'bundle', evidence='synthetic_smoke')


def test_measured_fit_rejects_unpaired_provenance(tmp_path):
    from scripts.fit_agent_controller import fit_bundle
    with pytest.raises(ValueError, match='provenance'):
        fit_bundle(smoke_rows(), tmp_path / 'bundle')
    assert not (tmp_path / 'bundle').exists()


def test_measured_pairs_allow_negative_token_difference_and_require_full_branch_costs():
    from rat.engine.controller import validate_pair_cost
    pair = dict(stop_tokens=200, continue_tokens=150, delta_tokens=-50, pair_trace_sha256='a' * 64)
    validate_pair_cost(pair)
    pair['delta_tokens'] = 50
    with pytest.raises(ValueError, match='does not match'):
        validate_pair_cost(pair)
    pair = dict(delta_tokens=50)
    with pytest.raises(ValueError, match='both branch'):
        validate_pair_cost(pair)
