# RAT Lite .23 — stable layout, source implementation

User explicitly deferred mode unification to backlog and authorized the ten-item
stable-layout plan. Full implementation mapping and constraints:
`docs/rat_lite_stable_layout_20261029.md`.

Read-only process inventory identified QA20 PID7562 at
`dist/rat-lite-20261029-observable/RAT Lite QA20.app/Contents/MacOS/RAT Lite QA20`.
This is not .22/.23. No app was stopped, replaced, activated or driven in this
iteration. Source menu now identifies runtime BUILD/PID, with the bundle version
using the same BUILD constant rather than a separate hard-coded version.

Source changes: retained busy geometry; shared220/380/580 width tiers; upward
growth from constant character envelope; stable side before relocation; a
min(300px,38% available height) reader budget; premeasurement at target width;
fixed status location and quieter idle background; selection/focus/menu/scroll
included in peek engagement. Existing contracts, dispatcher, pending handling,
scroll/selection storage and explicit reading expansion are reused.

No tests, smoke checks, UI tour, screenshots or native acceptance were run.
Packaging is recorded in build.log and does not validate live QML behavior or
smoothness. Historical checks do not count as verification of this revision.
Native resize/paint continuity, constrained-screen wrapping, status contrast
and complete source→read→close→recall behavior remain unverified.

Packaging completed with exit0 at `dist/rat-lite-20261029-stable-layout/`
(app and ZIP). No native run is implied. Existing QA20 is retained
for the user's session. No automatic future test/acceptance permission follows.
Default LLM off, main integration, M3 and Stage0 gates are unchanged.
