"""Re-run current acceptance checks into a fresh packet; never overwrite evidence."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / ("recheck_" + datetime.now(ZoneInfo("Asia/Saigon")).strftime("%Y%m%d_%H%M%S"))
OUT.mkdir()
monitored = json.loads((HERE / "manifest_start.json").read_text())


def hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in monitored}


start = hashes()
(OUT / "manifest_start.json").write_text(json.dumps(start, indent=2) + "\n")
record = json.loads((HERE / "test_run.json").read_text())
commands = [(s["name"], s["argv"]) for s in record["suites"]]
commands.append(("core", json.loads((HERE / "core_run.json").read_text())["argv"]))


def run(item):
    name, recorded_argv = item
    argv = [arg for arg in recorded_argv if not arg.startswith("--junitxml=")]
    argv.append("--junitxml=" + str(OUT / (name + ".xml")))
    tick = time.monotonic()
    result = subprocess.run(argv, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                            capture_output=True, text=True)
    (OUT / (name + ".log")).write_text(result.stdout + result.stderr)
    return {"name": name, "argv": argv, "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - tick, 3),
            "stdout": result.stdout, "stderr": result.stderr}


with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(run, commands))
finish = hashes()
drift = [p for p in start if start[p] != finish[p]]
(OUT / "manifest_finish.json").write_text(json.dumps(finish, indent=2) + "\n")
(OUT / "test_run.json").write_text(json.dumps({"suites": results, "source_drift": drift,
                                               "live_model_calls": 0}, indent=2) + "\n")
print(OUT)
print(json.dumps({"exit_codes": {r["name"]: r["exit_code"] for r in results}, "source_drift": drift}))
sys.exit(1 if drift or any(r["exit_code"] for r in results) else 0)
