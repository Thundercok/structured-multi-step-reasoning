# Authorized eight-question development pilot — contract v2

Execution plan recorded before v2 measured generation, 2026-10-08.
This is an exposed-development diagnostic after inspecting the historical
two-item pilot, **not a new confirmatory preregistration**. The user explicitly
authorized the selector/PAL prompt fixes, offline tests and this compute run.

## Fixed scope for this run

- Select all eight existing `train` questions, one seed 42. No calibration or
  prospective test question is evaluated, solved or used to choose settings.
- Four arms: PAL-answer, PAL-certificate, candidate-selection (three candidates
  plus selector), native-thinking. Exactly 56 planned model calls and 16 PAL
  executions, with no extra model probes, new seeds or automatic cap sweep.
- Cached Qwen3-8B-4bit revision `545dc4251c05440727734bcd94334791f6ab0192`.
  Set HF/Transformers offline mode; missing files must fail, not download.
  Revision content authentication remains pending.
- PAL cap 512, candidate cap 1,024, selector cap 64, native cap **2,048**.
  Decoding settings otherwise unchanged. A higher cap is not guaranteed to
  finish native reasoning or a matched-total-cost comparison.
- Record `prompt_profile=order-contract-v2` and
  `selector_parser_profile=single-zero-based-index-v2` in settings.
  Candidates are explicitly numbered 0/1/2 with end boundaries. The prompt
  asks `Best: X`; whole-response `Answer: X` and `Candidate X` are narrow
  zero-based aliases. Reject prose, multiple choices, out-of-range indices and
  truncation. Do not use gold to select an index or rescue an invalid output.
- PAL-answer prompt requests a bare runner string assigned to `result`, without
  rank labels or print statements. The ordering scorer remains unchanged.
- Generic query-derived certificate verification still includes uniqueness
  solving. Keep the query-only symbolic solver as a required baseline.
- New output: `audit/order_certificate_pilot_dev8_contract_v2_real_20261008/`.
  Do not append to, rewrite, rescore or update source hashes in the old run.
  Completed calls are individually fsynced; exact compatible resume is allowed
  by the existing collector, never mock-to-real or changed-profile reuse.

## Safety and reporting

Use one collector/model process, retain failure artifacts and prevent idle sleep
only for that process's lifetime. The Python execution helper has an import
allowlist and timeout but is not a security boundary; use the existing controlled
research workflow, not arbitrary personal-file indexing or a deployment claim.

Report accuracy, all invoked prompt/completion tokens, first-stage confusion,
rescue/harm and format/truncation diagnostics. Separate replayed generation
time, PAL execution diagnostics and verifier/solver CPU timing. These are model
tokens, not full inference cost, energy or measured online latency.

Changing prompts, parser and native cap together prevents causal attribution of
differences from the old N=2 run to any one change. W-certificate and Verified
remain paired on identical PAL/fallback outputs within this run. All eight
questions are exposed, with one seed and pending human/checkpoint review: no
superiority, noninferiority, confirmatory pass or Stage 0 change is authorized.
After 56 completed calls, only offline artifact verification and reporting remain;
do not start a larger campaign, cap increase or another model automatically.
