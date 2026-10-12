# GSM8K fixed-strategy development pilot — 2026-10-04

Question: does this fixed model have a useful tool-assisted alternative to
always-CoT, before fitting a router? This is a separate math development
experiment; it does not replace the mixed-family main study.

## Frozen pilot inputs

- Official source: [GSM8K](https://github.com/openai/grade-school-math/tree/3101c7d5072418e28b9008a6636bde82a006892c), MIT; only `train.jsonl`, README and LICENSE downloaded and matched to upstream Git blob hashes. The official test file was not downloaded.
- Seed 42 ranks normalized question identities without labels/outcomes. Select 24, assign alternating ranks to development train/calibration. Identity does not detect arbitrary semantic paraphrases.
- Agent review checks arithmetic with exact fractions. Exclude `gsm8k-dev-03628` before generation: source assumes 66 full forward/backward cycles (330 steps), but first arrival at the mailbox is 318 steps. Keep the candidate and exclusion evidence.
- Retain 23 questions / 23 groups, 11 train and 12 calibration, in `data/gsm8k_development_reviewed_v1/dataset.json`. Both splits are exposed development. Human review remains pending; no held-out evaluation or policy fitting.
- Model: local `mlx-community/Qwen3-8B-4bit` snapshot `545dc4251c05440727734bcd94334791f6ab0192`, authenticated using the saved upstream provenance. Rehash runtime content before loading.
- Three conditions per question: DIRECT, CoT and PAL, profile `english-math-v1`. Freeze all three English suffixes in the source commit. DIRECT requests a bare number; CoT adds concise steps; PAL requests arithmetic Python assigning `result`, without imports.
- Generation seed 42, strategy-specific draw seeds, deterministic condition order, temperature 0, `enable_thinking=False`, cap 1,024 per call. Do not change decoder or confidence formula in this pilot.
- 69 generations at most, one generation per condition, maximum 70,656 generated tokens. PAL has one execution attempt, existing helper timeout 5 seconds, no model retry. The helper is for this controlled development environment, not a security boundary.

## Measurement and decision

Use `python -m experiments.research_study --pilot`, headless, without Qt,
personal-file indexing, embeddings, training or controller fitting. Save raw
messages, completions, parsed answers, execution output, tokens and termination
reasons. PAL records execution duration separately; it is included in strategy
duration. Generated tokens exclude prompt/prefill/full inference costs. Model
loading and online controller overhead are not part of strategy duration.

Report all 23 questions together, plus development-split counts; compare
accuracy, mean generated tokens, parse/length failures and PAL execution
success. Count questions CoT misses that PAL solves, and reverse changes.
Any gold-informed ceiling must be labelled as non-deployable. No significance,
controller superiority, public benchmark score or calibrated confidence claim.

If PAL supplies complementary correct outputs at useful costs, prepare a
separate development validation comparison with fixed strategies and a simple
input rule before fitting the full policy. If fixed strategies already solve
nearly everything or PAL adds no useful alternative, narrow the question and
revisit development coverage; do not infer benefit from this exposed sample.
Stage 0 remains the existing internal-development PASS, with publication review
and the main-study freeze still pending.

## Preparation and collection

```bash
python -m scripts.prepare_gsm8k_development --source audit/gsm8k-source-20261004 --output data/NEW_GSM8K_CANDIDATE
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
python -m pytest tests/test_research_pilot.py test_qwen_mlx_backend_mocked.py tests/test_gsm8k_development.py -q
python -m experiments.research_study --backend smoke --pilot --strategies DIRECT COT PAL --prompt-profile english-math-v1 --max-tokens 1024 --output runs/NEW_GSM8K_SMOKE
```

The saved candidate review expressions/exclusion are agent review evidence;
humans must still review wording, labels and broader group overlap before a
main study. Run collection from a clean pinned source checkout:

```bash
python -m experiments.research_study --backend mlx --pilot \
  --dataset /absolute/path/to/data/gsm8k_development_reviewed_v1/dataset.json \
  --model /absolute/path/to/pinned-local-snapshot \
  --model-provenance /absolute/path/to/model_provenance.json \
  --strategies DIRECT COT PAL --prompt-profile english-math-v1 \
  --max-tokens 1024 --groups-per-stratum 12 --seed 42 \
  --output /absolute/path/to/NEW_MEASURED_RUN
```

The placeholders must be replaced with the saved reviewed dataset and verified
local model/provenance. Output directories are never overwritten. A raw pilot
summary or software test pass does not supply human/publication approval.
