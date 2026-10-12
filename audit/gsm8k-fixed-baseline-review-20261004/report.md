# GSM8K fixed-strategy development baseline — 2026-10-04

All 69 evaluations on 23 questions / 23 groups completed. English prompts, one pinned Qwen3-8B-4bit model snapshot, cap 1,024 per call, greedy generation, seed 42, thinking disabled. Both development splits are exposed; human review and publication approval remain pending.

| Prompt condition | Correct/questions | Accuracy | Mean generated tokens | Mean tool execution ms |
| --- | ---: | ---: | ---: | ---: |
| DIRECT | 20/23 | 87.0% | 93.4 | 0.0 |
| COT | 19/23 | 82.6% | 96.8 | 0.0 |
| PAL | 21/23 | 91.3% | 87.0 | 50.0 |

PAL solves all four questions CoT misses and loses two CoT gets right. DIRECT solves all four CoT misses; CoT solves all three DIRECT misses. Thus DIRECT/CoT alone have a gold-informed best-of-two ceiling of 23/23 here. That ceiling requires gold labels, is not deployable, and is not an evaluated controller.

All 23 PAL programs execute successfully. There are no parse failures or length stops in any condition. PAL uses fewer mean generated tokens than the other two on this sample, but longer prompts. Generated-token cost excludes prefill/full inference; tool duration includes the Python worker startup and execution and is included in strategy duration. Replay preserves those measured times, not online controller latency.

Selection ranked 24 official training questions without labels/outcomes, then agent review excluded one wording ambiguity before model generation. The retained sample has 11 development train and 12 calibration groups. This is not an official GSM8K test score, a comparison with the earlier mixed-family pilot, or a statistical superiority claim.

## Failure evidence

- PAL on `gsm8k-dev-00482` treats grandma as a child, giving 64 instead of 66. DIRECT invents a grandpa, giving 78. CoT is correct.
- PAL on `gsm8k-dev-01628` omits the first hose during the last two hours, giving 290 instead of 390. DIRECT and CoT are correct.
- CoT on `gsm8k-dev-05545` describes the right operations but finishes with 936 instead of 9144; DIRECT and PAL are correct.
- All nine incorrect condition evaluations have heuristic confidence above 0.8. That cutoff rejects none; this is not a calibrated correctness probability.

DIRECT emits text before its final Answer line on 19/23 questions despite the direct-answer instruction. The table compares prompt conditions and observed outputs; it does not establish absence of reasoning in DIRECT. The PAL adapter is zero-shot code generation/execution, not a full reproduction of the original few-shot PAL paper.

## Decision

Continue to a separate development validation experiment, keeping this pilot as exposed evidence. First compare the three fixed prompt conditions with a simple input-based rule. Strategy errors are complementary, but the strongest fixed condition is already 21/23 and only two more answers are available beyond it in these stored outputs. No learned controller benefit has been demonstrated.

Do not fit thresholds on these 23 questions and describe the result as held out. Freeze any new fitting/validation groups, budget grid and primary comparison before new outputs; review wording and semantic groups. In parallel, compare the candidate entry-plus-stopping contribution with prior routing/compute work before finalizing novelty.

## Evidence and reproduction

- Collection commit: `3dcd2c9bf17c7a451463c3fe4835bd70f8ae14a2`, clean Git status; model content authenticated to revision `545dc4251c05440727734bcd94334791f6ab0192`.
- [Raw collection](../gsm8k-fixed-baseline-measured-20261004/manifest.json), [audited summary](summary.json), [verification](verification.json), [byte-identical replay](../gsm8k-fixed-baseline-replay-20261004/manifest.json).
- [Frozen protocol](../../docs/gsm8k_development_protocol_20261004.md), [source archive](../gsm8k-source-20261004/manifest.json), [review/exclusion](../../data/gsm8k_development_reviewed_v1/manifest.json).

Use the recorded Python/packages. In a fresh checkout at the collection commit, replay using the supported entry point. Run the saved audit script with that checkout on PYTHONPATH; neither operation generates answers.

```bash
python -m experiments.research_study --replay /absolute/path/to/gsm8k-fixed-baseline-measured-20261004 --output /absolute/path/to/NEW_REPLAY
PYTHONPATH=/absolute/path/to/collection-checkout python /absolute/path/to/scripts/summarize_math_baselines.py --run /absolute/path/to/gsm8k-fixed-baseline-measured-20261004 --output /absolute/path/to/NEW_AUDIT
```
