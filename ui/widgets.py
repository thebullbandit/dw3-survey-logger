"""
Reusable widget helpers — button styling, label/value pairs, section headers, LED indicators.
"""

import logging
import tkinter as tk
from typing import Dict

logger = logging.getLogger("dw3.ui.widgets")


def style_button(btn: tk.Widget, colors: Dict[str, str], fonts: Dict[str, tuple],
                 *, accent: bool = False, success: bool = False):
    """Apply a flat, HUD-friendly button style."""
    bg = colors["ORANGE"] if accent else (colors["GREEN"] if success else colors["BG_PANEL"])
    fg = "#000000" if (accent or success) else colors["TEXT"]

    cfg = {
        "font": fonts["UI"],
        "bg": bg,
        "fg": fg,
        "activebackground": bg,
        "activeforeground": fg,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 1,
        "highlightbackground": colors["BORDER_INNER"],
        "highlightcolor": colors["ORANGE_DIM"],
        "padx": 10,
        "pady": 3,
        "cursor": "hand2",
    }
    for k, v in cfg.items():
        try:
            btn.configure(**{k: v})
        except Exception as e:
            logger.debug("Button configure %s failed: %s", k, e)

    if not (accent or success):
        try:
            btn.bind("<Enter>", lambda _e: btn.configure(highlightbackground=colors["BORDER_OUTER"]))
            btn.bind("<Leave>", lambda _e: btn.configure(highlightbackground=colors["BORDER_INNER"]))
        except Exception as e:
            logger.debug("Button hover bind failed: %s", e)


def create_label_value_pair(parent: tk.Widget, label_text: str, colors: Dict[str, str],
                            fonts: Dict[str, tuple], **grid_kw) -> tk.Label:
    """Create a LABEL: VALUE pair and return the value label widget."""
    tk.Label(
        parent,
        text=label_text,
        font=fonts["MONO"],
        fg=colors["MUTED"],
        bg=colors["BG_PANEL"],
    ).grid(**grid_kw)
    return tk.Label(
        parent,
        text="-",
        font=fonts["MONO"],
        fg=colors["TEXT"],
        bg=colors["BG_PANEL"],
        anchor="w",
    )


def create_section_header(parent: tk.Widget, text: str, colors: Dict[str, str],
                          fonts: Dict[str, tuple]) -> tk.Label:
    """Create an orange section-header label."""
    lbl = tk.Label(
        parent,
        text=text,
        font=fonts["UI_SMALL_BOLD"],
        fg=colors["ORANGE"],
        bg=colors["BG_PANEL"],
    )
    return lbl


def create_led_indicator(parent: tk.Widget, colors: Dict[str, str]):
    """Create a small LED canvas dot.  Returns (canvas, oval_id)."""
    canvas = tk.Canvas(parent, width=20, height=20, bg=colors["BG_PANEL"], highlightthickness=0)
    dot = canvas.create_oval(4, 4, 16, 16, fill=colors["LED_IDLE"], outline="")
    return canvas, dot
