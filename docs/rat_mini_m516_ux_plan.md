# M5.16 proposal — coherent Mini UX rework

2026-10-27: user is dissatisfied with all three areas: invocation/dismissal,
layout/mascot, and input/image/results. Pause tests. This document is a proposed
next implementation scope, not completed source or UX acceptance. M5.15 remains
a candidate. Earlier user verification is not overall satisfaction or M3 approval.
No new business capability, main integration, test, app launch or package in this
planning turn. Shared reasoning tools/dispatcher/verifiers remain authoritative.

## Experience contract

A temporary workspace: invoke intentionally, enter/drop/paste once, see progress
and a usable result, then dismiss without losing work. One composer, one primary
action per state, one content surface. Keep paper + fixed-size mascot. Content
length changes the scrollable surface, not mascot size or remembered home.

| State | Content surface | Primary action | Retained state |
|---|---|---|---|
| Hidden | None; tray remains | Explicit recall | Request, composer draft, image, edited OCR, result, scroll position |
| Ready | Compact composer | Send | Last task can be recalled explicitly |
| Working | Attachment/request context + local status | Stop | Submitted snapshot and independent next-request draft |
| Result | Translation, file list, or organization preview | Contextual task action | Source and result stay associated |
| Editing OCR | Editor replaces result; source preview available | Translate edited text | Uncommitted edit survives back/hide |
| Inspecting image | Image replaces result; fixed Back | Back to result/edit | Same task and edited text |
| Needs input / error | Specific question or explanation beside retained request | Answer / appropriate recovery | No re-entering or re-dropping required |
| Setup | Short welcome/help surface | Start / fix one relevant issue | Existing session not replaced by diagnostic output |

Model the presentation as one surface state rather than several independent
visibility flags. Business execution phase, task identity and visibility are
separate: hiding never cancels or creates another task; completion never implies
permission to show or activate. Menus/native pickers/drag have explicit ownership.
Do not expose internal reasoning or technical contracts in normal UX.

## 1. Invocation, dismissal and focus

- Tray click and reopening app recall the same session; do not clear a draft.
- Esc/click outside/actual app change hide the group. Preserve approved copy/open
  completion dismissal. Own menus/pickers and active drop must not dismiss it.
- A direct accepted drop is one engagement; delayed promised image completion is
  not another engagement. Background completion remains quiet.
- Decide window placement once on invocation/task expansion; avoid repeated moves
  while text wraps or progress changes. Retain user's home and chosen side.
- Native-dialog cancellation returns to the same surface and draft.

## 2. Paper, mascot and hierarchy

- Fixed 122×128 mascot; compact composer at remembered position.
- Expanded workbench has stable header, one scrolling content area and reachable
  actions. Mascot moves once to an available side near the top, then stays.
- At an edge, choose opposite side or shift workbench within usable screen bounds.
  Collapse restores home. Do not resize the mascot to solve a layout problem.
- Header communicates task/status; source summary uses one line + small thumbnail.
  Remove duplicate names, repeated instructions and competing collapse controls.
- Setup/help should not leave a large empty workbench behind it.

## 3. Composer and keyboard

- Enter submits the composer. Opening a file with Enter requires focus in the
  result list; an old selected result must not unexpectedly capture composer Enter.
- Shift+Enter inserts newline. Pasted text remains editable; submitting/dropping an
  image snapshots the instruction once. Keyboard focus is visible and predictable.
- Submitted request remains in task context; 'Sửa yêu cầu' restores it for editing.
  Keep an independent next-request draft so recall/retry cannot overwrite it.
- Prefer contextual recovery to a generic retry of an unrelated previous task.

## 4. Image, OCR and translation

- Drop/file picker/paste converge on the same capture tool contract.
- Immediate thumbnail then 'Đang đọc chữ…' then 'Đang dịch…', automatically.
- Source preview and OCR editing each replace the result surface, with a fixed
  Back path. Keep edited text when going back, hiding or retrying a provider.
- Distinguish original capture, edited source and current translation. Indicate
  when displayed translation predates the edit. Never silently re-OCR over edits.
- Error actions stay beside context: retry, change image, or adjust language.

## 5. Finder and Organizer results

- Finder: concise rows, clear selection/open affordance and bounded list; source
  scope/partial coverage readable without technical provider jargon.
- Organizer: folder + rule + move/skip counts first; group preview by destination,
  expandable detail. Keep Apply reachable outside the long scroll, pinned to the
  exact preview. Receipt explains moved/skipped/conflicts and offers explicit Undo.
- Current source puts Apply after up to 100 preview rows; revise that placement.
- Choosing an unsupported scope should provide the next action locally; do not
  silently extend permission scope or move files as a side effect of choosing.

## 6. Hello, settings and recovery

- Welcome teaches one task in a few lines. Only show blockers relevant to the
  feature being used. Move engine/model/hash detail into expandable diagnostics.
- Default settings: target language and allowed folders. Advanced services stay
  secondary. No blanket Full Disk Access, Accessibility or Screen Recording gate.
- Reopening help preserves current work; readiness observations never replace a
  translation or organization result. Deep checks only on explicit request.

## Implementation order and review gate

1. Specify surface transitions, keyboard ownership and retained task/draft data.
2. Refactor UI projection/state ownership without changing tool business logic.
3. Implement compact/expanded layout and stable mascot placement.
4. Join composer/image/OCR/results/recovery into the state contract.
5. Simplify Hello/settings; expose only necessary actions in each state.
6. Source review, then ask for explicit permission before tests, live UI or build.

Before later acceptance, user reviews the proposed visible states/layout. Later
real acceptance must cover recall/dismissal, image ingress, OCR edit/back, Finder
keyboard behavior, Organizer preview/apply/undo and actual product screenshots.
Native tool failures are recorded, not replaced by fabricated successful UI.
M3 and main integration remain separate gates. No test permission inferred from
'go on' or from this plan.

## Source implementation update

User authorized implementation with “ok do it”. Source work is documented in
rat_mini_m516_implementation.md. The proposed six areas have source changes;
no tests, live UI/screenshot or build were run. UX acceptance remains open.

## Revised visual direction — 2026-10-27

User rejected the broad visual redesign after seeing M5.16. Preserve the logic
improvements, but use main RAT's production PDFDesk.qml (loaded by quick_app.py,
Build 2026.10.25.33) as the layout baseline: bottom composer and offset overlapping
paper with backing sheets. The 440/520 panel and permanent header above are
superseded. Keep short Hello, pinned artifact actions and explicit Back paths.
Restoration is source only; see rat_mini_m516_implementation.md. No automatic
tests, launch, screenshots or packaging; user operates the app when opened on
request. M5.15 evidence does not validate this revision.
