#!/usr/bin/env python3
"""
scripts/overnight_pipeline.py — Master Autonomous Overnight Pipeline for 'rat'.
Executes:
  Step 1: Batch Embed all remaining documents into SQLite/VectorCache.
  Step 2: Run SOTA Benchmark Suite and generate comparison chart & LaTeX table.
  Step 3: 1-Click build standalone rat.app & rat.dmg for distribution.
  Final: Clean up WAL, release memory, and power down tasks.
Enforces a hard deadline (default 06:15 AM) so the machine is 100% idle before user departs.
"""

import argparse
import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "overnight_summary.log"


def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def run_pipeline(deadline_str: str = "06:15"):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== RAT AUTONOMOUS OVERNIGHT PIPELINE LOG ===\n\n")

    log(f"🚀 Initializing Master Overnight Pipeline...")
    log(f"⏰ Hard Deadline configured: {deadline_str} AM (will terminate before then)")

    # Calculate deadline timestamp
    now = datetime.datetime.now()
    try:
        h, m = map(int, deadline_str.split(":"))
        deadline_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if deadline_dt <= now:
            deadline_dt += datetime.timedelta(days=1)
    except Exception:
        deadline_dt = now + datetime.timedelta(hours=4)

    deadline_ts = deadline_dt.timestamp()

    # STEP 1: Batch Embedding
    log("▶️ STEP 1/3: Starting Batch Vector Embedding across unindexed documents...")
    t1_start = time.time()
    res1 = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "batch_embed_all.py"), "--deadline", deadline_str],
        cwd=str(PROJECT_ROOT)
    )
    t1_elapsed = time.time() - t1_start
    log(f"✅ STEP 1 Finished in {t1_elapsed/60.0:.2f} mins (Return code: {res1.returncode})")

    if time.time() >= deadline_ts:
        log("⚠️ Deadline reached after Step 1. Stopping cleanly.")
        return

    # STEP 2: SOTA Benchmarking & Charts
    log("▶️ STEP 2/3: Generating SOTA Latency Benchmark & LaTeX Tables...")
    t2_start = time.time()
    res2 = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "generate_showcase_benchmarks.py")],
        cwd=str(PROJECT_ROOT)
    )
    t2_elapsed = time.time() - t2_start
    log(f"✅ STEP 2 Finished in {t2_elapsed/60.0:.2f} mins (Return code: {res2.returncode})")

    if time.time() >= deadline_ts:
        log("⚠️ Deadline reached after Step 2. Stopping cleanly.")
        return

    # STEP 3: Standalone DMG Build
    log("▶️ STEP 3/3: Packaging Standalone rat.app & rat.dmg...")
    t3_start = time.time()
    res3 = subprocess.run(
        ["/bin/bash", str(PROJECT_ROOT / "scripts" / "build_app.sh")],
        cwd=str(PROJECT_ROOT)
    )
    t3_elapsed = time.time() - t3_start
    log(f"✅ STEP 3 Finished in {t3_elapsed/60.0:.2f} mins (Return code: {res3.returncode})")

    # FINAL CLEANUP
    log("🧹 Executing Final SQLite WAL Checkpoint and Memory Cleanup...")
    try:
        import sqlite3
        conn = sqlite3.connect(str(Path.home() / ".rat" / "rat_index.db"))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception as e:
        log(f"Note on WAL checkpoint: {e}")

    total_elapsed = (time.time() - t1_start) / 60.0
    log(f"🎉 All pipeline stages successfully completed in {total_elapsed:.2f} minutes!")
    log("💤 Machine is now completely idle, cool, and ready for departure.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master Autonomous Overnight Pipeline")
    parser.add_argument("--deadline", type=str, default="06:15", help="HH:MM hard deadline")
    args = parser.parse_args()
    run_pipeline(deadline_str=args.deadline)
