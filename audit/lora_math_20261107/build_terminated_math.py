"""Filter structured MATH training/validation sets to only sequences that finish

cleanly within 512 tokens (contain '</think>\n\nAnswer:' and <= 512 tokens).
This removes truncated training examples so the model learns proper termination.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from mlx_lm.tokenizer_utils import load_tokenizer
except ImportError:
    from mlx_lm.tokenizer_utils import load as _load
    def load_tokenizer(p):
        return _load(Path(p))

from structured_llm.intervene import model_path

SRC_DIRS = [
    Path("data/structured_math_v1"),
    Path("data/math_source/structured_math_v1"),
]

OUT_DIR = Path("data/structured_math_term_v1")


def find_src_dir() -> Path:
    for d in SRC_DIRS:
        if d.exists() and (d / "train.jsonl").exists():
            return d
    raise FileNotFoundError(f"None of the candidate source directories exist: {SRC_DIRS}")


def filter_split(src_file: Path, out_file: Path, tokenizer, max_len: int = 512) -> tuple[int, int, int]:
    total = 0
    kept = 0
    dropped = 0
    with open(src_file, "r", encoding="utf-8") as fin, open(out_file, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            total += 1
            row = json.loads(line)
            text = row.get("text", "")
            if "</think>\n\nAnswer:" not in text:
                dropped += 1
                continue
            toks = tokenizer.encode(text)
            if len(toks) > max_len:
                dropped += 1
                continue
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += 1
    return total, kept, dropped


def main():
    src_dir = find_src_dir()
    print(f"Reading source data from: {src_dir}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading tokenizer (CPU only, 0 weight loading)...")
    tokenizer = load_tokenizer(model_path())

    train_total, train_kept, train_dropped = filter_split(
        src_dir / "train.jsonl", OUT_DIR / "train.jsonl", tokenizer, max_len=512
    )
    print(f"Train: kept {train_kept}/{train_total} ({train_dropped} dropped)")

    valid_total, valid_kept, valid_dropped = filter_split(
        src_dir / "valid.jsonl", OUT_DIR / "valid.jsonl", tokenizer, max_len=512
    )
    print(f"Valid: kept {valid_kept}/{valid_total} ({valid_dropped} dropped)")

    # Also copy or symlink dev.jsonl if present so evaluations can access it if needed
    if (src_dir / "dev.jsonl").exists():
        import shutil
        shutil.copyfile(src_dir / "dev.jsonl", OUT_DIR / "dev.jsonl")

    manifest = {
        "source_dir": str(src_dir),
        "max_seq_length": 512,
        "required_closing_tag": "</think>\n\nAnswer:",
        "train_total": train_total,
        "train_kept": train_kept,
        "train_dropped_over_512": train_dropped,
        "valid_total": valid_total,
        "valid_kept": valid_kept,
        "valid_dropped_over_512": valid_dropped,
    }
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
