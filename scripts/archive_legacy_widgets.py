import hashlib
import os
from pathlib import Path
import shutil

src_dir = Path("rat/ui")
archive_dir = Path("audit/ui_widgets_retirement_20261025/legacy_widgets")
archive_dir.mkdir(parents=True, exist_ok=True)

retired_files = [
    "omnibar.py",
    "workbench_scene.py",
    "schedule_window.py",
    "workbench.py",
    "claude_widget.py",
    "chat_stream.py",
    "spotlight_window.py",
    "finder_window.py",
    "preview_panel.py",
    "turn_notes_preview.py",
    "turn_notes.py",
    "natal_chart.py",
    "view_renderer.py",
    "naming_dialog.py",
    "settings_dialog.py",
    "onboarding_dialog.py",
    "work_context.py",
    "compact_cot.py",
    "surface_layout.py",
    "assistant_presenter.py",
    "action_menu.py",
    "compact_results.py",
    "live_companion.py",
    "execution_flow.py",
    "apple_item_delegate.py",
    "artifact_resources.py",
    "feedback.py",
]

manifest = []
total_lines = 0

for f in retired_files:
    src_path = src_dir / f
    dst_path = archive_dir / f
    if src_path.exists():
        shutil.copy2(src_path, dst_path)
        data = src_path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        lines = len(data.splitlines())
        total_lines += lines
        manifest.append(f"- `{f}`: {lines} lines, SHA256: `{sha}`")

readme = f"""# Audit: Retirement of Legacy QtWidgets Monolith

**Date:** 2026-10-25
**Scope:** Complete transition of RAT UI to QtQuick / QML.
**Retired Files:** {len(manifest)} files, **{total_lines} lines of code**.

## Rationale
To support the heavy ML reasoning core (MLX, Ollama, Qwen, PyTorch) with minimal overhead, the CPU-bound QtWidgets architecture (with software rasterization and heavy pixmap caching) has been completely retired in favor of the hardware-accelerated **QtQuick Scenegraph (Apple Metal RHI)**.

## Archived Manifest
""" + "\n".join(manifest) + """

## Recovery
To restore any of these legacy files for historical inspection or reference:
```bash
cp audit/ui_widgets_retirement_20261025/legacy_widgets/<filename> rat/ui/
```
"""

(archive_dir.parent / "README.md").write_text(readme)
print(f"Archived {len(manifest)} files ({total_lines} lines) successfully.")
