"""
Inventory runner for all 132 test files across the repository.
Runs each test file in isolated subprocess with finite timeout (60s),
capturing JUnit XML and raw logs, continuing across collection/import errors.
"""
import os
import sys
import json
import time
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = WORKSPACE / "audit" / "rat_overnight_sweep_repair_20261019"
LOGS_DIR = OUTPUT_DIR / "test_logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = str(WORKSPACE / ".venv" / "bin" / "python")

def get_test_files():
    tests_dir_files = sorted([p.relative_to(WORKSPACE) for p in (WORKSPACE / "tests").rglob("test_*.py")])
    root_files = sorted([p.relative_to(WORKSPACE) for p in WORKSPACE.glob("test_*.py")])
    return [str(p) for p in (tests_dir_files + root_files)]

def categorize_test(path_str: str) -> str:
    p = Path(path_str)
    name = p.name
    if path_str.startswith("tests/subagent") or "subagent" in name:
        return "subagent"
    if any(k in name for k in ("workbench", "omnibar", "widget", "ui", "scene", "theme")):
        return "ui"
    if any(k in name for k in ("finder", "search", "scanner", "crawler", "book", "spider")):
        return "finder_crawler"
    if any(k in name for k in ("reasoning", "cot", "agent", "stopping", "predictor", "study", "policy", "env", "mcts")):
        return "structured_reasoning"
    if any(k in name for k in ("completion", "reconciliation", "contract", "boundary", "runtime", "dispatcher", "journal")):
        return "runtime_contracts"
    if any(k in name for k in ("mlx", "model", "slm", "qa", "document")):
        return "model_qa"
    return "general_engine"

def run_single_test(test_rel_path: str, timeout: int = 60):
    safe_name = test_rel_path.replace("/", "__").replace(".", "_")
    xml_path = LOGS_DIR / f"{safe_name}.xml"
    log_path = LOGS_DIR / f"{safe_name}.log"

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"

    cmd = [
        PYTHON_EXE,
        "-m",
        "pytest",
        test_rel_path,
        "-q",
        f"--junitxml={str(xml_path)}",
    ]

    t0 = time.perf_counter()
    status = "UNKNOWN"
    total = 0
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    out = ""
    err = ""

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        duration_s = time.perf_counter() - t0
        out = proc.stdout
        err = proc.stderr
        retcode = proc.returncode

        # Parse JUnit XML if produced
        if xml_path.exists() and xml_path.stat().st_size > 0:
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                suite = root.find("testsuite") if root.tag == "testsuites" else root
                if suite is not None:
                    total = int(suite.attrib.get("tests", 0))
                    failed = int(suite.attrib.get("failures", 0))
                    errors = int(suite.attrib.get("errors", 0))
                    skipped = int(suite.attrib.get("skipped", 0))
                    passed = total - (failed + errors + skipped)
            except Exception:
                pass

        if retcode == 0:
            status = "PASSED"
        elif retcode == 1:
            status = "FAILED" if failed > 0 else "ERROR"
        elif retcode == 2:
            status = "INTERRUPTED"
        elif retcode == 4:
            status = "NO_TESTS_COLLECTED"
        elif retcode == 5:
            status = "NO_TESTS_FOUND"
        else:
            status = "ERROR"

    except subprocess.TimeoutExpired as te:
        duration_s = time.perf_counter() - t0
        status = "TIMEOUT"
        out = te.stdout or ""
        err = te.stderr or ""
        err += f"\n[Runner] Test timed out after {timeout}s"
    except Exception as ex:
        duration_s = time.perf_counter() - t0
        status = "EXCEPTION"
        err = str(ex)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"=== STDOUT ===\n{out}\n=== STDERR ===\n{err}\n")

    return {
        "file": test_rel_path,
        "group": categorize_test(test_rel_path),
        "status": status,
        "duration_s": round(duration_s, 2),
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "log_file": str(log_path.relative_to(OUTPUT_DIR)),
        "xml_file": str(xml_path.relative_to(OUTPUT_DIR)) if xml_path.exists() else None,
    }

def main():
    test_files = get_test_files()
    print(f"Discovered {len(test_files)} test files. Running inventory...")

    results = []
    jsonl_path = OUTPUT_DIR / "test_inventory_132.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as jsonl_file:
        for idx, tf in enumerate(test_files, start=1):
            res = run_single_test(tf, timeout=60)
            results.append(res)
            jsonl_file.write(json.dumps(res) + "\n")
            jsonl_file.flush()
            print(f"[{idx:03d}/{len(test_files):03d}] {res['status']:<7} {res['file']:<45} ({res['duration_s']}s, pass={res['passed']}/{res['total']})")

    # Aggregate by group
    groups = {}
    total_passed_tests = 0
    total_failed_tests = 0
    total_error_tests = 0
    total_skipped_tests = 0

    files_passed = 0
    files_failed = 0
    files_error = 0
    files_timeout = 0

    for r in results:
        g = r["group"]
        if g not in groups:
            groups[g] = {"files": 0, "passed_files": 0, "failed_files": 0, "error_files": 0, "timeout_files": 0,
                         "tests_total": 0, "tests_passed": 0, "tests_failed": 0, "tests_errors": 0, "tests_skipped": 0}
        grp = groups[g]
        grp["files"] += 1
        st = r["status"]
        if st == "PASSED":
            grp["passed_files"] += 1
            files_passed += 1
        elif st == "FAILED":
            grp["failed_files"] += 1
            files_failed += 1
        elif st == "TIMEOUT":
            grp["timeout_files"] += 1
            files_timeout += 1
        else:
            grp["error_files"] += 1
            files_error += 1

        grp["tests_total"] += r["total"]
        grp["tests_passed"] += r["passed"]
        grp["tests_failed"] += r["failed"]
        grp["tests_errors"] += r["errors"]
        grp["tests_skipped"] += r["skipped"]

        total_passed_tests += r["passed"]
        total_failed_tests += r["failed"]
        total_error_tests += r["errors"]
        total_skipped_tests += r["skipped"]

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_files": len(test_files),
        "files_passed": files_passed,
        "files_failed": files_failed,
        "files_error": files_error,
        "files_timeout": files_timeout,
        "tests_passed": total_passed_tests,
        "tests_failed": total_failed_tests,
        "tests_errors": total_error_tests,
        "tests_skipped": total_skipped_tests,
        "groups": groups,
        "results": results,
    }

    with open(OUTPUT_DIR / "test_inventory_132.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Generate Markdown table
    md_lines = [
        "# Test Inventory Summary (132 Files)",
        "",
        f"- Timestamp: {summary['timestamp_utc']}",
        f"- Total Active Test Files: {summary['total_files']}",
        f"- Fully Passing Files: {summary['files_passed']}",
        f"- Files with Failures: {summary['files_failed']}",
        f"- Files with Errors/Uncollected: {summary['files_error']}",
        f"- Files Timed Out: {summary['files_timeout']}",
        f"- Total Tests Passed across all 132 files: {total_passed_tests}",
        f"- Total Tests Failed: {total_failed_tests}",
        f"- Total Tests Skipped: {total_skipped_tests}",
        "",
        "## Summary by Group",
        "",
        "| Group | Files | Passed Files | Failed Files | Error/Uncollected | Tests Passed | Tests Failed |",
        "|---|---|---|---|---|---|---|",
    ]
    for g, d in sorted(groups.items()):
        md_lines.append(f"| {g} | {d['files']} | {d['passed_files']} | {d['failed_files']} | {d['error_files']} | {d['tests_passed']} | {d['tests_failed']} |")

    md_lines.append("")
    md_lines.append("## Detailed File Status")
    md_lines.append("")
    md_lines.append("| File | Group | Status | Duration (s) | Passed / Total | Log |")
    md_lines.append("|---|---|---|---|---|---|")
    for r in results:
        md_lines.append(f"| `{r['file']}` | {r['group']} | **{r['status']}** | {r['duration_s']} | {r['passed']}/{r['total']} | [`log`]({r['log_file']}) |")

    with open(OUTPUT_DIR / "test_inventory_132.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nDone. Summary written to {OUTPUT_DIR / 'test_inventory_132.json'} and test_inventory_132.md")

if __name__ == "__main__":
    main()
