import re
from enum import IntEnum
from typing import Callable, Protocol, Sequence

import gymnasium as gym
import numpy as np


class ReasoningAction(IntEnum):
    COT = 0
    SELF_CONSISTENCY = 1
    TOT = 2
    REACT = 3
    PAL = 4
    ESCALATE = 5
    STOP = 6
    DIRECT = 7


A = ReasoningAction
STRATEGIES = (A.COT, A.SELF_CONSISTENCY, A.TOT, A.REACT, A.PAL)
LADDER = (A.COT, A.SELF_CONSISTENCY, A.TOT)  # chi phí tăng dần; ESCALATE đi theo chuỗi này
N_COMPLEXITY = 3


class LLMBackend(Protocol):
    hidden_size: int

    def embed(self, query: str) -> np.ndarray:
        """Mean-pooled hidden state của query, shape (hidden_size,)."""

    def run(self, strategy: ReasoningAction, query: str) -> tuple[str, float, int]:
        """(answer, confidence in [0,1], tổng token tiêu thụ gồm mọi sample/nhánh)."""


def complexity_features(query: str, version: int = 1) -> np.ndarray:
    """Đặc trưng độ phức tạp của câu hỏi.
    version=1: 3 đặc trưng nguyên bản [độ dài, số lượng số, từ khóa toán].
    version=2: 6 đặc trưng mở rộng (bổ sung từ khóa thứ tự, điều kiện, độ lồng câu).
    """
    n_words = len(query.split())
    n_nums = len(re.findall(r"\d+(?:\.\d+)?", query))
    q_lower = query.lower()
    math_kw = re.search(r"[+*/=^%]|\s-\s|\b(?:sum|total|each|per|ratio|percent|times|average|calculate|evaluate|compute)\b", q_lower)
    base = [
        min(np.log1p(n_words) / 6.0, 1.0),
        min(n_nums / 10.0, 1.0),
        float(math_kw is not None),
    ]
    if version == 1:
        return np.array(base, dtype=np.float32)

    order_kw = re.search(r"\b(?:first|last|before|after|ahead|behind|rank|position|place|order|ranking)\b", q_lower)
    cond_kw = re.search(r"\b(?:if|unless|given that|assuming|suppose|condition|whenever|whether)\b", q_lower)
    n_punct = len(re.findall(r"[,;:\(\)\[\]]", query))
    nesting = min(n_punct / 8.0, 1.0)
    return np.array(
        base + [float(order_kw is not None), float(cond_kw is not None), float(nesting)],
        dtype=np.float32,
    )


def expanded_complexity_features(query: str) -> np.ndarray:
    """Phiên bản 6 chiều của complexity_features."""
    return complexity_features(query, version=2)


class ReasoningEnv(gym.Env):
    """1 episode = 1 query. Mỗi step chạy 1 strategy, hoặc STOP để chấm đáp án hiện tại.

    State = [embedding (L2-norm) | complexity | confidence gần nhất | đã dùng strategy nào (5) | t/max_steps].
    Hai phần cuối là bắt buộc: thiếu chúng thì cùng 1 confidence sau CoT hay sau ToT là hai tình huống khác nhau,
    và max_steps làm bài toán mất tính Markov.

    ESCALATE = chạy nấc kế tiếp chưa dùng trên LADDER. Action không hợp lệ (STOP khi chưa có đáp án,
    ESCALATE khi hết ladder) = no-op bị phạt, vẫn tốn 1 step; mask có sẵn trong info["action_mask"].
    Hết max_steps mà chưa STOP -> truncated, đáp án hiện tại vẫn bị chấm.
    Strategy nằm ngoài `llm.supported` (nếu backend khai báo) bị mask và coi là không hợp lệ,
    nên thêm ToT/ReAct/PAL vào backend sau này không cần đụng tới env.

    Reward mỗi step = -lam * (nghìn token) + beta * (confidence mới - cũ); kết thúc cộng thêm +1 / -1.
    Cost chỉ bị trừ 1 lần, ngay lúc phát sinh.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        llm: LLMBackend,
        dataset: Sequence[tuple[str, str]],
        check: Callable[[str, str], bool],
        lam: float = 0.05,
        beta: float = 0.2,
        max_steps: int = 4,
        invalid_penalty: float = 0.1,
        complexity_version: int = 1,
        reward_initial_confidence: bool = False,
    ):
        super().__init__()
        self.llm, self.dataset, self.check = llm, dataset, check
        self.supported = frozenset(getattr(llm, "supported", STRATEGIES))
        self.lam, self.beta, self.max_steps, self.invalid_penalty = lam, beta, max_steps, invalid_penalty
        self.complexity_version = complexity_version
        self.reward_initial_confidence = reward_initial_confidence
        n_comp = 6 if complexity_version == 2 else N_COMPLEXITY
        self.state_dim = llm.hidden_size + n_comp + 1 + len(STRATEGIES) + 1
        self.action_space = gym.spaces.Discrete(len(A))
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (self.state_dim,), np.float32)
        self._emb_cache: dict[str, np.ndarray] = {}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        idx = (options or {}).get("index")
        if idx is None:
            idx = int(self.np_random.integers(len(self.dataset)))
        self.query, self.gold = self.dataset[idx]
        self.answer, self.conf, self.t, self.cost = None, 0.0, 0, 0.0
        self.used = np.zeros(len(STRATEGIES), dtype=np.float32)
        self._rung = 0  # nấc ladder kế tiếp mà ESCALATE sẽ chạy
        return self._obs(), {"action_mask": self._mask()}

    def step(self, action):
        a = A(int(action))
        self.t += 1
        reward, terminated, info = 0.0, False, {}
        rung = self._next_rung()
        if a in STRATEGIES:
            strat = a if a in self.supported else None
        elif a == A.ESCALATE and rung is not None:
            strat = LADDER[rung]
        else:
            strat = None

        if a == A.STOP and self.answer is not None:
            terminated = True
        elif strat is None:
            reward, info["invalid"] = -self.invalid_penalty, True
        else:
            prev_conf, had_answer = self.conf, self.answer is not None
            self.answer, conf, n_tokens = self.llm.run(strat, self.query)
            self.conf = float(np.clip(conf, 0.0, 1.0))
            cost = n_tokens / 1000.0
            self.cost += cost
            self.used[STRATEGIES.index(strat)] = 1.0
            if strat in LADDER:
                self._rung = max(self._rung, LADDER.index(strat) + 1)
            reward = -self.lam * cost
            if had_answer or self.reward_initial_confidence:
                reward += self.beta * (self.conf - prev_conf)

        truncated = not terminated and self.t >= self.max_steps
        if terminated or truncated:
            correct = self.answer is not None and bool(self.check(self.answer, self.gold))
            reward += 1.0 if correct else -1.0
            info.update(is_correct=correct, total_cost=self.cost, answer=self.answer)
        info["action_mask"] = self._mask()
        return self._obs(), float(reward), terminated, truncated, info

    def _next_rung(self):
        return next((i for i in range(self._rung, len(LADDER)) if LADDER[i] in self.supported), None)

    def _mask(self) -> np.ndarray:
        m = np.ones(len(A), dtype=bool)
        for s in STRATEGIES:
            m[s] = s in self.supported
        m[A.DIRECT] = False
        m[A.ESCALATE] = self._next_rung() is not None
        m[A.STOP] = self.answer is not None
        return m

    def _obs(self) -> np.ndarray:
        emb = self._emb_cache.get(self.query)
        if emb is None:
            v = np.asarray(self.llm.embed(self.query), dtype=np.float32)
            # hidden state của LLM có vài chiều outlier rất lớn -> L2-norm để mạng Q không bị chi phối bởi chúng
            emb = self._emb_cache[self.query] = v / (np.linalg.norm(v) + 1e-8)
        return np.concatenate(
            [
                emb,
                complexity_features(self.query, version=self.complexity_version),
                [self.conf],
                self.used,
                [self.t / self.max_steps],
            ]
        ).astype(np.float32)
