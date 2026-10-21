"""Pytest plugin to redirect probe fixture writers to a dedicated output folder.
Ensures immutable historical review directories are never overwritten during acceptance runs.
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROBE_OUTPUTS = HERE / "prior_probe_outputs"

@pytest.hookimpl
def pytest_collection_modifyitems(items):
    for item in items:
        mod = getattr(item, "module", None)
        if mod is None:
            continue
        p = Path(getattr(mod, "__file__", "")).resolve()
        if "audit/rat_cot_runtime_codex_review_r" in str(p) or "audit/rat_overnight_sweep_codex_review_r" in str(p):
            dest = PROBE_OUTPUTS / p.parent.name
            dest.mkdir(parents=True, exist_ok=True)
            mod.HERE = dest
