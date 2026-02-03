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

import json
import tkinter as tk
from tkinter import ttk, messagebox
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass

from observer_models import (
    ObserverNote,
    SliceStatus,
    SamplingMethod,
    ObservationFlags,
    create_observation_from_context,
    SURVEY_AXIS_INDEX,
)
from journal_state_manager import CurrentContext

import logging
logger = logging.getLogger("dw3.observer_overlay")

_SETTINGS_PATH = Path.home() / ".dw3_survey_logger" / "settings.json"


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
            except Exception as e:
                logger.debug("Tooltip after_cancel failed: %s", e)
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
            except Exception as e:
                logger.debug("Tooltip destroy failed: %s", e)
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
        get_context_fn: Optional[Callable[[], CurrentContext]] = None,
        on_save: Optional[Callable[[ObserverNote], None]] = None,
        on_export: Optional[Callable[[], None]] = None,
        session_id: str = "",
        app_version: str = "",
        observer_storage=None
    ):
        """
        Initialize overlay.

        Args:
            parent: Parent Tk window
            config: App config dict (for colors)
            on_save: Callback when observation is saved
            session_id: Current session ID
            app_version: App version string
            observer_storage: ObserverStorage instance for sample tracking
        """
        self.parent = parent
        self.config = config
        self.get_context_fn = get_context_fn
        self._ctx_bind_id = None
        self.on_save = on_save
        self.on_export = on_export
        self.on_edit: Optional[Callable[[ObserverNote], None]] = None
        self.on_save_boxel: Optional[Callable[[Dict[str, Any]], None]] = None
        self.session_id = session_id
        self.app_version = app_version
        self.observer_storage = observer_storage

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

        # Edit mode: when set, Save will amend this note instead of creating new
        self._editing_note_id: Optional[str] = None

        # Duplicate guard: track last saved system to prevent accidental double-saves
        self._last_saved_system_address: Optional[int] = None

        # Tkinter variables
        self._slice_status_var: Optional[tk.StringVar] = None
        self._confidence_var: Optional[tk.IntVar] = None
        self._method_var: Optional[tk.StringVar] = None
        self._system_count_var: Optional[tk.StringVar] = None
        self._corrected_n_var: Optional[tk.StringVar] = None
        self._max_distance_var: Optional[tk.StringVar] = None
        self._boxel_highest_system_var: Optional[tk.StringVar] = None
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

        # If window exists and is open, update context and focus it
        if self.window is not None and self.window.winfo_exists():
            # Update the context display (system name, z-bin, etc.)
            self._populate_from_context()
            self._ensure_context_binding()
            self.window.lift()
            self.window.focus_force()
            return

        # Create new window
        self._create_window()
        self._build_ui()
        self._populate_from_context()
        self._ensure_context_binding()

        # Let Tk calculate the ideal size so all sections are visible on open.
        # The scrollable content area handles overflow if the user shrinks later.
        self.window.update_idletasks()
        self._base_width = max(480, self.window.winfo_reqwidth())
        ideal_height = self.window.winfo_reqheight() + 20  # small buffer for footer
        # Cap to screen height so it never opens larger than the display
        screen_h = self.window.winfo_screenheight()
        ideal_height = min(ideal_height, int(screen_h * 0.85))
        self._base_height = ideal_height

        # Restore saved window size if available, otherwise use ideal
        saved_w, saved_h = self._load_window_size()
        if saved_w and saved_h:
            self.window.geometry(f"{saved_w}x{saved_h}")
        else:
            self.window.geometry(f"{self._base_width}x{ideal_height}")
        # Allow shrinking — scrollbar kicks in when content overflows
        self.window.minsize(self._base_width, 425)

        
        # Center on parent
        self._center_on_parent()

        # Focus
        self.window.focus_force()

    def hide(self):
        """Hide/close the overlay"""
        self._remove_context_binding()
        if self.window is not None and self.window.winfo_exists():
            # Persist window size for next launch
            try:
                w = self.window.winfo_width()
                h = self.window.winfo_height()
                self._save_window_size(w, h)
            except Exception as e:
                logger.debug("Failed to save window size: %s", e)
            try:
                self.window.unbind_all("<MouseWheel>")
                self.window.unbind_all("<Button-4>")
                self.window.unbind_all("<Button-5>")
            except Exception:
                pass
            self.window.destroy()
        self.window = None

    def is_visible(self) -> bool:
        """Check if overlay is currently visible"""
        return self.window is not None and self.window.winfo_exists()

    def _save_window_size(self, width: int, height: int):
        """Persist overlay window size to settings.json."""
        try:
            data = {}
            if _SETTINGS_PATH.exists():
                data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            data["overlay_width"] = width
            data["overlay_height"] = height
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("_save_window_size failed: %s", e)

    def _load_window_size(self) -> Tuple[Optional[int], Optional[int]]:
        """Load saved overlay window size from settings.json."""
        try:
            if _SETTINGS_PATH.exists():
                data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                w = data.get("overlay_width")
                h = data.get("overlay_height")
                if isinstance(w, int) and isinstance(h, int) and w >= 480 and h >= 425:
                    return w, h
        except Exception as e:
            logger.debug("_load_window_size failed: %s", e)
        return None, None

    def _ensure_context_binding(self):
        """Bind to context-change events while overlay is visible."""
        if self._ctx_bind_id is not None:
            return
        # Bind on the parent (root) so journal/presenter can event_generate there.
        try:
            self._ctx_bind_id = self.parent.bind("<<ObserverContextChanged>>", self._on_context_changed, add="+")
        except TypeError:
            # Older Tk variants may not support add as str; fall back without add.
            self._ctx_bind_id = self.parent.bind("<<ObserverContextChanged>>", self._on_context_changed)

    def _remove_context_binding(self):
        """Unbind context-change events when overlay closes."""
        if self._ctx_bind_id is None:
            return
        try:
            self.parent.unbind("<<ObserverContextChanged>>", self._ctx_bind_id)
        except Exception as e:
            logger.debug("unbind ObserverContextChanged failed: %s", e)
            pass
        self._ctx_bind_id = None

    def _on_context_changed(self, event=None):
        """Refresh overlay context when the app notifies new journal/state data."""
        if self.window is None or (hasattr(self.window, "winfo_exists") and not self.window.winfo_exists()):
            return
        old_addr = self._context.system_address if self._context else None
        if callable(self.get_context_fn):
            try:
                self._context = self.get_context_fn()
            except Exception as e:
                # Never crash UI on a refresh failure; keep last known context.
                logger.debug("get_context_fn failed on refresh: %s", e)
                pass
        # Clear duplicate guard when we arrive at a new system
        new_addr = self._context.system_address if self._context else None
        if new_addr is not None and new_addr != old_addr:
            self._last_saved_system_address = None
        self._populate_from_context()

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

        # Minimum size set dynamically in show() after UI is built
        self.window.minsize(480, 425)

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
            icon_name = self.config.get("ICON_NAME") or "earth2.ico"
            asset_path = self.config.get("ASSET_PATH")
            if not asset_path:
                return

            icon_path = Path(str(asset_path)) / icon_name
            if icon_path.exists():
                self.window.iconbitmap(default=str(icon_path))
        except Exception as e:
            logger.debug("Icon load failed: %s", e)
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
        self._boxel_highest_system_var = tk.StringVar(value="")

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

        # Outer container
        outer = tk.Frame(self.window, bg=self.colors.BG)
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        # Scrollable content area (canvas + scrollbar)
        self._scroll_canvas = tk.Canvas(outer, bg=self.colors.BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=self._scroll_canvas.yview)
        self._scroll_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="top", fill="both", expand=True)

        # Inner frame inside the canvas for all content sections
        main_frame = tk.Frame(self._scroll_canvas, bg=self.colors.BG)
        self._scroll_window_id = self._scroll_canvas.create_window(
            (0, 0), window=main_frame, anchor="nw"
        )

        # Keep canvas scroll region and inner frame width in sync
        def _on_frame_configure(event):
            self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

        def _on_canvas_configure(event):
            self._scroll_canvas.itemconfigure(self._scroll_window_id, width=event.width)

        main_frame.bind("<Configure>", _on_frame_configure)
        self._scroll_canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling (Windows/macOS + Linux)
        def _on_mousewheel(event):
            self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            direction = -1 if event.num == 4 else 1
            self._scroll_canvas.yview_scroll(direction, "units")

        self._scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._scroll_canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        self._scroll_canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        # Build sections inside scrollable area
        self._build_header(main_frame)
        self._build_z_target_section(main_frame)
        self._build_status_section(main_frame)
        self._build_details_section(main_frame)
        self._build_density_section(main_frame)
       #self._build_flags_section(main_frame)
        self._build_boxel_section(main_frame)
        self._build_notes_section(main_frame)

        # Footer pinned at bottom (outside scrollable area)
        self._build_footer(outer)

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
        header.pack(fill="x", pady=(0, 4))

        # Grid for context fields
        fields_frame = tk.Frame(header, bg=self.colors.BG_PANEL)
        fields_frame.pack(fill="x", padx=8, pady=6)

        # Balance columns so the content sits visually centered in the section.
        # Labels (0,2) stay compact; values (1,3) share the remaining width.
        fields_frame.grid_columnconfigure(0, weight=0)
        fields_frame.grid_columnconfigure(1, weight=1)
        fields_frame.grid_columnconfigure(2, weight=0)
        fields_frame.grid_columnconfigure(3, weight=1)

        # Row 1: System and Z-bin
        tk.Label(
            fields_frame,
            text="SYSTEM:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=0, column=0, sticky="e", padx=(0, 5), pady=2)

        system_row = tk.Frame(fields_frame, bg=self.colors.BG_PANEL)
        system_row.grid(row=0, column=1, columnspan=3, sticky="w", pady=2)

        self._lbl_system = tk.Label(
            system_row,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL,
            cursor="hand2"
        )
        self._lbl_system.pack(side="left")
        self._lbl_system.bind("<Button-1>", self._copy_system_name)

        self._lbl_copy_hint = tk.Label(
            system_row,
            text="click to copy",
            font=("Consolas", 8, "italic"),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL,
            cursor="hand2"
        )
        self._lbl_copy_hint.pack(side="left", padx=(6, 0))
        self._lbl_copy_hint.bind("<Button-1>", self._copy_system_name)

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

    def _build_z_target_section(self, parent: tk.Frame):
        """Build Next Sample Location section (replaces Drift Guardrail)."""
        z_frame = tk.LabelFrame(
            parent,
            text="NEXT SAMPLE LOCATION",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        z_frame.pack(fill="x", pady=(0, 4))

        inner = tk.Frame(z_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="x", padx=8, pady=6)

        # Grid layout:
        #   col 0 = labels (right aligned)
        #   col 1 = values (stretch)
        #   col 2 = progress mini-panel (fixed)
        #   col 3 = spacer (so progress isn't flush-right)
        inner.grid_columnconfigure(0, weight=0)
        inner.grid_columnconfigure(1, weight=1)
        inner.grid_columnconfigure(2, weight=0)
        inner.grid_columnconfigure(3, weight=1)

        # Row 0: Z-bin (moved here from CONTEXT so it sits with nav guidance)
        tk.Label(
            inner,
            text="Actual Y:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL,
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=(0, 4))

        self._lbl_zbin = tk.Label(
            inner,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
        )
        self._lbl_zbin.grid(row=0, column=1, sticky="w", pady=(0, 4))

        # Row 1: Next target Y
        tk.Label(
            inner,
            text="Next Target Y:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL,
        ).grid(row=1, column=0, sticky="e", padx=(0, 10), pady=2)

        self._lbl_current_z = tk.Label(
            inner,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors.TEXT,
            bg=self.colors.BG_PANEL,
        )
        self._lbl_current_z.grid(row=1, column=1, sticky="w", pady=2)

        # Row 2: Next slice
        tk.Label(
            inner,
            text="Next Slice Y:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL,
        ).grid(row=2, column=0, sticky="e", padx=(0, 10), pady=2)

        self._lbl_target_z = tk.Label(
            inner,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
        )
        self._lbl_target_z.grid(row=2, column=1, sticky="w", pady=2)

        # Progress mini-panel (moved inward by giving it a spacer column on the right)
        progress = tk.Frame(
            inner,
            bg=self.colors.BG_FIELD,
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors.BORDER_OUTER,
        )
        progress.grid(row=0, column=2, rowspan=3, sticky="n", padx=(14, 0), pady=(0, 0))

        tk.Label(
            progress,
            text="PROGRESS",
            font=("Consolas", 9, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_FIELD,
        ).pack(anchor="w", padx=8, pady=(6, 2))

        self._lbl_sample_count = tk.Label(
            progress,
            text="-",
            font=("Consolas", 9),
            fg=self.colors.TEXT,
            bg=self.colors.BG_FIELD,
            justify="left",
        )
        self._lbl_sample_count.pack(anchor="w", padx=8, pady=(0, 6))

        self._z_target_frame = z_frame


    

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
        status_frame.pack(fill="x", pady=(0, 4))
        self._status_frame = status_frame

        # Radio buttons in a row
        radio_frame = tk.Frame(status_frame, bg=self.colors.BG_PANEL)
        radio_frame.pack(fill="x", padx=8, pady=6)

        tk.Label(
            status_frame,
            text="Mark whether this Z-slice is still being sampled, complete, partial or discarded.",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", padx=10, pady=(0, 4))

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
        inner.pack(fill="x", padx=8, pady=6)

        # Confidence slider
        conf_frame = tk.Frame(inner, bg=self.colors.BG_PANEL)
        conf_frame.pack(fill="x", pady=(0, 8))

        tk.Label(
            inner,
            text="How confident you are this slice is representative (0–100%).",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", pady=(0, 4))

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
        ).pack(anchor="w", pady=(0, 4))

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
            "How you sampled this slice. Random = wander, Grid = systematic passes, Route Follow = along your plotted jumps, Targeted = chasing specific stars, Other = anything else.",
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
        self._density_frame.pack(fill="x", pady=(0, 4))

        help_lbl = tk.Label(
            self._density_frame,
            text="Enter values from the Nav panel. Corrected n is filled automatically.",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        help_lbl.pack(anchor="w", padx=10, pady=(6, 0))

        inner = tk.Frame(self._density_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="x", padx=8, pady=6)

        # Grid layout for inputs
        fields = [
            ("System Count:", self._system_count_var, "Raw count from the nav panel"),
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
            elif label.lower().startswith("max distance"):
                self._tooltips.append(Tooltip(
                    entry,
                    "Distance (in LY) to the nearest neighbouring star system.",
                    delay_ms=1200
                ))


            tk.Label(
                inner,
                text=tooltip,
                font=("Consolas", 8),
                fg=self.colors.MUTED,
                bg=self.colors.BG_PANEL
            ).grid(row=idx, column=2, sticky="w", padx=(10, 0), pady=3)

    def _build_boxel_section(self, parent: tk.Frame):
        """Build boxel size survey section (optional highest-numbered system)"""
        boxel_frame = tk.LabelFrame(
            parent,
            text="BOXEL SIZE (optional)",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        boxel_frame.pack(fill="x", pady=(0, 4))

        tk.Label(
            boxel_frame,
            text="For the Stellar Properties survey: enter the highest-numbered system in your current boxel.",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(6, 0))

        inner = tk.Frame(boxel_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="x", padx=8, pady=6)

        tk.Label(
            inner,
            text="Highest System:",
            font=("Consolas", 9),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=3)

        entry = tk.Entry(
            inner,
            textvariable=self._boxel_highest_system_var,
            font=("Consolas", 9),
            fg=self.colors.TEXT,
            bg=self.colors.BG_FIELD,
            insertbackground=self.colors.TEXT,
            relief="solid",
            bd=1,
            width=30
        )
        entry.grid(row=0, column=1, sticky="w", pady=3)

        btn_save_boxel = tk.Button(
            inner,
            text="Save Boxel",
            font=("Consolas", 9),
            bg="#3a5f8a",
            fg="#d0d8e8",
            activebackground="#4a7aaa",
            activeforeground="#ffffff",
            command=self._on_save_boxel,
            width=12,
            cursor="hand2"
        )
        btn_save_boxel.grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)

        self._boxel_status_lbl = tk.Label(
            inner,
            text="",
            font=("Consolas", 8),
            fg=self.colors.GREEN,
            bg=self.colors.BG_PANEL
        )
        self._boxel_status_lbl.grid(row=1, column=1, columnspan=2, sticky="w", pady=(0, 2))

        self._tooltips.append(Tooltip(
            entry,
            "Use Galaxy Map binary search to find the highest-numbered system "
            "in your boxel. Example: Eactainds LF-A d27",
            delay_ms=1200
        ))

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
        flags_frame.pack(fill="x", pady=(0, 4))

        # NOTE: Don't mix pack + grid in the same container.
        # Keep help text packed on the frame, and use a separate inner frame for grid widgets.
        tk.Label(
            flags_frame,
            text="Optional tags to explain data quality or issues (bias risk, low coverage, etc.)",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        ).pack(anchor="w", padx=10, pady=(0, 4))

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
        """Build notes section (multi-line text) - collapsible"""
        # Track collapsed state
        self._notes_collapsed = tk.BooleanVar(value=True)
        
        notes_frame = tk.LabelFrame(
            parent,
            text="",  # We'll use a custom header
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            relief="ridge",
            bd=2
        )
        notes_frame.pack(fill="both", expand=True, pady=(0, 8))  # Reduced padding

        # Clickable header to expand/collapse
        header_frame = tk.Frame(notes_frame, bg=self.colors.BG_PANEL, cursor="hand2")
        header_frame.pack(fill="x", padx=6, pady=4)  # Reduced padding
        
        self._notes_arrow = tk.Label(
            header_frame,
            text="▶",  # Right arrow when collapsed
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            cursor="hand2"
        )
        self._notes_arrow.pack(side="left", padx=(0, 5))
        
        notes_title = tk.Label(
            header_frame,
            text="NOTES (click to expand)",
            font=("Consolas", 10, "bold"),
            fg=self.colors.ORANGE,
            bg=self.colors.BG_PANEL,
            cursor="hand2"
        )
        notes_title.pack(side="left")
        
        # Hint when collapsed
        self._notes_hint_collapsed = tk.Label(
            header_frame,
            text="— Free text for unusual situations (required if Discard)",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL,
            cursor="hand2"
        )
        self._notes_hint_collapsed.pack(side="left", padx=(8, 0))
        
        # Bind click to toggle
        for widget in [header_frame, self._notes_arrow, notes_title, self._notes_hint_collapsed]:
            widget.bind("<Button-1>", lambda e: self._toggle_notes())

        # Container for text widget (initially hidden)
        self._notes_content_frame = tk.Frame(notes_frame, bg=self.colors.BG_PANEL)
        
        # Text widget with scrollbar
        inner = tk.Frame(self._notes_content_frame, bg=self.colors.BG_PANEL)
        inner.pack(fill="both", expand=True, padx=8, pady=(0, 4))  # Reduced padding

        scrollbar = tk.Scrollbar(inner, bg=self.colors.BG_PANEL)
        scrollbar.pack(side="right", fill="y")

        self._notes_widget = tk.Text(
            inner,
            font=("Consolas", 9),
            fg=self.colors.TEXT,
            bg=self.colors.BG_FIELD,
            insertbackground=self.colors.TEXT,
            wrap="word",
            height=4,  # Reduced from 5
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

        # Hint label (when expanded)
        self._notes_hint_expanded = tk.Label(
            self._notes_content_frame,
            text="Free text for anything unusual or important (required if Discard).",
            font=("Consolas", 8),
            fg=self.colors.MUTED,
            bg=self.colors.BG_PANEL
        )
        self._notes_hint_expanded.pack(anchor="w", padx=8, pady=(0, 4))  # Reduced padding

    def _toggle_notes(self):
        """Toggle notes section collapsed/expanded with dynamic window resizing"""
        if self._notes_collapsed.get():
            # Expand
            self._notes_collapsed.set(False)
            self._notes_arrow.config(text="▼")  # Down arrow
            self._notes_hint_collapsed.pack_forget()
            
            # Save current window size before expanding
            self.window.update_idletasks()
            self._saved_width = self.window.winfo_width()
            self._saved_height = self.window.winfo_height()
            
            # Show notes content
            self._notes_content_frame.pack(fill="both", expand=True)
            
            # Resize window to accommodate notes (add ~140px height)
            self.window.update_idletasks()
            new_height = self._saved_height + 140
            self.window.geometry(f"{self._saved_width}x{new_height}")
            
            self._notes_widget.focus_set()  # Focus on text area when expanding
        else:
            # Collapse
            self._notes_collapsed.set(True)
            self._notes_arrow.config(text="▶")  # Right arrow
            self._notes_content_frame.pack_forget()
            
            # Restore original window size
            if hasattr(self, '_saved_width') and hasattr(self, '_saved_height'):
                self.window.geometry(f"{self._saved_width}x{self._saved_height}")
            
            self._notes_hint_collapsed.pack(side="left", padx=(8, 0))

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

        # Edit Last button
        btn_edit_last = tk.Button(
            footer,
            text="Edit Last",
            font=("Consolas", 9),
            bg=self.colors.BG_PANEL,
            fg=self.colors.ORANGE,
            command=self._on_edit_last,
            width=12
        )
        btn_edit_last.pack(side="left")

        # Export button
        btn_export = tk.Button(
            footer,
            text="Export",
            font=("Consolas", 9),
            bg=self.colors.BG_PANEL,
            fg=self.colors.GREEN,
            command=self._on_export,
            width=12
        )
        btn_export.pack(side="left", padx=(10, 0))
        self._tooltips.append(Tooltip(btn_export, "Export Density Sheet", delay_ms=800))

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

        # Actual Y coordinate from game
        try:
            actual_y = self._context.star_pos[SURVEY_AXIS_INDEX]
            self._lbl_zbin.config(text=f"{actual_y:,.2f}" if actual_y is not None else "-")
        except (TypeError, IndexError):
            self._lbl_zbin.config(text="-")

        z_bin = self._context.z_bin

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

        # Next Sample Location (simplified for users)
        try:
            z_direction = getattr(self._context, "z_direction", 1)
            z_direction_known = getattr(self._context, "z_direction_known", False)
            actual_y = self._context.star_pos[SURVEY_AXIS_INDEX]

            # Next Target Y - show the locked target's Y coordinate
            target_pos = getattr(self._context, "target_star_pos", None)
            if target_pos is not None:
                target_y = target_pos[SURVEY_AXIS_INDEX]
                self._lbl_current_z.config(text=f"{target_y:,.2f}")
            else:
                self._lbl_current_z.config(text="-")

            # Next slice = actual Y +/- 50 in the detected travel direction
            # Only show after direction is detected (at least 1 jump)
            if z_direction_known:
                next_slice_y = actual_y + (50 * z_direction)
                arrow = "\u2191" if z_direction >= 1 else "\u2193"
                self._lbl_target_z.config(text=f"{next_slice_y:,.2f} {arrow}")
            else:
                self._lbl_target_z.config(text="(jump to detect)")

            # Update sample count display
            self._update_sample_count()

        except Exception as e:
            logger.debug("Z-target section update failed: %s", e)
            pass

    def _update_sample_count(self):
        """Update the sample count display based on observer storage data"""
        try:
            # Only update if we have observer_storage, context, and session_id
            if (not self.observer_storage or 
                not self._context or 
                not self._context.session_id or 
                self._context.z_bin is None):
                self._lbl_sample_count.config(text="-")
                return
            
            # Use locked z_bin if set, otherwise current context z_bin
            z_bin = self._locked_z_bin if self._locked_z_bin is not None else self._context.z_bin

            # Get sample counts from observer storage
            counts = self.observer_storage.get_sample_counts(
                self._context.session_id,
                z_bin
            )
            
            current_sample = counts['current_sample']
            current_systems = counts['current_systems']
            total_samples = counts['total_samples']

            # Format the display text for the PROGRESS mini-panel.
            count_text = (
                f"Sample: #{current_sample}\n"
                f"System: #{current_systems}\n"
                f"Total:  {total_samples}"
            )
            
            self._lbl_sample_count.config(text=count_text)
            
        except Exception as e:
            # If there's any error, just show a dash
            logger.debug("Sample count update failed: %s", e)
            self._lbl_sample_count.config(text="-")

    def _check_sample_hint(self):
        """Show a hint exactly once when the current sample reaches 20 systems."""
        try:
            if not self.observer_storage or not self._context or self._context.z_bin is None:
                return
            z_bin = self._locked_z_bin if self._locked_z_bin is not None else self._context.z_bin
            counts = self.observer_storage.get_sample_counts(
                self._context.session_id, z_bin
            )
            current_systems = counts.get("current_systems", 0)
            # Build a key so we only show the hint once per sample
            hint_key = (self._context.session_id, z_bin, counts.get("current_sample", 0))
            if current_systems == 20 and hint_key != getattr(self, "_last_hint_key", None):
                self._last_hint_key = hint_key
                messagebox.showinfo(
                    "Sample Hint",
                    "[HINT] 20 systems logged! Save one more to complete "
                    "the sample (21 total), then export.",
                    parent=self.window,
                )
        except Exception as e:
            logger.debug("_check_sample_hint failed: %s", e)

    def _update_section_visibility(self):
        """Show/hide sections based on status selection"""
        status = self._slice_status_var.get()

        # Preserve current window size so toggling status doesn't auto-shrink and hide footer buttons
        try:
            cur_w = self.window.winfo_width()
            cur_h = self.window.winfo_height()
        except Exception as e:
            logger.debug("Window size query failed: %s", e)
            cur_w = getattr(self, "_base_width", 480)
            cur_h = getattr(self, "_base_height", 728)

        # Details section (confidence, method): show if not in_progress
        if status != SliceStatus.IN_PROGRESS.value:
            self._details_frame.pack(fill="x", pady=(0, 6), after=self._get_status_frame())
        else:
            self._details_frame.pack_forget()

        # Update scroll region after showing/hiding sections
        try:
            self.window.update_idletasks()
            if hasattr(self, "_scroll_canvas"):
                self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
        except Exception as e:
            logger.debug("Window geometry update failed: %s", e)
            pass

        # Note: Density sampling section is always visible (main data entry fields)


    def _get_status_frame(self) -> tk.Widget:
        """Get the status section frame for pack ordering"""
        if hasattr(self, "_status_frame"):
            return self._status_frame
        return self._details_frame  # Fallback

    def _copy_system_name(self, event=None):
        """Copy system name to clipboard"""
        name = self._lbl_system.cget("text")
        if name and name != "-":
            try:
                self.window.clipboard_clear()
                self.window.clipboard_append(name)
                # Brief visual feedback
                original_fg = self._lbl_system.cget("fg")
                self._lbl_system.config(fg=self.colors.GREEN)
                self._lbl_copy_hint.config(text="copied!", fg=self.colors.GREEN)
                def _restore():
                    self._lbl_system.config(fg=original_fg)
                    self._lbl_copy_hint.config(text="click to copy", fg=self.colors.MUTED)
                self.window.after(800, _restore)
            except Exception as e:
                logger.debug("Clipboard copy failed: %s", e)

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
        # Duplicate guard: warn if saving the same system twice in a row
        current_addr = self._context.system_address if self._context else None
        if (current_addr is not None
                and current_addr == self._last_saved_system_address
                and not self._editing_note_id):
            system_name = (self._context.system_name or "this system") if self._context else "this system"
            if not messagebox.askyesno(
                "Duplicate Warning",
                f"You already saved an observation for {system_name}.\n\n"
                "Save another entry for the same system?",
                parent=self.window,
            ):
                return

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

        # Amend existing note or save new
        if self._editing_note_id and self.observer_storage:
            try:
                self.observer_storage.amend(self._editing_note_id, note)
                self._editing_note_id = None
                self.window.title("Add Observation")
                # Notify presenter of successful edit
                if callable(self.on_edit):
                    self.on_edit(note)
            except Exception as e:
                messagebox.showerror(
                    "Amend Error",
                    f"Failed to amend observation:\n{e}",
                    parent=self.window
                )
                return
        elif self.on_save:
            try:
                self.on_save(note)
            except Exception as e:
                messagebox.showerror(
                    "Save Error",
                    f"Failed to save observation:\n{e}",
                    parent=self.window
                )
                return

        # Update the sample counter display after successful save
        try:
            self._update_sample_count()
            # Check if system count hit 20 — nudge CMDR to complete the sample
            self._check_sample_hint()
        except Exception as e:
            logger.debug("Post-save sample count update failed: %s", e)
            pass

        # If the CMDR completed the slice, unlock so the next save starts a new splice sample.
        try:
            if note.slice_status == SliceStatus.COMPLETE:
                self._locked_z_bin = None
        except Exception as e:
            logger.debug("Post-save z_bin unlock failed: %s", e)
            pass

        # Record last saved system for duplicate guard
        self._last_saved_system_address = current_addr

        # Reset fields for new input
        self._clear_fields()

        # Don't close overlay after save - let user decide when to close
        # User can press ESC or click X to close manually
        # self.hide()  # Commented out - window stays open after save

    def _clear_fields(self):
        """Reset form fields to defaults after a successful save."""
        self._editing_note_id = None
        self.window.title("Add Observation")
        self._slice_status_var.set(SliceStatus.IN_PROGRESS.value)
        self._confidence_var.set(50)
        self._method_var.set(SamplingMethod.OTHER.value)
        self._system_count_var.set("")
        self._max_distance_var.set("")
        for var in self._flag_vars.values():
            var.set(False)
        self._notes_widget.delete("1.0", "end")

    def _on_save_boxel(self):
        """Handle Save Boxel button click"""
        boxel_val = self._boxel_highest_system_var.get().strip()
        if not boxel_val:
            self._boxel_status_lbl.config(text="Enter a system name first", fg=self.colors.RED)
            return

        if self.on_save_boxel:
            try:
                context_dict = self._context.to_dict() if self._context else {}
                entry = {
                    "cmdr_name": "",  # filled by presenter from model
                    "system_name": context_dict.get("system_name", ""),
                    "system_address": context_dict.get("system_address"),
                    "star_pos": context_dict.get("star_pos", (0.0, 0.0, 0.0)),
                    "boxel_highest_system": boxel_val,
                    "session_id": self.session_id,
                }
                self.on_save_boxel(entry)
                self._boxel_status_lbl.config(text="Saved!", fg=self.colors.GREEN)
                self._boxel_highest_system_var.set("")
            except Exception as e:
                self._boxel_status_lbl.config(text=f"Error: {e}", fg=self.colors.RED)
        else:
            self._boxel_status_lbl.config(text="Save not available", fg=self.colors.RED)

    def _on_edit_last(self):
        """Load the most recent observation into the form for editing."""
        if not self.observer_storage:
            messagebox.showinfo("Edit", "Storage not available.", parent=self.window)
            return
        try:
            notes = self.observer_storage.get_active(limit=1)
            if not notes:
                messagebox.showinfo("Edit", "No saved observations to edit.", parent=self.window)
                return
            last_note = notes[0]
            self.show_for_edit(last_note)
        except Exception as e:
            messagebox.showerror("Edit Error", f"Failed to load last observation:\n{e}", parent=self.window)

    def _on_export(self):
        """Handle export button click - delegates to presenter callback"""
        if callable(self.on_export):
            self.on_export()
        else:
            messagebox.showinfo("Export", "Export not available.", parent=self.window)

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

        # Preserve current window size so toggling status doesn't auto-shrink and hide the footer buttons
        try:
            cur_w = self.window.winfo_width()
            cur_h = self.window.winfo_height()
        except Exception as e:
            logger.debug("Validate window size query failed: %s", e)
            cur_w = getattr(self, "_base_width", 480)
            cur_h = getattr(self, "_base_height", 728)

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
                if val < 0:
                    errors.append("Max distance must be non-negative")
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

        # Track edit mode
        self._editing_note_id = note.id

        # Show window
        self.show(context)
        self.window.title("Edit Observation")

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

        # Boxel highest system
        if getattr(note, 'boxel_highest_system', ''):
            self._boxel_highest_system_var.set(note.boxel_highest_system)

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