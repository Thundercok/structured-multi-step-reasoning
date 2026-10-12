#!/usr/bin/env python3
"""
scripts/generate_icon.py — Generate high-resolution Apple Retina .icns App Icon for rat.
"""

import os
import shutil
import subprocess
from PIL import Image, ImageDraw

def create_master_icon(size=1024) -> Image.Image:
    # High-resolution master canvas with alpha
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. macOS Squircle Background with Linear Gradient Simulation
    pad = int(size * 0.08)
    bbox = [pad, pad, size - pad, size - pad]
    corner_radius = int(size * 0.22)

    # Draw gradient rounded rect using vertical slices with alpha mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(bbox, radius=corner_radius, fill=255)

    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(size):
        ratio = y / size
        # Smooth interpolation: #0f172a (dark slate) -> #312e81 (indigo) -> #4f46e5 (vibrant violet)
        r = int(15 * (1 - ratio) + 79 * ratio)
        g = int(23 * (1 - ratio) + 70 * ratio)
        b = int(42 * (1 - ratio) + 229 * ratio)
        line_draw = ImageDraw.Draw(gradient)
        line_draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    img.paste(gradient, (0, 0), mask)

    # Subtle inner border for macOS Depth
    draw.rounded_rectangle(bbox, radius=corner_radius, outline=(255, 255, 255, 45), width=int(size * 0.008))

    # 2. Sleek Vector Radar / Neural Search Glyph
    cx, cy = size // 2, size // 2

    # Radar concentric ripples
    for radius, alpha, w in [
        (int(size * 0.28), 60, int(size * 0.012)),
        (int(size * 0.21), 110, int(size * 0.015)),
        (int(size * 0.14), 180, int(size * 0.020))
    ]:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=(99, 102, 241, alpha), width=w)

    # Center glowing Search Lens
    lens_r = int(size * 0.11)
    lens_cx = cx - int(size * 0.03)
    lens_cy = cy - int(size * 0.03)
    draw.ellipse(
        [lens_cx - lens_r, lens_cy - lens_r, lens_cx + lens_r, lens_cy + lens_r],
        fill=(255, 255, 255, 235),
        outline=(129, 140, 248, 255),
        width=int(size * 0.018)
    )

    # Inner lens gradient dot
    dot_r = int(size * 0.04)
    draw.ellipse(
        [lens_cx - dot_r, lens_cy - dot_r, lens_cx + dot_r, lens_cy + dot_r],
        fill=(79, 70, 229, 255)
    )

    # Lens Handle angled at 45 degrees
    handle_start_x = lens_cx + int(lens_r * 0.7)
    handle_start_y = lens_cy + int(lens_r * 0.7)
    handle_end_x = handle_start_x + int(size * 0.15)
    handle_end_y = handle_start_y + int(size * 0.15)
    draw.line(
        [(handle_start_x, handle_start_y), (handle_end_x, handle_end_y)],
        fill=(255, 255, 255, 240),
        width=int(size * 0.035)
    )

    # Star / Sparkle highlight on top right
    spark_cx = cx + int(size * 0.18)
    spark_cy = cy - int(size * 0.18)
    sr = int(size * 0.035)
    draw.line([(spark_cx - sr, spark_cy), (spark_cx + sr, spark_cy)], fill=(255, 255, 255, 230), width=int(size * 0.01))
    draw.line([(spark_cx, spark_cy - sr), (spark_cx, spark_cy + sr)], fill=(255, 255, 255, 230), width=int(size * 0.01))

    return img

def build_icns(output_path="rat.icns"):
    iconset_dir = "rat.iconset"
    if os.path.exists(iconset_dir):
        shutil.rmtree(iconset_dir)
    os.makedirs(iconset_dir, exist_ok=True)

    master = create_master_icon(1024)

    # macOS icon sizes mapping
    sizes = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for filename, s in sizes:
        resized = master.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(os.path.join(iconset_dir, filename))

    print(f"Generated all icons in {iconset_dir}/")

    # Run Apple native iconutil
    subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", output_path], check=True)
    shutil.rmtree(iconset_dir)
    print(f"✅ Successfully compiled Apple Retina Icon: {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == "__main__":
    build_icns("rat.icns")
