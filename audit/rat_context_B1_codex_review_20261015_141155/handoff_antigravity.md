# Anti: apply the verified minimal B1 repair and hand back actual-source evidence

Work on `main` in
`/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Follow the updated AGENTS.md: no new feature/checkpoint branches, no git
push/pull/reset/force, preserve unrelated edits and recovery material. No live
model calls, research/UI/DocAI expansion or new runtime wiring.

Read `review.md`, `suggested_fix.patch`, `slot_isolation_probes.py` and
`candidate_run.json` in this folder. This is a small, concrete follow-up, not
another request to redesign the compiler.

## 1. Apply the verified patch, checking the real baseline first

Expected compiler SHA-256 before the patch:
`cca488dea3fabb814c6187d8980b69fbc5eaf7d8c8cef0552eb0cad4f2b86b1f`.

`suggested_fix.patch` removes six leaf-alias permissions from nested result
checks. A top-level `note_event` tag must authorize only that path, never
`operation_result.note_event`. Use complete emitted paths consistently for
receipt edges, entity edges and decoding. Preserve the separate top-level tag.

The isolated candidate already passes **171/171 B1 checks**, including the four
new failures on the current product compiler and a two-genuine-links control.
Expected compiler hash after applying the exact patch:
`11072c6098635903d0d90c408d49cfc81f10df756eb96f2dd9b21a826bbb07e7`.

Check for concurrent source changes before applying; do not overwrite a newer
file blindly. Preserve all immutable probes. Add a focused product regression
for a genuine top-level event combined with a raw nested event, covering known
and unknown operations and available/missing targets. Keep the valid two-link
control. Do not add features or another permission fallback.

## 2. Verify production source and return a fresh packet

Use `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`,
`PYTHONDONTWRITEBYTECODE=1`, and `-p no:cacheprovider`.

Run the focused command recorded in `test_run.json` plus this folder's unchanged
`slot_isolation_probes.py`. It should reproduce at least the 171 executions that
pass against the candidate, plus your new product regressions. Run the exact
recorded core command too; report the real result independently of B1.

Create a new timestamped audit packet with actual start/end source hashes, the
small baseline diff, exact argv/interpreter/results, product regression mapping,
asserted roundtrips and a concise self-review. Keep old packets intact. Mark
`ready_for_codex_review`; candidate testing is not production acceptance.

## 3. Keep the remaining runtime policy issue separate and honest

Core currently has **292 passes and one failure**. The diagnostic proves that
the runtime attempts three model calls for the old two-response fixture:
planner → premature final answer → completion-feedback continuation.
See `remaining_core_diagnostic.json` and `review.md`.

Do not dismiss this as only a mock side_effect count, append responses solely to
green the fixture, or silently change continuation behavior. Existing B2 scope
preserves controller/repair policy. Report whether this loop belongs to separately
authorized runtime work, and supply the relevant behavior/compatibility decision
if available in your session. Do not roll back another contributor's code.

B1 can be repaired and submitted independently. B2 acceptance must still resolve
that call-sequence question and the true copied-vector gap. Keep those facts
distinct in the final handoff; do not claim a fully green project or completed B2.

Complete the patch, meaningful regression and reproducible handoff without
requesting another prompt for routine steps.
