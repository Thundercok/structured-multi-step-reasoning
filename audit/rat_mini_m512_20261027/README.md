# RAT Mini M5.12 — wrap-up at user's request

Candidate only, NOT accepted as stable/friend-ready. Final package/hash/source
freeze: package.json. Full current state and next steps: status.json.

Free default now bundles OPUS-MT/Argos English↔Vietnamese translation, no key,
Python install, server or model download on recipient machine. Other pairs still
use online providers and their limits. Research/credits/recipe: ../../../docs/contracts/local_translation.md.

Actual packaged UI evidence: M5.11 native image picker→OCR→offline translation,
source edit→correction artifact→retranslation completed (../rat_mini_m511_20261027/live/).
M5.12 typed Hello world. auto-routed to translate_text and produced Chào cả thế
giới. with offline_argos. Matching screenshot: live/screenshots/01-live-offline-translation.png.
No assistant answer was injected. Source was edited as user input. Neural MT
ran locally; Agent-LLM counter=0 is not a claim of no model inference.

Finder remains unresolved: exact real provenance PDF filename, 0/3 roots finished,
all timed out without partial rows in app. Same provider outside app found the
public PDF in Documents, other two roots timed out. Partial rows are now retained
and verified if present, and UI no longer claims no-hit when coverage unfinished.
No Full Disk Access, TCC grants, index settings or security settings changed.

Attempted corpus-only scope check was not executed. FolderDialog added / into
unsaved draft unexpectedly; Escape discarded it. A separate test profile was
prepared for the public folder, but Mac locked and user requested wrap-up. That
profile was reset to defaults. Normal user's settings.json was absent and untouched.
Only the recorded idle test process was stopped; normal-profile launch requested.
No further tests after wrap-up instruction.

Remaining: Finder app-vs-headless diagnosis, physical thumbnail drop, soft-wrap/
translation-quality review, M3 recipient acceptance, then main integration. Shared
contracts/service/backend are implemented; main UI and live Agent planning are
not accepted. Stage 0 unchanged. Ad-hoc signed/not notarized.
