# Ordering pilot repair: offline validation — 2026-10-08

## Overall assessment: share software evidence with caveats

The requested collector/scoring/resume/claim repairs are implemented and checked
offline. No model download, native MLX import, model loading, GPU generation,
confirmatory collection, commit, push, pull or reset was performed. Existing
user/concurrent changes and historical artifacts were preserved. The original
Qwen/Meta-Reasoner Stage 0 gate is unchanged.

Fresh artifact: [mock pilot](order_certificate_pilot_mock_fix_20261008/report.md),
[manifest](order_certificate_pilot_mock_fix_20261008/manifest.json),
[call journal](order_certificate_pilot_mock_fix_20261008/calls.jsonl).
Its model outputs and token counts are SYNTHETIC SOFTWARE FIXTURES, not model
measurements. Authored mock PAL code is executed on CPU by the existing helper;
the helper is not a security boundary for untrusted real generation.

## Issues and regression checks

| Former issue | Repair / checked behavior |
| --- | --- |
| Mock imported native runtime | Lazy import; mock/module import never imports MLX. Test guards forbid runtime loading. |
| Count-only cache let mock become real or old caps reuse outputs | Identity pins mode/evidence, dataset, settings, runtime and semantic source hashes before resume. Mode/cap/seed/selection changes reject without rewriting artifacts. |
| Outputs lost until all seven calls finished | Each completed generation and PAL execution is flushed/fsynced to an append-only checksummed journal before proceeding. Completed-arm snapshots are derived. |
| Restart repeated finished calls | Interrupted mock resumes only missing calls; PAL generation survives interruption before execution. Valid journal tail survives a lagging manifest. |
| Concurrent/tampered/legacy output reused | Writer lock, complete artifact hash checks, journal chain checks, exact profile checks, and fail-closed legacy/corruption handling. No corrupt-tail truncation. |
| Truncated selected output scored correct | Shared study scorer marks selected candidate, selector, native and PAL length-stop incorrect; an unselected truncated branch does not invalidate a complete selected one. |
| Gate confusion used final fallback correctness | Confusion now uses the INITIAL PAL answer. Correct answer + invalid witness + failed fallback is an answer-based false reject and escalation harm. |
| Cascade cost omitted fallback | Every invoked prompt/completion count is included, with the conditional rejected-item fallback identity checked. |
| Stream chunk counts treated as model tokens | Adapter consumes the final response and requires backend token/termination telemetry; mocked adapter tests cover empty/missing/over-cap telemetry. Real adapter review remains pending. |
| Mock/prose treated as measured evidence | Every mock call/record/report is labelled; unsupported safety, power, resource-causality and efficiency claims were corrected. |

## Test evidence

Research harness regression required by AGENTS:

```bash
python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q -p no:cacheprovider
```

Result: **29 passed**.

Combined final regression selection, including that same required set:

```bash
python3.12 -m pytest tests/test_order_certificate_pilot.py tests/test_order_certificate_study.py tests/test_verified_pal_order.py tests/test_procedural_research_data.py tests/test_research_study.py tests/test_research_scoring.py tests/test_research_pilot.py tests/test_research_aggregate.py test_optimal_stopping.py test_entry_predictor.py -q -p no:cacheprovider
```

Result: **187 passed in 19.64 s**. This is not the entire repository suite.
`git diff --check` passed. Tests are software evidence, not measured model quality.

## Fresh supported-entry artifact and exact resume

```bash
python3.12 -m experiments.research_study --order-certificate-pilot --order-pilot-mock --order-pilot-items 2 --seed 42 --output audit/order_certificate_pilot_mock_fix_20261008
```

Verified independently after collection and compatible completed resume:

- Two exposed train questions, seed 42; zero prospective test evaluations.
- 14 synthetic generations, four authored PAL executions, eight completed arms.
- 26 journal entries; 16 policy evaluation rows across eight methods.
- All eight artifact hashes and eight semantic-source hashes match.
- Completed resume had zero pending calls and preserved every artifact byte,
  including the manifest/report. Native modules remained absent from `sys.modules`.
- Manifest: `evidence=synthetic_smoke`, `model_calls=false`, `confirmatory=false`,
  `model_revision_verified=false`, `publication_review_required=true`.

## Development-only solver and arithmetic checks

Independent CPU-only check selected `split in (train, calibration)` from the
candidate bundle, called `solve_order_query(query)` without metadata/gold, then
compared the returned answer to development gold. Result: 31/31 solved and gold
matches, mean assignments checked 3696.935483870968; **zero test items evaluated**.
No fresh solver timing claim is made. The solver/verifier share parser limits,
and generic verification includes exact uniqueness solving.

The reported two-item real-pilot figures are not authenticated by raw artifacts.
Conditional arithmetic is `4706 / 7756 = 0.606756` for Verified/fixed-candidate
FULL path cost, not 0.088. A correct Frank answer with an invalid witness is not
evidence of an incorrect-answer false accept. See the
[corrected development audit](ordering_development_audit_20261008.md).

## Required caveats and next step

Real generation, model revision authentication, tokenizer/backend accounting,
runtime resource use and interruption DURING an unfinished call are not validated
by mock. Completed-call durability does not account for all costs of interrupted
attempts. Source changes require a new directory, not historical hash rewriting.

The addendum remains a draft: −5 pp margin, 1,024 native-token cap, sample size,
power and boundary-safe inference need independent decisions/review. No 80% power,
non-inferiority, Pareto, open-language generalization or novelty claim is established.
No prospective test semantics/gold have been reviewed here. Next work is adapter
review and a small raw-artifact development pilot when resources permit, not an
automatic real-model run or confirmatory campaign.
