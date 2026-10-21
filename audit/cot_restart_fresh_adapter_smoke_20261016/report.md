# Fresh CoT restart adapter — offline acceptance, 16/10/2026

**Completed:** a fresh-base adapter collects O once, builds F/CONT and optional A,
and preserves original token IDs/EOS, per-call journal and selected-path costs.
The saved software smoke completed **12 mock calls / 3 authored groups** with
**0 real model calls**. It used 1,405 synthetic prompt+completion tokens; this is
software evidence, not measured accuracy, inference cost or online latency.

- O is greedy; F/CONT/A use temperature 0.6 and top_p 0.95, q requested = 0.50.
- Each group contributes one item, selected by item ID without model outcomes.
- Seeds exclude budget; poisoning gold leaves prompts, prefixes, seeds and
  generated IDs unchanged; direct smaller-cap mock draws preserve the prefix.
- Full traces, parser output and actual prefix fraction are retained, including
  empty-prefix collapses rather than selecting them away.
- Collection counts each call once; each selected path charges O once plus its
  additional arm, with prompt and EOS-inclusive completion counts separated.
- Completed resume is byte-identical. Failures keep a fsynced attempt and block
  silent retry; interrupted runs between completed calls resume without repeating O.
- Tampering, mode/settings changes and non-mock backends are rejected. A subprocess
  test blocks MLX and Qt imports throughout the software smoke.

**Validation:** 46 tests passed: 12 fresh-adapter acceptance cases, 29 required
research/optimal-stopping/entry-predictor regressions and 5 historical matched tests.
See [validation](../cot_restart_fresh_adapter_validation_20261016.json).

Metadata-only selection on the existing 71-item candidate produces exactly the
70 representatives in the pending [review frame](../cot_restart_fresh_data_review_20261016/candidate_frame.json).
No candidate model output or semantic/gold review was produced by that check.
Both historical plans still pass their existing verifier, including all frozen
source hashes; their runner and supported entry point were not edited:

- First plan: `9816139847b89f26508e3858430afd9fa806a4ff426e09cd2709b5fcd4117157`.
- Second plan: `132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6`.

The auxiliary smoke command is:

```bash
python3.12 -m scripts.smoke_cot_restart_fresh --output audit/NEW_SYNTHETIC_FRESH_SMOKE
```

Real research collection remains through `python -m experiments.research_study`;
the new adapter is not wired into a real collection mode. That mode needs its own
execution freeze after independent data review, n/power, cap/cost scope, practical
margin and decision implementation are settled. The fixture's 64-token caps do
not set study budgets, and 70 candidate groups do not establish sufficient power.
All results here are synthetic; Stage 0 and confirmatory status are unchanged.
