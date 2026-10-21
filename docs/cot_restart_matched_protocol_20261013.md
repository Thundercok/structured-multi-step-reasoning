# Proposed A/F/CONT development collection

Status: CPU/tokenizer preparation and synthetic execution only. Real generation
requires explicit approval of the prepared snapshot, seeds, calls and ceilings.
The user has fixed F at q=0.50. No lambda, practical margin or GO/NO-GO rule is
fitted or enabled for this 12-question diagnostic. Stage 0 remains unchanged.

Use all 12 historical exposed-development questions, independent of correctness.
Reuse their fixed visible base traces as intervention inputs; do not regenerate
the base or select only wrong questions. A has empty rationale, F retains the
historical sentence-snapped q=0.50 prefix and CONT retains the full rationale
before its first answer block. These are newly rendered/pre-filled prompts,
not restored original base token or KV checkpoints.

One fresh draw per item/arm gives 36 attempted calls. Prompts containing gold or
correctness are forbidden: preparation stores only query/prefix/IDs and logged
base token counts. Record collapsed/identical prompts; these do not establish
distinct interventions. Seeds use item/arm/call, without budget. Sampling is
temperature 0.6, top-p 0.95, no native thinking, fresh cache, no draft model,
no logits processors and no stop strings. Pin the existing local Qwen3.5-4B
4-bit snapshot and source/runtime identities; never download a checkpoint.

M remains at W=2048: L_i = W - P_i_CONT. Collect enough new completion to replay
L_i-8, L_i and L_i+8 for every arm. D proposes T*=2560, the next 256-token grid
point above the outcome-blind all-cell w=1 feasibility floor (2359 tokens with
the actual cached tokenizer). For each request:

    D_i,a(w) = T* - base_completion_i - w*(base_prompt_i + P_i,a)
    H_i,a = max(L_i+8, D_i,a(0), D_i,a(1))

All requested D caps must be positive. Generate once at H and replay the smaller
caps. This is a collection allowance, not a change to M's primary W. A flat
2056-token call limit has no common positive-completion T for all w=1 cells:
its feasible lower bound is 2359 while its upper bound is 2298.

The historical base count's EOS convention remains unverified. D is explicitly
conditional on those logged counts; it is not fully audited inference cost,
FLOPs, billing or online latency. No historical intervention completion is
reconstructed or substituted for a fresh A/F/CONT draw.

Preparation hashes the exact plan, all request IDs/caps/seeds, source, tokenizer
assets and installed backend runtime. Only the unchanged plan can run. Its
ceilings cover attempted calls and reserved prompt/completion tokens, including
failed attempts. No calls are automatically added for retries. Check the
eight-hour active-duration limit before each new call; this is not a mid-call
timeout. Journals preserve failed/incomplete runs and reject incompatible resume.

Supported commands:

```bash
python3.12 -m experiments.research_study --cot-restart-matched-plan --cot-restart-q-star .5 --output audit/NEW_PLAN
python3.12 -m experiments.research_study --cot-restart-matched-run audit/NEW_PLAN --cot-restart-matched-mock --output audit/NEW_SYNTHETIC_RUN
```

Only after explicit approval of that exact plan, use the same entry point with
`--cot-restart-matched-approved` instead of the mock flag. The approval flag is
an execution safeguard, not evidence of publication review or a Stage 0 pass.
All results remain exposed development and single draw. No probe fitting or
expanded 288-call experiment is authorized by this preparation.
