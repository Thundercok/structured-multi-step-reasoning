"""CPU-only rescue/harm diagnostics for audited development replay outputs."""

from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

from experiments.cot_restart_pilot import FINAL_MARKER, file_sha256
from scripts.analyze_cot_restart_matched import load_cpu_tokenizer


def clopper_pearson(x: int, n: int, alpha: float = .05) -> list[float]:
    """Two-sided CP interval under a binomial model; no normal approximation."""
    if not 0 <= x <= n or n < 1 or not 0 < alpha < 1:
        raise ValueError("invalid binomial counts or alpha")
    def cdf(k, p):
        return sum(comb(n, j) * p**j * (1-p)**(n-j) for j in range(k+1))
    def root(k, target):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if cdf(k, mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    return [0.0 if x == 0 else root(x-1, 1-alpha/2),
            1.0 if x == n else root(x, alpha/2)]


def diagnose(analysis: Path, run: Path, plan_dir: Path, output: Path) -> dict:
    analysis, run, plan_dir, output = (Path(p).resolve() for p in (analysis, run, plan_dir, output))
    if output.exists() or any(output.is_relative_to(p) for p in (analysis, run, plan_dir)):
        raise ValueError("use a new isolated diagnostics directory")
    audit = json.loads((analysis / "audit.json").read_text())
    for name, digest in audit["outputs_sha256"].items():
        if file_sha256(analysis / name) != digest:
            raise ValueError(f"analysis artifact hash mismatch: {name}")
    for name, digest in audit["run_artifact_hashes"].items():
        if file_sha256(run / name) != digest:
            raise ValueError(f"run artifact hash mismatch: {name}")
    plan = json.loads((plan_dir / "plan.json").read_text())
    if plan["plan_sha256"] != audit["plan_sha256"]:
        raise ValueError("diagnostic plan/analysis mismatch")
    summary = json.loads((analysis / "summary.json").read_text())
    if any(r["historical_correct"] != r["retrospective_correct"] for r in summary["base_rescoring"]):
        raise ValueError("base rescoring differs; review the diagnostic denominator first")
    base_correct = {r["question_id"]: r["retrospective_correct"] for r in summary["base_rescoring"]}
    replays = json.loads((analysis / "replays.json").read_text())
    counts = []
    for point in ("M", "D_w0", "D_w1"):
        for arm in ("A", "F", "CONT"):
            rows = [r for r in replays if r["point"] == point and r["arm"] == arm]
            rescued = [r["question_id"] for r in rows if not base_correct[r["question_id"]] and r["correct"]]
            harmed = [r["question_id"] for r in rows if base_correct[r["question_id"]] and not r["correct"]]
            wrong, right = sum(not v for v in base_correct.values()), sum(base_correct.values())
            counts.append({"point": point, "arm": arm, "rescued": len(rescued), "rescue_n": wrong,
                           "rescue_cp95": clopper_pearson(len(rescued), wrong) if wrong else None,
                           "harmed": len(harmed), "harm_n": right,
                           "harm_cp95": clopper_pearson(len(harmed), right) if right else None,
                           "rescued_ids": rescued, "harmed_ids": harmed})
    bases = json.loads((Path(plan["historical_dir"]) / "base_traces.json").read_text())
    raw = {(r["question_id"], r["arm"]): r for r in json.loads((run / "records.json").read_text())}
    cont_rescues = []
    tokenizer = None
    for result in replays:
        qid = result["question_id"]
        if result["point"] != "M" or result["arm"] != "CONT" or base_correct[qid] or not result["correct"]:
            continue
        record, base = raw[(qid, "CONT")], bases[qid]
        if tokenizer is None:
            tokenizer, _ = load_cpu_tokenizer(record)
        match = FINAL_MARKER.search(result["raw_output"])
        before = None
        if match:
            decoder = tokenizer.detokenizer
            before = 0
            ids = record["completion_token_ids"][:result["replay_cap"]]
            for index, token in enumerate(ids):
                if token in record["eos_token_ids"]:
                    break
                decoder.add_token(token)
                if len(decoder.text) <= match.start():
                    before = index + 1
                else:
                    break
        comparable = base["finish_reason"] == "stop" and base.get("parsed_answer") is not None
        cont_rescues.append({
            "question_id": qid, "base_finish_reason": base["finish_reason"],
            "base_parse_status": base["parse_status"], "base_parsed_answer": base.get("parsed_answer"),
            "new_parsed_answer": result["parsed_answer"], "new_tokens_before_answer_marker": before,
            "parsed_answer_text_change_comparable": comparable,
            "parsed_answer_text_changed": (str(base["parsed_answer"]).strip().casefold()
                                             != str(result["parsed_answer"]).strip().casefold()) if comparable else None,
        })
    result = {"evidence": "exposed_development_subset_diagnostics", "model_calls": 0,
              "interval_scope": "unadjusted CP under a binomial model; diagnostic, selected by base outcome",
              "counts": counts, "M_CONT_rescue_observables": cont_rescues}
    output.mkdir(parents=True, exist_ok=False)
    (output / "diagnostics.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# Rescue/harm development diagnostics", "",
             "All 12 base correctness labels agree with retrospective typed rescoring. Denominators: 5 wrong, 7 correct.",
             "CP intervals are unadjusted, under a binomial model; subsets were selected by the base outcome.",
             "These are not population treatment effects. Primary evidence remains all-question A/F/CONT paired contrasts.", "",
             "| Point | Arm | Rescue | CP 95% | Harm | CP 95% |",
             "| --- | --- | ---: | --- | ---: | --- |"]
    for row in counts:
        rci, hci = row["rescue_cp95"], row["harm_cp95"]
        lines.append(f"| {row['point']} | {row['arm']} | {row['rescued']}/{row['rescue_n']} | "
                     f"[{rci[0]:.3f}, {rci[1]:.3f}] | {row['harmed']}/{row['harm_n']} | [{hci[0]:.3f}, {hci[1]:.3f}] |")
    lines.extend(["", "CONT rescue observables at M are recorded in diagnostics.json.",
                  "Tokens before the marker count complete tokens whose emitted text ends before the first explicit marker.",
                  "Answer changes are compared only for stop-finished bases with parsed answers; text changes are not mechanistic classifications.",
                  "Neither rescue, short visible reasoning nor a parse failure establishes a formatting-only or tail-repair cause."])
    (output / "report.md").write_text("\n".join(lines) + "\n")
    (output / "audit.json").write_text(json.dumps({
        "plan_sha256": audit["plan_sha256"], "primary_analysis_audit_sha256": file_sha256(analysis / "audit.json"),
        "source_sha256": file_sha256(Path(__file__)),
        "outputs_sha256": {p.name: file_sha256(p) for p in output.iterdir()},
    }, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("analysis", "run", "plan", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.analysis, args.run, args.plan, args.output)
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
