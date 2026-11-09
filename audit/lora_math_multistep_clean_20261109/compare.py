"""Apply the reading rule in docs/ablation_math_multistep_spec.md section 5.

Usage: compare.py [treatment-tuned.jsonl control-tuned.jsonl]
"""
import json
import math
from pathlib import Path
import sys

RUN = Path(__file__).parent
sys.path.insert(0, str(RUN.parents[1] / "scripts"))
from run_math_multistep_ablation import analyze_records  # noqa: E402


def read(path):
    return {r["id"]: r for r in map(json.loads, Path(path).read_text().splitlines())}


def mcnemar(a, b):
    n = a + b
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2**n) if n else 1.0


def paired(treatment, control, value):
    only_treatment = sum(value(treatment[i]) and not value(control[i]) for i in treatment)
    only_control = sum(value(control[i]) and not value(treatment[i]) for i in treatment)
    return only_treatment, only_control, mcnemar(only_treatment, only_control)


def main():
    args = sys.argv[1:] or [RUN / "eval_treatment/tuned.jsonl", RUN / "eval_control/tuned.jsonl"]
    treatment, control = read(args[0]), read(args[1])
    if set(treatment) != set(control) or len(treatment) != 100:
        raise SystemExit(f"need the same 100 questions, got {len(treatment)} and {len(control)}")

    a, b, p = paired(treatment, control, lambda r: bool(r.get("truncated")))
    verdict = "supports" if a < b and p < 0.05 else "does not support"
    result = {
        "treatment": analyze_records(list(treatment.values())),
        "control": analyze_records(list(control.values())),
        "truncated_only_treatment": a,
        "truncated_only_control": b,
        "truncated_p": p,
        "verdict": verdict,
    }
    for name, value in (("correct", lambda r: bool(r["check"]["correct"])),
                        ("format_valid", lambda r: bool(r["check"]["format_valid"]))):
        result[name] = dict(zip(("only_treatment", "only_control", "p"), paired(treatment, control, value)))
    text = json.dumps(result, indent=2)
    print(text)
    if not sys.argv[1:]:
        (RUN / "comparison.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
