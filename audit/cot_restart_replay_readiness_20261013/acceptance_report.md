# CoT restart replay readiness

CPU preparation completed. No real-model calls or downloads; Stage 0 unchanged.

| Check | Result |
| --- | --- |
| T1 — backend request invariance | PASS; only max_tokens differs |
| T2 — EOS at L-1, L, L+1 | PASS; EOS counts in completion tokens |
| T3 — direct mock vs replay | PASS; 1,200 randomized cases, zero text/finish/parser mismatches |
| T4 — addendum journal | PASS; 12 synthetic records include original IDs, seed and provenance |
| T5 — historical tokenizer audit | FAIL; only 122/136 counts match after EOS adjustment |

The final targeted/research regression suite passed 63 tests. See validation.json
for exact commands, source hashes and the installed backend source identity.
Passing software tests is not evidence of measured model quality.

Historical text roundtrips pass 136/136; literal token-count matches are 59/136.
Fourteen completions still disagree under the EOS-aware convention. The historical
backend version is unverified. Detailed rows are in report.md and token_audit.json.
Historical artifact hashes and the journal head were rechecked and remain unchanged.

New completions now preserve prompt/completion IDs, EOS, seed, fixed decoding
kwargs, tokenizer assets/package versions and backend source/version. Future seeds
exclude budget; changed source/runtime cannot resume an old generation directory.
The causal mock really truncates output. Replay rescores prefix plus retained text
and refuses text-only records, unsupported stopping rules or increased caps.

Legacy arms remain at their original caps. No paired M/D estimate is produced:
CONT IDs alone do not make historical A/F records eligible. Before further model
calls, review/freeze the next call budget, all required arms, practical margin,
primary L_i/T* and the prospective sensitivity plan in the protocol.
