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

Contrary to obsolete documentation describing a single physical model boundary, current `rat/engine/assistant_runtime.py` exhibits **two distinct model-call invocations**:

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

## 3. Coherent Sampling & Recopy Protocol (`runtime_context.py`)

`rat/engine/runtime_context.py` implements the exact sampling and recopy protocol required by ADR-004 and Package B decisions:

### Boundary Vector Definition
A boundary vector captures the complete version and structural coordinate state across all stores:
```python
def boundary():
    ctx = notebook.current_context()
    pending = dispatcher.state.pending_input_request
    return (
        notebook.generation,                                    # 0: notebook generation
        notebook.event_cursor(),                                # 1: event sequence
        ctx.turn_ref.to_dict() if ctx else None,                # 2: turn reference
        ctx.execution_id if ctx else None,                      # 3: execution ID
        bool(notebook.selection_set),                           # 4: selection flag
        tuple(notebook.result_ids()),                           # 5: selected artifact IDs
        store.generation,                                       # 6: artifact store generation
        tuple((a.id, a.revision) for a in store.list()),        # 7: artifact (id, rev) tuple
        pending.to_dict() if pending else None,                 # 8: pending input state
    )
```

### The Three-Point Verification Protocol: `pre_vector == copied_vector == post_vector`
To guarantee that no concurrent mutation occurred while data was being copied:
1. **Pre-Vector (`before`):** Sampled immediately prior to reading stores.
2. **Execution Sanity Check:** Verifies that `conversation_id`, `turn_id`, `execution_id`, and `generation` match the active journal. If not, raises `ContextBuildError("context_build_failed:execution_changed")`.
3. **Copied Vector (`after`):** Sampled immediately after copying artifacts, notes, history, events, journal, contract, and task state.
   - If `before != after`: The state changed during copying. The loop retries with a fresh copy.
4. **Post-Vector (`post`):** Sampled immediately after compiling and validating the `ContextSnapshot`:
   - Checks `boundary() == before`.
   - If identical, the compiled snapshot is returned.
   - If mutated, the loop retries.

### Recopy Bounds (At Most Two Recopies)
The loop executes for at most 3 iterations:
```python
for _ in range(3):
    ...
```
- Iteration 1: Initial capture attempt.
- Iteration 2: First recopy attempt upon concurrent boundary change.
- Iteration 3: Second recopy attempt upon concurrent boundary change.
- If all 3 attempts fail due to concurrent change:
  ```python
  raise ContextBuildError("context_build_failed:concurrent_change")
  ```

### Explicit Unavailable References (No Invented Entities)
When referenced artifact revisions are no longer retained in `ArtifactStore`:
- The reference is explicitly recorded in `snapshot["unavailable_refs"]` with `reason="revision_no_longer_retained"` and `mandatory=False`.
- The compiler verifies pointer closure against `entities + unavailable_refs`.
- No mock artifact entities or fabricated payloads are generated.

---

## 4. B2 Integration Verification Plan

When B2 implementation begins, the following verification gates must be satisfied:
1. **Context Build Error Transparency:** Simulate concurrent store mutation; assert that `AssistantRuntime` cleanly returns `error="context_build_failed:concurrent_change"` without crashing or executing a partial view.
2. **Dual-Boundary Capture:** Verify that `_plan_task` and `_call_model` both record their respective `context_boundary` in `step.context_boundary`.
3. **Budget and Cancellation Guarantees:** Verify that token accounting, step counts, and cooperative cancellation remain 100% faithful to existing contracts.
4. **Regressions Green:** All 151 focused tests and full core suite continue passing.
