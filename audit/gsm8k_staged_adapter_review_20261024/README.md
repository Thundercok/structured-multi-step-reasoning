# Staged adapter follow-up — 2026-10-24

**Request changes; measured staged remains locked.** Targeted source review
finds three unmet adapter contracts. No candidate content or real inference
used, no production files changed, bridge and Stage 0 unchanged.

The exact ten-file suite from the handoff was rerun separately: **179 passed
in 9.83s**, exit 0. Passing it does not cover the three source contracts below.

1. **[P2] Apply the supplied generation seed.**
   `QwenMLXStagedRunner.run_generation` accepts `seed` but never uses it.
   Neither the new collector nor `_chat` applies the MLX seed on this path.
   Apply it at the generation boundary through an injectable seed setter and
   test the exact derived seed before dispatch. Temperature zero does not make
   an unused seed a correctly implemented recorded execution contract.
2. **[P2] Persist the prompt actually consumed by generation.**
   The runner renders a template independently, then `_chat` renders again.
   If rendering returns token IDs, `raw_prompt_text` becomes None and the IDs
   are not retained. Capture prompt/messages/token IDs from the actual `_chat`
   invocation's trace, not a separate rendering; decode only as an additional
   view. Test a tokenizer returning token IDs and verify the recorded IDs are
   exactly those dispatched. Current parity tests replace `_chat`, so they
   cannot establish this generation-boundary property.
3. **[P2] Restrict or remove invented-message fallback.**
   Collector `_build_record_from_evidence` still substitutes the bare query
   when `messages` is None, contrary to the handoff's complete-removal claim.
   Require real trace evidence for this adapter. If old synthetic fixtures
   need a fallback, make it explicitly synthetic and do not represent it as
   the messages actually sent. Test missing trace fields and interrupted/resumed
   reconstruction, not just the happy path containing messages.

Combined execution with `test_qwen_mlx_backend_mocked.py` yielded **1 failed,
202 passed, 2 skipped**: checker `test_no_forbidden_imports` saw `mlx` already
in global `sys.modules`. This is not proof checker imported MLX: the assertion
is process-global and the mocked suite can populate module stubs. Isolate the
import contract in a fresh subprocess with blocked forbidden imports. Do not
claim this combined suite passed, or weaken the no-model import contract.

The existing parity comparisons are useful for public parsing/confidence and
tool fallback, and measured evidence rejection is present. They do not yet
certify real-tokenizer prompt fidelity or seed execution. Historical H1–H3
fixture acceptance remains scoped to its reviewed source; these adapter changes
need their own fingerprints and acceptance. Return the three concrete points
above for repair; no new study or inference budget is authorized.
