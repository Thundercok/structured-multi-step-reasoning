# Unused source removal — 2026-10-17

User requested removing unused code. Archived and verified every regular-file byte and mode before removing legacy/V1, legacy/V2, qwen_backend.py and generate_history.py. Archive includes the old crawler PDF fixture and all current files; see metrics.json. Recovery archives, independent old checkouts, shared worktrees and .migration-backups remain untouched. No commit/push or history generation executed.

Evidence: scoped and repository-wide searches outside recovery/audit/work found no callers of QwenMacBackend, qwen_backend or generate_history, nor external imports/paths into the V1/V2 crawler copies. V1 contains the old emhuy crawler scaffold; V2 is the old independent Spider Qt crawler. Active application uses rat/ and optional subprocess Spider adapter. qwen_mlx_backend.py remains the supported research backend. Static searches cannot prove usage outside this repository.

Kept pipeline.py and benchmark_dataset.py: research_study and tests still import MockDemoBackend from pipeline, which imports benchmark_dataset. Kept scripts/legacy/run_sweep_p.py: data/MANIFEST.json cites it as historical reproducibility source. Kept timetable and astrology: they have active CLI/UI/registry consumers; unused-import analysis cannot authorize breaking those consumers. Further extension removal requires complete registry/UI/config cleanup rather than blind directory deletion.

Tests recorded in tests.log; software checks do not establish model quality or change Stage 0. Preserve unrelated dirty work.
