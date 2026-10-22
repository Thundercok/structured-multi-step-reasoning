# PydanticAI integration spike — 2026-10-22

Actual SDK: `pydantic-ai-slim==2.59.0`. Scripted `FunctionModel`; authored `.app`
fixtures and injected launcher only. No real model requests, OS launches, Qt,
personal-file indexing or production runtime integration. This is not a model
quality, performance or inference-cost benchmark.

**Result: 9/9 checks passed.** Eight cases compare the direct RAT dispatcher
with the real SDK tool-call path: success, ambiguous input, wrong type, unknown
argument, launcher error, cancellation before/during tool execution, and a
conversation reset during execution. A ninth case checks SDK request limit 0.
Assertions check outcome parity, side-effect counts, artifact identity/revision,
turn/execution provenance, and absence of committed results after cancellation.
The source/requirements hashes were unchanged over the probe.

## What this establishes

An existing operation schema can be exposed without copying it, and execution
can continue through RAT's existing dispatcher/store. `make_sdk_tool` in
`scripts/dev/rat_agent_sdk_spike.py` is the small development bridge. SDK model
request/tool-return handling and its zero-request guard worked in these fixtures.

## What this does not establish

- No RAT production code was removed or replaced. There is no measured LOC,
  maintenance-time or model-quality improvement yet.
- `Tool.from_schema` explicitly skips schema argument validation in this SDK
  version. RAT's existing validator rejected the invalid inputs; the SDK did
  not replace it. The inspected implementation is saved in
  `sdk_from_schema.py.snapshot`.
- Cancellation tests exercise the tool/commit boundary. In the SDK path,
  even `cancel_before` makes two scripted model requests; this does not prove
  early cancellation of real inference or active tool abortion.
- Source revision 1/provenance were checked; revision updates/lookback and full
  conversation lifecycle were not tested in this one-operation probe.
- `FunctionModel` token usage is synthetic. Real model calls/tokens are zero;
  no online latency or full inference-cost claim is made.
- MCP transport, Ollama/MLX integration, streaming, Qt lifecycle and packaging
  were not evaluated. Passing here is not acceptance of a replacement agent.

## Decision

**Keep PydanticAI out of production requirements for now.** The bridge is
feasible, but this wrapper alone adds a dependency without removing existing
runtime responsibility. A later adoption needs a concrete provider/tool-loop
implementation to replace and a complete cancellation/accounting mapping.
MCP connector reuse remains a separate next candidate, not a completed result.
Keep the existing CoT controller, headless study, model owner and Quick UI.

## Reproduction

Use the repository's current `.venv` for its existing dependencies. Install the
locked optional SDK wheels into a fresh temporary target, then run the script:

```bash
SDK_TARGET=$(mktemp -d /private/tmp/rat-agent-sdk-repro.XXXXXX)
.venv/bin/python -m pip install --only-binary=:all: --ignore-installed \
  --target "$SDK_TARGET" \
  -r audit/rat_cot_quick_unification_20261022/independent_review/sdk_spike/requirements.lock
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/dev/rat_agent_sdk_spike.py \
  --dependency-target "$SDK_TARGET" --output /private/tmp/rat-sdk-repro-result.json
```

The install uses network for packages; execution blocks network sockets and OS
launches and disables real SDK model requests. `requirements.lock` and the pip
report describe the temporary environment only, not RAT's required dependencies.

Raw evidence: `probe.txt`, `result.json`, `install.txt`, `install_report.json`,
`environment.json`, and `requirements.lock`. Temporary fixture bundle paths in
the report describe the run; the script recreates fixtures when repeated.
