# Standalone EVRP import

Imported from `Thundercok/evrp-optimizer`, branch `main`, at
`2c8fa69f8f3cfeae475792159ff0ebcf20529044` using Git subtree without squash.
The original 104 commits retain their IDs, author metadata and parent
history. The imported tracked tree was verified against that revision before
local cleanup. `IMPORT_PROVENANCE.json` records the commit IDs and file hashes.

## Scope

This module preserves the EVRP/VRPTW project as standalone source material.
It is not registered in RAT, imported by the research startup, or added to the
root dependency set. No claim of improved CoT or model quality follows from
this import. CoT/verifier research continues through the existing research
harness and its review gates.

Run standalone scripts with this directory as the working directory so that
their relative `data/` and `results/` paths stay inside the module. The benchmark
script requires its own NumPy, PyTorch and optional SciPy environment; no
benchmark or model experiment was run as part of the import.

## Local additions and current-tree cleanup

The original checkout had seven useful untracked files under `scripts/`,
`data/` and `results/`. They were copied byte-for-byte and recorded separately
from the upstream revision. Charging-station JSON/CSV is an unreviewed static
snapshot with missing fields, not a live availability source. The benchmark
results are legacy artifacts from procedural/synthetic instances; their labels
and tables are not evidence of reviewed model quality or valid BKS comparisons.

Generated build/cache files under `bin/`, `obj/` and `__pycache__/` were removed
from the current tree. Their original versions remain in the imported Git
history. The source checkout and its backup branch were left intact.

To inspect an original file revision, use `git show <source-commit>:<original-path>`;
original commits keep the source repository's original paths, without the
`modules/evrp/` prefix. Ordinary path-filtered log/blame views may therefore need
rename/copy following rather than showing every historical commit automatically.
