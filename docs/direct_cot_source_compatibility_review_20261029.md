# DIRECT/CoT historical source compatibility review

2026-10-29. Read-only source and artifact inventory; no tests, replay, model
inference or downloads were run. No research gate or execution behavior changed.

## Finding

`experiments/direct_cot_analysis.py:load_pilot` requires recorded hashes for
its semantic dependencies to match the current files. The source migration in
`644ec756` changed the dependency path from root `reasoning_strategies.py` to
`reasoning/reasoning_strategies.py`. An older manifest using the former key can
therefore fail the current guard. This is a compatibility limitation, not
evidence that replay should accept the old run.

The check already existed in `79f0a0d9`. Verifying a recorded file against its
original Git revision establishes historical byte identity only; it does not
establish compatibility with today's scorer, parser, dataset validator or
analysis. A path alias alone would not justify accepting changed semantics.

## Artifact search

Searched manifest files in the local `runs/` tree including ignored files, and
searched `audit/`, `artifacts/` and `.migration-backups/` where available for
`aligned-direct-cot-v1`. No aligned pilot manifest was found. The tracked tree
at `644ec756^` contains the analysis/protocol and historical test logs, but no
matching DIRECT/CoT pilot manifest/report bundle was identified. The canonical
`~/github/nesy-docai` alias resolves to this same checkout.

These are bounded search findings, not a claim that all external backups or
all Git revisions lack such a pilot. Historical test logs are not a replacement
for an original pilot with its manifest-bound dataset, records and artifacts.

## Disposition

Keep the strict current-source guard and all frozen manifests unchanged. The
old cleanup handoff's source-hash item is deferred pending an actual aligned
pilot and its original revision, rather than an immediately actionable repair.

If that input is recovered, verify its artifact hashes and each recorded source
at the original revision, then review semantic changes separately. Any proposed
compatibility path must retain original provenance, record current analysis
hashes and refuse unreviewed differences. Historical byte verification must not
be presented as current implementation parity or model-quality evidence.
