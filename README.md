# structured-multi-step-reasoning

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![MLX](https://img.shields.io/badge/optimized-Apple%20Silicon%20MLX-black.svg)](https://github.com/ml-explore/mlx)
[![Desktop Demo](https://img.shields.io/badge/demo-RAT%20macOS%20App-orange.svg)](rat/ROADMAP.md)
[![Status](https://img.shields.io/badge/status-active%20research-green.svg)](docs/research_plan.md)

Fine-tuning **Qwen3-8B** on Apple Silicon (`MLX`) to emit explicitly checkable multi-step reasoning traces (`<think>`, `Step`, `Calc`), verified via **counterfactual step interventions** to ensure final predictions causally depend on intermediate steps rather than post-hoc rationalization. Includes **RAT**, a native macOS desktop overlay agent built with `QtQuick` and `Rust`/`Python` used as the interactive testbed.

[Research Plan](docs/research_plan.md) | [Literature Survey](docs/literature_survey.md) | [RAT Roadmap](rat/ROADMAP.md)

---

## 1. Core Formulation & Causal Faithfulness

Standard Chain-of-Thought (CoT) fine-tuning often suffers from **unfaithful rationalization**: the model outputs seemingly plausible reasoning steps $z_{1:K}$ while computing the final answer $y$ via internal shortcuts independent of $z_{1:K}$. We enforce structural step verifiability and causal dependency through three mechanisms:

### A. Structured Step Decomposition
Given an input problem $x$, the model $\pi_\theta$ generates a discrete sequence of atomic, verifiable steps $z = (z_1, z_2, \dots, z_K)$ followed by final answer $y$:
$$\pi_\theta(y, z_{1:K} \mid x) = \pi_\theta(y \mid z_{1:K}, x) \prod_{k=1}^{K} \pi_\theta(z_k \mid z_{<k}, x)$$
Each step contains a bounded operation (e.g. `Calc(48 / 2 = 24)`), parsed and checked by deterministic symbolic solvers (`SymPy` / sandboxed Python AST) without arbitrary code execution.

### B. Counterfactual Step Intervention ($\text{do}$-Calculus)
To verify whether the final answer $y$ causally depends on intermediate step $z_k$, we apply a targeted perturbation operator $\mathcal{I}_k: z_k \mapsto \tilde{z}_k$ (editing a single intermediate `Calc` calculation) and let the model continue generation. Continuations are classified into deterministic outcome classes:

$$\mathcal{E}_k(x) = \begin{cases}
\textbf{follows} & \text{if } |\hat{y}_{\text{continued}} - y_{\text{expected}}| \le \epsilon \quad (\text{thinking causally drives the answer}) \\
\textbf{reverted} & \text{if } |\hat{y}_{\text{continued}} - y_{\text{original}}| \le \epsilon \quad (\text{model ignored or repaired the change}) \\
\textbf{follows\_rounded} & \text{if answer reflects commonsense clamping / rounding around } y_{\text{expected}} \\
\textbf{moved} & \text{if answer shifted to a distinct value on a flagged trace}
\end{cases}$$

A reasoning trace is **causally faithful** iff perturbing an essential intermediate step $z_k$ induces a deterministic shift in downstream deductions ($\mathbb{I}[\tilde{y} \neq y_{\text{orig}}] = 1$), whereas unfaithful traces revert to the original answer regardless of the edit.

### C. Confidence-Aware Help-Seeking Policy
During sequential generation, step-level predictive entropy is monitored:
$$H(z_k) = -\sum_{v \in \mathcal{V}} P_\theta(v \mid z_{<k}) \log P_\theta(v \mid z_{<k})$$
When $H(z_k) > \tau$, self-generation halts and triggers external verification or an adaptive fallback policy to prevent cascading error propagation.

---

## 2. Research Gates & Evaluation Protocol

Research progression follows an empirical gated validation protocol across `GSM8K` and checkable subsets of `MATH-500`:

| Gate | Validation Requirement | Empirical Status | Notes |
| :--- | :--- | :---: | :--- |
| **0. Format Learned** | `format_valid` $\ge 90\%$ on held-out dev | ⚠️ 70% | Improving step delimiters and prompt engineering |
| **1. Gap Exists** | Base model follows edited `Calc` $< 95\%$ | ⚠️ Open | Base model on GSM8K follows edited calculations strongly ($0/53$ kept old answer) |
| **2. Literature Novelty**| Unaddressed intervention paradigm | ✅ Passed | Provisional check confirms room in counterfactual reasoning evaluation |
| **3. Benchmark Complexity**| Hard enough for multi-step differentiation | ✅ Passed | Comparison modes score $55\%$–$64\%$ on MATH subset |
| **4. Signal Calibration** | Step checks catch $\ge 50\%$ wrong answers with $\le 20\%$ false alarms | 🔄 Active Tuning | Equation check calibration in progress on `audit/` runs |

---

## 3. Repository Architecture

```text
structured-multi-step-reasoning/
├── structured_llm/                   # Core MLX training & causal intervention engine
│   ├── trace.py                      # Step parsing, rendering (<think>, Step, Calc) & AST checks
│   ├── gsm8k.py                      # GSM8K dataset conversion, isolation & splits
│   ├── math_check.py & math_data.py  # SymPy equation verification & checkable MATH subset
│   ├── counterfactual.py             # Perturbation planning & counterfactual trace regeneration
│   ├── evaluate.py                   # Multi-mode model evaluation (base, instructed, tuned)
│   ├── intervene.py                  # Step intervention runner & outcome classifier
│   ├── analyze.py                    # Rescores audit logs & outputs RQ1 correlation tables
│   ├── pal.py                        # Sandboxed program-aided math interpreter
│   └── train.sh                      # LoRA fine-tuning for Apple Silicon Metal (16GB M1/M2/M3)
├── rat/                              # RAT: Native macOS desktop agent testbed
│   ├── main.py                       # Resident menu bar app entry point
│   ├── engine/                       # Execution runtime, verification, search & routing
│   ├── kernel/                       # Tool dispatcher, contracts & capabilities
│   ├── ui/                           # QtQuick / QML translucent floating desktop overlay
│   ├── os/                           # macOS hotkeys, permissions, daemon & shell integration
│   └── crawler/                      # Local file indexing by name and semantic meaning
├── data/                             # Pinned datasets and split manifests
├── audit/                            # Raw evaluation outputs and step intervention traces
├── runs/                             # Experiment run directories and benchmark artifacts
├── docs/                             # Research plan, literature surveys, and architecture specs
└── tests/                            # Unit test suite (pytest)
```

---

## 4. Quickstart & Reproduction

### Environment Setup
Requires macOS with Apple Silicon and Python 3.12:

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run test suite
pytest tests/test_analyze.py tests/test_counterfactual.py tests/test_math_check.py tests/test_structured_trace.py -q
```

### MLX Fine-Tuning & Intervention Harness
```bash
# 3. Prepare data and generate counterfactual intervention plans
python -m structured_llm.gsm8k
python -m structured_llm.counterfactual

# 4. Fine-tune Qwen3-8B with LoRA on Apple Silicon
structured_llm/train.sh adapters/first 200

# 5. Evaluate and run counterfactual step intervention
python -m structured_llm.evaluate --adapter adapters/first --limit 20 --out audit/first
python -m structured_llm.intervene --run audit/first --adapter adapters/first
python -m structured_llm.analyze audit/first
```

### Launch Interactive RAT Desktop Testbed
```bash
# Install RAT desktop dependencies and run native menu bar agent
pip install -r requirements-rat.txt
python -m rat.main
```
