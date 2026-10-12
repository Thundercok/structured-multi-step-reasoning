# Measured development pilot — 2026-10-04

All **96 evaluations** completed on 24 exposed development questions / 24
canonical groups. Both DIRECT and CoT used both per-call caps, 96 and 1,024,
with seed 42 and greedy generation. No test items, embeddings, tools, policy
fitting or online controller evaluation were involved. Human/source sign-off
remains pending; these are descriptive development results.

| Cap per call | Strategy | Correct / questions | Mean generated tokens | Parse failures | Length stops |
| ---: | --- | ---: | ---: | ---: | ---: |
| 96 | DIRECT | 5/24 | 38.7 | 5 | 7 |
| 96 | CoT | 5/24 | 90.3 | 12 | 19 |
| 1,024 | DIRECT | 10/24 | 116.8 | 0 | 1 |
| 1,024 | CoT | 15/24 | 324.9 | 4 | 4 |

At cap 1,024, switching DIRECT to CoT makes six answers correct and one
incorrect, with a mean increase of 208.1 generated tokens. At cap 96, two
answers become correct and two become incorrect. Increasing the cap within
DIRECT recovers five questions; within CoT it recovers ten, with no reverse
changes observed in either case. These are paired counts on the same small,
exposed question set, not estimates of controller superiority.

DIRECT's suffix is Vietnamese and CoT's is English. Prompt-language effects
remain mixed with strategy effects. Generated counts exclude prompt/prefill
and full inference cost; prompt tokens are recorded separately. Recorded
strategy duration includes generation and signal computation, excludes model
loading, and is retained by replay. It is not online controller latency.

## Failure review and next development work

The current heuristic confidence is at least 0.8 on **all 61 incorrect
evaluations** across the four conditions. A cutoff of 0.8 rejects none of those
errors. This signal is not a calibrated correctness probability; the observation
does not show that every possible confidence-based controller must fail.

At cap 1,024, DIRECT solves 0/8 Game-of-24 questions and CoT solves 4/8; all four
CoT failures terminate at the length cap. Both strategies make arithmetic
errors on the same two questions. On `order_0022_en_orig`, CoT lists Bob in
fourth place but ends with `Answer: Alice`; DIRECT returns Bob correctly. The
scorer grades the final answer rather than selecting a correct name from the
reasoning body. Raw traces and the agent failure notes are retained.

Before freezing a main study:

1. Align the language and answer-format instructions across DIRECT and CoT,
   then run a separately recorded development comparison.
2. Review confidence features and calibration on separate development groups;
   retain the current heuristic's failures as baseline evidence.
3. Obtain human wording/gold/group review and procedural ownership confirmation.
   Review budgets and calculator/PAL baselines before fixing data, prompts,
   generation seeds and lambda for held-out evaluation.

The pilot does not establish calibrated level difficulty, a parameter freeze,
publication approval or a new Stage 0 decision.

## Evidence and source revisions

- [Raw run](../audit/development-pilot-measured-20261004-runtimefix/manifest.json):
  `attempts.jsonl` equals `records.json`; all 96 conditions occur exactly once.
- [Paired report](../audit/development-pilot-measured-review-20261004/report.md),
  [verification](../audit/development-pilot-measured-review-20261004/validation.json)
  and [failure notes](../audit/development-pilot-measured-review-20261004/failure_review.json).
- [Replay](../audit/development-pilot-measured-replay-20261004/manifest.json):
  dataset, selection, records, summary, report and model provenance reproduce
  byte for byte. Replay and analysis make zero model calls.
- [Renewed preflight](../audit/development-pilot-preflight-20261004-runtimefix/validation.json):
  all 24 golds independently checked; all ten cached runtime files authenticated
  against Hugging Face revision `545dc4251c05440727734bcd94334791f6ab0192`.
- [Preserved failed attempt](../audit/development-pilot-measured-20261004/manifest.json):
  zero completed evaluations. Native MLX bfloat16 arrays could not be exported
  directly to NumPy. Casting inside MLX fixes log-probability and embedding
  export; both native regressions failed before the fix. The corrected isolated
  snapshot passes **55 tests**, including the required research checks.

Collection used clean Git `05a93cfd352b56a693ab50050fa44fc212cb4702`, retained
on local `codex/development-pilot-runtime` and in the review bundle's
`collection-source.bundle` (prerequisite: `495dec2`). This is `495dec2` plus the MLX
conversion fix, excluding subsequent concurrent generator/prompt changes.
The same conversion fix is saved on the shared project branch as `ed6d8ef`.
Analysis source is frozen in the review bundle with its SHA-256; its six tests
and synthetic validation are separate software evidence. The saved
`verifier_source.py` records the exact local audit, including local paths.

## Reproduce replay and analysis

Run from the repository containing the saved artifacts. Use a fresh checkout
of the collection revision because replay checks source hashes; the current
shared branch contains later changes. These commands make no model calls:

```bash
pilot_repo="$PWD"
pilot_checkout="$(mktemp -d)"
git clone --no-hardlinks "$pilot_repo" "$pilot_checkout"
git -C "$pilot_checkout" fetch "$pilot_repo/audit/development-pilot-measured-review-20261004/collection-source.bundle" codex/development-pilot-runtime:refs/heads/codex/development-pilot-runtime
git -C "$pilot_checkout" checkout --detach 05a93cfd352b56a693ab50050fa44fc212cb4702
cd "$pilot_checkout"
python -m experiments.research_study --replay "$pilot_repo/audit/development-pilot-measured-20261004-runtimefix" --output "$pilot_checkout/audit/NEW_REPLAY"
PYTHONPATH="$pilot_checkout" python "$pilot_repo/audit/development-pilot-measured-review-20261004/analysis_source.py" --run "$pilot_repo/audit/development-pilot-measured-20261004-runtimefix" --output "$pilot_checkout/audit/NEW_ANALYSIS"
```

Use the recorded Python/package versions for exact reproduction. The small
source bundle retains the isolated fix commit for other checkouts containing
its prerequisite. A fresh clone, bundle fetch, replay and exported analysis
are verified in `reproduction_verification.json`; outputs reproduce byte for
byte with zero model calls. Human/publication review is not supplied by replay.
