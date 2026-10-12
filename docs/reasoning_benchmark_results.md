# Legacy reasoning simulation — archived

**SIMULATED. These numbers are not empirical NCKH results.** The old
`CalibratedReasoningBackend` samples correctness using predefined probabilities,
returns gold answers on sampled successes, assigns fixed token costs and computes
latency with formulas. It does not measure Qwen/MLX inference.

The supported study is now [research_study](../experiments/research_study.py).
See [the research plan](research_plan.md) and [protocol](research_protocol.md).

## Why the old conclusions were withdrawn

- The legacy runner fits on the first 24 expanded examples and evaluates on all
  60, so its evaluation includes its fitting data.
- Prefix variants of original questions are not independent new problems.
- Different methods consume different random draws. Accuracy differences with
  zero escalation do not demonstrate that escalation rescued answers.
- The one-shot comparator shares targets built for the ladder; it is not an
  independent reproduction of the published Route-to-Reason method.
- At 410 tokens versus CoT's 280, the simulator uses 46.4% **more** tokens.
  The old prose incorrectly described this negative saving as a reduction.
- The Wilcoxon calculation in the runner compares against fixed SC, while old
  prose labeled it as CoT. Statistical tests on these simulated/leaking data do
  not establish a hardware or real-model result.

The checked-in LaTeX table is retained as an archived simulator artifact with an
explicit warning, not a table ready to insert into the paper.

## Historical output, retained for traceability

| Legacy label | Simulated accuracy (%) | Assigned tokens | Formula latency (ms) |
| --- | ---: | ---: | ---: |
| Direct | 25.0 | 45 | 72.8 |
| Fixed CoT | 61.7 | 280 | 357.0 |
| Fixed SC | 70.0 | 1420 | 1607.0 |
| One-shot router | 83.3 | 410 | 509.5 |
| Dynamic ESCALATE | 86.7 | 410 | 494.2 |
| Frugal | 95.0 | 410 | 494.2 |

## Pareto and publication status

The historical lambda sweep changes random draws between settings. It is not a
validated Pareto comparison. The new runner uses frozen outputs, disjoint
train/calibration/test groups and separately trained router targets.

No measured reasoning improvement or token reduction is claimed here. The Stage 0
gate remains in effect before the frozen real-model experiment campaign resumes.
