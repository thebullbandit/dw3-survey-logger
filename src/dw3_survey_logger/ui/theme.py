"""
UI Theme — colour palette and font definitions.
"""

import logging
import tkinter as tk
import tkinter.font as tkfont
from typing import Dict, Any

logger = logging.getLogger("dw3.ui.theme")


class UITheme:
    """Centralised colour and font configuration."""

    @staticmethod
    def setup_colors(config: Dict[str, Any]) -> Dict[str, str]:
        """Return a colours dict derived from *config* with safe defaults."""
        return {
            "BG": config.get("BG", "#0a0a0f"),
            "BG_PANEL": config.get("BG_PANEL", "#12121a"),
            "BG_FIELD": config.get("BG_FIELD", "#1a1a28"),
            "TEXT": config.get("TEXT", "#e0e0ff"),
            "MUTED": config.get("MUTED", "#6a6a8a"),
            "TEXT_DIM": config.get("TEXT_DIM", "#b8b8d8"),
            "BORDER_OUTER": config.get("BORDER_OUTER", "#2a2a3f"),
            "BORDER_INNER": config.get("BORDER_INNER", "#1f1f2f"),
            "ORANGE": config.get("ORANGE", "#ff8833"),
            "ORANGE_DIM": config.get("ORANGE_DIM", "#cc6622"),
            "GREEN": config.get("GREEN", "#44ff88"),
            "RED": config.get("RED", "#ff4444"),
            "LED_ACTIVE": config.get("LED_ACTIVE", "#00ff88"),
            "LED_IDLE": config.get("LED_IDLE", "#888888"),
        }

    @staticmethod
    def setup_fonts(root: tk.Tk) -> Dict[str, tuple]:
        """Return a fonts dict.  Must be called after Tk() exists."""
        try:
            fam = set(tkfont.families(root))
        except Exception as e:
            logger.debug("Failed to enumerate font families: %s", e)
            fam = set()

        def _pick(*names: str, fallback: str = "Segoe UI") -> str:
            for n in names:
                if n in fam:
                    return n
            return fallback

        title_family = _pick("Bahnschrift", "Segoe UI Variable Display", "Segoe UI", "Arial")

        return {
            "TITLE": (title_family, 16, "bold"),
            "SECTION": ("Segoe UI", 10, "bold"),
            "UI": ("Segoe UI", 9),
            "UI_BOLD": ("Segoe UI", 9, "bold"),
            "UI_SMALL": ("Segoe UI", 8),
            "UI_SMALL_BOLD": ("Segoe UI", 8, "bold"),
            "MONO": ("Consolas", 9),
            "MONO_BOLD": ("Consolas", 9, "bold"),
            "MONO_SMALL": ("Consolas", 8),
        }
