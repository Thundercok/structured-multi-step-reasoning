# M5.16 — source implementation, awaiting validation

2026-10-27. User authorized implementing docs/rat_mini_m516_ux_plan.md and
explicitly paused tests. Source edits and manual source review only. No pytest,
compile/smoke, real UI run, screenshots, package build or main integration was
performed for M5.16. Existing M5.15 results do not validate these changes.
The existing distributable remains M5.15. Future build metadata is prepared for
0.5.16 / 20261027.13; there is no M5.16 app or ZIP to hand off yet.

## Implemented in source

| Area | Change |
|---|---|
| Presentation | mini_presentation.py owns a single visible surface: result, OCR edit, image inspection, original capture, welcome/help or settings. Business phase, task ID, visibility and per-surface scroll state are separate. Background completion does not change the surface the user is reading. |
| Drafts | Controller owns composer draft. Editing a submitted request retains the independent next-request draft; submit/cancel restores it. Image ingress consumes only the instruction snapshot still matching the draft. Empty send does not clear input. |
| Keyboard | Composer Enter submits; Shift+Enter inserts a newline. Finder Enter/⌘Enter requires focus in its own list. Selection alone cannot capture composer Enter. |
| Workbench | One scrolling content area and action footer outside it. Compact panel 440, expanded 520 logical pixels, constrained to usable screen. Content area yields space before the outer panel exceeds screen height. |
| Mascot | 122×128 logical pixels. Expanded top anchor and chosen side persist across content changes, subject to screen bounds; no 300-pixel threshold that relocates the mascot. Drag translates remembered home instead of replacing home with the temporary dock position. |
| Focus | Native menus, combo popups, pickers and drag own focus temporarily. Welcome/help/settings content itself does not exempt app-change dismissal. Second launch of the same bundle is recognized as recall, rather than a different application PID. Background result presentation remains disabled. |
| Image/OCR | Shared capture/translation tools retained. OCR edit, full image and original capture replace the result at the same location. Back preserves edited text and scroll; an older translation is labelled when OCR draft differs. |
| Finder | Mini-specific compact rows, five initial hits, explicit selection and open/reveal actions. Main FinderResultsView remains unchanged by this iteration. Partial coverage is retained; found files stay usable. |
| Organizer | Preview grouped by destination, details expandable. Apply/Undo pinned below the scroll and still use exact observed artifact + trusted approval via existing dispatcher. Outdated UI pins invalidated when folder scopes change. No file moves during this source work. |
| Errors/settings | Contextual image/settings/retry/journal recovery; retained source and result on retry failures. Save settings preserves visible result and pending clarification. Readiness uses the same registered tool in a separate runtime to avoid dismissing the business session's pending question. |
| Hello | Short inline welcome with direct Start. Help shows three user-facing groups; technical component details expandable. Default settings show target language and chosen folders, with services/key/model under Advanced. |

Visible identifier: M5.16 source in window/tray/menu. Paper, palette, existing
QuietButton and DeskIcon components retained. No new Qt asset data entry needed;
new Python presentation module is imported from controller for future packaging.

## Files and boundaries

- rat/ui/mini_presentation.py: pure UI navigation, per-task scroll and return paths.
- rat/ui/mini_quick_controller.py: draft/task projection, shared tool adapters,
  contextual recovery and readiness observation projection.
- rat/ui/quick/MiniDesk.qml: layout, keyboard ownership, unified surfaces and
  sticky action footer; explicit native pickers remain.
- rat/ui/mini_shell.py and mini_placement.py: transient focus and placement policy.
- rat/ui/mini_quick.py: source version label.
- tools/build_rat_mini_app.sh: future version metadata only; not executed.

No translation engine, routing/model prompt, organizer filesystem implementation,
Agent service/dispatcher, main registry, research harness or Stage 0 change.
This does not establish live model planning or improved translation quality.

## Pending, only after explicit permission

Manual source review is not syntax/runtime acceptance. Update existing UI contract
fixtures for surface navigation (old showOcrEditor/showImagePreview flags and
Hello dialog assumptions changed), then perform one bounded verification batch.
Check initial/recall focus, menus/pickers/cancel, app-change dismissal, drag at
screen edges, edited request vs next draft, paste/drop instruction ownership,
OCR edit→image→Back, long Organizer preview actions and help during a pending
clarification. Validate actual QML sizing/scroll/focus on the live native backend.
Use genuine public files and actual offline translation, preserving observed
failures and new screenshots. Native tool access, physical thumbnail drag, M3,
notarization and main integration remain separate acceptance gates.

## User observation and revised acceptance preference

User has seen the new Hello and provided a screenshot of the source UI showing
a translation-local-unavailable message. Translation is not accepted; root cause
is not diagnosed from this screenshot alone. Artifact: audit/rat_mini_m516_preview/
user-translation-error.png. The source preview was opened later on explicit
screenshot request; native capture attempts failed. User now requests opening
only, with user-operated acceptance, unless a later specific check is authorized.

## Production layout restoration — 2026-10-27, source only

The user rejected the broad M5.16 visual rewrite. This update supersedes the
440/520-width panel and permanent header described above; the state/controller
improvements remain. The reference is the main RAT production entry
`rat/ui/quick_app.py` loading `rat/ui/quick/PDFDesk.qml`, with local history
`fb330db7` (Build 2026.10.25.33). Neither M5.15 nor an older Mini bundle was
selected as the visual baseline.

MiniDesk now follows that production structure: a 580-pixel bottom composer
(screen constrained), radius 18 and minimum height 94; a result paper inset
128 pixels on the mascot side, radius 16, overlapping the composer by 22;
and the slightly rotated backing sheets. The header belongs to the visible
paper only. Attachment, menu and hide controls sit on the composer's lower
row, beside a small `Mini · M5.16 · RAT` source identifier/drag handle. The
short Hello retains its copy and direct Start action on an auxiliary sheet.

The existing presentation, independent next draft/request edit, focus-owned
Enter behavior, retained OCR/results, Back navigation, scroll and quiet
background completion are preserved in source. Apply/Undo remain outside the
scrolling paper and call the same controller methods with the existing artifact
pins. Placement uses the paper's side gutter for the unchanged 122×128 mascot;
full-width auxiliary sheets retain the external side dock. Expanded top/side
memory and drag-home handling remain in MiniShell.

Changed source: MiniDesk.qml, mini_shell.py, mini_placement.py. No production
main UI, service, reasoning tool contract, dispatcher, verifier, routing or model
loop was changed. This presentation revision supplies no new evidence of live
Agent/model planning. Main UI integration and recipient M3 acceptance stay gated;
research scope and Stage 0 are unchanged.

Only source reading/editing was performed. No tests, syntax/QML smoke, app
launch, UI tour, screenshot, build or ZIP was run or created. The existing
distributable is still `dist/mini-m515/RAT Mini.app`; it does not contain this
revision. The user's translation-local-unavailable observation remains unresolved;
this layout change neither diagnoses nor fixes it. Source preview state remains
at `audit/rat_mini_m516_preview/state`. Open the source app only when requested,
then let the user operate it and report observations.

## Explicitly requested bounded validation and build — 2026-10-27

The user subsequently authorized tests, opening the app, screenshot and build
with token conservation. Updated the obsolete fixture assumptions for unselected
Finder focus and surface navigation; added the paper-gutter placement check.
17 software checks passed, 2 unrelated checks deselected. Initial sandbox Qt
import aborted; the same bounded group passed with native macOS access. Logs:
`audit/rat_mini_m516_restoration/tests-native.log` (initial abort retained).

Built `dist/mini-m516/RAT Mini.app` and `RAT Mini.zip`; build log and SHA-256
are recorded in `audit/rat_mini_m516_restoration/status.json`. Ad-hoc signature
verification passed; this is not notarization or recipient/M3 acceptance.
M5.15 remains preserved. This supersedes the earlier no-M5.16-build status.

Opened that exact app using its absolute path. Live Hello appeared; clicked
Start, entered `Dịch sang tiếng Việt: Hello world.` and pressed Return. Actual
UI reported `Đang thực hiện thao tác translate_text…`. The next combined
state/screenshot call timed out (-10005); screenshot-only fallback and final
state read also timed out. No screenshot was obtained, and translation completion
or failure is unconfirmed. No fabricated output or substitute screenshot was
used. Stopped retries and left the app running for the user. This does not
resolve the earlier source-preview translation error or establish live Agent
model planning. Main integration, M3 and research gates remain unchanged.

## Follow-up: lightweight Agent wiring, source only

After the M5.16 build the user approved connecting the reasoning loop and asked
for minimal weight. See [Agent loop source handoff](rat_mini_agent_loop.md).
Mini now enables the shared compact model planner only on the Agent lane;
one-step tool requests keep their deterministic lifecycle. This follow-up has
not been tested, launched or packaged. The existing M5.16 app/ZIP and earlier
17 checks do not include/validate these changes. No live planning claim yet.

## Look standby/C/B — later source implementation

User approved original standing standby, C for short results and B for paragraphs.
Look now has a separate no-input surface, original-sprite crops, bounded speech
bubble and independent edge placement. Quick image translation uses the same
capture/translation tools and preserves the hidden draft. Source label is
'RAT Mini · Look source'. See docs/rat_mini_look_modes.md for exact scope/limits.
No tests, launch, screenshot or build for this revision; existing M5.16 bundle
and its earlier 17 checks do not validate it. Main/M3/Stage 0 gates unchanged.
