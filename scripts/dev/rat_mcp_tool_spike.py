"""Development probe of an actual filesystem MCP server through RAT's dispatcher.

Only authored temporary fixtures are used. The reference server is an external
Node subprocess; its write tools are deliberately not registered in RAT. Neither
this probe nor its optional dependencies are imported by production code.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[2]
OPERATION = "mcp_read_text_file"


def read_operation(client, remote, loop, wire, after_read):
    """A synchronous RAT operation backed by the SDK's async stdio client."""
    from rat.kernel.registry import OperationDefinition

    async def call(arguments):
        result = await client.call_tool(remote.name, arguments, read_timeout_seconds=5)
        wire.append({"arguments": copy.deepcopy(arguments), "response": result.model_dump(mode="json")})
        after_read()
        if result.is_error:
            text = "\n".join(block.text for block in result.content if block.type == "text")
            raise ValueError("mcp_tool_error:" + text)
        payload = result.structured_content
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), str):
            raise ValueError("mcp_invalid_structured_content")
        text = payload["content"]
        return {"found": True, "path": arguments["path"], "filename": Path(arguments["path"]).name,
                "content": text, "returned_chars": len(text),
                "returned_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "source_tool": remote.name, "source_server": "reference-filesystem",
                "requested_excerpt": "head" in arguments or "tail" in arguments}

    def handle(arguments, **context):
        # The caller runs the synchronous dispatcher in a worker thread, while
        # the SDK client remains on its one owning asyncio loop.
        future = asyncio.run_coroutine_threadsafe(call(copy.deepcopy(arguments)), loop)
        try:
            return future.result(timeout=7)
        except TimeoutError:
            future.cancel()
            raise ValueError("mcp_transport_timeout") from None

    return OperationDefinition(OPERATION, remote.description or remote.name,
                               copy.deepcopy(remote.input_schema), handle,
                               artifact_kind="document_content")


async def run_probe(args):
    from importlib.metadata import version
    from mcp import Client, StdioServerParameters
    from mcp.client import stdio
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.dispatcher import ActionDispatcher
    from rat.kernel.registry import CapabilityRegistry

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    entry = args.node_prefix / "node_modules/@modelcontextprotocol/server-filesystem/dist/index.js"
    package = json.loads((entry.parent.parent / "package.json").read_text())
    source_files = ["rat/kernel/registry.py", "rat/kernel/dispatcher.py", "rat/kernel/contracts.py",
                    "rat/kernel/capabilities/documents.py", "rat/engine/task_state.py",
                    "rat/ui/quick/PDFDesk.qml", "rat/ui/quick_pdf_controller.py", "reasoning/runtime.py",
                    "experiments/research_study.py", "requirements.txt", "requirements-research.txt"]
    hashes = lambda: {p: hashlib.sha256((PROJECT / p).read_bytes()).hexdigest() for p in source_files}
    before = hashes()
    rows, wire, children = [], [], []
    create_process = stdio._create_platform_compatible_process

    async def observe_spawn(*positional, **keywords):
        # Observe the SDK's actual child handle, without enumerating host apps.
        process = await create_process(*positional, **keywords)
        children.append(process)
        return process
    with tempfile.TemporaryDirectory(prefix="rat-mcp-fixtures-") as temporary:
        root = Path(temporary).resolve()
        allowed = root / "allowed"
        allowed.mkdir()
        text = "Dòng một — RAT\nDòng hai — CoT\nDòng ba — MCP\n"
        file = allowed / "bản_thử.txt"
        file.write_text(text)
        empty = allowed / "empty.txt"
        empty.write_text("")
        outside = root / "outside.txt"
        outside.write_text("AUTHORED_OUTSIDE_CANARY")
        (allowed / "escape.txt").symlink_to(outside)
        guard = root / "offline.cjs"
        guard.write_text("const blocked=()=>{throw new Error('probe_network_forbidden')};\n"
                         "require('node:net').Socket.prototype.connect=blocked;\n"
                         "require('node:tls').connect=blocked;\n"
                         "require('node:dns').lookup=blocked;\n"
                         "globalThis.fetch=blocked;\n")
        params = StdioServerParameters(command=shutil.which("node"),
            args=["--require", str(guard), str(entry), str(allowed)], cwd=str(root))
        with patch.object(stdio, "_create_platform_compatible_process", side_effect=observe_spawn), \
                patch("socket.socket.connect", side_effect=AssertionError("probe_network_forbidden")), \
                patch("socket.socket.connect_ex", side_effect=AssertionError("probe_network_forbidden")):
            async with Client(params, raise_exceptions=False, read_timeout_seconds=5) as client:
                discovered = await client.list_tools()
                remote = next(tool for tool in discovered.tools if tool.name == "read_text_file")
                assert "path" in remote.input_schema["properties"]
                assert any(tool.name == "write_file" for tool in discovered.tools)
                child_pids = [process.pid for process in children]
                assert len(child_pids) == 1, child_pids
                facts = {"server_info": client.server_info.model_dump(mode="json") if client.server_info else None,
                         "protocol_version": client.protocol_version,
                         "discovered_tools": [tool.name for tool in discovered.tools],
                         "read_tool": remote.model_dump(mode="json"), "observed_child_pids": child_pids}
                cases = [
                    ("utf8_read", {"path": str(file)}, "success", 1),
                    ("head_excerpt", {"path": str(file), "head": 2}, "success", 1),
                    ("empty_file", {"path": str(empty)}, "success", 1),
                    ("missing_file", {"path": str(allowed / "missing.txt")}, "error", 1),
                    ("invalid_type", {"path": 17}, "error", 0),
                    ("unknown_argument", {"path": str(file), "extra": True}, "error", 0),
                    ("outside_root", {"path": str(outside)}, "error", 1),
                    ("symlink_escape", {"path": str(allowed / "escape.txt")}, "error", 1),
                    ("conflicting_excerpt", {"path": str(file), "head": 1, "tail": 1}, "error", 1),
                    ("cancel_before", {"path": str(file)}, "cancelled", 0),
                    ("cancel_after_read", {"path": str(file)}, "cancelled", 1),
                    ("reset_after_read", {"path": str(file)}, "cancelled", 1),
                    ("write_not_exposed", {"path": str(file), "content": "must not write"}, "error", 0),
                ]
                for name, arguments, expected, expected_calls in cases:
                    registry, store = CapabilityRegistry(), ArtifactStore()
                    dispatcher = ActionDispatcher(registry, store)
                    context = {"execution_id": "exec-mcp-" + name, "turn_id": "turn-mcp-" + name}

                    def after_read():
                        if name == "cancel_after_read":
                            dispatcher.cancel_execution(context["execution_id"])
                        elif name == "reset_after_read":
                            dispatcher.reset()

                    registry.register_operation(read_operation(client, remote, asyncio.get_running_loop(), wire, after_read))
                    assert len(registry.list_operations()) == 1
                    assert registry.get_operation("read_document") is None
                    if name == "cancel_before":
                        dispatcher.cancel_execution(context["execution_id"])
                    count_before = len(wire)
                    op = "mcp_write_file" if name == "write_not_exposed" else OPERATION
                    result = await asyncio.to_thread(dispatcher.execute_operation, op, arguments, context=context)
                    calls = wire[count_before:]
                    assert result.status == expected, (name, result)
                    assert len(calls) == expected_calls, (name, calls)
                    artifact = result.artifact.to_dict() if result.artifact else None
                    if expected == "success":
                        assert len(store.list()) == 1
                        assert artifact["kind"] == "document_content" and artifact["revision"] == 1
                        assert artifact["provenance"]["execution_id"] == context["execution_id"]
                        assert artifact["provenance"]["owner_turn_id"] == context["turn_id"]
                        assert store.get(artifact["id"]).payload == result.result
                        content = result.result["content"]
                        expected_lines = text.splitlines()[:2] if name == "head_excerpt" else text.splitlines()
                        if name == "empty_file":
                            assert content == ""
                        elif name == "head_excerpt":
                            assert content.splitlines() == expected_lines
                        else:
                            assert content == text
                    else:
                        assert not store.list() and result.result is None
                        if name in ("outside_root", "symlink_escape"):
                            assert "Access denied" in result.error, result.error
                            assert "AUTHORED_OUTSIDE_CANARY" not in result.error
                        if name == "conflicting_excerpt":
                            assert "mcp_tool_error:" in result.error
                    assert file.read_text() == text and outside.read_text() == "AUTHORED_OUTSIDE_CANARY"
                    rows.append({"case": name, "passed": True, "status": result.status,
                                 "remote_calls": len(calls), "result": result.result,
                                 "error": result.error, "artifact": artifact, "wire": calls,
                                 "events": [event.to_dict() for event in dispatcher.state.events]})
            # Validate the SDK-managed stdio subprocess has actually been reaped.
            remaining = [process.pid for process in children if process.returncode is None]
            assert not remaining, remaining
    after = hashes()
    assert before == after, "source changed during probe"
    report = {"status": "mcp_reference_tool_probe_passed", "cases_passed": len(rows),
              "client": {"name": "mcp", "version": version("mcp")},
              "server": {"name": package["name"], "version": package["version"],
                         "entry_sha256": hashlib.sha256(entry.read_bytes()).hexdigest()},
              "transport": "actual stdio subprocess", "real_model_calls": 0,
              "fixture_files_only": True, "source_hashes_before": before, "source_hashes_after": after,
              "registered_operations": [OPERATION], "discovery": facts,
              "server_subprocess_reaped": True, "cases": rows}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "cases_passed": len(rows),
                      "sdk_version": version("mcp"), "server_version": package["version"],
                      "server_subprocess_reaped": True, "real_model_calls": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependency-target", required=True, type=Path)
    parser.add_argument("--node-prefix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT))
    sys.path.insert(0, str(args.dependency_target.resolve()))
    asyncio.run(run_probe(args))


if __name__ == "__main__":
    main()
