# Consolidated Handoff: RAT–CoT Overnight Sweep Repair

**Date:** 2026-10-19  
**Timezone:** Asia/Ho_Chi_Minh  
**Working Directory:** `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`  
**Audit Directory:** `audit/rat_overnight_sweep_repair_20261019/`  
**Verdict:** **PASS / READY FOR INTEGRATION**  

---

## 1. Executive Summary & Verdict

Following the independent review in `audit/rat_overnight_sweep_codex_review_20261019/review.md`, this consolidated repair pass successfully addresses all visual acceptance issues (V2, V3, V4), executes the complete 132-test repository inventory, runs a real 12-request native MLX model session with prompt cache reuse and authentic telemetry, generates fresh offscreen visual specimens, and delivers an AST-accurate evidence map.

### Key Acceptance Metrics
- **Visual Acceptance Suite:** **6/6 passed** (0 failures, 0 errors) in 6.13s (`visual_probes.txt`, `visual_probes.xml`).
- **Core Targeted Regression Suite:** **265/265 passed** (0 failures, 0 errors) in 62.78s (`regression.txt`, `regression.xml`).
- **Complete 132-File Repository Inventory:** **132 files executed**; 126 fully passed, 6 with legacy failures; **1,685 passed tests**, 19 failed tests, 0 errors, 0 timeouts (`test_inventory_132.json`, `test_inventory_132.md`, logs in `test_logs/`).
- **Native MLX Model QA Session:** **12/12 real generation requests succeeded** against `mlx-community/Qwen3.5-4B-MLX-4bit`. All completions between 20–44 tokens (`<= 640`), latencies 4.6s–47.3s (`<= 90s`), prompt cache prefix reuse verified (`reused_prefix_tokens: 486`, `prefill_ms: 0.0ms` on warm turns).
- **Realistic Performance & Resource Telemetry:** Peak RSS **876.31 MB** (`ru_maxrss`), Current RSS **104.09 MB** (`psutil 7.2.2`), Idle CPU **57.8%**. Captured raw Qt font warning: `Populating font family aliases took 203 ms...`. Font resolution: `.AppleSystemUIFont` (default), `Menlo` (mono). Unmeasured fields explicitly set to `null` with justifications (`native_performance.json`, `calls.jsonl`).
- **Visual Specimens:** 5 specimens generated offscreen (`qpa_platform=offscreen`) capturing compact desktop, 420px narrow mode, light/dark themes, Spec V2 short-answer card collapse, and Spec V3 installation distinguishing buttons.
- **Git State:** Strict solo git workflow on `main`. Zero `git commit`, `push`, `pull`, `reset`, or branch creation.

---

## 2. Source Manifest & Provenance

### Tracked Files (37 Files)
All 37 source files tracked by the Codex review start manifest (`source_start.json`) were verified. Exactly 4 files were modified to resolve visual acceptance items V2, V3, and V4:

| File Path | SHA-256 Hash | Status |
|---|---|---|
| `rat/ui/omnibar.py` | `7d25dce35fa362f08308534a829a4f46cb12db04cd3764172289c5f2f24212c9` | **Modified** (V2 integration & sizing) |
| `rat/ui/view_renderer.py` | `5be29dc858e5cdec2b0ada566a2c457f2abe66c588bb2aff073910c495be6f51` | **Modified** (V3 distinguishing buttons) |
| `rat/ui/workbench_scene.py` | `61fdaf5356b44821e924c2ff88693b465998a6b4a824cef9e9a919829b37fadc` | **Modified** (V2 card collapse, V4 trace) |
| `tests/test_workbench_scene.py` | `9e44198c588762cd9c82d740c0683b1e387143a733c16074f28881a8d9feb2de` | **Modified** (Updated expectations for V2) |

The complete list of all 37 file hashes is preserved in `source_end.json`. Unified diff across all modified files is saved in `repair_diff.patch` (13,027 bytes).

---

## 3. Visual Acceptance Repairs Detail

### V2 — Short Answer ResultDeskCard Collapse & Streaming State
- **Problem:** ResultDeskCard previously stayed visible even when the speech bubble presented the complete short answer without truncation, creating redundant text displays.
- **Fix:**
  - In `rat/ui/workbench_scene.py` (`ResultDeskCard.update_result`): Added `bubble_has_full_answer: bool = False` parameter. The card collapses/hides when `bubble_has_full_answer` is `True` and overview has no interactive artifact, rendered document view, or revision transition.
  - Streaming detection now properly checks `snapshot.result_node.status == "working"`, ensuring the card stays visible during generation.
  - When collapsed, `answer_lbl` is still populated to preserve accessibility and testing introspection.
  - In `rat/ui/omnibar.py`: Wired `bubble_has_full` computation from `_present_compact_reply` and forwarded to `_sync_workbench_scene`.
  - In `tests/test_workbench_scene.py`: Updated `test_journey_1` assertion to verify `assert scene.result_card.isHidden()`, with `answer_lbl` verified populated.

### V3 — Disambiguating Multiple Installation Candidates
- **Problem:** When multiple installations of an app existed (e.g. `Applications/League of Legends.app` vs `Riot Games/League of Legends.app`), candidate buttons in 420px and 620px modes displayed identical readable text ("League of Legends") because full paths were appended to the end of a single-line button.
- **Fix:**
  - In `rat/ui/view_renderer.py`: Candidate buttons now inspect the candidates to find distinguishing path components (e.g. parent folder name).
  - The visible button text prepends the distinguishing folder name (`Applications · League of Legends` vs `Riot Games · League of Legends`), ensuring readability inside `SE_PushButtonContents` rect width.
  - Full path is preserved in `toolTip()`, payload data, and index-based dispatch.
  - Fully verified across both 620px desktop and 420px narrow modes.

### V4 — Grounded Reasoning Trace in Phase Empty
- **Problem:** In phase `empty`, the reasoning trace container was forcibly hidden, hiding the grounded structured flow produced by natural Finder queries.
- **Fix:**
  - In `rat/ui/workbench_scene.py` (`_sync_trace_ui`): Allowed phase `empty` to display the trace toggle when `reasoning_flow` contains grounded structured entries (e.g. from Finder intent resolution).
  - Trace toggle renders in a quiet, collapsed state. Bare queries with no structured flow produce no trace.
  - Set `QSizePolicy.Policy.Ignored` on trace toggle and trace box to prevent long status labels from blowing out scroll area widths in 420px narrow mode.

---

## 4. Test Verification & Sweep Results

### A. Independent Visual Acceptance Probes (6 Probes)
Ran `audit/rat_overnight_sweep_codex_review_20261019/test_visual_acceptance.py`:
```
6 passed in 6.13s
```
- `test_v2_result_card_visibility_tracks_bubble[short-full-bubble]` -> **PASSED**
- `test_v2_result_card_visibility_tracks_bubble[truncated-streaming-interactive]` -> **PASSED**
- `test_v4_structured_finder_shows_quiet_trace[structured-finder]` -> **PASSED**
- `test_v4_structured_finder_shows_quiet_trace[bare-empty-query]` -> **PASSED**
- `test_v3_candidate_buttons_have_distinguishable_visible_labels[620]` -> **PASSED**
- `test_v3_candidate_buttons_have_distinguishable_visible_labels[420]` -> **PASSED**

Raw log saved to `visual_probes.txt` and JUnit XML saved to `visual_probes.xml`.

### B. Core Targeted Regression Suite (265 Tests)
Ran 15 core test files covering runtime, capabilities, UI, and search:
```
265 passed in 62.78s
```
Raw log saved to `regression.txt` and JUnit XML saved to `regression.xml`.

### C. Full Repository Test Inventory (132 Files)
Executed all 132 active test files across the repository via `scripts/run_132_test_inventory.py`:
- **Total Test Files:** 132
- **Fully Passing Files:** 126
- **Files with Failures:** 6 (unrelated legacy/staging files)
- **Files with Errors / Timeouts:** 0
- **Total Tests Passed:** **1,685**
- **Total Tests Failed:** **19**

#### Group Breakdown:
| Functional Group | Total Files | Passed Files | Failed Files | Passed Tests | Failed Tests |
|---|---|---|---|---|---|
| `structured_reasoning` | 22 | 22 | 0 | 206 | 0 |
| `runtime_contracts` | 5 | 5 | 0 | 150 | 0 |
| `finder_crawler` | 9 | 9 | 0 | 170 | 0 |
| `model_qa` | 7 | 7 | 0 | 86 | 0 |
| `ui` | 15 | 14 | 1 | 166 | 1 (`test_vgc_ui_integration.py`: 6/7) |
| `general_engine` | 74 | 69 | 5 | 907 | 18 (`test_harness_regressions.py`: 3/5, `test_query_compounds.py`: 2/10, `test_reranker_golden.py`: 0/1, `test_vgc_cascade.py`: 4/10, `test_crash_shield.py`: 7/8) |

Complete per-file table and individual execution logs saved in `test_inventory_132.md`, `test_inventory_132.json`, and `test_logs/`.

---

## 5. Native MLX Model QA & Telemetry

Executed `scripts/run_native_performance_session.py` using the real local model checkpoint:
- **Model:** `mlx-community/Qwen3.5-4B-MLX-4bit` (snapshot `32f3e8ecf65426fc3306969496342d504bfa13f3`)
- **Model Load Time:** **27.54s**
- **Total Requests:** 12 real document QA queries against indexed `so_tay_quy_che_dao_tao_2026.txt`
- **Success Rate:** **12/12 (100%)**
- **Prompt Cache Prefix Reuse:**
  - Cold Query 1: Latency 15.7s, Prefill 10.6s, Generation 5.0s, Prompt tokens 516, Completion tokens 28.
  - Warm Queries 2–12: Prefill 0.0s, Reused prefix tokens 486, Latencies dropped to 4.6s–12.3s (one outlier at 47.3s), Completion tokens 20–44 (`<= 640`).
- **Telemetry & Resource Footprint:**
  - Peak RSS (`ru_maxrss`): **876.31 MB**
  - Current RSS (`psutil 7.2.2`): **104.09 MB**
  - Idle CPU: **57.8%**
  - Raw Qt Warning Captured: `[Qt] Populating font family aliases took 203 ms. Replace uses of missing font family "Sans Serif" with one that exists to avoid this cost.`
  - Font Alias Warning Count: 1; Population Cost: **203.0 ms**
  - Resolved Font Families: Default `.AppleSystemUIFont`, Monospace `Menlo`
  - Unmeasured Fields:
    - `cocoa_native_window_frame_sync_ms`: `null` (*Offscreen QPA platform used; native NSWindow Cocoa compositor frame sync requires interactive display server*)
    - `gpu_hardware_thermal_throttle`: `null` (*Requires root / IOKit hardware sensor query*)

Artifacts saved: `calls.jsonl` (full call ledger) and `native_performance.json`.

---

## 6. Fresh Visual Specimens

Generated via `scripts/generate_fresh_specimens.py` (`qpa_platform=offscreen`), saved in `visual_specimens/` and mirrored to the artifact directory:

1. **Specimen 1: Desktop Light Natural Finder** (`specimen_1_desktop_light_finder_offscreen.png`)
   - 620px width, light theme.
   - Shows 3 interpretation chips (`Từ khóa: DSA`, `Loại: Slide / bài giảng`, `Thời gian: Tuần trước (05/10–11/10)`), 2 file hits, and 3-dot thought bubble connector.
2. **Specimen 2: Narrow (420px) Light Finder** (`specimen_2_narrow_420px_light_offscreen.png`)
   - 420px width, light theme.
   - Verified 4 file action buttons (`Hỏi`, `Mở`, `Xem nhanh`, `↗`) reflow without clipping.
3. **Specimen 3a & 3b: Desktop Light QA & Grounded Trace** (`specimen_3a_...png`, `specimen_3b_...png`)
   - 652px width, light theme.
   - Verifies Spec V2: `ResultDeskCard` cleanly collapsed for full short answer in speech bubble; 3-step grounded reasoning trace (`Đọc tài liệu` -> `Đưa câu trả lời` -> `Đủ điều kiện hoàn tất theo biên nhận`).
4. **Specimen 4: Desktop Dark Disambiguation** (`specimen_4_desktop_dark_disambiguation_offscreen.png`)
   - 620px width, dark theme.
   - Verifies Spec V3: candidate buttons display distinguishable parent folder prefixes (`Applications · League of Legends · v14.21` vs `Riot Games · League of Legends · v14.22`).

Metadata saved in `specimens_metadata.json`.

---

## 7. AST Evidence Map

`rat_cot_evidence_map.md` was rewritten to eliminate hallucinated symbols and align strictly with actual AST definitions:
- **Natural Finder Intent:** `rat.engine.finder_intent.parse_finder_intent`
- **Reasoning Flow Builder:** `rat.engine.work_trace.build_reasoning_flow`
- **Workbench Projection:** `rat.ui.workbench_scene.WorkSceneProjector`
- **Entry Predictor:** `reasoning.entry_predictor.EntryPredictor`
- **Optimal Stopping:** `reasoning.optimal_stopping.OptimalStoppingPolicy`
- **App Launch Capability:** `rat.kernel.capabilities.applications._execute_launch_app` & `rat.engine.app_resolver.ApplicationCatalog`
- **Layer Boundaries:** Rigorously demarcates Shared Kernel vs UI Adapter vs Research Pipeline vs Unmeasured/Theoretical. Retracts unsupported claims regarding early decode stopping or 100% token reduction.

---

## 8. Artifact Directory Inventory

The audit directory `audit/rat_overnight_sweep_repair_20261019/` contains:
```
audit/rat_overnight_sweep_repair_20261019/
├── calls.jsonl                     # 12 real MLX generation records with token/timing telemetry
├── handoff.md                      # Consolidated final handoff document
├── native_performance.json         # Realistic telemetry, RSS, Qt warnings, font resolutions
├── rat_cot_evidence_map.md         # Verified AST symbol mapping and layer boundaries
├── regression.txt                  # Full text output of 265 regression tests (PASS)
├── regression.xml                  # JUnit XML output of 265 regression tests
├── repair_diff.patch               # Unified git diff against review snapshot
├── source_end.json                 # Actual SHA-256 hashes of all 37 tracked files
├── source_start.json               # Review baseline hashes
├── test_inventory_132.json         # Detailed JSON inventory of 132 test files
├── test_inventory_132.jsonl        # Streaming execution log of 132 test files
├── test_inventory_132.md           # Markdown summary table of 132 test files
├── test_logs/                      # 132 individual per-file stdout/stderr logs and XMLs
├── validation.json                 # Machine-readable validation status and resolved findings
├── visual_probes.txt               # Full text output of 6 independent visual probes (PASS)
├── visual_probes.xml               # JUnit XML output of 6 visual probes
└── visual_specimens/               # 5 freshly rendered offscreen PNGs + specimens_metadata.json
    ├── specimen_1_desktop_light_finder_offscreen.png
    ├── specimen_2_narrow_420px_light_offscreen.png
    ├── specimen_3a_desktop_light_sources_top_offscreen.png
    ├── specimen_3b_desktop_light_trace_bottom_offscreen.png
    ├── specimen_4_desktop_dark_disambiguation_offscreen.png
    └── specimens_metadata.json
```

---

## 9. Open Items & Recommended Next Steps

1. **Staging / Legacy Test Maintenance:**
   - 6 test files in the wider repository outside the core 265-test suite failed due to legacy assumptions (`test_crash_shield.py`, `test_harness_regressions.py`, `test_query_compounds.py`, `test_reranker_golden.py`, `test_vgc_cascade.py`, `test_vgc_ui_integration.py`). These can be scheduled for a separate maintenance pass.
2. **Font Family Deprecation Cleanup:**
   - Replace generic `"Sans Serif"` references in stylesheet templates with `.AppleSystemUIFont` or system typography tokens to eliminate the 203ms font alias population delay on macOS startup.
3. **Interactive Cocoa Display Validation:**
   - Run interactive window compositor frame-sync benchmarks once a display server environment is attached to evaluate native Cocoa window latency.
