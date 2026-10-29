#!/usr/bin/env python3
"""Export prepared RAT artwork with macOS sips/iconutil; never rebuild the app.

Artwork edits happen separately. This script only converts approved square PNG
masters to native icon resources and records their hashes for later integration.
"""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs/design/rat-app-icon-20261028/masters"
OUTPUT = ROOT / "rat/assets/app_icons"
VARIANTS = {
    "rat-default": "Paper pile (default)",
    "rat-lite": "Paper pile · lite",
    "rat-paper-stack": "Paper stack",
    "rat-classic": "Original alternative",
}
SIZES = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}
CHUNKS = dict(zip(SIZES, (
    b"icp4", b"ic11", b"icp5", b"ic12", b"ic07", b"ic13",
    b"ic08", b"ic14", b"ic09", b"ic10",
)))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_icns(iconset, destination):
    result = subprocess.run(
        ["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(destination)],
        capture_output=True, text=True)
    if result.returncode == 0:
        return "iconutil"
    # PNG-backed ICNS chunks preserve every already-exported size and alpha.
    # No illustration edits or resampling occur in this fallback container writer.
    chunks = []
    for name, kind in CHUNKS.items():
        payload = (iconset / name).read_bytes()
        chunks.append(kind + struct.pack(">I", len(payload) + 8) + payload)
    body = b"".join(chunks)
    destination.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)
    print("iconutil rejected the iconset; wrote PNG-backed ICNS container instead.")
    return "png-backed-icns"


def main():
    missing = [str(SOURCES / f"{key}.png") for key in VARIANTS
               if not (SOURCES / f"{key}.png").is_file()]
    if missing:
        raise SystemExit("Missing prepared masters:\n" + "\n".join(missing))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schema_version": 1,
        "default_full": "rat-default",
        "default_lite": "rat-lite",
        "runtime_switching_implemented": False,
        "packaging_integrated": False,
        "variants": [],
    }
    for key, label in VARIANTS.items():
        master = SOURCES / f"{key}.png"
        iconset = OUTPUT / f"{key}.iconset"
        iconset.mkdir(exist_ok=True)
        for name, size in SIZES.items():
            subprocess.run(["/usr/bin/sips", "-s", "format", "png", "-z",
                            str(size), str(size), str(master), "--out",
                            str(iconset / name)], check=True, capture_output=True)
        png = OUTPUT / f"{key}.png"
        png.write_bytes((iconset / "icon_512x512@2x.png").read_bytes())
        icns = OUTPUT / f"{key}.icns"
        compiler = compile_icns(iconset, icns)
        catalog["variants"].append({
            "id": key, "label": label,
            "edition": "lite" if key == "rat-lite" else "full",
            "png": png.name, "icns": icns.name, "iconset": iconset.name,
            "master": str(master.relative_to(ROOT)),
            "master_sha256": digest(master), "png_sha256": digest(png),
            "icns_sha256": digest(icns),
            "png_pixels": [1024, 1024],
            "icns_compiler": compiler,
        })
        print(f"Exported {key}: PNG + 10 iconset slots + ICNS")
    (OUTPUT / "manifest.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
