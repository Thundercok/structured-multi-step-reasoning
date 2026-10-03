# Execution State — NCKH Reasoning Harness

## Current Phase: Section B-lite Complete -> Awaiting User Instruction for Full Dev / Decision Rule

- **Branch**: `exp/reasoning-harness-v1`
- **Tag**: `harness-v1-run0`
- **Worktree**: `../reasoning-run` (HEAD: `1088095`)
- **Timestamp**: 2026-10-03T11:25:00+07:00

---

## Section B-lite Summary (Steps 0 – 5)

1. **Step 0. Arm DIRECT & Mock Test Verification**:
   - Added `DIRECT = 7` to `ReasoningAction` in `reasoning_env.py` (masked out in `ReasoningEnv._mask()` to maintain RL environment invariants).
   - Added `_direct()` and `DIRECT_SUFFIX = "\nTrả lời trực tiếp, kết thúc bằng đúng 1 dòng 'Answer: <kết quả>'."` to `qwen_mlx_backend.py`.
   - Added `test_direct_extracts_answer_and_confidence` unit test to `test_qwen_mlx_backend_mocked.py`.
   - Ran 10 reasoning files: **74 passed in 6.17s** (verbatim in `audit/B_gate0.txt`).
   - Committed explicitly and tagged `harness-v1-run0`.

2. **Step 1. Detached Worktree**:
   - Created clean worktree at `../reasoning-run` pointing to `harness-v1-run0`. All subsequent evaluations executed within this directory.

3. **Step 2. Model Loading & Tokenizer Inspection**:
   - Evaluated model: `mlx-community/Qwen2.5-0.5B-Instruct-4bit` (offline loaded from local HF cache).
   - `tokenizer.eos_token`: `<|im_end|>` (encodes to ID `151645`).
   - Ran 1 test generation with `enable_thinking=False` (temp=0.0): produced 126 tokens, finished with `finish_reason: stop` (verbatim in `audit/B_step2.txt`).

4. **Step 3. PAL Subprocess Coexistence in Loaded MLX Process**:
   - In same process with loaded model on Metal device:
     - Valid PAL script: `ok=True, result='1167'` in **39.22 ms**.
     - Infinite loop script (`while True: pass`): cleanly timed out at **2.010 s** (timeout limit: 2.0s) without hanging.
     - Verbatim in `audit/B_step3.txt`.

5. **Step 4. Smoke Run (3 Groups × 3 Variants × 6 Arms = 54 Evaluations)**:
   - Groups selected (`seed=0`): `grp_pal_004`, `grp_plain_004`, `grp_react_007`.
   - 9 items evaluated across 6 arms: `DIRECT`, `COT`, `SC`, `TOT`, `REACT`, `PAL`.
   - Saved 54 full trace records to `audit/B_smoke_trace.jsonl` containing `raw_output`, `finish_reason`, `prompt_tokens`, `completion_tokens`, `n_calls`, `wall_ms`, `parsed`, `gold`, `correct`.

6. **Step 5. Results Table & Raw Samples**:
   - Generated summary table and 3 random item inspections per arm from `audit/B_smoke_trace.jsonl` (verbatim in `audit/B_summary.txt`).
   - Halted without strategic comparison claims.

---

## Next Steps (Awaiting User Command)

- Review smoke table metrics (`#parse fail`, `% max_tokens`, accuracy, latency).
- On user approval:
  - Proceed with full development run across all 12 groups (36 items × 6 arms = 216 evaluations).
  - Threshold fitting & decision rule evaluation for meta-reasoning pipeline.
