# Bounded Real-Model Execution Plan (Strictly Unauthorized)

**Status**: UNAUTHORIZED — ZERO NEW REAL MODEL BUDGET ALLOCATED (Remaining Budget = 0)  
**Historical Real Calls**: 12 calls (Exhausted, locked ledger SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`)  
**Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Scope & Candidate Representation

1. **Target Population**:
   - 70 candidate canonical groups from `data/procedural_research_v1/main.json` (split: `test`).
   - Group representative selection rule: *lexicographically smallest item ID within each group*, chosen prior to model execution.
   - Outcome-blind representation: no model outputs, accuracy metrics, or trial results are used to select group representatives.

2. **Model & Runtime Target**:
   - Model Repository: `mlx-community/Qwen2.5-7B-Instruct-4bit` (Local Apple Silicon MLX).
   - Backend Protocol: `LLMBackend.v1`.
   - Prompt Profiles: `aligned-direct-cot-v1` (with matched prefix/instruction syntax across arms).

3. **Experimental Arms (Study 1: Fresh-Restart Manipulation)**:
   - Arm $O$: Original generation / baseline prompt with greedy decoding (`temperature=0.0`), no prefix (1 generation request per group representative).
   - Arm $F$: Continuation from partial reasoning prefix of $O$ at $q^* = 0.50$ (`temperature=0.6`, fresh per-call KV cache; 1 generation request per group representative).
   - Arm $CONT$: Continuation reasoning from full reasoning prefix of $O$ at $q = 1.0$ (`temperature=0.6`, fresh per-call KV cache; 1 generation request per group representative).
   - Arm $A$: Alternate generation without prefix using identical user CoT prompt (`temperature=0.6`, fresh per-call KV cache; 1 generation request per group representative).
   *(Note: The adaptive multi-call routing ladder from Study 2 is decoupled from this 280-call budget cap; see data_review_checklist.md).*

---

## 2. Strict Budget Caps & Attempt Accounting

- **Total Request Budget Cap**:
  - Exactly 70 groups $\times$ 1 item/group $\times$ 4 single-call arms = **280 maximum generation requests**.
  - Maximum per-turn generated tokens: 64 tokens.
- **Attempt Charging Policy**:
  - Every dispatched request attempt—including timeouts, exceptions, and cancelled generations—is recorded in the append-only ledger and charged against the 280-call quota.
  - No silent retries. No unrecorded executions.
- **Append-Only Ledger Specification**:
  - Path: `calls.jsonl` (monotonically increasing line index).
  - Schema per line:
    ```json
    {
      "call_index": 1,
      "timestamp_utc": "2026-10-20T...",
      "group_id": "math_procedural_042",
      "item_id": "math_042_a",
      "arm": "F",
      "backend_type": "real",
      "model_id": "mlx-community/Qwen2.5-7B-Instruct-4bit",
      "prompt_tokens": 128,
      "completion_tokens": 42,
      "duration_ms": 312.4,
      "status": "success",
      "error": null
    }
    ```

---

## 3. Mandatory Blocking Gates (Pre-requisites for Authorization)

Before any real-model execution can be initiated, the following four gates must be formally satisfied:

1. **Gate 1: Independent Human Review Completion**:
   - The 71 candidate items / 70 groups review packet must be independently audited and signed off with human reviewer rationales, variant verifications, and explicit item dispositions.
2. **Gate 2: Candidate Frame & Code Freeze**:
   - The candidate group frame (`candidate_frame.json`) and evaluation code must be cryptographically pinned with SHA256 hashes.
3. **Gate 3: Stage 0 Gate Passage**:
   - The Stage 0 gate for the Qwen/Meta-Reasoner campaign must be formally reviewed and approved; adding infrastructure does not imply passage.
4. **Gate 4: Explicit User Quota Grant**:
   - The user must explicitly allocate positive real-model budget and grant execution authorization in writing in the active prompt.
