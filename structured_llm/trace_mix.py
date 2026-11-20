"""Build nested self/human mixed training sets for the trace-source dose experiment.

Given matched `self/train.jsonl` and `human/train.jsonl` (same questions, same row order),
ranks row indices deterministically by SHA-256 of `f"{mix_seed}:{idx}"` and replaces the
first `k(pct)` rows with the `human` trace while keeping the remaining rows as `self`.

Because every ratio uses the same ranking, the human-trace index sets are strictly nested:
    S_0 (empty) ⊂ S_25 ⊂ S_50 ⊂ S_75 ⊂ S_100 (all rows),
and row order is preserved identically across all five datasets.

    python -m structured_llm.trace_mix SRC_DIR OUT_DIR [--seed 20261120]
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

SPLIT = "<|im_start|>assistant\n"
DEFAULT_RATIOS = (25, 50, 75)
DEFAULT_SEED = 20261120


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text)
    return hashlib.sha256(text.encode()).hexdigest()


def ranked_indices(n, seed=DEFAULT_SEED):
    """Deterministic permutation of 0..n-1 using SHA-256."""
    return sorted(range(n), key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())


def human_count(n, pct):
    """Number of human rows for integer percentage `pct` in [0, 100]."""
    return round(n * pct / 100)


def build_nested_mixes(src_dir, out_dir, ratios=DEFAULT_RATIOS, seed=DEFAULT_SEED):
    src = Path(src_dir)
    out = Path(out_dir)
    self_path = src / "self/train.jsonl"
    human_path = src / "human/train.jsonl"
    valid_path = src / "self/valid.jsonl"

    self_rows = read_jsonl(self_path)
    human_rows = read_jsonl(human_path)
    if len(self_rows) != len(human_rows):
        raise ValueError(f"row count mismatch: self={len(self_rows)} vs human={len(human_rows)}")

    n = len(self_rows)
    for i, (s, h) in enumerate(zip(self_rows, human_rows)):
        sp = s["text"].split(SPLIT, 1)[0]
        hp = h["text"].split(SPLIT, 1)[0]
        if sp != hp:
            raise ValueError(f"prompt mismatch at row {i}")

    order = ranked_indices(n, seed=seed)
    manifest = {
        "src_dir": str(src),
        "self_train_sha256": sha256_file(self_path),
        "human_train_sha256": sha256_file(human_path),
        "valid_sha256": sha256_file(valid_path),
        "n_rows": n,
        "mix_seed": seed,
        "ratios": {},
    }

    prev_set = set()
    for pct in sorted(ratios):
        k = human_count(n, pct)
        human_idx = set(order[:k])
        if not prev_set.issubset(human_idx):
            raise RuntimeError("nesting invariant violated")
        prev_set = human_idx

        mixed = [human_rows[i] if i in human_idx else self_rows[i] for i in range(n)]
        name = f"mix{pct}"
        target = out / name
        target.mkdir(parents=True, exist_ok=True)
        train_sha = write_jsonl(target / "train.jsonl", mixed)
        shutil.copyfile(valid_path, target / "valid.jsonl")
        manifest["ratios"][str(pct)] = {
            "name": name,
            "human_count": k,
            "self_count": n - k,
            "human_frac": round(k / n, 6),
            "train_sha256": train_sha,
            "human_indices": sorted(human_idx),
        }

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    manifest = build_nested_mixes(args.src_dir, args.out_dir, seed=args.seed)
    summary = {k: {m: v[m] for m in ("name", "human_count", "self_count", "human_frac", "train_sha256")}
               for k, v in manifest["ratios"].items()}
    print(json.dumps({"n_rows": manifest["n_rows"], "mix_seed": manifest["mix_seed"], "ratios": summary}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
