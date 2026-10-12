# Audit Report: RAT Interaction Kernel Implementation

**Author:** Gemini (Advanced Agentic Assistant)  
**Date:** 2026-10-11 21:15:00 +07:00  
**Target Reviewer:** Codex  
**Repository:** `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`  
**Primary Reference:** `docs/adr-001-rat-interaction-kernel.md`  

---

## 1. Scope, Git Status & Non-Interference Confirmation

### 1.1 Implementation Intent
Implements **Option 2** (Shared capability/operation contracts, input requests, versioned artifacts, actions, truthful execution state, and standard declarative presentation) while establishing clean architectural boundaries preparing for **Option 3** (declarative view contracts, swappable view providers without arbitrary code execution).
Per project rules and ADR-001:
- Zero forced standalone feature windows for migrated capabilities inside RAT assistant.
- Conversational birth requests and navigation enter the same shared interaction kernel workflow inline.
- Preserved research integrity, headless test harnesses, and model gate semantics.

### 1.2 Git Integrity Confirmation
- **No Git destruction:** No `git reset`, `git clean`, `git checkout --`, `git stash`, `git push`, or `git commit` commands were executed.
- **Untracked work preserved:** All pre-existing untracked files (audit logs, data files, scripts, research experiments) remain strictly intact.
- **Research pipeline untouched:** `experiments/research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`, and Stage 0 gate definitions were unaffected by this UI/runtime change.

### 1.3 Modified and Created Files
#### New Modules Created:
1. `rat/astrology/export.py`: Headless SVG, PNG, and PDF chart export without instantiating `QMainWindow`.
2. `rat/kernel/__init__.py`: Package export for interaction kernel.
3. `rat/kernel/contracts.py`: Headless definitions for `InputRequest`, `Artifact`, `ArtifactStore`, `ArtifactAction`, `DispatchResult`, `ExecutionEvent`, `ExecutionState` (zero Qt dependencies).
4. `rat/kernel/registry.py`: `CapabilityRegistry`, `OperationDefinition`, `Capability` with dynamic native tool definition exporter (`registry.to_tool_definitions()`).
5. `rat/kernel/dispatcher.py`: `ActionDispatcher` with stale revision detection (`StaleRevisionError`) and ambiguous reference resolution (`AmbiguousArtifactReferenceError`).
6. `rat/kernel/view_spec.py`: Declarative `ViewBlock`, `ViewSpec`, `StandardViewProvider`, and strict `validate_view_spec` validator.
7. `rat/kernel/capabilities/__init__.py`: `build_default_registry()` bundling all default capabilities.
8. `rat/kernel/capabilities/natal.py`: Birth place search, chart calculation with `InputRequest` generation, birth data updates, and export.
9. `rat/kernel/capabilities/timetable.py`: Schedule lookup, room location, and group availability operations.
10. `rat/kernel/capabilities/documents.py`: Document search and text reading (distinguishing finding from reading).
11. `rat/ui/view_renderer.py`: `QtViewRenderer` for rendering declarative `ViewSpec` into native RAT widgets with warm paper/gold palette.
12. `tests/test_interaction_kernel.py`: Comprehensive test suite verifying all 9 acceptance scenarios.
13. `audit/rat_interaction_kernel_gemini_20261011_211500/REPORT_FOR_CODEX.md`: This audit report.

#### Existing Modules Refactored:
1. `rat/astrology/chart.py`: Preserved pure deterministic calculation.
2. `rat/ui/natal_chart.py`: Delegated `export_to` to `rat.astrology.export.export_chart`.
3. `rat/engine/assistant_runtime.py`: Integrated `CapabilityRegistry`, `ArtifactStore`, and `ActionDispatcher`. Tool definitions and executions derive from registered operations; artifacts are versioned and stored; execution events and pending input requests are preserved.
4. `rat/ui/assistant_presenter.py`: Updated `source_panel` to render artifacts via `QtViewRenderer` and wire inline actions and inputs.
5. `rat/ui/omnibar.py`: Replaced standalone `NatalChartWindow` popup in `open_natal_chart` with inline `InputRequest` artifact creation within section 0 (Home chat); hooked `_on_action_dispatched` and `_on_input_submitted`.
6. `tests/test_omnibar.py`: Updated `test_natal_navigation_can_be_opened_twice_and_reset_clears_task_state` to verify inline workflow without standalone QMainWindow.
7. `docs/adr-001-rat-interaction-kernel.md`: Updated status to Implemented for Option 2 and added implementation documentation.
8. `docs/natal_chart.md`: Clarified inline assistant workflow versus standalone CLI viewer.

---

## 2. Architecture & Contracts

### 2.1 Headless Kernel Layer (`rat.kernel`)
- **Strict Isolation:** `rat.kernel` has zero imports of PyQt6, PySide, or Qt widgets. Importing `rat.kernel` leaves `sys.modules` free of Qt.
- **InputRequest:**
  ```python
  @dataclass
  class InputRequest:
      operation_name: str
      supplied_inputs: Dict[str, Any]
      missing_fields: List[Dict[str, Any]]
      candidate_choices: Optional[List[Dict[str, Any]]] = None
      target_artifact_id: Optional[str] = None
      status: str = "needs_input"  # needs_input, cancelled, resolved
  ```
  Enables resuming pending operations directly via UI controls or natural language without central keyword routers.
- **Artifact & ArtifactStore:**
  Stable UUIDs (`art-<kind>-<timestamp>`), incrementing revisions, payload, inputs, and provenance. `ArtifactStore` maintains prior revisions and allows fast lookup and rollback without a heavyweight database.
- **ArtifactAction & ActionDispatcher:**
  Actions (`action_name`, `target_artifact_id`, `target_revision`, `params`) execute through the dispatcher. If `target_revision` does not match the store's current revision, a `StaleRevisionError` is raised. If a user request refers to an ambiguous artifact kind where multiple candidates exist, `AmbiguousArtifactReferenceError` forces clarification.
- **CapabilityRegistry:**
  Decouples operations from monolithic `assistant_runtime.py` if-else branches. Native tool schemas are generated dynamically via `to_tool_definitions()`.

### 2.2 Declarative Presentation Layer (`ViewSpec` & `QtViewRenderer`)
- **ViewSpec (Schema Version 1):**
  Pure data structure specifying view layout:
  - `header`, `summary`: Key titles and status highlights.
  - `block_types`: `"text"`, `"table"`, `"wheel"`, `"input_fields"`, `"action_buttons"`, `"details"`.
- **Validation (`validate_view_spec`):**
  Rejects unknown schema versions, unknown block types, invalid field references, and invented actions. Prevents invalid presentation specs from corrupting artifacts or disguising runtime failures.
- **ViewProvider Seam (Option 3 Preparation):**
  `StandardViewProvider` generates `ViewSpec` deterministically from artifacts. Swapping the provider requires zero changes to the underlying artifacts, dispatcher, or registered operations.
- **QtViewRenderer:**
  Maps `ViewSpec` blocks into RAT native widgets conforming to the RAT design system (warm cream `#FDFBF7`, deep bronze `#2B2620`, subtle borders `#E6E1DA`, accent `#D97706`). Embeds `ChartCanvas` for astrological wheels without instantiating `NatalChartWindow`.

### 2.3 Headless Export Factorization (`rat.astrology.export`)
- Factored chart export from `NatalChartWindow` into a headless function:
  ```python
  export_chart(chart: Dict[str, Any], path: Union[str, Path], fmt: str = "svg", **kwargs) -> bool
  ```
  Supports SVG, PNG, and PDF rendering using Qt's offscreen painting without requiring a GUI window or active event loop.

---

## 3. Scenario-by-Scenario Acceptance Matrix

| Scenario | Requirement | Implementation & Verification | Result |
| :--- | :--- | :--- | :--- |
| **Scenario 1** | Partial natal request without birth data returns `InputRequest`; candidate place ambiguity handled; complete data yields inline chart artifact. | `rat/kernel/capabilities/natal.py` generates `InputRequest` with missing fields and candidate choices. Verified in `test_scenario_1_partial_natal_request_and_inline_completion`. | **PASSED** |
| **Scenario 2** | Birth time modification ("đổi giờ sinh thành 9:30") recalculates chart, increments revision to 2, preserves history, detects stale revisions. | Dispatcher executes `update_birth_data` on artifact; revision increments from 1 to 2; dispatching with stale revision 1 raises `StaleRevisionError`. Verified in `test_scenario_2_birth_time_modification_and_stale_detection`. | **PASSED** |
| **Scenario 3** | Schedule & Document operations produce versioned artifacts with truthful execution status; finding is distinguished from reading. | `search_documents` produces `document_search` artifact; `read_document` produces `document_content` artifact with actual content. Verified in `test_scenario_3_schedule_and_documents_produce_artifacts_with_truthful_status`. | **PASSED** |
| **Scenario 4** | Composed multi-step request (schedule + search + read) executes cleanly via dispatcher and runtime without hardcoded pipeline. | Simulated model decision sequence executing 3 distinct operations produces 3 versioned artifacts and truthful observed sources. Verified in `test_scenario_4_composed_multi_step_request_plumbing`. | **PASSED** |
| **Scenario 5** | Multiple candidate charts with ambiguous reference require clarification; prevents silent overwrite. | `resolve_target_artifact` detects multiple `natal_chart` artifacts and raises `AmbiguousArtifactReferenceError`. Verified in `test_scenario_5_ambiguous_chart_reference_prevents_silent_modification`. | **PASSED** |
| **Scenario 6** | Extensibility: New capability registered dynamically without touching central `assistant_runtime.py` branches. | Registered `mock_weather` capability into `CapabilityRegistry`. Dynamic tool definition and execution verified in `test_scenario_6_register_test_capability_without_central_branch_changes`. | **PASSED** |
| **Scenario 7** | ViewProvider swapping & ViewSpec validation: Rejects unknown schema versions, invalid blocks, and invented actions. | Swapped to `CompactViewProvider`; verified `validate_view_spec` errors on invalid blocks and version 99. Verified in `test_scenario_7_view_provider_swapping_and_spec_validation`. | **PASSED** |
| **Scenario 8** | Cancellation, reset, and safety against delayed callbacks. | Resetting runtime clears artifacts and pending input requests; cancelled requests do not leak. Verified in `test_scenario_8_cancellation_reset_and_delayed_callbacks_safety`. | **PASSED** |
| **Scenario 9** | Headless isolation: `rat.kernel` contracts independent of Qt. | Subprocess execution verifies `import rat.kernel` leaves `PyQt6` absent from `sys.modules`. Verified in `test_scenario_9_headless_contracts_independent_of_qt`. | **PASSED** |

---

## 4. Verification Evidence & Test Executions

### 4.1 Acceptance Test Suite (`tests/test_interaction_kernel.py`)
```bash
python3.12 -m pytest tests/test_interaction_kernel.py -v
```
**Output:**
```
============================= test session starts ==============================
platform darwin -- Python 3.12.6, pytest-9.0.3, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: /Users/thundercock2/Documents/Github/multi-step-structured-reasoning
plugins: anyio-4.12.1, timeout-2.4.0
collected 9 items

tests/test_interaction_kernel.py::test_scenario_9_headless_contracts_independent_of_qt PASSED [ 11%]
tests/test_interaction_kernel.py::test_scenario_1_partial_natal_request_and_inline_completion PASSED [ 22%]
tests/test_interaction_kernel.py::test_scenario_2_birth_time_modification_and_stale_detection PASSED [ 33%]
tests/test_interaction_kernel.py::test_scenario_3_schedule_and_documents_produce_artifacts_with_truthful_status PASSED [ 44%]
tests/test_interaction_kernel.py::test_scenario_4_composed_multi_step_request_plumbing PASSED [ 55%]
tests/test_interaction_kernel.py::test_scenario_5_ambiguous_chart_reference_prevents_silent_modification PASSED [ 66%]
tests/test_interaction_kernel.py::test_scenario_6_register_test_capability_without_central_branch_changes PASSED [ 77%]
tests/test_interaction_kernel.py::test_scenario_7_view_provider_swapping_and_spec_validation PASSED [ 88%]
tests/test_interaction_kernel.py::test_scenario_8_cancellation_reset_and_delayed_callbacks_safety PASSED [100%]

============================== 9 passed in 5.59s ===============================
```

### 4.2 Full UI & Runtime Regression Suite
```bash
QT_QPA_PLATFORM=offscreen python3.12 -m pytest tests/test_omnibar.py tests/test_natal_chart_ui.py tests/test_timetable_chat_cards.py tests/test_assistant_runtime.py tests/test_assistant_worker.py tests/test_rat_task_memory.py tests/test_rat_chat_session.py tests/test_slm_chat.py tests/test_natal_chart.py tests/test_natal_places.py -q
```
**Output:**
```
143 passed, 1 warning, 3 subtests passed in 83.15s
```

### 4.3 Research Pipeline Integrity Suite
```bash
python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```
**Output:**
```
.............................                                            [100%]
29 passed in 17.57s
```

---

## 5. Explicit Disclaimers and Non-Claims

1. **Software Verification vs. AI Reasoning Quality:**
   Passing software and unit tests demonstrate that contracts, dispatchers, validation schemas, and UI rendering function deterministically as designed. They do **not** constitute evidence of real SLM reasoning accuracy, zero tool hallucination, or robust semantic dialogue understanding in open-ended conversations.
2. **Stage 0 Research Gate:**
   The Stage 0 gate for the Qwen/Meta-Reasoner campaign is preserved and was not touched or claimed to have passed.
3. **Option 3 Boundaries Maintained:**
   Option 3 capabilities—such as AI-generated executable component code, runtime sandboxing, model-synthesized declarative view generation, and dynamic remote plugin loading—are intentionally **not** implemented in this phase. The architecture provides clean seams (swappable `ViewProvider`, declarative `ViewSpec`, decoupled `CapabilityRegistry`) for those future evolutions.

---

## 6. Dependencies, Known Limits & Risks

1. **Optional Swiss Ephemeris:**
   `pyswisseph` is an optional astrology dependency listed in `requirements-astrology.txt`. If absent, astrology tests gracefully skip or handle lack of ephemeris files.
2. **Geocoding Network Dependency:**
   Live geocoding queries Open-Meteo/GeoNames. If the network is unreachable, fallback to preset coordinates or manual user input is preserved.
3. **Model Prompting & Live Tool Choice:**
   In live local model runs (e.g. Qwen 3.5), tool selection quality depends on model prompt formatting. The interaction kernel accepts both natural language model tool calls and direct UI user actions through the exact same dispatcher.

---

## 7. Inspection Guide for Codex & Maintainers

To inspect or verify the kernel:

1. **Run Headless Contract & Acceptance Tests:**
   ```bash
   python3.12 -m pytest tests/test_interaction_kernel.py -v
   ```
2. **Verify Headless Isolation Directly in Python:**
   ```bash
   python3.12 -c "import sys; import rat.kernel; assert 'PyQt6' not in sys.modules; print('Clean headless isolation verified!')"
   ```
3. **Verify Omnibar and UI Offscreen:**
   ```bash
   QT_QPA_PLATFORM=offscreen python3.12 -m pytest tests/test_omnibar.py -k test_natal_navigation_can_be_opened_twice_and_reset_clears_task_state -v
   ```
4. **Verify Research Harness Intact:**
   ```bash
   python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
   ```
