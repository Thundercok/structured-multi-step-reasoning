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
    if conf.ndim != 1 or not len(conf):
        raise ValueError("Threshold fitting requires a nonempty confidence vector")
    if value_stop.shape != conf.shape or value_escalate.shape != conf.shape:
        raise ValueError("Threshold inputs must have matching shapes")
    if not all(np.isfinite(values).all() for values in (conf, value_stop, value_escalate)):
        raise ValueError("Threshold inputs must be finite")
    order = np.argsort(conf)
    sorted_conf = conf[order]
    sorted_stop = value_stop[order]
    sorted_escalate = value_escalate[order]
    # escalate đúng i điểm conf nhỏ nhất, stop phần còn lại: total(i) = total(i-1) + (ve[i-1]-vs[i-1])
    # => total(i) = total(0) + cumsum(gain)[:i], total(0) = sum(vs) (escalate 0 điểm)
    gain = sorted_escalate - sorted_stop
    totals = sorted_stop.sum() + np.concatenate([[0.0], np.cumsum(gain)])
    boundaries = np.concatenate(([0], np.flatnonzero(np.diff(sorted_conf) > 0) + 1, [len(conf)]))
    best_boundary = int(boundaries[np.argmax(totals[boundaries])])
    if best_boundary == 0:
        return float(np.nextafter(sorted_conf[0], -np.inf))
    if best_boundary == len(conf):
        return float(np.nextafter(sorted_conf[-1], np.inf))
    return float(sorted_conf[best_boundary])


def brier_score(conf: np.ndarray, correct: np.ndarray) -> float:
    """Mean squared error between confidence probabilities and binary correctness outcomes."""
    c = np.asarray(conf, dtype=np.float64).ravel()
    y = np.asarray(correct, dtype=np.float64).ravel()
    if len(c) == 0:
        return 0.0
    return float(np.mean((c - y) ** 2))


def expected_calibration_error(conf: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (ECE) with equal-width bins on [0, 1]."""
    c = np.asarray(conf, dtype=np.float64).ravel()
    y = np.asarray(correct, dtype=np.float64).ravel()
    if len(c) == 0:
        return 0.0
    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n_total = len(c)
    for i in range(n_bins):
        b_lo, b_hi = bin_boundaries[i], bin_boundaries[i + 1]
        mask = (c >= b_lo) & (c <= b_hi if i == n_bins - 1 else c < b_hi)
        n_in_bin = int(np.sum(mask))
        if n_in_bin > 0:
            bin_conf = float(np.mean(c[mask]))
            bin_acc = float(np.mean(y[mask]))
            ece += (n_in_bin / n_total) * abs(bin_acc - bin_conf)
    return float(ece)


class PlattCalibrator:
    """Logistic regression (Platt scaling) mapping confidence in [0, 1] to calibrated posterior probability."""

    def __init__(self):
        self.a: float = 1.0
        self.b: float = 0.0
        self.is_fitted: bool = False

    def fit(self, conf: np.ndarray, correct: np.ndarray) -> "PlattCalibrator":
        c = np.asarray(conf, dtype=np.float64).ravel()
        y = np.asarray(correct, dtype=np.float64).ravel()
        if len(np.unique(y)) < 2 or len(c) < 4:
            self.is_fitted = False
            return self
        try:
            from sklearn.linear_model import LogisticRegression

            clf = LogisticRegression(C=1.0, solver="lbfgs")
            clf.fit(c.reshape(-1, 1), y.astype(int))
            self.a = float(clf.coef_[0, 0])
            self.b = float(clf.intercept_[0])
            self.is_fitted = True
        except Exception:
            self.is_fitted = False
        return self

    def predict(self, conf: np.ndarray | float) -> np.ndarray | float:
        if not self.is_fitted:
            return conf
        c = np.asarray(conf, dtype=np.float64)
        z = np.clip(self.a * c + self.b, -30.0, 30.0)
        prob = np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))
        if np.isscalar(conf):
            return float(prob)
        return prob


class IsotonicCalibrator:
    """Monotone non-decreasing isotonic regression mapping confidence to calibrated probability."""

    def __init__(self):
        self._reg = None
        self.is_fitted: bool = False

    def fit(self, conf: np.ndarray, correct: np.ndarray) -> "IsotonicCalibrator":
        c = np.asarray(conf, dtype=np.float64).ravel()
        y = np.asarray(correct, dtype=np.float64).ravel()
        if len(np.unique(y)) < 2 or len(c) < 4:
            self.is_fitted = False
            return self
        try:
            from sklearn.isotonic import IsotonicRegression

            self._reg = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            self._reg.fit(c, y)
            self.is_fitted = True
        except Exception:
            self.is_fitted = False
        return self

    def predict(self, conf: np.ndarray | float) -> np.ndarray | float:
        if not self.is_fitted or self._reg is None:
            return conf
        c = np.asarray(conf, dtype=np.float64)
        pred = self._reg.predict(c)
        if np.isscalar(conf):
            return float(pred)
        return pred


def bootstrap_thresholds(
    calib: CalibrationData,
    lam: float,
    n_bootstraps: int = 200,
    seed: int = 42,
    alpha: float = 0.05,
    recalibrate: str | None = None,
) -> dict:
    """Bootstrap confidence intervals for optimal stopping thresholds tau_0 and tau_1."""
    N = calib.conf.shape[1]
    if N < 2:
        base_policy = OptimalStoppingPolicy(lam, recalibrate=recalibrate).fit(calib)
        return {
            "point_estimate": base_policy.tau,
            "mean": base_policy.tau,
            "std": [0.0, 0.0],
            "ci": [(base_policy.tau[0], base_policy.tau[0]), (base_policy.tau[1], base_policy.tau[1])],
            "n_bootstraps": 0,
        }
    rng = np.random.default_rng(seed)
    base_policy = OptimalStoppingPolicy(lam, recalibrate=recalibrate).fit(calib)
    point_tau = list(base_policy.tau)

    boot_taus = np.zeros((n_bootstraps, 2))
    for b in range(n_bootstraps):
        idx = rng.integers(0, N, size=N)
        sub_calib = CalibrationData(
            conf=calib.conf[:, idx],
            correct=calib.correct[:, idx],
            cost=calib.cost[:, idx],
            queries=[calib.queries[i] for i in idx] if calib.queries else [],
        )
        sub_policy = OptimalStoppingPolicy(lam, recalibrate=recalibrate).fit(sub_calib)
        boot_taus[b] = sub_policy.tau

    mean_tau = boot_taus.mean(axis=0).tolist()
    std_tau = boot_taus.std(axis=0).tolist()
    q_lo = float(alpha / 2.0)
    q_hi = float(1.0 - alpha / 2.0)
    ci0 = (float(np.quantile(boot_taus[:, 0], q_lo)), float(np.quantile(boot_taus[:, 0], q_hi)))
    ci1 = (float(np.quantile(boot_taus[:, 1], q_lo)), float(np.quantile(boot_taus[:, 1], q_hi)))

    return {
        "point_estimate": point_tau,
        "mean": mean_tau,
        "std": std_tau,
        "ci": [ci0, ci1],
        "n_bootstraps": n_bootstraps,
    }


class OptimalStoppingPolicy:
    """tau[0] cho rung CoT, tau[1] cho rung SC. Escalate khi conf_rung < tau[rung].
    entry_predictor (optional): xem entry_predictor.py - nếu có sẽ thay heuristic entry_action() thô.
    recalibrate (optional): 'platt' hoặc 'isotonic' để hiệu chuẩn confidence trước khi fit ngưỡng."""

    def __init__(self, lam: float, entry_predictor=None, recalibrate: str | None = None):
        self.lam = lam
        self.entry_predictor = entry_predictor
        self.recalibrate = recalibrate
        self.tau: list[float] = []
        self.mean_cost: list[float] = []
        self.calibrators: list[PlattCalibrator | IsotonicCalibrator] = []
        self.tau_ci: dict | None = None

    def fit(self, calib: CalibrationData, n_bootstraps: int = 0, bootstrap_seed: int = 42) -> "OptimalStoppingPolicy":
        conf, Y, cost = calib.conf, calib.correct, calib.cost
        self.mean_cost = [float(cost[k].mean()) for k in range(3)]

        self.calibrators = []
        used_conf = conf.copy()
        if self.recalibrate in ("platt", "isotonic"):
            for k in range(3):
                cal = PlattCalibrator() if self.recalibrate == "platt" else IsotonicCalibrator()
                cal.fit(conf[k], Y[k])
                self.calibrators.append(cal)
                used_conf[k] = cal.predict(conf[k])

        V_next = Y[2].copy()  # V_2 = Y_2, chưa có gì để escalate tiếp
        self.tau = [0.0, 0.0]
        for k in (1, 0):  # lùi từ rung 1 (SC) về rung 0 (CoT)
            value_escalate = V_next - self.lam * self.mean_cost[k + 1]
            tau_k = fit_threshold(value_stop=Y[k], value_escalate=value_escalate, conf=used_conf[k])
            self.tau[k] = tau_k
            escalate = used_conf[k] < tau_k
            V_next = np.where(escalate, value_escalate, Y[k])  # trở thành V_k, dùng cho vòng lặp kế (nếu k=1 -> dùng để fit k=0)

        if n_bootstraps > 0:
            self.tau_ci = bootstrap_thresholds(
                calib, self.lam, n_bootstraps=n_bootstraps, seed=bootstrap_seed, recalibrate=self.recalibrate
            )
        return self

    def transform_conf(self, rung: int, conf: float) -> float:
        """Transforms raw confidence through the fitted calibrator if active."""
        if self.calibrators and rung < len(self.calibrators):
            return float(self.calibrators[rung].predict(conf))
        return float(conf)

    def should_escalate(self, rung: int, conf: float) -> bool:
        c = self.transform_conf(rung, conf)
        return c < self.tau[rung]

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
