# RAT–CoT Evidence Map & Structural Mapping

**Date**: 2026-10-19  
**Scope**: Overnight RAT–CoT System Architecture, Symbol Grounding, and Empirical Evidence Map  
**Target Publication / Protocol**: NCKH Student Research Paper / `docs/project_scope.md` & `docs/research_protocol.md`  

---

## 1. System Relationship & Research Boundaries

RAT (Retrieval-Augmented Tool/Thought) is the **primary application implementation** of structured reasoning / Chain-of-Thought (CoT), not a disposable secondary demo. CoT is implemented and expressed through RAT. The headless experiment harness evaluates the underlying reasoning method reproducibly; it does not replace RAT as the implementation target.

Per `docs/project_scope.md` and `docs/research_protocol.md`:
- **Core implementation**: Execution contracts, tool verification, intent parsing, deterministic routing, progressive search, and grounded reasoning flow projection.
- **Headless pipeline**: Calibration threshold fitting, synthetic ladder replay, benchmark sweeps, and optimal stopping simulations.
- **Evidence standard**: Publish only claims supported by reviewed raw artifacts and actual measurements. Unconnected, synthetic, or unmeasured components are explicitly labeled.

---

## 2. Canonical Symbol Grounding & Call Path Map

All components are mapped to their actual AST symbols, verified file locations, and structural roles.

| Architectural Layer | Implementation Module | Actual AST Symbols | Role & Evidence Status |
|---|---|---|---|
| **Deterministic Intent Parsing** | `rat/engine/finder_intent.py` | `parse_finder_intent`, `FinderIntentPlan`, `is_slide_row`, `is_report_row` | **Shared Core**: Deterministic rule-based intent parsing (temporal windows, file extension heuristics). Verified via 265-test suite and probes. |
| **Grounded Reasoning Flow** | `rat/engine/work_trace.py` | `build_reasoning_flow`, `TraceEntry`, `summarize_step` | **Shared Core**: Constructs user-facing execution steps from `AgentStep`, `TurnContract`, and `ReconciliationReport`. Strictly forbids reading private thought tokens (`AgentStep.thought`). |
| **Workbench Desk Projection** | `rat/ui/workbench_scene.py` | `WorkSceneProjector`, `WorkSceneSnapshot`, `WorkbenchScene`, `ResultDeskCard` | **GUI Presentation**: Projects runtime receipts, observed source cards, and grounded trace into Qt widgets. Adheres to V1–V4 visual specifications (space reclamation, collapsible desk cards, distinguishing candidate prefixes). |
| **Selected Document QA Adapter** | `rat/engine/selected_document_qa.py` | `answer_selected_document`, `selected_document_messages` | **Runtime Adapter**: Executes single mechanical indexed document read (`read_document`), prepares grounded context, and executes single model generation call (`max_tokens=640`, `timeout=90s`). |
| **Native MLX Model Session** | `rat/engine/mlx_document_session.py` | `MLXDocumentSession`, `_native_backend` | **Native Model Backend**: Direct Apple Silicon MLX inference session managing key-value cache and streaming generation (`Qwen3.5-4B-MLX-4bit`). |
| **Operation Dispatch & Resolution** | `rat/kernel/dispatcher.py`<br>`rat/kernel/capabilities/applications.py` | `UnifiedDispatcher`, `create_applications_capability`, `ApplicationCatalog` | **Execution Engine**: Validates inputs, handles disambiguation, and executes checked application launches via explicit user confirmation. |
| **Entry Prediction (Headless)** | `reasoning/entry_predictor.py` | `EntryPredictor`, `EntryChoice`, `EntryTrainingData`, `collect_entry_training_data` | **Headless Research**: Classifies task difficulty into fast-path vs multi-step ladder. Evaluated in headless experiments (`test_entry_predictor.py`); *not directly invoked in the live RAT GUI turn dispatch*. |
| **Optimal Stopping Policy** | `reasoning/optimal_stopping.py` | `OptimalStoppingPolicy`, `CalibrationData`, `fit_threshold`, `PlattCalibrator`, `IsotonicCalibrator` | **Headless Research**: Fits post-hoc confidence thresholds for early termination in synthetic and replayed multi-step chains. *Not wired into live MLX token streaming decode*. |

---

## 3. Empirical Evidence & Scoped Claims

In accordance with independent review findings (O1, O2) and academic integrity principles:

### A. Execution Constraints vs. Early Stopping
- **Measured Reality**: `answer_selected_document` enforces a strict **one-call execution budget** (`calls == 1`) and max step bound (`max_steps == 2`). If a model completion fails to answer from the excerpt or requests excess steps, the runtime returns an unresolved decision rather than retrying indefinitely.
- **Scoped Claim**: Early termination on confidence saturation is evaluated **offline in the research harness** via `OptimalStoppingPolicy` and calibrated probability thresholds (`PlattCalibrator`, `IsotonicCalibrator`). The native MLX streaming loop (`MLXDocumentSession.chat_with_meta`) streams tokens until `stop` or `max_tokens=640`; it does *not* currently inspect verification receipts on a per-token basis to halt generation midway through decoding.
- **Evidence Source**: `audit/rat_overnight_sweep_repair_20261019/calls.jsonl` records real generation requests, showing single-attempt executions with exact token counts and latencies.

### B. Progressive Finder Intent & Retrieval Scope
- **Measured Reality**: SQL predicate projections in `rat/crawler/db.py` and `rat/engine/progressive_search.py` pass explicit filtering rules (e.g. `is_slide_row`, creation/modification date ranges). Two specific regressions (direct parent folder match and summary projection clipping after 200 characters) were identified and verified by probes.
- **Scoped Claim**: The query and projection fixes guarantee that valid search hits with indicators beyond 200 characters or within matching folder structures are preserved across the SQLite LIMIT boundary. This resolves specific false-negative omissions; it does **not** assert 100% recall across arbitrary unindexed files or unstructured corpora.
- **Evidence Source**: `audit/rat_milestones_abc_review_r3_20261019/test_slide_summary_projection.py` (2/2 pass) and `audit/rat_overnight_sweep_repair_20261019/regression.xml`.

### C. Visual Desk Refinements (V1–V4)
- **V1 (Card Posture & Style)**: Source cards and overflow widgets maintain distinct styling, object naming, and interactive click-to-open postures.
- **V2 (Result Card Collapse on Full Short Bubble)**: When the speech bubble presents the full short answer without truncation, and no interactive artifacts or revision transitions exist, `ResultDeskCard` collapses/hides while keeping its underlying `answer_lbl` populated.
- **V3 (Candidate Distinguishing Visible Labels)**: Disambiguation buttons prefix the distinguishing directory segment (e.g. `Applications · ` vs `Riot Games · `) within available button contents width, while retaining the full path in tooltips and choice payloads.
- **V4 (Quiet Structured Finder Flow)**: Structured Finder queries display a collapsed toggle disclosure even in `phase == 'empty'`, while bare queries produce no fake trace entries.
- **Evidence Source**: `audit/rat_overnight_sweep_repair_20261019/visual_probes.xml` (6/6 pass).

---

## 4. Evidence Classification Matrix

| Component | Integration Status | Telemetry Measured | Test Evidence Location |
|---|---|---|---|
| `parse_finder_intent` | Shared Production | Rule-based execution duration | `tests/test_progressive_search.py`, `test_finder_integration_probes.py` |
| `build_reasoning_flow` | Shared Production | Step counts, status transitions | `tests/test_workbench_scene.py`, `test_review_probes.py` |
| `ResultDeskCard` | RAT GUI Production | Visibility state, geometry reachability | `test_visual_acceptance.py` (V2), `test_workbench_scene.py` |
| `CandidateChoiceButton` | RAT GUI Production | Text contents width, visible distinction | `test_visual_acceptance.py` (V3) |
| `MLXDocumentSession` | Native Backend | Wall clock, prompt/completion tokens, first token latency, phase breakdown | `audit/rat_overnight_sweep_repair_20261019/calls.jsonl` |
| `answer_selected_document` | Runtime Adapter | Reconciliation report, artifact emission | `tests/test_selected_document_qa.py`, `test_selected_document_ui.py` |
| `EntryPredictor` | Headless Pipeline | Accuracy, ladder simulation cost | `test_entry_predictor.py`, `tests/test_research_study.py` |
| `OptimalStoppingPolicy` | Headless Pipeline | Calibration ECE, threshold curves | `test_optimal_stopping.py`, `tests/test_research_study.py` |
