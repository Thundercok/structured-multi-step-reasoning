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
        if "audit/" in str(p) and "rat_cot_runtime_acceptance" not in str(p):
            dest = PROBE_OUTPUTS / p.parent.name
            dest.mkdir(parents=True, exist_ok=True)
            mod.HERE = dest
            if hasattr(mod, "helper") and hasattr(mod.helper, "HERE"):
                mod.helper.HERE = dest
            if "test_qwen_boundary_replay" in str(p) and not getattr(mod, "_seam_versioned", False):
                mod._seam_versioned = True
                orig_source_backend = getattr(mod, "source_backend", None)
                if orig_source_backend:
                    def versioned_source_backend(*args, **kwargs):
                        backend, counters, controller = orig_source_backend(*args, **kwargs)
                        orig_chat = backend._chat
                        def structured_chat(messages, **kw):
                            try:
                                return orig_chat(messages, **kw)
                            except Exception:
                                if hasattr(backend, "last_trace") and isinstance(backend.last_trace, dict):
                                    backend.last_trace["generations"].append({
                                        "messages": messages,
                                        "status": "failed",
                                        "finish_reason": "error",
                                        "tokens": 0,
                                    })
                                raise
                        backend._chat = structured_chat
                        return backend, counters, controller
                    mod.source_backend = versioned_source_backend
