# RAT publication validation — 2026-10-13

The pending conversation/verification and inline-note UI changes were checked
before publication. Existing review artifacts and failed development model
outputs are retained without overwriting their original hashes or results.

## Fixes reproduced before publication

The independent conversation review had seven failures, all reproduced on the
pending source. Completion/failure now checks the original execution identity
even while a turn is in progress. Repeated terminal callbacks do not append
duplicate context or reopen a cancelled turn. Cancelled ambiguous operations
cannot create an input request, and waiting-input artifacts/events retain their
owner identity. Runtime passes its cancellation callback to the dispatcher so a
stop during a tool handler is checked before publishing its artifact. Historical
model context uses the latest saved note revision for each earlier owner turn.

The DSA fixture now passes its issued execution IDs into runtime, matching the
actual native worker contract. The seven lifecycle probes are also collected as
ordinary regressions in `tests/test_rat_conversation_lifecycle.py`.

## Validation

- Headless: 156 passed in 2.78s, comprising 149 regular tests and 7 independent
  audit probes. `headless_tests.txt` retains the raw pytest result.
- Qt offscreen: 42 passed in 7.61s. `ui_tests.txt` retains the raw result. Qt's
  NEON detection failed in the sandbox; these tests passed outside it.
- Existing source and test hashes are captured in `validation.json`.
- EVRP retains all 104 original commits. No author/committer dates were changed.

These are software contract regressions with scripted fixtures, not model
quality evidence. No new model calls, personal-file indexing, research
experiment or fitting ran. The saved DSA smoke still contains a timeout and
incorrect answers; it does not pass end-to-end model acceptance. Research
protocol, Stage 0 and standalone DocAI/EVRP separation remain unchanged.

GitHub resolves `Thundercok/nesy-docai` to the same repository ID as
`Thundercok/structured-multi-step-reasoning` at publication preflight. The latter
is its currently reported name. Only current work on `main` is published;
ignored local state, recovery bundles and archive refs remain local.
