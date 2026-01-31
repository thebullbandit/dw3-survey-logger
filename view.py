"""
View Layer - UI Components Only
================================

Pure UI code with no business logic.
Communicates with Presenter for all data operations.
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   view.py
#
# Connected modules (direct imports):
#   (none)
#
# Notes:
#   - This file is part of the DW3 Survery Logger Beta build.
#   - Section dividers below are comments only.
# ============================================================================

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk
from tkinter import filedialog, messagebox
from typing import Optional, Dict, Any, Callable, List
from collections import deque
import webbrowser


# ============================================================================
# CLASSES
# ============================================================================

class Earth2View:
    """View layer - manages all UI components"""
    
    def __init__(self, root: tk.Tk, config: Dict[str, Any]):
        """
        Initialize the view
        
        Args:
            root: Tkinter root window
            config: Configuration dictionary for UI settings
        """
        self.root = root
        self.config = config
        
        # UI state cache (for optimization)
        self._ui_cache = {}
        
        # Event callbacks (set by presenter)
        self.on_export_csv: Optional[Callable] = None
        self.on_export_db: Optional[Callable] = None
        self.on_export_density_xlsx: Optional[Callable] = None
        self.on_export_all: Optional[Callable] = None
        self.on_rescan: Optional[Callable] = None
        self.on_import_journals: Optional[Callable] = None
        self.on_options: Optional[Callable] = None
        self.on_about: Optional[Callable] = None
        self.on_options: Optional[Callable] = None
        self.on_about: Optional[Callable] = None
        
        # Widget references
        self.widgets = {}
        
        # Color scheme
        self._setup_colors()
        
        self._setup_fonts()
    def _setup_colors(self):
        """Setup color scheme from config"""
        self.colors = {
            "BG": self.config.get("BG", "#0a0a0f"),
            "BG_PANEL": self.config.get("BG_PANEL", "#12121a"),
            "BG_FIELD": self.config.get("BG_FIELD", "#1a1a28"),
            "TEXT": self.config.get("TEXT", "#e0e0ff"),
            "MUTED": self.config.get("MUTED", "#6a6a8a"),
            "BORDER_OUTER": self.config.get("BORDER_OUTER", "#2a2a3f"),
            "BORDER_INNER": self.config.get("BORDER_INNER", "#1f1f2f"),
            "ORANGE": self.config.get("ORANGE", "#ff8833"),
            "ORANGE_DIM": self.config.get("ORANGE_DIM", "#cc6622"),
            "GREEN": self.config.get("GREEN", "#44ff88"),
            "RED": self.config.get("RED", "#ff4444"),
            "LED_ACTIVE": self.config.get("LED_ACTIVE", "#00ff88"),
            "LED_IDLE": self.config.get("LED_IDLE", "#888888"),
        }

    def _setup_fonts(self):
        """Central font setup (UI uses sans-serif, data/logs use monospace)."""
        # Pick a title font that feels more "instrument panel" than default UI text.
        # Falls back gracefully if the font isn't installed.
        try:
            fam = set(tkfont.families(self.root))
        except Exception:
            fam = set()

        def _pick(*names: str, fallback: str = "Segoe UI") -> str:
            for n in names:
                if n in fam:
                    return n
            return fallback

        title_family = _pick("Bahnschrift", "Segoe UI Variable Display", "Segoe UI", "Arial")

        self.fonts = {
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

    def _style_button(self, btn: tk.Widget, *, accent: bool = False, success: bool = False):
        """Apply a flat, HUD-friendly button style."""
        bg = self.colors["ORANGE"] if accent else (self.colors["GREEN"] if success else self.colors["BG_PANEL"])
        fg = "#000000" if (accent or success) else self.colors["TEXT"]

        cfg = {
            "font": self.fonts["UI"],
            "bg": bg,
            "fg": fg,
            "activebackground": bg,
            "activeforeground": fg,
            "relief": "flat",
            "bd": 0,
            "highlightthickness": 1,
            "highlightbackground": self.colors["BORDER_INNER"],
            "highlightcolor": self.colors["ORANGE_DIM"],
            "padx": 10,
            "pady": 3,
            "cursor": "hand2",
        }
        # Best-effort apply (some widgets don't support all options)
        for k, v in cfg.items():
            try:
                btn.configure(**{k: v})
            except Exception:
                pass

        # Subtle hover affordance for non-accent buttons
        if not (accent or success):
            try:
                btn.bind("<Enter>", lambda _e: btn.configure(highlightbackground=self.colors["BORDER_OUTER"]))
                btn.bind("<Leave>", lambda _e: btn.configure(highlightbackground=self.colors["BORDER_INNER"]))
            except Exception:
                pass

    
    def build_ui(self):
        """Build the complete UI"""
        # Window setup
        self.root.title(f"{self.config['APP_NAME']} v{self.config['VERSION']}")
        
        # Get screen dimensions and calculate window size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        
        window_width = 900
        window_height = min(640, int(screen_height * 0.78))  # compact default, still tall enough
        
        # Set window size and position (centered)
        x_position = (screen_width - window_width) // 2
        y_position = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        
        # DPI-aware minimum size (works across machines)
        try:
            scale = float(self.root.tk.call("tk", "scaling"))
        except Exception:
            scale = 1.0
        min_w = int(680 * scale)
        min_h = int(440 * scale)
        self.root.minsize(min_w, min_h)
        
        self.root.configure(bg=self.colors["BG"])
        
        # Try to load icon
        self._load_icon()

        # Build main layout
        self._build_header()
        self._build_controls()
        self._build_footer()

        # Body: grid-based layout for predictable resizing
        self.body = tk.Frame(self.root, bg=self.colors["BG"])
        self.body.pack(fill="both", expand=True)

        # Grid: HUD (row 0), main area (row 1), COMMS drawer (row 2)
        # IMPORTANT UX: Keep Target/Stats panels content-sized; give extra vertical space to COMMS.
        self.body.grid_rowconfigure(1, weight=0)
        self.body.grid_rowconfigure(2, weight=1)
        self.body.grid_columnconfigure(0, weight=3)
        self.body.grid_columnconfigure(1, weight=1)

        # HUD strip replaces the tall STATUS panel
        self._build_hud_strip(parent=self.body)
        self.widgets["hud_strip"].grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 6))
        # Main work area: Full-width Statistics (Target Lock panel removed)
        # We still build Target Lock widgets invisibly so presenter updates keep working.
        stats_host = tk.Frame(self.body, bg=self.colors["BG"])
        stats_host.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        stats_host.grid_columnconfigure(0, weight=1)

        # Build hidden target-lock widgets for compatibility
        self._build_target_lock(parent=stats_host, visible=False)

        # Visible stats panel
        self._build_statistics_panel(parent=stats_host)

        # Bottom drawer: COMMS (collapsible)
        self._build_comms_drawer(parent=self.body)
        # COMMS gets the vertical expansion when the window is tall
        self.widgets["comms_drawer"].grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 8))


        # Responsive text wrapping for the Target Lock reason line
        if not getattr(self, "_wrap_bound", False):
            def _on_root_resize(event=None):
                try:
                    if event is not None and event.widget is not self.root:
                        return
                    lbl = self.widgets.get("lbl_reason")
                    if lbl:
                        w = max(400, self.root.winfo_width() - 80)
                        lbl.configure(wraplength=w)
                except Exception:
                    pass
            self.root.bind("<Configure>", _on_root_resize)
            self._wrap_bound = True

        # -----------------------------------------------------------------
        # UX GUARDFIX: COMMS must be visible at startup.
        # - User must NOT be able to resize the window to hide COMMS.
        # - Only the COMMS toggle button is allowed to collapse/expand
        #   the window height.
        # -----------------------------------------------------------------
        self._init_comms_window_behavior()

        return self.root

    # ---------------------------------------------------------------------
    # WINDOW / COMMS DRAWER SIZE MANAGEMENT
    # ---------------------------------------------------------------------
    def _init_comms_window_behavior(self):
        """Initialize fixed-size window behavior and COMMS startup state.

        Startup requirement:
          - COMMS is visible (expanded).
          - The user cannot resize the window manually.
          - Clicking the COMMS toggle collapses/expands and resizes the
            window programmatically.
        """
        # Safety: Only run once.
        if getattr(self, "_comms_window_ready", False):
            return

        # Ensure COMMS starts expanded (visible).
        self._comms_collapsed = False
        self._apply_comms_state(initial=True)
        self.root.update_idletasks()

        # Use current geometry width as the fixed width.
        w = self.root.winfo_width() or self.root.winfo_reqwidth()

        # Expanded target height: at least what's currently shown, but never
        # less than what the layout requires.
        expanded_req_h = self.root.winfo_reqheight()
        expanded_h = max(self.root.winfo_height() or 0, expanded_req_h)

        # Apply expanded geometry (in case current window height is too small).
        self.root.geometry(f"{w}x{expanded_h}")
        self.root.update_idletasks()

        # Capture expanded height after geometry settles.
        self._comms_expanded_height = self.root.winfo_height() or expanded_h

        # Measure collapsed height by temporarily collapsing COMMS.
        self._comms_collapsed = True
        self._apply_comms_state(initial=True)
        self.root.update_idletasks()
        self._comms_collapsed_height = self.root.winfo_reqheight()

        # Restore expanded state for startup.
        self._comms_collapsed = False
        self._apply_comms_state(initial=True)
        self.root.update_idletasks()
        self.root.geometry(f"{w}x{self._comms_expanded_height}")
        self.root.update_idletasks()

        # Hard-disable manual resizing.
        try:
            self.root.resizable(False, False)
        except Exception:
            pass

        # Clamp min/max to the current (expanded) geometry.
        # This guarantees COMMS cannot be hidden by dragging the window.
        try:
            self.root.minsize(w, self._comms_expanded_height)
            self.root.maxsize(w, self._comms_expanded_height)
        except Exception:
            pass

        self._comms_window_ready = True

    def _apply_window_size_for_comms_state(self):
        """Resize window (programmatically) to match COMMS drawer state.

        This is the ONLY allowed way the window height changes.
        """
        if not getattr(self, "_comms_window_ready", False):
            return

        # Recompute required heights defensively (different DPI/fonts).
        self.root.update_idletasks()
        w = self.root.winfo_width() or self.root.winfo_reqwidth()

        if getattr(self, "_comms_collapsed", True):
            # Collapsed height can vary slightly across systems.
            self._comms_collapsed_height = max(
                int(getattr(self, "_comms_collapsed_height", 0) or 0),
                int(self.root.winfo_reqheight() or 0),
            )
            target_h = int(self._comms_collapsed_height)
        else:
            self._comms_expanded_height = max(
                int(getattr(self, "_comms_expanded_height", 0) or 0),
                int(self.root.winfo_reqheight() or 0),
            )
            target_h = int(self._comms_expanded_height)

        # Apply geometry and clamp so the user can't drag-resize into a bad state.
        try:
            self.root.geometry(f"{w}x{target_h}")
            self.root.update_idletasks()
            self.root.minsize(w, target_h)
            self.root.maxsize(w, target_h)
        except Exception:
            pass
    
    def _build_target_lock(self, parent=None, visible=True):
        """Build target lock readout panel"""
        parent = parent or getattr(self, "body", None) or self.root
        panel = tk.LabelFrame(
            parent,
            text="TARGET LOCK",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            relief="solid",
            bd=1
        )

        # Keep panel compact (no vertical stretching)
        if visible:
            panel.pack(fill="x", expand=False, padx=0, pady=0)

        # System and Body (tighter padding)
        info_frame = tk.Frame(panel, bg=self.colors["BG_PANEL"])
        info_frame.pack(fill="x", padx=6, pady=(3, 2))

        tk.Label(
            info_frame,
            text="SYSTEM:",
            font=self.fonts["MONO"],
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(side="left", padx=(0, 5))

        lbl_sys = tk.Label(
            info_frame,
            text="-",
            font=self.fonts["MONO_BOLD"],
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_sys.pack(side="left", padx=(0, 20))

        tk.Label(
            info_frame,
            text="BODY:",
            font=self.fonts["MONO"],
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(side="left", padx=(0, 5))

        lbl_body = tk.Label(
            info_frame,
            text="-",
            font=self.fonts["MONO_BOLD"],
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_body.pack(side="left")

        # Badges (tighter padding)
        badge_frame = tk.Frame(panel, bg=self.colors["BG_PANEL"])
        badge_frame.pack(fill="x", padx=6, pady=(0, 2))

        badges = [
            ("lbl_badge_type", "TYPE: -"),
            ("lbl_badge_rating", "RATING: -"),
            ("lbl_badge_worth", "WORTH: -"),
        ]

        for widget_name, default_text in badges:
            badge = tk.Label(
                badge_frame,
                text=default_text,
                font=self.fonts["MONO_SMALL"],
                fg=self.colors["TEXT"],
                bg=self.colors["BG_FIELD"],
                relief="solid",
                bd=1,
                padx=6,
                pady=2
            )
            badge.pack(side="left", padx=4)
            self.widgets[widget_name] = badge

        # Reason text (tight bottom padding)
        lbl_reason = tk.Label(
            panel,
            text="-",
            font=self.fonts["MONO"],
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"],
            wraplength=900,
            justify="left"
        )
        lbl_reason.pack(fill="x", padx=6, pady=(0, 3))

        # Inara link (tight)
        lbl_inara = tk.Label(
            panel,
            text="-",
            font=self.fonts["MONO_SMALL"],
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"],
            cursor="hand2"
        )
        lbl_inara.pack(fill="x", padx=6, pady=(0, 3))

        # Similarity breakdown section (hidden by default)
        similarity_frame = tk.Frame(panel, bg=self.colors["BG_FIELD"])

        similarity_title = tk.Label(
            similarity_frame,
            text="━━━ EARTH SIMILARITY ━━━",
            font=self.fonts["MONO_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_FIELD"]
        )
        similarity_title.pack(pady=(5, 3))

        lbl_similarity_score = tk.Label(
            similarity_frame,
            text="Score: -",
            font=self.fonts["MONO_BOLD"],
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"]
        )
        lbl_similarity_score.pack(pady=2)

        lbl_similarity_category = tk.Label(
            similarity_frame,
            text="Category: -",
            font=self.fonts["MONO"],
            fg=self.colors["GREEN"],
            bg=self.colors["BG_FIELD"]
        )
        lbl_similarity_category.pack(pady=2)

        metrics_frame = tk.Frame(similarity_frame, bg=self.colors["BG_FIELD"])
        metrics_frame.pack(fill="x", padx=10, pady=5)

        lbl_similarity_metrics = tk.Label(
            metrics_frame,
            text="",
            font=self.fonts["MONO_SMALL"],
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"],
            justify="left"
        )
        lbl_similarity_metrics.pack(anchor="w")

        self.widgets["target_lock_panel"] = panel
        self.widgets["lbl_target_system"] = lbl_sys
        self.widgets["lbl_target_body"] = lbl_body
        self.widgets["lbl_reason"] = lbl_reason
        self.widgets["lbl_inara"] = lbl_inara
        self.widgets["similarity_frame"] = similarity_frame
        self.widgets["lbl_similarity_score"] = lbl_similarity_score
        self.widgets["lbl_similarity_category"] = lbl_similarity_category
        self.widgets["lbl_similarity_metrics"] = lbl_similarity_metrics

        # Click opens Inara link (set later when text updates)
        def _open_inara(_e=None):
            url = getattr(self, "_inara_url", None)
            if url:
                webbrowser.open(url)

        lbl_inara.bind("<Button-1>", _open_inara)
    
    def _load_icon(self):
        """Load application icon if available"""
        try:
            icon_name = self.config.get("ICON_NAME", "earth2.ico")
            icon_path = self.config.get("ASSET_PATH", "") / icon_name
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass  # Icon not critical

    def _apply_icon_to_window(self, win: tk.Toplevel | tk.Tk):
        """Apply app icon to a Tk/Toplevel window (Windows .ico)."""
        try:
            from pathlib import Path
            import sys, os

            # Prefer explicit Earth2.ico in assets/
            base_dir = Path(getattr(sys, "_MEIPASS", os.path.abspath(".")))
            earth2_ico = base_dir / "assets" / "Earth2.ico"
            if earth2_ico.exists():
                win.iconbitmap(str(earth2_ico))
                return

            # Fallback to configured icon (used by main window)
            icon_name = self.config.get("ICON_NAME", "earth2.ico")
            asset_path = self.config.get("ASSET_PATH", None)
            if asset_path:
                icon_path = Path(asset_path) / icon_name
                if icon_path.exists():
                    win.iconbitmap(str(icon_path))
        except Exception:
            pass  # Icon not critical

    
    def _build_header(self):
        """Build header with title and LED indicator"""
        header = tk.Frame(self.root, bg=self.colors["BG_PANEL"], height=60)
        header.pack(fill="x", padx=10, pady=(10, 5))
        header.pack_propagate(False)
        
        # Title
        title_label = tk.Label(
            header,
            text=f"{self.config['APP_NAME']} v{self.config['VERSION']}",
            font=self.fonts["TITLE"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        )
        title_label.pack(side="left", padx=20, pady=10)
        
        # LED indicator
        led_frame = tk.Frame(header, bg=self.colors["BG_PANEL"])
        led_frame.pack(side="right", padx=20)
        
        # Quick-link: DW3 community radio (opens in default browser)
        lbl_radio = tk.Label(
            led_frame,
            text="DW3 RADIO",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            cursor="hand2"
        )
        lbl_radio.pack(side="left", padx=(0, 10))
        lbl_radio.bind("<Button-1>", lambda _e: self._open_dw3_radio())

        led_canvas = tk.Canvas(led_frame, width=20, height=20, bg=self.colors["BG_PANEL"], highlightthickness=0)
        led_canvas.pack(side="left", padx=(0, 10))
        led_dot = led_canvas.create_oval(4, 4, 16, 16, fill=self.colors["LED_IDLE"], outline="")

        # Small hover affordance
        lbl_radio.bind("<Enter>", lambda _e: lbl_radio.config(fg=self.colors.get("TEXT", self.colors["ORANGE"])))
        lbl_radio.bind("<Leave>", lambda _e: lbl_radio.config(fg=self.colors["ORANGE"]))
        
        lbl_feed = tk.Label(
            led_frame,
            text="DATA FEED: INITIALIZING",
            font=self.fonts["UI_SMALL"],
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_feed.pack(side="left")
        
        # Store widget references
        self.widgets["header"] = header
        self.widgets["led_canvas"] = led_canvas
        self.widgets["led_dot"] = led_dot
        self.widgets["lbl_radio"] = lbl_radio
        self.widgets["lbl_feed"] = lbl_feed
        self.widgets["lbl_radio"] = lbl_radio
    
    def _build_hud_strip(self, parent: tk.Widget):
        """
        Build a compact HUD strip (replaces the tall STATUS panel).
        Keeps the same widget keys the presenter expects:
          - lbl_scan_status, lbl_journal, lbl_cmdr, lbl_signal, lbl_skipped
        """
        hud = tk.Frame(parent, bg=self.colors["BG_PANEL"], bd=1, relief="solid")
        self.widgets["hud_strip"] = hud

        # Layout: 3 rows x 3 pairs
        # Row 0: SCAN, JOURNAL, CMDR
        # Row 1: TARGET (full-width line)
        # Row 2: SIGNAL, SKIPPED, hint

        for i in range(6):
            hud.grid_columnconfigure(i, weight=1)

        def add_field(row, col, label_text, key):
            tk.Label(
                hud,
                text=label_text,
                font=("Consolas", 9),
                fg=self.colors["MUTED"],
                bg=self.colors["BG_PANEL"],
            ).grid(row=row, column=col, sticky="e", padx=(10, 4), pady=6)

            val = tk.Label(
                hud,
                text="-",
                font=("Consolas", 9),
                fg=self.colors["TEXT"],
                bg=self.colors["BG_PANEL"],
                anchor="w",
            )
            val.grid(row=row, column=col + 1, sticky="w", padx=(0, 14), pady=6)
            self.widgets[key] = val

        # Row 0
        add_field(0, 0, "SCAN:", "lbl_scan_status")
        add_field(0, 2, "JOURNAL:", "lbl_journal")
        add_field(0, 4, "CMDR:", "lbl_cmdr")

        # Row 1: Target line (where your red line is)
        tk.Label(
            hud,
            text="TARGET:",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"],
        ).grid(row=1, column=0, sticky="e", padx=(10, 4), pady=(0, 6))

        lbl_target_line = tk.Label(
            hud,
            text="-",
            font=("Consolas", 9),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"],
            anchor="w",
        )
        lbl_target_line.grid(row=1, column=1, columnspan=5, sticky="ew", padx=(0, 12), pady=(0, 6))
        self.widgets["lbl_target_line"] = lbl_target_line

        # Row 2
        add_field(2, 0, "SIGNAL:", "lbl_signal")
        add_field(2, 2, "SKIPPED:", "lbl_skipped")

        # Right-side subtle hint for hotkey / status (optional future use)
        self.widgets["hud_hint"] = tk.Label(
            hud,
            text="",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"],
            anchor="e",
        )
        self.widgets["hud_hint"].grid(row=2, column=4, columnspan=2, sticky="e", padx=(0, 12), pady=6)

        return hud

    def _build_comms_drawer(self, parent: tk.Widget):
        """
        Build a collapsible COMMS drawer (small by default, expandable).
        """
        drawer = tk.Frame(parent, bg=self.colors["BG_PANEL"], bd=1, relief="solid")
        self.widgets["comms_drawer"] = drawer

        # Title bar
        title = tk.Frame(drawer, bg=self.colors["BG_PANEL"])
        title.pack(fill="x")

        # Startup requirement: COMMS must be visible.
        # We still allow collapsing later via the toggle.
        self._comms_collapsed = False

        self._btn_comms_toggle = tk.Button(
            title,
            text="▾",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            activebackground=self.colors["BG_PANEL"],
            activeforeground=self.colors["ORANGE"],
            bd=0,
            relief="flat",
            command=self._toggle_comms_drawer,
        )
        self._btn_comms_toggle.pack(side="left", padx=(8, 6), pady=4)

        lbl = tk.Label(
            title,
            text="COMMS",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
        )
        lbl.pack(side="left", pady=4)

        # Content area (text + scrollbar)
        self._comms_content = tk.Frame(drawer, bg=self.colors["BG_PANEL"])
        self._comms_content.pack(fill="x", padx=6, pady=(0, 6))

        txt = tk.Text(
            self._comms_content,
            height=12,  # expanded default (visible on startup)
            wrap="word",
            font=("Consolas", 9),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"],
            insertbackground=self.colors["TEXT"],
            relief="sunken",
            bd=1,
        )
        txt.pack(side="left", fill="x", expand=True)

        scrollbar = tk.Scrollbar(self._comms_content, command=txt.yview)
        scrollbar.pack(side="right", fill="y")
        txt.config(yscrollcommand=scrollbar.set)

        self.widgets["txt_comms"] = txt

        # Start expanded (COMMS visible)
        self._apply_comms_state(initial=True)

        return drawer

    def _toggle_comms_drawer(self):
        self._comms_collapsed = not getattr(self, "_comms_collapsed", True)
        self._apply_comms_state()
        self._apply_window_size_for_comms_state()

    def _apply_comms_state(self, initial: bool = False):
        """
        Collapsed: short textbox height.
        Expanded: taller textbox height.
        """
        txt = self.widgets.get("txt_comms")
        if not txt:
            return

        if getattr(self, "_comms_collapsed", True):
            # Collapsed
            self._btn_comms_toggle.configure(text="▸")
            txt.configure(height=5)
            # Keep it visually compact
            if not initial:
                self.root.update_idletasks()
        else:
            self._btn_comms_toggle.configure(text="▾")
            txt.configure(height=12)
            if not initial:
                self.root.update_idletasks()

    def _build_status_panel(self, parent=None):
        """Build status information panel"""
        parent = parent or getattr(self, "body", None) or self.root
        panel = tk.LabelFrame(
            parent,
            text="STATUS",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            relief="ridge",
            bd=2
        )
        panel.pack(fill="x", padx=10, pady=5)
        
        # Grid layout for status fields
        fields = [
            ("SCAN:", "lbl_scan_status"),
            ("JOURNAL:", "lbl_journal"),
            ("CMDR:", "lbl_cmdr"),
            ("SIGNAL:", "lbl_signal"),
            ("SKIPPED:", "lbl_skipped"),
        ]
        
        for idx, (label_text, widget_name) in enumerate(fields):
            row = idx // 2
            col = (idx % 2) * 2
            
            tk.Label(
                panel,
                text=label_text,
                font=("Consolas", 9),
                fg=self.colors["MUTED"],
                bg=self.colors["BG_PANEL"]
            ).grid(row=row, column=col, sticky="e", padx=(10, 5), pady=5)
            
            label = tk.Label(
                panel,
                text="-",
                font=("Consolas", 9),
                fg=self.colors["TEXT"],
                bg=self.colors["BG_PANEL"]
            )
            label.grid(row=row, column=col+1, sticky="w", padx=(0, 20), pady=5)
            
            self.widgets[widget_name] = label
    
    def _build_target_lock(self, parent=None, visible=True):
        """Build target lock readout panel"""
        parent = parent or getattr(self, "body", None) or self.root
        panel = tk.LabelFrame(
            parent,
            text="TARGET LOCK",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            relief="solid",
            bd=1
        )
        # Important: allow this panel to expand vertically so we don't get a
        # dead "empty band" between the main panels and the COMMS drawer.
        # Parent already has padding via grid.
        # Keep this panel content-sized vertically (compact HUD).
        panel.pack(fill="x", expand=False, padx=0, pady=0)
        
        # System and Body
        info_frame = tk.Frame(panel, bg=self.colors["BG_PANEL"])
        info_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(
            info_frame,
            text="SYSTEM:",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(side="left", padx=(0, 5))
        
        lbl_sys = tk.Label(
            info_frame,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_sys.pack(side="left", padx=(0, 20))
        
        tk.Label(
            info_frame,
            text="BODY:",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(side="left", padx=(0, 5))
        
        lbl_body = tk.Label(
            info_frame,
            text="-",
            font=("Consolas", 9, "bold"),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_body.pack(side="left")
        
        # Badges (TYPE, RATING, WORTH)
        badge_frame = tk.Frame(panel, bg=self.colors["BG_PANEL"])
        badge_frame.pack(fill="x", padx=10, pady=5)
        
        badges = [
            ("lbl_badge_type", "TYPE: -"),
            ("lbl_badge_rating", "RATING: -"),
            ("lbl_badge_worth", "WORTH: -"),
        ]
        
        for widget_name, default_text in badges:
            badge = tk.Label(
                badge_frame,
                text=default_text,
                font=("Consolas", 8),
                fg=self.colors["TEXT"],
                bg=self.colors["BG_FIELD"],
                relief="solid",
                bd=1,
                padx=8,
                pady=4
            )
            badge.pack(side="left", padx=5)
            self.widgets[widget_name] = badge
        
        # Reason text
        lbl_reason = tk.Label(
            panel,
            text="-",
            font=("Consolas", 9),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"],
            wraplength=900,
            justify="left"
        )
        lbl_reason.pack(fill="x", padx=10, pady=5)
        
        # Inara link
        lbl_inara = tk.Label(
            panel,
            text="-",
            font=("Consolas", 8),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"],
            cursor="hand2"
        )
        lbl_inara.pack(fill="x", padx=10, pady=(0, 5))
        
        # Similarity breakdown section (hidden by default)
        similarity_frame = tk.Frame(panel, bg=self.colors["BG_FIELD"])
        
        similarity_title = tk.Label(
            similarity_frame,
            text="━━━ EARTH SIMILARITY ━━━",
            font=("Consolas", 9, "bold"),
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_FIELD"]
        )
        similarity_title.pack(pady=(5, 3))
        
        # Score and category
        lbl_similarity_score = tk.Label(
            similarity_frame,
            text="Score: -",
            font=("Consolas", 9, "bold"),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"]
        )
        lbl_similarity_score.pack(pady=2)
        
        lbl_similarity_category = tk.Label(
            similarity_frame,
            text="Category: -",
            font=("Consolas", 9),
            fg=self.colors["GREEN"],
            bg=self.colors["BG_FIELD"]
        )
        lbl_similarity_category.pack(pady=2)
        
        # Metrics breakdown (grid)
        metrics_frame = tk.Frame(similarity_frame, bg=self.colors["BG_FIELD"])
        metrics_frame.pack(fill="x", padx=10, pady=5)
        
        # Create labels for metrics (will be populated dynamically)
        lbl_similarity_metrics = tk.Label(
            metrics_frame,
            text="",
            font=("Consolas", 8),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"],
            justify="left",
            anchor="w"
        )
        lbl_similarity_metrics.pack(fill="x")
        
        # Store references
        self.widgets["similarity_frame"] = similarity_frame
        self.widgets["lbl_similarity_score"] = lbl_similarity_score
        self.widgets["lbl_similarity_category"] = lbl_similarity_category
        self.widgets["lbl_similarity_metrics"] = lbl_similarity_metrics
        
        # Goldilocks habitability section (hidden by default)
        goldilocks_frame = tk.Frame(panel, bg=self.colors["BG_FIELD"])
        
        goldilocks_title = tk.Label(
            goldilocks_frame,
            text="━━━ HABITABILITY ━━━",
            font=("Consolas", 9, "bold"),
            fg=self.colors["GREEN"],
            bg=self.colors["BG_FIELD"]
        )
        goldilocks_title.pack(pady=(5, 3))
        
        # Goldilocks score
        lbl_goldilocks_score = tk.Label(
            goldilocks_frame,
            text="Goldilocks: -",
            font=("Consolas", 9, "bold"),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"]
        )
        lbl_goldilocks_score.pack(pady=2)
        
        lbl_goldilocks_category = tk.Label(
            goldilocks_frame,
            text="Category: -",
            font=("Consolas", 9),
            fg=self.colors["GREEN"],
            bg=self.colors["BG_FIELD"]
        )
        lbl_goldilocks_category.pack(pady=2)
        
        # Goldilocks breakdown
        goldilocks_metrics_frame = tk.Frame(goldilocks_frame, bg=self.colors["BG_FIELD"])
        goldilocks_metrics_frame.pack(fill="x", padx=10, pady=5)
        
        lbl_goldilocks_metrics = tk.Label(
            goldilocks_metrics_frame,
            text="",
            font=("Consolas", 8),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"],
            justify="left",
            anchor="w"
        )
        lbl_goldilocks_metrics.pack(fill="x")
        
        # Store references
        self.widgets["goldilocks_frame"] = goldilocks_frame
        self.widgets["lbl_goldilocks_score"] = lbl_goldilocks_score
        self.widgets["lbl_goldilocks_category"] = lbl_goldilocks_category
        self.widgets["lbl_goldilocks_metrics"] = lbl_goldilocks_metrics

        # Store references
        self.widgets["lbl_sys"] = lbl_sys
        # Presenter compatibility aliases
        self.widgets["lbl_target_system"] = lbl_sys
        self.widgets["lbl_body"] = lbl_body
        # Presenter compatibility aliases
        self.widgets["lbl_target_body"] = lbl_body
        self.widgets["lbl_reason"] = lbl_reason
        self.widgets["lbl_inara"] = lbl_inara
    
    def _build_statistics_panel(self, parent=None):
        """Build statistics and ratings panel"""
        parent = parent or getattr(self, "body", None) or self.root
        panel = tk.LabelFrame(
            parent,
            text="STATISTICS",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            relief="solid",
            bd=1
        )
        # Same as Target Lock: stretch into available vertical space.
        # Keep this panel content-sized vertically (compact HUD).
        panel.pack(fill="x", expand=False, padx=0, pady=0)
        
        # Session stats
        session_frame = tk.Frame(panel, bg=self.colors["BG_PANEL"])
        session_frame.pack(fill="x", padx=10, pady=5)
        
        session_labels = [
            ("lbl_sess_time", "Session: 0h 0m"),
            ("lbl_sess_candidates", "Candidates: 0"),
            ("lbl_sess_systems", "Systems: 0"),
            ("lbl_sess_scanned", "Bodies Scanned: 0"),
            ("lbl_sess_rate", "Rate: 0.0/hour"),
        ]
        
        for widget_name, default_text in session_labels:
            label = tk.Label(
                session_frame,
                text=default_text,
                font=("Consolas", 9),
                fg=self.colors["TEXT"],
                bg=self.colors["BG_PANEL"]
            )
            label.pack(side="left", padx=10)
            self.widgets[widget_name] = label
        
        # Rating bars
        rating_frame = tk.Frame(panel, bg=self.colors["BG_PANEL"])
        rating_frame.pack(fill="x", padx=10, pady=5)

        # Session coverage (sampling phase)
        tk.Label(
            rating_frame,
            text="Session Coverage:",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=5, pady=(5, 2))

        session_coverage_canvas = tk.Canvas(
            rating_frame,
            height=20,
            bg=self.colors["BG_FIELD"],
            highlightthickness=0
        )
        session_coverage_canvas.pack(fill="x", padx=5, pady=2)

        lbl_session_coverage = tk.Label(
            rating_frame,
            text="Coverage (session): Aimless  0 / 10 candidates",
            font=("Consolas", 8),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_session_coverage.pack(anchor="w", padx=5, pady=2)
        
        # All-time coverage (total sampling depth)
        tk.Label(
            rating_frame,
            text="All-Time Coverage:",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=5, pady=(10, 2))

        alltime_coverage_canvas = tk.Canvas(
            rating_frame,
            height=20,
            bg=self.colors["BG_FIELD"],
            highlightthickness=0
        )
        alltime_coverage_canvas.pack(fill="x", padx=5, pady=2)

        lbl_alltime_coverage = tk.Label(
            rating_frame,
            text="Coverage (all-time): Aimless  0 / 10 candidates",
            font=("Consolas", 8),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_alltime_coverage.pack(anchor="w", padx=5, pady=2)
        
        # Store references
        self.widgets["session_coverage_canvas"] = session_coverage_canvas
        self.widgets["lbl_session_coverage"] = lbl_session_coverage
        self.widgets["alltime_coverage_canvas"] = alltime_coverage_canvas
        self.widgets["lbl_alltime_coverage"] = lbl_alltime_coverage
    
    def _build_comms_panel(self, parent=None):
        """Build COMMS feed panel"""
        parent = parent or getattr(self, "body", None) or self.root
        panel = tk.LabelFrame(
            parent,
            text="COMMS",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"],
            relief="ridge",
            bd=2
        )
        panel.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Scrollbar and text widget
        scrollbar = tk.Scrollbar(panel, bg=self.colors["BG_PANEL"])
        scrollbar.pack(side="right", fill="y")
        
        txt_comms = tk.Text(
            panel,
            font=("Consolas", 9),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_FIELD"],
            state="disabled",
            wrap="word",
            yscrollcommand=scrollbar.set
        )
        txt_comms.pack(fill="both", expand=True, padx=5, pady=5)
        
        scrollbar.config(command=txt_comms.yview)
        
        self.widgets["txt_comms"] = txt_comms
    
    def _build_controls(self):
        """Build control buttons"""
        control_frame = tk.Frame(self.root, bg=self.colors["BG"])
        control_frame.pack(fill="x", padx=10, pady=5)

        # Export dropdown (consolidates CSV/DB/XLSX into one button)
        export_btn = tk.Menubutton(
            control_frame,
            text="Export ▾",
            font=self.fonts["UI"],
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            activebackground=self.colors["BG_PANEL"],
            activeforeground=self.colors["TEXT"],
            relief="raised",
            bd=1,
            direction="below"
        )

        export_menu = tk.Menu(
            export_btn,
            tearoff=0,
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            activebackground=self.colors["ORANGE"],
            activeforeground="#000000"
        )
        export_menu.add_command(label="Export All (Choose Folder)...", command=self._on_export_all_clicked)
        export_menu.add_separator()
        export_menu.add_command(label="CSV", command=self._on_export_csv_clicked)
        export_menu.add_command(label="Database", command=self._on_export_db_clicked)
        export_menu.add_command(label="Density XLSX", command=self._on_export_density_xlsx_clicked)

        export_btn.config(menu=export_menu)
        export_btn.pack(side="left", padx=5)
        btn_rescan = tk.Button(
            control_frame,
            text="Rescan Current Journal",
            font=self.fonts["UI"],
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=self._on_rescan_clicked
        )
        btn_rescan.pack(side="left", padx=5)

        btn_import = tk.Button(
            control_frame,
            text="Import All Journals",
            font=self.fonts["UI"],
            bg=self.colors["ORANGE"],
            fg="#000000",
            command=self._on_import_journals_clicked,
            cursor="hand2"
        )
        btn_import.pack(side="left", padx=5)

        # Push utility buttons to the right
        spacer = tk.Frame(control_frame, bg=self.colors["BG"])
        spacer.pack(side="left", expand=True, fill="x")

        btn_about = tk.Button(
            control_frame,
            text="About",
            font=self.fonts["UI"],
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=self._on_about_clicked,
            cursor="hand2"
        )
        btn_about.pack(side="right", padx=5)

        btn_options = tk.Button(
            control_frame,
            text="Options",
            font=self.fonts["UI"],
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=self._on_options_clicked,
            cursor="hand2"
        )
        btn_options.pack(side="right", padx=5)


        # Flat button styling (no 3D relief)
        self._style_button(export_btn)
        self._style_button(btn_rescan)
        self._style_button(btn_import, accent=True)
        self._style_button(btn_options)
        self._style_button(btn_about)
        self.widgets["btn_export_menu"] = export_btn
        self.widgets["btn_rescan"] = btn_rescan
        self.widgets["btn_import"] = btn_import
        self.widgets["btn_options"] = btn_options
        self.widgets["btn_about"] = btn_about

    
    def _build_footer(self):
        """Build footer with summary statistics"""
        footer = tk.Frame(self.root, bg=self.colors["BG_PANEL"], height=30)
        footer.pack(fill="x", padx=10, pady=(5, 10))
        footer.pack_propagate(False)
        
        lbl_sb_left = tk.Label(
            footer,
            text="ELW: 0",
            font=("Consolas", 9),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_sb_left.pack(side="left", padx=10)
        
        lbl_sb_main = tk.Label(
            footer,
            text="Earth Search 2.0: No candidates logged yet",
            font=("Consolas", 9),
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_sb_main.pack(side="left", expand=True)
        
        lbl_sb_right = tk.Label(
            footer,
            text="Terraformable: 0",
            font=("Consolas", 9),
            fg=self.colors["TEXT"],
            bg=self.colors["BG_PANEL"]
        )
        lbl_sb_right.pack(side="right", padx=10)
        
        self.widgets["lbl_sb_left"] = lbl_sb_left
        self.widgets["lbl_sb_main"] = lbl_sb_main
        self.widgets["lbl_sb_right"] = lbl_sb_right
    
    # ========================================================================
    # UPDATE METHODS - Called by Presenter
    # ========================================================================
    
    def update_feed_status(self, status_text: str, led_color: str):
        """Update feed status and LED indicator"""
        self._update_if_changed("lbl_feed", "text", f"DATA FEED: {status_text}", "feed_text")
        
        if self._ui_cache.get("led_col") != led_color:
            self._ui_cache["led_col"] = led_color
            try:
                self.widgets["led_canvas"].itemconfigure(self.widgets["led_dot"], fill=led_color)
            except Exception:
                pass
    
    def update_status_panel(self, status_data: Dict[str, str]):
        """Update status panel fields"""
        mapping = {
            "scan_status": "lbl_scan_status",
            "journal": "lbl_journal",
            "cmdr_name": "lbl_cmdr",
            "signal": "lbl_signal",
            "skipped": "lbl_skipped",
        }
        
        for key, widget_name in mapping.items():
            if key in status_data:
                value = status_data[key] or "-"
                self._update_if_changed(widget_name, "text", value, f"status_{key}")
    
    def update_target_lock(self, target_data: Dict[str, str]):
        """Update target lock panel"""
        # System and body
        self._update_if_changed("lbl_sys", "text", target_data.get("system", "-"), "target_sys")
        self._update_if_changed("lbl_body", "text", target_data.get("body", "-"), "target_body")
        
        # Badges
        badge_type = f"TYPE: {target_data.get('type', '-')}"
        badge_rating = f"RATING: {target_data.get('rating', '-')}"
        badge_worth = f"WORTH: {target_data.get('worth', '-')}"
        
        self._update_if_changed("lbl_badge_type", "text", badge_type, "badge_type")
        self._update_if_changed("lbl_badge_rating", "text", badge_rating, "badge_rating")
        self._update_if_changed("lbl_badge_worth", "text", badge_worth, "badge_worth")
        
        # Badge colors
        self._update_badge_colors(target_data.get("rating"), target_data.get("worth"))
        

        # Inline TARGET line in HUD strip
        try:
            sysname = target_data.get('system', '-') or '-'
            ttype = target_data.get('type', '-') or '-'
            rating = target_data.get('rating', '-') or '-'
            worth = target_data.get('worth', '-') or '-'
            line = f"{sysname}   |   TYPE: {ttype}   RATING: {rating}   WORTH: {worth}"
            self._update_if_changed('lbl_target_line', 'text', line, 'target_line')
        except Exception:
            pass

        # Reason and link
        self._update_if_changed("lbl_reason", "text", target_data.get("reason", "-"), "target_reason")
        self._update_if_changed("lbl_inara", "text", target_data.get("inara_link", "-"), "target_inara")
        
        # Similarity breakdown (if available)
        similarity_score = target_data.get("similarity_score", -1)
        breakdown = target_data.get("similarity_breakdown", {})
        
        if similarity_score >= 0 and breakdown:
            # Show similarity frame
            self.widgets["similarity_frame"].pack(fill="x", padx=10, pady=5)
            
            # Update score and category
            score_text = f"Score: {similarity_score:.1f}"
            category_text = f"Category: {target_data.get('rating', '-')}"
            
            self._update_if_changed("lbl_similarity_score", "text", score_text, "sim_score")
            self._update_if_changed("lbl_similarity_category", "text", category_text, "sim_category")
            
            # Build metrics text
            metrics_lines = []
            
            if "gravity" in breakdown:
                g = breakdown["gravity"]
                metrics_lines.append(f"• Gravity:  {g['value']:.2f}{g['unit']} {g['indicator']}  (Earth: {g['target']:.2f}{g['unit']})")
            
            if "temperature" in breakdown:
                t = breakdown["temperature"]
                metrics_lines.append(f"• Temp:     {t['value']:.0f}{t['unit']} {t['indicator']}  (Earth: {t['target']:.0f}{t['unit']})")
            
            if "rotation" in breakdown:
                r = breakdown["rotation"]
                metrics_lines.append(f"• Day:      {r['value']:.1f}{r['unit']} {r['indicator']}  (Earth: {r['target']:.1f}{r['unit']})")
            
            if "pressure" in breakdown:
                p = breakdown["pressure"]
                metrics_lines.append(f"• Pressure: {p['value']:.2f}{p['unit']} {p['indicator']}  (Earth: {p['target']:.2f}{p['unit']})")
            
            if "tidal_lock" in breakdown:
                tl = breakdown["tidal_lock"]
                lock_text = "Locked" if tl["locked"] else "Not locked"
                metrics_lines.append(f"• Tidal:    {lock_text} {tl['indicator']}")
            
            metrics_text = "\n".join(metrics_lines)
            self._update_if_changed("lbl_similarity_metrics", "text", metrics_text, "sim_metrics")
        else:
            # Hide similarity frame if no data
            self.widgets["similarity_frame"].pack_forget()
        
        # Goldilocks breakdown (if available)
        goldilocks_score = target_data.get("goldilocks_score", -1)
        goldilocks_breakdown = target_data.get("goldilocks_breakdown", {})
        
        if goldilocks_score >= 0 and goldilocks_breakdown:
            # Show goldilocks frame
            self.widgets["goldilocks_frame"].pack(fill="x", padx=10, pady=5)
            
            # Update score and category
            stars = "⭐" * min(goldilocks_score // 3, 5)
            score_text = f"Goldilocks: {goldilocks_score}/16 {stars}"
            
            # Determine category from score
            if goldilocks_score == 16:
                category = "Perfect Goldilocks"
                cat_color = self.colors["GREEN"]
            elif goldilocks_score >= 14:
                category = "Excellent Habitat"
                cat_color = self.colors["GREEN"]
            elif goldilocks_score >= 12:
                category = "Very Good Habitat"
                cat_color = self.colors["ORANGE"]
            elif goldilocks_score >= 10:
                category = "Good Habitat"
                cat_color = self.colors["ORANGE"]
            else:
                category = "Acceptable Habitat"
                cat_color = self.colors["TEXT"]
            
            category_text = f"Category: {category}"
            
            self._update_if_changed("lbl_goldilocks_score", "text", score_text, "gold_score")
            self._update_if_changed("lbl_goldilocks_category", "text", category_text, "gold_category")
            
            # Update category color
            if self._ui_cache.get("gold_cat_color") != cat_color:
                self._ui_cache["gold_cat_color"] = cat_color
                self.widgets["lbl_goldilocks_category"].config(fg=cat_color)
            
            # Build metrics text
            metrics_lines = []
            
            if "temperature" in goldilocks_breakdown:
                t = goldilocks_breakdown["temperature"]
                metrics_lines.append(f"  Temperature:  {t['stars']} ({t['value']:.0f}{t['unit']})")
            
            if "gravity" in goldilocks_breakdown:
                g = goldilocks_breakdown["gravity"]
                metrics_lines.append(f"  Gravity:      {g['stars']} ({g['value']:.2f}{g['unit']})")
            
            if "pressure" in goldilocks_breakdown:
                p = goldilocks_breakdown["pressure"]
                metrics_lines.append(f"  Pressure:     {p['stars']} ({p['value']:.2f}{p['unit']})")
            
            if "day_length" in goldilocks_breakdown:
                d = goldilocks_breakdown["day_length"]
                if d.get("locked"):
                    metrics_lines.append(f"  Day Length:   {d['stars']} (Tidally Locked)")
                else:
                    metrics_lines.append(f"  Day Length:   {d['stars']} ({d['value']:.1f}{d['unit']})")
            
            metrics_text = "\n".join(metrics_lines)
            self._update_if_changed("lbl_goldilocks_metrics", "text", metrics_text, "gold_metrics")
        else:
            # Hide goldilocks frame if no data
            self.widgets["goldilocks_frame"].pack_forget()

    def update_statistics(self, stats_data: Dict[str, Any]):
        """Update statistics panel"""
        # Session stats
        self._update_if_changed("lbl_sess_time", "text", stats_data.get("session_time", "Session: 0h 0m"), "sess_time")
        self._update_if_changed("lbl_sess_candidates", "text", stats_data.get("session_candidates", "Candidates: 0"), "sess_candidates")
        self._update_if_changed("lbl_sess_systems", "text", stats_data.get("session_systems", "Systems: 0"), "sess_systems")
        self._update_if_changed("lbl_sess_scanned", "text", stats_data.get("session_scanned", "Bodies Scanned: 0"), "sess_scanned")
        self._update_if_changed("lbl_sess_rate", "text", stats_data.get("session_rate", "Rate: 0.0/hour"), "sess_rate")
        
        # Rating distributions
        if "session_candidate_count" in stats_data:
            self._draw_coverage_bar(
                self.widgets["session_coverage_canvas"],
                int(stats_data.get("session_candidate_count") or 0),
                self.widgets["lbl_session_coverage"],
                "session"
            )
        
        if "alltime_candidate_count" in stats_data:
            self._draw_coverage_bar(
                self.widgets["alltime_coverage_canvas"],
                int(stats_data.get("alltime_candidate_count") or 0),
                self.widgets["lbl_alltime_coverage"],
                "alltime"
            )

    def update_comms(self, messages: List[str]):
        """Update COMMS feed"""
        comms_text = "\n".join(messages) if messages else ""
        
        if self._ui_cache.get("comms") != comms_text:
            self._ui_cache["comms"] = comms_text
            
            # Check if scrolled to bottom
            try:
                at_bottom = self.widgets["txt_comms"].yview()[1] >= 0.99
            except Exception:
                at_bottom = True
            
            # Update text
            self.widgets["txt_comms"].config(state="normal")
            self.widgets["txt_comms"].delete("1.0", "end")
            self.widgets["txt_comms"].insert("1.0", comms_text)
            self.widgets["txt_comms"].config(state="disabled")
            
            # Auto-scroll if was at bottom
            if at_bottom:
                self.widgets["txt_comms"].see("end")
    
    def update_footer(self, total_all: int, total_elw: int, total_terraformable: int):
        """Update footer summary"""
        if total_all == 0:
            main_text = "Earth Search 2.0: No candidates logged yet"
        else:
            main_text = f"Earth Search 2.0: {total_all} candidate(s) logged"
        
        self._update_if_changed("lbl_sb_main", "text", main_text, "sb_main")
        self._update_if_changed("lbl_sb_left", "text", f"ELW: {total_elw}", "sb_left")
        self._update_if_changed("lbl_sb_right", "text", f"Terraformable: {total_terraformable}", "sb_right")
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _open_dw3_radio(self):
        """Open DW3 community radio in the user's default browser."""
        url = "https://distantworlds3.space/radio/"
        try:
            webbrowser.open(url, new=2)  # try new tab
            # If COMMS is present, drop a small breadcrumb.
            if "txt_comms" in self.widgets:
                try:
                    # This uses the existing COMMS update pipeline (model-driven),
                    # so we avoid directly inserting into the text widget here.
                    pass
                except Exception:
                    pass
        except Exception:
            # Fail silently: opening a browser shouldn't ever crash the logger.
            return
    
    def _update_if_changed(self, widget_name: str, property_name: str, new_value: Any, cache_key: str):
        """Update widget property only if value changed (optimization)"""
        if self._ui_cache.get(cache_key) != new_value:
            self._ui_cache[cache_key] = new_value
            try:
                widget = self.widgets.get(widget_name)
                if widget:
                    widget.config(**{property_name: new_value})
            except Exception:
                pass
    
    def _update_badge_colors(self, rating: Optional[str], worth: Optional[str]):
        """Update badge colors based on values"""
        # Rating badge colors (now using categories instead of A/B/C)
        if self._ui_cache.get("last_rating") != rating:
            self._ui_cache["last_rating"] = rating
            try:
                badge = self.widgets.get("lbl_badge_rating")
                if rating in ["Earth Twin", "Excellent"]:
                    badge.config(fg=self.colors["GREEN"], highlightbackground=self.colors["BORDER_INNER"])
                elif rating in ["Very Good", "Good"]:
                    badge.config(fg=self.colors["ORANGE"], highlightbackground=self.colors["ORANGE_DIM"])
                elif rating in ["Fair", "Marginal"]:
                    badge.config(fg=self.colors["TEXT"], highlightbackground=self.colors["BORDER_INNER"])
                else:
                    badge.config(fg=self.colors["MUTED"], highlightbackground=self.colors["BORDER_INNER"])
            except Exception:
                pass
        
        # Worth badge colors
        if self._ui_cache.get("last_worth") != worth:
            self._ui_cache["last_worth"] = worth
            try:
                badge = self.widgets.get("lbl_badge_worth")
                if (worth or "").lower() == "yes":
                    badge.config(fg=self.colors["GREEN"], highlightbackground=self.colors["BORDER_INNER"])
                elif (worth or "").lower() == "no":
                    badge.config(fg=self.colors["RED"], highlightbackground=self.colors["BORDER_INNER"])
                else:
                    badge.config(fg=self.colors["TEXT"], highlightbackground=self.colors["BORDER_INNER"])
            except Exception:
                pass
    
    def _draw_rating_bar(self, canvas: tk.Canvas, ratings: Dict[str, int], label: tk.Label, cache_prefix: str):
        """Draw rating distribution bar"""
        try:
            # Group categories by quality
            excellent = ratings.get("Earth Twin", 0) + ratings.get("Excellent", 0)
            good = ratings.get("Very Good", 0) + ratings.get("Good", 0)
            fair = ratings.get("Fair", 0) + ratings.get("Marginal", 0) + ratings.get("Poor", 0)
            unknown = ratings.get("Unknown", 0)
            
            total = excellent + good + fair + unknown
            
            # Check cache
            cache_key = f"{cache_prefix}_ratings"
            if self._ui_cache.get(cache_key) == (excellent, good, fair):
                return
            self._ui_cache[cache_key] = (excellent, good, fair)
            
            # Clear canvas
            canvas.delete("all")
            
            if total > 0:
                w = canvas.winfo_width() or 800
                h = canvas.winfo_height() or 20
                
                exc_w = int((excellent / total) * w)
                good_w = int((good / total) * w)
                fair_w = w - exc_w - good_w
                
                cur = 0
                if exc_w > 0:
                    canvas.create_rectangle(cur, 0, cur + exc_w, h, outline="", fill=self.colors["GREEN"])
                    cur += exc_w
                if good_w > 0:
                    canvas.create_rectangle(cur, 0, cur + good_w, h, outline="", fill=self.colors["ORANGE"])
                    cur += good_w
                if fair_w > 0:
                    canvas.create_rectangle(cur, 0, cur + fair_w, h, outline="", fill=self.colors["RED"])
            
            # Update label with detailed breakdown
            label_text = f"Ratings ({cache_prefix}): Excellent:{excellent}  Good:{good}  Fair:{fair}"
            label.config(text=label_text)
            
        except Exception as e:
            print(f"[VIEW ERROR] draw_rating_bar: {e}")
    

    def _draw_coverage_bar(self, canvas: tk.Canvas, candidate_count: int, label: tk.Label, cache_prefix: str):
        """Draw a single-bar session/all-time coverage indicator using Elite-flavored sampling phases."""
        try:
            tiers = [
                ("Aimless", 0, 9),
                ("Mostly Aimless", 10, 24),
                ("Scout", 25, 49),
                ("Surveyor", 50, 99),
                ("Trailblazer", 100, 199),
                ("Pathfinder", 200, 399),
                ("Ranger", 400, 699),
                ("Pioneer", 700, 999),
                ("Elite", 1000, None),
            ]

            # Determine tier
            name = "Aimless"
            start = 0
            end = 9
            for t_name, t_start, t_end in tiers:
                if t_end is None:
                    if candidate_count >= t_start:
                        name, start, end = t_name, t_start, t_end
                        break
                else:
                    if t_start <= candidate_count <= t_end:
                        name, start, end = t_name, t_start, t_end
                        break

            # Compute progress within tier
            if end is None:
                frac = 1.0
                tier_target = f"{start}+"
                progress_text = f"{candidate_count} / {tier_target}"
            else:
                tier_size = (end - start + 1)
                into_tier = max(0, candidate_count - start)
                frac = min(1.0, into_tier / float(tier_size))
                tier_target = end + 1
                progress_text = f"{candidate_count} / {tier_target}"

            # Cache
            cache_key = f"{cache_prefix}_coverage"
            cached = self._ui_cache.get(cache_key)
            cache_tuple = (candidate_count, name, start, end)
            if cached == cache_tuple:
                return
            self._ui_cache[cache_key] = cache_tuple

            # Draw bar
            canvas.delete("all")
            w = canvas.winfo_width() or 800
            h = canvas.winfo_height() or 20
            fill_w = int(frac * w)

            # Background (implicitly BG_FIELD), draw filled portion
            if fill_w > 0:
                canvas.create_rectangle(0, 0, fill_w, h, outline="", fill=self.colors.get("ORANGE_DIM", self.colors["ORANGE"]))

            # Label
            label.config(text=f"Coverage ({cache_prefix}): {name}  {progress_text} candidates")

        except Exception as e:
            print(f"[VIEW ERROR] draw_coverage_bar: {e}")

    # ========================================================================
    # EVENT HANDLERS - Call presenter callbacks
    # ========================================================================

    def show_options_dialog(self, *args, **kwargs) -> dict | None:
        """
        Show Options dialog.

        Returns a dict with:
          - data_dir: base folder for DB/logs/observer DB
          - export_dir: folder for CSV/DB exports
          - journal_dir: Elite Dangerous journal folder (optional)
          - hotkey_label: observer hotkey label (optional)
        or None if cancelled.
        """
        # Support both legacy and new calling conventions:
        #   1) show_options_dialog(export_dir, data_dir) -> returns dict
        #   2) show_options_dialog(settings_dict, hotkey, on_save) -> calls on_save(result)
        on_save_cb = None
        hotkey_value = None
        current_export_dir = ""
        current_data_dir = ""
        current_journal_dir = ""

        if args and not kwargs:
            if len(args) == 2 and all(isinstance(a, str) for a in args):
                current_export_dir, current_data_dir = args
            elif len(args) == 3 and isinstance(args[0], dict):
                settings = args[0] or {}
                hotkey_value = "" if args[1] is None else str(args[1])
                on_save_cb = args[2]
                current_export_dir = str(settings.get("export_dir") or settings.get("EXPORT_DIR") or settings.get("export") or "")
                current_data_dir = str(settings.get("data_dir") or settings.get("OUTDIR") or settings.get("data") or "")
                current_journal_dir = str(settings.get("journal_dir") or settings.get("JOURNAL_DIR") or settings.get("journal") or "")
            elif len(args) == 4 and all(isinstance(a, str) for a in args):
                current_export_dir, current_data_dir = args[0], args[1]
                hotkey_value = "" if args[2] is None else str(args[2])
                current_journal_dir = args[3]
            elif len(args) == 3 and all(isinstance(a, str) for a in args[:2]):
                current_export_dir, current_data_dir = args[0], args[1]
                hotkey_value = "" if args[2] is None else str(args[2])
            else:
                raise TypeError("show_options_dialog expected (export_dir, data_dir) or (settings_dict, hotkey, on_save)")
        else:
            # Keyword-friendly path (optional)
            current_export_dir = str(kwargs.get("export_dir", ""))
            current_data_dir = str(kwargs.get("data_dir", ""))
            current_journal_dir = str(kwargs.get("journal_dir", ""))
            hotkey_value = kwargs.get("hotkey", None)
            on_save_cb = kwargs.get("on_save", None)
        dlg = tk.Toplevel(self.root)
        dlg.title("Options")
        dlg.configure(bg=self.colors["BG_PANEL"])
        dlg.resizable(True, True)
        dlg.minsize(620, 320)
        dlg.transient(self.root)
        dlg.grab_set()
        self._apply_icon_to_window(dlg)

        # Center over parent
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + 80
        y = self.root.winfo_rooty() + 80

        # --- Data folder (DB/logs) ---
        tk.Label(
            dlg,
            text="Data folder (DB + logs) RESTART REQUIRED",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=12, pady=(12, 4))

        row_data = tk.Frame(dlg, bg=self.colors["BG_PANEL"])
        row_data.pack(fill="x", padx=12)

        var_data = tk.StringVar(value=current_data_dir or "")
        entry_data = tk.Entry(
            row_data,
            textvariable=var_data,
            font=("Consolas", 9),
            bg=self.colors["BG_FIELD"],
            fg=self.colors["TEXT"],
            insertbackground=self.colors["TEXT"],
            relief="solid",
            bd=1
        )
        entry_data.pack(side="left", fill="x", expand=True)

        def browse_data():
            chosen = filedialog.askdirectory(
                parent=dlg,
                initialdir=var_data.get() or None,
                title="Choose data folder (DB + logs)"
            )
            if chosen:
                var_data.set(chosen)

        tk.Button(
            row_data,
            text="Browse…",
            font=("Consolas", 9),
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=browse_data
        ).pack(side="left", padx=(8, 0))

        
        # --- Elite Dangerous Journal folder ---
        tk.Label(
            dlg,
            text="Elite Journal folder (Saved Games/Frontier Developments/Elite Dangerous)",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=12, pady=(12, 4))

        row_j = tk.Frame(dlg, bg=self.colors["BG_PANEL"])
        row_j.pack(fill="x", padx=12)

        var_journal = tk.StringVar(value=current_journal_dir or "")
        entry_j = tk.Entry(
            row_j,
            textvariable=var_journal,
            font=("Consolas", 9),
            bg=self.colors["BG_FIELD"],
            fg=self.colors["TEXT"],
            insertbackground=self.colors["TEXT"],
            relief="solid",
            bd=1
        )
        entry_j.pack(side="left", fill="x", expand=True)

        def browse_journal():
            chosen = filedialog.askdirectory(
                parent=dlg,
                initialdir=var_journal.get() or None,
                title="Choose Elite Dangerous Journal folder"
            )
            if chosen:
                var_journal.set(chosen)

        tk.Button(
            row_j,
            text="Browse…",
            font=("Consolas", 9),
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=browse_journal
        ).pack(side="left", padx=(8, 0))

        # --- Export folder ---
        tk.Label(
            dlg,
            text="Export folder (CSV + backups)",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=12, pady=(10, 4))

        row_exp = tk.Frame(dlg, bg=self.colors["BG_PANEL"])
        row_exp.pack(fill="x", padx=12)

        var_exp = tk.StringVar(value=current_export_dir or "")
        entry_exp = tk.Entry(
            row_exp,
            textvariable=var_exp,
            font=("Consolas", 9),
            bg=self.colors["BG_FIELD"],
            fg=self.colors["TEXT"],
            insertbackground=self.colors["TEXT"],
            relief="solid",
            bd=1
        )
        entry_exp.pack(side="left", fill="x", expand=True)

        def browse_export():
            chosen = filedialog.askdirectory(
                parent=dlg,
                initialdir=var_exp.get() or var_data.get() or None,
                title="Choose export folder"
            )
            if chosen:
                var_exp.set(chosen)

        tk.Button(
            row_exp,
            text="Browse…",
            font=("Consolas", 9),
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=browse_export
        ).pack(side="left", padx=(8, 0))

        # --- Hotkey (optional, used by newer presenter) ---
        tk.Label(
            dlg,
            text="Observer hotkey (e.g. Ctrl+Alt+O) RESTART REQUIRED",
            font=self.fonts["UI_SMALL_BOLD"],
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=12, pady=(12, 4))

        row_hot = tk.Frame(dlg, bg=self.colors["BG_PANEL"])
        row_hot.pack(fill="x", padx=12)

        if hotkey_value is None:
            hotkey_value = str(self.config.get("HOTKEY_OBSERVER", ""))
        var_hot = tk.StringVar(value=hotkey_value)
        entry_hot = tk.Entry(
            row_hot,
            textvariable=var_hot,
            width=28,
            font=self.fonts["UI_SMALL"],
            bg=self.colors["BG_FIELD"],
            fg=self.colors["TEXT"],
            insertbackground=self.colors["TEXT"]
        )
        entry_hot.pack(side="left")

        tk.Label(
            row_hot,
            text="(Use Ctrl/Alt/Shift + key or F1..F12)",
            font=("Consolas", 9),
            fg=self.colors["MUTED"],
            bg=self.colors["BG_PANEL"]
        ).pack(side="left", padx=(10, 0))
        # Buttons
        btns = tk.Frame(dlg, bg=self.colors["BG_PANEL"])
        btns.pack(fill="x", padx=12, pady=12)

        result: dict[str, str | None] = {"data_dir": None, "export_dir": None, "hotkey": None}

        def on_ok():
            data_dir = (var_data.get() or "").strip()
            export_dir = (var_exp.get() or "").strip()
            journal_dir = (var_journal.get() or "").strip()

            if not data_dir:
                messagebox.showwarning("Options", "Please choose a data folder.", parent=dlg)
                return

            # If export folder is empty, default to <data_dir>/exports
            if not export_dir:
                export_dir = str(Path(data_dir) / "exports")

            result["data_dir"] = data_dir
            result["export_dir"] = export_dir
            result["journal_dir"] = journal_dir or ""
            hotkey = (var_hot.get() or "").strip()
            result["hotkey_label"] = hotkey or None

            # If called with callback (newer presenter), notify it as well
            if on_save_cb:
                try:
                    on_save_cb({"data_dir": data_dir, "export_dir": export_dir, "journal_dir": journal_dir or "", "hotkey_label": hotkey or None})
                except TypeError:
                    # Backwards/alternate callback shapes
                    try:
                        on_save_cb(export_dir, data_dir, hotkey or None)
                    except TypeError:
                        on_save_cb(data_dir, export_dir, hotkey or None)
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        tk.Button(
            btns,
            text="Cancel",
            font=("Consolas", 9),
            bg=self.colors["BG_PANEL"],
            fg=self.colors["TEXT"],
            command=on_cancel
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            btns,
            text="Save",
            font=("Consolas", 9, "bold"),
            bg=self.colors["ORANGE"],
            fg="#000000",
            command=on_ok
        ).pack(side="right")

        # Size dialog to its content (avoid large empty bottom area)
        dlg.update_idletasks()
        req_w = max(620, dlg.winfo_reqwidth())
        req_h = max(320, dlg.winfo_reqheight())
        dlg.minsize(620, 320)
        dlg.geometry(f"{req_w}x{req_h}+{x}+{y}")


        entry_data.focus_set()
        self.root.wait_window(dlg)
        if result["data_dir"] and result["export_dir"]:
            # Always include journal_dir in the return payload.
            # Keep backward-compatible hotkey keys as well.
            payload = {
                "data_dir": result["data_dir"],
                "export_dir": result["export_dir"],
                "journal_dir": result.get("journal_dir", ""),
            }
            # Preserve legacy return shape unless hotkey/callback was used,
            # but if hotkey was used include it as well.
            if on_save_cb or hotkey_value is not None:
                payload["hotkey"] = result.get("hotkey")
                payload["hotkey_label"] = result.get("hotkey_label") or result.get("hotkey")
            # Regression guard: ensure required keys are present in the return payload.
            required_keys = {"data_dir", "export_dir", "journal_dir"}
            missing = required_keys.difference(payload.keys())
            if missing:
                # In dev (running from source), fail fast. In frozen EXE, warn instead.
                import sys
                msg = f"Options payload missing keys: {sorted(missing)}"
                if not getattr(sys, "frozen", False):
                    raise RuntimeError(msg)
                try:
                    self.add_comms_message(f"[WARN] {msg}")
                except Exception:
                    pass

            return payload
        return None
    def show_about_dialog(self, about_text: str, copy_text: str | None = None):
        """Show About dialog. If copy_text is provided, a 'Copy diagnostics' button is shown."""
        dlg = tk.Toplevel(self.root)
        dlg.title("About")
        dlg.configure(bg=self.colors["BG_PANEL"])
        dlg.resizable(True, True)
        dlg.minsize(620, 420)
        dlg.transient(self.root)
        dlg.grab_set()
        self._apply_icon_to_window(dlg)

        self.root.update_idletasks()
        x = self.root.winfo_rootx() + 90
        y = self.root.winfo_rooty() + 90
        dlg.geometry(f"620x360+{x}+{y}")

        tk.Label(
            dlg,
            text=f"{self.config.get('APP_NAME','App')} v{self.config.get('VERSION','')}",
            font=("Consolas", 12, "bold"),
            fg=self.colors["ORANGE"],
            bg=self.colors["BG_PANEL"]
        ).pack(anchor="w", padx=12, pady=(12, 6))

        txt = tk.Text(
            dlg,
            font=("Consolas", 9),
            bg=self.colors["BG_FIELD"],
            fg=self.colors["TEXT"],
            insertbackground=self.colors["TEXT"],
            height=14,
            width=74,
            relief="solid",
            bd=1
        )
        txt.pack(fill="both", expand=True, padx=12)
        txt.insert("1.0", about_text)
        txt.config(state="disabled")

        btns = tk.Frame(dlg, bg=self.colors["BG_PANEL"])
        btns.pack(fill="x", padx=12, pady=12)

        def copy_diag():
            if not copy_text:
                return
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(copy_text)
                messagebox.showinfo("About", "Diagnostics copied to clipboard.", parent=dlg)
            except Exception:
                messagebox.showwarning("About", "Could not copy to clipboard.", parent=dlg)

        if copy_text:
            tk.Button(
                btns,
                text="Copy diagnostics",
                font=("Consolas", 9),
                bg=self.colors["BG_PANEL"],
                fg=self.colors["TEXT"],
                command=copy_diag
            ).pack(side="left")

        tk.Button(
            btns,
            text="Close",
            font=("Consolas", 9, "bold"),
            bg=self.colors["ORANGE"],
            fg="#000000",
            command=dlg.destroy
        ).pack(side="right")

        self.root.wait_window(dlg)
    
    def _on_export_csv_clicked(self):
        """Handle export CSV button click"""
        if self.on_export_csv:
            self.on_export_csv()
    
    def _on_export_db_clicked(self):
        """Handle export DB button click"""
        if self.on_export_db:
            self.on_export_db()

    def _on_export_density_xlsx_clicked(self):
        """Handle export density worksheet XLSX button click"""
        if self.on_export_density_xlsx:
            self.on_export_density_xlsx()
    
    def _on_export_all_clicked(self):
        """Handle export all button click"""
        if self.on_export_all:
            self.on_export_all()
    
    def _on_rescan_clicked(self):
        """Handle rescan button click"""
        if self.on_rescan:
            self.on_rescan()
    
    def _on_import_journals_clicked(self):
        """Handle import journals button click"""
        if self.on_import_journals:
            self.on_import_journals()

    def _on_options_clicked(self):
        """Handle Options button click"""
        if self.on_options:
            self.on_options()

    def _on_about_clicked(self):
        """Handle About button click"""
        if self.on_about:
            self.on_about()
