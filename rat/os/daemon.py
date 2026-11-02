"""
rat.os.daemon — macOS LaunchAgent Daemon & Persistent Background Service Manager.
Manages system-level daemon execution, automatic startup on user login, and FSEvents background indexing.
"""

from __future__ import annotations

import logging
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("rat.os.daemon")

LAUNCH_AGENT_LABEL = "com.antigravity.rat.daemon"
LAUNCH_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENT_PLIST = LAUNCH_AGENT_DIR / f"{LAUNCH_AGENT_LABEL}.plist"


def generate_plist_dict() -> Dict[str, Any]:
    """Generate macOS launchd plist dictionary."""
    log_dir = Path.home() / ".rat" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if getattr(sys, "frozen", False):
        # When running inside standalone rat.app bundle
        program_args = [sys.executable, "--daemon"]
    else:
        python_bin = sys.executable
        repo_main = str(Path(__file__).resolve().parent.parent.parent / "main.py")
        program_args = [python_bin, repo_main, "--daemon"]

    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_dir / "daemon_stdout.log"),
        "StandardErrorPath": str(log_dir / "daemon_stderr.log"),
        "ProcessType": "Interactive",
    }


def install_launch_agent() -> bool:
    """Install and load macOS LaunchAgent for persistent background execution."""
    try:
        LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
        plist_data = generate_plist_dict()

        with open(LAUNCH_AGENT_PLIST, "wb") as f:
            plistlib.dump(plist_data, f)

        # Unload previous instance if present
        subprocess.run(["launchctl", "unload", str(LAUNCH_AGENT_PLIST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Load new plist
        subprocess.run(["launchctl", "load", "-w", str(LAUNCH_AGENT_PLIST)], check=True)

        logger.info(f"LaunchAgent installed successfully: {LAUNCH_AGENT_PLIST}")
        return True
    except Exception as e:
        logger.error(f"Failed to install LaunchAgent: {e}")
        return False


def uninstall_launch_agent() -> bool:
    """Unload and remove macOS LaunchAgent."""
    try:
        if LAUNCH_AGENT_PLIST.exists():
            subprocess.run(["launchctl", "unload", str(LAUNCH_AGENT_PLIST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            LAUNCH_AGENT_PLIST.unlink()
            logger.info("LaunchAgent uninstalled successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to uninstall LaunchAgent: {e}")
        return False


def is_launch_agent_installed() -> bool:
    """Check if LaunchAgent is installed."""
    return LAUNCH_AGENT_PLIST.exists()


def set_launch_at_login(enable: bool) -> bool:
    """Toggle Launch at Login state and sync configuration."""
    from rat.config import config
    if enable:
        ok = install_launch_agent()
    else:
        ok = uninstall_launch_agent()
    if ok:
        config.launch_at_login = enable
        config.save()
    return ok
