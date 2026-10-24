# H1–H3 targeted acceptance — 2026-10-24

**Close H1, H2 and H3 for the tested offline fixture scope.** Source inspection
and fresh verification agree with the repair handoff. No production changes
made by this review. No candidate 48/48 content accessed, model/embedding calls,
bridge changes or Stage 0 change. Authorized inference budget remains 0.

- Fresh nine-file research/collector/baseline/checker regression: **170 passed
  in 8.71s**, exit 0; captured output in [regression.txt](regression.txt).
- The repair author's probe script was copied and rerun in this new directory
  to preserve their artifacts. [Results](verification.json) include source
  fingerprints; [script](verification.py) contains the assertions.
- H1: cap/seed mismatch is rejected before runner dispatch or journal event.
  Source now derives dispatch parameters from the checkpoint and validates
  creation identities. This confirms the reviewed mismatch case, not arbitrary
  execution-environment provenance.
- H2: non-synthetic staged evidence is explicitly rejected as deferred. This
  closes the false-measured-label counterexample by restricting this path to
  synthetic fixtures. It does not approve a staged real-model adapter.
- H3: asymmetric fixture costs reconcile: total **6 calls/1,500 tokens** equals
  fitting **3/1,050** plus validation **3/450**. Full, fitting-only,
  validation-only and selected-path scopes are separately labeled.

The [preceding request-changes review](../gsm8k_collector_repair_review_20261024/README.md)
remains historical evidence; this follow-up supersedes its H1–H3 verdict for
the repaired source. Earlier default-cap payload, orphan, record-reconstruction
and bank-swap checks remain in the passing regression suite.

## Handoff / next work

Software evidence is ready to support further preparation, not data/model
acceptance. Keep the existing 27 rules, utility/tie order, five report rows,
single primary contrast, dataset review, gates and budget unchanged.

Before any measured run: review and source-pin an actual staged backend seam,
full model/tokenizer/template/environment provenance, collection accounting and
the manual custody/exposure procedure. Do not represent legacy combined-bank
fitting as outcome-access isolation, or filesystem-readable validation files
as technically inaccessible. These remain explicit limits, not reopened bridge
or checker work.

Return to the pending data/configuration review dossier without opening
candidate content automatically. Human/source/semantic-gold/exposure review,
execution freeze and explicit inference authorization remain separate work.
No synthetic gain or passing-test count establishes measured model quality,
online latency, full inference efficiency or main-study H1.

UI Session 17's corrected component result is separate. Its old raw run was
replaced before this review; do not claim a preserved original log exists just
because the narrative describes it. No live UI acceptance is established here.
