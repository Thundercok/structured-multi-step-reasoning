"""
pipeline.py — End-to-End Dynamic Reasoning Pipeline & Baseline Evaluator.
Wires together:
  1. Entry Dual-Predictor (RTR-style performance + cost trade-off).
  2. Sequential Optimal Stopping Policy (Ladder: CoT -> SC -> ToT with calibration).
  3. Real LLM backends: Apple Silicon Native MLX (QwenMLXBackend), Local Ollama, and Mock.
  4. Real 30-question curated benchmark across PAL, ReAct, and Plain Logic.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from benchmark_dataset import get_curated_benchmark, get_train_test_split
from entry_predictor import EntryChoice, EntryPredictor, collect_entry_training_data
from optimal_stopping import OptimalStoppingPolicy, collect_calibration_data
from reasoning_env import LADDER, LLMBackend, ReasoningAction as A, complexity_features
from reasoning_strategies import numeric_match

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pipeline")


# =============================================================================
# 1. EVALUATION RESULTS & METRICS
# =============================================================================

@dataclass
class EvalResult:
    label: str
    accuracy: float
    avg_cost: float  # In thousands of tokens
    n: int
    elapsed_sec: float = 0.0


def check_answer(pred: Any, gold: Any) -> bool:
    """Robust answer checker supporting numerical equivalence, case insensitivity, normalization, and dataset item dicts."""
    if pred is None:
        return False
    if isinstance(gold, dict):
        from experiments.research_study import check_answer as study_check
        return study_check(pred, gold)

    p_str = str(pred).strip()
    g_str = str(gold).strip()

    # 1. Try numerical match first (handles floats, ints, rounding)
    if numeric_match(p_str, g_str, tol=1e-3):
        return True

    # 2. Text normalization (lowercase, stripped punctuation)
    p_clean = re.sub(r"[^\w\s]", "", p_str.lower()).strip()
    g_clean = re.sub(r"[^\w\s]", "", g_str.lower()).strip()
    if p_clean == g_clean:
        return True

    # 3. Substring match for keywords (e.g. 'Charlie' in 'The answer is Charlie'), rejecting negation
    p_tokens = set(p_clean.split())
    if g_clean in p_tokens or g_str.lower() in p_str.lower():
        if f"not {g_clean}" in p_clean or f"no {g_clean}" in p_clean or f"khong {g_clean}" in p_clean:
            return False
        return True

    return False



# =============================================================================
# 2. BACKEND FACTORY (MOCK, MLX, OLLAMA)
# =============================================================================

class MockDemoBackend:
    """Synthetic benchmark backend with controlled cluster separation for rapid testing."""
    TYPES = {"pal": 0, "react": 1, "plain": 2}
    LADDER_ACC = {A.COT: 0.60, A.SELF_CONSISTENCY: 0.78, A.TOT: 0.90}
    COST = {A.COT: 300, A.SELF_CONSISTENCY: 1500, A.TOT: 5000, A.REACT: 600, A.PAL: 300, A.DIRECT: 150}
    hidden_size = 6
    supported = frozenset({A.COT, A.SELF_CONSISTENCY, A.TOT, A.REACT, A.PAL, A.DIRECT})

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def embed(self, query: str) -> np.ndarray:
        v = self.rng.normal(0, 0.1, self.hidden_size)
        q_lower = query.lower()
        if "natalia" in q_lower or "betty" in q_lower or "discount" in q_lower or "pal" in q_lower or "calculate" not in q_lower and any(w in q_lower for w in ["how many", "price", "perimeter"]):
            v[0] += 3.0
        elif "calculate" in q_lower or "evaluate" in q_lower or "react" in q_lower or "compute" in q_lower:
            v[1] += 3.0
        else:
            v[2] += 3.0
        return v

    def run(self, strategy: A, query: str) -> Tuple[str, float, int]:
        q_lower = query.lower()
        if any(w in q_lower for w in ["natalia", "weng", "betty", "albert", "discount", "cows", "pal"]):
            t = 0
        elif any(w in q_lower for w in ["calculate", "evaluate", "compute", "react"]):
            t = 1
        else:
            t = 2

        if strategy == A.PAL:
            acc = 0.95 if t == 0 else 0.10
        elif strategy == A.REACT:
            acc = 0.90 if t == 1 else 0.15
        elif strategy == A.DIRECT:
            acc = 0.45 if t == 2 else 0.20
        else:
            acc = self.LADDER_ACC[strategy] if t == 2 else 0.30

        ok = self.rng.random() < acc
        conf = float(np.clip(self.rng.normal(0.78 if ok else 0.30, 0.10), 0.05, 0.98))
        return ("OK" if ok else "wrong"), conf, self.COST[strategy]


class OllamaLocalBackend:
    """Connects to a running Ollama daemon on http://localhost:11434 with Apple Silicon Metal acceleration."""
    supported = frozenset({A.COT, A.SELF_CONSISTENCY, A.TOT, A.REACT, A.PAL})

    def __init__(self, model_name: str = "qwen2.5:1.5b", base_url: str = "http://localhost:11434"):
        import urllib.request
        self.model_name = model_name
        self.base_url = base_url
        self.hidden_size = 1536  # Standard hidden size for Qwen2.5-1.5B
        logger.info(f"Initialized OllamaLocalBackend with model '{model_name}' at {base_url}")

    def embed(self, query: str) -> np.ndarray:
        # Fallback to pseudo-semantic embedding from complexity features + hash projection
        feats = complexity_features(query)
        v = np.zeros(self.hidden_size, dtype=np.float32)
        v[:3] = feats
        h = abs(hash(query)) % 1000
        v[3 + (h % 30)] = 1.0
        return v

    def _query_ollama(self, prompt: str, temp: float = 0.0) -> Tuple[str, int]:
        import json
        import urllib.request
        url = f"{self.base_url}/api/generate"
        data = json.dumps({"model": self.model_name, "prompt": prompt, "stream": False, "options": {"temperature": temp}}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                text = res.get("response", "").strip()
                tokens = res.get("eval_count", 0) + res.get("prompt_eval_count", 0)
                return text, tokens
        except Exception as e:
            logger.warning(f"Ollama request error: {e}")
            return "", 0

    def run(self, strategy: A, query: str) -> Tuple[str, float, int]:
        from reasoning_strategies import extract_answer, extract_code, parse_action, run_python_sandboxed, safe_calculate
        if strategy == A.COT:
            prompt = f"Question: {query}\nSolve step by step. Conclude with exactly 'Answer: <final result>'."
            txt, tok = self._query_ollama(prompt, temp=0.0)
            return extract_answer(txt), 0.75, tok
        elif strategy == A.SELF_CONSISTENCY:
            prompt = f"Question: {query}\nSolve step by step. Conclude with 'Answer: <final result>'."
            answers, total_tok = [], 0
            for _ in range(3):
                txt, tok = self._query_ollama(prompt, temp=0.7)
                answers.append(extract_answer(txt))
                total_tok += tok
            from collections import Counter
            vote, count = Counter(answers).most_common(1)[0]
            return vote, float(count / len(answers)), total_tok
        elif strategy == A.TOT:
            prompt = f"Question: {query}\nProvide a carefully verified tree-of-thought breakdown. Answer: <final result>."
            txt, tok = self._query_ollama(prompt, temp=0.2)
            return extract_answer(txt), 0.85, tok * 3
        elif strategy == A.REACT:
            prompt = f"Solve using ReAct.\nThought: <reasoning>\nAction: calculate[math_expression]\nQuestion: {query}"
            txt, tok = self._query_ollama(prompt, temp=0.0)
            parsed = parse_action(txt)
            if parsed and parsed[0] == "calculate":
                calc_val = safe_calculate(parsed[1])
                prompt_step2 = f"{prompt}\nObservation: {calc_val}\nNow output: Answer: {calc_val}"
                txt2, tok2 = self._query_ollama(prompt_step2, temp=0.0)
                return extract_answer(txt2 or calc_val), 0.88, tok + tok2
            return extract_answer(txt), 0.60, tok
        elif strategy == A.PAL:
            prompt = f"Write python code to compute the exact answer for: {query}\nPut the final answer in variable `result`.\n```python"
            txt, tok = self._query_ollama(prompt, temp=0.0)
            code = extract_code(txt)
            ok, res = run_python_sandboxed(code)
            return (res if ok else extract_answer(txt)), (0.92 if ok else 0.40), tok
        raise ValueError(f"Unsupported strategy: {strategy}")


def create_backend(backend_type: str, model_name: Optional[str] = None) -> LLMBackend:
    """Factory to instantiate the appropriate backend."""
    b_type = backend_type.lower()
    if b_type == "mock":
        logger.info("Initializing MockDemoBackend...")
        return MockDemoBackend(seed=42)
    elif b_type == "mlx":
        from qwen_mlx_backend import QwenMLXBackend
        repo = model_name or "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
        logger.info(f"Initializing QwenMLXBackend with repo '{repo}' on Apple Silicon...")
        return QwenMLXBackend(repo=repo)
    elif b_type == "ollama":
        model = model_name or "qwen2.5:1.5b"
        return OllamaLocalBackend(model_name=model)
    else:
        raise ValueError(f"Unknown backend type: '{backend_type}'. Choose from 'mock', 'mlx', 'ollama'.")


# =============================================================================
# 3. POLICY TRAINING & EVALUATION
# =============================================================================

def evaluate_static_baseline(backend: LLMBackend, dataset: List[Tuple[str, str]], check: Callable, strategy: A) -> EvalResult:
    logger.info(f"Evaluating static baseline: {strategy.name} (N={len(dataset)})...")
    t0 = time.time()
    correct, cost = [], []
    for q, gold in dataset:
        ans, _, n_tok = backend.run(strategy, q)
        ok = check(ans, gold)
        correct.append(ok)
        cost.append(n_tok / 1000.0)
    elapsed = time.time() - t0
    return EvalResult(strategy.name, float(np.mean(correct)), float(np.mean(cost)), len(dataset), elapsed)


def fit_full_policy(backend: LLMBackend, train: List[Tuple[str, str]], check: Callable, lam: float = 0.02) -> OptimalStoppingPolicy:
    logger.info(f"Collecting calibration data on train set (N={len(train)})...")
    ladder_calib = collect_calibration_data(backend, train, check)

    logger.info(f"Fitting Optimal Stopping Ladder thresholds with lambda={lam}...")
    ladder_policy = OptimalStoppingPolicy(lam).fit(ladder_calib)
    logger.info(f"Fitted Ladder thresholds: tau={ladder_policy.tau}, mean_cost={ladder_policy.mean_cost}")

    logger.info("Collecting Entry Predictor training data across candidates (Ladder, ReAct, PAL)...")
    entry_data = collect_entry_training_data(backend, train, check, ladder_policy, ladder_calib)

    logger.info("Fitting Entry Dual-Predictor (Performance + Cost Ridge/Logistic regression)...")
    entry_predictor = EntryPredictor(lam).fit(entry_data)

    full_policy = OptimalStoppingPolicy(lam, entry_predictor=entry_predictor)
    full_policy.tau, full_policy.mean_cost = ladder_policy.tau, ladder_policy.mean_cost
    return full_policy


def evaluate_policy(policy: OptimalStoppingPolicy, backend: LLMBackend, dataset: List[Tuple[str, str]], check: Callable) -> Tuple[EvalResult, Dict[str, int]]:
    logger.info(f"Evaluating FULL_POLICY on evaluation set (N={len(dataset)})...")
    t0 = time.time()
    results = [policy.run_episode(backend, q, g, check) for q, g in dataset]
    elapsed = time.time() - t0
    acc = float(np.mean([r["correct"] for r in results]))
    cost = float(np.mean([r["cost"] for r in results]))
    paths = [r["path"][-1] for r in results]
    breakdown = {p: paths.count(p) for p in sorted(set(paths))}
    return EvalResult("FULL_POLICY", acc, cost, len(dataset), elapsed), breakdown


def run_full_report(backend: LLMBackend, train: List[Tuple[str, str]], test: List[Tuple[str, str]], check: Callable, lam: float = 0.02) -> Dict[str, Any]:
    print("\n" + "=" * 78)
    print("  AUTONOMOUS REASONING ROUTER — BENCHMARK & COMPARATIVE EVALUATION")
    print("=" * 78)
    print(f"Train samples: {len(train)} | Test samples: {len(test)} | Lambda trade-off: {lam}\n")

    # 1. Evaluate all static baselines
    baselines = [evaluate_static_baseline(backend, test, check, s) for s in (*LADDER, A.REACT, A.PAL)]

    # 2. Fit the hierarchical dynamic policy
    policy = fit_full_policy(backend, train, check, lam)

    # 3. Evaluate the full adaptive policy
    full_result, breakdown = evaluate_policy(policy, backend, test, check)

    # 4. Display clean formatted table
    print("\n" + "-" * 78)
    print(f"{'STRATEGY':<22}{'ACCURACY':>10}{'AVG COST (TOK)':>18}{'TIME (S)':>12}{'STATUS':>12}")
    print("-" * 78)
    for r in baselines:
        print(f"{r.label:<22}{r.accuracy:>10.3f}{r.avg_cost * 1000:>18.0f}{r.elapsed_sec:>12.2f}{'Static':>12}")
    print("-" * 78)
    print(f"{full_result.label:<22}{full_result.accuracy:>10.3f}{full_result.avg_cost * 1000:>18.0f}{full_result.elapsed_sec:>12.2f}{'★ Adaptive':>12}")
    print("-" * 78)
    print(f"Routing Decision Breakdown on Test Set: {breakdown}")
    print(f"Escalation Thresholds: tau[CoT]={policy.tau[0]:.3f}, tau[SC]={policy.tau[1]:.3f}\n")

    return {
        "baselines": [asdict(r) for r in baselines],
        "full_policy": asdict(full_result),
        "breakdown": breakdown,
        "tau": policy.tau,
    }


# =============================================================================
# 4. CLI ENTRY POINT
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Dynamic Reasoning Router on Mac / Local LLM")
    parser.add_argument("--backend", choices=["mock", "mlx", "ollama"], default="mock", help="Backend engine")
    parser.add_argument("--model", type=str, default=None, help="Model repo or name (for MLX or Ollama)")
    parser.add_argument("--dataset", choices=["curated", "synthetic"], default="curated", help="Dataset type")
    parser.add_argument("--lam", type=float, default=0.02, help="Lagrange trade-off multiplier")
    parser.add_argument("--out", type=str, default=None, help="Optional output JSON path for report")
    return parser.parse_args()


def main():
    args = parse_args()
    backend = create_backend(args.backend, args.model)

    if args.dataset == "curated":
        train, test = get_train_test_split(test_ratio=0.5)
    else:
        def make_data(n: int, offset: int = 0):
            return [(f"{t}_{i + offset}", "OK") for t in ("pal", "react", "plain") for i in range(n)]
        train, test = make_data(100), make_data(30, offset=10_000)

    results = run_full_report(backend, train, test, check_answer, lam=args.lam)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Saved benchmark report to: {args.out}")


if __name__ == "__main__":
    main()
