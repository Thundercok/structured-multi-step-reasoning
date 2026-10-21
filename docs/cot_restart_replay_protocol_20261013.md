# CoT restart token replay: CPU preparation

Status: development infrastructure and synthetic acceptance checks only. No new
real-model calls, held-out evaluation, frozen practical margin or Stage 0 pass.
The historical pilot and its journal remain immutable. Research collection still
uses `python -m experiments.research_study`.

## Generation and token contract

New pilot/addendum completions record the actual prompt IDs passed to the
backend, every sampled completion ID including terminal EOS, completion cap,
seed, finish flag, tokenizer package versions/assets, backend version/source
hash, text renderer and decoding configuration. The source identity includes
`experiments/cot_restart_replay.py`; runtime identity and decoding settings are
included in the resume fingerprint. Changed sources or runtime require a new
output directory, not a continuation of a historical run.

Completion counts include terminal EOS. EOS is omitted from visible text.
`finished` is true exactly when an EOS occurs within the retained token budget.
EOS at position L counts as stop; EOS at L+1 makes the L-token result length.
Identical text can therefore have different finish flags. At cap zero replay
returns empty new completion, zero tokens and a length finish.

New draws use seed `f(base_seed, item, arm, call_index)` (`item-arm-call-v1`),
without budget. The first call has index zero; retries reproduce that same draw.
All lower caps reuse one draw. The legacy seed function remains available for
historical reconstruction; existing budget-specific samples are not substituted
into a replay cap-sweep. Generation seeds do not guarantee identity across
different kernels/hardware/runtime versions.

The current backend contract is single-draw sampling with fixed temperature and
top-p, fresh cache, no logits processors, no draft model and no stop strings.
Cache/decoding kwargs are explicit and independent of cap. Nonempty stop strings
or other stopping contracts are refused by replay until their semantics have
separate implementation and acceptance tests. Replay requires matching tokenizer
assets/runtime and verifies that full original IDs reproduce the stored text.

## Replay and scoring

Only original ID-bearing records enter exact replay. For each arm, retain at
most its collected cap, render the retained IDs using its recorded renderer,
construct `prefix_text + cut_completion`, then run the existing typed parser and
procedural checker again. Native thinking is scored only after `</think>`.
Never reuse the full completion's parsed answer or correctness.

For M, define the common per-item new-completion cap from CONT's prompt,
`L_i = W - P_i_CONT`, after verifying it is feasible for every compared arm.
For D, freeze a primary T* and define each arm's remaining completion allowance
after charging the fixed base path and second prompt. Prompt-weight conventions
w=0 and w=1 are token-cost sensitivity assumptions, not measured FLOPs or online
latency. A fixed-base replay cannot change the base-generation cap or an adaptive
retry/selection policy.

Every compared arm must have accepted records at the same registered budget.
An ID-bearing CONT addendum alone cannot establish paired M/D contrasts against
ineligible text-only A/F artifacts. If an allowance exceeds a collected cap,
report unavailable rather than silently clipping just one arm or inventing a tail.

## Boundary sensitivity and inference

The planned offsets are {-8, 0, +8} tokens, with the same cap applied to all arms
within a question at each offset. The central contrast uses all 12 pilot items;
boundary-sensitive questions remain in the denominator. Report per-item arm
correctness, parsed answers and finish flags at each feasible cap, paired b/c
counts and actual contrast changes. A count of two sensitive questions does not
imply a 16.7 pp change in a paired contrast.

Do not average or pool the offsets, treat them as new independent draws, choose
the best cap, or turn sensitivity points into additional hypothesis tests. A
T-sweep is descriptive; inference is confined to registered M and D at T*.
Practical margin/lambda, decision statistic and nominal versus calibrated z
remain review-pending. These exposed-development artifacts are not confirmatory
results, even if a score CI excludes a threshold. Nominal Tango intervals also
retain the finite-sample limitations discussed in the supplied gonogo analysis.

## Acceptance and historical audit

- T1: spy on the real wrapper without MLX; requests differ only in max_tokens.
- T2: seeded causal mock with EOS at L-1, L and L+1; IDs and finish flags agree.
- T3: 1,200 random prompt/seed/cap cases; replay and direct mock generation agree
  on text, IDs, token counts, finish flags and independently parsed answers.
- T4: all 12 synthetic addendum journal records contain IDs, decoding settings
  and tokenizer/backend provenance. The mock now cuts text as well as counts.
- T5: audit all 136 historical journal completions using only the pinned local
  tokenizer JSON, without loading weights or downloading anything. Count EOS
  separately from visible text; the old backend version was not recorded.

Run software acceptance checks and the required research regressions:

```bash
python3.12 -m pytest tests/test_cot_restart_replay.py tests/test_cot_restart_pilot.py -q
python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
python3.12 -m scripts.audit_cot_restart_tokens --output audit/NEW_TOKEN_AUDIT_DIRECTORY
```

The [2026-10-13 token audit](../audit/cot_restart_replay_readiness_20261013/report.md)
found 136/136 text roundtrips, 59/136 literal count matches and 122/136 count
matches under the installed MLX-LM 0.31.3 EOS convention. Fourteen completions
still mismatch after the EOS adjustment, so T5 fails. Legacy arms remain at
their original caps; +/-8 does not repair this failure. Passing count/roundtrip
checks would itself not prove original token identity, because decoding is not
one-to-one.

The next [A/F/CONT preparation](cot_restart_matched_protocol_20261013.md) uses
the user-fixed q=0.50, prepares exact per-call IDs/caps/seeds and can execute a
synthetic batch through the supported research entry point. It proposes 36 fresh
development calls with enough completion for M +/-8 and D at T*=2560, conditional
on logged historical base costs. Real execution remains pending approval of the
concrete prepared budget; no GO/NO-GO rule or enlarged campaign is enabled.
