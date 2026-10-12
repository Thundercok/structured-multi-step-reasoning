# Development data and scoring validation

Overall assessment: **Needs revision before main-study release**.

This is a Codex AI-agent audit, not a record of independent human approval. No model calls or policy fitting occurred.
Semantic and answer review covers only train/calibration/dev/calib. Test content was not displayed or semantically reviewed; automated isolation checks used IDs, structural fingerprints and hashes without test labels.

## Verified calculations and coverage

| Dataset | Development answers verified | Groups by split | Structural classes crossing splits |
| --- | ---: | --- | ---: |
| data/nckh_reasoning_dataset_draft.json | 54 | {'test': 4, 'calibration': 6, 'train': 12} | 0 |
| data/gen_v2.json | 108 | {'dev': 36, 'calib': 72, 'test': 72} | 1 |
| data/gen_tune.json | 60 | {'dev': 24, 'calib': 36, 'test': 34} | 2 |

The curated audit covers 54 variants of 18 original development groups. Procedural checks cover 168 development items, using query-parsed arithmetic, exhaustive ordering constraints, and exact rational evaluation of Game-of-24 references. All intended development labels agreed with those checks; wording repairs made previously implicit assumptions explicit.
The order fingerprint canonicalizes clue graphs under every renaming and retains the asked rank. Matching fingerprints identify renamed logical instances; groups defined only by generated IDs miss this overlap. No held-out question or label was used to tune a scorer.

## Issues repaired

- **High:** ordering and arithmetic checkers accepted negation/alternative answers. They now match an entire scalar/name response, with a bounded unit vocabulary and consistent asserted rank.
- **High:** Game-of-24 ignored contradictory equality suffixes and generic parsing discarded the expression. The checker validates the whole equality; typed extraction and voting preserve expressions through CoT, SC, selection, ReAct and PAL.
- **High:** legacy parsing reduced contradictory Yes/No text to its first word. Research text extraction retains the complete final response for exact scoring.
- **Medium:** correct Vietnamese text labels were rejected and decimal commas could be stripped as thousands separators. Development items now declare finite text aliases or a decimal separator; no substring or label-dependent normalization is used.
- **Medium:** river crossing lacked capacity/rowing rules, pizza wording assumed consumption, travel variants omitted duration facts, and two translations changed the noun/domain. Ten development wording repairs restore explicit assumptions and matching facts.
- **High:** hard-coded reviewed/human labels lacked a reviewer record. Development rows now say agent_reviewed with human review pending; the legacy gold table recalculates labels and states its actual review status.

## Remaining release requirements

- Assign canonical problem identities and create fresh disjoint splits before a main study. Existing test rows were preserved for audit integrity rather than silently reassigned.
- Namespace procedural IDs by dataset release and prevent overlap between tuning and evaluation releases. Adapt dev/calib names and missing root/answer-type metadata to the supported research schema in the next preparation step.
- Obtain independent human review and establish ownership/source records for descriptive template origins. A CC-BY declaration alone is not a provenance record.
- Perform the held-out review through a separate process after scoring/prompt rules are frozen. This audit does not confirm any held-out answer or change Stage 0.

## Source evidence

The calibration Betty problem is an English adaptation of the official GSM8K training record at line 3, rather than a verbatim original. Its source label agrees. The pinned source revision and question/file fingerprints are in [source evidence](../development-source-evidence.json). The official repository records an [MIT license](https://github.com/openai/grade-school-math/blob/3101c7d5072418e28b9008a6636bde82a006892c/LICENSE). Paraphrase/translation provenance is recorded for all three development variants.
Other curated source strings describe task genres; this audit could not establish an upstream revision or a rights-holder declaration for them. The draft root now describes mixed item-level declarations rather than presenting a single verified license.

## Curated group review

| Group | Split | Verified label | Independent calculation or proof | Variant review |
| --- | --- | --- | --- | --- |
| grp_pal_003 | calibration | 5 | 100 - 100/2 - 15 - 2*15 | Official GSM8K training record matched semantically, not verbatim; local en_orig is an adaptation. |
| grp_pal_004 | train | 192 | (2*16 + 2*8)*4 | Repaired consumption assumption: all variants now ask for slices contained in purchased pizzas. |
| grp_pal_005 | train | 129.6 | 150 * 80/100 * 108/100 | Facts, units, relationships and requested target agree across the three variants. |
| grp_pal_006 | calibration | 285 | 75*2 + 90*3/2 | Facts, units, relationships and requested target agree across the three variants. |
| grp_pal_007 | train | 84 | 2*(24+18) | Facts, units, relationships and requested target agree across the three variants. |
| grp_pal_008 | train | 40 | (320 - 2*120)/(4-2) | Facts, units, relationships and requested target agree across the three variants. |
| grp_react_001 | calibration | 9501 | 345*28 - 1240/5 + 89 | Facts, units, relationships and requested target agree across the three variants. |
| grp_react_002 | train | 1167 | 24*18 + 15*25 + 30*12 | Facts, units, relationships and requested target agree across the three variants. |
| grp_react_003 | train | 146 | 15/100*840 + 25/100*620 - 30/100*450 | Facts, units, relationships and requested target agree across the three variants. |
| grp_react_004 | train | 440 | 145+210+85 | Restored the same three duration facts in paraphrase/translation; irrelevant facts still affect difficulty and routing features. |
| grp_react_005 | calibration | 1500 | 450+520+610-80 | Facts, units, relationships and requested target agree across the three variants. |
| grp_react_007 | train | 210 | 3*(45+55) - 4*(120-85) + 250/5 | Facts, units, relationships and requested target agree across the three variants. |
| grp_plain_002 | train | No | Countermodel: rose is a flower that fades slowly; lily is a flower that fades quickly. | Changed Vietnamese species-level wording to individual flowers; countermodel establishes non-entailment. |
| grp_plain_003 | train | E | Exhaustive ordering: 1 consistent order, E-D-C-A-B. | Facts, units, relationships and requested target agree across the three variants. |
| grp_plain_004 | train | Thursday | Tuesday index 1 + 100 days modulo 7 = Thursday index 3. | Facts, units, relationships and requested target agree across the three variants. |
| grp_plain_005 | train | Yes | All consistent strict age orderings put Tom before Tyke. | Facts, units, relationships and requested target agree across the three variants. |
| grp_plain_006 | calibration | Goat | Boat carries farmer plus one item; only removing Goat leaves a safe unattended starting bank. | Added farmer-plus-one boat capacity, farmer-only rowing and unattended-bank rules in all variants. |
| grp_plain_007 | calibration | Equal | Both masses are exactly 1 kg, using the ordinary mass interpretation. | Corrected Vietnamese iron to steel; both equal mass labels remain valid under ordinary mass interpretation. |

## Cross-dataset identity checks

- ['data/nckh_reasoning_dataset_draft.json', 'data/gen_v2.json']: 0 shared group names; 0 shared canonical problem identities.
- ['data/nckh_reasoning_dataset_draft.json', 'data/gen_tune.json']: 0 shared group names; 0 shared canonical problem identities.
- ['data/gen_v2.json', 'data/gen_tune.json']: 94 shared group names; 1 shared canonical problem identities.

## Reproduction

```bash
python -m scripts.audit_development_data --output audit/development-data-audit-new
```

Detailed per-item development proofs and blind held-out row fingerprints are in checks.json. Existing output directories are never overwritten.
These checks establish data/scoring properties. They provide no measured model-quality, inference-cost or online-latency evidence.
