"""Download the official GSM8K test file once and convert it to evaluation items.

See docs/sealed_test_gsm8k_prereg.md section 1. Prints counts only, never question text.
"""

import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from structured_llm import gsm8k  # noqa: E402

REVISION = "3101c7d5072418e28b9008a6636bde82a006892c"
URL = f"https://raw.githubusercontent.com/openai/grade-school-math/{REVISION}/grade_school_math/data/test.jsonl"
DATA = ROOT / "data/gsm8k_sealed_test_v1"
RUN = Path(__file__).parent


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    raw = DATA / "raw_test.jsonl"
    if not raw.exists():
        raw.write_bytes(urllib.request.urlopen(URL, timeout=60).read())
    rows = [json.loads(line) for line in raw.read_text().splitlines() if line.strip()]

    items = [{"id": gsm8k.rank_key(r["question"])[:16], "question": r["question"],
              "answer": gsm8k.gold_answer(r["answer"])} for r in rows]
    if len({i["id"] for i in items}) != len(items):
        raise SystemExit("duplicate ids in test items")
    with (DATA / "test.jsonl").open("w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    seen = {gsm8k.normalize(r["question"]) for split in gsm8k.load_splits() for r in split}
    seen |= {gsm8k.normalize(q) for q in gsm8k.used_questions()}
    overlap = sorted(i["id"] for i in items if gsm8k.normalize(i["question"]) in seen)

    manifest = {
        "url": URL,
        "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "items_sha256": hashlib.sha256((DATA / "test.jsonl").read_bytes()).hexdigest(),
        "rows": len(rows),
        "overlap_with_train_valid_dev": len(overlap),
        "overlap_ids": overlap,
    }
    (RUN / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "overlap_ids"}))
    if len(rows) != 1319:
        raise SystemExit(f"expected 1319 rows, got {len(rows)}")


if __name__ == "__main__":
    main()
