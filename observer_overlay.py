"""
Observer Overlay - UI for CMDR observation notes
=================================================

A popup window where CMDRs can record observation data that
supplements journal-derived data (slice status, confidence,
sampling method, flags, notes).

Matches the existing app styling (dark theme, Consolas font).
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   observer_overlay.py
#
# Connected modules (direct imports):
#   journal_state_manager, observer_models
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import tkinter as tk
from tkinter import ttk, messagebox
import os
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass

from observer_models import (
    ObserverNote,
    SliceStatus,
    SamplingMethod,
    ObservationFlags,
    create_observation_from_context,
)
from journal_state_manager import CurrentContext


# ============================================================================
# CLASSES
# ============================================================================

class Tooltip:
    def __init__(self, widget, text, delay_ms=1200, wraplength=360):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength

        self._after_id = None
        self._tipwin = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")  # click hides

    def _on_enter(self, _event=None):
        self._schedule()

    def _on_motion(self, _event=None):
        # Hvis brugeren bevæger musen inde i widget, så “resetter” vi delay
        # så den ikke popper midt i bevægelse.
        self._unschedule()
        self._schedule()

    def _on_leave(self, _event=None):
        self._unschedule()
        self._hide()

    def _schedule(self):
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _unschedule(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tipwin is not None:
            return

        # placér tooltip nær musen
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 18

        tw = tk.Toplevel(self.widget)
        self._tipwin = tw
        tw.wm_overrideredirect(True)  # ingen window border
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        # Styling: brug din egen theme hvis du vil
        bg = "#1d1f27"
        fg = "#d7d7d7"
        border = "#6a6a6a"

        frame = tk.Frame(tw, bg=border, bd=1)
        frame.pack(fill="both", expand=True)

        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            wraplength=self.wraplength,
            bg=bg,
            fg=fg,
            padx=8,
            pady=6,
            font=("Consolas", 9),
        )
        label.pack(fill="both", expand=True)

        # set inner bg (border trick)
        frame.configure(bg=border)
        label.configure(bg=bg)

    def _hide(self):
        if self._tipwin is not None:
            try:
                self._tipwin.destroy()
            except Exception:
                pass
            self._tipwin = None


@dataclass
class OverlayColors:
    """Color scheme matching main app"""
    BG: str = "#0a0a0f"
    BG_PANEL: str = "#12121a"
    BG_FIELD: str = "#1a1a28"
    TEXT: str = "#e0e0ff"
    MUTED: str = "#6a6a8a"
    BORDER_OUTER: str = "#2a2a3f"
    BORDER_INNER: str = "#1f1f2f"
    ORANGE: str = "#ff8833"
    ORANGE_DIM: str = "#cc6622"
    GREEN: str = "#44ff88"
    RED: str = "#ff4444"

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'OverlayColors':
        """Create from config dict"""
        return cls(
            BG=config.get("BG", cls.BG),
            BG_PANEL=config.get("BG_PANEL", cls.BG_PANEL),
            BG_FIELD=config.get("BG_FIELD", cls.BG_FIELD),
            TEXT=config.get("TEXT", cls.TEXT),
            MUTED=config.get("MUTED", cls.MUTED),
            BORDER_OUTER=config.get("BORDER_OUTER", cls.BORDER_OUTER),
            BORDER_INNER=config.get("BORDER_INNER", cls.BORDER_INNER),
            ORANGE=config.get("ORANGE", cls.ORANGE),
            ORANGE_DIM=config.get("ORANGE_DIM", cls.ORANGE_DIM),
            GREEN=config.get("GREEN", cls.GREEN),
            RED=config.get("RED", cls.RED),
        )


class ObserverOverlay:
    """
    Overlay window for recording CMDR observations.

    Usage:
        overlay = ObserverOverlay(root, config, on_save_callback)
        overlay.show(context)  # Opens with pre-filled data from context
    """

    def __init__(
        self,
        parent: tk.Tk,
        config: Dict[str, Any],
        on_save: Optional[Callable[[ObserverNote], None]] = None,
        session_id: str = "",
        app_version: str = ""
    ):
        """
        Initialize overlay.

        Args:
            parent: Parent Tk window
            config: App config dict (for colors)
            on_save: Callback when observation is saved
            session_id: Current session ID
            app_version: App version string
        """
        self.parent = parent
        self.config = config
        self.on_save = on_save
        self.session_id = session_id
        self.app_version = app_version

        # Hotkey hint shown in the overlay (set by main.py)
        # Example: "Hotkey: Ctrl+Shift+O (global)" or "Hotkey: Ctrl+O (in-app)"
        self.hotkey_hint: str = ""

        # Colors
        self.colors = OverlayColors.from_config(config)

        # Window reference (created on show)
        self.window: Optional[tk.Toplevel] = None

        # Current context (set on show)
        self._context: Optional[CurrentContext] = None

        # Slice lock: keep the same z-bin for an IN_PROGRESS splice run
        # so system_index counts up across multiple saved systems.
        self._locked_z_bin: Optional[int] = None

        # Tkinter variables
        self._slice_status_var: Optional[tk.StringVar] = None
        self._confidence_var: Optional[tk.IntVar] = None
        self._method_var: Optional[tk.StringVar] = None
        self._system_count_var: Optional[tk.StringVar] = None
        self._corrected_n_var: Optional[tk.StringVar] = None
        self._max_distance_var: Optional[tk.StringVar] = None
        self._notes_widget: Optional[tk.Text] = None

        # Flag variables
        self._flag_vars: Dict[str, tk.BooleanVar] = {}

        # Tooltip references (kept to avoid GC in some Tk builds)
        self._tooltips = []

        # Section frames (for show/hide)
        self._details_frame: Optional[tk.Frame] = None
        self._density_frame: Optional[tk.Frame] = None

        # Header widgets
        self._lbl_hotkey: Optional[tk.Label] = None
        self._lbl_slice_lock: Optional[tk.Label] = None

    def show(self, context: Optional[CurrentContext] = None):
        """
        Show the overlay window.

        Args:
            context: Current CMDR context (for pre-filling fields)
        """
        self._context = context

        # If window exists and is open, just focus it
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        # Create new window
        self._create_window()
        self._build_ui()
        self._populate_from_context()

        # Center on parent
        self._center_on_parent()

        # Focus
        self.window.focus_force()

    def hide(self):
        """Hide/close the overlay"""
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None

    def is_visible(self) -> bool:
        """Check if overlay is currently visible"""
        return self.window is not None and self.window.winfo_exists()

    # =========================================================================
    # WINDOW CREATION
    # =========================================================================

    def _create_window(self):
        """Create the toplevel window"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Add Observation")
        self.window.configure(bg=self.colors.BG)
        self.window.resizable(True, True)

        # Match main window icon (Windows .ico)
        # Tk does not automatically inherit the root icon for Toplevel.
        self._load_icon_for_toplevel()

        # Set minimum size
        self.window.minsize(500, 400)

        # Keep it associated with the parent window, but DO NOT make it modal.
        # Modal (grab_set) can freeze the app if the game blocks the overlay from coming to front.
        self.window.transient(self.parent)

        # Handle close
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Bind Escape to cancel
        self.window.bind("<Escape>", lambda e: self._on_cancel())

        # Bind Ctrl+Enter to save
        self.window.bind("<Control-Return>", lambda e: self._on_save())

    def _load_icon_for_toplevel(self):
        """Apply the same icon as the main window to this Toplevel (best-effort)."""
        try:
            # Config follows the same convention as view.py
            icon_name = self.config.get("ICON_NAME") or self.config.get("icon_name") or "earth2.ico"
            asset_path = self.config.get("ASSET_PATH")

            icon_path = None
            if asset_path:
                # ASSET_PATH is typically a pathlib.Path
                try:
                    icon_path = asset_path / icon_name
                except Exception:
                    icon_path = os.path.join(str(asset_path), icon_name)

            if icon_path:
                # pathlib.Path support
                try:
                    if hasattr(icon_path, "exists") and icon_path.exists():
                        self.window.iconbitmap(str(icon_path))
                        return
                except Exception:
                    pass

                # fallback for string path
                try:
                    if isinstance(icon_path, str) and os.path.exists(icon_path):
                        self.window.iconbitmap(icon_path)
                        return
                except Exception:
                    pass
        except Exception:
            pass  # Icon is cosmetic; never break the overlay for it.

    def _center_on_parent(self):
        """Center window on parent"""
        self.window.update_idletasks()

        # Get parent position and size
        px = self.parent.winfo_x()
        py = self.parent.winfo_y()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()

        # Get window size
        ww = self.window.winfo_width()
        wh = self.window.winfo_height()

        # Calculate position
        x = px + (pw - ww) // 2
        y = py + (ph - wh) // 2

        self.window.geometry(f"+{x}+{y}")

    # =========================================================================
    # UI BUILDING
    # =========================================================================

    def _build_ui(self):
        """Build the complete UI"""
        # Initialize variables
        self._slice_status_var = tk.StringVar(value=SliceStatus.IN_PROGRESS.value)
        self._confidence_var = tk.IntVar(value=50)
        self._method_var = tk.StringVar(value=SamplingMethod.OTHER.value)
        self._system_count_var = tk.StringVar(value="")
        self._corrected_n_var = tk.StringVar(value="")
        self._max_distance_var = tk.StringVar(value="")

        # Auto-calculate corrected_n (N = system_count + 1)
        self._system_count_var.trace_add("write", self._update_corrected_n)
        # Initialize corrected_n in case system_count already has a value
        self._update_corrected_n()

        # Flag variables
        self._flag_vars = {
            "bias_risk": tk.BooleanVar(value=False),
            "low_coverage": tk.BooleanVar(value=False),
            "anomaly_suspected": tk.BooleanVar(value=False),
            "interrupted": tk.BooleanVar(value=False),
            "repeat_needed": tk.BooleanVar(value=False),
        }

        # Main container with padding
        main_frame = tk.Frame(self.window, bg=self.colors.BG)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Build sections
        self._build_header(main_frame)
        self._build_drift_section(main_frame)
        self._build_status_section(main_frame)
        self._build_details_section(main_frame)
        self._build_density_section(main_frame)
        self._build_flags_section(main_frame)
        self._build_notes_section(main_frame)
        self._build_footer(main_frame)

        # Initially hide details (shown when status != in_progress)
        self._update_section_visibility()

    def _build_header(self, parent: tk.Frame):
        """Build header with context info (read-only)"""
        header = tk.LabelFrame(
            parent,
            text="CONTEXT",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        header.pack(fill="x", pady=(0, 10))

        # Grid for context fields
        fields_frame = tk.Frame(header, bg=self.colors.BG_PANEL)
        fields_frame.pack(fill="x", padx=10, pady=8)

        # Row 1: System and Z-bin
        tk.Label(
            fields_frame,
            text="SYSTEM:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=0, column=0, sticky="e", padx=(0, 5), pady=2)

        self._lbl_system = tk.Label(
            fields_frame,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL
        )
        self._lbl_system.grid(row=0, column=1, sticky="w", padx=(0, 20), pady=2)

        tk.Label(
            fields_frame,
            text="Z-BIN:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=0, column=2, sticky="e", padx=(0, 5), pady=2)

        self._lbl_zbin = tk.Label(
            fields_frame,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL
        )
        self._lbl_zbin.grid(row=0, column=3, sticky="w", pady=2)

        # Row 2: Position
        tk.Label(
            fields_frame,
            text="POSITION:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=1, column=0, sticky="e", padx=(0, 5), pady=2)

        self._lbl_position = tk.Label(
            fields_frame,
            text="X: -  Y: -  Z: -",
            font=("Consolas", 9),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL
        )
        self._lbl_position.grid(row=1, column=1, columnspan=3, sticky="w", pady=2)

        # Row 3: Session
        tk.Label(
            fields_frame,
            text="SESSION:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=2, column=0, sticky="e", padx=(0, 5), pady=2)

        self._lbl_session = tk.Label(
            fields_frame,
            text="-",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        self._lbl_session.grid(row=2, column=1, columnspan=3, sticky="w", pady=2)

        # Row 4: Hotkey hint (optional)
        tk.Label(
            fields_frame,
            text="HOTKEY:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=3, column=0, sticky="e", padx=(0, 5), pady=2)

        self._lbl_hotkey = tk.Label(
            fields_frame,
            text=self.hotkey_hint or "-",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        self._lbl_hotkey.grid(row=3, column=1, columnspan=3, sticky="w", pady=2)

        # Row 5: Slice lock (helps explain splice counters)
        tk.Label(
            fields_frame,
            text="SLICE LOCK:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=4, column=0, sticky="e", padx=(0, 5), pady=2)

        self._lbl_slice_lock = tk.Label(
            fields_frame,
            text="-",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        self._lbl_slice_lock.grid(row=4, column=1, columnspan=3, sticky="w", pady=2)

    def _build_drift_section(self, parent: tk.Frame):
        """Build Drift Guardrail section (NavRoute guidance)."""
        drift_frame = tk.LabelFrame(
            parent,
            text="DRIFT GUARDRAIL",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        drift_frame.pack(fill="x", pady=(0, 10))

        hint = tk.Label(
            drift_frame,
            text="Shows how far your next plotted jumps drift sideways from the intended survey line.",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        hint.pack(anchor="w", padx=10, pady=(6, 2))

        self._lbl_drift_status = tk.Label(
            drift_frame,
            text="Status: -",
            font=("Consolas", 9, "bold"),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL
        )
        self._lbl_drift_status.pack(anchor="w", padx=10, pady=(0, 2))

        self._lbl_drift_meta = tk.Label(
            drift_frame,
            text="",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        self._lbl_drift_meta.pack(anchor="w", padx=10, pady=(0, 4))

        self._lbl_drift_lines = tk.Label(
            drift_frame,
            text="",
            font=("Consolas", 8),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL,
            justify="left",
            anchor="w"
        )
        self._lbl_drift_lines.pack(fill="x", padx=10, pady=(0, 8))

        self._drift_frame = drift_frame

    def _build_status_section(self, parent: tk.Frame):
        """Build slice status section (radio buttons)"""
        status_frame = tk.LabelFrame(
            parent,
            text="SLICE STATUS",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        status_frame.pack(fill="x", pady=(0, 10))

        # Radio buttons in a row
        radio_frame = tk.Frame(status_frame, bg=self.colors.BG_PANEL)
        radio_frame.pack(fill="x", padx=10, pady=8)

        tk.Label(
            status_frame,
            text="Mark whether this Z-slice is still being sampled, complete, partial or discarded.",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", padx=10, pady=(0, 6))

        statuses = [
            (SliceStatus.IN_PROGRESS, "In Progress"),
            (SliceStatus.COMPLETE, "Complete"),
            (SliceStatus.PARTIAL, "Partial"),
            (SliceStatus.DISCARD, "Discard"),
        ]

        for status, label in statuses:
            rb = tk.Radiobutton(
                radio_frame,
                text=label,
                variable=self._slice_status_var,
                value=status.value,
                font=("Consolas", 9),
                fg=self.colors.TEXT,
                bg=self.colors.BG_PANEL,
                selectcolor=self.colors.BG_FIELD,
                activebackground=self.colors.BG_PANEL,
                activeforeground=self.colors.ORANGE,
                command=self._update_section_visibility
            )
            rb.pack(side="left", padx=10)
            # Hover tooltip (DW3-friendly)
            tip = {
                "In Progress": "Still working this Z-slice. Keep sampling and come back to mark it done.",
                "Complete": "You’re happy with coverage for this slice. Mark it done and move on.",
                "Partial": "Some coverage, but not enough for a full tick. Still useful data.",
                "Discard": "Data is too messy or biased to trust. Please leave a quick note why."
            }.get(label, "")
            if tip:
                self._tooltips.append(Tooltip(rb, tip, delay_ms=1200))


    def _build_details_section(self, parent: tk.Frame):
        """Build details section (confidence, method) - shown when status != in_progress"""
        self._details_frame = tk.LabelFrame(
            parent,
            text="DETAILS",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        # Don't pack yet - controlled by _update_section_visibility

        inner = tk.Frame(self._details_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="x", padx=10, pady=8)

        # Confidence slider
        conf_frame = tk.Frame(inner, bg=self.colors.BG_PANEL)
        conf_frame.pack(fill="x", pady=(0, 8))

        tk.Label(
            inner,
            text="How confident you are this slice is representative (0–100%).",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            conf_frame,
            text="CONFIDENCE:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(side="left", padx=(0, 10))

        self._confidence_slider = tk.Scale(
            conf_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self._confidence_var,
            font=("Consolas", 8),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL,
            troughcolor=self.colors.BG_FIELD,
            highlightthickness=0,
            length=200
        )
        self._confidence_slider.pack(side="left", fill="x", expand=True)

        # Tooltip for confidence slider
        self._tooltips.append(Tooltip(
            self._confidence_slider,
            "Your gut-check for this slice: 0 = basically a guess, 100 = you feel it’s solid coverage.",
            delay_ms=1200
        ))

        self._lbl_confidence = tk.Label(
            conf_frame,
            text="50%",
            font=("Consolas", 9, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            width=5
        )
        self._lbl_confidence.pack(side="left", padx=(10, 0))

        # Update label on slider change
        self._confidence_var.trace_add("write", self._on_confidence_changed)

        # Sampling method dropdown
        method_frame = tk.Frame(inner, bg=self.colors.BG_PANEL)
        method_frame.pack(fill="x")

        tk.Label(
            inner,
            text="How sampling was done (random/grid/route/targeted/other).",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            method_frame,
            text="METHOD:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(side="left", padx=(0, 10))

        methods = [
            (SamplingMethod.RANDOM.value, "Random"),
            (SamplingMethod.GRID.value, "Grid"),
            (SamplingMethod.ROUTE_FOLLOW.value, "Route Follow"),
            (SamplingMethod.TARGETED.value, "Targeted"),
            (SamplingMethod.OTHER.value, "Other"),
        ]

        self._method_combo = ttk.Combobox(
            method_frame,
            textvariable=self._method_var,
            values=[m[1] for m in methods],
            state="readonly",
            font=("Consolas", 9),
            width=20
        )
        self._method_combo.pack(side="left")

        self._tooltips.append(Tooltip(
            self._method_combo,
            "How you sampled this slice. Random = wander, Grid = systematic passes, Route Follow = along your plotted hops, Targeted = chasing specific stars, Other = anything else.",
            delay_ms=1200
        ))

        # Map display names to values
        self._method_map = {m[1]: m[0] for m in methods}
        self._method_map_reverse = {m[0]: m[1] for m in methods}
        self._method_combo.set("Other")

    def _build_density_section(self, parent: tk.Frame):
        """Build density sampling section (system count, corrected n, max distance)"""
        self._density_frame = tk.LabelFrame(
            parent,
            text="DENSITY SAMPLING",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        # Always visible - these are the main data entry fields
        self._density_frame.pack(fill="x", pady=(0, 10))

        help_lbl = tk.Label(
            self._density_frame,
            text="Enter values from the Nav panel. Corrected n is filled automatically.",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        help_lbl.pack(anchor="w", padx=10, pady=(6, 0))

        inner = tk.Frame(self._density_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="x", padx=10, pady=8)

        # Grid layout for inputs
        fields = [
            ("System Count:", self._system_count_var, "Raw count from the nav panel"),
            ("Corrected n:", self._corrected_n_var, "Auto: system count + 1"),
            ("Max Distance:", self._max_distance_var, "Search radius in LY"),
        ]

        for idx, (label, var, tooltip) in enumerate(fields):
            tk.Label(
                inner,
                text=label,
                font=("Consolas", 9),
                fg=self.colors.MUTED,
                bg=self.colors.BG_PANEL
            ).grid(row=idx, column=0, sticky="e", padx=(0, 10), pady=3)

            entry = tk.Entry(
                inner,
                textvariable=var,
                font=("Consolas", 9),
                fg=self.colors.TEXT,
                bg=self.colors.BG_FIELD,
                insertbackground=self.colors.TEXT,
                relief="solid",
                bd=1,
                width=15
            )
            entry.grid(row=idx, column=1, sticky="w", pady=3)

            # Hover tooltip (shows after a short delay, hides on move/leave)
            if label.lower().startswith("system count"):
                self._tooltips.append(Tooltip(
                    entry,
                    "From the left Nav panel: the raw system count for this star. (Not a galaxy map estimate.)",
                    delay_ms=1200
                ))
            elif label.lower().startswith("corrected"):
                self._tooltips.append(Tooltip(
                    entry,
                    "Calculated automatically from System Count.\n"
                    "The Nav panel does not include your current system, so the logger adds +1 to get the correct N.",
                    delay_ms=1200
                ))
            elif label.lower().startswith("max distance"):
                self._tooltips.append(Tooltip(
                    entry,
                    "The search radius (in LY) you used when counting. Use the project’s agreed radius so everyone matches.",
                    delay_ms=1200
                ))

            if label.lower().startswith("corrected"):
                entry.configure(state="readonly")

            tk.Label(
                inner,
                text=tooltip,
                font=("Consolas", 8),
                fg=self.colors.MUTED,
                bg=self.colors.BG_PANEL
            ).grid(row=idx, column=2, sticky="w", padx=(10, 0), pady=3)

    def _build_flags_section(self, parent: tk.Frame):
        """Build flags section (checkboxes)"""
        flags_frame = tk.LabelFrame(
            parent,
            text="FLAGS",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        flags_frame.pack(fill="x", pady=(0, 10))

        # NOTE: Don't mix pack + grid in the same container.
        # Keep help text packed on the frame, and use a separate inner frame for grid widgets.
        tk.Label(
            flags_frame,
            text="Optional tags to explain data quality or issues (bias risk, low coverage, etc.)",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", padx=10, pady=(0, 6))

        inner = tk.Frame(flags_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="x", padx=10, pady=(0, 8))

        # Checkboxes in 2 columns
        flags = [
            ("bias_risk", "Route Bias Risk"),
            ("low_coverage", "Low Coverage"),
            ("anomaly_suspected", "Anomaly Suspected"),
            ("interrupted", "Interrupted (AFK/Crash)"),
            ("repeat_needed", "Repeat Needed"),
        ]

        for idx, (key, label) in enumerate(flags):
            row = idx // 2
            col = idx % 2

            cb = tk.Checkbutton(
                inner,
                text=label,
                variable=self._flag_vars[key],
                font=("Consolas", 9),
                fg=self.colors.TEXT,
                bg=self.colors.BG_PANEL,
                selectcolor=self.colors.BG_FIELD,
                activebackground=self.colors.BG_PANEL,
                activeforeground=self.colors.ORANGE
            )
            cb.grid(row=row, column=col, sticky="w", padx=10, pady=2)

            # Tooltip per flag
            flag_tips = {
                "bias_risk": "You mainly followed a travel corridor/route, so the slice may be biased.",
                "low_coverage": "You only sampled briefly. Expect gaps or under-counting.",
                "anomaly_suspected": "Something odd here (cluster/void/weird counts). Might need a second look.",
                "interrupted": "Work was interrupted (AFK, crash, disconnect).",
                "repeat_needed": "This slice should be revisited later for better confidence."
            }
            tip = flag_tips.get(key, "")
            if tip:
                self._tooltips.append(Tooltip(cb, tip, delay_ms=1200))

    def _build_notes_section(self, parent: tk.Frame):
        """Build notes section (multi-line text)"""
        notes_frame = tk.LabelFrame(
            parent,
            text="NOTES",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        notes_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Text widget with scrollbar
        inner = tk.Frame(notes_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="both", expand=True, padx=10, pady=8)

        scrollbar = tk.Scrollbar(inner, bg=self.colors.BG_PANEL)
        scrollbar.pack(side="right", fill="y")

        self._notes_widget = tk.Text(
            inner,
            font=("Consolas", 9),
            fg=self.colors.TEXT,
            bg=self.colors.BG_FIELD,
            insertbackground=self.colors.TEXT,
            wrap="word",
            height=5,
            yscrollcommand=scrollbar.set
        )
        self._notes_widget.pack(fill="both", expand=True)

        self._tooltips.append(Tooltip(
            self._notes_widget,
            "Why it was discarded, what looked off, or any special circumstances.",
            delay_ms=1200,
            wraplength=420
        ))

        scrollbar.config(command=self._notes_widget.yview)

        # Hint label
        tk.Label(
            notes_frame,
            text="Free text for anything unusual or important (required if Discard).",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", padx=10, pady=(0, 5))

    def _build_footer(self, parent: tk.Frame):
        """Build footer with Save/Cancel buttons"""
        footer = tk.Frame(parent, bg=self.colors.BG)
        footer.pack(fill="x")

        # Cancel button
        btn_cancel = tk.Button(
            footer,
            text="Cancel",
            font=("Consolas", 9),
            bg=self.colors.BG_PANEL,
            fg=self.colors.TEXT,
            command=self._on_cancel,
            width=12
        )
        btn_cancel.pack(side="right", padx=(10, 0))

        # Save button (primary)
        btn_save = tk.Button(
            footer,
            text="Save",
            font=("Consolas", 9, "bold"),
            bg=self.colors.ORANGE,
            fg="#000000",
            command=self._on_save,
            width=12,
            cursor="hand2"
        )
        btn_save.pack(side="right")

        # Shortcut hint
        tk.Label(
            footer,
            text="Ctrl+Enter to save, Esc to cancel",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG
        ).pack(side="left")

    # =========================================================================
    # UI UPDATES
    # =========================================================================

    def _populate_from_context(self):
        """Populate header fields from context"""
        if self._context is None:
            return

        # System
        system = self._context.system_name or "-"
        self._lbl_system.config(text=system)

        # Z-bin
        z_bin = self._context.z_bin
        self._lbl_zbin.config(text=str(z_bin) if z_bin else "-")

        # Slice lock logic:
        # If the CMDR is saving multiple "in_progress" splice notes across different systems,
        # we keep the z-bin locked so system_sample counts up instead of resetting to 1.
        if z_bin is not None:
            if self._locked_z_bin is None:
                self._locked_z_bin = int(z_bin)

        # Update slice-lock label (show locked vs current)
        if hasattr(self, "_lbl_slice_lock") and self._lbl_slice_lock is not None:
            if self._locked_z_bin is None:
                self._lbl_slice_lock.config(text="not locked")
            else:
                if z_bin is not None and int(z_bin) != int(self._locked_z_bin):
                    self._lbl_slice_lock.config(text=f"locked {self._locked_z_bin} (current {z_bin})")
                else:
                    self._lbl_slice_lock.config(text=f"locked {self._locked_z_bin}")

        # Position
        pos = self._context.star_pos
        if pos and pos != (0.0, 0.0, 0.0):
            pos_text = f"X: {pos[0]:.1f}  Y: {pos[1]:.1f}  Z: {pos[2]:.1f}"
        else:
            pos_text = "X: -  Y: -  Z: -"
        self._lbl_position.config(text=pos_text)

        # Session
        session = self._context.session_id or self.session_id or "-"
        self._lbl_session.config(text=session)

        # Hotkey hint (provided by main.py)
        if hasattr(self, "_lbl_hotkey") and self._lbl_hotkey is not None:
            self._lbl_hotkey.config(text=self.hotkey_hint or "-")

        # Drift Guardrail
        try:
            drift_status = getattr(self._context, "drift_status", "-") or "-"
            self._lbl_drift_status.config(text=f"Status: {drift_status}")

            meta = getattr(self._context, "drift_meta", {}) or {}
            step = meta.get("step_ly")
            axis = meta.get("axis")
            locked = meta.get("locked")
            meta_bits = []
            if step:
                meta_bits.append(f"step {step} ly")
            if axis:
                meta_bits.append(str(axis))
            if locked is not None:
                meta_bits.append("locked" if locked else "unlocked")
            self._lbl_drift_meta.config(text=" | ".join(meta_bits))

            candidates = list(getattr(self._context, "drift_candidates", ()) or ())
            lines = []
            for c in candidates[:5]:
                try:
                    name = str(c.get("system") or "?")
                    drift = float(c.get("drift_ly", 0.0))
                    ideal = float(c.get("ideal_offset_ly", 0.0))
                    along = float(c.get("along_ly", 0.0))
                    lines.append(f"{name}: drift {drift:5.1f} ly | ideal {ideal:5.1f} ly | along {along:+6.0f} ly")
                except Exception:
                    continue
            if not lines:
                lines = ["(No upcoming jumps yet)"]
            self._lbl_drift_lines.config(text="\n".join(lines))
        except Exception:
            pass

    def _update_section_visibility(self):
        """Show/hide sections based on status selection"""
        status = self._slice_status_var.get()

        # Details section (confidence, method): show if not in_progress
        if status != SliceStatus.IN_PROGRESS.value:
            self._details_frame.pack(fill="x", pady=(0, 10), after=self._get_status_frame())
        else:
            self._details_frame.pack_forget()

        # Note: Density sampling section is always visible (main data entry fields)

    def _get_status_frame(self) -> tk.Widget:
        """Get the status section frame for pack ordering"""
        # Find the status LabelFrame
        for child in self.window.winfo_children():
            for subchild in child.winfo_children():
                if isinstance(subchild, tk.LabelFrame):
                    title = subchild.cget("text")
                    if title == "SLICE STATUS":
                        return subchild
        return self._details_frame  # Fallback

    def _on_confidence_changed(self, *args):
        """Update confidence label when slider changes"""
        value = self._confidence_var.get()
        self._lbl_confidence.config(text=f"{value}%")


    def _update_corrected_n(self, *args):
        """Auto-fill corrected_n as (system_count + 1). Clears on invalid input."""
        raw = self._system_count_var.get().strip() if hasattr(self, "_system_count_var") else ""
        if not raw:
            self._corrected_n_var.set("")
            return
        try:
            n = int(raw)
            self._corrected_n_var.set(str(n + 1))
        except ValueError:
            self._corrected_n_var.set("")


    # =========================================================================
    # ACTIONS
    # =========================================================================

    def _on_save(self):
        """Handle save button click"""
        # Validate
        is_valid, errors = self._validate()
        if not is_valid:
            messagebox.showerror(
                "Validation Error",
                "\n".join(errors),
                parent=self.window
            )
            return

        # Build ObserverNote
        note = self._build_note()

        # Call save callback
        if self.on_save:
            try:
                self.on_save(note)
            except Exception as e:
                messagebox.showerror(
                    "Save Error",
                    f"Failed to save observation:\n{e}",
                    parent=self.window
                )
                return

        # If the CMDR completed the slice, unlock so the next save starts a new splice sample.
        try:
            if note.slice_status == SliceStatus.COMPLETE:
                self._locked_z_bin = None
        except Exception:
            pass

        # Close overlay
        self.hide()

    def _on_cancel(self):
        """Handle cancel button click"""
        self.hide()

    def _validate(self) -> Tuple[bool, list]:
        """
        Validate form data.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Discard requires notes
        status = self._slice_status_var.get()
        notes = self._notes_widget.get("1.0", "end").strip()

        if status == SliceStatus.DISCARD.value and not notes:
            errors.append("Notes are required when status is 'Discard'")

        # Validate numeric fields
        system_count = self._system_count_var.get().strip()
        if system_count:
            try:
                val = int(system_count)
                if val < 0:
                    errors.append("System count must be non-negative")
            except ValueError:
                errors.append("System count must be a whole number")


        max_distance = self._max_distance_var.get().strip()
        if max_distance:
            try:
                val = float(max_distance)
                if val <= 0:
                    errors.append("Max distance must be positive")
            except ValueError:
                errors.append("Max distance must be a number")

        return (len(errors) == 0, errors)

    def _build_note(self) -> ObserverNote:
        """Build ObserverNote from form data"""
        # Get context data
        context_dict = self._context.to_dict() if self._context else {}

        # Create note from context
        note = create_observation_from_context(
            context=context_dict,
            session_id=self.session_id,
            app_version=self.app_version
        )

        # Set CMDR-input fields
        note.slice_status = SliceStatus(self._slice_status_var.get())
        note.completeness_confidence = self._confidence_var.get()

        # Map method display name back to enum value
        method_display = self._method_var.get()
        method_value = self._method_map.get(method_display, SamplingMethod.OTHER.value)
        note.sampling_method = SamplingMethod(method_value)

        # Density sampling data
        system_count = self._system_count_var.get().strip()
        if system_count:
            note.system_count = int(system_count)

            note.corrected_n = note.system_count + 1

        max_distance = self._max_distance_var.get().strip()
        if max_distance:
            note.max_distance = float(max_distance)

        # Flags
        note.flags = ObservationFlags(
            bias_risk=self._flag_vars["bias_risk"].get(),
            low_coverage=self._flag_vars["low_coverage"].get(),
            anomaly_suspected=self._flag_vars["anomaly_suspected"].get(),
            interrupted=self._flag_vars["interrupted"].get(),
            repeat_needed=self._flag_vars["repeat_needed"].get(),
        )

        # Notes
        note.notes = self._notes_widget.get("1.0", "end").strip()

        # Keep z-bin stable while the slice is IN_PROGRESS so that
        # (session_id, z_bin, sample_index) stays consistent and system_index increments.
        if self._locked_z_bin is not None and note.slice_status == SliceStatus.IN_PROGRESS:
            note.z_bin = int(self._locked_z_bin)

        return note

    # =========================================================================
    # PUBLIC METHODS FOR EDITING
    # =========================================================================

    def show_for_edit(self, note: ObserverNote):
        """
        Show overlay for editing an existing note.

        Args:
            note: ObserverNote to edit
        """
        # Create fake context from note
        from journal_state_manager import CurrentContext
        context = CurrentContext(
            system_name=note.system_name,
            system_address=note.system_address,
            star_pos=note.star_pos,
            z_bin=note.z_bin,
            session_id=note.session_id,
        )

        # Show window
        self.show(context)

        # Populate form with note data
        self._slice_status_var.set(note.slice_status.value)
        self._confidence_var.set(note.completeness_confidence)

        # Set method
        method_display = self._method_map_reverse.get(
            note.sampling_method.value,
            "Other"
        )
        self._method_combo.set(method_display)

        # Density data
        if note.system_count is not None:
            self._system_count_var.set(str(note.system_count))
        # corrected_n is auto-derived from system_count (kept for legacy notes)
        if note.system_count is None and note.corrected_n is not None:
            self._corrected_n_var.set(str(note.corrected_n))
        if note.max_distance is not None:
            self._max_distance_var.set(str(note.max_distance))

        # Flags
        self._flag_vars["bias_risk"].set(note.flags.bias_risk)
        self._flag_vars["low_coverage"].set(note.flags.low_coverage)
        self._flag_vars["anomaly_suspected"].set(note.flags.anomaly_suspected)
        self._flag_vars["interrupted"].set(note.flags.interrupted)
        self._flag_vars["repeat_needed"].set(note.flags.repeat_needed)

        # Notes
        self._notes_widget.delete("1.0", "end")
        self._notes_widget.insert("1.0", note.notes)

        # Update visibility
        self._update_section_visibility()