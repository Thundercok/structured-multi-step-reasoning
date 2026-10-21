# Antigravity: collect the second matched development draw

The user has authorized Antigravity to run this prepared second batch. Execute
the frozen plan below once, then audit/replay it offline. Codex has not started
this real batch. Use this existing checkout and its cached model; do not create
another draw or regenerate the historical bases.

Working directory:

```text
/Users/thundercock2/Documents/Github/multi-step-structured-reasoning
```

Use the same Python interpreter as preparation:

```text
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
```

The plan's `plan_sha256` is:

```text
132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6
```

Its current file SHA-256 is
`e9bac47e1697fcb503ac1d25ff5cd2d6ad14ccb88bf31e6909be95f6d2c2cbcd`.
Preparation and mock validation are documented in `report.md` and
`validation.json` next to this handoff. 58 tests passed, 36 mock calls completed
and all 180 replay cells were checked. These checks are synthetic software
evidence; the second real draw has not been measured yet.

## Fixed execution scope

- Same 12 exposed questions and original groups; A/F/CONT, q=0.50.
- Call/draw index 1, base seed 42; all 36 new seeds already reside in the plan.
- Same model snapshot, prompt text/IDs/order, sampling, cache and generation
  sources as draw 0. M uses W=2048; D uses T*=2560, w=0/1.
- At most 36 attempted calls, 72,996 sampled completion tokens including EOS,
  14,125 prompt tokens and 87,121 combined tokens. Maximum per-call combined
  allowance is 2,739 tokens.
- Refuse new calls after eight active hours; no mid-call timeout is promised.
  Failed attempts consume their reserved call/token allowance.

Keep generation files and the plan unchanged. The collector verifies their
hashes and runtime before model loading. If that check fails, preserve the
error and report it; do not replace old hashes or prepare another plan merely
to bypass the check. Verify weights from the existing local snapshot; no model
download or package upgrade is part of this task. Do not push/pull/reset/force
Git or modify unrelated RAT/DocAI work.

## Real collection

From the working directory above:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -u -m experiments.research_study \
  --cot-restart-matched-run audit/cot_restart_replication_plan_20261013 \
  --cot-restart-matched-approved \
  --output audit/cot_restart_replication_real_20261013
```

Use the host's Metal-capable execution environment. The first draw required
host GPU access because its sandbox reported `No Metal device available`
before any inference. Keep the exact interpreter and arguments above if the
same access issue recurs.

Preserve `manifest.json`, `calls.jsonl` and `records.json`. Do not overwrite a
different run, start parallel collectors or add unplanned retries. If
collection fails or is interrupted, inspect the journal before resuming: an
unfinished/failed inference consumes the existing allowance and needs reporting
rather than an automatic replacement draw. Completed calls can be recovered
through the same output directory. Once complete, avoid rerunning collection:
the existing collector preserves raw records but refreshes manifest timestamps
on completed resume, which changes the manifest file hash.

## Offline audit after successful collection

These commands use only the local tokenizer and saved IDs, not model weights:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m scripts.analyze_cot_restart_matched \
  --run audit/cot_restart_replication_real_20261013 \
  --plan audit/cot_restart_replication_plan_20261013 \
  --output audit/cot_restart_replication_analysis_20261013
```

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m scripts.cot_restart_rescue_diagnostics \
  --analysis audit/cot_restart_replication_analysis_20261013 \
  --run audit/cot_restart_replication_real_20261013 \
  --plan audit/cot_restart_replication_plan_20261013 \
  --output audit/cot_restart_replication_diagnostics_20261013
```

Return artifact paths, completion/failure status, attempted/completed calls,
sampled completion and prompt+completion totals, elapsed collection time, M/D
accuracy/paired contrasts and M +/-8 boundary sensitivity. Preserve artifact
hashes and the final journal head for review.

Each analysis above is one draw. Across draws, average within each question
before paired group resampling under the plan's frozen analysis specification;
do not pool the draws or replay caps as independent questions, or apply a
binary Tango table to fractional seed means. Cross-draw aggregation is a
separate offline follow-up. There are still 12 questions. D remains conditional
on historical base counts with unverified EOS scope, and collection timing is
not M/D online latency. All results remain exposed-development diagnostics;
Stage 0 and publication review are unchanged.
