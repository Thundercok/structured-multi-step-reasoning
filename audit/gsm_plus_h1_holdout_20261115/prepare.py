"""Build the 819-item GSM-Plus holdout (positions 501..1319). See docs/gsm_plus_h1_holdout_prereg.md.

Prints counts only, never question text.
"""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from structured_llm import gsm8k  # noqa: E402

DATA = ROOT / "data/gsm_plus_v1"
RUN = Path(__file__).parent
FIRST = ROOT / "audit/gsm_plus_replication_20261114"
N = 819


def main():
    raw = DATA / "raw_test.jsonl"
    expected = json.loads((FIRST / "data_manifest.json").read_text())["raw_sha256"]
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"raw sha256 {digest} != {expected}")
    rows = [json.loads(line) for line in raw.read_text().splitlines() if line.strip()]
    subst = [r for r in rows if "numerical substitution" in r["perturbation_type"].lower()]
    seen = {gsm8k.normalize(r["question"]) for split in gsm8k.load_splits() for r in split}
    seen |= {gsm8k.normalize(q) for q in gsm8k.used_questions()}
    pool = sorted((r for r in subst if gsm8k.normalize(r["question"]) not in seen),
                  key=lambda r: gsm8k.rank_key(r["question"]))
    items = [{"id": gsm8k.rank_key(r["question"])[:16], "question": r["question"],
              "answer": str(r["answer"]).strip().replace(",", "").replace("$", "")} for r in pool[500:]]

    first_ids = {json.loads(l)["id"] for l in (FIRST / "eval_cf/tuned.jsonl").read_text().splitlines() if l}
    ids = {i["id"] for i in items}
    if len(ids) != len(items) or len(items) != N or ids & first_ids or len(first_ids) != 500:
        raise SystemExit(f"bad holdout: {len(items)} items, {len(ids & first_ids)} shared with first 500")
    out = DATA / "holdout_819.jsonl"
    with out.open("w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    manifest = {"raw_sha256": digest, "items_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                "numerical_substitution": len(subst), "pool": len(pool), "holdout": len(items),
                "shared_with_first_500": 0}
    (RUN / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
