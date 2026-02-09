"""
Dialog windows — Options, Hotkey, About.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Dict, Any, Optional, Callable


class OptionsDialog:
    """Options dialog for data/export/journal/hotkey settings."""

    def __init__(self, view):
        self.view = view

    def show(self, *args, **kwargs) -> Optional[dict]:
        view = self.view
        root = view.root
        colors = view.colors
        fonts = view.fonts
        config = view.config

        # --- Parse arguments (support legacy and new calling conventions) ---
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
            current_export_dir = str(kwargs.get("export_dir", ""))
            current_data_dir = str(kwargs.get("data_dir", ""))
            current_journal_dir = str(kwargs.get("journal_dir", ""))
            hotkey_value = kwargs.get("hotkey", None)
            on_save_cb = kwargs.get("on_save", None)

        dlg = tk.Toplevel(root)
        dlg.title("Options")
        dlg.configure(bg=colors["BG_PANEL"])
        dlg.resizable(True, True)
        dlg.minsize(620, 320)
        dlg.transient(root)
        dlg.grab_set()
        view._apply_icon_to_window(dlg)

        root.update_idletasks()
        x = root.winfo_rootx() + 80
        y = root.winfo_rooty() + 80

        # --- Data folder ---
        tk.Label(dlg, text="Data folder (DB + logs) RESTART REQUIRED",
                 font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", padx=12, pady=(12, 4))

        row_data = tk.Frame(dlg, bg=colors["BG_PANEL"])
        row_data.pack(fill="x", padx=12)

        var_data = tk.StringVar(value=current_data_dir or "")
        entry_data = tk.Entry(row_data, textvariable=var_data, font=("Consolas", 9),
                              bg=colors["BG_FIELD"], fg=colors["TEXT"],
                              insertbackground=colors["TEXT"], relief="solid", bd=1)
        entry_data.pack(side="left", fill="x", expand=True)

        def browse_data():
            chosen = filedialog.askdirectory(parent=dlg, initialdir=var_data.get() or None,
                                             title="Choose data folder (DB + logs)")
            if chosen:
                var_data.set(chosen)

        tk.Button(row_data, text="Browse…", font=("Consolas", 9),
                  bg=colors["BG_PANEL"], fg=colors["TEXT"], command=browse_data
                  ).pack(side="left", padx=(8, 0))

        # --- Journal folder ---
        tk.Label(dlg, text="Elite Journal folder (Saved Games/Frontier Developments/Elite Dangerous)",
                 font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", padx=12, pady=(12, 4))

        row_j = tk.Frame(dlg, bg=colors["BG_PANEL"])
        row_j.pack(fill="x", padx=12)

        var_journal = tk.StringVar(value=current_journal_dir or "")
        entry_j = tk.Entry(row_j, textvariable=var_journal, font=("Consolas", 9),
                           bg=colors["BG_FIELD"], fg=colors["TEXT"],
                           insertbackground=colors["TEXT"], relief="solid", bd=1)
        entry_j.pack(side="left", fill="x", expand=True)

        def browse_journal():
            chosen = filedialog.askdirectory(parent=dlg, initialdir=var_journal.get() or None,
                                             title="Choose Elite Dangerous Journal folder")
            if chosen:
                var_journal.set(chosen)

        tk.Button(row_j, text="Browse…", font=("Consolas", 9),
                  bg=colors["BG_PANEL"], fg=colors["TEXT"], command=browse_journal
                  ).pack(side="left", padx=(8, 0))

        # --- Export folder ---
        tk.Label(dlg, text="Export folder (CSV + backups)",
                 font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", padx=12, pady=(10, 4))

        row_exp = tk.Frame(dlg, bg=colors["BG_PANEL"])
        row_exp.pack(fill="x", padx=12)

        var_exp = tk.StringVar(value=current_export_dir or "")
        entry_exp = tk.Entry(row_exp, textvariable=var_exp, font=("Consolas", 9),
                             bg=colors["BG_FIELD"], fg=colors["TEXT"],
                             insertbackground=colors["TEXT"], relief="solid", bd=1)
        entry_exp.pack(side="left", fill="x", expand=True)

        def browse_export():
            chosen = filedialog.askdirectory(parent=dlg,
                                             initialdir=var_exp.get() or var_data.get() or None,
                                             title="Choose export folder")
            if chosen:
                var_exp.set(chosen)

        tk.Button(row_exp, text="Browse…", font=("Consolas", 9),
                  bg=colors["BG_PANEL"], fg=colors["TEXT"], command=browse_export
                  ).pack(side="left", padx=(8, 0))

        # --- Hotkey ---
        tk.Label(dlg, text="Observer hotkey (e.g. Ctrl+Alt+O) RESTART REQUIRED",
                 font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", padx=12, pady=(12, 4))

        row_hot = tk.Frame(dlg, bg=colors["BG_PANEL"])
        row_hot.pack(fill="x", padx=12)

        if hotkey_value is None:
            hotkey_value = str(config.get("HOTKEY_OBSERVER", ""))
        var_hot = tk.StringVar(value=hotkey_value)
        entry_hot = tk.Entry(row_hot, textvariable=var_hot, width=28,
                             font=fonts["UI_SMALL"], bg=colors["BG_FIELD"],
                             fg=colors["TEXT"], insertbackground=colors["TEXT"])
        entry_hot.pack(side="left")

        tk.Label(row_hot, text="(Use Ctrl/Alt/Shift + key or F1..F12)",
                 font=("Consolas", 9), fg=colors["MUTED"], bg=colors["BG_PANEL"]
                 ).pack(side="left", padx=(10, 0))

        # --- Buttons ---
        btns = tk.Frame(dlg, bg=colors["BG_PANEL"])
        btns.pack(fill="x", padx=12, pady=12)

        result: dict = {"data_dir": None, "export_dir": None, "hotkey": None}

        def on_ok():
            data_dir = (var_data.get() or "").strip()
            export_dir = (var_exp.get() or "").strip()
            journal_dir = (var_journal.get() or "").strip()

            if not data_dir:
                messagebox.showwarning("Options", "Please choose a data folder.", parent=dlg)
                return

            if not export_dir:
                export_dir = str(Path(data_dir) / "exports")

            result["data_dir"] = data_dir
            result["export_dir"] = export_dir
            result["journal_dir"] = journal_dir or ""
            hotkey = (var_hot.get() or "").strip()
            result["hotkey_label"] = hotkey or None

            if on_save_cb:
                try:
                    on_save_cb({"data_dir": data_dir, "export_dir": export_dir,
                                "journal_dir": journal_dir or "", "hotkey_label": hotkey or None})
                except TypeError:
                    try:
                        on_save_cb(export_dir, data_dir, hotkey or None)
                    except TypeError:
                        on_save_cb(data_dir, export_dir, hotkey or None)
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        tk.Button(btns, text="Cancel", font=("Consolas", 9),
                  bg=colors["BG_PANEL"], fg=colors["TEXT"], command=on_cancel
                  ).pack(side="right", padx=(6, 0))

        tk.Button(btns, text="Save", font=("Consolas", 9, "bold"),
                  bg=colors["ORANGE"], fg="#000000", command=on_ok
                  ).pack(side="right")

        dlg.update_idletasks()
        req_w = max(620, dlg.winfo_reqwidth())
        req_h = max(320, dlg.winfo_reqheight())
        dlg.minsize(620, 320)
        dlg.geometry(f"{req_w}x{req_h}+{x}+{y}")

        entry_data.focus_set()
        root.wait_window(dlg)

        if result["data_dir"] and result["export_dir"]:
            payload = {
                "data_dir": result["data_dir"],
                "export_dir": result["export_dir"],
                "journal_dir": result.get("journal_dir", ""),
            }
            if on_save_cb or hotkey_value is not None:
                payload["hotkey"] = result.get("hotkey")
                payload["hotkey_label"] = result.get("hotkey_label") or result.get("hotkey")

            required_keys = {"data_dir", "export_dir", "journal_dir"}
            missing = required_keys.difference(payload.keys())
            if missing:
                import sys
                msg = f"Options payload missing keys: {sorted(missing)}"
                if not getattr(sys, "frozen", False):
                    raise RuntimeError(msg)
            return payload
        return None


class HotkeyDialog:
    """Simplified hotkey-only settings dialog."""

    def __init__(self, view):
        self.view = view

    def show(self) -> Optional[str]:
        view = self.view
        root = view.root
        colors = view.colors
        fonts = view.fonts
        config = view.config

        current_hotkey = str(config.get("HOTKEY_OBSERVER", "") or config.get("HOTKEY_LABEL", "") or "Ctrl+Alt+O")

        dlg = tk.Toplevel(root)
        dlg.title("Hotkey Settings")
        dlg.configure(bg=colors["BG_PANEL"])
        dlg.transient(root)
        dlg.grab_set()
        view._apply_icon_to_window(dlg)

        main_frame = tk.Frame(dlg, bg=colors["BG_PANEL"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(main_frame, text="Observer Hotkey",
                 font=fonts["UI_SMALL_BOLD"], fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", pady=(0, 8))

        var_hot = tk.StringVar(value=current_hotkey)
        entry_hot = tk.Entry(main_frame, textvariable=var_hot, width=30,
                             font=("Consolas", 10), bg=colors["BG_FIELD"],
                             fg=colors["TEXT"], insertbackground=colors["TEXT"],
                             relief="solid", bd=1)
        entry_hot.pack(fill="x", pady=(0, 8))
        entry_hot.focus_set()

        tk.Label(main_frame,
                 text="Examples: Ctrl+Alt+O, Ctrl+Shift+F5, Alt+H\nUse Ctrl/Alt/Shift with a key or F1-F12",
                 font=("Consolas", 8), fg=colors["TEXT_DIM"], bg=colors["BG_PANEL"],
                 justify="left").pack(anchor="w", pady=(0, 12))

        tk.Label(main_frame,
                 text="\u26a0 Application restart required for changes to take effect",
                 font=("Consolas", 8, "bold"), fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", pady=(0, 16))

        result = {"hotkey": None}

        def on_save():
            hotkey = var_hot.get().strip()
            if hotkey:
                result["hotkey"] = hotkey
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btn_frame = tk.Frame(main_frame, bg=colors["BG_PANEL"])
        btn_frame.pack(fill="x")

        tk.Button(btn_frame, text="Save", font=("Consolas", 9, "bold"),
                  bg=colors["ORANGE"], fg="#000000", activebackground=colors["ORANGE_DIM"],
                  command=on_save, width=12).pack(side="left", padx=(0, 8))

        tk.Button(btn_frame, text="Cancel", font=("Consolas", 9),
                  bg=colors["BG_PANEL"], fg=colors["TEXT"],
                  command=on_cancel, width=12).pack(side="left")

        dlg.update_idletasks()
        root.update_idletasks()
        x = root.winfo_rootx() + 150
        y = root.winfo_rooty() + 150
        dlg.geometry(f"460x260+{x}+{y}")
        dlg.minsize(460, 260)
        dlg.resizable(False, False)

        entry_hot.bind("<Return>", lambda e: on_save())
        dlg.bind("<Escape>", lambda e: on_cancel())

        dlg.wait_window()
        return result.get("hotkey")


class AboutDialog:
    """About / diagnostics dialog."""

    def __init__(self, view):
        self.view = view

    def show(self, about_text: str, copy_text: Optional[str] = None):
        view = self.view
        root = view.root
        colors = view.colors
        config = view.config

        dlg = tk.Toplevel(root)
        dlg.title("About")
        dlg.configure(bg=colors["BG_PANEL"])
        dlg.resizable(True, True)
        dlg.minsize(620, 420)
        dlg.transient(root)
        dlg.grab_set()
        view._apply_icon_to_window(dlg)

        root.update_idletasks()
        x = root.winfo_rootx() + 90
        y = root.winfo_rooty() + 90
        dlg.geometry(f"620x360+{x}+{y}")

        tk.Label(dlg, text=f"{config.get('APP_NAME', 'App')} v{config.get('VERSION', '')}",
                 font=("Consolas", 12, "bold"), fg=colors["ORANGE"], bg=colors["BG_PANEL"]
                 ).pack(anchor="w", padx=12, pady=(12, 6))

        txt = tk.Text(dlg, font=("Consolas", 9), bg=colors["BG_FIELD"], fg=colors["TEXT"],
                      insertbackground=colors["TEXT"], height=14, width=74, relief="solid", bd=1)
        txt.pack(fill="both", expand=True, padx=12)
        txt.insert("1.0", about_text)
        txt.config(state="disabled")

        btns = tk.Frame(dlg, bg=colors["BG_PANEL"])
        btns.pack(fill="x", padx=12, pady=12)

        def copy_diag():
            if not copy_text:
                return
            try:
                root.clipboard_clear()
                root.clipboard_append(copy_text)
                messagebox.showinfo("About", "Diagnostics copied to clipboard.", parent=dlg)
            except Exception:
                messagebox.showwarning("About", "Could not copy to clipboard.", parent=dlg)

        if copy_text:
            tk.Button(btns, text="Copy diagnostics", font=("Consolas", 9),
                      bg=colors["BG_PANEL"], fg=colors["TEXT"], command=copy_diag
                      ).pack(side="left")

        tk.Button(btns, text="Close", font=("Consolas", 9, "bold"),
                  bg=colors["ORANGE"], fg="#000000", command=dlg.destroy
                  ).pack(side="right")

        root.wait_window(dlg)
