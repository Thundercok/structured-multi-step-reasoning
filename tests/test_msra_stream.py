"""Unit tests for MSRAStepDriver streaming runtime."""

import pytest
from structured_llm.msra.router import CapabilityRouter
from structured_llm.msra.sandbox import SymPySandbox
from structured_llm.msra.stream_driver import MockGeneratorBackend, MSRAStepDriver
from structured_llm.msra.types import CapabilityTag, Decision, VerificationStatus


def test_msra_step_driver_e2e_with_symbolic_helper():
    router = CapabilityRouter()
    sandbox = SymPySandbox()
    router.register_helper(
        CapabilityTag.SYMBOLIC_CALC,
        lambda q: sandbox.execute_algebraic_query(q)["result"],
        cost=0.1,
    )

    # Scripted sequence of LLM responses across decision points:
    # Step 1: solve locally
    # Step 2: ask help from SymPy
    script = {
        '<step id="1"': (
            '  <subgoal>Establish known prices</subgoal>\n'
            '  <deps>None</deps>\n'
            '  <capability>CAP:DECOMPOSE</capability>\n'
            '  <decision>SOLVE_LOCAL</decision>\n'
            '  <execution>Base price is 50</execution>\n'
            '  <verification status="COMMIT">Given in problem</verification>\n'
            '  <output_var>p = 50</output_var>\n'
            '</step>'
        ),
        '<step id="2"': (
            '  <subgoal>Solve for final quantity</subgoal>\n'
            '  <deps>p = 50</deps>\n'
            '  <capability>CAP:SYMBOLIC_CALC</capability>\n'
            '  <decision>ASK_HELP</decision>\n'
            '  <query_payload>Solve 2*x + 50 = 90</query_payload>\n'
        ),
        'helper_response': (
            '  <verification status="COMMIT">Helper output verified</verification>\n'
            '  <output_var>x = 20</output_var>\n'
            '</step>'
        ),
        '<step id="3"': "<final_answer>20</final_answer>",
        '<final_answer>': "20</final_answer>",
    }

    backend = MockGeneratorBackend(script)
    driver = MSRAStepDriver(backend=backend, router=router)

    result = driver.solve("A store sells items...", initial_budget=2.0)

    assert result["final_answer"] == "20"
    assert len(result["nodes"]) == 2
    assert result["total_cost"] == 0.1
    assert result["budget_remaining"] == 1.9
    assert result["committed_vars"]["x"] == "20"
    assert result["nodes"][0].decision == Decision.SOLVE_LOCAL
    assert result["nodes"][1].decision == Decision.ASK_HELP
    assert "20" in result["trace"]
