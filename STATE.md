# Execution State — NCKH Reasoning Harness

## Current Phase: Section A-fix Complete -> Awaiting User Instruction for Section B

- **Branch**: `exp/reasoning-harness-v1`
- **Tag**: `harness-v1-run0`
- **Timestamp**: 2026-10-03T10:15:00+07:00

---

## Section A Execution Summary (A1 – A10)

1. **A6. True Reverse Mutation Verification (Offline, No Model)**:
   - Replaced all ad-hoc string mutators with authentic unified diff reverse patches:
     - `audit/mutants/patch_1.diff`: Reverts generation prompt (`add_generation_prompt=True`) and finish_reason in `qwen_mlx_backend.py`.
     - `audit/mutants/patch_1b.diff`: Retains generation prompt, removes only `finish_reason` in `qwen_mlx_backend.py`.
     - `audit/mutants/patch_2.diff`: Reverts `REACT_SYSTEM` to Vietnamese with placeholder artifacts in `qwen_mlx_backend.py`.
     - `audit/mutants/patch_3.diff`: Reverts `run_python_sandboxed` to `mp.Process` in `reasoning_strategies.py`.
     - `audit/mutants/patch_4.diff`: Reverts `extract_answer` & `extract_conclusion_number` in `reasoning_strategies.py`.
     - `audit/mutants/patch_5.diff`: Reverts ToT candidate index parsing to greedy digit regex in `qwen_mlx_backend.py`.
   - Each mutant was applied via `git apply`, tested with `pytest tests/test_harness_regressions.py -q --tb=short --junitxml=audit/mutants/m{i}.xml | tee audit/mutants/m{i}.txt`, and reversed via `git apply -R`.
   - XML-derived Mutation Matrix:
     - Base (m0): 5 PASS / 0 FAIL
     - Mutant 1: Test 1 FAIL, Test 5 FAIL (FakeTokenizer enforces generation prompt across all _chat calls)
     - Mutant 1b: Test 1 FAIL (`AssertionError: Expected finish_reason 'stop', got None`), Tests 2-5 PASS (isolated check on finish_reason)
     - Mutant 2: Test 2 FAIL (`AssertionError: REACT_SYSTEM prompt leaked placeholder 'bieu_thuc_so_hoc'`), Tests 1, 3, 4, 5 PASS
     - Mutant 3: Test 3 FAIL (`AssertionError: Code without result must fail, but got ok=True`), Tests 1, 2, 4, 5 PASS
     - Mutant 4: Test 4 FAIL (`AssertionError: Expected '192', got 'Therefore, the total number of pizza slices Albert eats in 4 weeks is 192 slices.'`), Test 2 FAIL (old parser unstripped placeholders in 201331c), Tests 1, 3, 5 PASS
     - Mutant 5: Test 5 FAIL (`AssertionError: ToT must select candidate 1 ('1167'), got '422'`), Tests 1, 2, 3, 4 PASS
   - Accounting of remaining hunks from `git diff 201331c 6aff01b`:
     - `experiments/research_study.py`: attacher of `last_trace` to experiment records.
     - `qwen_mlx_backend.py`: initialization and helper `_record_tool` for trace logging.

2. **A7. Clean Worktree Reasoning Suite (73 Tests)**:
   - Evaluated in detached worktree `/tmp/chk`.
   - 10 reasoning files executed cleanly: 73 passed in 10.74s.
   - Exact collection tally: 73 tests across 10 files (breakdown confirmed via `pytest --collect-only`).

3. **A8. ReAct Placeholder Audit in Real Outputs**:
   - `grep -c bieu_thuc_so_hoc outputs/*.json | grep -v ':0$'` returned `outputs/pilot_real_model_report.json:2`.
   - Inspection confirmed the only occurrences were:
     1. In line 188: model complaint regarding the function name in thought text.
     2. In line 210: the prompt definition in `locked_protocol`.
   - No output traces showed the model echoing `Action: finish[dap_an]` or `Action: calculate[bieu_thuc_so_hoc]`.
   - In accordance with instructions, Test 2 docstring explicitly notes: `"chưa tái hiện bug ReAct trên trace thật; chỉ kiểm parser + prompt"`.

4. **A9. Audit Log Tee & RAT Suite Breakdown**:
   - Re-tee'd `git log --stat -3`, `git log --all -- docs/stage0_gate_decision.md`, and `git show 201331c | grep stage0` to `audit/gate_A4.txt`.
   - Confirmed `docs/stage0_gate_decision.md` has 0 git history.
   - Verified exact test breakdown:
     - **Reasoning harness**: 10 files, 73 tests.
     - **RAT engine/UI**: 24 files, 187 tests (including `tests/test_frcot.py` with 10 tests).
     - **Total**: 34 test files, 260 tests.

5. **A10. Dev Split Gold Standard Table**:
   - Generated `audit/dev_golds.md` mapping all 12 dev groups (`split: 'train'`, 36 items) to their gold answers, exact mathematical/deductive derivation methods, and 3 variant IDs.

---

## Next Step: Section B (Awaiting User Command "GO B")

Next execution target:
- Clean isolated worktree checkout:
  `git worktree add --detach ../reasoning-run harness-v1-run0`
- **B1**: Checkpoint inspect `~/.cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit`, verify shards, load + 1 generate, print templated prompt with `enable_thinking=False`.
- **B2**: PAL + MLX in same process: run 2 items (1 valid code, 1 `while True`) to verify non-hanging.
- **B3**: DIRECT arm + smoke on 3 groups.
- **B4**: Decision rule + dev run (12 groups × 6 arms).
- **B5**: Stats reporting from jsonl.
