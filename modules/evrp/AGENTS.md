# Standalone legacy EVRP module

Keep EVRP standalone unless the user explicitly requests an integration. Do not
register it in the default RAT registry, import it during research startup, or
add its dependencies to the root environment as routine work.

Read `IMPORT.md` and `IMPORT_PROVENANCE.json` for origin, original commit IDs,
local additions and cleanup. Preserve source history; do not rewrite imported
commits as routine cleanup.

Treat legacy benchmark tables and charging-station data as unreviewed artifacts.
The benchmark generators use procedural/synthetic instances; imported results
do not establish a valid comparison to named BKS values, improved CoT, or model
quality. Any new research comparison follows the repository's research plan,
protocol and Stage 0 gates.

Run standalone scripts with this module as the working directory and its own
dependency environment.
