# RAT Lite — next iteration while .24 is being tried

2026-10-29. User asked to continue planning while manually trying .24. This
document is planning only. .24 has been packaged/launched; no user feedback or
acceptance result has yet been supplied in this chat. Keep its running app,
settings and source unchanged while planning. Do not launch another candidate.

## Priority and size

First resolve any reported startup, typing, hidden-result or focus failure.
Then address disruptive movement or lost reading context. Refine task-specific
clarity after the basic interaction is usable. Additional capabilities and main
integration are outside this iteration. One concern per small commit; no bulk
rewrite of the controller or QML file.

The next build number is assigned when its actual scope is fixed. These items
are candidates, not a promise to bundle them all into .25.

## 1. Close the continuity gaps found during .24 use

Map each actual observation to its transition: compose → working, working →
result/error, read → expanded, expanded → compact, pending preview → recall,
hide → recall, or an owned dialog/menu. Record expected behavior, observed
behavior, build and the smallest relevant code area. Keep proposed fixes separate
from user observations. A screenshot shows a state, not the full transition.

Source-review questions to resolve against feedback:

- Does keyboard focus follow the single editor when it changes parent? Does
  returning from source/image/settings restore the intended input or reader?
- Does retaining geometry leave too little reader space or unnecessary blank
  space? Separate the stable outer body from the allocation between reader,
  composer and action rail; prefer reducing the scroll viewport to moving RAT.
- Does opening pending then recalling current work restore the previous extent
  as well as reading position? .24 preview explicitly requests compact extent;
  a separate return-context record may be needed for expanded reading.
- Are copy/selection and outside-click dismissal consistent across compact and
  expanded? Treat hide, close preview, stop task and stop listening as separate
  events even when their controls are nearby.

For a confirmed failure, change only its state/placement boundary first. Keep
the paper, seated mascot scale and one editor so the result is recognizable.

## 2. Make compact results useful for every enabled tool

.24's compact text projection primarily suits translation. Its existing
`look_projection()` mostly chooses summary/text/status; Finder cards and folder
approval details remain in the expanded task. This is a source-level limitation,
not a claim that a user has already encountered a failure.

Proposed next change: a Qt-free task presentation projection, derived solely
from actual execution observations and artifact references:

| Result | Compact content | Next action |
| --- | --- | --- |
| Translation | Actual translated text, partial/OCR-edit caveat when applicable | Copy; expand for source/editing |
| File search | Actual returned count, partial coverage when reported, short selected-hit label when available | View files; open only through existing selected-hit dispatch |
| Folder preview | Explicit `Bản xem trước`, scoped folder and proposed operation count from the plan | Review expanded preview; retain explicit Apply there |
| Folder apply/undo | Actual completion/partial/failure and receipt-backed state | View receipt or explicit existing Undo |
| Clarification | Actual question and same composer | Send the answer through pending-input handling |
| Error/partial | Actual failure or incompleteness with retained source | One relevant recovery action |
| Agent response | Public conclusion and actual completion status | Inspect tool evidence when available |

The projection carries task/artifact identity and action IDs. QML renders and
emits gestures; the controller resolves actions to the existing dispatcher and
approval contracts. Never infer success from an operation name, a busy label or
the presence of a registered tool. Do not invent counters or progress percentages.

Implement in small parts: projection contract → translation/Finder projection →
organization projection → contextual labels/actions. Keep verification notices
honest: structural/hash verification does not certify translation meaning or
OCR accuracy. No raw/private model reasoning in the UI.

## 3. Reduce interaction ambiguity after correctness is stable

Use task-specific labels such as `Xem file`, `Xem bản sắp xếp`, or `Xem nguồn`
where they better explain the existing expansion action. Prioritize a small
action set: Close, Copy where valid, one contextual action, and More. Keep Stop
visible during execution; composing the next draft remains available. Review
rail height against retained compact geometry before adding any controls.

The Clipboard badge means pending input. It must not look like execution,
completion or unread output. Listening status belongs in the secondary menu;
show an inline explanation when the user first explicitly enables it. Any
remembered listening preference would require a separate decision: .24 starts
off, and this plan does not authorize background monitoring on future launches.

For reading continuity beyond translation, consider an artifact/revision plus
text-block identifier, UTF-16 offset and pixel offset instead of matching whole
rendered strings. Partial prefixes, public summaries and source/result text have
different identities. Retain per-view scroll as fallback. Do not apply offsets
from one artifact or revision to another.

## Handoff and verification boundary

Wait for the user's .24 feedback before choosing or implementing the next
candidate. Any user-reported blocker takes precedence over the order above.
Small documentation commits/pushes are authorized by README/AGENTS. This planning
request does not authorize tests, screenshots, a new build, app relaunch or an
automated UI tour. A later requested check must target the changed transition;
manual observations do not establish all capabilities or a live Agent loop.

Current model execution, main reuse, recipient M3 and research Stage 0 retain
their existing evidence gates. Shared reasoning tools/service/artifacts remain
the execution path for all proposed task actions.
