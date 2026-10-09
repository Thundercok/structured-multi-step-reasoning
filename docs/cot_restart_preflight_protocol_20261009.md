# CoT restart: development preflight draft

Status: CPU-only preparation authorized; generation, probe training, and any
held-out evaluation remain unauthorized. This is not a preregistered measured
experiment or an amendment to Stage 0. Supported research collection remains
`python -m experiments.research_study`; that collector currently does not perform
prefix-conditioned repair.

## Question and scope

Does restarting from a retained visible rationale offer enough quality-cost
headroom to justify a learned locator? Keep one repairer, sampling profile,
continuation contract and budget fixed first. Expensive-planner/cheap-executor
and multi-session interventions are separate future ablations.

Read only the pinned Run 11 trace and `gen02_tune.json`, both already exposed.
Their obsolete split labels do not grant held-out status. Prepare all 100 CoT
records, including correct, wrong, malformed and truncated outputs. Derive
outcome-blind dev_fit/dev_eval halves by canonical question; both remain exposed.
Do not open the main/calibration/test candidates or promote any exposed question.

## Checkpoint contract

- Menu q = {0, .25, .5, .75}, measured on locally retokenized reasoning text.
- Exclude the first explicit final-answer block and everything after it.
- Snap to conservative interior sentence boundaries, never inside fenced code
  or display math. Boundary ties choose the earlier cut for reproducibility,
  not because an earlier cut is safer. Review sentence/step faithfulness manually.
- Record requested/actual fractions and duplicate prefixes. Collapsed points
  are not independent arms. Missing punctuation is a preparation limitation.
- Store query/prefix separately from gold and correctness annotations.
- Retokenized text is not the original generated token sequence or a saved KV
  checkpoint. Continuation framing, thinking mode and exact prefill handling
  must be reviewed before generation; they are not frozen by this draft.

## Future comparisons, not measured here

A: regenerate from q=0. F: one global menu point chosen on dev_fit. C: a
gold-informed per-trace menu selector using selection draws, evaluated on new
draws. C is a finite-sample selected diagnostic, **not a guaranteed upper bound**.
Keep self-consistency and budget-matched native thinking as baselines. Freeze
voting, original-answer inclusion, seeds, lambda and stopping/cap rules before
the evaluation draws. Use canonical-question paired bootstrap, not step splits.

Evaluate all questions for deployed accuracy, rescue/harm and total cost. A
wrong-trace-only headroom diagnostic cannot establish a deployable trigger.
Rescue denominator includes every initially wrong question. Report repairable /
below-floor / unresolved only after estimating V(k,model,budget); a low point
estimate is not proof of unrepairability. Changing repairer invalidates labels.
No such values or labels are created by this preflight.

## Cost and decision boundary

Count every initial call, continuation prompt/prefix, completion, critique,
selector, retry and verification call. Report collection/labeling separately
from deployed policy cost. If models differ, report per-model tokens and measured
billing cost rather than treating tokens as equally priced.

Dense example m_s=m_e=4 gives 32 calls per trace. Ideal completion-only cost is
20L; repeated prefix prefill adds 12L, plus 32P query-prompt tokens. Boundary
snapping, final-answer removal and new wrappers change this approximation. It
is neither a prediction of actual runtime nor an approved hard token ceiling.
Independent evaluation of only selected points is a separate allocation option.

Before compute: inspect prefixes, review the continuation mechanism, select a
small feasibility-only development sample, and obtain explicit approval for
the snapshot, caps, seed set, calls and total budget. Small or inconclusive C-A
differences do not kill the general localization hypothesis. Compare C-F using
a predeclared practical margin; nonsignificance is not equivalence. No probe
training until localization headroom and end-to-end cost justify it.
