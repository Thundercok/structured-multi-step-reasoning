# B2 Preparation: Accurate Model-Call Boundary Mapping & Architectural Plan

**Status:** Documentation Only — Ready for Codex Review  
**Target Module:** `rat/engine/assistant_runtime.py` & `rat/engine/runtime_context.py`  
**Context:** Prepared for transition to Package B2 following B1 acceptance  

---

## 1. Executive Summary & Canonical Architecture

In Package B2, the runtime execution loop in `AssistantRuntime.run()` uses `collect_runtime_context` to compile coherent, validated `ContextSnapshot` views immediately prior to invoking the model, replacing ad-hoc dictionary passing with schema-validated, typed context projections.

### Core Architectural Invariants:
1. **Zero Runtime State Store Overhaul:** No separate transactional coordinator, runtime truth store, or caching layer is introduced. The existing `ArtifactStore`, `ExecutionJournal`, and `WorkNotebook` remain the sole sources of truth.
2. **Deterministic Functional Compilation:** `compile_context_snapshot` remains a pure functional compiler operating on deep copies of runtime state.
3. **No Cross-Store Transaction Claims:** Artifact writes, notebook operations, and journal receipts remain isolated native operations.
4. **Honest Failure Reporting (No Fallback Views):** If state changes concurrently during context assembly, the runtime attempts up to 3 captures (1 initial attempt + at most 2 recopies). If coherence cannot be established, or if validation fails, the runtime raises `ContextBuildError("context_build_failed:...")` honestly. It **never** manufactures an unvalidated "minimal fallback view" or silently drops obligations.
5. **Preserve Native Assistant & Tool Call Constraints:**
   - Real model calls remain gated by `live_model_disabled` during testing/research.
   - Token and step budgets (`max_tokens`, `max_steps`, `total_prompt`, `total_completion`) are strictly enforced.
   - Cooperative cancellation and reset (`should_cancel`, `conversation_reset`).
   - Pending user inputs (`waiting_input` / `needs_input` lifecycle).
   - Contract lifecycle and freeze (`turn_contract.frozen`, `decision_contract`).
   - Queued tools (`pending_calls.extend(decision.extra_tool_calls)`).
   - Finish-only protocol (`finish_only=True` forcing synthesis without tools).
   - Injected fixture / mock protocols (`initial_decision`, `model_callable`).

---

## 2. Actual Model-Call Boundaries in Current Runtime

In current `rat/engine/assistant_runtime.py`, there are **two distinct model-call invocations**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AssistantRuntime.run(goal, ...)                        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                  [plan_tasks and no initial_steps/decision?]
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼ YES                               ▼ NO
       ┌───────────────────────────┐                     │
       │   Boundary A: Planner     │                     │
       │   self._plan_task(goal)   │                     │
       │   builder('planner')      │                     │
       └─────────────┬─────────────┘                     │
                     │ (produces task_state / outcomes)  │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   Main Step Loop (1..max)     │
                       └───────────────┬───────────────┘
                                       │
                          [pending_calls queued?]
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼ YES                               ▼ NO
       ┌───────────────────────────┐       ┌───────────────────────────┐
       │ Bypass model invocation   │       │   Boundary B: Step Model  │
       │ pop next tool call        │       │   self._call_model(...)   │
       └───────────────────────────┘       │   builder('actor'|...)    │
                                           └───────────────────────────┘
```

### Boundary A: Native Planner Boundary (`_plan_task`)
- **Runtime Location:** `rat/engine/assistant_runtime.py:1020-1065`.
- **View Target:** `view="planner"`.
- **Context Builder Invocation:**
  ```python
  builder = context.get('context_builder')
  if builder:
      user_payload = builder('planner')
  ```
- **Context Provided:**
  - `query`: The current user goal.
  - `prior_state`: Active task state.
  - `active_notes`: Validated active notes from notebook.
  - `turn_references`: Recent turn continuity summaries.
  - `source_metadata`: Observed source metadata from previous turns.
- **Model Output & Ingress:**
  - Constrained by `_planning_schema()`.
  - Ingress validates the proposal structure and populates initial `task_state` and/or `turn_contract.outcomes`.
  - Context build failures halt the turn immediately:
    ```python
    except ContextBuildError as exc:
        return response(error=str(exc))
    ```

### Boundary B: Step Model Execution Boundary (`_call_model`)
- **Runtime Location:** `rat/engine/assistant_runtime.py:560-615` (called from step loop at line 1122).
- **View Target Selection:**
  ```python
  view = "repair" if context.get("answer_schema") else "finish" if context.get("finish_only") else "actor"
  context["context_snapshot"] = builder(view)
  ```
  1. `view="actor"`: Standard action selection step (pre-first-effect or post-action continuation).
  2. `view="finish"`: Budget-exhaustion step where `finish_only=True`; model must formulate final response using observed context without further tools.
  3. `view="repair"`: Scoped verification failure step where `answer_schema` is present; model must correct candidate answer based strictly on verified feedback.
- **Model Output & Ingress:**
  - Produces `ModelDecision`.
  - If tool call: verified and dispatched to `self.dispatcher`.
  - If final answer: checked by `verification.check_answer` and evaluated against `turn_contract` before terminal acceptance.

---

## 3. Coherent Sampling in Current Source & The B2 Copied-Vector Gap

### Current Implementation in `rat/engine/runtime_context.py`
The current `collect_runtime_context` function uses three live-state checks:

```python
def boundary():
    ctx = notebook.current_context()
    pending = dispatcher.state.pending_input_request
    return (
        notebook.generation, notebook.event_cursor(),
        ctx.turn_ref.to_dict() if ctx else None,
        ctx.execution_id if ctx else None,
        bool(notebook.selection_set), tuple(notebook.result_ids()),
        store.generation, tuple((a.id, a.revision) for a in store.list()),
        pending.to_dict() if pending else None,
    )

for _ in range(3):
    before = boundary()       # Sample 1: Live store state prior to copying
    ...                       # Deep-copies notes, artifacts, journal, contract, task
    after = boundary()        # Sample 2: Live store state immediately after copying
    if before != after:
        continue
    snapshot = compile_context_snapshot(...)
    valid, errors = validate_context_snapshot(snapshot)
    if not valid:
        raise ContextBuildError(...)
    if boundary() == before:  # Sample 3: Live store state after compilation/validation
        return snapshot
raise ContextBuildError("context_build_failed:concurrent_change")
```

### Clarification of the B2 Implementation Gap
It is critical to distinguish between live-state checks and true copied-bundle validation:
- **What is currently implemented:** `runtime_context.py` samples live store state three times (`before`, `after`, and the post-validation check).
- **What is NOT yet implemented:** The second sample (`after`) is **not** a vector derived from the captured bundle / deep-copied objects; it is simply a second live call to `boundary()`.
- **The Protocol Gap:** The idealized Three-Point Verification Protocol `pre_vector == copied_vector == post_vector` requires that `copied_vector` be computed strictly from the deep-copied data structures (evaluating the copied notebook generation/cursor, copied artifact store list, copied journal execution ID, etc.) rather than querying the live singletons again.
- **B2 Work Item:** Implementing a true `copied_vector` derived directly from the copied bundle, along with full contract binding and copied content checks, remains an explicit B2 acceptance item under ADR-004 and Package B decisions.

---

## 4. B2 Integration Verification Plan

When B2 implementation begins, the following verification gates must be satisfied:
1. **True Copied-Vector Derivation:** Implement a function that calculates the boundary coordinate vector directly from the deep-copied objects in memory, ensuring that `copied_vector` reflects the actual contents passed to `compile_context_snapshot`.
2. **Context Build Error Transparency:** Simulate concurrent store mutation; assert that `AssistantRuntime` cleanly returns `error="context_build_failed:concurrent_change"` without crashing or executing a partial view.
3. **Dual-Boundary Capture:** Verify that `_plan_task` and `_call_model` both record their respective `context_boundary` in `step.context_boundary`.
4. **Budget and Cancellation Guarantees:** Verify that token accounting, step counts, and cooperative cancellation remain 100% faithful to existing contracts.
5. **Regressions Green:** All 166 focused tests and full core suite continue passing.
