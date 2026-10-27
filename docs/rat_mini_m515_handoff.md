# M5.15 candidate: acceptance and reuse gates

Approved ten-point iteration, 2026-10-27. Source is completed before a bounded
verification batch. Results are recorded separately in audit/rat_mini_m515_20261027.

| # | Scope | Acceptance / limit |
|---|---|---|
| 1 | Tray toggle and reopen same app | Existing native single-click handler + instance bridge; physical tray click requires native UI access. |
| 2 | Screenshot ingress | Drop/file/paste share capture contract; explicit drop activates once; delayed promise cannot present RAT. Physical thumbnail requires actual OS drag evidence. |
| 3 | Hide and retain | Esc/app change/copy/open hide the group; no background completion activation; keep draft/OCR/result. Native dialogs and drag own focus temporarily. |
| 4 | Workbench | Existing fixed 122×128 mascot and side placement; sticky OCR Back; geometry masks. Physical click-through / monitors remain distinct acceptance. |
| 5 | Recipient M3 | NOT ACCEPTED until real recipient hardware run. No remote access to that Mac in this session. |
| 6 | Reuse in main | Shared engines/contracts/dispatcher ready for review; actual main composition deferred until Mini + M3 gates pass. |
| 7 | Folder organization | Preview → explicit Apply → durable receipt → explicit Undo, scoped/nonrecursive/no overwrite. See contracts/rat_mini_organization.md. |
| 8 | Hello setup | First welcome → local readiness → Start; reopen via menu/tray. Optional missing features do not block all use. Deep hash checks only on explicit button. |
| 9 | Minor UI | Retain paper+rat/one composer; preview and action labels, readiness status, contextual recovery. Version visible as M5.15. |
| 10 | One final acceptance/package | Bounded software checks then real UI/backend, screenshots, one app+ZIP; clearly separate candidate, pass and unverified. |

M3 handoff: extract ZIP → move app to Applications → open → Hello → check local
components → Start. Translate one short public English paragraph; capture with
⌘⇧4, wait for file or drag thumbnail; paste an image; correct OCR and translate;
find one known permitted file and open it. For organizer, use COPIES in a selected
test folder added in Settings; inspect preview, Apply, Undo, verify originals.
Switch apps and recall; check draft retained; confirm RAT does not steal focus.
Record OS version and failure text. No terminal, Python install or API key needed
for bundled English↔Vietnamese. Ad hoc signed candidate is not notarized.

Reuse map: engine/folder_organization.py and kernel/capabilities/folder_organizer.py
are Qt-free. mini_readiness.py and mini_setup.py share setup observations.
mini.py is composition; goal_routing.py compiles clear goals; mini_worker.py carries
trusted approval separately from model args; mini_quick_controller.py projects
artifacts. mini_shell/image_drop keep native focus behavior in UI adapters.
Main integration must register these capabilities through main's chosen profile,
connect approval gestures and artifact projection, then independently verify
Agent execution. Registration alone is not evidence of live model planning.
Stage 0 and research claims unchanged. No main registry expansion this turn.

Rollback: retain dist/mini-m514-ready/RAT Mini.app and its ZIP. Settings add only
setup_completed; organization journals are separate and retained on rollback.
Finish/undo active organization using M5.15 before rollback. Do not delete journals
or recovery material as build cleanup.

## UX gate reopened, 2026-10-27

User reports dissatisfaction across invocation/dismissal, layout/mascot and
input/image/results. Earlier personal verification does not accept overall UX.
Testing is paused explicitly. Proposed next scope: rat_mini_m516_ux_plan.md.
Keep M5.15 as candidate; do not advance M3/main gates from software checks.
