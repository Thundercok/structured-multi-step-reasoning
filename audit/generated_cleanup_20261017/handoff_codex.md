# Generated-file cleanup — 2026-10-17

Removed scratch/build_spider/target (Rust build output), .pytest_cache, six tracked legacy Python bytecode files and the empty modules directory. Total regular-file payload removed: 2,003,223,925 bytes across 9,307 files; filesystem allocation may differ. This reduces disk usage, not authored source complexity. Existing ignore rules already exclude target build output and Python bytecode.

Preserved Spider recovery source under scratch/build_spider/, all recovery archives, .migration-backups/, work/ and research artifacts. Verified SHA256 of rat/bin/spider and every scratch/*.tar.gz unchanged before/after; hashes in metrics.json. Runtime binary still reports spider_cli 2.51.208. Scoped diff whitespace check passed. No source behavior changed, so previous 102-test regression result was not rerun or relabeled as a post-cleanup test run. No commit, push, pull or reset. Unrelated dirty changes remain intact.
