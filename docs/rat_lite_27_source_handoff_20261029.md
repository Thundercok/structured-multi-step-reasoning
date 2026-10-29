# RAT Lite .27 — compact interaction and the 20-item roadmap

User authorization: implement the expanded roadmap, including the optional pin,
shortcut configuration, source analysis and temporary task history. This supersedes
the proposal-only scope in `rat_lite_expanded_roadmap_20261029.md`.

**Status: source implementation, not a delivered or accepted build.** The running
.26 app has not been replaced. No tests, smoke, native/UI acceptance, screenshots,
model requests or packaging commands were run for this iteration. The only command
check was Git whitespace/diff review. Existing behavior is identified as reused,
not revalidated. A later requested build must include the new native helper.

## Visible difference from .26

| Element | .26 source | .27 source |
| --- | --- | --- |
| Empty composer starting width | 300 logical px | 240 logical px; grows to 320 while typing |
| Head host / optical height | 64 / 44 px | 44 / 30 px |
| Composer minimum height | 64 px | 48 px |
| Shortcut tutorial | Always present in idle input | Head tooltip; inline only for connection/busy feedback |
| Head click | Recall work | Toggle the same mounted composer |
| Passive reader budget | 180 px | 160 px; explicit expand keeps the same reader |
| Placement | Remembered corner | Optional observed selection bounds; corner fallback |

These are source constraints, not measured native window dimensions. Font remains
16 px in the result reader. Resizing keeps one panel, input and result editor;
there is no second chat window or new UI mode selector.

## All 20 items: concrete source and remaining evidence

| # | Implementation / reuse | Evidence still needed |
| --- | --- | --- |
| 1 Near selection | `selected_text.py` obtains optional bounds for the selected range from the same AX element/PID. Callback travels through capture tool/workflow/worker to `selection_placement.py`. Invalid geometry does not invalidate text. | Actual app support for AX range bounds and placement. |
| 2 Stable anchor | Choose home/side once per successful capture. Keep task anchor in RAM; drag updates it, history recalls it. Completion does not recompute source bounds. | Processing/result/error, drag and expansion on device. |
| 3 Displays/scale | Map native display coordinates to Qt logical geometry; match display name or logical frame, clip to work area, fall back when ambiguous. Recall selects the saved screen if present. Existing speech geometry rewraps before relocating. | Mixed scale, negative origins, display removal and Spaces. |
| 4 Shortcut | Three supported Space chords share one native/label table. SELECT2 handshake includes build, key and modifiers. Close old owner, try new exclusive registration, attempt old chord on failure. Save only after success; settings-write failure attempts rollback. | Native conflict, registration and rollback paths. |
| 5 Keyboard | Explicit composer/send/more/close Tab chain; Enter sends, Shift+Enter newline. Esc unwinds dialogs/menus/preview/subview before hiding. Existing Finder keyboard selection and selected-text copy remain. | Real focus traversal and native popup behavior. |
| 6 Pin | More toggle and visible dot. Outside click and passive peek timeout honor pin; Close/Esc still hide. Pin is per task and not persisted. | Read beside another app without focus theft. |
| 7 Reader | Reuse mounted scrolling reader, selection/anchor restoration, overflow scrollbar and separate selected/full copy. Analysis uses the same reader. Dirty-source warning applies to both. | Long final lines, copying and resize without scroll jumps. |
| 8 Source comparison | Reuse wide side-by-side / narrow source surface. Clipboard translation now retains its capture ref. Selection app label comes from the source app snapshot; no document-path inference. | Source/result view on narrow screens and actual images. |
| 9 Translation adjustments | Retry uses the exact captured ref; target/source language settings update retry args. Faithful uses existing provider; plain explicitly uses opted-in cloud and records model/provider/style. No ignored style flag. | Real provider response, language and style acceptance. |
| 10 OCR correction | Reuse correction artifact with parent/root/hash chain, draft warning and corrected-source retry; no recapture on network retry. Analysis/style actions require saving a dirty correction first. | User correction and provider-failure recovery. |
| 11 Source follow-up | Composer forwards source ref after translation as well as capture-only. Explicit analysis phrases route to shared tool; ambiguous requests use opted-in existing Agent. Missing source asks for one. | A real source → tool/Agent → answer run. |
| 12 Analysis tools | `source_analysis` capability registers `analyze_captured_text` with typed mode: summary/explanation/terms/rewrite, source ref, instruction, language. Model JSON must include literal excerpts present in source. Output contract, artifact and structural verifier are shared. | Live model output; semantic accuracy is unverified. |
| 13 Multiple steps | Source-bound “dịch rồi tóm tắt” routes to shared model planning rather than becoming translation payload. MINI_PROFILE permits analysis. Existing cancellation, partial completion, deadline and cloud budget remain. | A real multi-tool run, public answer, verification and usage receipt. |
| 14 Task tray | Up to five previous tasks in RAM; result, source, draft, image references, scroll and reading selection retained. Busy switching disabled; recall does not dispatch tools. Old organizer approval is discarded; refs still expire at tool boundary. | Task switching with typing, images, stale refs and interrupted work. |
| 15 Finder | Reuse observed hit count, partial coverage/permission status, keyboard navigation and open/reveal via exact artifact/revision/resource id. No automatic document reading added. | Real Spotlight coverage and chosen-hit actions. |
| 16 Organizer | Reuse grouped plan/receipt, conflict rows, expanded review, explicit Apply/Undo and journal recovery. History recall disables old approval and points to recovery. Model-visible tools cannot apply/undo. | Explicitly requested acceptance on a user-selected copy. |
| 17 Readiness | Reuse contextual permission/provider/scope recovery and explicit deep-check action. Add shortcut picker and registered chord label; cloud stays off by default. | Actual permissions/provider states, separately. |
| 18 Diagnostics | Human stage list in Help, last 12 from bounded 32-event journal. Explicit JSON Save dialog exports journal metadata only; no source text, images, geometry, paths, settings or credentials. | Save dialog and failure display on device. |
| 19 Delivery identity | `mini_version.py` is the source of build/version. Native handshake rejects another build. Packaging writes build/revision/source-dirty/helper-hash manifest into bundle and ZIP. Existing bundle id/signing and old recovery packages remain. | A requested .27 build, package inspection and explicit launch. |
| 20 Main reuse | Reuse map below; shared contracts/service already carry Lite operations. Main capability composition and main UI remain gated. | Lite and recipient M3 acceptance, then an explicit main integration request. |

## Reuse map for main RAT

| Layer | Shared implementation | Lite adapter / integration boundary |
| --- | --- | --- |
| Source capture and correction | `translation` capability, `observed_source`, `capture_translation`, `document_intake` | Native selection PID/range bounds and explicit capture UI. Geometry is ephemeral, not an artifact/model argument/default journal field. |
| Source analysis | `source_analysis` capability, typed operation/result schema, literal-evidence verifier | MINI_PROFILE registration and CloudModelClient opt-in. Not enabled in main composition. |
| Routing and execution | ToolGoalRouter → MiniSession → AgentExecutionService → dispatcher; same registered operation for menu and model | Lite profile/scopes/budgets. Main source ref ingress still needs its own integration. |
| Files and organization | Existing finder/organization tools, verifiers, pinned actions, mutation journal | Compact projection and UI approval gesture. No new UI file-moving implementation. |
| Interaction | MiniPresentation owns draft/extent/scroll/selection; geometry policy is pure Python | QML reader/composer, Cocoa hotkey/AX transport, ephemeral pin/history. Main UI not switched. |
| Evidence and stopping | Existing execution ids, observations, verification reports, completion status and budget limits | Sanitized diagnostic export is transport metadata, not a full acceptance run or research evidence. |

The model loop is wired in source through existing AssistantRuntime planning with
MINI_PROFILE operations; direct analysis/style tools also use the same opted-in
client, budget and dispatcher. A direct model-backed tool is still labeled
`direct_tool`, not a completed Agent loop. Literal quotes/hashes and successful
schema checks do not establish semantic correctness. No model or real UI run
was executed for .27. Main integration, recipient M3 and research Stage 0 are
separate and remain unpassed by this iteration.

## Review and delivery

Review base: `4ce8b72b`, the expanded-roadmap commit before this implementation.
Source commits were split by capture, geometry, compact UI/tools, settings/history,
source retry and delivery identity. Do not include unrelated local audit/design
edits or the user's direct-inspection screenshot folder in commits/pushes.

When a build is explicitly requested, use `tools/build_rat_mini_app.sh` so the
helper and Python build match. Building only Python against the old SELECT1
helper will correctly report unavailable shortcut. Open only the intended new
bundle when launch is requested, preserving the .26 package for recovery. Let
the user operate it; do not start an unsolicited test or screenshot tour.
