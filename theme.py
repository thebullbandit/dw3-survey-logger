"""UI theme constants.

This module intentionally contains only UI-related constants (colors, sizing defaults).
It should not read/write any user settings.

If you want to make theme configurable later, do it by overlaying user-provided values
on top of DEFAULT_COLORS in memory, not by mixing UI constants into settings storage.
"""

from __future__ import annotations

from typing import Dict

# Default color scheme (matches dependency_injection.UIConfig defaults)
DEFAULT_COLORS: Dict[str, str] = {
    "BG": "#0a0a0f",
    "BG_PANEL": "#12121a",
    "BG_FIELD": "#1a1a28",
    "TEXT": "#e0e0ff",
    "MUTED": "#6a6a8a",
    "BORDER_OUTER": "#2a2a3f",
    "BORDER_INNER": "#1f1f2f",
    "ORANGE": "#ff8833",
    "ORANGE_DIM": "#cc6622",
    "GREEN": "#44ff88",
    "RED": "#ff4444",
    "LED_ACTIVE": "#00ff88",
    "LED_IDLE": "#888888",
}

def resolve_color(config: dict, key: str) -> str:
    """Resolve a color key from an in-memory config overlaying DEFAULT_COLORS.

    If a caller passes a runtime config dict that contains a color override, we honor it,
    otherwise we return the theme default.
    """
    val = None
    try:
        val = config.get(key)
    except Exception:
        val = None
    return str(val) if val else DEFAULT_COLORS[key]
