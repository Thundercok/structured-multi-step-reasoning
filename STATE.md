# Execution State — NCKH Reasoning Harness

## Current Phase: development pilot software validated; independent review and measured pilot pending

- **Branch**: `exp/reasoning-harness-v1`
- **Tags**: `v0.1.0-nckh-baseline`, `harness-p0-fixed`, `harness-v1-run0`, `harness-v1-run2`, `harness-v1-run3`
- **Note on harness-v1-run1**: `harness-v1-run1` nằm trên main (`f51db3f`), thiếu fix P0. Nhánh `exp/reasoning-harness-v1` đã cherry-pick commit này thành `0047bb2` (gộp MANIFEST).
- **Completed sweep worktree**: `../reasoning-run3` (detached HEAD at `harness-v1-run3` / `76d311b`).
- **H4 sweep**: complete, **188/188** records (DIRECT 94, COT 94); no missing, unexpected or duplicate item/arm pairs. Final `audit/G_sweep_trace.jsonl` and `audit/G_summary.txt` in this repository match the worktree copies byte for byte. Verification: `audit/G_completion_verification.json`.
- **Model**: `mlx-community/Qwen3-8B-4bit` (4.29 GB safetensors; cache-derived snapshot name `545dc4251c05440727734bcd94334791f6ab0192`, without independent loaded-weight identity verification).
- **Status checked**: 2026-10-03, sweep completion and agent retrospective review verified; independent human review pending.

---

## Development Pilot Implementation — 2026-10-04

- Supported `python -m experiments.research_study --pilot` collects fixed
  strategy diagnostics on train/calibration only. It rejects held-out inputs
  before model loading and fits no controller. Main-study evaluation and the
  existing Stage 0 decision remain separate.
- Whole-group, label-independent sampling by split/family/level; proposed
  DIRECT/CoT grid gives both arms per-call caps of 96 and 1,024. Default sampling
  selects 24 items / 24 canonical groups from the actual tuning candidate.
  These are preparation choices, not frozen main-study parameters.
- Records preserve raw messages/output, generation settings, finish reasons,
  heuristic confidence, prompt/generated counts, all-call strategy cost and
  duration. ReAct respects smaller caps while retaining its 200-token ceiling.
  Measured pilot inputs require a local model directory with content hashes;
  those hashes do not authenticate an upstream revision.
- **158 research tests passed**, including the required harness, stopping and
  entry checks. Synthetic pilot/replay and fresh main-study smoke/replay/
  three-seed aggregation validate software only; no new model inference ran.
- Evidence: `audit/development-pilot-validation-20261004/`. Historical candidate
  manifest restored to its original, audit-verified source hashes. Rebuilding
  unchanged data checks content reproducibility without rewriting provenance.
- Preparation/review instructions: `docs/development_pilot_protocol.md`.
  Human/source review and measured collection remain pending; publication
  parameters and difficulty calibration remain unfrozen.
- Implementation/data/audit checkpoint: `ce298b1`. A fresh clone at that
  commit passes **158 tests** and reproduces saved pilot outputs byte for byte;
  fresh main-study smoke/replay/three-seed aggregation also passes. Verification:
  `audit/development-pilot-validation-20261004/checkpoint_verification.json`.

---

## H4 Offline Tuning Review — 2026-10-03

- Review bundle: `audit/qwen3-8b-tuning-review-20261003/`, reproducible with
  `python -m scripts.review_tuning_sweep --output NEW_DIR`.
- Reproduced **188/188** legacy parse/score records from pinned Git `76d311b`.
  Independently verified all **94 exposed tuning questions/golds**, including
  obsolete tune test rows. Main-study held-out content was not reviewed.
- Retrospective typed scores: DIRECT **21/94 (22.3%)**, CoT **63/94 (67.0%)**.
  Historical DIRECT was 22/94: one correct arithmetic reasoning tail at the
  token cap lacks the requested bare answer and fails the strict format contract.
  This is a format-score change, not a newly identified arithmetic mistake.
- Fixed balanced bold/repeated Answer: presentation handling for six correct
  CoT ordering responses. Whole contradictory clauses, alternatives, wrong
  ordinals and equality suffixes remain subject to strict scoring. No correct
  Game-of-24 answers are recovered by parsing changes in this trace.
- DIRECT cap 96 vs CoT cap 1,024 confounds budget and prompt effects. Length
  terminations affect 23/32 DIRECT arithmetic and 20/30 CoT Game-of-24 outputs.
  CoT arithmetic levels 1–3 and ordering level 4 reach 8/8; ordering level
  accuracy is nonmonotonic. **Parameters remain unfrozen**; difficulty spread
  and strategy effects are not established by this single greedy sweep.
- Costs in the review are recorded generated tokens, with prompt counts
  separate. Historical arm wall times are not online controller latency.
  The runner's cache-derived snapshot name does not independently prove the
  loaded weight identity; future collection needs a pinned local snapshot.
- **132 tests passed**, with eight audit checks rerun after the final analysis
  refinement. Fresh synthetic smoke/replay results agree byte for byte.
  Validation: `audit/h4_tuning_review_validation.json`.
- Original trace/summary are unchanged. No model call, policy fit, dataset
  parameter freeze or Stage 0 decision was added; human review remains pending.

---

## Canonical Procedural Dataset Preparation — 2026-10-03

- Candidate bundle: `data/procedural_research_v1/`, rebuilt by
  `python -m scripts.build_procedural_research_data --split-seed 42 --output NEW_DIR`.
- Main: **179 items / 177 canonical groups**, with train 36/36, calibration
  72/71 and test 71/70 (items/groups). Exposed tuning pool: **94/91**, with
  train 32/32, calibration 62/59 and no test split.
- Canonical fingerprints group renamed ordering graphs, arithmetic operation
  sequences and Game-of-24 number multisets. Item IDs have separate release
  namespaces; canonical `problem_id` and `group_id` agree.
- Excluded one main-source ordering item present in the tuning pool. Canonical
  and item-ID overlap between releases is zero; all groups stay in one split.
  Rebuilt development splits by family/level and a label-independent SHA-256
  rank. Eligible original test groups retain test status; no previously reviewed
  development item is promoted into test.
- Original procedural files and retained question/label/metadata content are
  unchanged. Source IDs/splits, row hashes and agent review provenance are
  recorded. Human, license/ownership, held-out gold and prior test-exposure
  review remain pending; this is a candidate, not a publication release.
- The study runner recomputes canonical identities and rejects exposed tuning
  pools as held-out study inputs. New identity source is included in run hashes.
- **114 tests passed**, including required harness/stopping/entry checks;
  seven release tests also confirmed the saved bundle reproduces byte for byte.
  Fresh headless smoke/replay artifacts are synthetic software validation only.
  Verification: `audit/procedural_data_validation.json`.
- Preserved an immutable **148/188** legacy Qwen3-8B tuning trace checkpoint
  in `audit/qwen3-8b-tuning-checkpoint-20261003/`, with source/model/input hashes
  and the dirty resume-runner snapshot. The detached worktree is untouched.
  The sweep subsequently completed: final trace/summary copies are verified
  by `audit/G_completion_verification.json`. Historical scoring is retained
  separately from the repaired research scorer.
- No additional model experiment, Stage 0 decision or quality claim was added.

---

## Development Data and Scoring Audit — 2026-10-03

- Independently verified 54 curated development variants (18 groups), 108
  procedural v2 development items and 60 tune development items: **222 total**.
- Applied 10 development wording repairs, explicit Vietnamese aliases/decimal
  formatting and recorded AI-agent review provenance. Intended development
  labels agreed with independent calculations; human review remains pending.
- Repaired negation/alternative-answer acceptance, contradictory Game-of-24
  equality suffixes and loss of expressions during research parsing/voting.
  The supported collector supplies format metadata to MLX without gold labels.
- Pinned and verified the adapted GSM8K calibration source, its upstream split
  and repository license; other descriptive template sources still lack
  ownership/original-source records.
- Blinded structural checks found 1 ordering class crossing splits in v2
  (2 items) and 2 classes in tune (5 items). The two procedural files also share
  94 group names and 1 canonical problem identity. The separate candidate
  migration above resolves this structural overlap; legacy inputs remain intact.
- All held-out rows retain their exact baseline fingerprints; both procedural
  input files remain unchanged. No real-model run, fitting or Stage 0 decision
  was added by this audit.
- Validation: **107 passed** across the required research checks, aggregation,
  scoring, development-audit, generator and mocked-backend tests. Eleven
  before/after scoring probes reproduced from pinned pre-audit code are in
  `audit/scoring_audit_cases.json`.
- Report and machine proofs: `audit/development-data-20261003-final/`.
  Older smoke/aggregate artifacts retain their original source hashes; updated
  scoring requires fresh source-pinned runs.

---

## Supported Research Pipeline Update — 2026-10-03

- Added `python -m experiments.research_study --aggregate RUN RUN ... --output NEW_DIR`.
- Aggregate inputs require matching frozen datasets/settings/runtime, distinct
  generation seeds, intact artifact hashes and complete paired test outcomes.
  Answers and cumulative path costs are checked against recorded attempts.
- Average seeds per question before bootstrapping original problem groups;
  retain unique test-question counts and report descriptive seed variability.
- Validation: **50 passed** across `tests/test_research_study.py`,
  `tests/test_research_aggregate.py`, `test_optimal_stopping.py` and
  `test_entry_predictor.py` using the installed Python 3.12 runtime.
- Smoke validation: seeds 11/22/33, replay of seed 11 and aggregate completed in
  `runs/aggregate-validation-20261003-final/`. The aggregate retains 24 test
  questions and 24 groups. These are `synthetic_smoke` software artifacts,
  not measured model-quality evidence. Audit: `audit/research_aggregate_validation.json`.
- Procedural checker source is included in collection/replay source hashes.
  Publication review and the existing Stage 0 requirements remain in force;
  this update does not establish a new gate decision or checkpoint provenance.

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

## Next Research Work

- Obtain independent human/source review; keep held-out review separate from
  development tuning. Review prior test exposure before freezing the candidate.
  Dataset/scoring checks do not establish model quality.
- Review the development-only pilot configuration and matched budget grid in
  `docs/development_pilot_protocol.md`. Retain H4 as historical exposed-
  development diagnostics; main-study comparisons remain pending.
- Freeze model snapshot, prompts, lambda and generation seeds, and satisfy the
  applicable Stage 0 review before further Qwen/Meta-Reasoner measurements.
- Collect development/pilot artifacts through the supported research pipeline,
  then evaluate preregistered test runs with the multi-seed aggregate analysis.
