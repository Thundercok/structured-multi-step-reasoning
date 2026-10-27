# RAT Mini M5 — implementation/build handoff, NOT tested

User explicitly prohibited tests, smoke runs, UI acceptance and screenshots
unless requested. None were run for M5. Packaging is not runtime evidence.
Prior M2–M4 results must not be used as acceptance of these changes.

Implemented in source:
- Option+Shift+D emits a queued GUI signal, hides RAT, then schedules the
  shared capture_text(region) tool. Captured OCR artifact is passed by source_ref
  to translate_text through AgentExecutionService. Cancel/empty capture never
  uses stale clipboard text as fallback.
- Capture completion remembers cursor position; region results are presented
  near that position without an explicit requestActivate.
- Composer paste adapter snapshots text/local file references/image pixels.
  Text origin and previous successful operation inform the reusable headless
  goal router. Pasted image remains a removable draft until Enter, then uses
  capture_text(image) and the same translation tool. Images are trusted local
  input context, never model-visible capture arguments.
- Composer remains one input without mode selection; submitted draft clears.
  Clipboard translation remains a separate secondary menu action.
- Mascot is anchored 12px inside composer left; hint follows its right edge.

Composition: Finder and Translation capabilities only. Main profile does not
use the new ingress router yet. Cloud loop wiring is retained, not verified
with a real model here. No Stage 0/research claims changed.

Build: tools/build_rat_mini_app.sh, output dist/mini-m5/. Build script no longer
runs the former runtime-import smoke. No app launch, permission interaction,
provider call, OCR capture, test suite or live conversation was performed.

Known limits: inference of ambiguous text is heuristic, with clarification when
needed. OCR quality, focus behavior, hotkey/TCC permissions, rendering and the
new paste paths await user-authorized testing. App is ad-hoc signed, not notarized.
