"""
Panel builders — HUD strip, Target Lock, Statistics, COMMS, Status.

Each function takes the view instance and a parent widget, creates the panel,
registers widget references into ``view.widgets``, and returns the root frame.
"""

import tkinter as tk
import webbrowser
from typing import Dict, Any


# ============================================================================
# HUD STRIP
# ============================================================================

def build_hud_strip(view, parent: tk.Widget) -> tk.Frame:
    """Compact HUD strip (replaces the tall STATUS panel)."""
    colors = view.colors
    fonts = view.fonts

    hud = tk.Frame(parent, bg=colors["BG_PANEL"], bd=1, relief="solid")
    view.widgets["hud_strip"] = hud

    for i in range(4):
        hud.grid_columnconfigure(i, weight=1)

    def add_field(row, col, label_text, key):
        tk.Label(hud, text=label_text, font=("Consolas", 9),
                 fg=colors["MUTED"], bg=colors["BG_PANEL"]
                 ).grid(row=row, column=col, sticky="e", padx=(8, 3), pady=4)

        val = tk.Label(hud, text="-", font=("Consolas", 9),
                       fg=colors["TEXT"], bg=colors["BG_PANEL"], anchor="w")
        val.grid(row=row, column=col + 1, sticky="w", padx=(0, 10), pady=4)
        view.widgets[key] = val

    # Row 0
    add_field(0, 0, "SCAN:", "lbl_scan_status")
    add_field(0, 2, "JOURNAL:", "lbl_journal")

    # Row 1: Target line
    tk.Label(hud, text="TARGET:", font=("Consolas", 9),
             fg=colors["MUTED"], bg=colors["BG_PANEL"]
             ).grid(row=1, column=0, sticky="e", padx=(8, 3), pady=(0, 4))

    lbl_target_line = tk.Label(hud, text="-", font=("Consolas", 9),
                               fg=colors["TEXT"], bg=colors["BG_PANEL"], anchor="w")
    lbl_target_line.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=(0, 4))
    view.widgets["lbl_target_line"] = lbl_target_line

    # Row 2
    add_field(2, 0, "SIGNAL:", "lbl_signal")
    add_field(2, 2, "SKIPPED:", "lbl_skipped")

    view.widgets["hud_hint"] = tk.Label(hud, text="", font=("Consolas", 9),
                                        fg=colors["MUTED"], bg=colors["BG_PANEL"], anchor="e")
    view.widgets["hud_hint"].grid(row=2, column=4, columnspan=2, sticky="e", padx=(0, 12), pady=6)

    return hud


# ============================================================================
# TARGET LOCK
# ============================================================================

def build_target_lock(view, parent: tk.Widget, visible: bool = True) -> tk.LabelFrame:
    """Build target lock readout panel."""
    colors = view.colors
    fonts = view.fonts

    panel = tk.LabelFrame(parent, text="TARGET LOCK",
                          font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"],
                          bg=colors["BG_PANEL"], relief="solid", bd=1)
    panel.pack(fill="x", expand=False, padx=0, pady=0)

    # System and Body
    info_frame = tk.Frame(panel, bg=colors["BG_PANEL"])
    info_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(info_frame, text="SYSTEM:", font=("Consolas", 9),
             fg=colors["MUTED"], bg=colors["BG_PANEL"]).pack(side="left", padx=(0, 5))

    lbl_sys = tk.Label(info_frame, text="-", font=("Consolas", 9, "bold"),
                       fg=colors["TEXT"], bg=colors["BG_PANEL"])
    lbl_sys.pack(side="left", padx=(0, 20))

    tk.Label(info_frame, text="BODY:", font=("Consolas", 9),
             fg=colors["MUTED"], bg=colors["BG_PANEL"]).pack(side="left", padx=(0, 5))

    lbl_body = tk.Label(info_frame, text="-", font=("Consolas", 9, "bold"),
                        fg=colors["TEXT"], bg=colors["BG_PANEL"])
    lbl_body.pack(side="left")

    # Badges
    badge_frame = tk.Frame(panel, bg=colors["BG_PANEL"])
    badge_frame.pack(fill="x", padx=10, pady=5)

    badges = [
        ("lbl_badge_type", "TYPE: -"),
        ("lbl_badge_rating", "RATING: -"),
        ("lbl_badge_worth", "WORTH: -"),
    ]
    for widget_name, default_text in badges:
        badge = tk.Label(badge_frame, text=default_text, font=("Consolas", 8),
                         fg=colors["TEXT"], bg=colors["BG_FIELD"],
                         relief="solid", bd=1, padx=8, pady=4)
        badge.pack(side="left", padx=5)
        view.widgets[widget_name] = badge

    # Reason
    lbl_reason = tk.Label(panel, text="-", font=("Consolas", 9),
                          fg=colors["TEXT"], bg=colors["BG_PANEL"],
                          wraplength=900, justify="left")
    lbl_reason.pack(fill="x", padx=10, pady=5)

    # Inara link
    lbl_inara = tk.Label(panel, text="-", font=("Consolas", 8),
                         fg=colors["MUTED"], bg=colors["BG_PANEL"], cursor="hand2")
    lbl_inara.pack(fill="x", padx=10, pady=(0, 5))

    # Similarity breakdown (hidden by default)
    similarity_frame = tk.Frame(panel, bg=colors["BG_FIELD"])
    tk.Label(similarity_frame, text="━━━ EARTH SIMILARITY ━━━",
             font=("Consolas", 9, "bold"), fg=colors["ORANGE"],
             bg=colors["BG_FIELD"]).pack(pady=(5, 3))

    lbl_similarity_score = tk.Label(similarity_frame, text="Score: -",
                                    font=("Consolas", 9, "bold"), fg=colors["TEXT"],
                                    bg=colors["BG_FIELD"])
    lbl_similarity_score.pack(pady=2)

    lbl_similarity_category = tk.Label(similarity_frame, text="Category: -",
                                       font=("Consolas", 9), fg=colors["GREEN"],
                                       bg=colors["BG_FIELD"])
    lbl_similarity_category.pack(pady=2)

    metrics_frame = tk.Frame(similarity_frame, bg=colors["BG_FIELD"])
    metrics_frame.pack(fill="x", padx=10, pady=5)

    lbl_similarity_metrics = tk.Label(metrics_frame, text="", font=("Consolas", 8),
                                      fg=colors["TEXT"], bg=colors["BG_FIELD"],
                                      justify="left", anchor="w")
    lbl_similarity_metrics.pack(fill="x")

    view.widgets["similarity_frame"] = similarity_frame
    view.widgets["lbl_similarity_score"] = lbl_similarity_score
    view.widgets["lbl_similarity_category"] = lbl_similarity_category
    view.widgets["lbl_similarity_metrics"] = lbl_similarity_metrics

    # Goldilocks habitability (hidden by default)
    goldilocks_frame = tk.Frame(panel, bg=colors["BG_FIELD"])
    tk.Label(goldilocks_frame, text="━━━ HABITABILITY ━━━",
             font=("Consolas", 9, "bold"), fg=colors["GREEN"],
             bg=colors["BG_FIELD"]).pack(pady=(5, 3))

    lbl_goldilocks_score = tk.Label(goldilocks_frame, text="Goldilocks: -",
                                    font=("Consolas", 9, "bold"), fg=colors["TEXT"],
                                    bg=colors["BG_FIELD"])
    lbl_goldilocks_score.pack(pady=2)

    lbl_goldilocks_category = tk.Label(goldilocks_frame, text="Category: -",
                                       font=("Consolas", 9), fg=colors["GREEN"],
                                       bg=colors["BG_FIELD"])
    lbl_goldilocks_category.pack(pady=2)

    goldilocks_metrics_frame = tk.Frame(goldilocks_frame, bg=colors["BG_FIELD"])
    goldilocks_metrics_frame.pack(fill="x", padx=10, pady=5)

    lbl_goldilocks_metrics = tk.Label(goldilocks_metrics_frame, text="",
                                      font=("Consolas", 8), fg=colors["TEXT"],
                                      bg=colors["BG_FIELD"], justify="left", anchor="w")
    lbl_goldilocks_metrics.pack(fill="x")

    view.widgets["goldilocks_frame"] = goldilocks_frame
    view.widgets["lbl_goldilocks_score"] = lbl_goldilocks_score
    view.widgets["lbl_goldilocks_category"] = lbl_goldilocks_category
    view.widgets["lbl_goldilocks_metrics"] = lbl_goldilocks_metrics

    # Store references
    view.widgets["lbl_sys"] = lbl_sys
    view.widgets["lbl_target_system"] = lbl_sys
    view.widgets["lbl_body"] = lbl_body
    view.widgets["lbl_target_body"] = lbl_body
    view.widgets["lbl_reason"] = lbl_reason
    view.widgets["lbl_inara"] = lbl_inara

    return panel


# ============================================================================
# STATISTICS
# ============================================================================

def build_statistics_panel(view, parent: tk.Widget) -> tk.LabelFrame:
    """Build statistics and ratings panel."""
    colors = view.colors
    fonts = view.fonts

    panel = tk.LabelFrame(parent, text="STATISTICS",
                          font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"],
                          bg=colors["BG_PANEL"], relief="solid", bd=1)
    panel.pack(fill="x", expand=False, padx=0, pady=0)

    # Session stats
    session_frame = tk.Frame(panel, bg=colors["BG_PANEL"])
    session_frame.pack(fill="x", padx=10, pady=5)

    session_labels = [
        ("lbl_sess_time", "Session: 0h 0m"),
        ("lbl_sess_candidates", "Candidates: 0"),
        ("lbl_sess_systems", "Systems: 0"),
        ("lbl_sess_scanned", "Bodies Scanned: 0"),
        ("lbl_sess_rate", "Rate: 0.0/hour"),
    ]
    for widget_name, default_text in session_labels:
        label = tk.Label(session_frame, text=default_text, font=("Consolas", 9),
                         fg=colors["TEXT"], bg=colors["BG_PANEL"])
        label.pack(side="left", padx=10)
        view.widgets[widget_name] = label

    # Rating bars
    rating_frame = tk.Frame(panel, bg=colors["BG_PANEL"])
    rating_frame.pack(fill="x", padx=10, pady=5)

    # Session coverage
    tk.Label(rating_frame, text="Session Coverage:", font=("Consolas", 9),
             fg=colors["MUTED"], bg=colors["BG_PANEL"]).pack(anchor="w", padx=5, pady=(5, 2))

    session_coverage_canvas = tk.Canvas(rating_frame, height=20,
                                        bg=colors["BG_FIELD"], highlightthickness=0)
    session_coverage_canvas.pack(fill="x", padx=5, pady=2)

    lbl_session_coverage = tk.Label(rating_frame,
                                    text="Coverage (session): Aimless  0 / 10 candidates",
                                    font=("Consolas", 8), fg=colors["MUTED"],
                                    bg=colors["BG_PANEL"])
    lbl_session_coverage.pack(anchor="w", padx=5, pady=2)

    # All-time coverage
    tk.Label(rating_frame, text="All-Time Coverage:", font=("Consolas", 9),
             fg=colors["MUTED"], bg=colors["BG_PANEL"]).pack(anchor="w", padx=5, pady=(10, 2))

    alltime_coverage_canvas = tk.Canvas(rating_frame, height=20,
                                        bg=colors["BG_FIELD"], highlightthickness=0)
    alltime_coverage_canvas.pack(fill="x", padx=5, pady=2)

    lbl_alltime_coverage = tk.Label(rating_frame,
                                    text="Coverage (all-time): Aimless  0 / 10 candidates",
                                    font=("Consolas", 8), fg=colors["MUTED"],
                                    bg=colors["BG_PANEL"])
    lbl_alltime_coverage.pack(anchor="w", padx=5, pady=2)

    view.widgets["session_coverage_canvas"] = session_coverage_canvas
    view.widgets["lbl_session_coverage"] = lbl_session_coverage
    view.widgets["alltime_coverage_canvas"] = alltime_coverage_canvas
    view.widgets["lbl_alltime_coverage"] = lbl_alltime_coverage

    return panel


# ============================================================================
# COMMS DRAWER
# ============================================================================

def build_comms_drawer(view, parent: tk.Widget) -> tk.Frame:
    """Build a collapsible COMMS drawer."""
    colors = view.colors
    fonts = view.fonts

    drawer = tk.Frame(parent, bg=colors["BG_PANEL"], bd=1, relief="solid")
    view.widgets["comms_drawer"] = drawer

    # Title bar
    title = tk.Frame(drawer, bg=colors["BG_PANEL"])
    title.pack(fill="x")

    view._comms_collapsed = False

    view._btn_comms_toggle = tk.Button(
        title, text="▾", font=fonts["UI_SMALL_BOLD"],
        fg=colors["ORANGE"], bg=colors["BG_PANEL"],
        activebackground=colors["BG_PANEL"], activeforeground=colors["ORANGE"],
        bd=0, relief="flat", command=view._toggle_comms_drawer)
    view._btn_comms_toggle.pack(side="left", padx=(8, 6), pady=4)

    tk.Label(title, text="COMMS", font=fonts["UI_SMALL_BOLD"],
             fg=colors["ORANGE"], bg=colors["BG_PANEL"]).pack(side="left", pady=4)

    # Content area
    view._comms_content = tk.Frame(drawer, bg=colors["BG_PANEL"])
    view._comms_content.pack(fill="x", padx=6, pady=(0, 6))

    txt = tk.Text(view._comms_content, height=12, wrap="word", font=("Consolas", 9),
                  fg=colors["TEXT"], bg=colors["BG_FIELD"],
                  insertbackground=colors["TEXT"], relief="sunken", bd=1)
    txt.pack(side="left", fill="x", expand=True)

    scrollbar = tk.Scrollbar(view._comms_content, command=txt.yview)
    scrollbar.pack(side="right", fill="y")
    txt.config(yscrollcommand=scrollbar.set)

    # Color tags for comms messages
    txt.tag_configure("error", foreground=colors["RED"])
    txt.tag_configure("success", foreground=colors["GREEN"])
    txt.tag_configure("warning", foreground=colors["ORANGE"])
    txt.tag_configure("link", foreground="#5599ff", underline=True)

    view.widgets["txt_comms"] = txt

    view._apply_comms_state(initial=True)

    return drawer


# ============================================================================
# COMMS PANEL (legacy, unused in current layout but kept for compatibility)
# ============================================================================

def build_comms_panel(view, parent: tk.Widget):
    """Build COMMS feed panel (legacy layout)."""
    colors = view.colors
    fonts = view.fonts

    panel = tk.LabelFrame(parent, text="COMMS", font=fonts["UI_SMALL_BOLD"],
                          fg=colors["ORANGE"], bg=colors["BG_PANEL"],
                          relief="ridge", bd=2)
    panel.pack(fill="both", expand=True, padx=10, pady=5)

    scrollbar = tk.Scrollbar(panel, bg=colors["BG_PANEL"])
    scrollbar.pack(side="right", fill="y")

    txt_comms = tk.Text(panel, font=("Consolas", 9), fg=colors["TEXT"],
                        bg=colors["BG_FIELD"], state="disabled", wrap="word",
                        yscrollcommand=scrollbar.set)
    txt_comms.pack(fill="both", expand=True, padx=5, pady=5)
    scrollbar.config(command=txt_comms.yview)

    # Color tags for comms messages
    txt_comms.tag_configure("error", foreground=colors["RED"])
    txt_comms.tag_configure("success", foreground=colors["GREEN"])
    txt_comms.tag_configure("warning", foreground=colors["ORANGE"])
    txt_comms.tag_configure("link", foreground="#5599ff", underline=True)

    view.widgets["txt_comms"] = txt_comms


# ============================================================================
# STATUS PANEL (legacy, replaced by HUD strip)
# ============================================================================

def build_status_panel(view, parent: tk.Widget):
    """Build status information panel (legacy layout)."""
    colors = view.colors
    fonts = view.fonts

    panel = tk.LabelFrame(parent, text="STATUS", font=fonts["UI_SMALL_BOLD"],
                          fg=colors["ORANGE"], bg=colors["BG_PANEL"],
                          relief="ridge", bd=2)
    panel.pack(fill="x", padx=10, pady=5)

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

        tk.Label(panel, text=label_text, font=("Consolas", 9),
                 fg=colors["MUTED"], bg=colors["BG_PANEL"]
                 ).grid(row=row, column=col, sticky="e", padx=(10, 5), pady=5)

        label = tk.Label(panel, text="-", font=("Consolas", 9),
                         fg=colors["TEXT"], bg=colors["BG_PANEL"])
        label.grid(row=row, column=col + 1, sticky="w", padx=(0, 20), pady=5)
        view.widgets[widget_name] = label
