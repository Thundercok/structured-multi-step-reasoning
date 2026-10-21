# Fresh-base CoT restart adapter: offline acceptance

The adapter in `experiments/cot_restart_fresh.py` exercises a new base O, then F
at requested q=0.50 and CONT on the same question, with optional A. It selects
one representative per original group by item ID before seeing outcomes and
uses the existing dataset validator to preserve canonical split separation.

All executions are synthetic software checks. The adapter accepts only explicitly
synthetic fixtures and the offline MockLLM backend; it cannot enable real inference.
The 71-item candidate review packet is not collected or semantically inspected.
No main-study sample size, margin, utility weight, budget or decision rule is frozen.

Base O is collected greedily once per question with original prompt/completion IDs,
including EOS. F/CONT/A use temperature 0.6, top_p 0.95, fresh caches and one
cap-independent seed per item/arm. Prompts contain no gold. Prefixes exclude the
first explicit final-answer block; actual q and empty-prefix collapses are recorded,
and collapsed cases are retained rather than selected away. The mock's equal new
completion caps are software parameters, not a registered M/D budget design.

Each call journals a fsynced start before generation and its token-preserving
completion after scoring. Resume binds source, dataset and settings; completed
resume leaves artifacts unchanged. An unfinished attempt is preserved and blocks
automatic retry. A failure must receive separate budget handling before any future
real collector can reuse this mechanism. Token costs count base O once per selected
path plus the chosen extra arm; collection counts each executed mock call once.
These are synthetic token counts, not full inference costs or online latency.

Historical generation sources, entry point and hashed plans remain unchanged.
`python -m experiments.research_study` remains the supported research entry point;
its future fresh-data mode will need a separately versioned execution freeze after
review, power, budgets and the decision implementation are complete. This adapter
does not add a second real-model research entry point.

Auxiliary software check, using three authored fixtures only:

```bash
python3.12 -m scripts.smoke_cot_restart_fresh --output audit/NEW_SYNTHETIC_FRESH_SMOKE
python3.12 -m pytest tests/test_cot_restart_fresh.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Stopping condition for this implementation step: fresh-base/arm collection,
original IDs/EOS, outcome-blind prompts/seeds, costs, failure/resume and headless
acceptance pass on mock fixtures while historical plan verification still passes.
Human data review and a reviewed execution freeze remain necessary for real calls;
Stage 0 is unchanged.
