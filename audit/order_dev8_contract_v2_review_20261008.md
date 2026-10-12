# Ordering contract-v2 development pilot — offline review

Review date: 2026-10-08 (Asia/Saigon). QA assessment: **share with caveats**
as exploratory development diagnostics, not a confirmatory result.

The completed run has eight exposed train questions/eight groups, seed 42,
`order-contract-v2`, and native cap 2,048. This review checks completeness,
same-output policy comparisons, cost accounting and error interpretation.
It does not fit a router or retest the historical cross-family static policy.

Sources: [original report](order_certificate_pilot_dev8_contract_v2_real_20261008/report.md),
[manifest](order_certificate_pilot_dev8_contract_v2_real_20261008/manifest.json),
[raw records](order_certificate_pilot_dev8_contract_v2_real_20261008/records.json),
[journal](order_certificate_pilot_dev8_contract_v2_real_20261008/calls.jsonl),
and the [pre-run execution plan](order_dev8_contract_v2_plan_20261008.md).
Only the saved train dataset was replayed. No additional model call, model
download, MLX import, calibration/test evaluation, source/prompt/settings change,
historical rescoring or Git mutation was performed for this review.

## Integrity and calculation checks

- Collector session 94084 exited with code 0; the saved manifest is `complete`.
- All eight artifact hashes and eight source hashes matched. Canonical dataset
  and settings digests matched the saved identity.
- The checksum chain, sequence, unique journal keys and manifest head matched:
  **56 generations + 16 executions + 32 completed-arm records = 104 entries**.
  Every record reproduced its journaled generation/execution payload and link.
- Record/profile validation passed. All **64 evaluation rows** reproduced
  exactly except fresh `offline_verifier_ms` and `offline_solver_ms`, which
  measure new CPU executions and are expected to vary.
- Every selected-path prompt/completion sum, recorded generation-time sum and
  summary metric matched. Initial stages and all fallback branches/selector
  count even when the result is wrong, malformed or truncated.
- Full collection consumed **64,424 recorded model tokens**: 25,706 prompt and
  38,718 completion. This is all-arm collection cost, not a deployed policy's
  cost, energy, FLOPs or full inference cost. Completion counts remain the
  saved backend telemetry, not independently recovered generated token IDs.
- All nine original run files (manifest plus eight artifacts) remained
  byte-identical during replay. The old N=2 manifest and its eight artifact
  hashes also remain intact; its historical source hashes were not rewritten.

Completed-run manifest SHA-256:
`a6666054e254394fd1bc1d5cbbd516215096947f4e0e954b44cc7caa110b63fd`.

## Reproduced exploratory results

Tokens below mean **prompt + completion across every invoked call**, averaged
over the same eight questions. They exclude non-model CPU work. The fallback is
three generated candidates plus a selector, **not Tree of Thoughts**.

| Method | Correct /8 | Mean prompt | Mean completion | Mean model tokens | Escalations /8 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed PAL-answer | 4 | 124.375 | 142.000 | 266.375 | 0 |
| Fixed PAL-certificate | 4 | 126.375 | 284.250 | 410.625 | 0 |
| Fixed candidate-selection | 3 | 2860.125 | 2365.500 | 5225.625 | 0 |
| Fixed native-thinking | 0 | 102.375 | 2048.000 | 2150.375 | 0 |
| W-answer (exec gate) | 4 | 542.375 | 493.000 | 1035.375 | 1 |
| W-certificate (exec gate) | 4 | 546.375 | 639.500 | 1185.875 | 1 |
| Verified-certificate | 4 | 1885.375 | 1741.250 | 3626.625 | 5 |
| Query-only symbolic solver | 8 | 0 | 0 | 0 | 0 |

W-certificate and Verified use the **same PAL-certificate and fallback outputs**.
They are correct on exactly the same four questions; their paired rescue/harm
is 0/0. Verified costs **3.058× W-certificate**, an extra 2,440.750 tokens per
question (19,526 across eight). It costs 0.694× fixed candidate-selection, but
that comparator is weaker here. Neither cascade improves on its own fixed PAL
accuracy in this run: rescue/harm versus its first stage is 0/0 for all three.
Equal observed accuracy is not evidence of population noninferiority.

The all-path identities independently reproduce the measured means:

- W-answer: `266.375 + (1/8) × 6152 = 1035.375`.
- W-certificate: `410.625 + (1/8) × 6202 = 1185.875`.
- Verified: `410.625 + (5/8) × 5145.6 = 3626.625`.

Use the **conditional fallback cost among rejected questions**, not the overall
fixed-candidate mean, to reconstruct cost. These are replayed selected paths;
their generation-time sums do not measure online end-to-end latency.

## First-stage gate confusion and witness validity

Labels refer to the **initial answer under the frozen scoring contract**,
not the fallback answer or witness schema validity.

| Gate | True accept | False accept | True reject | False reject |
| --- | ---: | ---: | ---: | ---: |
| W-answer | 4 | 3 | 1 | 0 |
| W-certificate | 4 | 3 | 1 | 0 |
| Verified-certificate | 3 | 0 | 4 | 1 |

Certificate outcomes are three valid, two invalid, three unverifiable. Five
payloads decode into the required dict; decoding alone does not imply validity.
The Frank answer (`order_0001_en_orig`) is right while its witness has gap 3
instead of 2. Rejecting that witness is correct; it is a false reject **by answer
correctness**, not a verifier bug. Its fallback now chooses Frank, so there is
no harm on that question. The four initially incorrect/contract-invalid
certificate answers have no successful fallback rescue.

W-certificate's three false accepts include two non-dict execution payloads,
not three proven semantically wrong named answers. In `order_0009_en_orig`, the
actual payload is a prose `order: ..., answer: Grace`; Grace matches gold, but
the dict contract fails, so the frozen initial answer is empty. It is not
silently rescored as a valid certificate. `order_0016_en_orig` produces
`4th place: Frank`, also not a certificate. Execution success alone accepts
both. The separate `order_0025_en_orig` PAL-certificate execution fails with
`NameError: name 'result' is not defined`.

Observed zero false accepts among the three Verified accepts does not establish
a zero false-accept rate outside this tiny exposed sample.

## Format, selector and truncation diagnostics

- **Selector syntax:** all 8/8 outputs are complete, valid `Best: 0/1/2` forms.
  This removes selector-format failures in this run; the joint prompt/parser/
  cap changes and different sample size do not identify a causal improvement.
- **Candidate budgets:** 8/24 candidate branches terminate at length 1,024;
  four other, stopped branches have no final line accepted by `_final_answer`.
  Headings/bold forms such as `### Answer: Erin` or `**Answer: Grace**` violate
  this pilot's plain-final-line contract, despite containing a named answer.
- **Selection of truncation:** `order_0016_en_orig` selects branch 1, which is
  truncated, although branch 2 stops and ends with `**Answer: Heidi**`. That
  unselected branch is also format-rejected by the frozen parser.
  `order_0017_en_orig` has all three branches truncated. A valid selector index
  is not assurance of a complete or correct chosen candidate.
- **Selected format-only rejection:** `order_0025_en_orig` selects the stopped
  branch 1 ending with `**Answer: Grace**`. The named answer matches gold, but
  its frozen extracted answer is empty. This is a real contract failure, not
  proof that the model could not name the answer. No parser-only retrospective
  accuracy is substituted for the saved result.
- **PAL-answer:** seven executions succeed and return bare names; one produces
  no result. The helper also accepts printed output, so successful output is
  not proof that the model followed the requested `result` assignment.
- **Native-thinking:** all 8/8 calls reach length **2,048**, with no `Answer:`
  marker and no closing `</think>`. Its 0/8 is a budget/termination observation,
  not general native-thinking quality or evidence that any higher cap suffices.

## Interpretation, caveats and next decision

The verifier detects bad/missing witnesses, but the recorded fallback cannot
rescue the rejected cases. More gating therefore increases cost without an
accuracy gain here. This is a useful development failure mode, not VGC
superiority or a confirmatory negative result. Fixed PAL is cheaper at the same
aggregate accuracy in this run; the native and candidate comparisons also have
different budgets, so they do not isolate prompting from available compute.

The symbolic solver gets 8/8 with zero **model** tokens, not zero CPU cost.
Original report mean offline solver time is about 5.512 ms, and Verified's
mean offline verifier time is about 2.649 ms; fresh timings vary. The generic
verifier includes exact uniqueness solving, and the solver shares its query
parser. This pool does not support a witness-only-cheapness or reasoning-router
advantage over a query-only program. It also does not independently validate
that shared parser or substitute for human generator/gold review.

Recommended next step, **not executed**: review bounded, gold-independent final
answer/whole-payload format handling and selection/abstention when candidates
are incomplete, using offline train fixtures before requesting more GPU work.
Any normalization, selector or budget repair must have a prospective versioned
contract; any retrospective rescoring must be separate and labelled. Do not
automatically increase the native cap, add seeds or open calibration/test.

Human generator/unique-asked-rank review, checkpoint-content authentication,
sample-size/power and confirmatory execution freeze remain pending. The run
keeps `model_revision_verified=false`; hashing local artifacts does not
authenticate the weights. No CI, significance, noninferiority, preregistration
PASS, VGC success or Stage 0 pass is inferred from N=8/one seed.

## Reproduce this read-only QA

[Review script](order_dev8_contract_v2_replay_review_20261008.py):

```bash
python3.12 -B audit/order_dev8_contract_v2_replay_review_20261008.py
```

It pins the completed manifest, verifies source/artifact/identity/journal links,
validates the full matrix, compares all 64 replay rows, independently sums path
costs and summaries, prints gate/format diagnostics, checks historical artifacts,
and verifies original run files were not changed. It makes no model calls and
prints JSON without writing an output directory. This QA used the
`data:validate-data` methodology to separate contract failures, witness failures,
fallback failures and unsupported population claims.
