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
# 
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import re


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


# ============================================================================
# HOTKEY PARSING UTILITIES
# ============================================================================
# Users think in labels like: "Ctrl+Alt+O" or "Ctrl+Shift+F1".
# We convert that into:
#   - pynput GlobalHotKeys string: "<ctrl>+<alt>+o"
#   - Tk bind sequences: ["<Control-Alt-o>", "<Control-Alt-O>"]
#
# Supported:
#   Modifiers: Ctrl/Control, Alt, Shift
#   Keys: A-Z, 0-9, F1..F12
#
# Notes:
#   - Tk's Alt bindings can be inconsistent depending on platform/WM.
#   - If global hotkeys are unavailable, we still bind in-app (fallback).

from typing import List, Tuple

_MOD_SYNONYMS = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
}

_TK_MOD = {
    "ctrl": "Control",
    "alt": "Alt",
    "shift": "Shift",
}

_PYNPUT_MOD = {
    "ctrl": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
}

def parse_hotkey_label(label: str) -> Tuple[str, List[str], str]:
    """Parse a human hotkey label into (pynput_str, tk_sequences, normalized_label).

    Examples:
        "Ctrl+Alt+O" -> ("<ctrl>+<alt>+o", ["<Control-Alt-o>", "<Control-Alt-O>"], "Ctrl+Alt+O")
        "ctrl + shift + f2" -> ("<ctrl>+<shift>+<f2>", ["<Control-Shift-F2>"], "Ctrl+Shift+F2")

    Raises:
        ValueError: if the label cannot be parsed.
    """
    if not label or not str(label).strip():
        raise ValueError("Hotkey is empty")

    raw = str(label).strip()

    # Split on + or whitespace-around-plus
    parts = [p.strip() for p in re.split(r"\s*\+\s*", raw) if p.strip()]
    if len(parts) < 2:
        raise ValueError("Hotkey must include at least one modifier and a key (e.g., Ctrl+O)")

    mods = []
    key_token = parts[-1].strip().lower()
    for p in parts[:-1]:
        tok = p.strip().lower()
        if tok in _MOD_SYNONYMS:
            m = _MOD_SYNONYMS[tok]
            if m not in mods:
                mods.append(m)
        else:
            raise ValueError(f"Unknown modifier: '{p}'")

    if not mods:
        raise ValueError("Hotkey must include at least one modifier (Ctrl, Alt, Shift)")

    # Key: letter/digit or F1..F12
    tk_key = None
    pynput_key = None
    norm_key = None

    if re.fullmatch(r"f(\d{1,2})", key_token):
        n = int(re.fullmatch(r"f(\d{1,2})", key_token).group(1))
        if n < 1 or n > 12:
            raise ValueError("Only F1..F12 are supported")
        tk_key = f"F{n}"
        pynput_key = f"<f{n}>"
        norm_key = f"F{n}"
        tk_sequences = [f"<{'-'.join(_TK_MOD[m] for m in mods)}-{tk_key}>"]
    elif re.fullmatch(r"[a-z0-9]", key_token):
        ch = key_token.lower()
        tk_key = ch
        pynput_key = ch
        norm_key = ch.upper() if len(ch)==1 and ch.isalpha() else ch
        tk_mods = "-".join(_TK_MOD[m] for m in mods)
        tk_sequences = [f"<{tk_mods}-{ch}>"]
        # Also bind uppercase variant for convenience.
        if ch.isalpha():
            tk_sequences.append(f"<{tk_mods}-{ch.upper()}>")
    else:
        raise ValueError("Key must be a letter (A-Z), digit (0-9), or F1..F12")

    # Pynput string
    pynput_mods = "+".join(_PYNPUT_MOD[m] for m in mods)
    pynput_str = f"{pynput_mods}+{pynput_key}"

    # Normalized label (Ctrl+Alt+O)
    order = ["ctrl", "alt", "shift"]
    nice_mods = []
    for m in order:
        if m in mods:
            if m == "ctrl":
                nice_mods.append("Ctrl")
            elif m == "alt":
                nice_mods.append("Alt")
            elif m == "shift":
                nice_mods.append("Shift")
    normalized_label = "+".join(nice_mods + [norm_key])

    return pynput_str, tk_sequences, normalized_label
