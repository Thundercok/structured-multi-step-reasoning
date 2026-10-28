# Entry evaluation verification — 2026-10-29

The user authorized one focused test batch and one offline smoke, conditional
on preserving the active VRPTW workload. No solver files, processes, environment
or settings were modified. No real model was loaded or called.

## Software regressions

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTEST_ADDOPTS= \
nice -n 19 python -m pytest tests/test_entry_evaluation.py \
  tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Actual result: **50 passed in 66.75s**. Raw stdout/stderr is in `pytest.log`;
`pytest.xml` contains the JUnit result. No unrelated suite was run.

The sandbox denied the initial `nice` call while still launching pytest; the
raw log retains that warning. The test process initially ran at normal priority
with one compute thread. An elevated, command-verified `renice 19` request for
only that pytest PID completed late in the batch. This is not evidence that
the full test run had reduced scheduling priority.

## Saved-output smoke

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 nice -n 19 \
python -m experiments.research_study \
  --entry-evaluation runs/smoke-42 --entry-configs old scaler_only pca32 \
  --entry-folds 3 --entry-repeats 1 --entry-bootstrap 200 --seed 42 \
  --output runs/entry-development-smoke-20261029
```

This run executed outside the sandbox so `nice` could apply. A read-only process
snapshot confirmed its niceness was **19**, while the VRPTW controller/worker
remained active at their original normal priority. Memory free percentage was
48% before/during tests and 50% during smoke on an 8-physical-core host. These
observations establish continued solver activity, not zero performance impact
or controlled timing isolation. Do not treat concurrent VRPTW timing as an
otherwise idle-machine benchmark on the basis of this verification.

Result: successful `synthetic_development_cv`, 168 OOF predictions over 24 train
items and seven methods, three group-isolated folds, 24 test items excluded,
and zero selected configurations or real-model calls. Current evaluator source
hashes and emitted artifact hashes matched at read-only inspection. The
synthetic accuracy/utility values are software evidence only; they do not
establish a measured model improvement or change Stage 0.

`input-run/` retains an exact copy of the frozen synthetic input run. Its
original source fingerprints remain historical. `smoke-evaluation/` retains
an exact copy of the generated output, including its input-manifest binding,
predictions, folds, targets, calibration, summary and current-source hashes.
The archived output's recorded input path still names the original local
`runs/smoke-42` directory; this copy is evidence preservation, not a second run.
