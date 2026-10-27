# M5.9 live UI — 2026-10-27, Asia/Saigon

User authorized self-test and unlocked Mac. Exact packaged app M5.9 observed.
No new code changes or new provider requests beyond one initial image and one
corrected-source retry. No broad suite run in this continuation.

- Real ASCII composer input BEST-Route.pdf checked before Enter. 1 genuine
  provenance PDF returned; two other Spotlight calls timed out (partial scope).
- Actual Enter invoked open_file through shared service. Preview AX changed
  from public-textedit-input.png to correct BEST-Route.pdf URL/page 1 of 25.
  Corpus origin/hash: ../../../artifacts/rat_mini_m1_20261026/pdf-provenance.json.
- Preview's public screenshot PNG was copied through native UI, then pasted
  into RAT; attachment label confirmed before Enter. Real OCR captured 68 chars.
- Initial cloud translation failed translation_rate_limited. Keyboard edit was
  checked complete before Retry. New captured-text artifact retains original
  input provenance and parent/root hashes; capture_correction_structure PASS.
  Retry reached translation, failed rate limit and retained edited text.
  This validates the contract fix; it is not successful retranslation.
- httpx request/source URLs are absent in current stage log after logging fix.
- Finder getApp timed out again while unlocked. No real drag occurred and no
  native transport receipt exists. Paste success does not count as drop success.
- Observed model calls: 0. Direct tool/service flows only, no real LLM acceptance.

Screenshot validity:
01-finder-result.png matches real UI: verified hit plus partial-scope warning.
02-ocr-edit.png has stale pixels (original OCR while AX reported edited text).
Keep unchanged, DO NOT use as edit-success evidence. After normal LaunchServices
Show of the same running app, 03-ocr-edit-active.png matches clean source and
pending-edit notice. These are real app captures, no compositing/mock answers.
Post-retry state was verified through AX and raw JSON; its screenshot attempt
was blocked because Mac locked again. No completed-product screenshot claimed.

Remaining blockers: translation provider quota, native thumbnail/file drop,
full default-scope Finder coverage, recipient M3 acceptance. Main integration
remains gated. App currently stays running with retained edited source.
