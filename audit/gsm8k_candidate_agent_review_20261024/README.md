# GSM8K candidate: agent data review — 2026-10-24

**Assessment: needs human/source review before collection.** All 96 development
queries have now been reviewed by this agent; 93 query-derived calculations
agree with the frozen gold, and three need adjudication. These counts measure
label agreement, **not model accuracy or validated difficulty**. No rule was
fit, model/embedding called, source label changed or candidate item removed.
Inference budget remains 0. Bridge/checker acceptance and Stage 0 unchanged.

This continues the user's instruction to advance data/provenance preparation.
Earlier statements that the candidate was unopened describe earlier turns;
they no longer describe the current data-review exposure. All 96 query texts
and labels are now agent-exposed for quality review, not generated outcomes.

## Method and evidence

The agent first read queries without displaying gold/source solutions, wrote
exact arithmetic derivations in five batches, and saved their hashes in
[derivation_lock.json](derivation_lock.json). Only after all 96 derivations were
saved were they compared with gold; source explanations for the three disputed
rows were inspected subsequently. This is a recorded review chronology, not a
claim of independently audited blinding: Python parsed the dataset containing
labels, while displayed query batches omitted them. Public mathematics here
is reviewer calculation, not fabricated model generation.

- [96-row review ledger](review_ledger.csv): query fingerprints, source line,
  group/role, independent answer/derivation, gold agreement, assumptions and
  pending human sign-off.
- [Gold comparison](gold_comparison.json) and `query_derivations_01.json` through
  `query_derivations_05.json`: complete arithmetic and wording notes.
- [Structural checks](structural_verification.json): source archive hashes,
  exact reproduction of label-independent selection, 48/48 groups, 24 original
  exclusions and zero normalized-query overlap. Original source line IDs kept.
  Selection reproduced with the preparation implementation, not a second
  independently implemented ranker.
- [Lexical screen](lexical_overlap_screen.json): highest eight query-token
  Jaccard pairs within candidate and against old exposed candidate. Manual
  reading of those pairs did not identify an exact paraphrase; this screen and
  the full-query reading do not prove absence of semantic equivalence or model
  pretraining exposure. No embeddings or official test were used.
- [Model content recheck](model_content_recheck.json): **10/10** files match
  the saved Qwen3-8B revision provenance, including opaque weight bytes.
  No MLX import/model load/network. Package/platform metadata recorded; this
  is not an execution freeze, performance estimate or license approval.

## Three adjudication cases — all in fitting, not validation

| ID | Frozen gold | Query-derived reading | Issue to adjudicate |
| --- | ---: | ---: | --- |
| `gsm8k-dev-02343` | 190 | 200 | Discount applies *before* day 25; payment *on* day 25 is outside that stated condition. Source applies the discount anyway. |
| `gsm8k-dev-00484` | 36 | 27.375 | After gain, weight is 192; losing 1/8 of current weight monthly gives `192 × (7/8)^3 = 128.625`, so loss from original156 is27.375. Source subtracts fixed24 each month instead. |
| `gsm8k-dev-03823` | 5 | 10 | Thirty students promise support, five only consider it, and five of the25 opponents switch. Firm support is35, short of45 by10. Source counts the five considering students as committed, giving40. |

These are proposed interpretation disputes, not an automatic declaration that
the upstream labels must be overwritten. Retain original wording/labels and
reviewer derivations. A human must choose whether to retain with an explicit
assumption, revise wording/label in a new release, or exclude.

## Additional wording priorities despite numerical agreement

`07140`: repeated split rounds versus individual split operations; `01439`:
which day includes the first halving; `04489`: simultaneous departure despite
"follows"; `05243` and `05821`: "times more" versus "times as many"; `01985`:
"less than1800" versus treating1800 as an exact target; `04007`: "three times
greater" interpreted colloquially rather than a fourfold price.

Other ordinary assumptions are documented per row (pairs of earrings,
52 weeks/year, additive syrup volumes, full working shifts, fictional premises).
Agreement with gold does not remove these interpretation issues. Do not select
items or change assumptions based on future recipe outcomes.

## Release and exposure consequences

Do not silently remove the three disputed fitting items. Doing so produces
**45 fitting / 48 validation = 93 groups**, incompatible with the present
96-group measured guard. Do not silently replace them or promote validation
items. Any replacement/exclusion/wording/gold correction needs a new version,
an explicit pre-generation rule and review of protocol/guards. Wording edits
also change the word-count routing feature and therefore need fresh hashes.

The fixed 27-rule family and development lambda remain unchanged. Data-quality
review reads gold; it does not give the deployed router access to gold, and
does not authorize validation model-outcome inspection before a fitting seal.
No generated outcomes exist from this review. Human review, source/rights
confirmation, prior-exposure review and named custody still remain pending.

## Reproduce checks

```bash
.venv/bin/python audit/gsm8k_candidate_agent_review_20261024/verify_review.py
```

This checks saved derivations using restricted exact-fraction AST arithmetic,
their immutable batch hashes, gold agreement and deterministic source selection.
It reads development data but calls no model and writes nothing. Historical
source/candidate files remain byte-identical. These are data/audit checks;
research harness/controller code was not changed, so no new model/software
quality claim or test-suite acceptance is inferred.

## Where outside input is now useful

Antigravity is not required to decide label truth or sign human approval.
The concrete next decision is human adjudication of the three rows and wording
priorities, then source/rights/custody sign-off and a release decision. Optional
Antigravity work later is implementation of that explicit release decision or
additional independent checks, without modifying this original candidate.
The actual-model run remains gated and unallocated.
