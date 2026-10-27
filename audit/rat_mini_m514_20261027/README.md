# RAT Mini M5.14 — bounded acceptance, 2026-10-27

Later explicit cleanup request: generated intermediate build bundles/unpacked
duplicates from this session were removed; raw audit evidence and source remain.
Latest ready app/ZIP and M5.13 rollback ZIP were preserved and latest ZIP hash
rechecked. Manifest: cleanup_generated_builds_20261027.json (3.78 GiB removed).
Historical statements about preserving candidate bundles refer to pre-cleanup.

Deliverable: dist/mini-m514-ready/RAT Mini.zip, 0.5.14 / 20261027.11,
ARM64/macOS 14+, ad-hoc signed/not notarized. Hashes: package.json.
Candidate for recipient testing, not broad stability or M3 acceptance.

Implemented: no always-on-top; explicit activation; Qt + native macOS activation
dismissal with menu/dialog/drag ownership guards; copy/open/reveal/Esc/Cmd+W hide
without clearing in-memory state. Background results don't reopen RAT. Tray left
click toggle/right click actions is opt-in, preserving main's old default.

One paper surface; OCR edit/image inspection replace result; final Back control
stays above scrolling body. Fixed 122×128 RAT; stable side docking, screen edges,
negative monitor origins, restore user home, reduced motion, masked gap.

Shared NMT: sentence segmentation, beam 4/coverage penalty 0.2, bounded 256-token
source units. Cancellation between units. Same bundled models. Structure checks
do not certify semantic correctness. Spotlight: one timeout retry per scope
inside 12 s, no scope expansion or filesystem fallback; removed an unbounded
protected-directory open preflight. Every hit still gets normal read/identity/
scope verification. No permissions reset, full-disk grant or index rebuild.

## Software checks and failures

Initial source work preceded checks; only failed/changed sections repeated.
contracts.log: 13 passed, one failure, 14 deselected. qml-failure-detail.log
identified Cocoa NSView conversion on an offscreen id. Added Cocoa guard;
qml-repair.log passed. shell-repair.log/native-focus-contract.log passed the
changed lifecycle contract. finder-repair.log/finder-preflight-repair.log each
passed three selected timeout/retry/cancellation checks. Synthetic fixtures are
software contracts, not UI/model acceptance. No broad/research suite ran.

Early .8 candidate needed explicit activation. .9 added it; .10 added native
activation and fixed Back navigation; .11 removed the blocking Finder preflight.
All candidates/failures retained. A .9 Finder run stalled ~230 s then returned
cancelled:finder: live-final/mini-d66a82fd1e174d0187434770fc862af5.json.
The bounded native sampling attempt timed out and proved no complete OS cause.

## Actual UI evidence

Build .9 (same NMT/controller/result display as final .11):
- Exact typed input: Hello world. This is a short public text for translation.
- Actual offline output: Xin chào thế giới. Đây là một văn bản công cộng ngắn để dịch.
  The old world/public omissions are absent in this sample, not a broad quality claim.
- Copy dismissed RAT; explicit recall retained result and Unsent public draft.
- Copied the real public PNG from Preview, then Cmd+V in RAT. OCR/translation
  started without Enter; provenance clipboard_image. Image/provenance origin:
  audit/rat_mini_m57_20261027/public-textedit-input.png. Toolbar noise remained.
- OCR editor replaced result. Entered clean public source as user input, verified
  field before Retry; shared correction artifact → source_ref → translate returned
  Xin chào thế giới. / Đây là một văn bản công cộng ngắn để dịch.
  No assistant answer injected. Raw observations/lineage: live-final/*.json.
- Image inspection worked in body; Back scrolled away in .9. Final source puts
  it outside the scroll body; bundled QML hash matches. Last Back adjustment
  wasn't separately re-exercised on a long image in .11.
- Actual screenshots: live-final/screenshots/01-idle.png, 02-translation.png,
  03-image-paste.png, 04-edit-replaces-result.png, 05-corrected-translation.png,
  06-image-inspection.png.

Final build .11:
- Found actual BEST-Route.pdf, 3/3 default roots complete, 7,973 ms, one bounded
  timeout retry. Raw: live-ready/mini-b99518fb660b428b834d7a4c92236d3f.json.
- Native outside activation triggered hide; background Finder finished without
  reopening; explicit recall retained result. One CUA capture reported
  ScreenCaptureKit -3811 during hide; app continued, recall worked. No capture
  permissions changed.
- Clicked Open PDF through tool. Preview showed correct corpus URL/page 1 of 25.
  Evidence: live-ready/02-opened-pdf-ax.txt and open_file artifact/stages.log.
- Product screenshot: live-ready/screenshots/01-finder-complete.png.

PDF origin: https://arxiv.org/pdf/2506.22716; local
artifacts/rat_mini_m1_20261026/corpus/BEST-Route.pdf; SHA256
9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c.

## Remaining

Physical thumbnail drag/slow promises, physical gap click-through, real
multi-monitor drag, native tray single click, native dialog/drag focus edge
cases, M3 recipient, broad translation quality and notarization remain pending.
Don't infer those from software geometry/state checks.

Shared capabilities/dispatcher/execution/verification are in use. Observed Agent
LLM calls were zero; neural MT inference was real. Main UI/live Agent planning
aren't accepted; research/Stage 0 unchanged. Normal settings untouched, profiles
isolated here. No Git push/new branch. Finder receipt's legacy M5.13 label is
inherited; bundle build/transport v3 identify this run. Final process cleanup and
normal launch are recorded separately in cleanup.json.
