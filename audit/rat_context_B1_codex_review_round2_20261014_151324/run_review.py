"""Run independent headless B1 review suites and record source stability."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
start = json.loads((HERE / "manifest_start.json").read_text())
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
suites = {
    "existing_regressions": [
        "tests/test_rat_context_snapshot.py",
        "audit/rat_context_B1_codex_review_20261014_123157/review_probes.py",
        "tests/test_rat_context_audit.py",
        "tests/test_artifact_store_lifecycle.py",
    ],
    "provenance_probes": [str(HERE / "provenance_probes.py")],
}


def run(item):
    name, files = item
    argv = [sys.executable, "-m", "pytest", *files, "-p", "no:cacheprovider", "-q", "--tb=short",
            f"--junitxml={HERE / (name + '.xml')}"]
    then = time.monotonic()
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE / (name + ".log")).write_text(result.stdout + result.stderr)
    xml = ET.parse(HERE / (name + ".xml")).getroot()
    stats = {key: sum(int(s.get(key, 0)) for s in xml.iter("testsuite"))
             for key in ("tests", "failures", "errors", "skipped")}
    return {"name": name, "argv": argv, "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - then, 3), **stats,
            "stdout": result.stdout, "stderr": result.stderr}


with ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(run, suites.items()))
finish = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in start}
(HERE / "manifest_finish.json").write_text(json.dumps(finish, indent=2) + "\n")
drift = [p for p in start if start[p] != finish[p]]
report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "suites": results,
          "changed_during_review": drift, "software_tests_only": True, "live_model_calls": 0}
(HERE / "test_run.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"suites": [{k: r[k] for k in ("name", "exit_code", "tests", "failures", "errors", "duration_seconds")}
                            for r in results], "source_drift": drift}, indent=2))
