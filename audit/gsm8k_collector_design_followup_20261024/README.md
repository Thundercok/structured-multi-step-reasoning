# Revised collector design — follow-up, 2026-10-24

**Verdict: suitable to move into fixture-only implementation with the corrections
below incorporated. Not software acceptance or permission for real collection.**
This reviews the second user-forwarded design against the prior D1–D6 report.
No production code/protocol was edited, no new tests run, no candidate content
opened, no model/embedding calls made. Budget remains 0 and Stage 0 unchanged.

## Design decisions now aligned

- D1: durable started-only attempts are unknown, counted, reserved and halted;
  no implicit redispatch. A new attempt requires separate authorization.
- D2: generation, tool and assembled-record stages are separated; generation
  evidence is persisted before tool execution. Two semantic corrections remain
  below.
- D3: torn/invalid chains fail closed without trimming; a stale manifest head
  may advance only to a verified journal descendant under the validated identity.
- D4: retain five named report rows and the fitting-selected primary contrast;
  reuse the existing fitter signature and supported research module entry point.
- D5/D6: expose a fitting-only command boundary and externally hash selection;
  implementation must make the boundary/provenance details below concrete.

## Correction F1 — Unknown cost must not be stored as measured cost

The revised generation-failure event still specifies `measured_tokens: 1024`.
That is a conservative budget charge, not a measurement. Use separate fields:

```json
{
  "status": "failed",
  "measured_generated_tokens": null,
  "budget_charge_tokens": 1024,
  "cost_status": "unknown_reserved"
}
```

Field names are illustrative, not a new frozen schema. Preserve known valid
measured counts when available; charge conservatively where uncertainty remains
without promoting a reservation to measured cost. Keep a failed/unknown
generation out of the complete analyzable bank. Include measured and reserved
totals separately in accounting/reporting. Test known partial counts, fully
unknown outcomes and malformed token metadata.

## Correction F2 — PAL tool failure must preserve existing parsing semantics

The state diagram says `ToolFailed -> AssembledRecord: Parse error output`.
Current `qwen_mlx_backend.py:_pal` instead parses the original model response
when `ok=False`; tool diagnostics remain in `trace.tools`. The offline
`validate_records` checks the same contract. Parsing a traceback/timeout message
as an answer would change the recipe and can make the new collector's records
incompatible with the accepted evaluator.

Required behavior: tool success uses recorded tool output; tool failure retains
diagnostics and parses the generation output using the existing typed parser.
Persist measured generation tokens in both cases; do not add a model call or
re-execute the tool. Assemble the existing record keys, including `answer`
(not only the draft's `parsed_answer`), `correct`, timing and full trace.
Fixtures must use distinguishable values in model text and tool error so they
detect the wrong source being parsed, not merely assert a failure count.

## Implementation acceptance conditions; no additional design cycle needed

1. **Actual dispatch boundary:** existing `_pal` performs generation and tool
   execution inside one `backend.run`. A wrapper that journals only around that
   call cannot meet the staged guarantee. Implement/test an explicit stage hook
   or adapter seam with equivalent prompts, decoding, parser, confidence and
   tool behavior; do not certify the real backend from a more capable mock.
   Keep this opt-in and preserve the already closed bridge scope.
2. **Failure/record recovery:** specify whether completed terminal evidence
   permits pure record reconstruction. Unknown generation/tool outcome halts;
   never silently rerun either stage. Assembly must reproduce measured timing
   and public trace from persisted data, not replace them with resume latency.
3. **Sealed CLI integration:** `--gsm8k-routing-fit` is proposed, not an existing
   CLI flag. Current `--gsm8k-routing-analysis` always calls `fit_selection`
   again and writes a new selection. Add explicit orchestration/compatibility
   checks so validation consumes the original sealed selection, never silently
   refits it. Keep the legacy analysis path's evidence scope explicit. Test
   invocation through `python -m experiments.research_study`.
4. **Exposure scope:** distinguish metadata access from validation outcome
   access. Existing frame checks inspect roles/query metadata; that is not label
   leakage. A split view of one common journal requires a real read/filter
   boundary, not just two names for the same file. Enumerate logs, tracebacks,
   partial records and journals. Assign an actual custodian/operator procedure;
   log supported-command access and declare that arbitrary manual reads are
   outside application enforcement. Do not claim filesystem blinding merely
   from an `AssertionError` fixture or a headless process label.
5. **Freeze completeness:** retain the full D6 list, including tokenizer/template
   files beyond `tokenizer.json`, packages/platform, ordered conditions and
   protocol/parser/tool source. Preserve a trusted external seal reference;
   a mutable file and mutable manifest alone are not a tamper-proof freeze.

Implement these conditions on authored fixtures, then review the code and
failure probes. Do not expand into candidate collection or design new rules.
The prior 288-call envelope remains a proposal. No new research signal,
selection policy or model-quality claim is introduced by this design review.
