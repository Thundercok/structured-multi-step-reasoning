# RAT Mini M5.9 — candidate, not accepted

LATEST: after unlock, live UI found/opened the real PDF; fresh image OCR and
correction contract passed. Both translation attempts hit provider rate limits.
Native drop unverified (Finder tool timeout), two default roots timed out, Mac
locked again. See live/README.md, status.json and matching screenshots. The
initial pre-unlock notes below are retained as history, not current status.

Package: `../../dist/mini-m59/RAT Mini.zip` (75 MB). Metadata, hash and frozen
source paths are in status.json. Build exited 0, codesign deep/strict verify
exited 0; ZIP contains the M5.9 quick guide. Not notarized.

Real M5.8 UI retry exposed `invalid_object:result` before provider execution.
Correction copied the complete observed capture payload, while its result
contract omitted inherited fields. M5.9 derives the correction contract from
the same capture schema, preserving image provenance and parent/root ancestry.
Two targeted dispatcher regressions passed (clipboard/image; repeated edits
and immutable original); these seeded tests are not UI/OCR/model acceptance.
No global schema validator, research harness, claims or Stage 0 changes.

M5.9 also suppresses httpx/httpcore INFO request URLs (source text can be in
GET query strings). Footer shows “Thả ảnh hoặc ⌘V”. Shared workflow/contracts
remain headless; UI projects the same service/dispatcher results. Main UI is
not wired. The observed direct flows had zero LLM calls, so no real-model
planning/agent-loop acceptance is claimed.

After build, LaunchServices open requested for the exact M5.9 bundle with an
opt-in live evidence directory. No UI acceptance yet: macOS locked again;
user was asked to unlock and keep it open. No new M5.9 screenshot could be
obtained. M5.8 raw screenshots/AX/artifacts remain in ../rat_mini_m58_20261027/
with explicit stale-screenshot caveats. Do not use a mismatching screenshot
as evidence of a successful result.

Remaining narrow checks after unlock:
1. Exact ASCII BEST-Route.pdf in composer; verify text before Enter; open real
   provenance PDF from result. Earlier automation entered `tm BEST-Route.pdf`,
   so no-hits does not establish Finder failure. Outside sandbox Spotlight is
   enabled and mdfind finds the PDF. No OS index/permission changes.
2. One fresh Preview image paste → OCR → edit → retry on M5.9. Inspect actual
   correction parent/root refs and displayed state; quota failure is a failure,
   not a translation success. Google429/MyMemory quota observed in M5.8.
3. Real native floating-thumbnail/file drop and safe local receipt. Finder UI
   automation repeatedly timed out; there is still no native drop receipt.
4. Screenshot matching actual M5.9 state. Friend's M3 test remains pending.

Do not hand off as stable or integrate into main until these gates are met.
