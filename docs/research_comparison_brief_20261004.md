# Reference points and next decision — 2026-10-04

The present evidence is a development prototype. It supports diagnosing
generation, scoring and confidence; it does not yet demonstrate a useful
controller or establish a new research contribution.

## What we can compare today

Same 24 exposed questions, same Qwen3-8B-4bit snapshot, seed 42, cap 1,024:

| Reference | Correct/questions | Mean generated tokens |
| --- | ---: | ---: |
| Always DIRECT | 10/24 (41.7%) | 116.8 |
| Always CoT | 15/24 (62.5%) | 324.9 |
| Choose the correct answer from those two, using gold labels | 16/24 (66.7%) | Not a deployable method |
| Always calculator/ReAct or PAL | Pending measurement | Pending measurement |
| Simple routing rule or the proposed learned controller | Pending measurement | Pending measurement |

The gold-informed ceiling leaves one question of accuracy headroom beyond
always-CoT when selecting from these two stored outputs at this cap. It does
not bound strategies that generate other answers or use tools. Cost savings
can still matter, but selecting between two wrong outputs cannot repair the
eight questions both strategies miss.
CoT uses approximately 2.8 times DIRECT's mean generated-token count here.
The prompt languages differ, and this small exposed set gives no held-out
estimate. Costs exclude prefill/full inference and controller overhead.

Confidence also needs a stronger reference. In the larger-cap CoT condition,
its score is higher for a correct output than a wrong one in 70 of 135 pairs
(ranking AUC 0.519, ties count half). Those pairs are not independent samples;
there are 24 questions. Raw token margin ranks at 0.711 and length/parse status
at 0.722 on the same data. This post-hoc inspection supplies candidates to
test on separate development groups, not validated feature improvements.
No calibration model or stopping threshold has been fitted.

The [offline assessment](../audit/pilot-reference-assessment-20261004/assessment.json)
rechecks the frozen raw answers/scores and hashes. Its manifest records zero
new model calls. A confidence probability needs reliability checks in addition
to ranking; Brier score alone mixes several properties, as described in the
[scikit-learn calibration documentation](https://scikit-learn.org/stable/modules/calibration.html).

To reproduce the assessment, first create the source-pinned checkout using the
[pilot reproduction recipe](development_pilot_results_20261004.md#reproduce-replay-and-analysis),
which defines `pilot_repo` and `pilot_checkout`. Then run:

```bash
PYTHONPATH="$pilot_checkout" python "$pilot_repo/scripts/assess_pilot_reference.py" \
  --run "$pilot_repo/audit/development-pilot-measured-20261004-runtimefix" \
  --audited-analysis "$pilot_repo/audit/development-pilot-measured-review-20261004" \
  --output "$pilot_checkout/audit/NEW_REFERENCE_ASSESSMENT"
```

This requires the recorded Python/package versions and refuses an existing
output directory. The current shared harness has later source changes; the
collection checkout is required for its replay hash checks.

## External reference points

Qwen's technical report Table 18 reports **87.4 on MATH-500** and **26.7 on
ZebraLogic** for Qwen3-8B in non-thinking mode. These are published evaluations
on different tasks and settings, not targets directly comparable with our
custom 24-question accuracy. The report also distinguishes thinking and
non-thinking evaluations. [Qwen3 report](https://arxiv.org/html/2505.09388v1#S4.T18).

The official model card recommends sampling settings and output allowances
different from this greedy, 1,024-token, four-bit pilot. A published-score
reproduction would need to match those choices rather than attributing a gap
to the controller. [Pinned Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B/blob/b968826d9c46dd6066d109eabc6255188de91218/README.md).

[GSM8K](https://github.com/openai/grade-school-math) supplies human-written
multi-step math word problems and predefined training/test files; its repository
includes an [MIT license](https://github.com/openai/grade-school-math/blob/master/LICENSE).
It is a candidate public anchor for a separate math experiment. Preparation
should start from training data only and preserve the official test for the
frozen evaluation. Dataset identity, grouping, gold extraction and review must
be recorded; public availability does not prove absence from model pretraining.

For the research approach, [Route to Reason](https://arxiv.org/abs/2505.19435)
already studies joint model/strategy routing, and
[BEST-Route](https://arxiv.org/abs/2506.22716) studies model/sample-budget routing.
Our candidate contribution is a controlled fixed-small-model study of entry
selection plus stopping. Its value and difference from prior work require
evidence; routing terminology or passing tests do not establish novelty.

## One next measurement, with a decision attached

Prepare a small, reviewed GSM8K **training-only development** sample and
compare English DIRECT, English CoT and English PAL on the same pinned model
and questions, with declared per-call caps and tool-turn limits. Sum generated
tokens across every PAL call and report tool time separately. This is a
separate math development experiment, not a replacement for the mixed-family
main study. Record fixed strategies before adding a router.
This answers whether tool-assisted execution creates a worthwhile alternative
to always-CoT. Sampling/default changes require a separately named protocol;
do not change language, decoder and confidence formula in one comparison.

The subsequent controller must beat a strong fixed strategy or a simple
input-based rule on accuracy–generated-token tradeoffs. Any fitted features,
rules and thresholds need disjoint fitting/validation groups before held-out
evaluation. If fixed PAL dominates the useful range, report that limitation and
narrow the controller claim. Stage 0 and publication review remain unchanged.

The next deliverable is one readable baseline table and a continue/narrow
decision tied to it. Add experiment infrastructure only to enable that result.
