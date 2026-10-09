# Ordering contract-v2 pilot launch — 2026-10-08

Status at handoff: **running**, not completed model-quality evidence.
The user explicitly authorized compute after the development-only execution
plan. Debugging and contract-regression checks motivated numbered candidates,
bounded selector aliases, versioned settings and a bare-name PAL-answer prompt;
the scorer and generic certificate-verifier policy remain unchanged.

## Software validation before measured collection

- Selector/collector/checker/required harness selection: 145 passed in 13.15 s.
- Full relevant ordering/research selection: **226 passed in 16.18 s**.
- Required standalone harness command:
  `python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q -p no:cacheprovider`:
  **29 passed in 3.13 s**.
- `git diff --check` passed.
- [Fresh v2 mock](order_certificate_pilot_contract_v2_mock_20261008/report.md):
  two train questions, native cap 2,048, 14 synthetic model calls; all eight
  artifact hashes matched. Mock did not import/load MLX. These are fixtures.
- Every hashed artifact in the historical two-item real run remained unchanged.

## Live launch

Preflight found AC power and cached config/tokenizer/weight files. A read-only
process check found no Python/caffeinate inference process at that time.
Sandbox MLX import failed with no accessible Metal device; the GPU command was
then authorized outside that sandbox through the execution approval mechanism.
This is not a claim that the PAL helper is a secure sandbox.

```bash
env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /usr/bin/caffeinate -is python3.12 -u -m experiments.research_study --order-certificate-pilot --order-pilot-items 8 --order-pilot-thinking-tokens 2048 --seed 42 --output audit/order_certificate_pilot_dev8_contract_v2_real_20261008
```

The process-local caffeinate assertion ends with the process; no persistent
power setting was changed. Offline flags prevent downloading new model files.
Exec session: `94084`. Initial journal inspection confirmed two completed real
generations, two executions and two arm records (six entries), with
`mock=false`, eight train questions, `order-contract-v2`, native cap 2,048 and
`evidence=measured_development_pilot`. Candidate-selection was then in progress.

Output [manifest](order_certificate_pilot_dev8_contract_v2_real_20261008/manifest.json),
[completed-call journal](order_certificate_pilot_dev8_contract_v2_real_20261008/calls.jsonl).
The final report/summary are not available until collection completes.

## Unattended follow-up and bounds

The app heartbeat `theo-d-i-pilot-ordering-v2-8-c-u` is ACTIVE, checking every
15 minutes in this thread and quiet while state is unchanged/non-actionable.
It is instructed not to start another process or change profiles, caps, seeds,
source, calibration/test use or historical runs. On completion it checks hashes,
journal, 56 generations/16 executions/32 records and saved-path scoring/token
math, then writes a separate offline review and reports briefly. Failure preserves
all evidence and requires user attention, not an automatic restart. The heartbeat
should disable itself after the completed/failed handoff.

The [pre-generation plan](order_dev8_contract_v2_plan_20261008.md) bounds the
run. N=8 is exposed development with one seed; changed prompts/parser/cap cannot
be treated as an isolated ablation against N=2. No confirmatory, superiority,
noninferiority, authenticated-checkpoint or Stage 0 pass is claimed. Source
hashes of old runs are historical and were not rewritten. No Git commit,
push, pull, reset, personal-file-indexing or RAT change was performed here.
