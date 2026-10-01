"""Entry-choice dual predictor kiểu RTR (Pan et al. 2025): dự đoán performance + cost cho từng
candidate rồi chọn score = acc - lam*cost cao nhất. Khác RTR ở 2 chỗ, có chủ đích:
  1. Feature = embedding từ chính LLM (đã quyết định trước đó), không phải sentence-transformer riêng.
  2. Chỉ 3 candidate cố định (LADDER/REACT/PAL) nên dùng embedding one-hot học được thay vì
     encode mô tả text qua 1 model phụ - RTR cần mô tả text vì họ route qua hàng chục model,
     ở đây không cần thêm 1 dependency chỉ để phân biệt 3 lựa chọn đã biết trước.
LADDER không phải 1 lần chạy tĩnh - nó tự escalate. Nên target train cho LADDER phải là outcome
THẬT của OptimalStoppingPolicy đã fit, replay lại trên đúng data đã log (không tốn thêm LLM call).
"""

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

from optimal_stopping import CalibrationData, OptimalStoppingPolicy
from reasoning_env import LLMBackend, ReasoningAction as A, complexity_features


class EntryChoice(IntEnum):
    LADDER = 0
    REACT = 1
    PAL = 2


@dataclass
class EntryTrainingData:
    embed: np.ndarray       # (N, hidden_size) - từ backend.embed(), cùng nguồn với ladder
    complexity: np.ndarray  # (N, 3)
    accuracy: np.ndarray    # (N, 3) - đúng/sai thật của mỗi candidate trên từng query
    cost: np.ndarray        # (N, 3) - nghìn token thật


def simulate_ladder_outcome(policy: OptimalStoppingPolicy, calib: CalibrationData, i: int) -> tuple[float, float]:
    """Replay quyết định của policy đã fit trên conf/correct/cost đã log sẵn của query i -
    không gọi LLM thêm lần nào."""
    total_cost = 0.0
    for rung in range(3):
        total_cost += calib.cost[rung, i]
        if rung == 2 or not policy.should_escalate(rung, calib.conf[rung, i]):
            return calib.correct[rung, i], total_cost
    raise AssertionError("unreachable")


def collect_entry_training_data(
    backend: LLMBackend, dataset, check, ladder_policy: OptimalStoppingPolicy, ladder_calib: CalibrationData
) -> EntryTrainingData:
    N = len(dataset)
    embed = np.zeros((N, backend.hidden_size), dtype=np.float32)
    complexity = np.zeros((N, 3), dtype=np.float32)
    accuracy, cost = np.zeros((N, 3)), np.zeros((N, 3))
    for i, (q, gold) in enumerate(dataset):
        embed[i], complexity[i] = backend.embed(q), complexity_features(q)
        accuracy[i, EntryChoice.LADDER], cost[i, EntryChoice.LADDER] = simulate_ladder_outcome(ladder_policy, ladder_calib, i)
        for choice, strat in ((EntryChoice.REACT, A.REACT), (EntryChoice.PAL, A.PAL)):
            ans, _, n_tok = backend.run(strat, q)
            accuracy[i, choice], cost[i, choice] = float(check(ans, gold)), n_tok / 1000.0
    return EntryTrainingData(embed, complexity, accuracy, cost)


class _ConstantClassifier:
    """LogisticRegression cần >=2 class - fallback này cho case 1 candidate luôn đúng/luôn sai trong tập train."""

    def __init__(self, value: float):
        self.value = float(value)

    def predict_proba(self, X):
        p = np.full((len(X), 2), [1 - self.value, self.value])
        return p


class EntryPredictor:
    def __init__(self, lam: float = 0.05):
        self.lam = lam
        self.perf: list = []
        self.cost: list = []

    def _features(self, embed: np.ndarray, complexity: np.ndarray) -> np.ndarray:
        return np.concatenate([embed, complexity], axis=-1)

    def fit(self, data: EntryTrainingData) -> "EntryPredictor":
        X = self._features(data.embed, data.complexity)
        for c in range(len(EntryChoice)):
            y_acc = data.accuracy[:, c]
            self.perf.append(_ConstantClassifier(y_acc[0]) if len(np.unique(y_acc)) < 2 else LogisticRegression(max_iter=2000).fit(X, y_acc))
            self.cost.append(Ridge(alpha=1.0).fit(X, data.cost[:, c]))
        return self

    def score(self, embed: np.ndarray, complexity: np.ndarray) -> np.ndarray:
        x = self._features(embed[None], complexity[None])
        pred_acc = np.array([m.predict_proba(x)[0, 1] for m in self.perf])
        pred_cost = np.array([m.predict(x)[0] for m in self.cost])
        return pred_acc - self.lam * pred_cost

    def choose(self, embed: np.ndarray, complexity: np.ndarray) -> EntryChoice:
        return EntryChoice(int(np.argmax(self.score(embed, complexity))))
