# RAT Smart Notes: explicit effect requirements — 2026-10-26

Scope: RAT main; preserve the separate Mini work. No Stage 0 or research claim changes.

- Bounded Vietnamese creation commands bind an explicit `Thêm việc cần làm:` / `checklist:` task. The note verifier rejects omission or a completed status before dispatcher commit. No silent insertion and no nested model call.
- Bounded checklist/section mutation commands bind an observed note ID and current revision (explicit ID, UI pin, or latest note). Unknown/conflicting targets and stale revisions fail; wrong operations, items, status and headings receive repair feedback through the existing Agent loop.
- Requirements become a frozen turn outcome; a final response without the committed effect is unresolved even with task planning disabled. Native model messages expose the same bound requirement. Direct actions use the same capability/dispatcher guard. Selected PDF context does not redirect recognized note mutations into PDF QA.
- The live Finder/notes acceptance script now asserts the exact pending BEST-Route Section 3 task after retaining its snapshot.

Validation: deterministic software tests in `tests/test_note_requirements.py`, plus existing Smart Notes, execution service and completion reconciliation tests. Scripted decisions test error handling and receipts; they are not evidence of model quality or live UI acceptance. No real inference calls were made for this change. No UI iteration, live acceptance, research experiment or Stage 0 gate was run.

Limits: this is a bounded command parser, not general intent understanding. It binds one explicit task clause, literal task matching and a section heading preceding a colon. Other phrasing still uses the existing Agent flow. Structure/source excerpt checks do not verify free-form summaries, analysis or scientific truth. Shared service subplan orchestration remains outside this fix.
