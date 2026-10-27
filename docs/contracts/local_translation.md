# Free translation packaged with RAT Mini — M5.11 candidate

User decision 2026-10-27: keep free translation and make the recipient workflow
plug-and-play. API-key setup is optional, not the solution to the default UX.

## What informed the choice

- [Firefox](https://support.mozilla.org/en-US/kb/website-translation) ships local
  language models; once installed a pair does not need cloud requests.
- [Argos](https://github.com/argosopentech/argos-translate) uses OpenNMT /
  CTranslate2 and packaged language pairs; [official index](https://www.argosopentech.com/argospm/index/)
  includes en→vi and vi→en. The packaged README for each selected model states
  CC-BY 4.0; attribution and original README files are included in the app.
- [Easydict](https://github.com/tisfeng/Easydict) supports several providers,
  system translation and local-model adapters. Provider choice alone does not
  guarantee key-free availability or remove public endpoint quotas.
- [CTranslate2](https://opennmt.net/CTranslate2/hardware_support.html) supports
  ARM64. It offers a CPU translation API without an Agent LLM/server runtime.

These sources motivate the implementation; their performance/quality claims
are not measurements of RAT or proof of recipient compatibility.

## Shared execution

UI paste, drop and selected local file → ImageInput → capture_text → observed
source_ref → translate_text → structural verification → artifact → projection.
Direct text uses the same translate_text tool/service. The local backend is
inside the translation capability, with no alternate UI business path or Agent
loop. Corrections keep parent/root source refs and use the same backend choice.

`automatic` (default for a fresh installation): detect source as before; en↔vi
uses the bundled local pair. Other pairs use existing Google GTX/MyMemory
online behavior, with its quota/network limits and disclosure. An explicit
legacy provider choice is preserved; switch it to Automatic to opt into local.
A missing/corrupt local pair fails with retained source; it does not silently
send that text to cloud. Optional paid/key providers remain in settings.

The model loads lazily in the worker, CPU int8 where supported, one pair cached
at a time, 2 intra-op threads. No runtime model download, shell, Python install,
Ollama, or API key is needed for the packaged English/Vietnamese path.

## Reproducible packaging and evidence

`tools/rat_translation_models.lock.json` pins official package URL, SHA256 and
bytes. Run `tools/prepare_rat_translation_models.py --download` at developer
packaging time (or supply the previously downloaded archives). It extracts
only fixed inference files; excludes Stanza/pickle/PyTorch payloads; retains
original attribution. Large weights are ignored by Git and reconstructed from
the lock. Runtime verifies inference-file hashes before loading each pair.
Build requires both pairs and packages all model files and runtime metadata.

UTF-8 chunks keep contiguous source offsets and every character, prefer word
boundaries and preserve edge whitespace between translated chunks. No input
truncation; output budget and per-token cancellation are explicit. Model hash,
pair, runtime version and compute type are observed in the translation artifact.
`translation_structure` also checks local model provenance; PASS is not semantic
quality verification. Actual first development output had residual SentencePiece
markers despite structural PASS; decode normalization was fixed against upstream
[Argos tokenizer](https://github.com/argosopentech/argos-translate/blob/master/argostranslate/tokenizer.py).
The raw initial failure is retained in audit, never counted as successful UI.

Real tool smoke after that fix: 3 public inputs, no cloud permitted in the test
process; en→vi and vi→en actual model outputs in audit/rat_mini_m511_20261027/.
Measured on this development host, not recipient M3: ~0.15–0.61s per snippet,
peak process RSS ~470 MB in this short run. Agent LLM calls=0; neural MT inference
is real and separate from that counter. No broad model-quality/research claim.

App UI, native thumbnail and recipient acceptance are reported separately in the
version's status.json. Main UI integration remains gated; Stage 0 unchanged.
