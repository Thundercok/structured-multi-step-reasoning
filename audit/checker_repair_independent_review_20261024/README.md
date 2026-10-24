# Checker repair R1–R5 — independent follow-up review, 2026-10-24

**Verdict: request changes; do not close the entire repair package yet.**
The main budget-isolation, cancellation-cost and strict-cap counterexamples
from the earlier review now behave correctly. Three reproducible issues remain
in evidence preservation, provenance labeling and selector parity. Review only:
no edits to Anti's implementation or prior artifacts, no model/embedding calls,
no GSM8K 48/48 candidate content, no bridge or Stage 0 change.

## Verified acceptance evidence

- All **9/9** repair artifact hashes and **2/2** declared source hashes match
  current files: [hash checks](hash_checks.json). This verifies integrity, not
  correctness or measured model quality.
- Fresh mandatory research/verifier/dry-run suite: **104 passed in 46.51s**,
  exit 0; exact command in [regression record](regression.txt).
- Reran the existing reviewer probes in a new temporary directory and separately
  asserted their returned budget/cancellation/selector/duplicate/interruption
  conditions: [retained probe output](legacy_probe_rerun.json). Historical input
  hashes are unchanged; no forbidden imports. That script's received-artifact
  hash section refers to the old handoff directory; `hash_checks.json` separately
  checks the new repair directory.

## Findings

### C1 — [P1] Refuse reuse of an evidence directory before any write

`experiments/checker_dry_run.py:976–981` allows existing directories and touches
an existing journal. The next lines overwrite the running manifest, then
generation appends new events with call IDs starting at 1. Repeating a completed
build in the same isolated directory produces **320 journal events instead of
160**, only 80 unique call IDs, and a replacement complete manifest/ledger
still claiming one 80-call collection. Hashes now bless the mixed journal and
the prior run's manifest/report are lost. An interrupted rerun can replace a
previous successful manifest with interrupted state too.

Required repair: reject an occupied run directory before writing anything;
allow an empty pre-created directory only if deliberately supported. Exact
resume would need its own identity/state validation and is not implied here.
Regression must verify every existing byte remains unchanged on rejection.

### C2 — [P2] Label fixed-CoT replay cost as synthetic

`experiments/checker_dry_run.py:1117–1120` assigns every CoT record **120 generated
and 25 prompt tokens** regardless of historical cost. At line 1325 the resulting
path is labeled `is_synthetic=false`, `data_provenance="historical pilot measured"`.
The rebuilt JSON consequently labels **960 generated / 200 prompt tokens** as
historical measured cost. Historical answers may be reused, but this cost and
the scripted replay execution are synthetic. The Markdown's Historical/Synth
heading does not correct the machine-readable claim.

Required repair: distinguish historical answer provenance from authored cost
provenance; mark this replay row/cost synthetic, or use verified historical
token records with explicit matching measurement scope. Keep actual historical
review outcomes separate. Do not reinterpret the synthetic percentage savings
as measured efficiency.

### C3 — [P2] Normalize expression vote keys in selector fallback

`experiments/checker_dry_run.py:641–646` uses `Counter(answers)` on raw strings,
while `qwen_mlx_backend.py:_vote` calls shared `majority_vote` with answer-format
metadata. For expression answers, shared vote keys strip whitespace and
normalize multiplication/division glyphs. Authored candidates:

```text
1+2+3+4
(1+3)*(2+4)
(1 + 3) * (2 + 4)
```

With an unparseable selector output, dry-run picks the first expression and
verifies **invalid**. Shared backend expression voting selects the two-vote
valid expression. The existing probe only uses byte-identical majority answers,
so its PASS does not establish the claimed normalization parity.

Required repair: share the expression-vote semantics, preserving the selected
public expression and declared tie behavior. Cover whitespace/glyph variants,
genuine ties and invalid selector indices. Do not merge distinct expressions
merely because they evaluate to the same number 24.

## Reproduce new findings

```bash
.venv/bin/python audit/checker_repair_independent_review_20261024/counterexamples.py
```

[Counterexample output](counterexamples.json) uses isolated temporary output
directories and authored selector cases. Builder inputs are the already exposed
historical G24 review artifacts; no protected/new candidate data is involved.
The probe intentionally demonstrates unsafe rerun behavior only on its own
temporary run. It never reruns into the handed-off repair directory.

## Interpretation and next step

R1's budget separation and dynamic ladder totals, R2's tested cooperative
partial-cost/interrupted-builder behavior and R3's tested cap checks are
supported by this rerun. R4 still needs C3; R5's duplicate/model-reference
repairs are present but evidence labeling needs C2. C1 affects the artifact
lifecycle across the package. Journals flush but are not fsynced or resumable;
this review does not certify recovery from process/power failure.

Additional reporting limitation: solver wall time is still duplicated into
`cpu_time_ms`/`mean_cpu_time_ms`; these aliases are not independently measured
CPU time. Several solver claims (accuracy 1.0, eight-of-eight, <10 ms) remain
hardcoded despite the broad dynamic-report claim. Retain their current-sample
scope and remove unsupported measurement labels when revising the report.

Return these findings to Anti for correction and a fresh evidence directory.
Do not overwrite the earlier repair artifacts. This review does not authorize
a G24 collection, change the pending GSM8K development comparison, pass Stage 0
or establish any model-quality gain.
