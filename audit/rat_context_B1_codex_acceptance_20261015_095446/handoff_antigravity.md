# Anti: finish the existing B1 origin invariant at nested result slots

Repository: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Read applicable AGENTS.md and this folder's `review.md`,
`registered_result_probes.py`, test logs and source manifest. Preserve other
working-tree changes, historical packets and immutable independent probes.
Do not git push/pull/reset/force or call real models.

The previous receipt-level repair works: all 151 existing focused executions,
including the 8 raw-receipt probes, now pass. B1 acceptance still has one blocker:
4 new cases fail at raw `note`/`note_event` children of `record_work_note` results.
The canonical note/event positive control passes.

## Implement one complete emitted-edge plan

`projected_slots` currently records only receipt header substitutions. The nested
operation-result adapter still decodes wrappers based on operation name alone.
Extend origin tracking to **every result subslot the compiler actually rewrites**.
Use the same definition for graph extraction, validation, chains and receipt,
entity and whole-snapshot expansion. Retain raw result children when no rewrite
occurred, including available/missing/self-referencing literals and wrappers with
the exact same target kind/identity/pointer as a genuine projector link.

A minimal compatible approach is to carry nested emitted locations alongside
the existing receipt metadata, for example explicit paths for
`operation_result.note` and `operation_result.note_event`, populated only in the
successful substitution branches. An equivalent explicit typed plan is fine.
Associate locations with the full owning receipt/entity identity, not a bare
receipt_id or operation name. Keep raw native fields outside that metadata.

Do not solve this with target-kind whitelists, wrapper-shape checks, trusted-parent
inheritance, or blanket permission for all fields of registered operation results.
Do not add a truth store. When a duplicate cannot safely be compressed, preserve
it inline. Follow the existing exact JSON equality/provenance requirements and
keep `rat.context/1`, source stores, native args and expected values intact.

Check every expansion entry point, especially resolving an outer result link,
expanding an entity or whole snapshot, and restoring a serialized snapshot with
an explicit trusted root. A metadata change that protects only one helper is
incomplete. Keep real typed links/cycles validated while raw literals stay data.

## Validate and hand back the completed bounded package

Run all earlier immutable independent probe files plus:
`audit/rat_context_B1_codex_acceptance_20261015_095446/registered_result_probes.py`.
Keep their assertions unchanged. Add meaningful product regressions for the
nested origin boundary, JSON roundtrip, valid projector links and immutability.
Use `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3` with
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

Use `run_review.py` here as an exact command reference, but create a fresh output
packet instead of overwriting this frozen evidence. Run focused suites after
the fix, then the recorded core command. Report actual JUnit counts by file;
Anti's earlier per-file prose counts were incorrect even though the focused total
was 151. Distinguish repeated product/independent executions from new scenarios.

Core currently has 286 passes and 7 failures: six planner compatibility cases and
one cancelled-turn history assertion. Preserve current runtime work. Do not
redesign the planner, loosen core matching or weaken tests during this B1 repair.
Include a separate source-to-failure triage if those failures persist; do not
claim a full-green core run or attribute unrelated changes to your compiler fix.
The shared runtime changed again after Codex's tests; those counts are tied to
the frozen runtime hash in `review.md`. Inspect the later source manifest and
rerun your actual start source rather than assuming the older results cover it.

Correct the new B2 documentation: a second live boundary sample is not a vector
derived from the copied bundle. State the remaining gap precisely. Do not claim
the three-way invariant is implemented, and do not add B2 wiring or a minimal
context fallback as part of this repair.

Create a fresh timestamped audit folder with the real baseline diff, start/end
source hashes, exact commands/results, runnable verification, asserted raw →
projected → restored examples, self-review and limitations. Freeze protected
runtime/copier/core/schema/probe sources and report any concurrent drift.
Use status `ready_for_codex_review`; B1 acceptance is Codex's next check.

Finish the whole bounded package without needing another prompt for routine
steps. This closes the existing origin invariant; do not expand RAT features,
research scope, UI or DocAI.
