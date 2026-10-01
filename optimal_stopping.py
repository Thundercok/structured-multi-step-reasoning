"""Optimal Stopping cho ladder CoT->SC->ToT, thay cho DDQN.
Không cần rollout online: fit threshold 1 lần trên tập calibration đã chạy offline.
"""

from dataclasses import dataclass, field

import numpy as np

from reasoning_env import LADDER, LLMBackend, ReasoningAction as A, complexity_features


@dataclass
class CalibrationData:
    conf: np.ndarray   # (3, N) confidence mỗi rung, mỗi query
    correct: np.ndarray  # (3, N) 0/1
    cost: np.ndarray   # (3, N) token cost thật của mỗi lần chạy (dùng để đánh giá cuối, không dùng để fit ngưỡng)
    queries: list[str] = field(default_factory=list)


def collect_calibration_data(backend: LLMBackend, dataset, check) -> CalibrationData:
    """Chạy cả 3 rung trên MỌI query 1 lần - không cần policy nào để thu thập, không có exploration."""
    N = len(dataset)
    conf, correct, cost = np.zeros((3, N)), np.zeros((3, N)), np.zeros((3, N))
    for i, (q, gold) in enumerate(dataset):
        for k, strat in enumerate(LADDER):
            ans, c, n_tok = backend.run(strat, q)
            conf[k, i], correct[k, i], cost[k, i] = c, float(check(ans, gold)), n_tok / 1000.0
    return CalibrationData(conf, correct, cost, [q for q, _ in dataset])


def fit_threshold(value_stop: np.ndarray, value_escalate: np.ndarray, conf: np.ndarray) -> float:
    """Ngưỡng tau tối đa hoá sum(value_escalate nếu conf<tau else value_stop).
    Quét mọi điểm cắt có thể giữa các giá trị conf đã sort - O(n log n), tối ưu toàn cục trên tập này."""
    order = np.argsort(conf)
    c, vs, ve = conf[order], value_stop[order], value_escalate[order]
    # escalate đúng i điểm conf nhỏ nhất, stop phần còn lại: total(i) = total(i-1) + (ve[i-1]-vs[i-1])
    # => total(i) = total(0) + cumsum(gain)[:i], total(0) = sum(vs) (escalate 0 điểm)
    gain = ve - vs
    totals = vs.sum() + np.concatenate([[0.0], np.cumsum(gain)])
    best_i = int(np.argmax(totals))
    if best_i == 0:
        return float(c[0]) - 1e-6  # escalate 0 điểm
    if best_i == len(c):
        return float(c[-1]) + 1e-6  # escalate hết
    return float((c[best_i - 1] + c[best_i]) / 2)


class OptimalStoppingPolicy:
    """tau[0] cho rung CoT, tau[1] cho rung SC. Escalate khi conf_rung < tau[rung].
    entry_predictor (optional): xem entry_predictor.py - nếu có sẽ thay heuristic entry_action() thô."""

    def __init__(self, lam: float, entry_predictor=None):
        self.lam = lam
        self.entry_predictor = entry_predictor
        self.tau: list[float] = []
        self.mean_cost: list[float] = []

    def fit(self, calib: CalibrationData) -> "OptimalStoppingPolicy":
        conf, Y, cost = calib.conf, calib.correct, calib.cost
        self.mean_cost = [float(cost[k].mean()) for k in range(3)]
        V_next = Y[2].copy()  # V_2 = Y_2, chưa có gì để escalate tiếp
        self.tau = [0.0, 0.0]
        for k in (1, 0):  # lùi từ rung 1 (SC) về rung 0 (CoT)
            value_escalate = V_next - self.lam * self.mean_cost[k + 1]
            tau_k = fit_threshold(value_stop=Y[k], value_escalate=value_escalate, conf=conf[k])
            self.tau[k] = tau_k
            escalate = conf[k] < tau_k
            V_next = np.where(escalate, value_escalate, Y[k])  # trở thành V_k, dùng cho vòng lặp kế (nếu k=1 -> dùng để fit k=0)
        return self

    def should_escalate(self, rung: int, conf: float) -> bool:
        return conf < self.tau[rung]

    def entry_action(self, query: str, embed: np.ndarray | None = None):
        """Dùng entry_predictor nếu đã fit (xem entry_predictor.py); nếu chưa, fallback về
        heuristic thô (math keyword -> PAL, còn lại vào ladder) - KHÔNG phải phần optimal-stopping."""
        feats = complexity_features(query)
        if self.entry_predictor is not None:
            from entry_predictor import EntryChoice

            choice = self.entry_predictor.choose(embed, feats)
            return {EntryChoice.LADDER: A.COT, EntryChoice.REACT: A.REACT, EntryChoice.PAL: A.PAL}[choice]
        return A.PAL if feats[2] > 0.5 else A.COT  # feats[2] = có math keyword

    def run_episode(self, backend: LLMBackend, query: str, gold: str, check) -> dict:
        embed = backend.embed(query) if self.entry_predictor is not None else None
        entry = self.entry_action(query, embed)
        if entry in (A.PAL, A.REACT):
            ans, conf, n_tok = backend.run(entry, query)
            return {"answer": ans, "correct": check(ans, gold), "cost": n_tok / 1000.0, "path": [entry.name]}
        total_cost, path = 0.0, []
        for rung, strat in enumerate(LADDER):
            ans, conf, n_tok = backend.run(strat, query)
            total_cost += n_tok / 1000.0
            path.append(strat.name)
            if rung == len(LADDER) - 1 or not self.should_escalate(rung, conf):
                return {"answer": ans, "correct": check(ans, gold), "cost": total_cost, "path": path}
        raise AssertionError("unreachable")  # vòng for luôn return ở rung cuối
