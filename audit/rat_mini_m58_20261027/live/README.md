# Live evidence and limits

Public input: ../../rat_mini_m57_20261027/public-textedit-input.png (actual
TextEdit screenshot; see its provenance JSON). Copied through real Preview UI,
pasted through RAT UI, Enter submitted capture/translation tools. This is not
physical screenshot-thumbnail or file drag acceptance.

- mini-45207a9eeab4412488969fbabe01aebe.json: actual OCR + MyMemory translation,
  Google429, structural verifier PASS, 0 LLM calls. Semantic quality not verified.
- mini-f10594ba06ea423495715a132e9765e5.json: actual fresh OCR, cloud rate limit.
- mini-f10669f1e49d4584a76bcbdb1c6d2605.json: fresh source correction failed
  invalid_object:result before provider; inherited capture fields missing in
  correction contract. M5.9 fixes contract without altering global validator.
- 03-ocr-edit-pending.png: actual edited source and stale-answer hidden state.
- 04-expired-source-keeps-edit.png: expired source refusal with draft retained.

IMPORTANT screenshot validity: 02-clipboard-translation.png shows stale idle
pixels despite AX reporting the real translation; it is NOT a successful
translation screenshot. 05-correction-contract-error.png also has stale pixels
from the preceding rate-limit view and is NOT visual evidence of the contract
error. Corresponding text/JSON remains the actual returned state. Raw images
are retained unchanged. Use only matching actual screenshots for handoff.

Spotlight diagnosis correction: sandbox mdutil previously said disabled; outside
sandbox indexing is enabled and mdfind finds the provenance PDF in Documents.
App no-hits is not evidence macOS Spotlight is globally disabled. No system
index or permissions were changed. Native Finder control now permitted, but
Go to Folder automation timed out/reset; no drop receipt was produced.

stages.log retains raw public test data; HTTP INFO logging included Google GET
source text. M5.9 disables httpx/httpcore INFO output. Do not use private text
in acceptance data or assume trace recording is enabled for recipient builds.

Finder trace correction: mini-ab96560131e0493e8388e0eaaf7619fd.json received `tm BEST-Route.pdf`, not intended `tìm BEST-Route.pdf`; the input automation dropped a diacritic. This no-hits case does not isolate an app Finder bug. Retest exact ASCII filename.
