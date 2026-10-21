# Consolidated Overnight Sweep Repair Handoff — RAT–CoT System

**Date**: 2026-10-19  
**Review Reference**: `audit/rat_overnight_sweep_repair_codex_review_20261019/review.md`  
**Execution Context**: Solo Git Workflow on `main` (zero commits/pushes/resets/branches), unified RAT–CoT / NCKH student research paper framework, strictly offline / fake-backend instrumentation testing with zero new real-model generation requests.

---

## 1. Executive Summary & Verification Verdict

All 6 findings (**R1–R6**) from the independent review have been addressed, verified with code fixes, and validated through empirical test suites:
- **Consolidated Regression & Visual Acceptance Suite**: **289 / 289 PASSED** (0 failures, 0 errors, 0 skipped) in 37.26s (`regression_and_visual.xml`).
  - Baseline regression suite: 245 cases
  - Milestone & repair review probes: 20 cases
  - Visual acceptance probes (`test_visual_acceptance.py`): 6 cases
  - Follow-up acceptance probes (`test_followup_acceptance.py`): 5 cases
  - Crash shield & resident tray tests (`test_crash_shield.py`): 8 cases
  - Parser & harness regression tests (`test_harness_regressions.py`): 5 cases
- **Mandatory Research Protocol Checks**: **29 / 29 PASSED** in 3.00s (`pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q`).
- **Real-Model Backend Calls**: Exactly **0 new calls** issued (budget strictly capped at 12). All 12 historical records preserved in locked `calls.jsonl`.
- **Triage of 19 Full-Sweep Failures**: Fully triaged into 3 code bugs (now fixed) and 16 stale test expectations / deprecated legacy adapters documented with exact contracts.

---

## 2. Detailed Resolution of Review Findings (R1–R6)

### R1 — [P1 Startup Blocker] System Tray QSS F-String Braces Fixed
- **Root Cause**: In `rat/os/menu_bar.py`, lines 107–119, the stylesheet was formatted as an f-string to inject `{FONT_FAMILY}`, but CSS rule blocks for `QMenu::item`, `QMenu::item:selected`, and `QMenu::separator` used single braces (`{ padding: ... }`), triggering `NameError: name 'padding' is not defined` when `SystemTrayManager()` was instantiated during resident startup.
- **Fix**: Escaped all CSS rule blocks with double braces (`{{ padding: 6px 14px; ... }}`).
- **Verification**: `tests/test_crash_shield.py::TestCrashShield::test_system_tray_manager_shutdown` now **PASSES** cleanly (full test suite passes 8/8 in 1.48s). Resident tray initialization occurs without runtime exceptions.

### R2 — [P2 / V2] Answer Visibility Reconciled on Mode Navigation & Rendering
- **Root Cause**: In `rat/ui/omnibar.py` (`_sync_workbench_scene`, `_on_scene_mode_changed`, `_present_compact_reply`) and `rat/ui/workbench_scene.py` (`apply_snapshot`), `bubble_has_full_answer` checked `_copy_text` instead of rendered text. When the user navigated from source detail back to overview, `_copy_text` still held the answer even though the speech bubble was displaying a navigation status message, causing `ResultDeskCard` to hide while the bubble also did not show the answer.
- **Fix**: Replaced `_copy_text` inspection with rendered `dialogue.text()`, ensuring that `ResultDeskCard` only collapses when the answer text is visibly rendered in the speech bubble. In `_on_scene_mode_changed`, added explicit result card visibility reconciliation when returning to `scene_mode == "overview"`.
- **Verification**: All 5 cases in `audit/rat_overnight_sweep_repair_codex_review_20261019/test_followup_acceptance.py` **PASS** (initial, source-detail-back, snapshot-refresh). Both cases in `test_visual_acceptance.py` (V2) continue to **PASS**. Answer remains visibly accessible on at least one surface at all times.

### R3 — [P2 / V3] Multi-Depth Path Suffix Distinction Across Candidates
- **Root Cause**: In `rat/ui/view_renderer.py`, candidate button formatting previously relied solely on `Path(p).parent.name`. For system vs user installations located in identically named parent folders (e.g. `/Applications/League of Legends.app` vs `/Users/fixture/Applications/League of Legends.app`), both buttons received the identical label `Applications · League of Legends · v1.0`.
- **Fix**: Implemented candidate-wide collision resolution that computes the shortest unique path suffix across all candidates before formatting button labels. Suffixes are joined with ` · ` and elided cleanly if length exceeds the width budget. Tooltips and choice payloads retain the full absolute path.
- **Verification**: `test_v3_installations_with_same_parent_name_remain_distinguishable` passes for both same-parent-basename collision and different-parent control. Buttons render distinct visible labels (`Applications · ...` vs `fixture/Applications · ...`).

### R4 — [P2] Native Runner Instrumentation & Append-Only Ledger
- **Root Cause**: `scripts/run_native_performance_session.py` previously opened `calls.jsonl` in `"w"` mode, recorded only post-completion events, lacked pre-request checkpoints, and lacked durable global budget enforcement.
- **Fix**:
  1. Added `--fake-backend` flag utilizing a lightweight mock tokenizer/backend to verify runner execution, lifecycle, and budget accounting offline without touching MLX weights or issuing model requests.
  2. Implemented append-only ledger (`"a"` mode) preserving all historical entries.
  3. Added pre-request durable checkpoint (`{"event": "request_start", "call_index": ..., "request_id": ..., ...}`) flushed to disk immediately prior to dispatching each query.
  4. Added post-request event (`{"event": "request_complete", ...}`) with full latency and token breakdown, flushed immediately.
  5. Added durable global budget guard counting all recorded attempts/requests; if attempts reach `--max-budget` (default 12), the runner halts and refuses to issue additional generation calls.
- **Verification**: Verified offline in temporary test directories with `--fake-backend`. Pre-request checkpoints, completed events, and budget guard halt on rerun confirmed 100%. Locked 12 real calls from previous session preserved intact.

### R5 — [P2] Telemetry Provenance & Measurement Boundaries Scoped
- **Corrected Fields in `native_performance.json`**:
  - `host_cpu_percent: 57.8`: Explicitly documented as system-wide host CPU across all cores during 1.0s `psutil.cpu_percent()` interval, not RAT process idle CPU.
  - `process_idle_cpu_percent: null`: Scoped as unmeasured (runner process was executing setup/teardown; resident app was not measured in an isolated idle state).
  - `backend_runner_rss_mb: 2221.72` & `backend_runner_peak_rss_mb: 2503.25`: Accurately identified as the memory footprint of the headless MLX inference worker loading 4-bit weights, not the resident GUI app.
  - `resident_gui_app_rss_mb: null`: Resident Workbench GUI app memory was not measured in the headless run.
  - `document_prefix_prefill_ms: 10605.94`: Timed on cold document context prepare.
  - `question_suffix_prefill_ms: null`: Question suffix tokens are processed during generation wall time and not separately timed by MLX.
  - `displayed_ui_token_ms: null`: Runner was headless; live UI token stream rendering was not hosted.
  - `warm_generation_latency_ms`: Recorded accurately with range 4,635.92–47,359.53 ms, median 6,364.26 ms, call 8 at 31,830.36 ms. Clarified that varying question complexity across warm runs does not constitute matched before/after cache speedup.
  - `font_alias_population_cost_ms: 203.0`: Scoped to offscreen `QApplication` initialization probe before creating any RAT window; does not measure RAT window first-paint or stylesheet render latency.

### R6 — [P2] AST Evidence Map Corrected (100% Symbol Accuracy)
- **Corrections in `rat_cot_evidence_map.md`**:
  - Replaced `UnifiedDispatcher` with actual AST class `ActionDispatcher` in `rat/kernel/dispatcher.py`.
  - Replaced `CandidateChoiceButton` with `QtViewRenderer` (`render_candidates` creating `QPushButton` widgets with `objectName="CandidateBtn"`).
  - Replaced `_execute_launch_app` with actual entry callable `create_applications_capability` in `rat/kernel/capabilities/applications.py`.
  - Scoped all headless research models (`EntryPredictor`, `OptimalStoppingPolicy`) as headless-only components, confirming they are not wired into the live GUI dispatch or MLX token streaming decode.

---

## 3. Triage of the 19 Full-Sweep Test Failures

Analysis of the 19 active test failures identified during the 132-file inventory:

| Test File & Case | Failure Category | Root Cause & Contract Analysis | Resolution Status |
|---|---|---|---|
| `tests/test_crash_shield.py::test_system_tray_manager_shutdown` | **Code Bug (R1)** | Single braces in f-string QSS in `rat/os/menu_bar.py` raised `NameError: name 'padding' is not defined`. | **FIXED** in `rat/os/menu_bar.py`. Test passes (8/8 pass). |
| `tests/test_harness_regressions.py::test_regression_react_placeholder_rejection` | **Code Bug** | `<kết quả>` placeholder leaked into parsed answer in untyped ReAct mode. | **FIXED** in `reasoning/reasoning_strategies.py` (`_clean_cand`). Test passes. |
| `tests/test_harness_regressions.py::test_regression_parser_does_not_pick_wrong_trailing_token_or_unit` | **Code Bug** | Terminal equation `= <number>` leaked equation string into answer instead of scalar conclusion; trailing dot in `extract_number`. | **FIXED** in `reasoning/reasoning_strategies.py` (`_clean_cand` and regex). Test passes (5/5 pass). |
| `tests/test_reranker_golden.py` (1 case) | **Stale Expectation** | Test asserted hardcoded `len(candidate["_feats"]) == 20`. Production `Reranker` was extended with 5 academic features (`study_doc`, `sem_dir`, `course_code_dir`, `slide_lecture`, `acronym_match`), yielding 25 features. All 20 score values, bounds, and additive feature sums continue to pass exactly. | **Analyzed & Documented**. Feature schema is 25 in production; scores invariant. |
| `tests/test_query_compounds.py` (8 cases) | **Stale Expectation** | `ContextParser.parse_query` was connected to `curriculum_mapper.expand()` to add course codes (e.g. `501011`, `CALC1`, `GT1`) into `clean_keywords`. Compound keywords are properly preserved as unfragmented phrases (`giai tich`), but tests asserted exact pre-curriculum keyword list `["giai tich", "slides"]`. | **Analyzed & Documented**. Production behavior preserves compound matching while expanding curriculum codes for student search. |
| `tests/test_vgc_cascade.py` (6 cases) | **Stale Expectation / Deprecated Adapter** | Legacy cascade tests assert English substrings (`"verified"`, `"mismatch"`) while production `CalculationVerifier` was localized to Vietnamese (`"đối chiếu ..."`). `rat/engine/vgc.py` is explicitly documented as a legacy deterministic helper not used by the live assistant. | **Analyzed & Documented**. Live assistant uses `answer_selected_document`, `ReconciliationReport`, and `WorkTrace`. |
| `tests/test_vgc_ui_integration.py` (1 case) | **Stale Expectation / Deprecated Adapter** | Deprecated citation packaging test expecting legacy VGC `valid` certificate status rather than live `ReconciliationReport`. | **Analyzed & Documented**. Live UI relies on `WorkSceneSnapshot` and `AgentStep` verification. |

---

## 4. Verification Evidence & Artifact Manifest

All artifacts are preserved in `audit/rat_overnight_sweep_repair_codex_repair_20261019/`:

- `command.json`: Complete argv and environment variables for the 289-test consolidated regression run.
- `regression_and_visual.xml`: JUnit XML report confirming **289 passed**, 0 failed, 0 errors, 0 skipped.
- `calls.jsonl`: Locked 12-call ledger containing real-model generation telemetry.
- `native_performance.json`: Telemetry metrics with verified measurement boundaries and unmeasured annotations.
- `rat_cot_evidence_map.md`: Verified AST architectural mapping with 100% symbol accuracy.
- `source_start.json`: 40-file start manifest matching the previous review.
- `source_end.json`: Actual sha256 hashes of all 41 tracked files.
- `repair_diff.patch`: Exact unified diff of the 7 modified files against `reviewed_source/`.
- `validation.json`: Summary verdict and findings verification record.
- `visual_specimens/`: Fresh offscreen specimens and metadata:
  - `specimen_1_desktop_light_finder_offscreen.png`: Compact Desktop Finder (light, 620x600).
  - `specimen_2_narrow_420px_light_offscreen.png`: Narrow 420px Finder with compact action buttons.
  - `specimen_3a_desktop_light_sources_top_offscreen.png` & `specimen_3b_desktop_light_trace_bottom_offscreen.png`: Desktop Light QA showing collapsed `ResultDeskCard` and grounded reasoning trace.
  - `specimen_4_desktop_dark_disambiguation_offscreen.png`: Desktop Dark App Disambiguation with distinguishing candidate prefixes (`Applications · ...` vs `Riot Games · ...`).
  - `specimens_metadata.json`: Offscreen capture metadata and geometry metrics.

---

## 5. Source Delta Summary (7 Files Modified)

| Modified File | Delta Description |
|---|---|
| `rat/os/menu_bar.py` | Escaped QSS f-string braces in `QMenu::item`, `QMenu::item:selected`, and `QMenu::separator`. |
| `rat/ui/omnibar.py` | Checked rendered `dialogue.text()` for answer presence; added result card visibility reconciliation on mode change back to overview. |
| `rat/ui/workbench_scene.py` | Checked rendered `dialogue.text()` in `apply_snapshot` before hiding `ResultDeskCard`. |
| `rat/ui/view_renderer.py` | Implemented candidate-wide multi-depth unique path suffix resolution for disambiguation buttons. |
| `reasoning/reasoning_strategies.py` | Stripped prompt placeholders in `_clean_cand`; extracted scalar conclusion from terminal equations; fixed trailing dot regex. |
| `scripts/generate_fresh_specimens.py` | Configured output path to `audit/rat_overnight_sweep_repair_codex_repair_20261019/visual_specimens/`. |
| `scripts/run_native_performance_session.py` | Added `--fake-backend`, append-only ledger, pre-request checkpoint/flush, post-request event, and budget guard. |

---

## 6. Open Scopes & Honest Boundaries

1. **Native Interactive Scenarios**: The 12 real-model records represent real MLX inference on local document context in a headless environment. Interactive scenarios requiring live token streaming into a visible Cocoa window, mid-generation user cancellations, file modification invalidations, and outside-excerpt queries remain unmeasured in live GUI mode and are explicitly flagged as `not_run / blocked` pending interactive display access and dedicated model inference budget.
2. **Research Harness Separation**: The headless experiment pipeline evaluates optimal stopping thresholds and entry prediction policies on offline data. These research mechanisms are not wired into live MLX token decoding and should not be claimed as runtime decode optimizations.
