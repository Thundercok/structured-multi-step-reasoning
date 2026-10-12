import zlib

import numpy as np

from reasoning_env import A, LADDER, ReasoningEnv


class MockLLM:
    hidden_size = 16
    TOK = {A.COT: 300, A.SELF_CONSISTENCY: 1500, A.TOT: 5000, A.REACT: 800, A.PAL: 500}
    P = {A.COT: 0.55, A.SELF_CONSISTENCY: 0.7, A.TOT: 0.8, A.REACT: 0.6, A.PAL: 0.65}

    def __init__(self, gold, deterministic=False, seed=0):
        self.gold, self.det, self.rng = gold, deterministic, np.random.default_rng(seed)

    def embed(self, query):
        v = np.random.default_rng(zlib.crc32(query.encode())).normal(size=self.hidden_size)
        v[-1] *= 50.0  # outlier dim như hidden state LLM thật
        return v

    def run(self, strategy, query):
        if self.det:
            conf = {A.COT: 0.8, A.SELF_CONSISTENCY: 0.9}.get(strategy, 0.7)
            return self.gold[query], conf, self.TOK[strategy]
        ok = self.rng.random() < self.P[strategy]
        conf = float(np.clip(self.rng.normal(0.5 + 0.3 * ok, 0.15), 0, 1))
        return (self.gold[query] if ok else "wrong"), conf, self.TOK[strategy]


DATA = [(f"q{i}: what is {i}+{i}?", str(2 * i)) for i in range(50)]
GOLD = dict(DATA)


def make_env(deterministic=False, **kw):
    return ReasoningEnv(MockLLM(GOLD, deterministic), DATA, lambda pred, gold: pred == gold, **kw)


def test_random_policy_invariants():
    env = make_env()
    rng = np.random.default_rng(0)
    n_correct = 0
    for ep in range(300):
        obs, info = env.reset(seed=ep)
        for _ in range(env.max_steps):
            assert obs.shape == (env.state_dim,) and obs.dtype == np.float32
            assert env.observation_space.contains(obs)
            obs, r, term, trunc, info = env.step(rng.integers(len(A)))
            assert np.isfinite(r) and info["action_mask"].shape == (len(A),)
            if term or trunc:
                assert info["total_cost"] >= 0
                n_correct += info["is_correct"]
                break
        else:
            raise AssertionError("episode did not end within max_steps")
    assert 0 < n_correct < 300


def test_reset_index_is_deterministic():
    env = make_env()
    env.reset(options={"index": 7})
    assert env.query == DATA[7][0]


def test_masks_and_escalate_ladder():
    env = make_env(deterministic=True)
    _, info = env.reset(options={"index": 0})
    assert not info["action_mask"][A.STOP] and info["action_mask"][A.ESCALATE]
    for i in range(len(LADDER)):  # 3 lần ESCALATE liên tiếp = CoT -> SC -> ToT
        _, _, _, _, info = env.step(A.ESCALATE)
        assert env.used[i] == 1.0
        assert info["action_mask"][A.STOP]
    assert not info["action_mask"][A.ESCALATE]


def test_invalid_stop_is_penalized_noop():
    env = make_env(deterministic=True)
    env.reset(options={"index": 0})
    _, r, term, trunc, info = env.step(A.STOP)
    assert info["invalid"] and not term and not trunc and np.isclose(r, -env.invalid_penalty)


def test_reward_accounting_no_double_cost():
    lam, beta = 0.05, 0.2
    env = make_env(deterministic=True, lam=lam, beta=beta)
    env.reset(options={"index": 3})
    _, r1, *_ = env.step(A.COT)
    _, r2, *_ = env.step(A.SELF_CONSISTENCY)
    _, r3, term, _, info = env.step(A.STOP)
    assert np.isclose(r1, -lam * 0.3)
    assert np.isclose(r2, -lam * 1.5 + beta * (0.9 - 0.8))
    assert term and info["is_correct"] and np.isclose(r3, 1.0)
    assert np.isclose(r1 + r2 + r3, 1.0 - lam * 1.8 + beta * 0.1)


def test_truncation_grades_current_answer():
    env = make_env(deterministic=True, max_steps=2)
    env.reset(options={"index": 1})
    env.step(A.COT)
    _, r, term, trunc, info = env.step(A.PAL)
    assert trunc and not term and info["is_correct"] and r > 0


def test_truncation_without_answer_is_wrong():
    env = make_env(deterministic=True, max_steps=2)
    env.reset(options={"index": 1})
    env.step(A.STOP)
    _, r, term, trunc, info = env.step(A.STOP)
    assert trunc and not info["is_correct"] and np.isclose(r, -env.invalid_penalty - 1.0)


def test_expanded_complexity_features():
    from reasoning_env import complexity_features, expanded_complexity_features

    q1 = "What is 5 + 7?"
    f_v1 = complexity_features(q1, version=1)
    assert len(f_v1) == 3
    assert f_v1[2] == 1.0  # math keyword '+'

    q2 = "Who finished after Heidi, if Bob was in second place?"
    f_v2 = expanded_complexity_features(q2)
    assert len(f_v2) == 6
    assert f_v2[3] == 1.0  # ordering keyword 'after'
    assert f_v2[4] == 1.0  # conditional keyword 'if'
    assert f_v2[5] > 0.0   # nesting/punctuation


def test_env_with_expanded_features_and_initial_confidence_reward():
    lam, beta = 0.05, 0.2
    env = make_env(
        deterministic=True,
        lam=lam,
        beta=beta,
        complexity_version=2,
        reward_initial_confidence=True,
    )
    obs, info = env.reset(options={"index": 3})
    assert obs.shape == (env.state_dim,)
    assert env.state_dim == env.llm.hidden_size + 6 + 1 + len(env.supported) + 1

    # First step gets initial confidence reward beta * conf
    _, r1, *_ = env.step(A.COT)
    # COT conf is 0.8 in deterministic MockLLM
    expected_r1 = -lam * 0.3 + beta * 0.8
    assert np.isclose(r1, expected_r1)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)

