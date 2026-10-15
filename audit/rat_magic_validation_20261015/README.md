# RAT local implementation validation — 2026-10-15

This packet records product development validation. It establishes no NCKH
model-quality result, benchmark, Stage 0 pass, or native GUI/model equivalence.
Research changes already present in the shared checkout were not part of this
implementation. DocAI remains deferred.

## Implemented and tested

- One bottom composer; lower screen placement and upward growth; editor/draft
  continuity. Optional debug controls through `RAT_DEBUG_UI=1`.
- Existing indexed-file delivery with hash/fingerprint checks, actual file rows,
  click/keyboard opening, missing-file handling, and no automatic external open.
- Filename matching preserves digits and normalizes punctuation/accents/case;
  missing indexed paths are filtered. Filename literals do not return arbitrary PDFs.
- Coherent context compilation, typed-origin and current-execution proof scope,
  revision pins, compact model facts, and actual native tool observations.
- Natural pending questions/cancellation/dismissal; accepted answer repairs reopen
  remaining tools. Failure status is metadata, not fabricated assistant dialogue.
- Direct app actor with core document schemas and committed-receipt tool discovery.
  Default public planner retains rich typed outcomes; operation-list wire is an
  explicit diagnostic opt-in. Invalid planner declarations retain invalid attribution.

## Software evidence

Round 2: **479 core tests + 122 UI tests passed**, plus 3 UI subtests. Source
hashes were stable throughout the run. Commands, hashes, and full fixture logs
are in `round2/software_validation.json`, `round2/core.txt`, and `round2/ui.txt`.

Two explicit exclusions remain visible in the commands and manifest:

1. An archived contract probe accepts a fluent answer with an unmet effect; the
   new continuation/termination behavior is covered by current recovery tests.
2. An unchanged legacy MetaReasoner test expects valid verification of incomplete
   arithmetic and a canned policy. This is outside the current AssistantRuntime
   and UI rendering path. Its failure is retained in round 1; unchanged source
   fingerprints relative to the checkpoint are recorded in `legacy_vgc_scope.json`.

Initial failures are preserved in this directory's first-round logs/manifest.
The regression run is not a claim that all tests in the repository pass.

The later collector-only delta adds an explicit `--native-limits` opt-in for
8 steps/90 seconds, matching the GUI's per-turn caps while retaining the global
15-call budget. Defaults remain 5/60. Its 16 tests passed; this overlaps the core
suite rather than adding 16 distinct cases. See `collector_native_limits_validation.json`.

## Actual-file evidence and model limit

Real indexed PDFs were tested with a read-only personal index; no original PDF
was copied or uploaded. Dispatcher tests located/read a real page, matched pypdf
text exactly, and handed over a local reference with unchanged hash and size.
A Qt render showed the actual delivery artifact with a bottom composer; click
and Enter passed the exact path to a patched opener. External PDF viewer opening
and native GUI/model equivalence have not been observed.

Latest model development runs are summarized without document contents or paths
in `model_review_sanitized.json`. **End-to-end model acceptance was not achieved.**
The 4B model found/read the real page but timed out; the 1.5B default omitted work
or made an unsupported scanned-file claim. Runtime error=null is not a quality
verdict. Missing token counts remain unknown; client wall times are not full
inference costs or a controlled model comparison. The final run13 used the GUI's 8-step/90-second per-call caps, with 15 global
calls. The initial summary timed out; subsequent page search/read and original
file delivery succeeded. The page read was a 1000-character prefix of 1489
characters. The quoted characters match after PDF extraction whitespace removal
(not a byte-exact match); page 1 and original path/hash/size were checked.
Those two turns took 105.50 and 86.41 seconds client wall time. This remains a
failed whole-workflow acceptance and an unacceptable latency for the requested
immersive experience. The actual model-produced answer/artifact were separately
replayed through Qt with click/Enter to a patched opener; this does not establish
a live native GUI/model run. Temporary servers were stopped and saved model
settings were not changed.

Raw observations, exact-file checks, UI image, and private reviews remain under
`/private/tmp/rat-local-file-*`; no raw document text is included in this packet.
Prior exposed development failures are preserved. The implementation is packaged on `codex/rat-magic-workflow-20261015`,
continuing the approved source checkpoint. Personal documents and raw model
observations remain excluded.
