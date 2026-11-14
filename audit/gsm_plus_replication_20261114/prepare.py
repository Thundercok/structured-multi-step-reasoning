"""Download GSM-Plus once, keep numerical substitution, sample 500. See docs/gsm_plus_replication_prereg.md.

Prints counts only, never question text.
"""

import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from structured_llm import gsm8k  # noqa: E402

REVISION = "3b708db57b96a16e8e3368ed2956990c0809440e"
URL = f"https://huggingface.co/datasets/qintongli/GSM-Plus/resolve/{REVISION}/data/test-00000-of-00001.jsonl"
DATA = ROOT / "data/gsm_plus_v1"
RUN = Path(__file__).parent
N = 500


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    raw = DATA / "raw_test.jsonl"
    if not raw.exists():
        raw.write_bytes(urllib.request.urlopen(URL, timeout=120).read())
    rows = [json.loads(line) for line in raw.read_text().splitlines() if line.strip()]
    types = sorted({r["perturbation_type"] for r in rows})
    subst = [r for r in rows if "numerical substitution" in r["perturbation_type"].lower()]

    seen = {gsm8k.normalize(r["question"]) for split in gsm8k.load_splits() for r in split}
    seen |= {gsm8k.normalize(q) for q in gsm8k.used_questions()}
    overlap = [r for r in subst if gsm8k.normalize(r["question"]) in seen]
    pool = sorted((r for r in subst if gsm8k.normalize(r["question"]) not in seen),
                  key=lambda r: gsm8k.rank_key(r["question"]))
    items = [{"id": gsm8k.rank_key(r["question"])[:16], "question": r["question"],
              "answer": str(r["answer"]).strip().replace(",", "").replace("$", "")} for r in pool[:N]]
    if len({i["id"] for i in items}) != len(items):
        raise SystemExit("duplicate ids")
    with (DATA / "test.jsonl").open("w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    manifest = {
        "url": URL,
        "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "items_sha256": hashlib.sha256((DATA / "test.jsonl").read_bytes()).hexdigest(),
        "rows": len(rows),
        "perturbation_types": types,
        "numerical_substitution": len(subst),
        "overlap_with_train_valid_dev": len(overlap),
        "sampled": len(items),
    }
    (RUN / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))
    if len(subst) != 1319 or len(items) != N:
        raise SystemExit(f"expected 1319 substitution rows and {N} items, got {len(subst)} and {len(items)}")


if __name__ == "__main__":
    main()
