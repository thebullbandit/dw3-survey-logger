"""Global hotkey support with graceful fallback.

Tkinter cannot register system-wide hotkeys by itself. This module tries to
register a *global* hotkey using `pynput` (works on Windows and Linux X11).

If global registration fails (missing dependency, Wayland restrictions, etc.),
the caller should fall back to an in-app Tk bind.

Design goals:
  - Never crash the app if global hotkeys aren't available.
  - Keep a tiny API surface.
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   hotkey_manager.py
#
# Connected modules (direct imports):
#   (none)
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple


@dataclass
# ============================================================================
# CLASSES
# ============================================================================

class HotkeyStatus:
    ok: bool
    mode: str  # "global" or "fallback"
    hotkey_label: str
    error: Optional[str] = None


class GlobalHotkey:
    """Register/unregister a single global hotkey using pynput."""

    def __init__(self):
        self._listener = None
        self._registered: Optional[Tuple[str, Callable[[], None]]] = None

    @staticmethod
    def _ensure_pynput():
        try:
            from pynput import keyboard  # type: ignore
        except Exception as e:  # ImportError + platform errors
            raise RuntimeError(f"pynput not available: {e}")
        return keyboard

    def register(self, hotkey_pynput: str, callback: Callable[[], None]) -> None:
        """Register the hotkey.

        Args:
            hotkey_pynput: pynput GlobalHotKeys string, e.g. '<ctrl>+<shift>+o'
            callback: function to call when triggered
        """
        keyboard = self._ensure_pynput()

        # Stop any previous listener
        self.unregister()

        try:
            self._listener = keyboard.GlobalHotKeys({hotkey_pynput: callback})
            self._listener.start()
            self._registered = (hotkey_pynput, callback)
        except Exception as e:
            self._listener = None
            self._registered = None
            raise RuntimeError(f"failed to register global hotkey: {e}")

    def unregister(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
# ============================================================================
# FUNCTIONS
# ============================================================================

        self._listener = None
        self._registered = None


def try_register_global_hotkey(
    callback: Callable[[], None],
    *,
    # Default chosen to avoid NVIDIA overlay (Ctrl+Shift+O) and similar common conflicts.
    hotkey_pynput: str = "<ctrl>+<alt>+o",
    hotkey_label: str = "Ctrl+Alt+O",
) -> Tuple[Optional[GlobalHotkey], HotkeyStatus]:
    """Try to register a global hotkey. Returns (handle, status).

    If it fails, handle will be None and status.ok will be False.
    """
    handle = GlobalHotkey()
    try:
        handle.register(hotkey_pynput, callback)
        return handle, HotkeyStatus(ok=True, mode="global", hotkey_label=hotkey_label)
    except Exception as e:
        try:
            handle.unregister()
        except Exception:
            pass
        return None, HotkeyStatus(
            ok=False,
            mode="fallback",
            hotkey_label=hotkey_label,
            error=str(e),
        )
