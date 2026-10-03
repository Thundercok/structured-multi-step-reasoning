# Offline review of the Qwen3-8B H4 tuning sweep

Assessment: share with caveats as development diagnostics. Human review and publication claims remain pending. No parameters were frozen and Stage 0 is unchanged.

Reproduced all 188 recorded parser/scorer outcomes from Git 76d311b. Independently checked all 94 tuning questions and reference answers using query-parsed arithmetic, exhaustive ordering and exact rational expression evaluation. This is agent review of an exposed tuning pool, including its obsolete test labels; no main-study held-out content was reviewed.

## Arm-separated results

Typed scores reparse these same historical raw outputs with the current strict parser/checker. They are retrospective rescoring, not newly generated or held-out results.

| Family | Arm | N | Legacy correct | Typed correct | Typed accuracy | Length stops | Mean generated tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| arith | DIRECT | 32 | 9 | 8 | 25.0% | 23 | 79.9 |
| arith | COT | 32 | 28 | 28 | 87.5% | 1 | 198.1 |
| g24 | DIRECT | 30 | 2 | 2 | 6.7% | 0 | 18.3 |
| g24 | COT | 30 | 7 | 7 | 23.3% | 20 | 800.3 |
| order | DIRECT | 32 | 11 | 11 | 34.4% | 1 | 6.9 |
| order | COT | 32 | 28 | 28 | 87.5% | 2 | 413.0 |
| All | DIRECT | 94 | 22 | 21 | 22.3% | 24 | 35.4 |
| All | COT | 94 | 63 | 63 | 67.0% | 23 | 463.4 |

## Parsing findings

Correctness changes: 1; parsed-answer changes: 29. Presentation normalization recovers 6 correct answers rejected by the strict checker on the legacy parse. The original trace and summary are unchanged.

Balanced bold around a whole answer/label and contiguous repeated Answer: prefixes are normalized. The entire remaining answer is retained; negation, alternatives, wrong ordinals, disallowed expressions and contradictory equalities remain rejected. These presentation rules apply by format rather than by gold label.

The legacy DIRECT arithmetic answer arith_0011_en_orig extracted 1196 from a reasoning tail at the token cap. Its arithmetic is correct, but it lacks the requested bare final answer. The typed contract rejects that explanatory tail. This score change is a format-contract difference, not evidence of an arithmetic error.

Correct CoT ordering answers with **Answer: Frank** and a Final Answer:/Answer: sequence were susceptible to strict format rejection before the presentation fix. Existing permissive name matching had accepted these strings; the repaired typed parser now handles their presentation explicitly without searching the answer for a gold name.

Game-of-24 parser score gains: 0. Failure includes incomplete/repeated attempts at the token cap and invalid final expressions; attributing these failures to parser error alone is unsupported.

## Difficulty bands and measurement limits

DIRECT uses temperature 0 and a 96-token cap; CoT uses temperature 0 and a 1,024-token cap, with different prompt suffixes. Budget and instruction effects are confounded; the observed gap does not isolate the effect of the reasoning instruction. There is one greedy output per question/arm, no logged generation-seed series or original runtime manifest, and each family/level has only 7–8 questions.

The historical summary pools token counts, truncation and parser diagnostics across both arms. The tables here separate arms. Costs are recorded generated-token counts, with prompt counts shown separately in summary.json; they omit loading, embeddings and other full inference costs. Recorded wall_ms measures each historical arm generation call; it is descriptive across interrupted sessions, not online controller latency or a replay latency estimate.

Arithmetic CoT levels 1–3 saturate at 8/8, while level 4 is 4/8. Ordering CoT is not monotonic with declared level; level 4 is 8/8. Game-of-24 has a low-accuracy floor and many CoT length terminations. Generator levels therefore do not yet establish calibrated difficulty or useful accuracy spread for all strategies.

Canonical groups number 91 for 94 tuning questions; renamed ordering variants are dependent. Scores here are question-weighted descriptions. No confidence interval, significance, population superiority or statistical-power claim is made.

The runner records a snapshot name from cache inspection but loads the model by repository ID. The recorded checkpoint field is not independent proof of the loaded weight identity. Fresh supported runs should supply an explicitly pinned local snapshot. Parser/checker source is reproducible; the full historical generation environment is not reconstructed by this review.

## Decision before parameter freeze

1. Keep the existing dataset levels, prompts and budgets unfrozen as publication choices. Preserve this run as exposed-development evidence.
2. Retain the presentation parsing repair and verify it with regression/smoke checks. New collection must record the updated parser source hash.
3. Before another real-model pilot, complete human/source review and the applicable Stage 0 review, then record model path/revision, prompts, budgets and generation settings. Compare common token caps or a declared budget grid on development if isolating instruction effects is a research goal.
4. Use a supported headless development collection workflow for any further pilot, without exposing main-study test items or labeling an all-split runner execution as development-only. Review family/level floors and ceilings there before fixing sample counts and preregistering the main study.

## Family/level detail

| Family | Level | Arm | N | Typed correct | Accuracy | Length stops | Mean generated tokens |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| arith | 1 | DIRECT | 8 | 7 | 87.5% | 0 | 31.6 |
| arith | 1 | COT | 8 | 8 | 100.0% | 0 | 58.2 |
| arith | 2 | DIRECT | 8 | 1 | 12.5% | 7 | 95.9 |
| arith | 2 | COT | 8 | 8 | 100.0% | 0 | 116.5 |
| arith | 3 | DIRECT | 8 | 0 | 0.0% | 8 | 96.0 |
| arith | 3 | COT | 8 | 8 | 100.0% | 0 | 195.4 |
| arith | 4 | DIRECT | 8 | 0 | 0.0% | 8 | 96.0 |
| arith | 4 | COT | 8 | 4 | 50.0% | 1 | 422.2 |
| g24 | 1 | DIRECT | 7 | 1 | 14.3% | 0 | 18.0 |
| g24 | 1 | COT | 7 | 3 | 42.9% | 4 | 684.7 |
| g24 | 2 | DIRECT | 7 | 0 | 0.0% | 0 | 18.4 |
| g24 | 2 | COT | 7 | 0 | 0.0% | 5 | 847.0 |
| g24 | 3 | DIRECT | 8 | 1 | 12.5% | 0 | 18.4 |
| g24 | 3 | COT | 8 | 1 | 12.5% | 6 | 896.4 |
| g24 | 4 | DIRECT | 8 | 0 | 0.0% | 0 | 18.2 |
| g24 | 4 | COT | 8 | 3 | 37.5% | 5 | 764.4 |
| order | 1 | DIRECT | 8 | 3 | 37.5% | 0 | 4.0 |
| order | 1 | COT | 8 | 7 | 87.5% | 0 | 142.9 |
| order | 2 | DIRECT | 8 | 6 | 75.0% | 0 | 4.0 |
| order | 2 | COT | 8 | 7 | 87.5% | 0 | 327.0 |
| order | 3 | DIRECT | 8 | 2 | 25.0% | 1 | 15.5 |
| order | 3 | COT | 8 | 6 | 75.0% | 2 | 598.8 |
| order | 4 | DIRECT | 8 | 0 | 0.0% | 0 | 4.0 |
| order | 4 | COT | 8 | 8 | 100.0% | 0 | 583.5 |

## Score/format transitions

| Item | Arm | Legacy parsed | Typed parsed | Legacy correct | Typed correct |
| --- | --- | --- | --- | --- | --- |
| arith_0011_en_orig | DIRECT | 1196 | Step 4: Add 980 → 216 + 980 = 1196 | True | False |
| order_0008_en_orig | COT | Frank** | Frank | True | True |
| order_0009_en_orig | COT | Bob** | Bob | True | True |
| order_0013_en_orig | COT | Frank** | Frank | True | True |
| order_0022_en_orig | COT | Bob** | Bob | True | True |
| order_0029_en_orig | COT | Answer: Carol | Carol | True | True |
| order_0030_en_orig | COT | Answer: Grace | Grace | True | True |

Detailed outcomes record original trace line numbers and raw-output hashes. The manifest pins input, historical and current analysis sources. No model was loaded and no policy was fitted.
