"""Window focus helpers.

Why this exists
--------------
Tkinter can usually raise its windows with ``lift()`` and ``focus_force()``.
However, fullscreen / borderless games often prevent normal desktop apps from
stealing focus.

This module provides a *best effort* ``bring_to_front`` helper:

1) Always do safe Tk calls (deiconify, lift, temporary topmost toggle).
2) On Windows, if ``pywin32`` is installed, also call Win32 APIs to restore and
   foreground the window.

It will never crash the app if pywin32 is missing.
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   window_focus.py
#
# Connected modules (direct imports):
#   (none)
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

from __future__ import annotations

import sys
from typing import Any


# ============================================================================
# FUNCTIONS
# ============================================================================

def bring_to_front(tk_window: Any) -> None:
    """Best-effort attempt to bring a Tk/Toplevel window in front.

    Args:
        tk_window: a Tkinter window (Tk or Toplevel)
    """

    # --- Tkinter-level nudges (cross-platform) ---
    try:
        tk_window.deiconify()
    except Exception:
        pass

    try:
        tk_window.lift()
    except Exception:
        pass

    # Temporary topmost toggle is a common trick to force a z-order refresh.
    try:
        tk_window.attributes("-topmost", True)
        tk_window.update_idletasks()
        tk_window.update()
        tk_window.attributes("-topmost", False)
    except Exception:
        pass

    try:
        tk_window.focus_force()
    except Exception:
        pass

    # --- Windows Win32 API (optional) ---
    if not sys.platform.startswith("win"):
        return

    try:
        import win32con  # type: ignore
        import win32gui  # type: ignore

        hwnd = int(tk_window.winfo_id())

        # Restore if minimized.
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass

        # Nudge z-order: TOPMOST then NOTOPMOST.
        flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        try:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
        except Exception:
            pass

        # Foreground request (may still be blocked by the OS/game policy).
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    except Exception:
        # pywin32 not installed or not functional: silently ignore.
        return
