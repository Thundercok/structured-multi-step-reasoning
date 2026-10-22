"""Development-only PydanticAI bridge probe: real SDK, scripted model, fixture app.

No runtime imports this module. Dependencies live in a separately supplied target.
The OS launcher and network connections are blocked during the probe. This is
software integration evidence, not agent/model-quality or cost evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import plistlib
import sys
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[2]


def packet(result):
    return {
        "status": result.status,
        "result": copy.deepcopy(result.result),
        "error": result.error,
        "artifact": result.artifact.to_dict() if result.artifact else None,
        "input_request": result.input_request.to_dict() if result.input_request else None,
    }


def make_sdk_tool(dispatcher, context):
    """Export the existing schema; keep execution/validation/store owned by RAT."""
    from pydantic_ai.tools import Tool

    spec = dispatcher.registry.get_operation("open_application").to_tool_definition()

    def invoke(**arguments):
        return packet(dispatcher.execute_operation(spec.name, arguments, context=context))

    return Tool.from_schema(
        function=invoke, name=spec.name, description=spec.description,
        json_schema=copy.deepcopy(spec.parameters), sequential=True,
    )


def comparable(value):
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items() if k != "created_at"}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    if isinstance(value, str) and value.startswith(("art-", "input-")):
        return "<generated-id>"
    return value


def make_bundle(root, folder):
    from rat.engine.app_resolver import revalidate_application_bundle

    path = root / folder / "SDK Probe.app"
    executable = path / "Contents/MacOS/Probe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"Authored fixture; never execute.\n")
    (path / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "org.rat.sdk-probe." + folder,
        "CFBundleExecutable": "Probe", "CFBundleDisplayName": "SDK Probe",
    }))
    return revalidate_application_bundle(path)


def make_dispatcher(apps, scenario, context):
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.kernel.contracts import ArtifactStore
    from rat.kernel.dispatcher import ActionDispatcher
    from rat.kernel.registry import CapabilityRegistry
    from rat.kernel.capabilities.applications import create_applications_capability

    calls = []
    store, registry = ArtifactStore(), CapabilityRegistry()
    dispatcher = ActionDispatcher(registry, store)

    def fixture_launcher(app):
        calls.append(app.resource_id)
        if scenario == "launcher_error":
            return False
        if scenario == "cancel_during":
            dispatcher.cancel_execution(context["execution_id"])
        if scenario == "conversation_reset":
            store.clear()
        return True

    catalog = ApplicationCatalog(tuple(apps if scenario == "needs_input" else apps[:1]))
    registry.register_capability(create_applications_capability(catalog, fixture_launcher))
    if scenario == "cancel_before":
        dispatcher.cancel_execution(context["execution_id"])
    return dispatcher, calls


def assert_contract(dispatcher, result, calls, context, expected_status, expected_calls):
    assert result["status"] == expected_status, result
    assert len(calls) == expected_calls, calls
    stored = dispatcher.store.list()
    if expected_status in ("success", "needs_input"):
        assert len(stored) == 1
        artifact = result["artifact"]
        assert stored[0].id == artifact["id"]
        assert artifact["provenance"]["execution_id"] == context["execution_id"]
        assert artifact["provenance"]["owner_turn_id"] == context["turn_id"]
        if expected_status == "success":
            assert artifact["kind"] == "application_launch"
            assert artifact["revision"] == 1
            assert artifact["payload"] == result["result"]
        else:
            assert artifact["id"] == result["input_request"]["id"]
            assert len(result["input_request"]["candidate_choices"]) == 2
    else:
        assert stored == [], stored


async def run_probe(output):
    from importlib.metadata import version
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models import override_allow_model_requests
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.usage import UsageLimits
    from pydantic_ai.exceptions import UsageLimitExceeded

    tracked = [
        "rat/kernel/registry.py", "rat/kernel/contracts.py", "rat/kernel/dispatcher.py",
        "rat/kernel/capabilities/applications.py", "rat/engine/app_resolver.py",
        "rat/engine/task_state.py", "requirements.txt", "requirements-research.txt",
    ]
    hashes = lambda: {p: hashlib.sha256((PROJECT / p).read_bytes()).hexdigest() for p in tracked}
    before = hashes()
    rows = []
    # Third-party model-provider requests are disabled by the SDK's test guard.
    # Socket/OS patches additionally prohibit real network/launch side effects.
    with tempfile.TemporaryDirectory(prefix="rat-sdk-fixtures-") as temporary, \
            override_allow_model_requests(False), \
            patch("socket.socket.connect", side_effect=AssertionError("network_forbidden")), \
            patch("socket.socket.connect_ex", side_effect=AssertionError("network_forbidden")), \
            patch("rat.kernel.capabilities.applications.subprocess.run", side_effect=AssertionError("os_launch_forbidden")):
        apps = [make_bundle(Path(temporary), folder) for folder in ("one", "two")]
        scenarios = [
            ("success", {"query": "SDK Probe"}, "success", 1),
            ("needs_input", {"query": "SDK Probe"}, "needs_input", 0),
            ("invalid_type", {"query": 17}, "error", 0),
            ("unknown_argument", {"query": "SDK Probe", "extra": True}, "error", 0),
            ("launcher_error", {"query": "SDK Probe"}, "error", 1),
            ("cancel_before", {"query": "SDK Probe"}, "cancelled", 0),
            ("cancel_during", {"query": "SDK Probe"}, "cancelled", 1),
            ("conversation_reset", {"query": "SDK Probe"}, "cancelled", 1),
        ]
        for name, arguments, status, call_count in scenarios:
            context = {"turn_id": "turn-probe-" + name, "execution_id": "exec-probe-" + name,
                       "platform": "darwin"}
            direct, direct_calls = make_dispatcher(apps, name, context)
            expected = packet(direct.execute_operation("open_application", arguments, context=context))
            assert_contract(direct, expected, direct_calls, context, status, call_count)
            bridged, bridge_calls = make_dispatcher(apps, name, context)
            tool = make_sdk_tool(bridged, context)
            mock_calls = []

            async def scripted_model(messages, info):
                mock_calls.append(len(messages))
                returned = [part for message in messages for part in message.parts
                            if isinstance(part, ToolReturnPart)]
                if returned:
                    return ModelResponse(parts=[TextPart(json.dumps(returned[-1].content))])
                spec = bridged.registry.get_operation("open_application").to_tool_definition()
                assert info.function_tools[0].parameters_json_schema == spec.parameters
                return ModelResponse(parts=[ToolCallPart("open_application", arguments)])

            agent = Agent(FunctionModel(scripted_model), tools=[tool], retries=0)
            run = await agent.run("Scripted integration fixture only.",
                                  usage_limits=UsageLimits(request_limit=2, tool_calls_limit=1))
            actual = json.loads(run.output)
            assert_contract(bridged, actual, bridge_calls, context, status, call_count)
            assert comparable(actual) == comparable(expected), (name, expected, actual)
            assert len(mock_calls) == 2
            rows.append({
                "case": name, "passed": True, "direct": expected, "sdk": actual,
                "fixture_launcher_calls": len(bridge_calls), "scripted_model_requests": len(mock_calls),
                "events": [event.to_dict() for event in bridged.state.events],
                "sdk_messages": json.loads(run.all_messages_json()),
            })

        dispatcher, calls = make_dispatcher(apps, "zero_request_budget", context)
        async def forbidden_model(messages, info):
            raise AssertionError("zero_request_budget_dispatched")
        agent = Agent(FunctionModel(forbidden_model), tools=[make_sdk_tool(dispatcher, context)], retries=0)
        try:
            await agent.run("No request allowed.", usage_limits=UsageLimits(request_limit=0))
        except UsageLimitExceeded:
            assert not calls and not dispatcher.store.list()
            rows.append({"case": "zero_request_budget", "passed": True,
                         "scripted_model_requests": 0, "fixture_launcher_calls": 0})
        else:
            raise AssertionError("zero request cap was not enforced")

    after = hashes()
    assert before == after, "source changed during probe"
    report = {
        "status": "offline_bridge_probe_passed", "sdk": "pydantic-ai-slim",
        "sdk_version": version("pydantic-ai-slim"), "cases_passed": len(rows),
        "real_model_calls": 0, "real_generated_tokens": 0, "real_os_launches": 0,
        "fixture_applications_only": True, "qt_used": False,
        "sdk_token_estimates": "synthetic FunctionModel estimates; not reported as inference cost",
        "scope": "one existing operation; no replacement of RAT runtime or research policy",
        "source_hashes_before": before, "source_hashes_after": after, "cases": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                 default=lambda value: value.to_dict()) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "sdk_version", "cases_passed",
                    "real_model_calls", "real_os_launches")}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependency-target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT))
    sys.path.insert(0, str(args.dependency_target.resolve()))
    asyncio.run(run_probe(args.output))


if __name__ == "__main__":
    main()
