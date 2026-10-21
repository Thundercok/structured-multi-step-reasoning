# RAT–CoT Evidence Map: Methodology, Runtime Architecture & Evaluation Harness

**Date**: 2026-10-20  
**Context**: NCKH Student Research Paper Implementation & Headless Reproducible Evaluation  
**Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. High-Level System Architecture: One System, Two Expressions

As confirmed in `docs/project_scope.md`:
- **RAT is the primary application implementation of the Structured Reasoning / CoT method**, not a disposable demo.
- **The Headless Research Harness evaluates the exact same reasoning system reproducibly**; it does not replace RAT as the implementation target.
- The two expressions share identical canonical algorithmic implementations under `reasoning/`.

```
                        ┌──────────────────────────────────────────────────────────┐
                        │        Canonical RL Reasoning Core (reasoning/)          │
                        │  - EntryPredictor (RTR Dual Score: acc - lam * cost)     │
                        │  - OptimalStoppingPolicy (Backward Induction Tau)        │
                        │  - PolicyBundle & Provenance Validator                   │
                        │  - OnlineReasoningController (Budget & Cancel Contracts) │
                        └────────────┬─────────────────────────────┬───────────────┘
                                     │                             │
             ┌───────────────────────▼─────────┐         ┌─────────▼───────────────────────┐
             │    Desktop Runtime Expression   │         │    Headless Research Harness    │
             │             (RAT UI)            │         │      (experiments/ & tests/)    │
             ├─────────────────────────────────┤         ├─────────────────────────────────┤
             │ - rat.engine.meta_reasoner      │         │ - experiments.research_study    │
             │ - rat.ui.reasoning_worker       │         │ - experiments.cot_restart_fresh │
             │ - rat.ui.assistant_worker       │         │ - experiments.cot_restart_pilot │
             │ - rat.engine.selected_doc_qa    │         │ - tests/test_research_study     │
             │ - rat.ui.omnibar                │         │ - tests/test_optimal_stopping   │
             └─────────────────────────────────┘         └─────────────────────────────────┘
```

---

## 2. Five-Tier Evidence Mapping Table

| Tier 1: Method Principle | Tier 2: Canonical Implementation (`reasoning/`) | Tier 3: RAT Runtime Expression | Tier 4: Headless Research Counterpart | Tier 5: Contracts, Stopping & Budget | Tier 6: Raw Evidence Artifacts | Tier 7: Legitimate Claims vs Explicit Boundaries |
|---|---|---|---|---|---|---|
| **Entry Dual Predictor** | `reasoning/entry_predictor.py` (shim: `entry_predictor.py`) | `MetaReasonerEngine.solve()` via `OnlineReasoningController` | `experiments/research_study.py`, `test_entry_predictor.py` | Routes to LADDER, REACT, or PAL based on embedding + complexity features | `tests/test_online_reasoning.py`, `test_entry_predictor.py` (10 tests) | **Claim**: Dynamic routing selects strategy without gold truth. **Limit**: Does not prove human superiority or cross-model generalization. |
| **Optimal Stopping Ladder** | `reasoning/optimal_stopping.py` (shim: `optimal_stopping.py`) | Escalates $COT \to SC \to TOT$ in `OnlineReasoningController` | `experiments/research_study.py`, `test_optimal_stopping.py` | Backward induction thresholds $\tau$; stops when transformed confidence $\ge \tau_k$ | `tests/test_optimal_stopping.py` (10 tests), `tests/test_online_reasoning.py` | **Claim**: Stops multi-step ladder when confidence threshold met. **Limit**: Thresholds depend on calibration distribution. |
| **Policy Bundle Provenance** | `reasoning/bundle.py` (shim: `bundle.py`) | `build_composed_meta_reasoner()` with fail-closed validation | `PolicyBundle.to_dict()` JSON validation in experiments | Validates model snapshot, prompt profile, lambda, thresholds, dimensions; rejects unreviewed/mismatched | `tests/test_policy_bundle.py` (11 tests pass), `specimen_bundle.json` | **Claim**: Safe, pickle-free bundle composition; fails closed on missing/unreviewed. **Limit**: Synthetic specimen marked dev-only. |
| **Budget & Attempt Ledger** | `reasoning/runtime.py` (`ExecutionCostLedger`) | `OnlineReasoningWorker` with subcall tracking | `experiments/cot_restart_fresh.py`, `scripts/run_native_performance_session.py` | Multi-call tracking (SC=5, TOT=4); failed/cancelled attempts charged; generated tokens $\ne$ full cost | `tests/test_online_reasoning_execution.py` (8 tests pass), `calls.jsonl` (12 calls) | **Claim**: Every dispatched attempt is charged to budget. **Limit**: Generated token count is not full cloud/hardware cost. |
| **Cooperative Cancellation & Timeout** | `reasoning/runtime.py` (`deadline_monotonic`, `is_cancelled`) | `OnlineReasoningWorker` checks `isInterruptionRequested()` | Controllable doubles in native tests | Cooperative polling in prefill, decode, and between ladder rungs; drops late callbacks | `tests/test_native_acceptance_readiness.py` (8 tests pass) | **Claim**: Prevents runaway generation cooperatively. **Limit**: Hard OS thread preemption is not supported. |
| **Document QA vs Strategy LLM Boundary** | `reasoning/runtime.py` protocol check | `rat/engine/selected_document_qa.py`, `rat/engine/mlx_document_session.py` | `tests/test_mlx_document_session.py`, `tests/test_selected_document_qa.py` | `MLXDocumentSession` rejected as strategy `LLMBackend`; document missing/changed $\to$ unresolved | `tests/test_mlx_document_session.py` (26 tests pass), `test_online_reasoning_execution.py` | **Claim**: Selected document QA and strategy backend remain strictly separated. **Limit**: No false PASS inheritance. |
| **Verifier & Arithmetic Contracts** | `rat/engine/vgc.py`, `rat/engine/verification.py` | `MetaReasonerEngine._solve_with_pal` with `literal_request` | `tests/test_research_scoring.py`, `test_reasoning_strategies.py` | VGC returns VALID, INVALID, or UNVERIFIABLE; zero tokens and 0.0 confidence for missing inputs | `test_reasoning_strategies.py` (30 tests), `tests/test_research_scoring.py` (14 tests) | **Claim**: No fabricated CPA/tuition figures or artificial confidence. **Limit**: Arithmetic checker covers literal grammar only. |

---

## 3. Preservation of Prior Ledgers and Audit Manifests

1. **12 Real-Call Historical Ledger**:
   - SHA256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`
   - Verified byte-identical across all historical audits and this acceptance directory.
   - Zero new real-model requests executed in this cycle.
2. **Prior Review Audits Maintained**:
   - Consolidation r3: `audit/rat_cot_structural_consolidation_review_r3_20261020/` (S1/S2/P3 closed).
   - Overnight Sweep Repair r7: `audit/rat_overnight_sweep_codex_repair_r7_20261020/` (G1 resolved, 331 tests pass).
   - Candidate Review 71/70: `audit/cot_restart_fresh_data_review_20261016/` (pending human review).
