# Real ordering development pilot: independent offline review

QA assessment: **share with caveats** as two-question development diagnostics.
The tables reproduce from raw artifacts, but the supplied interpretation and
proposed repairs need revision. This review used code-review and analysis-QA
checks; it did not alter the collector, scorer, settings or original run.

Source: [saved development run](order_certificate_pilot_dev2_real_20261008/report.md),
[manifest](order_certificate_pilot_dev2_real_20261008/manifest.json),
[raw journal](order_certificate_pilot_dev2_real_20261008/calls.jsonl).
Only the two saved train questions were evaluated. No additional model call,
MLX/GPU import, prospective-test evaluation, model download or Git mutation.

## Provenance and calculation checks

- Eight artifact hashes and eight source hashes matched the saved manifest.
  Canonical dataset/settings digests matched the recorded run identity.
- The journal checksum chain and manifest head matched: 14 generations, four
  executions and eight completed-arm records, 26 entries total. Each arm's
  generations/execution reproduced its journal entries.
- Record/profile validation passed. All 16 policy rows reproduced exactly except
  fresh offline verifier/solver timing, which is expected to vary.
- Every selected-path prompt/completion sum and summary cost matched raw calls.
  The collection consumed **10,557 recorded model tokens** across all arms;
  this is not any one deployed policy's cost or full compute/energy.
- Re-encoding all 14 saved rendered prompts with the cached tokenizer yielded
  exactly the recorded prompt counts. Completion counts are backend telemetry;
  text re-encoding is not an independent recovery of generated token IDs/EOS.
- The installed MLX-LM source forwards the requested revision when loading and
  supplies final prompt/generation counters and termination. Checkpoint contents
  and historical GPU/power state are not authenticated by this review;
  `model_revision_verified=false` remains appropriate.
- The original run's files remained byte-identical after the read-only checks.

## Interpretation corrections

1. **Certificate schema is not certificate validity.** Both payloads decoded,
   but only the Carol witness was valid. The Frank payload uses an Erin→Frank
   distance of three instead of two. Its answer nevertheless matches gold.
   Rejecting that witness is correct under the certificate contract; the final
   fallback creates one answer-based harm, not an incorrect-answer false accept.

2. **A permissive selector parser alone does not fix the harm.** On the Frank
   question, candidate indices 0/1/2 end with Frank/Grace/Grace respectively, all
   complete. The selector emits `Answer: 2`, which the frozen `Best:` contract
   rejects. A labelled, in-memory counterfactual replacing only that string with
   `Best: 2` selects Grace, still wrong, at unchanged recorded token cost. Thus
   parser-only repair would leave this pilot's candidate/Verified accuracy at
   1/2. This counterfactual is not a new measured model run.

3. **The selector prompt lacks explicit candidate indices.** It asks for 0/1/2
   but concatenates three raw responses without `Candidate 0/1/2` boundaries.
   This makes index selection less explicit. It is a prompt-contract issue to
   fix prospectively, not a proven cause of this particular selection error.
   Any accepted alias should be a full, unambiguous index form, with truncation,
   invalid/out-of-range or conflicting selections still rejected.

4. **PAL-answer has an output-format failure.** The Frank execution prints
   `4th place: Frank`, which the current whole-answer ordering scorer rejects.
   The saved 1/2 remains correct under that frozen format contract, but it must
   not be interpreted as only one of two named answers being semantically right.
   The PAL program also contains the offset error; matching the asked occupant
   does not make its inferred permutation correct. Do not rewrite the historical
   score or change normalization after test inspection.

5. **Native truncation is observed; a successful higher cap is not.** Both
   native calls terminate at length 1,024 before a final answer. This explains
   their scored 0/2, not general native-thinking quality or proof that 2,048 or
   3,072 tokens will suffice. A cap comparison remains an exposed-development
   experiment with fresh settings/output directories and full cost reporting.

6. **No VGC superiority follows.** W-certificate has 2/2 at 345.5 mean model
   tokens; Verified has 1/2 at 2,212.0. Its identity is
   `345.5 + 0.5 × 3733 = 2212`, with Verified/candidate ratio 0.6329041488.
   The query-only symbolic baseline has 2/2 with zero model tokens, not zero CPU
   cost. Generic verification itself includes uniqueness solving. N=2, one seed,
   exposed data and pending checkpoint/human review cannot establish accuracy,
   noninferiority, generalization or a cheap-verifier research contribution.

## Suggested next action (not executed)

First version the selector prompt/parser contract and add offline regression
cases, including this wrong-selected-candidate example. Keep the old run and its
hashes unchanged; prospective fixes need a new profile/run, and retrospective
rescoring must be labelled separately. Consider a development-only native cap
comparison afterwards; do not automatically run the remaining train questions.

The current CLI selects `train[:num_items]`: `--order-pilot-items 8` would select
all eight, not just the remaining six (56 calls for a fresh full pilot). Changed
selection/caps/source cannot resume into the old two-item directory. An exact
six-item continuation needs a separate explicit selection workflow; never bypass
the identity checks or silently change the historical run.

## Regression evidence

```bash
python3.12 -m pytest tests/test_order_certificate_pilot.py tests/test_order_certificate_study.py tests/test_verified_pal_order.py -q -p no:cacheprovider
```

**77 passed in 15.45 s.** This is a relevant offline selection, not the entire
repository or evidence of new model quality. No code/harness change was made.
Stage 0 and the prospective execution/publication gates remain unchanged.
