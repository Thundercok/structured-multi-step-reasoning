"""Small presentation preference; it never changes model or execution behavior."""
from __future__ import annotations

import os


def debug_ui_enabled() -> bool:
    """Keep technical controls available for development, outside the primary path."""
    return os.environ.get("RAT_DEBUG_UI", "").strip().lower() in {"1", "true", "yes"}
