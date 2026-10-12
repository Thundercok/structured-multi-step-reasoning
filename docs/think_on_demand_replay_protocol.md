# Think-on-demand: frozen Run 11 replay and next experiment

Status: **retrospective development audit; not a preregistration and not held-out evidence**.

This document makes the policy reconstructed from Run 11 executable without
changing the historical trace. It does not amend
`prereg/decision_rule_cascade.md`, whose frozen Policy V escalates from COT to
PAL for arithmetic and to SC for ordering. The verifier and the alternative
PAL/COT/TOT policy were chosen after outcomes from `gen02_tune` had been seen.

## Frozen replay boundary

The replay accepts only these exact inputs:

- `audit/run11_sweep_trace.jsonl`, SHA-256
  `3d57df7f4e81c71513a30b46a190c2d848ea020dac78adf88776620b6e67e632`;
- `data/gen02_tune.json`, SHA-256
  `f3bfa9750038ecce95f31dcdd7362082c4d85487d37ff091282442874a12041c`;
- `prereg/decision_rule_cascade.md`, SHA-256
  `8b8cd86c19c6b843a80d643211761ea6afa5edf59b801236f105f6ccd60ed3c4`.

It validates all 571 unique arm--item conditions, dataset identity, recorded
model provenance and the known SC checker disagreements before analysis. The
scope of the reconstructed policy is 40 arithmetic and 31 ordering questions.
Game-of-24 is excluded and must not be implied by the 71-item result.

The supported command is:

```bash
python -m experiments.research_study \
  --run11-think-on-demand-replay audit/run11_sweep_trace.jsonl \
  --dataset data/gen02_tune.json \
  --lam 0.02 \
  --output runs/NEW_RUN11_THINK_ON_DEMAND_REPLAY
```

The command makes no model calls and refuses to overwrite an existing output
directory. It saves per-item paths, summaries, source validation, policy
definitions, a report and hashes of every generated artifact.

## Policies reported

The replay keeps three questions separate:

1. **Frozen Policy V:** run COT, then run PAL (arithmetic) or SC (ordering) when
   the legacy verifier flags or COT reaches its length cap. Both the historical
   runner correctness and a checker-rescored diagnostic are shown because the
   SC runner invalidated the whole vote whenever any branch hit the cap.
2. **Post-hoc fail-open reconstruction:** route arithmetic directly to PAL; for
   ordering, retain COT unless the legacy verifier flags or COT reaches its cap,
   otherwise pay for and select legacy `TOT`.
3. **Post-hoc fail-closed sensitivity:** use the same metadata router, but treat
   `invalid` and `unverifiable` ordering rationales as escalation-worthy.

The three-state verifier API is `valid | invalid | unverifiable`. The legacy
boolean APIs remain unchanged so this audit cannot silently alter historical
Policy V. A verifier validates consistency of an elicited visible rationale; it
does not establish that the rationale causally produced the answer.

## Cost and routing limitations

`prompt_tokens + completion_tokens` is only a logged proxy. Run 11 records the
prompt once for five-call SC and for legacy `TOT`, although the latter uses
three complete candidate calls plus a selector. Selector input tokens cannot be
reconstructed. ReAct prompt growth is also missing. Therefore replay tables do
not report full inference cost, billing cost, FLOPs or online latency.

The router reads the dataset's perfect family label, and the ordering verifier
reads canonical structured metadata. A real deployable system would need to
measure query classification and natural-language parsing errors and their
costs. Legacy `TOT` is candidate generation and selection, not tree search.

## Gate for a prospective replication

Before collecting any fresh model output, a separate preregistration must:

- choose the family scope and declare how family routing is obtained at runtime;
- freeze fail-closed verifier behavior and all escalation arms;
- use reviewed, non-overlapping development groups not seen during Run 11;
- record every prompt and completion token for every model call, including
  selectors and repeated conversation context;
- seed or otherwise make all stochastic decoding provenance explicit;
- define treatment of partial/length-stopped multi-sample arms before scoring;
- declare accuracy, token, utility, rescue/harm and grouped uncertainty gates;
- reserve an untouched test set until the development replication passes its
  frozen gate.

Until that replication exists, the 62/71 result may be described only as a
post-hoc observation on exposed development data.
