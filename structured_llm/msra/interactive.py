"""Interactive CLI & Step-by-Step Inspector for MSRA.

Allows researchers to interactively query the MSRA runtime, inspect the factored MDP
trajectory, observe subgoals, tool dispatch events, epistemic verifications,
and budget depletion in real time.

Usage:
    # Single question query:
    python -m structured_llm.msra.interactive --question "A store has 40 shirts. It sells 15 shirts on Monday and twice as many on Tuesday. How many are left?"

    # With trained LoRA adapter:
    python -m structured_llm.msra.interactive --adapter adapters/msra_coldstart_2000_s0

    # Interactive REPL mode:
    python -m structured_llm.msra.interactive
"""

import argparse
import sys
import time
from typing import Optional

from .router import CapabilityRouter
from .sandbox import SymPySandbox
from .stream_driver import MockGeneratorBackend, MSRAStepDriver
from .trace_parser import parse_trace
from .types import CapabilityTag


def create_default_driver(
    adapter_path: Optional[str] = None,
    model_path: str = "mlx-community/Qwen3-8B-4bit",
) -> MSRAStepDriver:
    """Build a fully registered MSRAStepDriver with SymPy Sandbox and CapabilityRouter."""
    router = CapabilityRouter()
    sandbox = SymPySandbox()

    # Register symbolic helper
    router.register_helper(
        CapabilityTag.SYMBOLIC_CALC,
        lambda q: sandbox.execute_algebraic_query(q)["result"],
        cost=0.10,
        source_id="h_sym",
    )

    if adapter_path:
        from .mlx_backend import MLXGeneratorBackend
        backend = MLXGeneratorBackend(model_path=model_path, adapter_path=adapter_path)
    else:
        # Fallback demonstrator backend for offline / dry-run testing
        backend = MockGeneratorBackend({
            "<step id=\"1\"": (
                "  <subgoal>Calculate shirts sold on Tuesday</subgoal>\n"
                "  <deps>None</deps>\n"
                "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
                "  <decision>SOLVE_LOCAL</decision>\n"
                "  <execution>15 * 2 = 30</execution>\n"
                "  <verification status=\"COMMIT\">Exact product verified</verification>\n"
                "  <output_var>v1 = 30</output_var>\n"
                "</step>"
            ),
            "<step id=\"2\"": (
                "  <subgoal>Calculate total shirts sold across Monday and Tuesday</subgoal>\n"
                "  <deps>v1 = 30</deps>\n"
                "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
                "  <decision>SOLVE_LOCAL</decision>\n"
                "  <execution>15 + 30 = 45</execution>\n"
                "  <verification status=\"COMMIT\">Exact sum</verification>\n"
                "  <output_var>v2 = 45</output_var>\n"
                "</step>"
            ),
            "<step id=\"3\"": (
                "  <subgoal>Calculate shirts remaining from stock</subgoal>\n"
                "  <deps>v2 = 45</deps>\n"
                "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
                "  <decision>SOLVE_LOCAL</decision>\n"
                "  <execution>50 - 45 = 5</execution>\n"
                "  <verification status=\"COMMIT\">Exact non-negative stock remainder</verification>\n"
                "  <output_var>v3 = 5</output_var>\n"
                "</step>"
            ),
            "<step id=\"4\"": "<final_answer>5</final_answer>",
            "<final_answer>": "5</final_answer>",
        })

    return MSRAStepDriver(backend=backend, router=router)


def display_msra_solution(solution: dict):
    """Pretty-print the MSRA reasoning trajectory to terminal."""
    trace_text = solution["trace"]
    parsed = parse_trace(trace_text)

    print("\n" + "=" * 65)
    print("🧠 MSRA FACTORED REASONING TRAJECTORY")
    print("=" * 65)

    for node in parsed.nodes:
        status_icon = "✅" if node.verification_status.value == "COMMIT" else "⚠️"
        decision_badge = (
            f"[\033[92m{node.decision.value}\033[0m]"
            if node.decision.value == "SOLVE_LOCAL"
            else f"[\033[94m{node.decision.value}\033[0m]"
        )

        print(f"\n🔹 Step {node.step_id}: {node.subgoal}")
        print(f"   ├─ Dependencies:  {node.deps if node.deps else 'None'}")
        print(f"   ├─ Capability:    {node.capability_tag.value}")
        print(f"   ├─ Decision:      {decision_badge}")
        if node.query_payload:
            print(f"   ├─ Query Payload: {node.query_payload}")
        print(f"   ├─ Execution:     {node.execution_result}")
        print(f"   ├─ Verification:  {status_icon} [{node.verification_status.value}] {node.critique}")
        print(f"   └─ Output Var:    {node.output_var if node.output_var else 'None'}")

    print("\n" + "-" * 65)
    final_ans = solution.get("final_answer", "N/A")
    cost = solution.get("total_cost", 0.0)
    steps = solution.get("steps_taken", len(parsed.nodes))

    print(f"🎯 Final Answer:       \033[1;32m{final_ans}\033[0m")
    print(f"📊 Total Steps Taken:  {steps}")
    print(f"💰 Routing Cost:       ${cost:.3f}")
    print(f"🛡️  DAG Format Valid:   {parsed.is_valid}")
    if parsed.errors:
        print(f"❌ Structural Errors:  {parsed.errors}")
    print("=" * 65 + "\n")


def run_interactive_repl(driver: MSRAStepDriver):
    """Start an interactive command-line loop."""
    print("=" * 65)
    print("🤖 MSRA Interactive Shell (Type 'exit' or 'quit' to stop)")
    print("=" * 65)

    while True:
        try:
            query = input("\n📝 Enter problem prompt > ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("Exiting MSRA interactive session. Goodbye!")
                break

            t0 = time.perf_counter()
            solution = driver.solve(query)
            dur = time.perf_counter() - t0

            display_msra_solution(solution)
            print(f"⏱️  Inference & verification took {dur:.2f}s")

        except (KeyboardInterrupt, EOFError):
            print("\nSession interrupted. Exiting.")
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", "-q", default=None, help="Single math/reasoning question")
    parser.add_argument("--adapter", "-a", default=None, help="Path to LoRA adapter weights")
    parser.add_argument("--model", "-m", default="mlx-community/Qwen3-8B-4bit", help="Base model identifier")
    args = parser.parse_args()

    driver = create_default_driver(adapter_path=args.adapter, model_path=args.model)

    if args.question:
        solution = driver.solve(args.question)
        display_msra_solution(solution)
    else:
        run_interactive_repl(driver)


if __name__ == "__main__":
    main()
