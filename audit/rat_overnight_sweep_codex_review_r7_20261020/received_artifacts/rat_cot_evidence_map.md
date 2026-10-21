# RAT–CoT Evidence Map & Structural AST Mapping (Repair r6)

**Date**: 2026-10-20  
**Scope**: Overnight RAT–CoT System Architecture, Verified AST Symbol Grounding, Strict Provenance Identity (F1), and Current-Run Execution Isolation (F2)  
**Target Publication / Protocol**: NCKH Student Research Paper / `docs/project_scope.md` & `docs/research_protocol.md`  

---

## 1. System Relationship & Research Boundaries

RAT (Retrieval-Augmented Tool/Thought) is the **primary application implementation** of structured reasoning / Chain-of-Thought (CoT), not a disposable secondary demo. CoT is implemented and expressed through RAT. The headless experiment harness evaluates the underlying reasoning method reproducibly; it does not replace RAT as the implementation target.

Per `docs/project_scope.md` and `docs/research_protocol.md`:
- **Core implementation**: Execution contracts, tool verification, intent parsing, deterministic routing, progressive search, grounded reasoning flow projection, and resident lifecycle.
- **Headless pipeline**: Calibration threshold fitting, synthetic ladder replay, benchmark sweeps, and optimal stopping simulations.
- **Evidence standard**: Publish only claims supported by reviewed raw artifacts and actual measurements. Unconnected, synthetic, or unmeasured components are explicitly labeled. Passing software tests or module imports do not transform unmeasured UI interactions or synthetic metrics into empirically verified model properties.
- **Zero Real-Model Requests**: The historical 12-call MLX inference ledger (`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`) remains byte-identical and budget-locked. No new real generation calls were executed.

---

## 2. Canonical Symbol Grounding & Call Path Map (100% AST Verified)

All components are mapped to their actual, verified AST symbols, exact file locations, and structural roles:

| Architectural Layer | Implementation Module | Verified AST Symbols | Structural Role & Evidence Status |
|---|---|---|---|
| **Deterministic Intent Parsing** | `rat/engine/finder_intent.py` | `parse_finder_intent`, `FinderIntentPlan`, `is_slide_row`, `is_report_row` | **Shared Core**: Deterministic rule-based intent parsing (temporal windows, file extension heuristics). Verified via 327-test consolidated suite. |
| **Grounded Reasoning Flow** | `rat/engine/work_trace.py` | `build_reasoning_flow`, `TraceEntry`, `summarize_step` | **Shared Core**: Constructs user-facing execution steps from `AgentStep`, `TurnContract`, and `ReconciliationReport`. Strictly forbids reading private thought tokens (`AgentStep.thought`). |
| **Workbench Desk Projection** | `rat/ui/workbench_scene.py` | `WorkSceneProjector`, `WorkSceneSnapshot`, `WorkbenchScene`, `ResultDeskCard` | **GUI Presentation**: Projects runtime receipts, observed source cards, and grounded trace into Qt widgets. Adheres to V1–V4 visual specifications (space reclamation, collapsible desk cards, distinguishing candidate prefixes). |
| **Candidate View Rendering** | `rat/ui/view_renderer.py` | `QtViewRenderer._render_input_form` | **GUI Presentation**: Constructs candidate selection buttons (`QPushButton` with `CandidateBtn` styling) using multi-depth directory disambiguation, filesystem bundle stem collision resolution (`Path(p).stem`), full paths in tooltips/payloads, and index-based event dispatch. |
| **Selected Document QA Adapter** | `rat/engine/selected_document_qa.py` | `answer_selected_document`, `selected_document_messages` | **Runtime Adapter**: Executes single mechanical indexed document read (`read_document`), prepares grounded context, and executes single model generation call (`max_tokens=640`, `timeout=90s`). |
| **Native MLX Model Session** | `rat/engine/mlx_document_session.py` | `MLXDocumentSession`, `_native_backend` | **Native Model Backend**: Direct Apple Silicon MLX inference session managing key-value cache and streaming generation (`Qwen3.5-4B-MLX-4bit`). |
| **Operation Dispatch & Resolution** | `rat/kernel/dispatcher.py`<br>`rat/kernel/capabilities/applications.py` | `ActionDispatcher`, `create_applications_capability`, `ApplicationCatalog` | **Execution Engine**: Validates inputs, handles disambiguation, and executes checked application launches via explicit user confirmation. |
| **Resident System Tray Lifecycle** | `rat/os/menu_bar.py`<br>`rat/os/app.py` | `SystemTrayManager`, `ResidentApplication` | **OS Integration**: Hosts macOS menu bar icon, status transitions, and hotkey activation shield. Preserves R1 f-string QSS brace escaping. |
| **Entry Prediction (Headless)** | `reasoning/entry_predictor.py` | `EntryPredictor`, `EntryChoice`, `EntryTrainingData`, `collect_entry_training_data` | **Headless Research**: Classifies task difficulty into fast-path vs multi-step ladder. Evaluated in headless experiments (`test_entry_predictor.py`); *not directly wired into the live RAT GUI turn dispatch*. |
| **Optimal Stopping Policy** | `reasoning/optimal_stopping.py` | `OptimalStoppingPolicy`, `CalibrationData`, `fit_threshold`, `PlattCalibrator`, `IsotonicCalibrator` | **Headless Research**: Fits post-hoc confidence thresholds for early termination in synthetic and replayed multi-step chains. *Not wired into live MLX token streaming decode*. |
| **Untyped Reasoning Parsing** | `reasoning/reasoning_strategies.py` | `extract_conclusion_number`, `_clean_cand`, `EQUALS_RESULT`, `TRAILING_NUMERIC_RESULT` | **Reasoning Core**: Evaluates terminal conclusion clause first before scalar extraction. Preserves terminal rationals and expressions (e.g. `Answer: 2 + 2 = 4; 1 / 4 = 1/4`, `Therefore 2 + 2 = 4; 1 / 4 = 1/4`, `x = 3/4`, `x = 3.25/4`) without intermediate scalar override (`= 4`). |
| **Provenance Verification (F1)** | `scripts/run_native_performance_session.py` | `classify_record_backend` | **Session Runner**: Eliminates string substring heuristics (`model_path` contains checkpoint, `document_path` contains temp directory). Classifies `"real"` strictly on explicit `backend_type == "real"` or exact `(call_index, timestamp_utc)` signature matching against the reviewed 12-call historical ledger. Synthetic or unverified records classify as `"unknown"` or `"fake"`. |
| **Current-Run Execution Isolation (F2)** | `scripts/run_native_performance_session.py` | `main` reporting block | **Session Runner**: Both real and fake reporting paths strictly isolate current-run executions (`real_calls_count = new_real_executed`, `fake_calls_count = new_fake_executed`). When budget guard halts on existing history (0 new requests dispatched), executed count is strictly `0`, warm latency is `null`, and status reflects `budget_halt_existing_real_history` (or fake/unknown history). |

---

## 3. Empirical Evidence & Scoped Claims

### A. Execution Constraints vs. Early Stopping
- **Measured Reality**: `answer_selected_document` enforces a strict **one-call execution budget** (`calls == 1`) and max step bound (`max_steps == 2`). If a model completion fails to answer from the excerpt or requests excess steps, the runtime returns an unresolved decision rather than retrying indefinitely.
- **Scoped Claim**: Early termination on confidence saturation is evaluated **offline in the research harness** via `OptimalStoppingPolicy` and calibrated probability thresholds (`PlattCalibrator`, `IsotonicCalibrator`). The native MLX streaming loop (`MLXDocumentSession.chat_with_meta`) streams tokens until `stop` or `max_tokens=640`; it does *not* currently inspect verification receipts on a per-token basis to halt generation midway through decoding.
- **Evidence Source**: `audit/rat_overnight_sweep_codex_repair_r6_20261020/calls.jsonl` preserves the 12 locked real-model generation requests byte-identically.

### B. Strict Provenance Classification (F1 / E2 Resolution)
- **Measured Reality**: In previous revisions, `classify_record_backend` relied on `model_path` containing `"qwen3.5"` or `"mlx-community"`, or `document_path` containing `"rat_native_perf_f9mhsshs"`. Reviewer probes demonstrated that synthetic fixtures derived from fake runs modifying only those path fields were falsely classified as real.
- **Scoped Claim**: Path strings describe inputs or configured weights, not execution provenance. In repair r6, `classify_record_backend` verifies explicit `backend_type == "real"` or exact `(call_index, timestamp_utc)` matching against the reviewed 12-call historical ledger signatures. All unverified or synthetic records lacking authenticated signatures evaluate to `"unknown"` (or `"fake"`), preventing synthetic fixtures from masquerading as verified real inference.
- **Evidence Source**: `audit/rat_overnight_sweep_codex_repair_r6_20261020/legacy_identity_and_real_history.txt` (8/8 pass, including 4 path text variants and 1 same-document CLI replay).

### C. Current-Run Isolation and Guard Halts (F2 / E3 Resolution)
- **Measured Reality**: When `--fake-backend` or real mode ran against an exhausted budget ledger, the runner previously fell back to reporting historical record totals as executed calls of the current process and attempted to compute warm latency from previous sessions.
- **Scoped Claim**: Reporting for both real and fake modes strictly isolates current-process dispatches. When the guard halts with 0 new requests dispatched:
  - `real_calls_count = 0` (or `fake_calls_count = 0`),
  - `scope_status = "budget_halt_existing_real_history"` (or fake/unknown history),
  - `relevant_for_warm = []` (`warm_generation_latency_ms = None`).
  Historical totals remain segregated under `historical_ledger_totals`.
- **Evidence Source**: Replays in `fake_history_halt`, `locked_ledger_replay`, `legacy_fake_history_halt`, and `same_document_legacy_fake` all report 0 executed calls and null warm latency upon guard halt.

---

## 4. Evidence Classification Matrix

| Component | Integration Status | Telemetry Measured | Test Evidence Location |
|---|---|---|---|
| `parse_finder_intent` | Shared Production | Rule-based execution duration | `tests/test_progressive_search.py`, `test_finder_integration_probes.py` |
| `build_reasoning_flow` | Shared Production | Step counts, status transitions | `tests/test_workbench_scene.py`, `test_review_probes.py` |
| `ResultDeskCard` | RAT GUI Production | Rendered dialogue reconciliation, visibility state | `test_visual_acceptance.py` (V2), `test_followup_acceptance.py` (R2) |
| `QtViewRenderer._render_input_form` | RAT GUI Production | Path suffix & bundle stem collision resolution, visible distinction | `test_visual_acceptance.py` (V3), `test_followup_acceptance.py` (R3), `test_remaining_probes.py` (C4), `test_final_edges.py` (hosted 420px) |
| `SystemTrayManager` | RAT OS Integration | Lifecycle startup/shutdown without QSS syntax errors | `tests/test_crash_shield.py` (R1) |
| `MLXDocumentSession` | Native Backend | Wall clock, prompt/completion tokens, first token latency, phase breakdown | `audit/rat_overnight_sweep_codex_repair_r6_20261020/calls.jsonl` (12 calls) |
| `answer_selected_document` | Runtime Adapter | Reconciliation report, artifact emission | `tests/test_selected_document_qa.py`, `test_selected_document_ui.py` |
| `EntryPredictor` | Headless Pipeline | Accuracy, ladder simulation cost | `test_entry_predictor.py`, `tests/test_research_study.py` |
| `OptimalStoppingPolicy` | Headless Pipeline | Calibration ECE, threshold curves | `test_optimal_stopping.py`, `tests/test_research_study.py` |
| `_clean_cand` / `EQUALS_RESULT` / Fallback | Reasoning Core | Terminal rational/expression preservation over intermediate scalars | `test_provenance_and_conclusion.py` (E1, 4/4 pass), `test_final_edges.py` (D1, 4/4 pass) |
| Provenance Signature Mapping (F1) | Session Runner | Verified signature mapping, unknown fallback | `test_legacy_identity_and_real_history.py` (F1, 5/5 pass) |
| Current-Run Isolation (F2) | Session Runner | Symmetric executed call counting, halt status, warm nulling | `test_legacy_identity_and_real_history.py` (F2, 3/3 pass) |
