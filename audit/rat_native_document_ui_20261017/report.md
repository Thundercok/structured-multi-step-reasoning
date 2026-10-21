# Native Document Q&A & Finder Keyboard Integration Report (2026-10-17)

## Executive Summary
This milestone completes the 3-phase revision requested by the user:
- **Part A (Keyboard Defects)**: Addressed 4 keyboard/selection bugs in finder and composer. Verified with 18 tests (12 original probes + 6 follow-up regression cases).
- **Part B (Native Document Q&A Wiring)**: Connected the existing resident MLX document engine directly into the unified UI (`OmnibarWindow`, `AssistantWorker`, and `SettingsDialog`), providing non-blocking model preload via `Future`, token streaming via `on_text`/`text_streamed`, strict error reporting without silent Ollama/cloud fallback, and clean thread/runtime shutdown.
- **Part C (Offline Live Verification & Artifacts)**: Ran a 100% offline live UI session with `mlx-community/Qwen3.5-4B-MLX-4bit` across 5 generations on a synthetic document in a temporary SQLite database, verifying first question, followup with cached prefix, fresh disk read after file update, mid-stream cancellation, and re-asking after cancellation. Recorded wall-clock timings, process RSS, Metal allocations, and UI specimens.

---

## Part A: Finder Keyboard Follow-ups

### Issues Resolved:
1. **Enter / Space on Action Buttons**: In `rat/ui/omnibar.py` (`OmnibarInputFilter.eventFilter`), intercepted `Return`, `Enter`, and `Space` when focus is on a `QPushButton` (e.g. `btn_ask`) to explicitly call `watched.click()` and consume the event (`return True`), preventing it from bubbling to the parent row's `open_file_default`.
2. **Tab & Row Focus Sync**: Installed `OmnibarInputFilter` on finder rows and action buttons; captured `QEvent.Type.FocusIn` to immediately sync `selected_resource_id` and `window._finder_selected_id`. Keyboard shortcuts (Cmd+Enter, Alt+Enter) now resolve targets from the currently focused row.
3. **Shift+Down Native Selection**: Tightened modifier checks in `OmnibarInputFilter` so that `Shift+Down` / `Shift+Up` bypass the finder boundary check and delegate directly to `super().eventFilter(...)`, preserving native multi-line text selection in `ChatComposer`.
4. **Snapshot Re-render Row Reconciliation**: In `FinderSuggestionsWidget.set_snapshot` (`rat/ui/workbench_scene.py`), replaced total widget recreation (`deleteLater()`) with in-place row reconciliation keyed by `resource_id`. Preserves the focused row, active button role, and scroll position across progressive FTS/lexical updates.

### Test Evidence:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  audit/rat_finder_codex_review_20261016/test_finder_integration_probes.py \
  audit/rat_finder_codex_review_r2_20261017/test_keyboard_followups.py \
  --junitxml=audit/rat_finder_codex_review_r2_20261017/tests_keyboard.xml -v
```
**Result: 18 passed in 8.33s.**

---

## Part B: Native Document Q&A UI Wiring

### Components Connected:
1. **Settings Controls (`rat/ui/settings_dialog.py`)**: Added native document model settings group with folder picker for local MLX directory (`config.document_model_path`) and preload toggle (`config.document_model_preload`), respecting environment overrides.
2. **Runtime Ownership & Preload (`rat/ui/omnibar.py`)**:
   - Initialized `AssistantRuntime` with `document_model_path`. If path is invalid or missing, wraps it in `ErrorDocumentModel` to prevent silent fallback to Ollama or cloud providers.
   - Non-blocking startup preload via `runtime.preload_document_model()`, delivering status signals to GUI via queued `_NativeModelSignalBridge`.
3. **Streaming & Worker Integration (`rat/ui/assistant_worker.py`)**:
   - Added `text_streamed = pyqtSignal(str)` on `AssistantWorker` and connected `on_text=self.text_streamed.emit` to `answer_selected_document`.
   - Wired into `OmnibarWindow._on_assistant_text_streamed` with generation and handle ownership checks. Late or stale chunks from cancelled turns are discarded.
4. **Safe Shutdown Handshake**:
   - Replaced blocking `wait(31000)` with `wait(2000)` and asynchronous worker release.
   - Off-thread runtime closure prevents GUI freeze while awaiting native resource cleanup.

### Test Evidence:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_document_model_startup.py \
  tests/test_mlx_document_session.py \
  tests/test_selected_document_qa.py \
  tests/test_assistant_runtime.py \
  tests/test_rat_headless_cli.py \
  tests/test_selected_document_ui.py \
  --junitxml=audit/rat_native_document_ui_20261017/tests_native_qa.xml -v
```
**Result: 96 passed in 9.09s.**

---

## Full Regression Suite

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py \
  tests/test_work_context_ui.py tests/test_rat_chat_session.py \
  tests/test_rat_verification_ui.py tests/test_work_context.py \
  tests/test_omnibar.py tests/test_workbench_scene.py \
  tests/test_progressive_search.py \
  audit/rat_workbench_flash_review_20261016/test_live_detail_probe.py -v
```
**Result: 172 passed, 3 subtests passed in 44.95s.**

---

## Part C: Live Offline UI Session

### Session Configuration:
- **Model**: `mlx-community/Qwen3.5-4B-MLX-4bit` (snapshot `32f3e8ecf65426fc3306969496342d504bfa13f3`)
- **Runtime Environment**: macOS Darwin 25.5.0 (Apple Silicon arm64), PyQt6 6.8.1 (QPA: `cocoa`), Python 3.12.6, MLX 0.32.2, MLX LM 0.31.3.
- **Offline Enforcement**: `sys.addaudithook` blocking all socket connections; verified **0 network attempts**.
- **Ollama Isolation**: Ollama service explicitly blocked (`is_service_running=False`); 100% native execution.
- **Data Isolation**: Synthetic document `huong_dan_hoc_vu_2026.txt` in a temporary SQLite database. Zero access to personal files or directories.

### Measured Results:
- **Startup Preload Duration**: 29.42 s (loaded weights & tokenizer into Metal)
- **Initial Process RSS**: 29.66 MB -> **Post-Preload RSS**: 1149.06 MB
- **Metal Memory**: Active 2257.85 MB, Peak 2838.47 MB

| Generation | Action / Question | UI First Token Wall Time | UI Done Wall Time | Answer Summary | Status |
|---|---|---:|---:|---|---|
| 1 | First question on selected file | 28.19 s | 35.67 s | `Mã xác nhận bảo lưu chính thức là BL-8842-X.` | Success |
| 2 | Follow-up question (cached prefix) | 2.13 s | 5.42 s | `Phòng tiếp nhận hồ sơ là Văn phòng Đào tạo B203.` | Success |
| 3 | File edited on disk (fresh read check) | 9.24 s | 12.65 s | `Phòng tiếp nhận hồ sơ mới sau khi chuyển đổi là Hội trường C501.` | Success |
| 4 | Mid-stream cancellation | 2.80 s | 3.58 s | Cancelled after 2 stream chunks | Cancelled |
| 5 | Re-ask after cancel | 1.93 s | 6.47 s | `Thời hạn nộp đơn xin bảo lưu là trước ngày 15 tháng 11 năm 2026.` | Success |

- **Shutdown Handshake**: Completed in 0.54 s. Final Metal active memory cleanly freed to 0.00 MB.

### UI Specimens Recorded:
- `native_qa_gen1.png` (Gen 1 complete state)
- `native_qa_gen2.png` (Followup complete state)
- `native_qa_gen3.png` (Post-edit complete state with updated room)
- `native_qa_gen4.png` (Cancelled mid-stream state)
- `native_qa_gen5.png` (Re-ask after cancel complete state)
- `native_qa_desktop.png` (Standard desktop 652x810)
- `native_qa_narrow.png` (Narrow responsive 420x810)
- `native_qa_dark.png` (Dark theme 620x810)

### Artifact Locations:
- Session Manifest: `audit/rat_native_document_ui_20261017/native_qa_session.json`
- JUnit XML A: `audit/rat_finder_codex_review_r2_20261017/tests_keyboard.xml`
- JUnit XML B: `audit/rat_native_document_ui_20261017/tests_native_qa.xml`
- Workbench Scene Specimen Manifest: `docs/evidence/rat_workbench_native/native_scene_session.json`

---

## Boundaries & Constraints
- Only selected-document Q&A runs via native MLX; the general agent CoT, app launching, semantic embedding providers, and Stage 0 research benchmarks remain unchanged.
- Native document model requires an explicit local directory path; no auto-downloading or auto-enabling was introduced.
- Native IME composition remains pending direct user hardware testing (simulated programmatic events do not establish physical IME behavior).
