# RAT–CoT Evidence Map & Structural AST Mapping

**Date**: 2026-10-19  
**Scope**: Overnight RAT–CoT System Architecture, Verified AST Symbol Grounding, and Empirical Evidence Map  
**Target Publication / Protocol**: NCKH Student Research Paper / `docs/project_scope.md` & `docs/research_protocol.md`  

---

## 1. System Relationship & Research Boundaries

RAT (Retrieval-Augmented Tool/Thought) is the **primary application implementation** of structured reasoning / Chain-of-Thought (CoT), not a disposable secondary demo. CoT is implemented and expressed through RAT. The headless experiment harness evaluates the underlying reasoning method reproducibly; it does not replace RAT as the implementation target.

Per `docs/project_scope.md` and `docs/research_protocol.md`:
- **Core implementation**: Execution contracts, tool verification, intent parsing, deterministic routing, progressive search, grounded reasoning flow projection, and resident lifecycle.
- **Headless pipeline**: Calibration threshold fitting, synthetic ladder replay, benchmark sweeps, and optimal stopping simulations.
- **Evidence standard**: Publish only claims supported by reviewed raw artifacts and actual measurements. Unconnected, synthetic, or unmeasured components are explicitly labeled. Passing software tests or module imports do not transform unmeasured UI interactions or synthetic metrics into empirically verified model properties.

---

## 2. Canonical Symbol Grounding & Call Path Map (100% AST Verified)

All components are mapped to their actual, verified AST symbols, exact file locations, and structural roles:

| Architectural Layer | Implementation Module | Verified AST Symbols | Structural Role & Evidence Status |
|---|---|---|---|
| **Deterministic Intent Parsing** | `rat/engine/finder_intent.py` | `parse_finder_intent`, `FinderIntentPlan`, `is_slide_row`, `is_report_row` | **Shared Core**: Deterministic rule-based intent parsing (temporal windows, file extension heuristics). Verified via 309-test suite and probes. |
| **Grounded Reasoning Flow** | `rat/engine/work_trace.py` | `build_reasoning_flow`, `TraceEntry`, `summarize_step` | **Shared Core**: Constructs user-facing execution steps from `AgentStep`, `TurnContract`, and `ReconciliationReport`. Strictly forbids reading private thought tokens (`AgentStep.thought`). |
| **Workbench Desk Projection** | `rat/ui/workbench_scene.py` | `WorkSceneProjector`, `WorkSceneSnapshot`, `WorkbenchScene`, `ResultDeskCard` | **GUI Presentation**: Projects runtime receipts, observed source cards, and grounded trace into Qt widgets. Adheres to V1–V4 visual specifications (space reclamation, collapsible desk cards, distinguishing candidate prefixes). |
| **Candidate View Rendering** | `rat/ui/view_renderer.py` | `QtViewRenderer._render_input_form` | **GUI Presentation**: Constructs candidate selection buttons (`QPushButton` with `CandidateBtn` styling) using multi-depth directory disambiguation, filesystem bundle stem collision resolution (`Path(p).stem`), full paths in tooltips/payloads, and index-based event dispatch. (Note: Rendered via `_render_input_form`; `render_candidates` does not exist). |
| **Selected Document QA Adapter** | `rat/engine/selected_document_qa.py` | `answer_selected_document`, `selected_document_messages` | **Runtime Adapter**: Executes single mechanical indexed document read (`read_document`), prepares grounded context, and executes single model generation call (`max_tokens=640`, `timeout=90s`). |
| **Native MLX Model Session** | `rat/engine/mlx_document_session.py` | `MLXDocumentSession`, `_native_backend` | **Native Model Backend**: Direct Apple Silicon MLX inference session managing key-value cache and streaming generation (`Qwen3.5-4B-MLX-4bit`). |
| **Operation Dispatch & Resolution** | `rat/kernel/dispatcher.py`<br>`rat/kernel/capabilities/applications.py` | `ActionDispatcher`, `create_applications_capability`, `ApplicationCatalog` | **Execution Engine**: Validates inputs, handles disambiguation, and executes checked application launches via explicit user confirmation. (Note: Class name is `ActionDispatcher`, not `UnifiedDispatcher`; entry callable is `create_applications_capability`, not `_execute_launch_app`). |
| **Resident System Tray Lifecycle** | `rat/os/menu_bar.py`<br>`rat/os/app.py` | `SystemTrayManager`, `ResidentApplication` | **OS Integration**: Hosts macOS menu bar icon, status transitions, and hotkey activation shield. Fixed R1 f-string QSS brace escaping. |
| **Entry Prediction (Headless)** | `reasoning/entry_predictor.py` | `EntryPredictor`, `EntryChoice`, `EntryTrainingData`, `collect_entry_training_data` | **Headless Research**: Classifies task difficulty into fast-path vs multi-step ladder. Evaluated in headless experiments (`test_entry_predictor.py`); *not directly wired into the live RAT GUI turn dispatch*. |
| **Optimal Stopping Policy** | `reasoning/optimal_stopping.py` | `OptimalStoppingPolicy`, `CalibrationData`, `fit_threshold`, `PlattCalibrator`, `IsotonicCalibrator` | **Headless Research**: Fits post-hoc confidence thresholds for early termination in synthetic and replayed multi-step chains. *Not wired into live MLX token streaming decode*. |
| **Untyped Reasoning Parsing** | `reasoning/reasoning_strategies.py` | `extract_conclusion_number`, `_clean_cand`, `EQUALS_RESULT`, `TRAILING_NUMERIC_RESULT` | **Reasoning Core**: Normalizes extracted conclusion tokens across both marker and fallback paths while strictly preserving rational expressions/fractions (e.g. `Therefore x = 3/4`, `x = 3.25/4`) using non-backtracking lookahead `(?!\.?\d)(?!\s*[/÷×*+-])` and unified `_clean_cand` fallback delegation. |

---

## 3. Empirical Evidence & Scoped Claims

In accordance with independent review findings (D1, D2, C1–C4, R1–R6) and academic integrity principles:

### A. Execution Constraints vs. Early Stopping
- **Measured Reality**: `answer_selected_document` enforces a strict **one-call execution budget** (`calls == 1`) and max step bound (`max_steps == 2`). If a model completion fails to answer from the excerpt or requests excess steps, the runtime returns an unresolved decision rather than retrying indefinitely.
- **Scoped Claim**: Early termination on confidence saturation is evaluated **offline in the research harness** via `OptimalStoppingPolicy` and calibrated probability thresholds (`PlattCalibrator`, `IsotonicCalibrator`). The native MLX streaming loop (`MLXDocumentSession.chat_with_meta`) streams tokens until `stop` or `max_tokens=640`; it does *not* currently inspect verification receipts on a per-token basis to halt generation midway through decoding.
- **Evidence Source**: `audit/rat_overnight_sweep_codex_repair_r4_20261019/calls.jsonl` preserves the 12 locked real-model generation requests, showing single-attempt executions with exact token counts (370 completion tokens total) and latencies.

### B. Progressive Finder Intent & Retrieval Scope
- **Measured Reality**: SQL predicate projections in `rat/crawler/db.py` and `rat/engine/progressive_search.py` pass explicit filtering rules (e.g. `is_slide_row`, creation/modification date ranges). Two specific regressions (direct parent folder match and summary projection clipping after 200 characters) were identified and verified by probes.
- **Scoped Claim**: The query and projection fixes guarantee that valid search hits with indicators beyond 200 characters or within matching folder structures are preserved across the SQLite LIMIT boundary. This resolves specific false-negative omissions; it does **not** assert 100% recall across arbitrary unindexed files or unstructured corpora.
- **Evidence Source**: `audit/rat_milestones_abc_review_r3_20261019/test_slide_summary_projection.py` (2/2 pass) and consolidated regression suite (309/309 pass).

### C. Visual Desk Refinements (V1–V4, C4)
- **V1 (Card Posture & Style)**: Source cards and overflow widgets maintain distinct styling, object naming, and interactive click-to-open postures.
- **V2 (Result Card Collapse & Dialogue Visibility Reconcile)**: Evaluates rendered dialogue text (`dialogue.text()`) rather than raw internal copy buffer (`_copy_text`). Reconciles `ResultDeskCard` visibility across overview, mode switches (source detail -> back), streaming updates, and snapshot refreshes, guaranteeing answer visibility on at least one surface.
- **V3 & C4 (Candidate Distinguishing Visible Labels & Stem Disambiguation)**: Computes minimal unique path suffixes across candidate directories. When candidates share the exact same directory and metadata name (e.g. `/Applications/League of Legends.app` vs `/Applications/League of Legends copy.app`), falls back to filesystem bundle stem (`Path(p).stem`), ensuring visible distinction in a hosted 420px viewport while preserving full paths in tooltips/payloads.
- **V4 (Quiet Structured Finder Flow)**: Structured Finder queries display a collapsed toggle disclosure even in `phase == 'empty'`, while bare queries produce no fake trace entries.
- **Evidence Source**: `audit/rat_overnight_sweep_codex_review_20261019/test_visual_acceptance.py` (6/6 pass), `audit/rat_overnight_sweep_repair_codex_review_20261019/test_followup_acceptance.py` (5/5 pass), `audit/rat_overnight_sweep_codex_review_r3_20261019/test_remaining_probes.py` (13/13 pass), and `audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py` (7/7 pass).

### D. Native Telemetry & Performance Measurement Boundaries (C2, D2)
- **Host CPU vs Process CPU**: `host_cpu_percent` is 57.8% (measured system-wide via `psutil.cpu_percent(interval=1.0)`). `process_idle_cpu_percent` is null because resident app idle CPU was not isolated.
- **Runner RSS vs GUI App RSS**: Runner RSS (104.09 MB current, 876.31 MB peak in original 12-call run) reflects the MLX inference runner. `resident_gui_app_rss_mb` is null.
- **Prefill & Decode Timing**: Document-prefix prefill is 10,605.94 ms (measured on cold document prepare). Question-suffix prefill is not separately timed by MLX and is included in overall generation wall time. Warm generation latency ranges from 4,635.92 ms to 47,359.53 ms (median 6,364.26 ms, call 8 at 31,830.36 ms).
- **Font Alias Warning**: 203 ms warning occurred during offscreen `QApplication` initialization probe before creating any RAT window. It does not measure RAT window first paint or stylesheet rendering time.
- **Provenance Separation (D2)**: Headless fake simulations (`--fake-backend`) separate current-run requests from historical ledger totals. When budget guard halts on existing 12-call real history, `fake_model_calls_executed` strictly outputs `0`, status records `budget_halt_existing_real_history`, and `warm_generation_latency_ms` evaluates to `null`. Historical real-model 12-call telemetry is preserved with its original measurement baseline.

---

## 4. Evidence Classification Matrix

| Component | Integration Status | Telemetry Measured | Test Evidence Location |
|---|---|---|---|
| `parse_finder_intent` | Shared Production | Rule-based execution duration | `tests/test_progressive_search.py`, `test_finder_integration_probes.py` |
| `build_reasoning_flow` | Shared Production | Step counts, status transitions | `tests/test_workbench_scene.py`, `test_review_probes.py` |
| `ResultDeskCard` | RAT GUI Production | Rendered dialogue reconciliation, visibility state | `test_visual_acceptance.py` (V2), `test_followup_acceptance.py` (R2) |
| `QtViewRenderer._render_input_form` | RAT GUI Production | Path suffix & bundle stem collision resolution, visible distinction | `test_visual_acceptance.py` (V3), `test_followup_acceptance.py` (R3), `test_remaining_probes.py` (C4), `test_final_edges.py` (hosted 420px) |
| `SystemTrayManager` | RAT OS Integration | Lifecycle startup/shutdown without QSS syntax errors | `tests/test_crash_shield.py` (R1) |
| `MLXDocumentSession` | Native Backend | Wall clock, prompt/completion tokens, first token latency, phase breakdown | `audit/rat_overnight_sweep_codex_repair_r4_20261019/calls.jsonl` (12 calls) |
| `answer_selected_document` | Runtime Adapter | Reconciliation report, artifact emission | `tests/test_selected_document_qa.py`, `test_selected_document_ui.py` |
| `EntryPredictor` | Headless Pipeline | Accuracy, ladder simulation cost | `test_entry_predictor.py`, `tests/test_research_study.py` |
| `OptimalStoppingPolicy` | Headless Pipeline | Calibration ECE, threshold curves | `test_optimal_stopping.py`, `tests/test_research_study.py` |
| `_clean_cand` / `EQUALS_RESULT` / Fallback | Reasoning Core | Rational/fraction expression retention across marker & fallback | `test_remaining_probes.py` (C1), `test_final_edges.py` (D1), `test_reasoning_strategies.py` |
| Telemetry Provenance & Budget Guard | Session Runner | Per-request backend tagging, current vs historical counts | `test_remaining_probes.py` (C2, C3), `test_final_edges.py` (D2) |
