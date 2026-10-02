# Project priorities

The primary outcome is a student research paper (NCKH) supported by a reproducible
experiment pipeline. RAT is a secondary demonstration for a nontechnical user.
Read `docs/research_plan.md` and `docs/research_protocol.md` when changing research
scope, evaluation, model behavior or project claims.

Prioritize reviewed data, valid comparisons, raw artifacts and manuscript evidence.
UI expansion is secondary unless the user explicitly requests it. Keep research
experiments headless and independent of personal-file indexing and Qt.

The supported research entry point is `python -m experiments.research_study`.
Legacy simulator outputs, notebook claims and passing software tests are not
evidence of measured model quality. Label synthetic results and proposed
contributions explicitly. Keep train, calibration and test groups disjoint.

Preserve the existing Stage 0 gate for the Qwen/Meta-Reasoner campaign; adding
experiment infrastructure does not establish that the gate has passed. Prefer
smoke validation while real-model experiments remain pending review.

For changes to the research harness or threshold fitting, run:

```bash
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Publish only claims supported by reviewed run artifacts. State whether costs are
synthetic, generated-token counts, or full inference costs, and distinguish
replayed strategy time from measured online latency.
