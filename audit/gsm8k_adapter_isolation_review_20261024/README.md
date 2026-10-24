# Adapter offline parity/import acceptance — 2026-10-24

**Accept the repaired offline parity/import-isolation scope.** Supersedes the
exit-134 blocker in `audit/gsm8k_staged_adapter_acceptance_20261024/README.md`
for the source fingerprints recorded in [verification.json](verification.json).
No production files were edited by this review.

Fresh reruns, each in a separate process:

- Exact ten-file regression suite: **186 passed in 10.97s**, exit 0;
  [captured output](regression.txt).
- Mocked backend/checker pair: **46 passed, 2 skipped in 3.05s**, exit 0;
  [captured output](combined.txt). The two native-bfloat16 cases remain untested
  in this environment. No claim of 48 passes is made.
- Repair verification copied into this new directory and rerun: exit 0;
  [script](verification.py), [stdout](probe_stdout.txt),
  [results/source hashes](verification.json). Previous artifacts unchanged.

Source inspection and probes confirm the injected seed/sampler/numerical
boundary, exact token-ID capture from generation, staged missing-message
rejection and trace reconstruction coverage. The fresh import-blocking
subprocess exercises legacy and staged Python paths with authored generation/
tool fixtures without importing MLX or mlx_lm. This verifies tested Python
contracts, not output quality or native MLX generation on actual weights.

Measured staged evidence remains rejected. No candidate questions/solutions,
model weights, real generation or embedding calls were accessed/invoked.
Inference budget 0; bridge, checker acceptance and Stage 0 unchanged.

## Deferred before measured use

Keep actual model/tokenizer/template provenance, hardware/package freeze,
human/source/semantic-data review and custody/access procedure separate.
`QwenMLXBackend.set_seed` still catches exceptions in its non-injected MLX
branch; a measured execution must fail closed or explicitly report unapplied
seed rather than silently claiming it applied. This real-branch behavior is
outside the injected fixture acceptance and must be addressed before opening
the measured gate. Native bfloat16 checks and real backend accounting/latency
are likewise not established by this review.

Next research work is the pending data/configuration review and measured-run
readiness decision. This acceptance does not itself authorize opening the
candidate, enabling measured staged ingestion, downloading/loading a model or
allocating the proposed 288-call budget.
