import numpy as np

from entry_predictor import EntryChoice, EntryPredictor, collect_entry_training_data, simulate_ladder_outcome
from optimal_stopping import CalibrationData, OptimalStoppingPolicy, collect_calibration_data
from reasoning_env import ReasoningAction as A


def test_simulate_ladder_outcome_matches_manual_trace():
    # query 0: conf rung0=0.9 (>= tau giả định 0.5) -> dừng ở CoT ngay, chỉ tốn cost rung0
    conf = np.array([[0.9], [0.1], [0.1]])
    correct = np.array([[1.0], [0.0], [0.0]])
    cost = np.array([[0.3], [1.5], [5.0]])
    calib = CalibrationData(conf, correct, cost)
    policy = OptimalStoppingPolicy(lam=0.01)
    policy.tau = [0.5, 0.5]  # gán tay, không cần fit cho test đơn vị này
    acc, c = simulate_ladder_outcome(policy, calib, 0)
    assert acc == 1.0 and np.isclose(c, 0.3)


def test_simulate_ladder_outcome_escalates_when_conf_low():
    conf = np.array([[0.1], [0.9], [0.1]])  # rung0 thấp -> escalate; rung1 cao -> dừng ở SC
    correct = np.array([[0.0], [1.0], [0.0]])
    cost = np.array([[0.3], [1.5], [5.0]])
    calib = CalibrationData(conf, correct, cost)
    policy = OptimalStoppingPolicy(lam=0.01)
    policy.tau = [0.5, 0.5]
    acc, c = simulate_ladder_outcome(policy, calib, 0)
    assert acc == 1.0 and np.isclose(c, 0.3 + 1.5)  # cộng dồn cả 2 rung đã đi qua


class ClusteredMockLLM:
    """3 loại query phân biệt bằng prefix - PAL thắng ở pal_, REACT thắng ở react_, ladder thắng ở plain_."""

    TYPES = {"pal": 0, "react": 1, "plain": 2}
    LADDER_ACC = {A.COT: 0.85, A.SELF_CONSISTENCY: 0.9, A.TOT: 0.95}  # dùng chung cho mọi loại, cố tình cao để rung0 đủ ăn ở plain_
    COST = {A.COT: 300, A.SELF_CONSISTENCY: 1500, A.TOT: 5000, A.REACT: 600, A.PAL: 300}
    hidden_size = 6

    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)

    def _type(self, query):
        return self.TYPES[query.split("_")[0]]

    def embed(self, query):
        v = self.rng.normal(0, 0.1, self.hidden_size)
        v[self._type(query)] += 3.0  # tín hiệu tách cụm rõ, giống 1 embedding thật đã phân biệt được loại câu hỏi
        return v

    def run(self, strategy, query):
        t = self._type(query)
        if strategy == A.PAL:
            acc = 0.95 if t == 0 else 0.1
        elif strategy == A.REACT:
            acc = 0.9 if t == 1 else 0.15
        else:
            acc = self.LADDER_ACC[strategy] if t == 2 else 0.2  # ladder chỉ giỏi thật ở plain_
        ok = self.rng.random() < acc
        conf = float(np.clip(self.rng.normal(0.75 if ok else 0.3, 0.12), 0, 1))
        return ("OK" if ok else "wrong"), conf, self.COST[strategy]


def make_dataset(n_per_type=60):
    data = []
    for t in ("pal", "react", "plain"):
        data += [(f"{t}_{i}", "OK") for i in range(n_per_type)]
    return data


CHECK = lambda pred, gold: pred == gold


def test_constant_classifier_fallback_when_one_candidate_always_correct():
    backend = ClusteredMockLLM(seed=1)
    train = make_dataset(20)
    ladder_calib = collect_calibration_data(backend, train, CHECK)
    ladder_policy = OptimalStoppingPolicy(lam=0.02).fit(ladder_calib)
    # ép toàn bộ accuracy PAL = 1 để kích hoạt nhánh _ConstantClassifier, không nên raise lỗi
    data = collect_entry_training_data(backend, train, CHECK, ladder_policy, ladder_calib)
    data.accuracy[:, EntryChoice.PAL] = 1.0
    predictor = EntryPredictor(lam=0.02).fit(data)  # không được raise
    score = predictor.score(data.embed[0], data.complexity[0])
    x0 = predictor._features(data.embed[:1], data.complexity[:1])
    assert np.isclose(score[EntryChoice.PAL], 1.0 - 0.02 * predictor.cost[EntryChoice.PAL].predict(x0)[0])


def test_predictor_learns_correct_routing_per_cluster():
    backend = ClusteredMockLLM(seed=2)
    train = make_dataset(80)
    ladder_calib = collect_calibration_data(backend, train, CHECK)
    ladder_policy = OptimalStoppingPolicy(lam=0.02).fit(ladder_calib)
    data = collect_entry_training_data(backend, train, CHECK, ladder_policy, ladder_calib)
    predictor = EntryPredictor(lam=0.02).fit(data)

    expect = {"pal": EntryChoice.PAL, "react": EntryChoice.REACT, "plain": EntryChoice.LADDER}
    test_backend = ClusteredMockLLM(seed=99)  # embedding cluster giống hệt (seed chỉ ảnh hưởng noise nhỏ + run())
    correct_routes = 0
    n = 30
    for t, want in expect.items():
        for i in range(n):
            q = f"{t}_test{i}"
            got = predictor.choose(test_backend.embed(q), __import__("reasoning_env").complexity_features(q))
            correct_routes += int(got == want)
    assert correct_routes / (n * 3) > 0.9  # >90% route đúng loại, không phải đoán mò (1/3 ~ 33%)


def test_full_pipeline_end_to_end_via_run_episode():
    backend = ClusteredMockLLM(seed=3)
    train = make_dataset(80)
    test = [(f"{t}_holdout{i}", "OK") for t in ("pal", "react", "plain") for i in range(15)]
    ladder_calib = collect_calibration_data(backend, train, CHECK)
    ladder_policy = OptimalStoppingPolicy(lam=0.02).fit(ladder_calib)
    entry_data = collect_entry_training_data(backend, train, CHECK, ladder_policy, ladder_calib)
    entry_predictor = EntryPredictor(lam=0.02).fit(entry_data)

    full_policy = OptimalStoppingPolicy(lam=0.02, entry_predictor=entry_predictor)
    full_policy.tau = ladder_policy.tau  # dùng lại threshold ladder đã fit ở trên
    results = [full_policy.run_episode(backend, q, g, CHECK) for q, g in test]
    acc = np.mean([r["correct"] for r in results])
    assert acc > 0.7  # nếu route sai nhiều, acc sẽ rơi về ~0.15-0.3 (accuracy của lựa chọn sai loại)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
