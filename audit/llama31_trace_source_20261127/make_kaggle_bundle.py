"""Build self-contained ~1.5 MB Kaggle Dataset zip for H5 (Llama-3.1-8B-Instruct).

Packages:
  - structured_llm/ pure-Python modules (trace.py, gsm8k.py, counterfactual.py, evaluate.py, intervene.py, pal.py)
  - audit/llama31_trace_source_20261127/hf_runner.py
  - docs/llama31_trace_source_prereg.md
  - bundle/candidates_strict.jsonl, valid_strict.jsonl, eval_500.jsonl, bundle_manifest.json

Output: dist/kaggle_llama31_h5_bundle.zip
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.llama31_trace_source_20261127.hf_runner import cmd_prep_pool


def build_zip(out_zip: Path | None = None) -> Path:
    if out_zip is None:
        out_zip = ROOT / "dist" / "kaggle_llama31_h5_bundle.zip"
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        cmd_prep_pool(stage / "bundle")

        pkg_dst = stage / "structured_llm"
        pkg_dst.mkdir(parents=True, exist_ok=True)
        for mod_name in ("__init__.py", "trace.py", "gsm8k.py", "counterfactual.py", "evaluate.py", "intervene.py", "pal.py"):
            shutil.copy2(ROOT / "structured_llm" / mod_name, pkg_dst / mod_name)

        runner_dst = stage / "audit" / "llama31_trace_source_20261127"
        runner_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "audit" / "llama31_trace_source_20261127" / "hf_runner.py", runner_dst / "hf_runner.py")

        docs_dst = stage / "docs"
        docs_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "docs" / "llama31_trace_source_prereg.md", docs_dst / "llama31_trace_source_prereg.md")

        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(stage.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(stage))

    print(f"Built {out_zip} ({out_zip.stat().st_size / 1024:.1f} KB)")
    return out_zip


if __name__ == "__main__":
    build_zip()
