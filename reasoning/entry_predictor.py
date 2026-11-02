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
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import log_loss
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from reasoning.optimal_stopping import CalibrationData, OptimalStoppingPolicy
    from reasoning.reasoning_env import LLMBackend, ReasoningAction as A, complexity_features
except ImportError:
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


# Regularization grids. With d >> N the data is almost surely linearly separable, so the
# penalty strength is THE hyperparameter - it is chosen by CV, never left at sklearn defaults.
_C_GRID = np.logspace(-4, 1, 11)       # LogisticRegression: smaller C = stronger L2
_ALPHA_GRID = np.logspace(-1, 5, 13)   # Ridge: larger alpha = stronger L2
_FALLBACK_C = 0.01                     # used only when CV is impossible (too few samples/class)
_FALLBACK_ALPHA = 1e3


def _binary_log_loss(estimator, X, y):
    # A group-isolated validation fold may legitimately contain only one class.
    return -log_loss(y, estimator.predict_proba(X), labels=[0, 1])


class EntryPredictor:
    """Per-candidate accuracy (logistic) + cost (ridge) heads on [LLM embedding | complexity].

    Anti-overfitting design for N ~ 100-200, d ~ 4096:
      * embedding block and complexity block are standardized SEPARATELY (else 4096 dims drown 3);
      * optional PCA(whiten) on the embedding block (n_components=None disables it);
      * L2 strength tuned by inner CV; scaler/PCA are refit inside every fold (no leakage).
    """

    def __init__(self, lam: float = 0.05, n_components: int | None = 32, seed: int = 0, cv_folds: int = 5):
        self.lam = lam
        self.n_components = n_components
        self.seed = seed
        self.cv_folds = cv_folds
        self.perf: list = []
        self.cost: list = []

    def _features(self, embed: np.ndarray, complexity: np.ndarray) -> np.ndarray:
        return np.concatenate([embed, complexity], axis=-1)

    def _pipeline(self, d: int, c: int, n_comp: int | None, head) -> Pipeline:
        embed_steps = [("scale", StandardScaler())]
        if n_comp:
            embed_steps.append(("pca", PCA(n_components=n_comp, whiten=True, random_state=self.seed)))
        pre = ColumnTransformer([
            ("embed", Pipeline(embed_steps), list(range(d))),
            ("complexity", StandardScaler(), list(range(d, d + c))),
        ])
        return Pipeline([("pre", pre), ("head", head)])

    def _components(self, d, training_rows):
        # Centering leaves at most training_rows - 1 useful PCA directions.
        # A single-row fallback cannot support whitening; keep scaling only.
        if not self.n_components or training_rows < 2:
            return None
        return min(self.n_components, d, training_rows - 1)

    def _group_splits(self, X, y, groups):
        n_splits = min(self.cv_folds, len(np.unique(groups)))
        if n_splits < 2:
            return []
        return list(GroupKFold(n_splits=n_splits).split(X, y, groups))

    def _fit_classifier(self, X, y, d, c, groups=None):
        classes, counts = np.unique(y, return_counts=True)
        if len(classes) < 2:
            return _ConstantClassifier(y[0])
        n_splits = min(self.cv_folds, int(counts.min()))
        if groups is None:
            splits = list(StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.seed).split(X, y)) if n_splits >= 2 else []
        else:
            splits = self._group_splits(X, y, groups)
            # Never split a group just to make both classes available in a fold.
            if any(len(np.unique(y[train])) < 2 for train, _ in splits):
                splits = []
        if not splits:
            pipe = self._pipeline(d, c, self._components(d, len(y)), LogisticRegression(max_iter=2000))
            return pipe.set_params(head__C=_FALLBACK_C).fit(X, y)
        n_comp = self._components(d, min(len(train) for train, _ in splits))
        pipe = self._pipeline(d, c, n_comp, LogisticRegression(max_iter=2000))
        scoring = _binary_log_loss if groups is not None else "neg_log_loss"
        return GridSearchCV(pipe, {"head__C": _C_GRID}, cv=splits, scoring=scoring, error_score="raise").fit(X, y)

    def _fit_regressor(self, X, y, d, c, groups=None):
        n_splits = min(self.cv_folds, len(y))
        if groups is None:
            splits = list(KFold(n_splits=n_splits, shuffle=True, random_state=self.seed).split(X, y)) if n_splits >= 2 else []
        else:
            splits = self._group_splits(X, y, groups)
        if not splits:
            pipe = self._pipeline(d, c, self._components(d, len(y)), Ridge())
            return pipe.set_params(head__alpha=_FALLBACK_ALPHA).fit(X, y)
        n_comp = self._components(d, min(len(train) for train, _ in splits))
        pipe = self._pipeline(d, c, n_comp, Ridge())
        return GridSearchCV(pipe, {"head__alpha": _ALPHA_GRID}, cv=splits, scoring="neg_mean_squared_error", error_score="raise").fit(X, y)

    def fit(self, data: EntryTrainingData, *, groups=None) -> "EntryPredictor":
        N, d = data.embed.shape
        if N == 0:
            raise ValueError("EntryPredictor requires at least one training row")
        if groups is not None:
            groups = np.asarray(groups)
            if groups.shape != (N,) or not all(isinstance(group, (str, np.str_)) and group.strip() for group in groups):
                raise ValueError("groups must contain one nonempty string per training row")
        c = data.complexity.shape[1]
        X = self._features(data.embed, data.complexity)
        perf, cost = [], []  # built locally: a failed fit() leaves the previous state intact
        for k in range(len(EntryChoice)):
            y_acc = (data.accuracy[:, k] > 0.5).astype(int)
            perf.append(self._fit_classifier(X, y_acc, d, c, groups))
            cost.append(self._fit_regressor(X, data.cost[:, k], d, c, groups))
        self.perf, self.cost = perf, cost  # replaces, never appends -> re-fit is safe
        return self

    def score(self, embed: np.ndarray, complexity: np.ndarray) -> np.ndarray:
        x = self._features(embed[None], complexity[None])
        pred_acc = np.array([m.predict_proba(x)[0, 1] for m in self.perf])
        pred_cost = np.array([m.predict(x)[0] for m in self.cost])
        return pred_acc - self.lam * pred_cost

    def choose(self, embed: np.ndarray, complexity: np.ndarray) -> EntryChoice:
        return EntryChoice(int(np.argmax(self.score(embed, complexity))))
