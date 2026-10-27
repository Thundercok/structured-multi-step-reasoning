# M5.11 — bundled English/Vietnamese translation candidate

User selected free, ultra plug-and-play. Default automatic now chooses a bundled
OPUS-MT / Argos en↔vi pair; other languages still use online services and their
limits. No key, interpreter install, server or runtime model download is needed
for this packaged pair. Existing explicit provider settings are preserved.

Includes M5.10 work: up to 3 concurrent cancellable Spotlight scopes, completed
scope coverage, image picker as an explicit alternative to native drop/paste,
optional key setup to Keychain, MyMemory cooldown and quota-recovery message.
M5.10 checkpoint built but not live-tested; it is superseded by M5.11 here.

Shared tools/service/verifiers remain the only business path. Local translation
is a backend of translate_text; capture/correction source refs remain observable.
No main UI integration or Stage 0 change. Agent-LLM calls=0 does not mean zero
model inference: this is real neural machine translation on CPU.

Sources, packaging recipe, licenses and limits: docs/contracts/local_translation.md.
Pinned archives and per-file hashes: tools/rat_translation_models.lock.json and
rat/assets/translation/manifest.json. 168 MB unpacked model resources. CTranslate2
4.8.4 ARM64 runtime installed in a separate temporary build dependency directory.

Real tool checks: 3 public sentences with all cloud calls forbidden by the test
process; output and raw artifacts in real-offline-tool.json. Structural PASS does
not verify semantic quality. Original bad detokenization (residual ▁) is retained
as real-offline-tool-initial-markers.json; fix follows upstream Argos space-marker
normalization while preserving ordinary underscores. After-fix host timings
0.15–0.61s per snippet and peak process RSS ~470 MB are not M3 measurements or a
broad quality evaluation. Two focused chunk regression checks passed. M5.10
parallel/cancel/quota tests passed; Qt sandbox import abort was preserved, and
only the 3 affected Qt checks were rerun outside sandbox (all passed).

Runtime acceptance/status is updated separately after packaged build and UI.
Native floating-thumbnail drag has no successful receipt yet. Screenshot and
recipient-M3 gates remain open until actual results are recorded.
