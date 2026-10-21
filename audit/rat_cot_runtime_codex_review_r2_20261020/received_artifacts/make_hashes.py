import json
import hashlib
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

with open(ROOT / "audit/rat_overnight_sweep_codex_repair_r7_20261020/source_end.json") as f:
    start_data = json.load(f)

source_start = {
    "time_utc": "2026-10-20T06:34:00+00:00",
    "files": dict(start_data["files"]),
}
with open(ROOT / "audit/rat_cot_runtime_acceptance_20261020/source_start.json", "w") as f:
    json.dump(source_start, f, indent=2)

tracked_files = list(start_data["files"].keys()) + [
    "bundle.py",
    "reasoning/bundle.py",
    "reasoning/runtime.py",
    "rat/engine/meta_reasoner.py",
    "rat/ui/reasoning_worker.py",
    "tests/test_policy_bundle.py",
    "tests/test_online_reasoning_execution.py",
    "tests/test_native_acceptance_readiness.py",
]
end_files = {}
for p in sorted(tracked_files):
    h = hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    end_files[p] = h

modified = [p for p in start_data["files"] if end_files.get(p) != start_data["files"][p]]
new_fls = [p for p in end_files if p not in start_data["files"]]

source_end = {
    "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "files": end_files,
    "modified_files": modified,
    "new_files": new_fls,
}
with open(ROOT / "audit/rat_cot_runtime_acceptance_20261020/source_end.json", "w") as f:
    json.dump(source_end, f, indent=2)

print(f"source_start.json ({len(source_start['files'])} files) and source_end.json ({len(source_end['files'])} files) saved.")
print(f"Modified: {modified}")
print(f"New: {new_fls}")
