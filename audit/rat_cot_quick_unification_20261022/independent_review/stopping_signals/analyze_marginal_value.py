"""Exact descriptive cost accounting on a pinned, exposed development pilot.

No model, new policy selection, fitting, statistical testing or held-out input.
The symbolic utility expressions are identities, not a new choice of lambda.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PACKET = Path(__file__).resolve().parent
RUN = ROOT / "audit/gsm8k-fixed-baseline-measured-20261004"
PINNED_RECORDS = "858af874dc7ba0393e0aef6a4d7ba39fc3fa2a6e67347b1bc09708ed38ddee54"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value):
    return {"fraction": str(value), "decimal": float(value)}


def main(output):
    names = ["marginal_value.json", "marginal_value.png", "marginal_value.svg"]
    require(not any((output / name).exists() for name in names), "Preserve earlier outputs; choose a new directory")
    manifest = read(RUN / "manifest.json")
    expected = manifest["artifact_sha256"]
    require(expected["records.json"] == PINNED_RECORDS, "Unexpected historical pilot")
    before = {name: digest(RUN / name) for name in expected}
    require(before == expected, "Historical artifacts differ from pinned manifest")
    require(manifest["evidence"] == "measured_development_pilot" and manifest["seed"] == 42, "Unexpected evidence/seed")
    require(manifest["prompt_profile"] == "english-math-v1", "Unexpected prompt profile")
    item_digest = digest(PACKET / "items.json")
    items = read(PACKET / "items.json")
    records = read(RUN / "records.json")
    by_id = {}
    for row in records:
        require(row["split"] in {"train", "calibration"}, "Only exposed development supported")
        require(row["token_budget"] == 1024, "Unexpected per-call cap")
        require(type(row["correct"]) is bool and type(row["tokens"]) is int and row["tokens"] > 0, "Invalid labels/costs")
        arms = by_id.setdefault(row["id"], {})
        require(row["strategy"] not in arms, "Duplicate recipe")
        arms[row["strategy"]] = row
    require(len(records) == 69 and len(by_id) == len(items) == 23, "Unexpected row/group coverage")
    require(len({row["id"] for row in items}) == len({row["group_id"] for row in items}) == 23, "Duplicate derived ID/group")
    require(set(by_id) == {row["id"] for row in items}, "Derived/raw ID mismatch")
    require(all(set(arms) == {"DIRECT", "COT", "PAL"} for arms in by_id.values()), "Missing recipes")
    for row in items:
        arms = by_id[row["id"]]
        for strategy, prefix in (("COT", "cot"), ("PAL", "pal")):
            source = arms[strategy]
            require(source["correct"] == row[prefix + "_correct"] and source["tokens"] == row[prefix + "_tokens"], "Derived/raw labels or costs differ")
            require(source["group_id"] == row["group_id"], "Derived/raw group mismatch")
            require(len(source["trace"]["generations"]) == 1, "One call per recipe expected here")
            require(sum(g["tokens"] for g in source["trace"]["generations"]) == source["tokens"], "Generation/recipe cost mismatch")
        transition = ("both_correct" if row["cot_correct"] and row["pal_correct"] else
                      "rescue" if row["pal_correct"] else "harm" if row["cot_correct"] else "both_wrong")
        require(row["transition"] == transition, "Derived transition differs")
        trace = arms["COT"]["trace"]
        marker = (trace["parse_status"] == "fail" or any(g["finish_reason"] == "length" for g in trace["generations"])
                  or any(tool.get("ok") is False for tool in trace["tools"]))
        require(marker == row["cot_failure_marker"], "Derived/raw marker differs")
    n = len(items)
    strata = {}
    for transition in ("rescue", "harm", "both_correct", "both_wrong"):
        rows = [row for row in items if row["transition"] == transition]
        strata[transition] = {"groups": len(rows), "cot_generated_tokens": sum(row["cot_tokens"] for row in rows),
                              "pal_generated_tokens": sum(row["pal_tokens"] for row in rows)}
    cot_correct = sum(row["cot_correct"] for row in items)
    pal_correct = sum(row["pal_correct"] for row in items)
    cot_tokens = sum(row["cot_tokens"] for row in items)
    pal_tokens = sum(row["pal_tokens"] for row in items)
    methods = {
        "fixed_cot": {"correct": cot_correct, "generated_tokens": cot_tokens, "calls": n},
        "fixed_pal": {"correct": pal_correct, "generated_tokens": pal_tokens, "calls": n},
        "cot_then_pal_always_saved_output_replay": {"correct": pal_correct, "generated_tokens": cot_tokens + pal_tokens, "calls": 2 * n},
    }
    for row in methods.values():
        row["groups"] = n
        row["accuracy"] = exact(Fraction(row["correct"], n))
        row["mean_generated_tokens"] = exact(Fraction(row["generated_tokens"], n))
    # Two independent accounting identities, without choosing an escalation set.
    require(sum(row["groups"] for row in strata.values()) == n, "Stratum count mismatch")
    require(strata["rescue"]["groups"] - strata["harm"]["groups"] == pal_correct - cot_correct, "Paired gain identity failed")
    require(sum(row["pal_generated_tokens"] for row in strata.values()) == pal_tokens, "Stratum cost mismatch")
    utility_difference = {
        "pal_minus_cot": {"accuracy_term": exact(Fraction(pal_correct - cot_correct, n)),
                          "lambda_coefficient": exact(Fraction(cot_tokens - pal_tokens, 1000 * n))},
        "always_cascade_minus_pal": {"accuracy_term": exact(Fraction(0)),
                                     "lambda_coefficient": exact(-Fraction(cot_tokens, 1000 * n))},
    }
    require(cot_correct == 19 and pal_correct == 21 and cot_tokens == 2227 and pal_tokens == 2002, "Historical report totals differ")
    require(all(not row["cot_failure_marker"] for row in items), "Unexpected marker trigger")
    require(before == {name: digest(RUN / name) for name in expected}, "Historical inputs changed")
    require(item_digest == digest(PACKET / "items.json"), "Derived inputs changed")
    output.mkdir(parents=True, exist_ok=True)
    figure = draw_figure(methods, output)
    result = {
        "kind": "retrospective_exposed_development_marginal_cost_accounting", "groups": n, "observed_seeds": [42],
        "new_model_calls": 0, "new_scoring": False, "policy_fitted": False, "lambda_selected": False,
        "held_out_read": False, "human_review_status": "pending", "publication_ready": False,
        "cost_scope": "saved generated tokens only; excludes prompt, embeddings, tools, router and loading",
        "timing_claim": "none; conditional replay is not online latency",
        "fallback_context": "PAL receives original query; no CoT-answer feedback or targeted repair",
        "methods": methods, "transitions": strata, "utility_differences": utility_difference,
        "always_cascade_extra_tokens_over_pal": cot_tokens,
        "always_cascade_token_ratio_to_pal": exact(Fraction(cot_tokens + pal_tokens, pal_tokens)),
        "arbitrary_gate_identity": {
            "accuracy_change_vs_cot": "(selected_rescues - selected_harms) / n",
            "extra_generated_tokens": "sum(PAL generated tokens for selected escalation groups)",
            "utility_change_vs_cot": "(selected_rescues - selected_harms) / n - lambda * selected_PAL_tokens / (1000*n)",
            "warning": "post-hoc accounting identity only; rescue/harm labels are unavailable at inference; no subset or threshold fitted",
        },
        "interpretation": [
            "Fixed PAL has higher observed correctness and fewer generated tokens than fixed CoT on these 23 exposed groups; no universal or full-cost dominance claim.",
            "Always CoT then independent PAL has identical final answers to fixed PAL and adds every CoT token; equal utility at lambda=0 and lower at any lambda>0 under this cost definition.",
            "A signal that merely detects an initially wrong answer does not establish that the next recipe will rescue it; neutral escalations still cost compute.",
            "Do not infer a fitted checker benefit, held-out effect or isolated tool effect from this descriptive pilot.",
        ],
        "provenance": {"historical_manifest_sha256": digest(RUN / "manifest.json"), "historical_artifact_sha256": before,
                       "derived_items_sha256": item_digest, "analysis_source_sha256": digest(Path(__file__)),
                       "historical_inputs_unchanged": True, "figure_sha256": figure},
    }
    (output / "marginal_value.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"methods": methods, "transitions": strata, "utility_differences": utility_difference}, indent=2))


def draw_figure(methods, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(9, 5.2), layout="constrained")
    names = ["fixed_pal", "fixed_cot", "cot_then_pal_always_saved_output_replay"]
    titles = ["Fixed PAL", "Fixed CoT", "Always CoT then PAL"]
    positions = [(15, 98), (50, 65), (151, 66)]
    colors = ["#147d64", "#52668a", "#b36535"]
    for name, title, pos, color in zip(names, titles, positions, colors):
        row = methods[name]
        x, y = row["mean_generated_tokens"]["decimal"], row["accuracy"]["decimal"]
        label = f"{title}\n{row['correct']}/{row['groups']}; {x:.1f} tokens"
        ax.scatter(x, y, color=color, s=90, zorder=3)
        ax.annotate(label, xy=(x, y), xytext=(pos[0], pos[1]/100), color=color,
                    arrowprops={"arrowstyle": "-", "color": color}, fontsize=10)
    ax.set(xlim=(0, 230), ylim=(0, 1.08), xlabel="Mean generated tokens per question (lower is cheaper)", ylabel="Observed answer accuracy")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.grid(alpha=.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(f"{methods['fixed_cot']['groups']} exposed GSM8K development groups · one observed seed", loc="left", pad=15, weight="bold")
    fig.text(.12, -.035, "Saved independent outputs; always-cascade is conditional replay. Generated tokens exclude input/tool/router costs.\nHuman/publication review pending; no held-out or measured online-controller result.", fontsize=9, color="#555555")
    result = {}
    for extension in ("png", "svg"):
        path = output / ("marginal_value." + extension)
        fig.savefig(path, dpi=180, bbox_inches="tight", metadata={"Creator": "offline exposed-development analysis"})
        result[path.name] = digest(path)
    plt.close(fig)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PACKET, help="Destination; refuses to replace existing analysis outputs")
    main(parser.parse_args().output.resolve())
