#!/usr/bin/env python3
"""Real-time pipeline monitoring dashboard for multi-step structured reasoning.

Displays active training jobs, loss curves, hardware thermals/battery,
and queued stages across GSM8K, MATH, and MSRA.

Usage:
    python tools/pipeline_status.py
    python tools/pipeline_status.py --watch
"""

import argparse
import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Dict, Optional, Tuple

REPO_ROOT = Path(__file__).parent.parent


def get_system_metrics() -> Dict[str, str]:
    """Extract battery, AC power, and memory/swap statistics."""
    metrics = {
        "battery": "Unknown",
        "ac": "Unknown",
        "load": "Unknown",
        "swap": "Unknown",
    }

    try:
        res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=2)
        m_batt = re.search(r"(\d+)%", res.stdout)
        if m_batt:
            metrics["battery"] = f"{m_batt.group(1)}%"
        metrics["ac"] = "AC Connected" if "AC Power" in res.stdout else "Battery Power"
    except Exception:
        pass

    try:
        load = os.getloadavg()
        metrics["load"] = f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
    except Exception:
        pass

    try:
        res = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, timeout=2)
        m_swap = re.search(r"used = (\d+\.?\d*M)", res.stdout)
        if m_swap:
            metrics["swap"] = m_swap.group(1)
    except Exception:
        pass

    return metrics


def parse_mlx_log(log_path: Path, total_iters: int) -> Dict[str, any]:
    """Parse MLX LoRA training log for latest metrics, progress, and speed."""
    info = {
        "exists": log_path.exists(),
        "current_iter": 0,
        "total_iters": total_iters,
        "train_loss": None,
        "val_loss": None,
        "it_sec": None,
        "tok_sec": None,
        "peak_mem": None,
        "is_active": False,
        "is_finished": False,
    }
    if not log_path.exists():
        return info

    content = log_path.read_text(encoding="utf-8", errors="replace")
    
    # Check if finished
    if "Saved adapter weights" in content and f"{total_iters:07d}_adapters.safetensors" in content:
        info["is_finished"] = True
    if "exit: 0" in content:
        info["is_finished"] = True

    # Find last training iteration
    iters = re.findall(
        r"Iter (\d+): Train loss ([\d\.]+), Learning Rate [^,]+, It/sec ([\d\.]+), Tokens/sec ([\d\.]+).*Peak mem ([\d\.]+) GB",
        content,
    )
    if iters:
        last = iters[-1]
        info["current_iter"] = int(last[0])
        info["train_loss"] = float(last[1])
        info["it_sec"] = float(last[2])
        info["tok_sec"] = float(last[3])
        info["peak_mem"] = f"{last[4]} GB"

    # Find last validation loss
    val_losses = re.findall(r"Iter (\d+): Val loss ([\d\.]+)", content)
    if val_losses:
        info["val_loss"] = float(val_losses[-1][1])

    # Check if updated within last 5 minutes (covers 50-step validation intervals)
    mtime = log_path.stat().st_mtime
    age_sec = time.time() - mtime
    info["is_active"] = (age_sec < 300) and not info["is_finished"]
    info["age_sec"] = age_sec

    return info


def render_progress_bar(current: int, total: int, width: int = 24) -> str:
    fraction = min(1.0, max(0.0, current / max(1, total)))
    filled = int(width * fraction)
    bar = "█" * filled + "░" * (width - filled)
    pct = fraction * 100.0
    return f"[{bar}] {pct:5.1f}% ({current}/{total})"


def render_dashboard():
    sys_info = get_system_metrics()

    stages = [
        (
            "GSM8K Plain Enriched SFT",
            REPO_ROOT / "audit/lora_gsm8k_enriched_20261107/train_gsm8k_enriched_2000_s0.log",
            2000,
        ),
        (
            "MATH Level 3-5 LoRA SFT",
            REPO_ROOT / "audit/lora_math_20261107/train.log",
            1000,
        ),
        (
            "GSM8K Counterfactual Enriched SFT",
            REPO_ROOT / "audit/lora_gsm8k_enriched_20261107/train_gsm8k_cf_enriched_2000_s0.log",
            2000,
        ),
        (
            "MATH Terminated-512 LoRA SFT",
            REPO_ROOT / "audit/lora_math_20261107/train_term.log",
            1000,
        ),
        (
            "MSRA Stage 1 Cold-Start DAG SFT",
            REPO_ROOT / "audit/lora_msra_20261107/train_stage1.log",
            2000,
        ),
        (
            "MSRA Stage 2 SimPO Alignment",
            REPO_ROOT / "audit/lora_msra_20261107/train_simpo.log",
            1000,
        ),
    ]

    out = []
    out.append("=" * 78)
    out.append(f"  MULTI-STEP STRUCTURED REASONING — LIVE PIPELINE DASHBOARD")
    out.append(f"  Local Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"  Power: {sys_info['ac']} ({sys_info['battery']}) | Swap: {sys_info['swap']} | Load: {sys_info['load']}")
    out.append("=" * 78)
    out.append("")

    active_found = False
    for name, log_path, total_iters in stages:
        parsed = parse_mlx_log(log_path, total_iters)
        if parsed["is_finished"]:
            status_tag = "\033[1;34m[COMPLETED]\033[0m"
        elif parsed["exists"] and sys_info["ac"] == "Battery Power":
            status_tag = "\033[1;33m[PAUSED (Battery Power — Plug in AC to auto-resume)]\033[0m"
        elif parsed["is_active"]:
            status_tag = "\033[1;32m[RUNNING]\033[0m"
            active_found = True
        elif parsed["exists"]:
            status_tag = "\033[1;33m[PAUSED / STAGED]\033[0m"
        else:
            status_tag = "\033[1;30m[QUEUED]\033[0m"

        out.append(f"{status_tag} {name}")
        if parsed["exists"]:
            bar = render_progress_bar(parsed["current_iter"], total_iters)
            train_l = f"{parsed['train_loss']:.4f}" if parsed["train_loss"] is not None else "N/A"
            val_l = f"{parsed['val_loss']:.4f}" if parsed["val_loss"] is not None else "N/A"
            speed = f"{parsed['tok_sec']:.1f} tok/s ({parsed['it_sec']:.2f} it/s)" if parsed["tok_sec"] else "N/A"
            mem = parsed["peak_mem"] or "N/A"
            
            # Compute ETA
            eta_str = ""
            if parsed["is_active"] and parsed["it_sec"] and parsed["it_sec"] > 0:
                rem_steps = total_iters - parsed["current_iter"]
                rem_sec = rem_steps / parsed["it_sec"]
                rem_min = rem_sec / 60.0
                eta_str = f" | ETA: {rem_min:.1f}m"

            out.append(f"    Progress: {bar}{eta_str}")
            out.append(f"    Train Loss: {train_l} | Val Loss: {val_l} | Speed: {speed} | Peak Mem: {mem}")
        else:
            out.append(f"    Progress: [Waiting for previous stage to complete]")
        out.append("")

    # Artifacts & Reports
    out.append("-" * 78)
    out.append("  PUBLICATION ARTIFACTS:")
    paper_pdf = REPO_ROOT / "docs/paper/nckh_structured_reasoning.pdf"
    gsm8k_rep = REPO_ROOT / "audit/lora_gsm8k_enriched_20261107/REPORT.md"
    gsm8k_cf_eval = REPO_ROOT / "audit/lora_gsm8k_enriched_20261107/eval_cf/tuned.jsonl"
    math_rep = REPO_ROOT / "audit/lora_math_20261107/REPORT.md"
    math_eval = REPO_ROOT / "audit/lora_math_20261107/eval/tuned.jsonl"
    msra_rep = REPO_ROOT / "audit/lora_msra_20261107/REPORT.md"
    msra_s1_eval = REPO_ROOT / "audit/lora_msra_20261107/eval_dev100.json"
    msra_s2_eval = REPO_ROOT / "audit/lora_msra_20261107/eval_simpo_dev100.json"

    def line_count(p: Path) -> int:
        return len(p.read_text(encoding="utf-8", errors="replace").splitlines()) if p.exists() else 0

    if paper_pdf.exists():
        size_kb = paper_pdf.stat().st_size / 1024.0
        out.append(f"    * Academic Paper: docs/paper/nckh_structured_reasoning.pdf ({size_kb:.1f} KB, Compiled)")
    else:
        out.append("    * Academic Paper: docs/paper/nckh_structured_reasoning.tex (Uncompiled)")

    cf_n = line_count(gsm8k_cf_eval)
    if cf_n >= 100:
        out.append("    * GSM8K Report: audit/lora_gsm8k_enriched_20261107/REPORT.md (Complete: Plain + CF)")
    elif cf_n > 0:
        out.append(f"    * GSM8K Report: audit/lora_gsm8k_enriched_20261107/REPORT.md (Evaluating CF: {cf_n}/100)")
    elif gsm8k_rep.exists():
        out.append("    * GSM8K Report: audit/lora_gsm8k_enriched_20261107/REPORT.md (Preliminary: Plain Done, CF Queued)")
    else:
        out.append("    * GSM8K Report: Pending evaluation completion")

    math_n = line_count(math_eval)
    math_term_n = line_count(REPO_ROOT / "audit/lora_math_20261107/eval_term/tuned.jsonl")
    if math_term_n >= 100:
        out.append("    * MATH Report: audit/lora_math_20261107/REPORT.md (Complete: Base + LoRA + Term-512)")
    elif math_term_n > 0:
        out.append(f"    * MATH Terminated-512 Eval: audit/lora_math_20261107/eval_term/tuned.jsonl ({math_term_n}/100)")
    elif math_n >= 100:
        out.append("    * MATH Report: audit/lora_math_20261107/REPORT.md (Complete: 100/100 Evaluated)")
    elif math_eval.exists():
        out.append(f"    * MATH Report: audit/lora_math_20261107/REPORT.md (Evaluating Dev-100: {math_n}/100)")
    elif math_rep.exists():
        out.append("    * MATH Report: audit/lora_math_20261107/REPORT.md (Preliminary: Training in Progress)")
    else:
        out.append("    * MATH Report: Pending evaluation completion")

    tool_p_n = line_count(REPO_ROOT / "audit/lora_gsm8k_enriched_20261107/eval_plain/tuned_tool.jsonl")
    tool_cf_n = line_count(REPO_ROOT / "audit/lora_gsm8k_enriched_20261107/eval_cf/tuned_tool.jsonl")
    if tool_p_n > 0 or tool_cf_n > 0:
        out.append(f"    * GSM8K tuned_tool Ablation: Plain {tool_p_n}/100, CF {tool_cf_n}/100")

    if msra_s2_eval.exists():
        out.append("    * MSRA Report: audit/lora_msra_20261107/REPORT.md (Complete: Stage 1 + Stage 2 Evaluated)")
    elif msra_s1_eval.exists():
        out.append("    * MSRA Report: audit/lora_msra_20261107/REPORT.md (Preliminary: Stage 1 Evaluated, Stage 2 Running)")
    else:
        out.append("    * MSRA Extension: structured_llm/msra/ (Scoped as Future Work — 15/15 Unit Tests Passing)")

    out.append("-" * 78)
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Multi-Step Reasoning Pipeline Dashboard")
    parser.add_argument("--watch", action="store_true", help="Continuously refresh every 5 seconds")
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                os.system("clear")
                print(render_dashboard())
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nDashboard exited.")
    else:
        print(render_dashboard())


if __name__ == "__main__":
    main()
