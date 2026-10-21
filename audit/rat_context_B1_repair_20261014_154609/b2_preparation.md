# B2 Preparation: Model-Call Boundary Mapping & Architectural Plan

**Status:** Documentation Only — No Runtime Wiring in B1 Turn  
**Target Module:** `rat/engine/assistant_runtime.py` (and interactions with `rat/engine/completion.py`, `rat/engine/context_snapshot.py`)  
**Context:** Gated upon Codex acceptance of B1 (`rat_context_B1_repair_20261014_154609`)  

---

## 1. Executive Summary & Architectural Scope

In step B2, the runtime execution loop in `AssistantRuntime.run()` will project canonical state into `ContextSnapshot` views immediately prior to invoking the model, replacing informal dictionary packing with schema-validated, typed context projections.

### Non-Negotiable Architectural Constraints:
1. **Zero Runtime State Store Overhaul:** Do not invent a new context store, transactional manager, or controller loop. The existing `ArtifactStore`, `ExecutionJournal`, and `WorkNotebook` remain the single source of truth.
2. **Deterministic Functional Compilation:** `compile_context_snapshot` remains a pure functional compiler operating on deep copies of runtime state.
3. **No Cross-Store Transaction Claims:** Artifact writes, notebook operations, and journal receipts remain isolated native operations.
4. **Preserve All Runtime Semantics:**
   - Token and step budgets (`max_tokens`, `max_steps`, `total_prompt`, `total_completion`).
   - Cooperative cancellation and reset (`should_cancel`, `conversation_reset`).
   - Pending user inputs (`waiting_input` lifecycle).
   - Contract lifecycle and freeze (`turn_contract.frozen`, `decision_contract`).
   - Queued tools (`pending_calls.extend(decision.extra_tool_calls)`).
   - Finish-only protocol (`finish_only=True` forcing synthesis without tools).
   - Injected fixture / mock protocols (`initial_decision`, `model_callable`).

---

## 2. Model-Call Boundary Mapping in Current Runtime

In the current runtime (`rat/engine/assistant_runtime.py`), model invocations occur at a single physical method `self._call_model(goal, trajectory, **context, finish_only=finish_only)` called inside the main step loop (line 957). However, semantically, execution transitions through four distinct boundary classes corresponding to `VALID_VIEWS`:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                      AssistantRuntime.run(goal, ...)                      │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                        [initial_decision present?]
                                ├───────────── YES ──> Bypass model call
                                │                      (Use fixture decision)
                                NO
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
       [finish_only=True?]               [repair iteration?]
              ├──── YES ──> "finish" view         ├──── YES ──> "repair" view
              NO                                  NO
              │                                   │
              └─────────────────┬─────────────────┘
                                ▼
                         "actor" view
              (pre-first-effect or post-action)
```

### Boundary Class 1: Actor Step — Pre-First-Effect
- **Runtime Location:** `rat/engine/assistant_runtime.py:939-958` (when `number == 1` and `initial_decision is None`).
- **View Target:** `view="actor"`.
- **Pre-Conditions:**
  - `active_turn_id` allocated; `active_exec_id` initialized.
  - `turn_contract.frozen == False`.
  - Journal has 0 action receipts.
  - ArtifactStore may contain historical artifacts or pre-seeded inputs.
- **Fresh Copied Inputs Vector:**
  - `boundary`: `ExecutionBoundary(conversation_id, turn_id, execution_id, generation=notes_generation)`
  - `artifact_store_items`: Deep copy of all active artifacts from `artifact_store.list()`.
  - `selected_artifact_ids`: Derived from current query / context focus.
  - `selection_set`: `False`.
  - `notebook_notes`: Deep copy of `notebook.list_notes()`.
  - `notebook_history`: Deep copy of previous turns' notes.
  - `recent_events`: Deep copy of `notebook.list_events()`.
  - `execution_journal`: Copy of empty/initial journal.
  - `turn_contract`: Copy of initial `TurnContract(intent_coverage="unchecked")`.
- **Post-Conditions & Effect:**
  - Model returns `ModelDecision` with either `final_answer`, `tool_name` + `tool_args`, or `extra_tool_calls`.
  - If contract unfrozen, `decision_contract(decision)` proposes turn contract.

### Boundary Class 2: Actor Step — Post-Action Continuation
- **Runtime Location:** `rat/engine/assistant_runtime.py:939-958` (when `number > 1`, `pending_calls` is empty, `finish_only == False`, and not in repair).
- **View Target:** `view="actor"`.
- **Pre-Conditions:**
  - Previous actions executed and recorded in `journal` with `ExecutionReceipt`s.
  - Any created notes/artifacts committed with monotonically incremented revisions.
  - `turn_contract` may be frozen or mutable.
- **Fresh Copied Inputs Vector:**
  - Same input vector as Boundary 1, but `execution_journal` contains all current turn receipts.
  - `artifact_store_items` reflects new revisions.
  - `notebook_notes` reflects note modifications.
  - `note_event_cursor` set to position after prior events.
- **Post-Conditions & Effect:**
  - Reconciler matches receipts against contract outcomes.
  - Model receives updated journal evidence without re-authorizing raw descendant pointers.

### Boundary Class 3: Verified Repair Loop
- **Runtime Location:** `rat/engine/assistant_runtime.py:996-1002` (after `verification.check_answer` yields `guard_action == "REPAIR"`).
- **View Target:** `view="repair"`.
- **Pre-Conditions:**
  - `decision.final_answer` was produced but failed verification checks.
  - `journal.record_verification(rep, candidate_answer=...)` appended verification receipt.
  - `verification_repairs < max_verification_repairs`.
  - `pending_calls` cleared.
  - `context['answer_schema']` updated from failed report.
- **Fresh Copied Inputs Vector:**
  - `view="repair"`.
  - `execution_journal`: Contains the candidate answer receipt and verification report receipt.
  - `unmodeled_observations`: Formatted verification feedback / repair instruction.
  - Contract remains frozen with `outcomes` tracking candidate status.
- **Post-Conditions & Effect:**
  - Model must produce an adjusted conclusion addressing the specific verification discrepancy.
  - Bound by `max_verification_repairs` (default 2); if exceeded, transitions to rejection.

### Boundary Class 4: Finish-Only Boundary
- **Runtime Location:** `rat/engine/assistant_runtime.py:947-949` (when `number == max_steps`) or line 1027 (duplicate action detected).
- **View Target:** `view="finish"`.
- **Pre-Conditions:**
  - `finish_only = True`.
  - `pending_calls.clear()`.
- **Fresh Copied Inputs Vector:**
  - `view="finish"`.
  - Complete journal, all notes, all artifacts.
  - Prompt/instruction explicitly restricts available tools to none, requiring textual synthesis from existing observations.
- **Post-Conditions & Effect:**
  - If model refuses finish and attempts tool call, runtime terminates with `controller_finish_refused`.
  - If model produces final answer, proceeds to verification.

---

## 3. Strict Pre/Copies/Post Vector Protocol

To prevent mutation leakage between the runtime loop and context projection, all context compilation will follow a 3-phase protocol:

```
[Phase 1: Pre-Check]
  - Check budgets: total_prompt + total_completion < max_tokens
  - Check cancel: not should_cancel()
  - Check pending input: if store has waiting_input, prompt input continuation rather than model step

[Phase 2: Deep-Copy Isolation]
  - raw_artifacts = [copy.deepcopy(a) for a in artifact_store.list()]
  - raw_notes = [copy.deepcopy(n) for n in notebook.list_notes()]
  - raw_journal = copy.deepcopy(execution_journal)
  - raw_contract = copy.deepcopy(turn_contract)

[Phase 3: Pure Compilation]
  - snapshot = compile_context_snapshot(view=view, ...)
  - (valid, errors) = validate_context_snapshot(snapshot)
  - if not valid: trigger failure path (Max 2 retries)

[Phase 4: Model Invocation]
  - Formulate messages according to native assistant/tool format
  - Invoke model
  - Update token budgets and trajectory
```

---

## 4. Retry Budget & Failure Paths

### Maximal 2 Retries Policy:
If context snapshot compilation or validation fails (`valid == False`):
1. **Retry 1 (Sanitization Retry):** Re-copy state with explicit `unavailable_refs` pruning broken links, re-running `compile_context_snapshot`.
2. **Retry 2 (Minimal Fallback View):** Compile minimal view containing only essential prompt and confirmed constraints.
3. **Terminal Failure:** If validation fails after 2 retries, do NOT call model. Immediately return `response(error="context_build_failed")`.

### Failure Path Mapping:
- `context_build_failed`: Emitted when snapshot compilation fails schema or closure validation after 2 retries.
- `cancelled`: Emitted when `should_cancel()` returns `True` before or after model call.
- `token_budget_exhausted`: Emitted when token ceiling reached.
- `controller_finish_refused`: Emitted when `finish_only` is active but model returns tool call.
- `verification_failed`: Emitted when repair budget exceeded or answer definitively rejected.

---

## 5. Native Assistant and Tool Message Constraints

When converting `ContextSnapshot` into model-specific prompts/messages (in `_call_model` / `slm_engine`):
1. **Opaque Value References:** Never expose `$value_ref` syntax to model prompts; if full text is required by prompt template, decode via `expand_value_refs` within the formatter boundary.
2. **Lossless Tool Results:** Unknown plugin results and non-artifact scalar outputs must be serialized to native string/json tool messages with exact types preserved.
3. **Assistant Message Role Invariance:** Multi-step tool calls in `pending_calls` must maintain valid alternating `assistant` (with `tool_calls`) and `tool` (with matching `tool_call_id`) message sequence.
4. **Contract Freeze Invariance:** Once `turn_contract.frozen == True`, `proposal` state in context snapshots must remain immutable.

---

## 6. Concrete Call Sites & Changes Required in B2

| Call Site | File & Line | Current Behavior | Planned B2 Implementation |
| :--- | :--- | :--- | :--- |
| **CS-1** | `rat/engine/assistant_runtime.py:946-958` | Directly calls `_call_model(goal, trajectory, **context)` | Determine view (`planner`, `actor`, `repair`, `finish`), execute Pre/Copies/Post vector, compile `ContextSnapshot`, validate, pass snapshot to `_call_model`. |
| **CS-2** | `rat/engine/assistant_runtime.py:527-540` | `_call_model` formats unstructured trajectory | Accept `snapshot: Dict[str, Any]`, extract structured entities and verified proofs to construct model prompt. |
| **CS-3** | `rat/engine/assistant_runtime.py:996-1002` | `guard_action == "REPAIR"` increments repairs and sets `context['answer_schema']` | Explicitly flag view as `"repair"`, include verification report receipt in snapshot. |
| **CS-4** | `rat/engine/assistant_runtime.py:947-949, 1027` | Sets `finish_only = True` | Explicitly flag view as `"finish"`, prune tool definitions from snapshot projection. |
| **CS-5** | `rat/engine/assistant_runtime.py:950-952` | Pops `initial_decision` | Preserve fixture injection protocol without invoking `compile_context_snapshot` unless requested. |

---

## 7. Gate Confirmation

**No runtime code was modified in this turn.** All runtime wiring remains strictly deferred to step B2 following formal Codex acceptance of B1.
