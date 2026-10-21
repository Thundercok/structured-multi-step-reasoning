# Second matched development draw

This prospective addendum follows inspection of the first A/F/CONT draw on 12
exposed questions. It checks generation variability on fixed historical bases,
not held-out quality or a newly isolated prefix mechanism. F stays at the
user-fixed q=0.50; all three arms and all questions remain included. Stage 0
does not change. The authorized next task is preparation and mock validation.

Copy the first prepared plan after verifying its checksum, generation sources,
runtime, pinned history, complete real journal and records. Preserve the exact
model snapshot, prompt text/IDs/order, cache, sampling and M/D caps. Only seeds
and draw/provenance metadata change. Keep base seed 42 and freeze call index 1
in the existing item/arm/call seed namespace, without budget. Reject any seed
collision with the first draw or within the new 36-cell matrix.

Generation sources stay frozen so both plans remain verifiable by the existing
collector. Hash the preparation helper and this addendum separately inside the
new plan's provenance, then hash the full new plan. This records new preparation
logic without relabeling historical generator source hashes. No tokenizer or
model loading is needed: prompts/IDs come from the verified parent plan.

Preparation:

```bash
python3.12 -m scripts.prepare_cot_restart_replication \
  --parent-plan audit/cot_restart_matched_plan_20261013 \
  --parent-run audit/cot_restart_matched_real_20261013 \
  --output audit/NEW_REPLICATION_PLAN
```

Mock and real collection both use the supported research entry point:

```bash
python3.12 -m experiments.research_study \
  --cot-restart-matched-run audit/NEW_REPLICATION_PLAN \
  --cot-restart-matched-mock --output audit/NEW_REPLICATION_MOCK
```

Real collection uses `--cot-restart-matched-approved` after authorization of the
new batch. The first run's 36-call approval has already been consumed. New
ceilings are 36 attempted calls, 72,996 completion tokens including EOS and
14,125 prompt tokens, totaling 87,121 tokens. Failed attempts retain their full
reservation; no automatic additional draws or retries expand this allowance.
The collector refuses new calls after eight active hours, without imposing a
mid-call timeout. Cached weights are verified locally, never downloaded.

If collected, report each draw separately at M and D(w=0/1), including paired
correctness and token differences. Aggregate by averaging correctness and
tokens within each question across the two draws, then taking question-weighted
means. Retain 12 unique questions and the recorded original group count.
Descriptive paired percentile intervals use 2,000 bootstrap samples of original
groups, seed 20261013, preserving every group member and both draws. They are
conditional on the observed draws and fixed bases, and do not estimate
uncertainty over new seeds or policy fitting. A binary Tango table is
inapplicable to fractional seed means. The three existing contrasts remain
exploratory; no comparison is promoted into a confirmatory primary claim.

M +/-8 points remain paired sensitivity checks, not independent observations.
D retains unverified historical base EOS counts. Costs are sampled/prefill token
counts; neither replay nor larger-cap collection measures online M/D latency.
No lambda, practical margin, automatic GO/NO-GO rule or learned locator is
selected. The small exposed set remains diagnostic after replication. A larger
study needs fresh reviewed groups, prospectively chosen decisions and cost
scope, and a separate power assessment.
