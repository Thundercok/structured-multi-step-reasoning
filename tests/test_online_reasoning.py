"""Synthetic fitted-policy integration; not model or calibration evidence."""
import numpy as np
import pytest

from reasoning.entry_predictor import EntryChoice, EntryPredictor, EntryTrainingData
from reasoning.optimal_stopping import CalibrationData, IsotonicCalibrator, OptimalStoppingPolicy
from reasoning.reasoning_env import ReasoningAction as A
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import MetaReasonerEngine


class Backend:
    hidden_size = 2

    def __init__(self, confidence=.1):
        self.confidence = confidence
        self.calls = []

    def embed(self, query):
        return np.zeros(self.hidden_size)

    def run(self, strategy, query):
        self.calls.append((strategy, query))
        return f"observed-{strategy.name}", self.confidence, 10 + int(strategy)


def fitted(choice=EntryChoice.LADDER):
    accuracy = np.zeros((8, 3))
    accuracy[:, choice] = 1
    predictor = EntryPredictor(lam=.02).fit(EntryTrainingData(
        embed=np.zeros((8, 2)), complexity=np.zeros((8, 3)),
        accuracy=accuracy, cost=np.full((8, 3), .1),
    ))
    return OptimalStoppingPolicy(.02, entry_predictor=predictor).fit(CalibrationData(
        conf=np.array([[.2] * 8, [.6] * 8, [.9] * 8]),
        correct=np.array([[0] * 8, [0] * 8, [1] * 8]),
        cost=np.full((3, 8), .1),
    ))


@pytest.mark.parametrize('choice,confidence,path', [
    (EntryChoice.LADDER, .1, [A.COT, A.SELF_CONSISTENCY, A.TOT]),
    (EntryChoice.LADDER, .95, [A.COT]),
    (EntryChoice.REACT, .1, [A.REACT]),
    (EntryChoice.PAL, .1, [A.PAL]),
])
def test_rat_executes_fitted_route_and_stopping_without_gold_or_legacy_branches(choice, confidence, path):
    backend = Backend(confidence)
    policy = fitted(choice)
    engine = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, policy, policy_source='synthetic-unit-fixture',
    ))
    # A legacy intent branch would use canned tuition numbers for this query.
    query = 'Tính học phí 123'
    result = engine.solve(query)
    assert [action for action, _ in backend.calls] == path
    assert all(q == query for _, q in backend.calls)
    assert result.answer == f'observed-{path[-1].name}'
    assert result.strategy_path == [action.name for action in path]
    assert result.tokens == sum(10 + int(action) for action in path)
    assert result.escalated == (len(path) > 1)
    assert result.execution_mode == 'online_policy'
    assert result.policy_source == 'synthetic-unit-fixture'
    assert result.verification_status == 'unverified'
    assert result.confidence_kind == 'backend_raw'
    replay = policy.run_episode(Backend(confidence), query, result.answer, lambda a, b: a == b)
    assert replay['path'] == result.strategy_path
    assert replay['cost'] == pytest.approx(result.tokens / 1000)
    engine.solve(query)
    assert len(backend.calls) == 2 * len(path)  # no stale cached costs/path


def test_stopping_applies_fitted_confidence_calibration():
    policy = fitted()
    calibrator = IsotonicCalibrator().fit(np.array([.01, .05, .5, .9]), np.array([0, 1, 1, 1]))
    assert calibrator.is_fitted
    assert calibrator.predict(.1) == pytest.approx(calibrator.predict(np.array([.1]))[0])
    policy.calibrators = [calibrator] * 3
    backend = Backend(.1)
    result = OnlineReasoningController(backend, policy, policy_source='synthetic').solve('query')
    assert len(result.observations) == 1  # raw .1 escalates; calibrated 1 stops
    assert result.observations[0].confidence == .1


def test_unfitted_or_inconsistent_policy_cannot_start_backend():
    backend = Backend()
    with pytest.raises(ValueError, match='fitted entry predictor'):
        OnlineReasoningController(backend, OptimalStoppingPolicy(.02), policy_source='synthetic')
    policy = fitted()
    policy.entry_predictor.lam = .5
    with pytest.raises(ValueError, match='same lambda'):
        OnlineReasoningController(backend, policy, policy_source='synthetic')
    assert not backend.calls


@pytest.mark.parametrize('confidence', [float('nan'), 1.1, True])
def test_invalid_observation_fails_without_escalation_or_canned_answer(confidence):
    backend = Backend(confidence)
    engine = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, fitted(), policy_source='synthetic',
    ))
    with pytest.raises(ValueError, match='confidence'):
        engine.solve('học phí 12')
    assert len(backend.calls) == 1


def test_backend_failure_is_not_replaced_by_a_legacy_response(monkeypatch):
    backend = Backend()
    def fail(*args):
        raise RuntimeError('backend unavailable')
    monkeypatch.setattr(backend, 'run', fail)
    engine = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, fitted(), policy_source='synthetic',
    ))
    with pytest.raises(RuntimeError, match='backend unavailable'):
        engine.solve('học phí 12')


@pytest.mark.parametrize('tokens', [-1, True, 1.5])
def test_invalid_cost_does_not_become_a_reported_token_count(monkeypatch, tokens):
    backend = Backend()
    monkeypatch.setattr(backend, 'run', lambda *args: ('answer', .5, tokens))
    controller = OnlineReasoningController(backend, fitted(), policy_source='synthetic')
    with pytest.raises(ValueError, match='generated-token count'):
        controller.solve('query')


def test_invalid_embedding_prevents_strategy_calls(monkeypatch):
    backend = Backend()
    monkeypatch.setattr(backend, 'embed', lambda query: np.array([np.nan, 0]))
    controller = OnlineReasoningController(backend, fitted(), policy_source='synthetic')
    with pytest.raises(ValueError, match='embedding'):
        controller.solve('query')
    assert not backend.calls
