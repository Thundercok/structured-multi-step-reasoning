# NeSy primary repository migration — 2026-10-12

Both repository histories are retained. The original NeSy and reasoning heads
are ancestors of the migration branch. Both self-contained Git bundles were
restored into temporary bare clones and their expected HEADs matched.

Preserved 1592 current working files at mapped destinations, with hashes;
11 have deliberate layout/separation adaptations. 205 ignored state files
and 11 late source updates were retained locally. The recently added invoice
RAT adapter remains only in the recovery snapshot; integration is deferred.

Root reasoning/RAT/late UI checks: **91 passed**. Standalone DocAI checks:
**54 passed, 1 skipped** (opt-in live OCR batch). Its wheel built successfully,
contains the Swift OCR source and contains no RAT package. Existing DocAI
Streamlit initial-render test also passed in the legacy environment. No new
foundation-model inference, personal-file indexing or research study ran.

DocAI is isolated at `modules/docai/`, with independent dependencies, CLI,
tests and package metadata. RAT has no `inspect_invoice` registration or
DocAI imports. The research RQ, splits and Stage 0/publication gates remain.

Main catalog/agent navigation now points to `nesy-docai`. Existing symlinks,
source checkout and shared worktrees are retained. Recovery material is in
`.migration-backups/20261012/` and is not staged for public publication.

All Git operations were local: no push, pull, reset, force, or GitHub repository
deletion. Public publication and deletion remain pending explicit push
authorization required by the repository's AGENTS.md.

[Validation](validation.json) · [Preservation manifest](manifest.json) · [Recovery checks](recovery_checks.json)
