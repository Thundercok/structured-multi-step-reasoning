# Codex B1 review — nested slot isolation

Decision: **Request changes on production source; a minimal repair candidate is verified.**

Reviewed compiler SHA-256:
`cca488dea3fabb814c6187d8980b69fbc5eaf7d8c8cef0552eb0cad4f2b86b1f`.
It matches Anti's packet. Working branch is `main`; no branches or production
files were changed by this review.

## Independent results

| Source/check | Passed | Failed | Collection errors |
| --- | ---: | ---: | ---: |
| Current B1 focused suites and all earlier probes | 166 | 0 | 0 |
| New slot-isolation probes against production compiler | 1 | 4 | 0 |
| Recorded core command against current runtime | 292 | 1 | 0 |
| Suggested compiler candidate: all B1 suites plus slot-isolation probes | 171 | 0 | 0 |

Counts are test executions, including repeated product/independent scenarios.
Candidate testing used a fresh process importing the audit candidate under the
canonical module name; it did not replace the product file. No live model calls
or model-quality measurements were made. Source manifests cover the tested state.

## R6-1 [P1] A top-level event permission also authorizes the unrelated nested event slot

Locations: `rat/engine/context_snapshot.py:255-259`, `:285-290`, `:366-372`.

The new nested tags are correct, but the consumer accepts both complete paths
and leaf aliases. In particular, `"note_event" in projected_slots` authorizes
`operation_result.note_event` as well as the real top-level `receipt.note_event`.

A public journal receipt carries a genuine canonical `note_event` and a result
with a raw `note_event` wrapper. Compilation correctly marks only `note_event`
and the outer `operation_result`; it does **not** emit
`operation_result.note_event`. The alias nevertheless makes the raw nested
wrapper a typed graph edge. With an available target, restoration silently
replaces it with a canonical event. With a missing target, validation rejects
the literal as a broken structural reference.

Both `record_work_note` and `unknown_plugin` reproduce the issue. No compiled
snapshot is mutated by the probes. The positive control uses two genuine links
and confirms both complete paths can coexist and restore correctly.

Required change: permission tokens identify exact locations. Remove the leaf
aliases from nested result checks in receipt graph extraction, entity graph
extraction and result expansion. Preserve the independent top-level event tag.
`note` aliases are also unnecessary because this compiler emits complete nested
paths; remove them consistently rather than keeping ambiguous shortcuts.

## Concrete verified candidate

`suggested_fix.patch` removes exactly three `note` alias checks and three
`note_event` alias checks, with no other source changes. It is based on the
frozen reviewed compiler and has not been applied to the working tree.

Candidate SHA-256:
`11072c6098635903d0d90c408d49cfc81f10df756eb96f2dd9b21a826bbb07e7`.

`verify_candidate.py` imports `context_snapshot_candidate.py` in an isolated
process and runs all 166 existing B1 checks plus the 5 new checks. Result:
**171 passed, zero failures/errors**. Evidence: `candidate_run.json`,
`candidate.log`, `candidate.xml`, and `candidate_metadata.json`.

This closes the reproduced compiler blocker in the candidate. Production B1
acceptance still requires applying the repair and verifying the actual source.
The candidate result is not a full runtime/B2 acceptance claim.

## Remaining core failure is an observed continuation-policy difference

The sole failing core check is
`test_native_planner_outcomes_are_not_rejected_as_task_state`.
`diagnose_remaining_core.py` reproduces its two-response synthetic client and
records **three attempted calls**, ending in `StopIteration`.

The sequence is:

1. The planner proposes a `record_work_note` outcome.
2. The actor says `Đã ghi` without executing it.
3. The runtime computes `completion_feedback` with `omitted_action`, then
   continues to a third model call at the `missing_work` branch.

Source locations: `rat/engine/assistant_runtime.py:1217-1247`.
This is not a random fixture import/counting issue. The two-response fixture
exposes a real call-sequence change. A real client would receive another request
rather than raising the mock's `StopIteration`.

The existing B context decisions preserve controller behavior and prohibit adding
a new repair loop as part of projection wiring. If the completion-feedback loop
is intentional separate work, it needs a documented semantic/compatibility
decision and its own tests/call accounting. Do not hide it by merely adding more
mock responses or loosening assertions. B1 repair can stay separate while B2
acceptance remains pending.

Evidence: `core.log`, `core.xml`, `test_run.json`, and
`remaining_core_diagnostic.json`. The diagnostic uses `MagicMock`, not network
inference. An initial standalone diagnostic import failure was repaired in the
audit helper; its bootstrap log is preserved and it did not affect pytest results.

Historical packets, independent probes and unrelated working-tree changes have
been retained.
