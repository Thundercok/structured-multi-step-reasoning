"""Independent current B1/core review. Writes evidence only in this review folder."""
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
baseline = ROOT / "audit/rat_context_B1_codex_acceptance_20261015_095446"
previous = json.loads((baseline / "test_run.json").read_text())["suites"]
focused = [a for a in previous[0]["argv"] if not a.startswith("--junitxml=")]
focused.insert(3, str(baseline / "registered_result_probes.py"))
core = [a for a in previous[2]["argv"] if not a.startswith("--junitxml=")]
commands = {
    "focused": focused,
    "slot_isolation": [PYTHON, "-m", "pytest", str(HERE / "slot_isolation_probes.py"),
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
diagnostic = subprocess.run([PYTHON, str(HERE / "diagnose_remaining_core.py")], cwd=ROOT,
                            env=env, capture_output=True, text=True)
(HERE / "diagnostic.log").write_text(diagnostic.stdout + diagnostic.stderr)
start = json.loads((HERE / "manifest_start.json").read_text())
finish = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in start}
drift = [p for p in start if start[p] != finish[p]]
(HERE / "manifest_finish.json").write_text(json.dumps(finish, indent=2) + "\n")
(HERE / "test_run.json").write_text(json.dumps({"suites": results, "source_drift": drift,
    "diagnostic_exit_code": diagnostic.returncode, "live_model_calls": 0}, indent=2) + "\n")
print(json.dumps({"suites": [{k: r[k] for k in ("name", "exit_code", "tests", "failures", "errors") if k in r}
                             for r in results], "source_drift": drift,
                  "diagnostic_exit_code": diagnostic.returncode}, indent=2))
sys.exit(1 if drift or any(r["exit_code"] for r in results) or diagnostic.returncode else 0)
