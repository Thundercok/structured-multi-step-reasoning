"""Verify unchanged review inputs and final local design artifacts, offline."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DESIGN = ROOT / "audit/rat_context_snapshot_design_20261014"
ADR = ROOT / "docs/adr-004-rat-context-snapshot.md"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = read(HERE / "manifest_start.json")
changed = [name for name, expected in manifest["protected_inputs_sha256"].items()
           if sha(ROOT / name) != expected]
assert not changed, changed
fixed = read(ROOT / "audit/rat_core_reconciliation_fix_20261013/test_run.json")
assert all(sha(ROOT / name) == value for name, value in fixed["source_sha256_finish"].items())
raw = read(ROOT / "audit/rat_context_audit_20261014/captures.json")
actor = [c for c in raw["calls"] if c["phase"] == "actor"]
tools = [c["measurements"]["components"]["tools"]["chars"] for c in actor]
totals = [c["measurements"]["total"]["chars"] for c in actor]
measured = {"cases": len(raw["cases"]), "turns": len(raw["turns"]), "calls": len(raw["calls"]),
            "actor_calls": len(actor), "planner_calls": len(raw["calls"]) - len(actor),
            "tools_share_mean_per_call_percent": sum(t / total for t, total in zip(tools, totals)) / len(actor) * 100,
            "tools_share_ratio_sums_percent": sum(tools) / sum(totals) * 100,
            "tools_share_min_percent": min(t / total for t, total in zip(tools, totals)) * 100,
            "tools_share_max_percent": max(t / total for t, total in zip(tools, totals)) * 100}
assert measured["cases"] == 12 and measured["turns"] == 20 and measured["calls"] == 41
assert round(measured["tools_share_mean_per_call_percent"], 2) == 58.72
assert round(measured["tools_share_ratio_sums_percent"], 2) == 53.26
validation = read(DESIGN / "validation.json")
assert validation["status"] == "design_examples_consistent_not_runtime_validation"
assert validation["production_implemented"] is False and validation["live_model_calls"] == 0
assert all(sha(DESIGN / name) == expected for name, expected in validation["files_sha256"].items())

files = [ADR, *sorted(p for p in DESIGN.iterdir() if p.is_file()),
         HERE / "review.md", HERE / "validate_review.py"]
broken_links, whitespace_errors = [], []
for path in files:
    if path.suffix == ".py":
        ast.parse(path.read_text(), filename=str(path))
    if path.suffix == ".md":
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if "://" not in target and not target.startswith("#") and not (path.parent / target.split("#")[0]).resolve().exists():
                broken_links.append({"path": str(path.relative_to(ROOT)), "target": target})
    result = subprocess.run(["git", "diff", "--no-index", "--check", "/dev/null", str(path)],
                            capture_output=True, text=True)
    if result.stdout.strip() or result.stderr.strip() or result.returncode not in (0, 1):
        whitespace_errors.append({"path": str(path.relative_to(ROOT)), "exit_code": result.returncode,
                                  "output": result.stdout + result.stderr})
assert not broken_links, broken_links
assert not whitespace_errors, whitespace_errors
report = {
    "status": "handoffs_reviewed_B_design_proposed_not_implemented",
    "at_utc": datetime.now(timezone.utc).isoformat(),
    "protected_input_count": len(manifest["protected_inputs_sha256"]),
    "changed_protected_inputs": changed,
    "core_matches_previous_fix_packet": True,
    "production_tests_rerun": False,
    "reason_no_production_test_rerun": "Protected core/source/tests unchanged; previous 292-test result remains the existing regression evidence.",
    "A_metrics_recomputed": measured,
    "B_design_checks": len(validation["checks"]),
    "broken_local_links": broken_links,
    "new_artifact_whitespace_errors": whitespace_errors,
    "live_inference_calls": 0, "runtime_or_UI_implemented_in_this_review": False,
    "git_push_pull_reset_force": False,
    "design_and_review_files_sha256": {str(p.relative_to(ROOT)): sha(p) for p in files},
    "limits": ["Scripted captures and authored B design examples are not measured AI quality or speed-up.",
               "B runtime implementation, new native channel fixtures and user phase decision remain pending."],
}
(HERE / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(f"Reviewed inputs preserved: {len(manifest['protected_inputs_sha256'])} files; design checks {len(validation['checks'])}; links/whitespace clean.")
