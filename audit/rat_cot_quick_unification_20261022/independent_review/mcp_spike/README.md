# MCP tool reuse probe — 2026-10-22

**13/13 cases passed.** Real `mcp==2.3.0` Python client, real
`@modelcontextprotocol/server-filesystem==1.0.0` Node subprocess, actual stdio
transport. No model, Qt, personal-file indexing, production dependency or runtime
changes. Files and the outside-root canary are authored temporary fixtures.

## Result and decision

The server's `read_text_file` schema is discovered and registered as the single
RAT operation `mcp_read_text_file`. Calls go through the existing
`CapabilityRegistry`, `ActionDispatcher` and `ArtifactStore`; no second store,
conversation engine or agent loop is added. The probe adapter in
`scripts/dev/rat_mcp_tool_spike.py` bridges async MCP calls to the synchronous
dispatcher. MCP structured output becomes a `document_content` artifact;
`is_error` becomes a failed dispatch rather than a successful content artifact.

This demonstrates actual reuse of an external server, rather than testing a
new server written for the probe. **Keep MCP as an optional future connector
boundary; do not migrate the native tools or CoT runtime for this result.**
Plain text reading alone does not justify the extra process/dependencies or
remove an existing implementation. Use this path when a maintained external
server supplies a genuinely missing integration. No production LOC savings,
maintenance savings, agent quality or latency improvement has been measured.

## Checks

- Exact UTF-8 content, head excerpt and empty file; output/provenance and source
  reference stay attached to the RAT-created artifact and turn/execution IDs.
- Missing file, invalid argument type, unknown argument, outside-root path,
  symlink escaping the allowed root, and conflicting head/tail arguments.
- Cancellation before dispatch makes no remote call. Cancellation/reset after
  the actual read rejects publication of the late result. These cases do not
  prove interruption of a running remote tool.
- A write operation is not registered, makes no remote call and leaves fixture
  bytes unchanged. The external reference server itself advertises write tools;
  the adapter allowlist is not a read-only OS sandbox for that whole process.
- The SDK-managed child is observed via its actual process handle and is reaped
  on client close. An initial harness attempt used host process enumeration,
  which the sandbox denied. Its log is preserved separately; the probe now
  observes only the SDK's own child, delegating the real spawn unchanged.

Python sockets and Node networking are blocked during execution; package
installation uses network. There are zero model calls. Source hashes for kernel,
UI, research runner and requirements match before/after the successful probe.

## Limits

Only this one tool/schema/result shape was evaluated. The synchronous bridge
must run off the owning async loop; blocking it directly on the Qt/main loop
would be inappropriate. It is development code, not a general production MCP
integration. No reconnect, crashed-server recovery, large/binary-file handling,
server trust review, Qt lifecycle or packaging acceptance is claimed.

The existing indexed `read_document`, PDF/OCR readers and their contracts are
unchanged. The reference server reads text; this is not a drop-in replacement
for those richer semantics. The returned-text digest describes returned text,
not a claimed hash of an entire source file when an excerpt was requested.

The npm package's license field says `SEE LICENSE IN LICENSE`, but that file
was absent in the installed package. Resolve provenance/notices with the
[upstream repository](https://github.com/modelcontextprotocol/servers) before
production adoption; this probe does not certify licensing of all dependencies.

## Reproduction and evidence

Create fresh temporary Python and Node targets. Install `requirements.lock`
with pip's `--target`/`--only-binary=:all:`; copy this directory's `package.json`
and `package-lock.json` to the Node target and run `npm ci --ignore-scripts` there.
Then, using the repository `.venv` for its existing dependencies:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/dev/rat_mcp_tool_spike.py \
  --dependency-target /absolute/path/to/python-target \
  --node-prefix /absolute/path/to/node-target \
  --output /private/tmp/rat-mcp-repro-result.json
```

This run used Node 20.18.0/npm 10.8.2. Exact temporary paths, package/source
hashes and versions are in `environment.json`. Locks pin the successful install;
`install_report.json` records Python wheel sources and hashes, while the npm
lock records tarball integrity. Fixtures are recreated on every execution.

Raw logs/results: `probe.txt`, `result.json`, `install_python.txt`,
`install_node.txt`, `probe_process_inspection_blocked.txt`.

Primary references: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
[filesystem server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem),
[client lifecycle and tools](https://py.sdk.modelcontextprotocol.io/client/).
