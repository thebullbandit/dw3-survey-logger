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
#   ui/view.py  (refactored from monolithic view.py)
#
# Connected modules (direct imports):
#   ui.theme, ui.widgets, ui.dialogs, ui.panels
# ============================================================================

import logging
import tkinter as tk
from pathlib import Path

logger = logging.getLogger("dw3.ui.view")
from tkinter import filedialog, messagebox
from typing import Optional, Dict, Any, Callable, List
import webbrowser

from ui.theme import UITheme
from ui.widgets import style_button
from ui.dialogs import OptionsDialog, HotkeyDialog, AboutDialog
from ui import panels as _panels


class Earth2View:
    """View layer - manages all UI components"""

    def __init__(self, root: tk.Tk, config: Dict[str, Any]):
        self.root = root
        self.config = config

        # UI state cache (for optimization)
        self._ui_cache = {}

        # Event callbacks (set by presenter)
        self.on_export_csv: Optional[Callable] = None
        self.on_export_db: Optional[Callable] = None
        self.on_export_density_xlsx: Optional[Callable] = None
        self.on_export_boxel_xlsx: Optional[Callable] = None
        self.on_export_all: Optional[Callable] = None
        self.on_export_diagnostics: Optional[Callable] = None
        self.on_rescan: Optional[Callable] = None
        self.on_import_journals: Optional[Callable] = None
        self.on_options: Optional[Callable] = None
        self.on_journal_folder: Optional[Callable] = None
        self.on_about: Optional[Callable] = None
        self.on_reset_observer_progress: Optional[Callable] = None

        # Widget references
        self.widgets = {}

        # Color scheme & fonts
        self.colors = UITheme.setup_colors(config)
        self.fonts = UITheme.setup_fonts(root)

        # Dialog helpers (lazy, share view state)
        self._options_dialog = OptionsDialog(self)
        self._hotkey_dialog = HotkeyDialog(self)
        self._about_dialog = AboutDialog(self)

    # ------------------------------------------------------------------
    # BUTTON STYLING  (delegates to ui.widgets)
    # ------------------------------------------------------------------
    def _style_button(self, btn: tk.Widget, *, accent: bool = False, success: bool = False):
        style_button(btn, self.colors, self.fonts, accent=accent, success=success)

    # ------------------------------------------------------------------
    # BUILD UI
    # ------------------------------------------------------------------
    def build_ui(self):
        """Build the complete UI"""
        self.root.title(f"{self.config['APP_NAME']} v{self.config['VERSION']}")

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        window_width = 650
        window_height = min(640, int(screen_height * 0.78))

        x_position = (screen_width - window_width) // 2
        y_position = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

        try:
            scale = float(self.root.tk.call("tk", "scaling"))
        except Exception:
            scale = 1.0
        min_w = int(580 * scale)
        min_h = int(440 * scale)
        self.root.minsize(min_w, min_h)

        self.root.configure(bg=self.colors["BG"])

        self._load_icon()

        self._build_header()
        self._build_controls()
        self._build_footer()

        # Body
        self.body = tk.Frame(self.root, bg=self.colors["BG"])
        self.body.pack(fill="both", expand=True)

        self.body.grid_rowconfigure(1, weight=0)
        self.body.grid_rowconfigure(2, weight=1)
        self.body.grid_columnconfigure(0, weight=3)
        self.body.grid_columnconfigure(1, weight=1)

        # HUD strip
        _panels.build_hud_strip(self, parent=self.body)
        self.widgets["hud_strip"].grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 6))

        # Statistics host
        stats_host = tk.Frame(self.body, bg=self.colors["BG"])
        stats_host.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        stats_host.grid_columnconfigure(0, weight=1)

        _panels.build_target_lock(self, parent=stats_host, visible=False)
        _panels.build_statistics_panel(self, parent=stats_host)

        # COMMS drawer
        _panels.build_comms_drawer(self, parent=self.body)
        self.widgets["comms_drawer"].grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 8))

        # Responsive text wrapping
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

        self._init_comms_window_behavior()

        return self.root

    # ------------------------------------------------------------------
    # WINDOW / COMMS DRAWER SIZE MANAGEMENT
    # ------------------------------------------------------------------
    def _init_comms_window_behavior(self):
        if getattr(self, "_comms_window_ready", False):
            return

        self._comms_collapsed = False
        self._apply_comms_state(initial=True)
        self.root.update_idletasks()

        w = self.root.winfo_width() or self.root.winfo_reqwidth()
        expanded_req_h = self.root.winfo_reqheight()
        expanded_h = max(self.root.winfo_height() or 0, expanded_req_h)

        self.root.geometry(f"{w}x{expanded_h}")
        self.root.update_idletasks()

        self._comms_expanded_height = self.root.winfo_height() or expanded_h

        self._comms_collapsed = True
        self._apply_comms_state(initial=True)
        self.root.update_idletasks()
        self._comms_collapsed_height = self.root.winfo_reqheight()

        self._comms_collapsed = False
        self._apply_comms_state(initial=True)
        self.root.update_idletasks()
        self.root.geometry(f"{w}x{self._comms_expanded_height}")
        self.root.update_idletasks()

        try:
            self.root.minsize(w, self._comms_expanded_height)
        except Exception:
            pass

        self._comms_window_ready = True

    def _apply_window_size_for_comms_state(self):
        if not getattr(self, "_comms_window_ready", False):
            return

        self.root.update_idletasks()
        w = self.root.winfo_width() or self.root.winfo_reqwidth()

        if getattr(self, "_comms_collapsed", True):
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

        try:
            self.root.geometry(f"{w}x{target_h}")
            self.root.update_idletasks()
            self.root.minsize(w, target_h)
            self.root.maxsize(w, target_h)
        except Exception:
            pass

    def _toggle_comms_drawer(self):
        self._comms_collapsed = not getattr(self, "_comms_collapsed", True)
        self._apply_comms_state()
        self._apply_window_size_for_comms_state()

    def _apply_comms_state(self, initial: bool = False):
        txt = self.widgets.get("txt_comms")
        if not txt:
            return

        if getattr(self, "_comms_collapsed", True):
            self._btn_comms_toggle.configure(text="▸")
            txt.configure(height=5)
            if not initial:
                self.root.update_idletasks()
        else:
            self._btn_comms_toggle.configure(text="▾")
            txt.configure(height=12)
            if not initial:
                self.root.update_idletasks()

    # ------------------------------------------------------------------
    # HEADER / CONTROLS / FOOTER  (kept inline — small & tightly coupled)
    # ------------------------------------------------------------------
    def _load_icon(self):
        try:
            icon_name = self.config.get("ICON_NAME", "earth2.ico")
            icon_path = self.config.get("ASSET_PATH", "") / icon_name
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _apply_icon_to_window(self, win):
        try:
            import sys, os
            base_dir = Path(getattr(sys, "_MEIPASS", os.path.abspath(".")))
            earth2_ico = base_dir / "assets" / "Earth2.ico"
            if earth2_ico.exists():
                win.iconbitmap(str(earth2_ico))
                return
            icon_name = self.config.get("ICON_NAME", "earth2.ico")
            asset_path = self.config.get("ASSET_PATH", None)
            if asset_path:
                icon_path = Path(asset_path) / icon_name
                if icon_path.exists():
                    win.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _build_header(self):
        header = tk.Frame(self.root, bg=self.colors["BG_PANEL"], height=50)
        header.pack(fill="x", padx=10, pady=(10, 5))
        header.pack_propagate(False)

        title_label = tk.Label(header,
                               text=f"{self.config['APP_NAME']} v{self.config['VERSION']}",
                               font=self.fonts["TITLE"], fg=self.colors["ORANGE"],
                               bg=self.colors["BG_PANEL"])
        title_label.pack(side="left", padx=12, pady=8)

        led_frame = tk.Frame(header, bg=self.colors["BG_PANEL"])
        led_frame.pack(side="right", padx=12)

        lbl_radio = tk.Label(led_frame, text="DW3 RADIO",
                             font=self.fonts["UI_SMALL_BOLD"], fg=self.colors["ORANGE"],
                             bg=self.colors["BG_PANEL"], cursor="hand2")
        lbl_radio.pack(side="left", padx=(0, 10))
        lbl_radio.bind("<Button-1>", lambda _e: self._open_dw3_radio())

        led_canvas = tk.Canvas(led_frame, width=20, height=20,
                               bg=self.colors["BG_PANEL"], highlightthickness=0)
        led_canvas.pack(side="left", padx=(0, 10))
        led_dot = led_canvas.create_oval(4, 4, 16, 16, fill=self.colors["LED_IDLE"], outline="")

        lbl_radio.bind("<Enter>", lambda _e: lbl_radio.config(fg=self.colors.get("TEXT", self.colors["ORANGE"])))
        lbl_radio.bind("<Leave>", lambda _e: lbl_radio.config(fg=self.colors["ORANGE"]))

        lbl_feed = tk.Label(led_frame, text="DATA FEED: INITIALIZING",
                            font=self.fonts["UI_SMALL"], fg=self.colors["TEXT"],
                            bg=self.colors["BG_PANEL"])
        lbl_feed.pack(side="left")

        self.widgets["header"] = header
        self.widgets["led_canvas"] = led_canvas
        self.widgets["led_dot"] = led_dot
        self.widgets["lbl_radio"] = lbl_radio
        self.widgets["lbl_feed"] = lbl_feed

    def _build_controls(self):
        control_frame = tk.Frame(self.root, bg=self.colors["BG"])
        control_frame.pack(fill="x", padx=10, pady=3)

        cmdr_container = tk.Frame(control_frame, bg=self.colors["BG"])
        cmdr_container.pack(side="left", padx=3)

        tk.Label(cmdr_container, text="CMDR:", font=("Consolas", 9),
                 fg=self.colors["MUTED"], bg=self.colors["BG"]).pack(side="left", padx=(0, 3))

        lbl_cmdr = tk.Label(cmdr_container, text="-", font=("Consolas", 9),
                            fg=self.colors["TEXT"], bg=self.colors["BG"])
        lbl_cmdr.pack(side="left")

        # Export dropdown
        export_btn = tk.Menubutton(control_frame, text="Export ▾", font=self.fonts["UI"],
                                   bg=self.colors["BG_PANEL"], fg=self.colors["TEXT"],
                                   activebackground=self.colors["BG_PANEL"],
                                   activeforeground=self.colors["TEXT"],
                                   relief="raised", bd=1, direction="below")
        export_menu = tk.Menu(export_btn, tearoff=0, bg=self.colors["BG_PANEL"],
                              fg=self.colors["TEXT"], activebackground=self.colors["ORANGE"],
                              activeforeground="#000000")
        export_menu.add_command(label="Export All (Choose Folder)...", command=self._on_export_all_clicked)
        export_menu.add_separator()
        export_menu.add_command(label="CSV", command=self._on_export_csv_clicked)
        export_menu.add_command(label="Database", command=self._on_export_db_clicked)
        export_menu.add_command(label="Density Sheet", command=self._on_export_density_xlsx_clicked)
        export_menu.add_command(label="Boxel Sheet", command=self._on_export_boxel_xlsx_clicked)
        export_btn.config(menu=export_menu)
        export_btn.pack(side="left", padx=3)

        # Options dropdown
        options_btn = tk.Menubutton(control_frame, text="Options ▾", font=self.fonts["UI"],
                                    bg=self.colors["BG_PANEL"], fg=self.colors["TEXT"],
                                    activebackground=self.colors["BG_PANEL"],
                                    activeforeground=self.colors["TEXT"],
                                    relief="raised", bd=1, direction="below")
        options_menu = tk.Menu(options_btn, tearoff=0, bg=self.colors["BG_PANEL"],
                               fg=self.colors["TEXT"], activebackground=self.colors["ORANGE"],
                               activeforeground="#000000")
        options_menu.add_command(label="Hotkey Settings...", command=self._on_options_clicked)
        options_menu.add_command(label="Journal Folder...", command=self._on_journal_folder_clicked)
        options_menu.add_command(label="Import All Journals", command=self._on_import_journals_clicked)
        options_menu.add_separator()
        options_menu.add_command(label="Backup Database", command=self._on_export_db_clicked)
        options_menu.add_separator()
        options_menu.add_command(label="Reset Observer Progress...", command=self._on_reset_observer_progress_clicked)
        options_menu.add_separator()
        options_menu.add_command(label="Export Diagnostics (ZIP)...", command=self._on_export_diagnostics_clicked)
        options_btn.config(menu=options_menu)
        options_btn.pack(side="left", padx=3)

        spacer = tk.Frame(control_frame, bg=self.colors["BG"])
        spacer.pack(side="left", expand=True, fill="x")

        btn_about = tk.Button(control_frame, text="About", font=self.fonts["UI"],
                              bg=self.colors["BG_PANEL"], fg=self.colors["TEXT"],
                              command=self._on_about_clicked, cursor="hand2")
        btn_about.pack(side="right", padx=3)

        self._style_button(export_btn)
        self._style_button(options_btn)
        self._style_button(btn_about)

        self.widgets["btn_export_menu"] = export_btn
        self.widgets["btn_options_menu"] = options_btn
        self.widgets["btn_about"] = btn_about
        self.widgets["lbl_cmdr"] = lbl_cmdr

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=self.colors["BG_PANEL"], height=30)
        footer.pack(fill="x", padx=10, pady=(5, 10))
        footer.pack_propagate(False)

        lbl_sb_left = tk.Label(footer, text="ELW: 0", font=("Consolas", 9),
                               fg=self.colors["TEXT"], bg=self.colors["BG_PANEL"])
        lbl_sb_left.pack(side="left", padx=10)

        lbl_sb_main = tk.Label(footer, text="Earth Search 2.0: No candidates logged yet",
                               font=("Consolas", 9), fg=self.colors["ORANGE"],
                               bg=self.colors["BG_PANEL"])
        lbl_sb_main.pack(side="left", expand=True)

        lbl_sb_right = tk.Label(footer, text="Terraformable: 0", font=("Consolas", 9),
                                fg=self.colors["TEXT"], bg=self.colors["BG_PANEL"])
        lbl_sb_right.pack(side="right", padx=10)

        self.widgets["lbl_sb_left"] = lbl_sb_left
        self.widgets["lbl_sb_main"] = lbl_sb_main
        self.widgets["lbl_sb_right"] = lbl_sb_right

    # ========================================================================
    # UPDATE METHODS - Called by Presenter
    # ========================================================================

    def update_feed_status(self, status_text: str, led_color: str):
        self._update_if_changed("lbl_feed", "text", f"DATA FEED: {status_text}", "feed_text")
        if self._ui_cache.get("led_col") != led_color:
            self._ui_cache["led_col"] = led_color
            try:
                self.widgets["led_canvas"].itemconfigure(self.widgets["led_dot"], fill=led_color)
            except Exception:
                pass

    def update_status_panel(self, status_data: Dict[str, str]):
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
        self._update_if_changed("lbl_sys", "text", target_data.get("system", "-"), "target_sys")
        self._update_if_changed("lbl_body", "text", target_data.get("body", "-"), "target_body")

        badge_type = f"TYPE: {target_data.get('type', '-')}"
        badge_rating = f"RATING: {target_data.get('rating', '-')}"
        badge_worth = f"WORTH: {target_data.get('worth', '-')}"

        self._update_if_changed("lbl_badge_type", "text", badge_type, "badge_type")
        self._update_if_changed("lbl_badge_rating", "text", badge_rating, "badge_rating")
        self._update_if_changed("lbl_badge_worth", "text", badge_worth, "badge_worth")

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

        self._update_if_changed("lbl_reason", "text", target_data.get("reason", "-"), "target_reason")
        self._update_if_changed("lbl_inara", "text", target_data.get("inara_link", "-"), "target_inara")

        # Similarity breakdown
        similarity_score = target_data.get("similarity_score", -1)
        breakdown = target_data.get("similarity_breakdown", {})

        if similarity_score >= 0 and breakdown:
            self.widgets["similarity_frame"].pack(fill="x", padx=10, pady=5)

            score_text = f"Score: {similarity_score:.1f}"
            category_text = f"Category: {target_data.get('rating', '-')}"
            self._update_if_changed("lbl_similarity_score", "text", score_text, "sim_score")
            self._update_if_changed("lbl_similarity_category", "text", category_text, "sim_category")

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
            self.widgets["similarity_frame"].pack_forget()

        # Goldilocks breakdown
        goldilocks_score = target_data.get("goldilocks_score", -1)
        goldilocks_breakdown = target_data.get("goldilocks_breakdown", {})

        if goldilocks_score >= 0 and goldilocks_breakdown:
            self.widgets["goldilocks_frame"].pack(fill="x", padx=10, pady=5)

            stars = "\u2b50" * min(goldilocks_score // 3, 5)
            score_text = f"Goldilocks: {goldilocks_score}/16 {stars}"

            if goldilocks_score == 16:
                category, cat_color = "Perfect Goldilocks", self.colors["GREEN"]
            elif goldilocks_score >= 14:
                category, cat_color = "Excellent Habitat", self.colors["GREEN"]
            elif goldilocks_score >= 12:
                category, cat_color = "Very Good Habitat", self.colors["ORANGE"]
            elif goldilocks_score >= 10:
                category, cat_color = "Good Habitat", self.colors["ORANGE"]
            else:
                category, cat_color = "Acceptable Habitat", self.colors["TEXT"]

            category_text = f"Category: {category}"
            self._update_if_changed("lbl_goldilocks_score", "text", score_text, "gold_score")
            self._update_if_changed("lbl_goldilocks_category", "text", category_text, "gold_category")

            if self._ui_cache.get("gold_cat_color") != cat_color:
                self._ui_cache["gold_cat_color"] = cat_color
                self.widgets["lbl_goldilocks_category"].config(fg=cat_color)

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
            self.widgets["goldilocks_frame"].pack_forget()

    def update_statistics(self, stats_data: Dict[str, Any]):
        self._update_if_changed("lbl_sess_time", "text", stats_data.get("session_time", "Session: 0h 0m"), "sess_time")
        self._update_if_changed("lbl_sess_candidates", "text", stats_data.get("session_candidates", "Candidates: 0"), "sess_candidates")
        self._update_if_changed("lbl_sess_systems", "text", stats_data.get("session_systems", "Systems: 0"), "sess_systems")
        self._update_if_changed("lbl_sess_scanned", "text", stats_data.get("session_scanned", "Bodies Scanned: 0"), "sess_scanned")
        self._update_if_changed("lbl_sess_rate", "text", stats_data.get("session_rate", "Rate: 0.0/hour"), "sess_rate")

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

    _URL_RE = None  # compiled on first use

    def update_comms(self, messages: List[str]):
        import re
        if self._URL_RE is None:
            Earth2View._URL_RE = re.compile(r'(https?://\S+)')

        comms_text = "\n".join(messages) if messages else ""
        if self._ui_cache.get("comms") != comms_text:
            self._ui_cache["comms"] = comms_text
            try:
                at_bottom = self.widgets["txt_comms"].yview()[1] >= 0.99
            except Exception:
                at_bottom = True
            txt = self.widgets["txt_comms"]
            txt.config(state="normal")
            txt.delete("1.0", "end")
            for i, line in enumerate(messages or []):
                if i > 0:
                    txt.insert("end", "\n")
                line_tag = self._comms_tag_for_line(line)
                # Split line on URLs so links get their own clickable tag
                parts = self._URL_RE.split(line)
                for part in parts:
                    if self._URL_RE.fullmatch(part):
                        # Create a unique tag per URL for the click binding
                        url_tag = f"url_{id(part)}_{i}"
                        txt.tag_configure(url_tag, foreground="#5599ff", underline=True)
                        txt.tag_bind(url_tag, "<Button-1>", lambda e, u=part: self._open_url(u))
                        txt.tag_bind(url_tag, "<Enter>", lambda e: txt.config(cursor="hand2"))
                        txt.tag_bind(url_tag, "<Leave>", lambda e: txt.config(cursor=""))
                        tags = (url_tag,)
                    else:
                        tags = (line_tag,) if line_tag else ()
                    txt.insert("end", part, tags)
            txt.config(state="disabled")
            if at_bottom:
                txt.see("end")

    @staticmethod
    def _open_url(url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    @staticmethod
    def _comms_tag_for_line(line: str) -> str:
        """Return a tag name based on the message prefix, or empty string."""
        upper = line.upper()
        if "[ERROR]" in upper or "ERROR]" in upper or "[✗]" in upper:
            return "error"
        if "[WARNING]" in upper or "[WARN]" in upper:
            return "warning"
        if "[✓]" in upper or "SAVED" in upper or "EXPORTED" in upper or "EDITED" in upper:
            return "success"
        return ""

    def update_footer(self, total_all: int, total_elw: int, total_terraformable: int):
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
        try:
            webbrowser.open("https://distantworlds3.space/radio/", new=2)
        except Exception:
            return

    def _update_if_changed(self, widget_name: str, property_name: str, new_value: Any, cache_key: str):
        if self._ui_cache.get(cache_key) != new_value:
            self._ui_cache[cache_key] = new_value
            try:
                widget = self.widgets.get(widget_name)
                if widget:
                    widget.config(**{property_name: new_value})
            except Exception:
                pass

    def _update_badge_colors(self, rating: Optional[str], worth: Optional[str]):
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
        try:
            excellent = ratings.get("Earth Twin", 0) + ratings.get("Excellent", 0)
            good = ratings.get("Very Good", 0) + ratings.get("Good", 0)
            fair = ratings.get("Fair", 0) + ratings.get("Marginal", 0) + ratings.get("Poor", 0)
            unknown = ratings.get("Unknown", 0)
            total = excellent + good + fair + unknown

            cache_key = f"{cache_prefix}_ratings"
            if self._ui_cache.get(cache_key) == (excellent, good, fair):
                return
            self._ui_cache[cache_key] = (excellent, good, fair)

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

            label_text = f"Ratings ({cache_prefix}): Excellent:{excellent}  Good:{good}  Fair:{fair}"
            label.config(text=label_text)
        except Exception as e:
            logger.error("draw_rating_bar: %s", e)

    def _draw_coverage_bar(self, canvas: tk.Canvas, candidate_count: int, label: tk.Label, cache_prefix: str):
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

            name, start, end = "Aimless", 0, 9
            for t_name, t_start, t_end in tiers:
                if t_end is None:
                    if candidate_count >= t_start:
                        name, start, end = t_name, t_start, t_end
                        break
                else:
                    if t_start <= candidate_count <= t_end:
                        name, start, end = t_name, t_start, t_end
                        break

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

            cache_key = f"{cache_prefix}_coverage"
            cached = self._ui_cache.get(cache_key)
            cache_tuple = (candidate_count, name, start, end)
            if cached == cache_tuple:
                return
            self._ui_cache[cache_key] = cache_tuple

            canvas.delete("all")
            w = canvas.winfo_width() or 800
            h = canvas.winfo_height() or 20
            fill_w = int(frac * w)

            if fill_w > 0:
                canvas.create_rectangle(0, 0, fill_w, h, outline="", fill=self.colors.get("ORANGE_DIM", self.colors["ORANGE"]))

            label.config(text=f"Coverage ({cache_prefix}): {name}  {progress_text} candidates")
        except Exception as e:
            logger.error("draw_coverage_bar: %s", e)

    # ========================================================================
    # DIALOGS  (delegate to ui.dialogs)
    # ========================================================================

    def show_options_dialog(self, *args, **kwargs):
        return self._options_dialog.show(*args, **kwargs)

    def show_hotkey_dialog(self) -> Optional[str]:
        return self._hotkey_dialog.show()

    def show_about_dialog(self, about_text: str, copy_text: Optional[str] = None):
        return self._about_dialog.show(about_text, copy_text)

    # ========================================================================
    # EVENT HANDLERS - Call presenter callbacks
    # ========================================================================

    def _on_export_csv_clicked(self):
        if self.on_export_csv:
            self.on_export_csv()

    def _on_export_db_clicked(self):
        if self.on_export_db:
            self.on_export_db()

    def _on_export_density_xlsx_clicked(self):
        if self.on_export_density_xlsx:
            self.on_export_density_xlsx()

    def _on_export_boxel_xlsx_clicked(self):
        if self.on_export_boxel_xlsx:
            self.on_export_boxel_xlsx()

    def _on_export_all_clicked(self):
        if self.on_export_all:
            self.on_export_all()

    def _on_export_diagnostics_clicked(self):
        if self.on_export_diagnostics:
            self.on_export_diagnostics()

    def _on_rescan_clicked(self):
        if self.on_rescan:
            self.on_rescan()

    def _on_import_journals_clicked(self):
        if self.on_import_journals:
            self.on_import_journals()

    def _on_journal_folder_clicked(self):
        if self.on_journal_folder:
            self.on_journal_folder()

    def _on_options_clicked(self):
        if self.on_options:
            self.on_options()

    def _on_reset_observer_progress_clicked(self):
        if self.on_reset_observer_progress:
            self.on_reset_observer_progress()

    def _on_about_clicked(self):
        if self.on_about:
            self.on_about()
