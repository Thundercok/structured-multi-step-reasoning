#!/usr/bin/env python3
"""UI Screenshot and Screen Recording Toolkit for macOS & RAT UI testing.

Usage:
  # 1. Record live desktop video for N seconds (or until Ctrl+C):
  python scripts/record_ui.py --record 10 --output test.mov

  # 2. Render all screenshots in a session folder to MP4 and GIF:
  python scripts/record_ui.py --render work/rat_ui_iteration_sessions_20261024/13-chat-apps/screenshots/

  # 3. Take an instant desktop screenshot:
  python scripts/record_ui.py --screenshot test.png
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg") or ("/opt/homebrew/bin/ffmpeg" if Path("/opt/homebrew/bin/ffmpeg").exists() else None)


def take_screenshot(output_path: Path):
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["/usr/sbin/screencapture", "-x", str(output_path)]
    subprocess.run(cmd, check=True)
    print(f"Screenshot saved: {output_path}")


def record_desktop(duration: float, output_path: Path):
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["/usr/sbin/screencapture", "-v", "-k", "-C"]
    if duration > 0:
        cmd.extend(["-V", str(int(duration))])
    cmd.append(str(output_path))
    dur_str = f"{duration}s" if duration > 0 else "until Ctrl+C"
    print(f"Recording desktop to {output_path} ({dur_str})...")
    proc = subprocess.Popen(cmd)
    try:
        proc.wait(timeout=duration + 5 if duration > 0 else None)
    except KeyboardInterrupt:
        print("Stopping recording...")
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=5)
    print(f"Video saved: {output_path}")


def render_screenshots(screenshots_dir: Path, output_base: Path, fps: int = 1) -> bool:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("Error: ffmpeg not found.", file=sys.stderr)
        return False
    screenshots_dir = screenshots_dir.expanduser().resolve()
    pngs = sorted(screenshots_dir.glob("*.png"))
    if not pngs:
        print(f"No PNG files found in {screenshots_dir}", file=sys.stderr)
        return False

    out_mp4 = output_base.with_suffix(".mp4")
    out_gif = output_base.with_suffix(".gif")

    # Render MP4 with canvas padding for mixed dimensions
    cmd_mp4 = [
        ffmpeg, "-y", "-framerate", str(fps),
        "-pattern_type", "glob", "-i", str(screenshots_dir / "*.png"),
        "-vf", "scale=560:600:force_original_aspect_ratio=decrease,pad=560:600:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4)
    ]
    subprocess.run(cmd_mp4, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Walkthrough MP4 rendered: {out_mp4}")

    # Render GIF
    cmd_gif = [
        ffmpeg, "-y", "-framerate", str(fps),
        "-pattern_type", "glob", "-i", str(screenshots_dir / "*.png"),
        "-vf", "scale=520:560:force_original_aspect_ratio=decrease,pad=520:560:(ow-iw)/2:(oh-ih)/2:color=black,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        str(out_gif)
    ]
    subprocess.run(cmd_gif, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Walkthrough GIF rendered: {out_gif}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--screenshot", type=Path, metavar="OUTPUT_PNG",
                       help="Take an instant desktop screenshot")
    group.add_argument("--record", type=float, nargs="?", const=10.0, default=None, metavar="SECONDS",
                       help="Record desktop video via screencapture (default 10s; 0 for until Ctrl+C)")
    group.add_argument("--render", type=Path, metavar="SCREENSHOTS_DIR",
                       help="Compile all PNGs in a directory into MP4 and GIF walkthroughs")

    parser.add_argument("--output", type=Path, default=None,
                        help="Output path for recorded video or rendered walkthrough (default auto-named)")
    parser.add_argument("--fps", type=int, default=1,
                        help="Framerate for rendered walkthrough (default 1 fps)")

    args = parser.parse_args()

    if args.screenshot:
        take_screenshot(args.screenshot)
    elif args.record is not None:
        out = args.output or Path(f"work/recording_{int(time.time())}.mov")
        record_desktop(args.record, out)
    elif args.render:
        out_base = args.output or (args.render.parent / "walkthrough")
        render_screenshots(args.render, out_base, fps=args.fps)


if __name__ == "__main__":
    main()
