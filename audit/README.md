# Audit artifacts

Commit `644ec756` (2026-10-28) removed the historical audit artifacts from the
working tree at the user's request. Every removed file is still in Git history.

Several research scripts read those files and now stop with a
`FileNotFoundError` that names the missing path. Restore that path (a file or a
directory) before running the script:

```bash
git restore --source=644ec756^ -- audit/run11_sweep_trace.jsonl
```

`git restore --source` writes the file back without staging it, so it is not
re-committed by accident. The restored bytes are identical to the originals, so
SHA-256 pins in the scripts still match. Delete the file again when you are done.
Restoring all of `audit/` brings back 5,625 files (about 272 MB).

| Removed input | Read by |
|---|---|
| `run11_sweep_trace.jsonl` | `scripts/agreement.py`, `scripts/analyze_ae4.py`, `scripts/analyze_af_offline.py`, `scripts/analyze_calibration.py`, `experiments/offline_stopping_study.py`, `scripts/prepare_cot_restart.py`, `scripts/report_af1.py`, `scripts/report_ag.py`, `scripts/report_results.py` |
| `ae_palv2_trace.jsonl` | `scripts/agreement.py`, `scripts/analyze_ae4.py`, `scripts/analyze_af_offline.py`, `scripts/report_af1.py`, `scripts/report_ag.py` |
| `af_palv3_trace.jsonl` | `scripts/report_af1.py` |
| `G_sweep_trace.jsonl`, `G_completion_verification.json`, `G_summary.txt`, `qwen3-8b-tuning-checkpoint-20261003/` | `scripts/review_tuning_sweep.py` |
| `development_data_review.json`, `development_audit_baseline.json`, `development-source-evidence.json` | `scripts/audit_development_data.py` (review file also `scripts/build_nckh_dataset.py`) |
| `development-data-20261003-final/` | `scripts/build_procedural_research_data.py` |
| `development-pilot-measured-20261004-runtimefix/`, `rat_cot_quick_unification_20261022/` | `experiments/checker_dry_run.py` |
| `cot_restart_matched_*_20261013/`, `cot_restart_replication_*_20261013/` | `scripts/review_cot_restart_budget.py`, `scripts/review_cot_restart_reporting.py` |
| `cot_restart_reporting_review_20261014/` | `scripts/review_cot_restart_budget.py` |

The supported research entry point, `python -m experiments.research_study`,
does not read any removed file.
