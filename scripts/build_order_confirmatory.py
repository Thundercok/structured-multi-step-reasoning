#!/usr/bin/env python3
"""Builds a fresh, held-out confirmatory ordering dataset with gapB wording.

Ensures:
- Exactly 100 items (25 per level across levels 1..4)
- Gap wording style B
- Seed 5000 (completely disjoint from tune pool seed 1000 and gen02_v2 seed 0)
- Zero canonical problem overlap with exposed tune pool
- 100% verification pass by both procedural solver and query parser
"""

import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.gen_tasks as gt
from scripts.verified_pal_order import parse_order_query


def build_confirmatory_order_dataset(
    out_path: str = "data/order_confirmatory_gapB_100.json",
    seed: int = 5000,
    n_per_level: int = 25,
) -> dict:
    tune_path = ROOT / "data/gen02_tune.json"
    tune_keys = set()
    if tune_path.exists():
        tune_data = json.loads(tune_path.read_text(encoding="utf-8"))
        for it in tune_data.get("items", []):
            if it.get("family") == "order":
                k = gt._key("order", it.get("meta", {}), it.get("query", ""))
                tune_keys.add(k)

    rng = random.Random(seed)
    seen = set(tune_keys)
    items = []
    idx = 0

    for lvl in range(len(gt.ORDER_LEVELS)):
        for _ in range(n_per_level):
            while True:
                m, q, a, diff = gt.gen_order(rng, lvl, gap_style="B")
                k = gt._key("order", m, q)
                if k not in seen:
                    break
            seen.add(k)
            item = {
                "id": f"order_conf_{idx:04d}_en_gapB",
                "group_id": f"grp_order_conf_{idx:04d}",
                "query": q,
                "answer": a,
                "split": "confirmatory",
                "category": "order",
                "family": "order",
                "level": lvl + 1,
                "difficulty": diff,
                "checker": "order",
                "source": f"procedural:gen_tasks.py@0.2.2/seed={seed}/gapB",
                "meta": m,
            }
            assert gt.verify(item), f"Procedural verify failed for {item['id']}"
            ir = parse_order_query(q)
            assert ir is not None, f"Query parser failed for {item['id']}"
            items.append(item)
            idx += 1

    sha_items = gt.digest(items)
    meta = {
        "generator": f"gen_tasks.py {gt.VERSION} / build_order_confirmatory.py",
        "seed": seed,
        "n_items": len(items),
        "n_per_level": n_per_level,
        "family": "order",
        "gap_style": "B",
        "sha256_items": sha_items,
    }

    full_data = {"meta": meta, "items": items}
    target = ROOT / out_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=1)

    print(f"Generated {len(items)} items to {target} (sha256_items: {sha_items})")
    return meta


if __name__ == "__main__":
    build_confirmatory_order_dataset()
