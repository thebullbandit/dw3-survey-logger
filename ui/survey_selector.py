"""
Survey Selector Dialog - Choose survey type before observation
==============================================================

Modal dialog that appears when the observer hotkey is pressed,
allowing the user to select which type of survey to perform.
"""

import tkinter as tk
from pathlib import Path
from typing import Optional, Dict, Any

from observer_models import SurveyType


class SurveySelector:
    """
    Modal dialog for selecting survey type before observation.

    Shows three large buttons with descriptions:
    - Regular Density Scan (21 samples, 50 LY spacing)
    - Logarithmic Density Scan (24 samples, variable spacing)
    - Boxel Size Survey (single entry)

    Usage:
        selector = SurveySelector(root, colors)
        survey_type = selector.show()
        if survey_type is not None:
            # User selected a survey type
            ...
    """

    # Survey type definitions with display info
    SURVEY_INFO = {
        SurveyType.REGULAR_DENSITY: {
            "title": "Regular Density Scan",
            "samples": "21 samples",
            "description": "Standard survey with 50 LY Z-bin increments\nfrom 0 to 1000 LY",
            "color": "#4488ff",  # Blue
        },
        SurveyType.LOGARITHMIC_DENSITY: {
            "title": "Logarithmic Density Scan",
            "samples": "24 samples",
            "description": "Variable increments: 50 LY far from plane,\n20 LY mid-range, 10 LY near galactic plane",
            "color": "#aa66ff",  # Purple
        },
        SurveyType.BOXEL_SIZE: {
            "title": "Boxel Size Survey",
            "samples": "1 entry",
            "description": "Record the highest-numbered system\nin the current boxel",
            "color": "#44cc88",  # Green
        },
    }

    def __init__(self, parent: tk.Tk, colors: Optional[Dict[str, str]] = None):
        """
        Initialize the survey selector.

        Args:
            parent: Parent Tk window
            colors: Optional color dictionary (uses defaults if not provided)
        """
        self.parent = parent
        self.colors = colors or self._default_colors()
        self.result: Optional[SurveyType] = None
        self.window: Optional[tk.Toplevel] = None

    @staticmethod
    def _default_colors() -> Dict[str, str]:
        """Default dark theme colors matching the app."""
        return {
            "BG": "#0a0a0f",
            "BG_PANEL": "#12121a",
            "BG_FIELD": "#1a1a28",
            "TEXT": "#e0e0ff",
            "MUTED": "#6a6a8a",
            "BORDER_OUTER": "#2a2a3f",
            "ORANGE": "#ff8833",
        }

    def show(self) -> Optional[SurveyType]:
        """
        Show the survey selector dialog and wait for user selection.

        Returns:
            Selected SurveyType, or None if cancelled
        """
        self.result = None

        # Create modal window
        self.window = tk.Toplevel(self.parent)
        self.window.title("Select Survey Type")
        self.window.configure(bg=self.colors["BG"])
        self.window.transient(self.parent)
        self.window.grab_set()

        # Apply app icon to the window
        try:
            # Try multiple possible icon locations
            icon_paths = [
                Path(__file__).parent.parent / "assets" / "earth2.ico",
                Path("assets") / "earth2.ico",
                Path(__file__).parent.parent / "earth2.ico",
            ]
            for icon_path in icon_paths:
                if icon_path.exists():
                    self.window.iconbitmap(str(icon_path))
                    break
        except Exception:
            pass  # Icon is cosmetic, don't fail if unavailable

        # Build UI
        self._build_ui()

        # Position window
        self._center_window()

        # Bind escape to cancel
        self.window.bind("<Escape>", lambda e: self._on_cancel())

        # Bind keyboard shortcuts (1, 2, 3)
        self.window.bind("1", lambda e: self._on_select(SurveyType.REGULAR_DENSITY))
        self.window.bind("2", lambda e: self._on_select(SurveyType.LOGARITHMIC_DENSITY))
        self.window.bind("3", lambda e: self._on_select(SurveyType.BOXEL_SIZE))

        # Focus the window
        self.window.focus_force()

        # Wait for window to close
        self.parent.wait_window(self.window)

        return self.result

    def _build_ui(self):
        """Build the dialog UI."""
        window = self.window
        colors = self.colors

        # Main container with padding
        main_frame = tk.Frame(window, bg=colors["BG"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(
            main_frame,
            text="Select Survey Type",
            font=("Segoe UI", 14, "bold"),
            fg=colors["ORANGE"],
            bg=colors["BG"]
        )
        title_label.pack(pady=(0, 6))

        # Subtitle with keyboard hint
        hint_label = tk.Label(
            main_frame,
            text="Press 1, 2, or 3 to quick-select  |  ESC to cancel",
            font=("Consolas", 9),
            fg=colors["MUTED"],
            bg=colors["BG"]
        )
        hint_label.pack(pady=(0, 16))

        # Survey buttons
        survey_types = [
            SurveyType.REGULAR_DENSITY,
            SurveyType.LOGARITHMIC_DENSITY,
            SurveyType.BOXEL_SIZE,
        ]

        for idx, survey_type in enumerate(survey_types, start=1):
            self._create_survey_button(main_frame, survey_type, idx)

    def _create_survey_button(self, parent: tk.Frame, survey_type: SurveyType, number: int):
        """Create a large button for a survey type."""
        colors = self.colors
        info = self.SURVEY_INFO[survey_type]

        # Button container (acts as the clickable area)
        btn_frame = tk.Frame(
            parent,
            bg=colors["BG_PANEL"],
            highlightbackground=colors["BORDER_OUTER"],
            highlightthickness=1,
            cursor="hand2"
        )
        btn_frame.pack(fill="x", pady=6)

        # Inner padding frame
        inner = tk.Frame(btn_frame, bg=colors["BG_PANEL"])
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # Top row: number badge, title, sample count
        top_row = tk.Frame(inner, bg=colors["BG_PANEL"])
        top_row.pack(fill="x")

        # Number badge
        badge = tk.Label(
            top_row,
            text=str(number),
            font=("Consolas", 11, "bold"),
            fg=colors["BG"],
            bg=info["color"],
            width=2,
            height=1
        )
        badge.pack(side="left", padx=(0, 10))

        # Title
        title = tk.Label(
            top_row,
            text=info["title"],
            font=("Segoe UI", 11, "bold"),
            fg=info["color"],
            bg=colors["BG_PANEL"]
        )
        title.pack(side="left")

        # Sample count (right side)
        samples = tk.Label(
            top_row,
            text=info["samples"],
            font=("Consolas", 10),
            fg=colors["MUTED"],
            bg=colors["BG_PANEL"]
        )
        samples.pack(side="right")

        # Description
        desc = tk.Label(
            inner,
            text=info["description"],
            font=("Consolas", 9),
            fg=colors["TEXT"],
            bg=colors["BG_PANEL"],
            justify="left",
            anchor="w"
        )
        desc.pack(fill="x", pady=(8, 0))

        # Bind click to all widgets in the button
        def on_click(e, st=survey_type):
            self._on_select(st)

        for widget in [btn_frame, inner, top_row, badge, title, samples, desc]:
            widget.bind("<Button-1>", on_click)

        # Hover effects
        def on_enter(e):
            btn_frame.configure(highlightbackground=info["color"])

        def on_leave(e):
            btn_frame.configure(highlightbackground=colors["BORDER_OUTER"])

        btn_frame.bind("<Enter>", on_enter)
        btn_frame.bind("<Leave>", on_leave)

    def _on_select(self, survey_type: SurveyType):
        """Handle survey type selection."""
        self.result = survey_type
        if self.window:
            self.window.destroy()

    def _on_cancel(self):
        """Handle cancel (ESC or close)."""
        self.result = None
        if self.window:
            self.window.destroy()

    def _center_window(self):
        """Center the dialog on the parent window."""
        window = self.window
        parent = self.parent

        # Update to get actual sizes
        window.update_idletasks()

        # Set size (420 height fits all 3 survey buttons)
        width = 420
        height = 420
        window.geometry(f"{width}x{height}")
        window.minsize(width, height)
        window.resizable(False, False)

        # Position relative to parent
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()

        x = px + (pw - width) // 2
        y = py + (ph - height) // 2

        # Ensure on screen
        x = max(0, x)
        y = max(0, y)

        window.geometry(f"{width}x{height}+{x}+{y}")
