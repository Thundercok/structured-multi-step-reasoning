# RAT–CoT integrity and live acceptance review — 2026-10-25

**Status: PARTIAL. Do not treat the original “all phases passed” statement as universal acceptance.**

This review covers production source, software regressions, and actual macOS UI interactions with local `qwen3:4b-instruct`. It does not change Stage 0 or establish model quality. RAT is the primary implementation; the headless study remains its separate reproducible evaluation environment.

## Findings and repairs

- Historical Smart Notes telemetry was assigned by `mock_model` (800 prompt / 125 completion). Preserved original script/report/README in `before/`, corrected the historical README, and replaced the generator with an explicitly synthetic software audit. Serialized JSON bytes are not model tokens, full inference costs or proof of semantic equivalence.
- Removed Smart Notes' hidden nested model call and fabricated fallback analysis. The existing Agent loop can prepare `structured_note`; the tool validates/stores it. Without a proposal it does labeled extractive organization only. No canned assistant completion is used for live acceptance.
- Notes now preserve raw input text and SHA-256, and the dispatcher owns one canonical artifact ID/commit. Same input in separate invocations creates distinct artifacts; historical revisions remain readable in the session store. This is session-memory storage, not a durable file-save promise.
- Removed duplicated checklist text from extractive analysis sections so a toggled item cannot still appear unchecked in an old copied section; sentence boundaries keep the task separate from preceding prose. This last extractor repair was software-tested after the live .30 process had loaded its earlier implementation.
- Missing/ambiguous checklist targets fail without adding a new completed task. Stale revisions fail; toggle verification compares the requested mutation and previous snapshot. Expansion requires actual supplied content rather than copying an instruction as completed analysis.
- Note checks validate schema/source hash and exact normalized source excerpts. A shared keyword cannot certify a false numeric claim. PASS is scoped to those checks; summaries, analysis, recommendations and the final answer stay unverified. An unrelated note or reading checker does not issue a global verdict without evidence.
- Fixed continuation validation using the actual artifact store and prevented explicit actions with verifier FAIL from emitting completed.
- Observation Pack formatting now reaches observations wrapped with verification feedback and retains the canonical reference. Full raw data stays in the session artifact, retrievable by `inspect_artifact`.
- App launches use the shared service without a direct fallback; UI errors do not expose raw OS exception text. Registered launch receipts still mean OS request acceptance only.
- Removed direct read fallback from context expansion and moved expansion execution out of a QML text binding. Source text never falls back to the model's answer.
- Fixed Finder's reference to IDs moved into its extracted QML component. A discovered collapse hang (five results → three, selected fifth) was reproduced in a software test and fixed by a stable scroll gutter/reset.
- Fixed page projection: a genuine page with extracted text no longer shows “no excerpt” merely because there is no search hit.
- Production default UI runtime uses existing tool discovery. Smart Note creation schema is core, mutation schemas become available when a structured note exists. Clarified artifact notes versus session memory, and future checklist work versus immediate tool execution.
- Preserved explicit zero cached-token counts and projected general runtime telemetry into the controller. New PDF-page observations carry actual page metadata; note/discovery results are not document citations.

## Contract, UI projection, model loop: current inventory

| Capability | Contract / dispatcher | UI projection | Model-loop evidence and limits |
| --- | --- | --- | --- |
| General chat | Service → AssistantRuntime → dispatcher | Production QML, real prompts/errors | Live discovery and multi-call execution observed. General intent coverage remains unchecked by default; a final response is not proof every user requirement was met. |
| Selected PDF Q&A | Bound path/hash, registered read and expansion recipe | Answer, source labels, compact/full | Live PDF answer observed. Selected-document recipe remains bounded; current tests do not establish arbitrary automatic recovery or complete grounding. |
| Direct PDF selection/search/page | `selected_pdf` helpers and `_LatestPDFWorker` still call PDF operations directly | Genuine pages/search results; page-text projection repaired | **Remaining migration gap:** not all direct reader operations pass AgentExecutionService/dispatcher. Do not claim universal business-boundary consolidation. |
| Finder typing preview | ProgressiveSearch / SearchCoordinator; direct retrieval remains | Real indexed PDF search and keyboard selection observed | **Remaining migration gap:** preview retrieval has not become the specified service subplan. It is not evidence of a model reasoning step. |
| File/app committed actions | Some service operations; app launch fallback removed | Existing Finder/actions | App contracts/regressions verified in software. No live app launch claimed in this run. |
| Calculate | Shared tool and independent arithmetic checker | Existing answer projection | Scoped software regressions; no model-quality claim. |
| Smart Notes | Shared registered operations, ArtifactStore, scoped NoteVerifier | Artifact refs retained in turns and visible model answer tested. Concurrent .31 Smart Notes Desk code exists but was not reviewed/accepted in the .30 live run | Live creation observed, including a failure to include the requested checklist. Follow-ups/recovery are recorded separately below. Initial single-request journey is **not accepted**. |
| Reading / natal | Plugin packs and registered verifiers; existing coordinator | Existing ReadingDesk | No new live synthesis/natal acceptance in this review. Phase-6 opening a workbench/setting cards alone does not verify model synthesis. Concurrent Reading changes are outside this review. |
| Learned stopping | Opt-in controller / provenance contracts | Existing runtime | No fitted-policy or Stage-0 acceptance inferred from this work. |

## Live evidence

Genuine source: `work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf`, origin `https://arxiv.org/pdf/2506.22716`, SHA-256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`.

Launch command (no injected prompts/answers/UI actions):

```
python scripts/run_agentic_integrity_live.py --output-dir artifacts/rat_agentic_integrity_20261025/live_04
```

Interact through the real window. The launcher only sets up the existing UI/runtime, indexes this genuine PDF in an isolated database, and passively records actual model calls, responses and snapshots. Source code was being changed concurrently in this checkout; do not infer a frozen-source campaign or universal reproducibility from the build label. A separate process committed shared files as `cabdef4f` during the review; this chat did not issue a git commit/push/pull/reset.

- `live_01`: Finder found the genuine PDF. QML exposed the extracted-component reference error. The review logger then crashed on a mappingproxy while serializing a response; this instrumentation failure was repaired. This attempt is not a successful conversation.
- `live_02`, Build .28: real PDF Q&A returned UNKNOWN with 971 prompt / 200 completion tokens. Full/minimal screenshots are retained. Source-page projection failed although backend text existed. Smart Note request timed out after 90s with all 34 schemas. Missing backend usage on that failure is **unknown**, not zero inference cost.
- `live_03`, Build .29: source page displayed actual text after repair; screenshot retained. Discovery executed actual search/read calls, but selected session-memory `record_work_note`, sent invalid arguments and failed. No Smart Note success claimed for that attempt.
- `live_04`, Build .30: genuine PDF answer and actual Smart Note artifact creation observed. The initial note's checklist was empty, despite the user asking for a future task; the model read additional PDF pages instead. The returned artifact ID was real, but this does not satisfy the full requested outcome. Screenshot and complete prompt/call/response trace retained. Recovery/follow-ups are recorded in the final live summary.

Evidence folders: `artifacts/rat_agentic_integrity_20261025/live_01` through `live_04`. `model_requests.jsonl` records submitted requests; `model_calls.jsonl` records returned metadata/public model output, including failures. `responses.jsonl` and `artifacts.json` record observed responses and committed artifacts. Screenshots are captured from the actual UI. Test fixtures are kept separate in `audit/rat_smart_notes_software_20261025`.

## Research evidence

See `stopping_review/README.md` and `source_diagnostic.json`: equal-share imputed candidate token costs; 74/500 literal-scoring disagreements with the existing procedural checker on the corresponding exposed-development items. The exporter now labels these limitations, writes metadata and removes hard-coded headline conclusions. Historical raw results remain preserved. No new research model calls; Stage 0 unchanged.

## Verification and remaining work

Software regression: **253 passed**, `regression_final.log` (Qt offscreen; no live acceptance claim). After the final extractor-only cleanup, the affected note/runtime/service subset passed **60 tests**, `note_final.log`, and the explicitly synthetic software audit was regenerated. Research regression: **40 passed**, `research_regression.log`, including the required three test files and offline-stopping software checks. Context/worker isolation: **17 passed**, `context_worker.log`; the previous combined run hung on Finder collapse, was interrupted, and is superseded by the final passing run. `finder_collapse.log` retains the isolated reproduction/repair check. The shared checkout also has unrelated concurrent changes; whitespace warnings in those files were not silently cleaned.

See `artifacts/rat_agentic_integrity_20261025/summary.json` (repo root) for every retained turn and reported token counts. Rebuild it with `python -m scripts.summarize_agentic_integrity_live` after closing the test UI; it does no inference. `evidence_manifest.json` pins the retained evidence bytes. PASS on software contracts does not pass UI acceptance or the research gate. The next core milestone is completion/repair against **all requested outcomes**, including note checklist content, followed by a fresh unassisted end-to-end journey. Remaining direct Finder/PDF bypasses must be migrated before claiming every business capability shares the service. Do not re-expand unrelated domains to close these gaps.


## Final live outcome ledger

| Step | Observed outcome | Acceptance |
| --- | --- | --- |
| Find genuine PDF / open / question | Production Finder, PDF source text and real model answer observed | Bounded slice observed; no global grounding claim |
| Initial Smart Note request | Created `art-0db36cb6ec50458a8f7d384e6af71dfc` but no checklist | FAIL for the full request |
| Correct missing checklist | New note `art-05361aa787f14ab8840a2d46ecbd880b`; update via tool to revision 2, task pending | Guided recovery observed; extractive mode, not model-authored structured proposal |
| “Latest note” toggle | Model invented `note_12345`; dispatcher did not mutate the real note | FAIL for natural reference resolution; safe failure retained |
| Exact ID/revision toggle | Actual requested checklist change to done, revision 3 | Guided mutation verified |
| Natural expansion request | Created a different note, then claimed it modified the target | FAIL; final prose overclaims despite UNKNOWN |
| Explicit target/operation recovery | `inspect_artifact` then `expand_note_section`, original note revision 4; done checklist preserved | Mutation observed; heading became `Mở rộng: risks_and_constraints`, not the requested label `Giới hạn`. Final prose misstated storage location. Not a full semantic PASS |
| Missing peak-VRAM probe | Replied that no measurement existed; no invented GB count | Negative probe observed |
| Cancel read-only analysis | Actual Stop click; runtime response `error=cancelled`, no dispatched operations or new note revision | UI/runtime cancellation observed; server usage unavailable, not zero cost |

`live_04` retains 9 public turns and 23 logged chat calls. Reported usage for calls with known metadata totals 74,966 prompt and 1,979 completion tokens; one cancelled call has unknown usage and is excluded from these totals. These are counts for this logged app test, not a cost-saving result or full inference cost. `live_02` also has one timeout with unknown usage; `live_01` instrumentation was incomplete. See summary.json for the exact per-attempt ledger and actual transcript files. All natural-request failures remain failures even after guided recovery.

The run was closed after the cancellation probe; the launcher exited successfully. No background automation, new model download, research campaign, or push was started by this review. Shared-checkout changes made concurrently by another process remain in place.
