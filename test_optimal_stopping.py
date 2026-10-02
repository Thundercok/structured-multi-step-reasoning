import numpy as np

from optimal_stopping import CalibrationData, OptimalStoppingPolicy, collect_calibration_data, fit_threshold
from reasoning_env import LADDER, ReasoningAction as A


class MockLadderLLM:
    """CoT rẻ/kém, SC vừa, ToT đắt/giỏi. Confidence tương quan thật với đúng/sai (không phải random)."""

    COST = {A.COT: 300, A.SELF_CONSISTENCY: 1500, A.TOT: 5000, A.PAL: 400}
    ACC = {A.COT: 0.55, A.SELF_CONSISTENCY: 0.75, A.TOT: 0.85}
    supported = frozenset({A.COT, A.SELF_CONSISTENCY, A.TOT, A.PAL})

    def __init__(self, gold, seed=0):
        self.gold, self.rng = gold, np.random.default_rng(seed)

    def run(self, strategy, query):
        if strategy == A.PAL:
            return "wrong", 0.5, self.COST[A.PAL]
        ok = self.rng.random() < self.ACC[strategy]
        conf = float(np.clip(self.rng.normal(0.75 if ok else 0.35, 0.15), 0.0, 1.0))
        return (self.gold[query] if ok else "wrong"), conf, self.COST[strategy]


DATA = [(f"q{i}", str(i)) for i in range(600)]
GOLD = dict(DATA)
CHECK = lambda pred, gold: pred == gold


def test_fit_threshold_picks_global_optimum_on_toy_example():
    conf = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    value_stop = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    value_escalate = np.array([1.0, 1.0, -1.0, -1.0, -1.0])  # đáng escalate chỉ khi conf<0.5
    tau = fit_threshold(value_stop, value_escalate, conf)
    assert 0.3 < tau <= 0.5


def test_threshold_cannot_split_equal_confidences():
    confidence = np.array([0.2, 0.2, 0.8])
    stop = np.zeros(3)
    escalate = np.array([3.0, -4.0, -1.0])
    threshold = fit_threshold(stop, escalate, confidence)
    realized_value = np.where(confidence < threshold, escalate, stop).sum()
    assert realized_value == 0.0


def test_tied_threshold_matches_exhaustive_feasible_cuts():
    generator = np.random.default_rng(123)
    for _ in range(50):
        confidence = generator.choice([0.0, 0.5, 1.0], size=20)
        stop = generator.normal(size=20)
        escalate = generator.normal(size=20)
        threshold = fit_threshold(stop, escalate, confidence)
        candidates = [*np.unique(confidence), np.nextafter(confidence.max(), np.inf)]
        expected = max(np.where(confidence < candidate, escalate, stop).sum() for candidate in candidates)
        actual = np.where(confidence < threshold, escalate, stop).sum()
        assert np.isclose(actual, expected)


def test_fit_threshold_handles_escalate_none_and_all():
    conf = np.array([0.2, 0.4, 0.6, 0.8])
    assert fit_threshold(np.zeros(4), -np.ones(4), conf) < conf.min()  # escalate luôn tệ hơn -> tau thấp nhất
    assert fit_threshold(-np.ones(4), np.zeros(4), conf) > conf.max()  # escalate luôn tốt hơn -> tau cao nhất


def test_calibration_collects_all_three_rungs():
    backend = MockLadderLLM(GOLD, seed=1)
    calib = collect_calibration_data(backend, DATA[:50], CHECK)
    assert calib.conf.shape == (3, 50) and calib.correct.shape == (3, 50)
    # accuracy thu được nên xấp xỉ ACC thật (seed cố định, n=50 đủ để không lệch quá xa)
    for k, strat in enumerate(LADDER):
        assert abs(calib.correct[k].mean() - MockLadderLLM.ACC[strat]) < 0.2


def test_higher_lambda_escalates_less_monotonic():
    backend = MockLadderLLM(GOLD, seed=2)
    calib = collect_calibration_data(backend, DATA, CHECK)
    taus = []
    for lam in [0.0001, 0.001, 0.01, 0.1, 1.0]:
        policy = OptimalStoppingPolicy(lam).fit(calib)
        taus.append(policy.tau)
    tau0 = [t[0] for t in taus]
    tau1 = [t[1] for t in taus]
    # lambda tăng (cost đắt hơn) -> ngưỡng escalate phải giảm hoặc bằng (escalate ít lại), ở cả 2 rung
    assert all(a >= b - 1e-9 for a, b in zip(tau0, tau0[1:]))
    assert all(a >= b - 1e-9 for a, b in zip(tau1, tau1[1:]))
    # 2 đầu mút phải thực sự khác nhau, không phải fit bị flat vô nghĩa
    assert tau0[0] > tau0[-1] + 0.05 or tau1[0] > tau1[-1] + 0.05


def test_backward_induction_uses_downstream_value_not_just_next_rung():
    """Rung 0 phải nhìn thấy giá trị CỦA policy rung1-trở-đi, không phải so trực tiếp Y0 vs Y1.
    Dựng calib giả nơi rung1 tự nó tệ nhưng rung1+escalate-tiếp lên rung2 rất tốt -> rung0 vẫn nên escalate."""
    N = 200
    conf = np.zeros((3, N))
    correct = np.zeros((3, N))
    cost = np.zeros((3, N))
    conf[0] = np.linspace(0.05, 0.95, N)
    correct[0] = 0  # CoT luôn sai trong toy example này
    correct[1] = 0  # SC (nếu dừng ở đây) cũng luôn sai
    conf[1] = 0.9   # nhưng SC luôn tự tin (để lộ điểm yếu nếu code chỉ nhìn Y1 mà quên V1 thật)
    correct[2] = 1  # ToT luôn đúng, cực rẻ trong toy này để chắc chắn escalate có lợi
    cost[:] = 0.001
    calib = CalibrationData(conf, correct, cost)
    policy = OptimalStoppingPolicy(lam=0.01).fit(calib)
    # nếu code SAI (so Y0 vs Y1 trực tiếp, bỏ qua V1 thật): sẽ thấy rung1 "toàn sai" nên không bao giờ đáng escalate
    # nếu code ĐÚNG: rung0 phải luôn escalate vì downstream (qua rung2) luôn đúng và gần như free
    assert policy.tau[0] > conf[0].max(), "rung 0 phải escalate ở MỌI mức confidence trong toy example này"


def test_policy_beats_cheapest_and_costs_less_than_priciest():
    backend = MockLadderLLM(GOLD, seed=3)
    train, test = DATA[:400], DATA[400:]
    calib = collect_calibration_data(backend, train, CHECK)
    policy = OptimalStoppingPolicy(lam=0.02).fit(calib)
    results = [policy.run_episode(backend, q, g, CHECK) for q, g in test]
    acc = np.mean([r["correct"] for r in results])
    cost = np.mean([r["cost"] for r in results])
    assert MockLadderLLM.ACC[A.COT] - 0.1 < acc  # không tệ hơn CoT đơn thuần
    assert acc > MockLadderLLM.ACC[A.COT]  # phải cải thiện so với chỉ dùng CoT
    assert cost < MockLadderLLM.COST[A.TOT] / 1000 * 0.9  # rẻ hơn hẳn luôn-ToT
    escalated_to_tot = np.mean([r["path"][-1] == "TOT" for r in results])
    assert 0 < escalated_to_tot < 1  # phải thật sự dùng ladder có chọn lọc, không phải luôn 1 rung


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
