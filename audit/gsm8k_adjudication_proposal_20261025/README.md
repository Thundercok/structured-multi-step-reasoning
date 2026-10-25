# Three wording adjudication proposals — 2026-10-25

**Concrete proposal for human review, not an approved release.** Original
candidate and all source labels remain unchanged. No fitting, model loading,
inference/embedding calls, gate changes or publication claims.

## Proposed decision

Clarify the intended source interpretation in the three disputed **fitting**
queries, retaining source gold rather than silently replacing labels or
removing groups. These edits are informed by the prior query/gold review;
do not describe the wording transformation as label-blind. No generated model
outcomes were used. The label-independent original group selection is retained.

| Item | Exact fragment before | Proposed fragment after | Retained gold |
| --- | --- | --- | ---: |
| `02343` | `pays before the 25th` | `pays on or before the 25th` | 190 |
| `00484` | `an eighth of his weight every month` | `a fixed one-eighth of his post-growth weight each month` | 36 |
| `03823` | `only 5 have said they are thinking about voting for him` | `5 more have said they will definitely vote for him` | 5 |

Exact complete before/after questions, source line IDs, groups, hashes and
pending decisions are in [proposal.json](proposal.json).

Arithmetic under the proposals:

- Internet: `4 × 50 × 0.95 = 190`; day25 now explicitly qualifies.
- Weight: post-growth192; fixed monthly loss192/8=24; final120; initial156
  minus final120=36. The revised text rules out monthly compounding.
- Votes: 30 committed +5 additional committed +one-fifth of25 opponents=40;
  target45, shortfall5. Considering support is no longer counted as a promise.

## Checks performed

- Original dataset SHA-256 still matches its historical manifest.
- In-memory patched data passes existing pilot structural validation and keeps
  all96 IDs/groups/splits, all gold values and the 48/48 frame.
- Word counts change **44→46**, **55→57**, **129→128**. No cutoff at20/40/60/80
  is crossed; all27 declared rules preserve their action on each modified query.
  This is feature/action correspondence, not proof of model-output equivalence.
- The saved proposal intentionally lacks a runnable dataset `items` schema.
  Existing dataset validation rejects it, preventing accidental collection as
  an approved new release. No candidate release file has been generated.

Reproduce, without a model or writes to the original dataset:

```bash
.venv/bin/python audit/gsm8k_adjudication_proposal_20261025/build_proposal.py
```

The script preserves an existing identical proposal and rejects differing
output rather than overwriting it. No harness implementation changed; these
are data/audit checks, not a new software-quality acceptance or measured run.

## Decision and release boundaries

Human adjudication is still pending for each proposed edit. Agreement with
these three edits does not approve the other93 labels, source rights, semantic
overlap or custody. The seven additional wording priorities remain in the
[prior review](../gsm8k_candidate_agent_review_20261024/README.md); no validation
wording has been changed by this proposal.

If accepted, produce a separately versioned release retaining original source
question hashes/line IDs and adding explicit transformation provenance and
new query hashes. Do not overwrite upstream provenance with edited text hashes.
Record the human decision/date and review the protocol's dataset hash binding
before collection. The current measured gate stays closed. If the human prefers
exclusion or corrected labels instead, prepare that alternative separately;
do not apply an unrecorded choice or silently alter the sample frame.

This is the concrete decision now needed to advance the dataset release.
Antigravity is optional for later implementation/review, not a substitute for
the named human adjudication or inference authorization. Bridge/checker/Stage0
remain unchanged; inference budget remains0.
