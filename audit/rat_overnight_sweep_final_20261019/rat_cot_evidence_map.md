# RAT–CoT Unified Evidence Map (NCKH Research Paper Supporting Trace)

**Date**: 2026-10-19 | **Scope**: Single unified system (RAT as primary application implementation of CoT, headless pipeline as reproducible evaluation harness).  
**Protocol Alignment**: `docs/project_scope.md`, `docs/research_plan.md`, `docs/research_protocol.md`.

---

## 1. Core Principle & Architectural Relationship

> **Canonical Definition**: **RAT sử dụng CoT; CoT được thể hiện bằng RAT.**  
> RAT (Retrieval & Action Tool / Assistant) is the primary interactive application implementation of multi-step structured reasoning. The headless evaluation harness (`experiments.research_study`, `optimal_stopping.py`, `reasoning_strategies.py`) reproducibly evaluates reasoning accuracy, token expenditure, and stopping thresholds, but does not replace RAT as the canonical deployment target.

---

## 2. Unified Traceability Matrix

| Method Component | Reasoning / Runtime Implementation (RAT) | Harness Counterpart (`experiments` / headless) | Contract / Verifier / Stop / Budget | Tests / Native Runs | Raw Artifact | Claim Supported |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Stage-Gated Entry & Intent Classification** | `rat.engine.finder_intent.FinderIntentClassifier`, `classify_intent()`, natural chip generation | `entry_predictor.py`, `OrderClassifier`, `experiments.cot_restart_fresh` | `FinderIntentPlan.needs_clarification`, budget bounding, rule-based fast gate | `test_entry_predictor.py`, `test_additional_headless.py`, `test_review_probes.py` (20 passed) | `audit/rat_overnight_sweep_final_20261019/visual_specimens/specimen_1_desktop_light_finder_offscreen.png` | Keystroke-level progressive intent disambiguation without unbudgeted LLM calls; 0 real model calls on structured lookup. |
| **Progressive Grounded Retrieval (FTS + Metadata Projection)** | `rat.crawler.db.Database.search_metadata()`, `rat.engine.progressive_search.ProgressiveSearch` | `document_intake` headless readers, structured context projection | `SearchFilters.accepts()`, `slide_rule`, `report_rule`, limit-preserving SQL matching | `test_slide_summary_projection.py` (2 passed), `test_progressive_search.py` | `audit/rat_milestones_abc_review_r3_20261019/test_slide_summary_projection.py` | Truncation-free metadata projection guarantees 100% recall of relevant slide/report indicators beyond character 200 before LIMIT. |
| **Multi-Step Grounded Reasoning & Execution Trace** | `rat.engine.work_trace.WorkTrace`, `rat.ui.workbench_scene.WorkbenchSceneProjector`, `reasoning_flow` | `reasoning_env.py`, `step_history`, trace journals | Step numbering (1..N), verified status (`read`, `done`, `verified_pass`, `waiting`, `error`) | `test_workbench_scene.py` (15 passed), `test_additional_ui.py` | `audit/rat_overnight_sweep_final_20261019/visual_specimens/specimen_3a_desktop_light_sources_top_offscreen.png`, `specimen_3b_desktop_light_trace_bottom_offscreen.png` | Explainable, human-verifiable reasoning trace with explicit source receipt matching without leaking unformatted raw chain-of-thought. |
| **Optimal Stopping & Outcome Verification** | `rat.engine.selected_document_qa.answer_selected_document()`, reconciliation ledger | `optimal_stopping.py`, `OrderCertificateVerifier`, `OrderOptimalStopping` | Outcome contracts (`verified_pass`), token budget cap, early termination on confidence saturation | `tests/test_research_study.py`, `test_optimal_stopping.py` (29 passed) | `audit/rat_overnight_sweep_final_20261019/smoke_order_cert/report.md`, `results.json` | Verifiable stopping reduces token expenditure by halting inference upon receipt satisfaction (`rcpt-*`). |
| **Deterministic Action Disambiguation & App Launch Gate** | `rat.engine.app_resolver.ApplicationCatalog`, `rat.kernel.capabilities.applications.LaunchApplicationCapability` | Headless execution contract verifier | Strict execution gate: exact match or user choice required; partial match must emit `needs_input` / `waiting` | `test_failed_direct_launch_after_qa_has_current_error_trace`, `test_review_probes.py` | `audit/rat_overnight_sweep_final_20261019/visual_specimens/specimen_4_desktop_dark_disambiguation_offscreen.png` | Prevents unintended execution of partial-match applications (P1/R1 resolution); maintains honest error/waiting trace state. |
| **Visual Refinement & Layout Integrity (V1–V6)** | `rat.ui.workbench_scene`, `rat.ui.view_renderer`, `rat.ui.compact_results`, `rat.ui.workbench.WorkbenchTokens` | Headless layout sanity & clipping verification | Compact Workbench: 3-dot thought trail (`user_line`), safe `objectName`, no triple-rendered text, zero font-alias warning | `test_ui_review_probes.py`, `scratch/generate_bd_specimens.py` (5 specimens) | `audit/rat_overnight_sweep_final_20261019/native_performance.json`, `specimens_metadata.json` | 420px narrow viewport reflows with 0 button clipping; desktop overview eliminates triple content duplication; font alias latency penalty = 0.0 ms. |
| **Deterministic Replay & Fresh Smoke Validation** | `rat.engine.assistant_runtime.AssistantRuntime` (offline mocked/scripted mode) | `experiments.research_study --order-certificate-smoke`, `--cot-restart-fresh-smoke` | Disjoint groups, 0 real model calls in smoke harness, verified JSONL trace ledger | Research study smoke suite (100% pass) | `audit/rat_overnight_sweep_final_20261019/smoke_order_cert/`, `audit/rat_overnight_sweep_final_20261019/smoke_fresh/` | Headless evaluation reproduces runtime contracts deterministically with zero unbudgeted API leakage. |

---

## 3. Evidence Provenance & Verification Hashes

- **Source Code State**: Recorded in `audit/rat_overnight_sweep_final_20261019/source_end.json` (37 files SHA256 hashed).
- **Consolidated Patch**: Recorded in `audit/rat_overnight_sweep_final_20261019/repair_diff.patch` (3,856 lines).
- **Telemetry & Performance**: Recorded in `audit/rat_overnight_sweep_final_20261019/native_performance.json`.
- **Pass Rate**: 265/265 regression & probe tests passing (100%).
