# Format/selector shadow audit — next-step decision

2026-10-08 (Asia/Saigon). **Retrospective what-if on exposed development data**,
N=8/eight groups, seed 42. Not a new model run, production contract, preregistered
comparison or confirmation. The original measured scores remain unchanged.

Question: can bounded final-answer normalization alone rescue the recorded
fallback, and does a completion-aware selection guard add anything?

Input: [completed contract-v2 run](order_certificate_pilot_dev8_contract_v2_real_20261008/report.md),
[raw records](order_certificate_pilot_dev8_contract_v2_real_20261008/records.json),
and [original offline review](order_dev8_contract_v2_review_20261008.md).
The existing QA script first rechecked all eight artifact/source hashes, journal
links and 64 original replay rows. Only the saved train questions are accessed.
No model call, download, GPU, calibration/test evaluation or production source,
prompt, settings, PAL extraction or verifier-gate change was made.

## Shadow rules (not integrated into the harness)

**A — format only:** keep the stopped selector's chosen index. Accept a terminal
answer block containing a single consistent runner under these exact whole-line
forms: `Answer: NAME`, `**Answer: NAME**`, `**Answer:** NAME`, with an optional
one-to-six-hash Markdown heading prefix. Names must belong to the query-derived
runner list. Conflicting repeated answers, unknown names, extra prose, malformed
wrappers and truncated calls fail. This is bounded presentation normalization,
not substring search for the correct name or recovery of partial reasoning.

**B — A plus unique admissible branch:** keep the selector's choice if it stops
and has a parsable terminal answer. If that choice is inadmissible, use another
branch only when **exactly one** branch stops and has such an answer; otherwise
abstain. Invalid/truncated selectors still abstain. No clue solving, correctness
ranking, majority voting or gold-based candidate selection is used.

Answers are selected from raw generations and query-derived names **before**
gold is consulted for scoring. Recorded initial PAL answers, gate decisions,
policy paths and every invoked call's costs remain frozen. In particular,
changing the chosen candidate does not remove the other branches or selector
from token accounting. Abstention is scored incorrect, not dropped.

## Reproduced counts — correct out of the same eight questions

| Method | Original measured contract | A: format-only shadow | B: format + unique-complete shadow | Mean model tokens, unchanged |
| --- | ---: | ---: | ---: | ---: |
| Fixed PAL-answer | 4 | 4 | 4 | 266.375 |
| Fixed PAL-certificate | 4 | 4 | 4 | 410.625 |
| Fixed candidate-selection | 3 | 4 | 5 | 5225.625 |
| Fixed native-thinking | 0 | 0 | 0 | 2150.375 |
| W-answer | 4 | 4 | 5 | 1035.375 |
| W-certificate | 4 | 5 | 5 | 1185.875 |
| Verified-certificate | 4 | 5 | 6 | 3626.625 |
| Query-only symbolic solver | 8 | 8 | 8 | 0 |

Tokens are saved all-path prompt + completion counts, not full inference cost or
newly measured online performance. A/B add no generation; parser/selection CPU
overhead is not measured. Original collection is still 56 completed calls and
64,424 model tokens; there is no new 56-call campaign.

All-path escalation remains W-answer 1/8, W-certificate 1/8 and Verified 5/8.
In A, W-certificate and Verified each rescue one initially incorrect/contract-
invalid answer. In B, W-answer rescues one, W-certificate one and Verified two.
All three have zero observed harms in these shadows. Initial gate confusion
does not change. These tiny, post-hoc counts do not establish safety or
noninferiority outside the exposed sample.

## Two cases explain every added correct answer

- `order_0025_en_orig`: selector index 1 already points to a stopped branch
  ending `**Answer: Grace**`. A reads Grace; no index change is needed. Both
  W-certificate and Verified had escalated, so both benefit equally. **Format
  repair alone does not create a Verified advantage over W-certificate.**
- `order_0016_en_orig`: the selector chooses length-stopped index 1. Index 2
  is the only stopped, parsable branch and ends `**Answer: Heidi**`. B redirects
  to index 2 without consulting gold. W-answer and Verified had escalated;
  W-certificate had accepted the initial non-dict `4th place: Frank` payload,
  so it never reaches that fallback. The one-question Verified/W difference
  in B therefore involves **gate plus fallback admissibility**, not gating
  alone. It is a retrospectively designed mechanism diagnostic, not new evidence
  of VGC superiority.

The remaining selected answers and all native truncations are unchanged.
The symbolic baseline still solves every question with zero model tokens and
nonzero CPU cost; the generic verifier still includes uniqueness solving.
Repairing the contract does not address that research-comparator limitation.

## Decision and recommended next action

First implement/review a **new, prospective contract version** for bounded final
answer aliases and completion-aware selection/abstention, with regression tests
for ambiguity, wrong names and truncation. Keep the old raw run, scores and
manifests intact. Explicitly decide whether the unique-admissible rule is part
of the policy; it must not be hidden as a scorer-only fix. A parseable completed
candidate is not automatically correct.

Do not spend more GPU time or increase native caps solely because these shadow
counts look better. Prospective pilot scope/caps need separate approval. Before
a confirmatory campaign, human generator/gold review, model authentication,
sample-size/statistical review and a meaningful comparator/task scope remain
required. No router expansion, test opening, preregistration PASS or Stage 0
change follows from this audit.

## Reproduce and validate

[Standalone shadow script](order_dev8_format_selector_shadow_20261008.py):

```bash
python3.12 -B audit/order_dev8_format_selector_shadow_20261008.py
```

The script passed **28 parser/selection regression assertions**, retained the
same eight-row denominator for every method/scenario, checked unchanged paths
and costs, and rechecked all nine original run-file hashes after analysis. It
prints JSON and does not write into the run directory. Tests validate this
audit prototype, not measured model quality or a deployed contract-v3 adapter.
The `data:analyze` workflow separated format-only effects from selection-policy
effects and kept post-hoc shadows distinct from the reviewed measurements.
