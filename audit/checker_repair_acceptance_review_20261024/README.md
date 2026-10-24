# Checker C1–C3 acceptance follow-up — 2026-10-24

**Verdict: close C1, C2 and C3 within the offline dry-run software scope.**
No new blocking issue found in the targeted repairs. This is not acceptance of
model quality, live RAT behavior, the proposed G24 campaign or the unrelated
regulation-scope/parser/UI proposals included in the handoff. Inference and
embedding calls remain 0, candidate GSM8K 48/48 content unread, bridge unchanged,
Stage 0 unchanged.

## Fresh verification

- Mandatory research/pilot/verifier/checker suite: **107 passed in 47.76s**, exit
  0. Full command is the same six-file suite in the prior review; raw captured
  stdout/stderr is [regression.txt](regression.txt).
- New repair directory: `audit/rat_cot_quick_unification_20261022/checker_development_dry_run_repair_20261024/`.
  **9/9 artifacts** and **2/2 declared source hashes** match current files.
- [Fresh verification script](verify.py) uses isolated temporary outputs and
  authored selector cases. [Verification results](verification.json) confirm:

| Finding | Independent check | Result |
| --- | --- | --- |
| C1: occupied directory reuse | Build once; snapshot every file; rerun and require rejection before any byte changes | Closed |
| C2: synthetic CoT cost provenance | Require synthetic flag, authored-cost provenance, 960 synthetic generated tokens and matching Markdown badge | Closed |
| C3: expression selector fallback | Whitespace variants, multiplication glyph, out-of-range/negative selector index and genuine three-way tie compared with shared expression voting | Closed |

The tie test keeps distinct expressions distinct even where two evaluate to
24, and retains first-candidate tie behavior. CPU-time aliases are absent from
the rebuilt JSON; timing is wall time. Solver reporting now derives its counts
from this exposed sample rather than claiming universal accuracy or a fixed
runtime bound. These checks do not independently prove solver completeness or
benchmark generalization.

Reproduce the additional checks with:

```bash
.venv/bin/python audit/checker_repair_acceptance_review_20261024/verify.py
```

The script snapshots the original dry-run directory and both dated repair
directories before/after and confirms no changes during this review. Source
and evidence match checks refer to the files declared by the repair manifest;
they are not a complete environment/dependency execution freeze.

## Evidence chronology

The preceding [request-changes review](../checker_repair_independent_review_20261024/README.md)
records the earlier source state. The repair author revised its
`counterexamples.py` and regenerated `counterexamples.json` to test acceptance,
so those current files should not be cited as unchanged pre-repair failure
evidence. This follow-up uses a separate script/result directory and preserves
the files as received at the start of this review. The old request-changes
verdict is historical, superseded for C1–C3 by this dated follow-up.

## Boundaries and next research work

Earlier budget isolation, partial cancellation accounting and strict-cap
regressions remain in the passing suite. Persistence here is the tested
process/exception behavior; no power-loss/fsync recovery, partial resume or
real-backend campaign accounting acceptance is established.

The synthetic call/token savings remain software examples. Do not use them
as measured model-efficiency evidence. Human/source review, model/settings
freeze and inference authorization remain pending. No new English G24 profile
or G24 collection is implied by this acceptance.

For this chat, resume the independent GSM8K development preparation: specify
collector started/completed/failed accounting, partial-run recovery and a
validation-access procedure on authored fixtures before opening candidate
data. The UI/parser section of Anti's handoff needs its own source review and
real UI/model evidence if implemented; it is outside this sign-off.
