"""Independent arithmetic oracle on authored fixtures; no candidate/model access."""
import hashlib
import json
from pathlib import Path
import random
import runpy
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments import gsm8k_routing_baseline as implementation


def main():
    helpers = runpy.run_path(str(ROOT / "tests/test_gsm8k_routing_baseline.py"))
    rng = random.Random(20261024)
    actions = ("DIRECT", "COT", "PAL")
    menu = [(f"constant_{a}", a, a, None) for a in actions]
    menu += [(f"words_le_{c:03d}_{a}_else_{b}", a, b, c)
             for c in (20, 40, 60, 80) for a in actions for b in actions if a != b]
    assert len(menu) == 27
    assert {m[0] for m in menu} == {r.id for r in implementation.candidate_rules()}
    boundaries = (19, 20, 21, 39, 40, 41, 59, 60, 61, 79, 80, 81)
    for rule_id, short, long, cutoff in menu:
        actual = next(r for r in implementation.candidate_rules() if r.id == rule_id)
        for words in boundaries:
            query = " \t\n".join(["authored"] * words)
            assert actual.choose(query) == (short if cutoff is None or words <= cutoff else long)
    for case in range(100):
        items, records = helpers["fixture_data"]()
        for item in items:
            words = boundaries[rng.randrange(len(boundaries))]
            item["query"] = " ".join([item["id"]] + ["word"] * (words - 1))
        for row in records:
            correct = bool(rng.getrandbits(1))
            tokens = rng.randint(1, 1024)
            answer = "7" if correct else "8"
            row.update(correct=correct, answer=answer, tokens=tokens)
            row["trace"]["generations"][0].update(tokens=tokens, output=f"Answer: {answer}")
            if row["strategy"] == "PAL":
                row["trace"]["tools"][0]["output"] = answer
        fit = [i for i in items if i["split"] == "train"]
        bank = {(r["id"], r["strategy"]): r for r in records}
        ranks = []
        for rule_id, short, long, cutoff in menu:
            chosen = [bank[(i["id"], short if cutoff is None or len(i["query"].split()) <= cutoff else long)] for i in fit]
            correct = sum(r["correct"] for r in chosen)
            tokens = sum(r["tokens"] for r in chosen)
            # All candidates share n: exact utility numerator is 10000*c - t.
            ranks.append((-(10000 * correct - tokens), -correct, tokens, cutoff is not None, rule_id))
        result = implementation.fit_selection(items, records)
        assert result["selected_rule"]["id"] == min(ranks)[-1], case
        assert result["fixed_reference"]["id"] == min(r for r in ranks if not r[3])[-1], case

    # Unequal group sizes: resample complete lists, independently of production
    # sufficient-statistic sums/counts. Explicit linear percentile interpolation.
    ours, reference = [], []
    for index, (group, good, tokens) in enumerate([
        ("a", True, 300), ("b", False, 50), ("b", True, 800),
        ("c", False, 1000), ("c", False, 40), ("c", True, 600),
    ]):
        ours.append(dict(id=str(index), group_id=group, correct=good, tokens=tokens))
        reference.append(dict(id=str(index), group_id=group, correct=not good, tokens=200))
    result = implementation.paired_comparison(ours, reference)
    groups = [[(int(a["correct"])-int(b["correct"]), a["tokens"]-b["tokens"])
               for a, b in zip(ours, reference) if a["group_id"] == g] for g in ("a", "b", "c")]
    generator = np.random.default_rng(42)
    draws = []
    for _ in range(2000):
        sample = [pair for g in generator.integers(0, 3, 3) for pair in groups[g]]
        acc = sum(v[0] for v in sample) / len(sample)
        tokens = sum(v[1] for v in sample) / len(sample)
        draws.append((acc, tokens, acc - tokens / 10000))
    for column, name in enumerate(("accuracy", "generated_tokens", "utility")):
        values = sorted(d[column] for d in draws)
        expected = []
        for p in (.025, .975):
            position = p * 1999
            lo = int(position)
            expected.append(values[lo] + (position-lo) * (values[lo+1]-values[lo]))
        assert np.allclose(expected, result["metrics"][name]["ci95"], atol=1e-12, rtol=0)
    paths = ["experiments/gsm8k_routing_baseline.py", "experiments/research_study.py",
             "experiments/research_pilot.py", "tests/test_gsm8k_routing_baseline.py",
             "docs/gsm8k_development_validation_protocol_20261004.md"]
    evidence = dict(kind="independent_authored_fixture_review", random_banks=100,
                    rule_boundary_checks=27*len(boundaries), bootstrap_draws_checked=2000,
                    source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                    candidate_content_read=False, new_model_calls=0, stage0_changed=False,
                    model_quality_evidence=False)
    (Path(__file__).parent / "probe_results.json").write_text(json.dumps(evidence, indent=2)+"\n")
    print("PASS: 100 independent selection oracles; 324 boundaries; 2000 group-bootstrap draws.")


if __name__ == "__main__":
    main()
