"""Static planning arithmetic; reads source/metadata only, never a dataset or model."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main(output):
    require(not output.exists(), "Preserve prior planning artifact; choose a new output")
    backend_path = ROOT / "qwen_mlx_backend.py"
    harness_path = ROOT / "experiments/research_study.py"
    env_path = ROOT / "reasoning/reasoning_env.py"
    report_path = ROOT / "data/procedural_research_v1/report.md"
    protocol_path = ROOT / "docs/research_protocol.md"
    inputs = [backend_path, harness_path, env_path, report_path, protocol_path]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    backend = ast.parse(backend_path.read_text())
    cls = next(node for node in backend.body if isinstance(node, ast.ClassDef) and node.name == "QwenMLXBackend")
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    positional = dict(zip([a.arg for a in init.args.args][-len(init.args.defaults):], init.args.defaults))
    defaults = {**positional, **dict(zip([a.arg for a in init.args.kwonlyargs], init.args.kw_defaults))}
    values = {name: ast.literal_eval(defaults[name]) for name in ("max_tokens", "sc_samples", "tot_branches", "react_max_turns")}
    require(all(type(v) is int and v > 0 for v in values.values()), "Review non-integer or nonpositive defaults")
    react = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_react")
    require(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "min"
                and any(isinstance(a, ast.Constant) and a.value == 200 for a in node.args) for node in ast.walk(react)), "Review ReAct per-turn cap")
    harness = ast.parse(harness_path.read_text())
    collector = next(node for node in harness.body if isinstance(node, ast.FunctionDef) and node.name == "collect_records")
    run_calls = [node for node in ast.walk(collector) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "backend" and node.func.attr == "run"]
    require(len(run_calls) == 1 and not run_calls[0].keywords, "Review collector request-budget semantics")
    constructors = [node for node in ast.walk(harness) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "QwenMLXBackend"]
    require(len(constructors) == 1 and not constructors[0].args and {k.arg for k in constructors[0].keywords} == {"repo"}, "Review main backend overrides")
    env = ast.parse(env_path.read_text())
    strategies = next(node.value for node in env.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "STRATEGIES" for t in node.targets))
    require([node.attr for node in strategies.elts] == ["COT", "SELF_CONSISTENCY", "TOT", "REACT", "PAL"], "Review recipe set")
    match = re.search(r"^\| main \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|", report_path.read_text(), re.M)
    require(match is not None, "Missing candidate count metadata")
    items, groups, train, calibration, test = map(int, match.groups())
    require(train + calibration + test == items, "Metadata counts disagree")
    test_match = re.search(r"test (\d+)/(\d+)\.", protocol_path.read_text())
    require(test_match is not None and int(test_match[1]) == test, "Review test group metadata")
    pairs = items * 3
    call_counts = {"COT": 1, "SELF_CONSISTENCY": values["sc_samples"], "TOT": values["tot_branches"] + 1,
                   "REACT": values["react_max_turns"], "PAL": 1}
    scenarios = []
    for cap, status in ((values["max_tokens"], "current backend default; not an execution freeze"),
                        (1024, "what-if only; main CLI does not expose pilot token-budget override")):
        tokens = {strategy: calls * (min(cap, 200) if strategy == "REACT" else cap) for strategy, calls in call_counts.items()}
        scenarios.append({"cap": cap, "status": status, "calls_per_item_seed_upper": sum(call_counts.values()),
                          "generated_tokens_per_item_seed_upper": sum(tokens.values()), "recipe_call_upper": call_counts,
                          "recipe_generated_token_upper": tokens, "total_generation_calls_upper": pairs * sum(call_counts.values()),
                          "total_generated_tokens_upper": pairs * sum(tokens.values())})
    result = {
        "kind": "static_proposed_collection_envelope_not_authorization", "new_model_calls": 0,
        "held_out_content_read": False, "inference_budget_allocated": 0, "seed_count_assumption": 3,
        "seed_list_frozen": False, "candidate": {"items": items, "groups": groups, "train_items": train,
            "calibration_items": calibration, "test_items": test, "test_groups": int(test_match[2]), "review_status": "pending"},
        "item_seed_pairs": pairs, "embedding_calls_in_current_collector": pairs,
        "method_count_per_test_item": 9, "replayed_test_rows_at_three_seeds": test * 3 * 9,
        "scenarios": scenarios,
        "assumptions": ["All declared items/recipes complete; no retries or extra strategies; early termination may lower counts.",
                        "Collector backend.run is called without an explicit aggregate max_tokens override.",
                        "ReAct has at most four turns at min(200, backend cap) per turn under current defaults.",
                        "Ceilings are completion-token bounds, not expected usage, full inference cost or latency.",
                        "Embeddings, prompt tokens, tool CPU, model loading and fitting compute are excluded from completion-token counts.",
                        "Nine policies replay a five-recipe bank; replay rows are not new model calls or independent problems.",
                        "Three seeds do not turn 70 original test groups into 210 independent groups.",
                        "The unapproved candidate and default backend/profile are not a reviewed real-run configuration."],
        "source_metadata_sha256": hashes, "analysis_source_sha256": digest(Path(__file__)),
    }
    require(hashes == {str(p.relative_to(ROOT)): digest(p) for p in inputs}, "Source changed during estimation")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"generation_calls_upper": scenarios[0]["total_generation_calls_upper"],
                      "embeddings": pairs, "scenarios": scenarios}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("collection_envelope.json"))
    main(parser.parse_args().output.resolve())
