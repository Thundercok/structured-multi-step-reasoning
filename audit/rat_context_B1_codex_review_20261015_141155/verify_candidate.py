"""Test the suggested compiler patch in an isolated process, without editing product files."""
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
original = json.loads((HERE / "test_run.json").read_text())["suites"][0]["argv"]
args = [a for a in original[3:] if not a.startswith("--junitxml=")]
args.insert(0, str(HERE / "slot_isolation_probes.py"))
args.append("--junitxml=" + str(HERE / "candidate.xml"))
bootstrap = """
import importlib.util, sys
from pathlib import Path
import rat.engine
candidate_path = sys.argv.pop(1)
spec = importlib.util.spec_from_file_location('rat.engine.context_snapshot', candidate_path)
candidate = importlib.util.module_from_spec(spec)
sys.modules['rat.engine.context_snapshot'] = candidate
spec.loader.exec_module(candidate)
rat.engine.context_snapshot = candidate
assert Path(candidate.compile_context_snapshot.__code__.co_filename).resolve() == Path(candidate_path).resolve()
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
"""
argv = [PYTHON, "-c", bootstrap, str(HERE / "context_snapshot_candidate.py"), *args]
tick = time.monotonic()
result = subprocess.run(argv, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                        capture_output=True, text=True)
(HERE / "candidate.log").write_text(result.stdout + result.stderr)
xml = HERE / "candidate.xml"
stats = ({key: sum(int(s.get(key, 0)) for s in ET.parse(xml).getroot().iter("testsuite"))
          for key in ("tests", "failures", "errors", "skipped")} if xml.exists() else {})
record = {"argv": argv, "exit_code": result.returncode, **stats,
          "duration_seconds": round(time.monotonic() - tick, 3),
          "candidate_sha256": hashlib.sha256((HERE / "context_snapshot_candidate.py").read_bytes()).hexdigest(),
          "isolation": "fresh subprocess importing audit candidate under the canonical module name",
          "applied_to_product": False, "stdout": result.stdout, "stderr": result.stderr}
(HERE / "candidate_run.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({k: record[k] for k in ("exit_code", "tests", "failures", "errors", "applied_to_product") if k in record}))
sys.exit(result.returncode)
