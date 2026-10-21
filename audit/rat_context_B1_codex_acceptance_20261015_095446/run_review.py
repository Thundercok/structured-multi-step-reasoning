"""Run current headless B1 acceptance and core checks without touching old packets."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
focused = [
    "tests/test_rat_context_snapshot.py", "tests/test_rat_context_audit.py", "tests/test_artifact_store_lifecycle.py",
    "audit/rat_context_B1_codex_review_20261014_123157/review_probes.py",
    "audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py",
    "audit/rat_context_B1_independent_20261014_084657/origin_scope_probes.py",
    "audit/rat_context_B1_codex_review_current_20261014_210330/raw_receipt_probes.py",
]
core = json.loads((ROOT / "audit/rat_context_B1_codex_review_current_20261014_210330/core_run.json").read_text())["argv"]
core = [a for a in core if not a.startswith("--junitxml=")]
core[0] = PYTHON
commands = {
    "focused": [PYTHON, "-m", "pytest", *focused, "-p", "no:cacheprovider", "-q", "--tb=short"],
    "registered_result": [PYTHON, "-m", "pytest", str(HERE / "registered_result_probes.py"),
                          "-p", "no:cacheprovider", "-q", "--tb=short"],
    "core": core,
}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(item):
    name, command = item
    argv = [*command, "--junitxml=" + str(HERE / (name + ".xml"))]
    tick = time.monotonic()
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE / (name + ".log")).write_text(result.stdout + result.stderr)
    xml = HERE / (name + ".xml")
    stats = ({key: sum(int(s.get(key, 0)) for s in ET.parse(xml).getroot().iter("testsuite"))
              for key in ("tests", "failures", "errors", "skipped")} if xml.exists() else {})
    return {"name": name, "argv": argv, "exit_code": result.returncode, **stats,
            "duration_seconds": round(time.monotonic() - tick, 3), "stdout": result.stdout, "stderr": result.stderr}


with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(run, commands.items()))
start = json.loads((HERE / "manifest_start.json").read_text())
finish = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in start}
drift = [p for p in start if start[p] != finish[p]]
(HERE / "manifest_finish.json").write_text(json.dumps(finish, indent=2) + "\n")
(HERE / "test_run.json").write_text(json.dumps({"suites": results, "source_drift": drift,
                                               "live_model_calls": 0}, indent=2) + "\n")
print(json.dumps({"suites": [{k: r[k] for k in ("name", "exit_code", "tests", "failures", "errors") if k in r}
                             for r in results], "source_drift": drift}, indent=2))
sys.exit(1 if drift or any(r["exit_code"] for r in results) else 0)
