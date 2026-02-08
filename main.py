# ============================================================================
# CACHE CLEANUP (must run before any project imports)
# ============================================================================
import shutil
import os
from pathlib import Path

_app_dir = Path(__file__).parent
for _cache_dir in _app_dir.rglob("__pycache__"):
    try:
        shutil.rmtree(_cache_dir)
    except Exception:
        pass

# ============================================================================
# IMPORTS
# ============================================================================

import logging
import threading
import tkinter as tk
from utils import resource_path
import sys
import json
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dw3.main")

from earth2_database import Earth2Database
from model import Earth2Model
from ui import Earth2View
from presenter import Earth2Presenter
from journal_monitor import JournalMonitor
from journal_state_manager import JournalStateManager
from observer_storage import ObserverStorage
from observer_overlay import ObserverOverlay
from observer_models import ObserverNote, SliceStatus, SurveyType
from ui.survey_selector import SurveySelector
from typing import Dict


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_config() -> dict:
    """
    Get application configuration.

    All user settings are stored in a single file at a stable location
    (~/.dw3_survey_logger/settings.json) so the user can relocate OUTDIR
    without losing preferences.
    """
    import os
    import json
    from pathlib import Path

    # Prefer USERPROFILE on Windows, but never allow it to become "." (Path(""))
    userprofile_env = os.environ.get("USERPROFILE")
    USERPROFILE = Path(userprofile_env) if userprofile_env else Path.home()

    # Bootstrap settings (stable location so users can relocate OUTDIR safely)
    # Windows: %USERPROFILE%/.dw3_survey_logger/settings.json
    # Linux/macOS: ~/.dw3_survey_logger/settings.json
    BOOTSTRAP_SETTINGS_PATH = Path.home() / ".dw3_survey_logger" / "settings.json"

    # Default storage directory (can be overridden by bootstrap settings)
    OUTDIR = USERPROFILE / "Documents" / "DW3" / "Earth2"

    # Bootstrap overrides
    bootstrap_data_dir = None
    bootstrap_export_dir = None
    bootstrap_hotkey_label = None
    bootstrap_journal_dir = None

    try:
        if BOOTSTRAP_SETTINGS_PATH.exists():
            data = json.loads(BOOTSTRAP_SETTINGS_PATH.read_text(encoding="utf-8"))
            bootstrap_data_dir = data.get("data_dir")
            bootstrap_export_dir = data.get("export_dir")
            bootstrap_hotkey_label = data.get("hotkey_label")
            bootstrap_journal_dir = data.get("journal_dir")
    except Exception as e:
        # optional; ignore corrupted/missing
        logger.warning("Failed to load bootstrap settings: %s", e)
        pass

    if bootstrap_data_dir:
        OUTDIR = Path(os.path.expandvars(str(bootstrap_data_dir))).expanduser()

    # Default Elite journal path
    default_journal = USERPROFILE / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
    JOURNAL_DIR = (
        Path(os.path.expandvars(str(bootstrap_journal_dir))).expanduser()
        if bootstrap_journal_dir
        else default_journal
    )

    # Base config
    config = {
        # Application info
        "APP_NAME": "DW3 Survey Logger",
        "VERSION": "0.9.17",

        # Hotkey
        "HOTKEY_LABEL": bootstrap_hotkey_label or "Ctrl+Alt+O",

        # Paths
        "JOURNAL_DIR": JOURNAL_DIR,
        "OUTDIR": OUTDIR,
        "EXPORT_DIR": OUTDIR / "exports",
        "BOOTSTRAP_SETTINGS_PATH": BOOTSTRAP_SETTINGS_PATH,
        "DB_PATH": OUTDIR / "DW3_Earth2.db",
        "OUTCSV": OUTDIR / "exports",
        "LOGFILE": OUTDIR / "DW3_Earth2_Logger.log",
        "ASSET_PATH": resource_path("assets"),
        "ICON_NAME": "earth2.ico",

        # Monitoring settings
        "POLL_SECONDS_FAST": 0.1,
        "POLL_SECONDS_SLOW": 0.5,
        "TEST_MODE": False,
        "TEST_READ_FROM_START": True,

        # UI settings
        "UI_REFRESH_FAST_MS": 100,
        "UI_REFRESH_SLOW_MS": 250,
        "COMMS_MAX_LINES": 150,

        # Rating criteria
        "TEMP_A_MIN": 240.0,
        "TEMP_A_MAX": 320.0,
        "TEMP_B_MIN": 200.0,
        "TEMP_B_MAX": 360.0,
        "GRAV_A_MIN": 0.80,
        "GRAV_A_MAX": 1.30,
        "GRAV_B_MIN": 0.50,
        "GRAV_B_MAX": 1.80,
        "DIST_A_MAX": 5000.0,
        "DIST_B_MAX": 15000.0,

        # Worth landing criteria
        "WORTH_DIST_MAX": 8000.0,
        "WORTH_TEMP_MIN": 210.0,
        "WORTH_TEMP_MAX": 340.0,
        "WORTH_GRAV_MAX": 1.60,

        # Color scheme (DO NOT REMOVE)
        "BG": "#0a0a0f",
        "BG_PANEL": "#12121a",
        "BG_FIELD": "#1a1a28",
        "TEXT": "#e0e0ff",
        "MUTED": "#6a6a8a",
        "BORDER_OUTER": "#2a2a3f",
        "BORDER_INNER": "#1f1f2f",
        "ORANGE": "#ff8833",
        "ORANGE_DIM": "#cc6622",
        "GREEN": "#44ff88",
        "RED": "#ff4444",
        "LED_ACTIVE": "#00ff88",
        "LED_IDLE": "#888888",
    }

    # Apply bootstrap export_dir override
    if bootstrap_export_dir:
        try:
            exp = Path(os.path.expandvars(str(bootstrap_export_dir))).expanduser()
            config["EXPORT_DIR"] = exp
            config["OUTCSV"] = exp
        except Exception as e:
            logger.warning("Failed to apply export_dir override: %s", e)
            pass

    return config

# ============================================================================
# APPLICATION SETUP
# ============================================================================

def main():
    """Main application entry point"""

    # Get configuration
    config = get_config()

    # Ensure output directory exists
    config["OUTDIR"].mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------
    # Initialize critical objects to None so shutdown is always safe
    # --------------------------------------------------------------------
    root = None
    db = None
    observer_storage = None
    state_manager = None
    model = None
    view = None
    presenter = None
    journal_monitor = None
    # Dictionary of overlays keyed by SurveyType - allows multiple windows open simultaneously
    observer_overlays: Dict[SurveyType, ObserverOverlay] = {}
    global_hotkey_handle = None

    # Initialize database (DB worker thread)
    try:
        db = Earth2Database(config["DB_PATH"])
        logger.info("Database initialized: %s", config['DB_PATH'])
    except Exception as e:
        import traceback
        logger.error("Database initialization failed: %s", e)
        traceback.print_exc()
        db = None


    if db is None:
        logger.info("Cannot start without a working database. Exiting.")
        return

    # ========================================================================
    # CREATE OBSERVER STORAGE (Step 3a)
    # ========================================================================
    observer_db_path = config["OUTDIR"] / "DW3_Earth2_Observations.db"
    try:
        observer_storage = ObserverStorage(observer_db_path)
        logger.info("Observer storage initialized: %s", observer_db_path)
        # NOTE: presenter is created later; observer_storage will be passed into presenter constructor.
    except Exception as e:
        logger.error("Observer storage initialization failed: %s", e)
        observer_storage = None

    # ========================================================================
    # CREATE JOURNAL STATE MANAGER (Step 3b)
    # ========================================================================
    state_manager = JournalStateManager()
    logger.info("Journal state manager initialized")
    logger.info("Auto-export on COMPLETE: disabled")


    # Create Tkinter root
    root = tk.Tk()

    # ========================================================================
    # CREATE MVP COMPONENTS (Step 1)
    # ========================================================================
    model = Earth2Model(db, config)
    view = Earth2View(root, config)
    presenter = Earth2Presenter(model, view, config, observer_storage=observer_storage)
    # Bind observer storage to model for exporter/guards
    try:
        model.observer_db = observer_storage
    except Exception as e:
        logger.debug("model.observer_db assignment: %s", e)
        pass
    # Ensure presenter has observer_storage even if constructed differently
    try:
        presenter.observer_storage = observer_storage
    except Exception as e:
        logger.debug("presenter.observer_storage assignment: %s", e)
        pass

    def _cleanup_databases():
        """Close databases on early exit."""
        try:
            if db:
                db.close()
        except Exception as e:
            logger.debug("Early cleanup: db.close: %s", e)
        try:
            if observer_storage:
                observer_storage.close()
        except Exception as e:
            logger.debug("Early cleanup: observer_storage.close: %s", e)

    # Build UI
    try:
        view.build_ui()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Startup Error", f"Failed to build UI:\n\n{e}\n\nPlease report this on GitHub.")
        except Exception as e2:
            logger.debug("messagebox.showerror failed: %s", e2)
            pass
        _cleanup_databases()
        return

    # Start presenter (begins UI refresh loop)
    try:
        presenter.start()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("Startup Error", f"Failed to start presenter:\n\n{e}\n\nPlease report this on GitHub.")
        except Exception as e2:
            logger.debug("messagebox.showerror failed: %s", e2)
            pass
        _cleanup_databases()
        return

    # ========================================================================
    # CREATE JOURNAL MONITOR (Step 2) - Now with state_manager
    # ========================================================================
    journal_monitor = JournalMonitor(
        journal_dir=config["JOURNAL_DIR"],
        model=model,
        presenter=presenter,
        config=config,
        state_manager=state_manager  # Pass state manager for overlay integration
    )

    # Start journal monitoring
    journal_monitor.start()

    # ========================================================================
    # CREATE OBSERVER OVERLAY (Step 3c)
    # ========================================================================

    def on_observation_saved(note: ObserverNote):
        """Callback when observation is saved from overlay"""
        if observer_storage:
            try:
                note_id = observer_storage.save(note)

                # Update Z-target tracking
                try:
                    state_manager.set_last_sample_z_bin(note.z_bin)
                except Exception as e:
                    logger.debug("set_last_sample_z_bin failed: %s", e)
                    pass

                # Friendly status labels for comms
                _status_labels = {
                    SliceStatus.IN_PROGRESS: "Sample in Progress",
                    SliceStatus.COMPLETE: "Density Sample Complete o7",
                    SliceStatus.PARTIAL: "Sample Partial",
                    SliceStatus.DISCARD: "Sample Discarded",
                }
                status_text = _status_labels.get(note.slice_status, note.slice_status.value)

                if note.sample_index is not None:
                    presenter.add_comms_message(
                        f"[OBSERVER] Density sample saved: Sample #{note.sample_index} | System #{note.system_index} | {status_text}"
                    )
                else:
                    presenter.add_comms_message(
                        f"[OBSERVER] Density sample saved: {status_text}"
                    )

                logger.info("Observation saved with ID: %s", note_id)


            except Exception as e:
                presenter.add_comms_message(f"[OBSERVER ERROR] Failed to save {e}")
        else:
            presenter.add_comms_message("[OBSERVER ERROR] Storage not available")


    # Overlays are created on-demand when user selects a survey type
    # Define callbacks that will be attached to each overlay when created

    def on_boxel_saved(entry: dict):
        """Save a boxel entry to the separate boxel table."""
        try:
            if not observer_storage:
                presenter.add_comms_message("[OBSERVER ERROR] Storage not available for boxel save")
                return
            cmdr = (model.get_status("cmdr_name") or "").strip() or "UnknownCMDR"
            entry["cmdr_name"] = cmdr
            observer_storage.save_boxel_entry(entry)
            presenter.add_comms_message(f"[OBSERVER] Boxel entry saved: {entry.get('boxel_highest_system', '')}")
        except Exception as e:
            presenter.add_comms_message(f"[OBSERVER ERROR] Boxel save failed: {e}")

    def on_observation_edited(note: ObserverNote):
        """Callback when observation is edited/amended from overlay"""
        if note.sample_index is not None:
            presenter.add_comms_message(
                f"[OBSERVER] Sample #{note.sample_index} edited successfully"
            )
        else:
            presenter.add_comms_message("[OBSERVER] Observation edited successfully")

    def open_observer_overlay():
        """Open the observer overlay with current context after survey type selection.

        Allows multiple survey windows to be open simultaneously (one per survey type).
        """
        nonlocal observer_overlays

        # Show survey type selector first
        selector = SurveySelector(root, {
            "BG": config.get("BG", "#0a0a0f"),
            "BG_PANEL": config.get("BG_PANEL", "#12121a"),
            "BG_FIELD": config.get("BG_FIELD", "#1a1a28"),
            "TEXT": config.get("TEXT", "#e0e0ff"),
            "MUTED": config.get("MUTED", "#6a6a8a"),
            "BORDER_OUTER": config.get("BORDER_OUTER", "#2a2a3f"),
            "ORANGE": config.get("ORANGE", "#ff8833"),
        })
        survey_type = selector.show()

        # User cancelled
        if survey_type is None:
            return

        context = state_manager.get_context()

        # Check if we already have an overlay for this survey type
        existing_overlay = observer_overlays.get(survey_type)

        if existing_overlay is not None and existing_overlay.is_visible():
            # Overlay already open - just focus it and update context
            try:
                existing_overlay.session_id = getattr(journal_monitor, "current_session_id", None) or ""
            except Exception as e:
                logger.debug("Observer session_id update failed: %s", e)
            existing_overlay.show(context)
            presenter.add_comms_message(f"[OBSERVER] Focused existing {survey_type.value} overlay")
            return

        # Create new overlay for this survey type
        try:
            new_overlay = ObserverOverlay(
                root,
                config,
                get_context_fn=state_manager.get_context,
                on_save=on_observation_saved,
                session_id=(getattr(journal_monitor, "current_session_id", None) or ""),
                app_version=str(config.get("VERSION") or ""),
                observer_storage=observer_storage,
                survey_type=survey_type,
            )
            # Set up callbacks
            new_overlay.on_save_boxel = on_boxel_saved
            new_overlay.on_export = presenter.handle_export_density_xlsx
            new_overlay.on_export_boxel = presenter.handle_export_boxel_xlsx
            new_overlay.on_edit = on_observation_edited
            new_overlay.hotkey_hint = hotkey_hint_text

            # Store in dictionary
            observer_overlays[survey_type] = new_overlay

        except Exception as e:
            presenter.add_comms_message(f"[OBSERVER ERROR] Failed to create overlay: {e}")
            return

        new_overlay.show(context)

        # Log which survey type was selected
        survey_names = {
            SurveyType.REGULAR_DENSITY: "Regular Density",
            SurveyType.LOGARITHMIC_DENSITY: "Logarithmic Density",
            SurveyType.BOXEL_SIZE: "Boxel Size",
        }
        presenter.add_comms_message(f"[OBSERVER] {survey_names.get(survey_type, 'Survey')} overlay opened")

    # Add button to control frame
    btn_observation = tk.Button(
        view.widgets.get("btn_export_menu", view.root).master if view.widgets.get("btn_export_menu") else view.root,  # Control frame parent
        text="Add Observation",
        font=("Consolas", 9),
        bg=config["GREEN"],
        fg="#000000",
        command=open_observer_overlay,
        cursor="hand2"
    )
    btn_observation.pack(side="left", padx=5)

    from hotkey_manager import try_register_global_hotkey

    # Preferred hotkey label (user-configurable via Options)
    # Default chosen to (Ctrl+Shift+O).
    from hotkey_manager import parse_hotkey_label

    HOTKEY_LABEL = str(config.get("HOTKEY_LABEL") or "Ctrl+Alt+O")
    try:
        GLOBAL_HOTKEY_PYNPUT, FALLBACK_TK_SEQS, HOTKEY_LABEL = parse_hotkey_label(HOTKEY_LABEL)
        config["HOTKEY_LABEL"] = HOTKEY_LABEL  # store normalized
    except Exception as e:
        # If config is invalid, fall back safely
        logger.warning("Failed to parse hotkey label: %s", e)
        GLOBAL_HOTKEY_PYNPUT, FALLBACK_TK_SEQS, HOTKEY_LABEL = "<ctrl>+<alt>+o", ["<Control-o>", "<Control-O>"], "Ctrl+Alt+O"
        config["HOTKEY_LABEL"] = HOTKEY_LABEL

    GLOBAL_HOTKEY_LABEL = HOTKEY_LABEL

    def _open_overlay_from_hotkey():
        # Pynput callbacks can run on a non-Tk thread, so always hop to Tk thread.
        root.after(0, open_observer_overlay)

    global_hotkey_handle, hk_status = try_register_global_hotkey(
        _open_overlay_from_hotkey,
        hotkey_pynput=GLOBAL_HOTKEY_PYNPUT,
        hotkey_label=GLOBAL_HOTKEY_LABEL,
    )

    def _bind_fallback_hotkey():
        def on_hotkey_observation(event):
            open_observer_overlay()
            return "break"

        for seq in FALLBACK_TK_SEQS:
            try:
                root.bind(seq, on_hotkey_observation)
            except Exception as e:
                logger.warning("Failed to bind fallback hotkey %s: %s", seq, e)
                pass

    hotkey_hint_text = ""
    if hk_status.ok:
        hotkey_hint_text = f"{GLOBAL_HOTKEY_LABEL} (global)"
        presenter.add_comms_message(f"[SYSTEM] Observer hotkey: {GLOBAL_HOTKEY_LABEL} (global)")
    else:
        _bind_fallback_hotkey()
        hotkey_hint_text = f"{GLOBAL_HOTKEY_LABEL} (in-app)"
        presenter.add_comms_message(f"[SYSTEM] Observer hotkey: {GLOBAL_HOTKEY_LABEL} (in-app)")
        # Keep the error quiet, but useful for debugging in console.
        if hk_status.error:
            logger.warning("Global hotkey unavailable, using fallback. Reason: %s", hk_status.error)

    # Note: hotkey_hint is set on each overlay when created in open_observer_overlay()

    # Add startup messages
    presenter.add_comms_message("[SYSTEM] Application started")
    presenter.add_comms_message("[SYSTEM] MVP architecture active")
    presenter.add_comms_message("[SYSTEM] Journal monitor active")
    presenter.add_comms_message(f"[SYSTEM] Observer system active ({hotkey_hint_text or 'hotkey unavailable'})")
    presenter.add_comms_message("[SYSTEM] Scanning for journal files...")

    # Check for updates in background
    def _check_for_update():
        repo = "thebullbandit/dw3-survey-logger"
        current = config.get("VERSION", "0.0.0")
        try:
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "DW3-Survey-Logger"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name", "").lstrip("vV")
            if latest and latest != current:
                link = data.get("html_url", f"https://github.com/{repo}/releases/latest")
                presenter.add_comms_message(
                    f"[UPDATE] New version v{latest} available! {link}"
                )
            else:
                presenter.add_comms_message(f"[UPDATE] v{current} is up to date.")
        except Exception as e:
            logger.debug("Update check failed: %s", e)

    threading.Thread(target=_check_for_update, daemon=True).start()

    # Set initial status
    presenter.update_scan_status("INITIALIZING")
    
    # ========================================================================
    # CONNECT UI CONTROLS TO JOURNAL MONITOR
    # ========================================================================
    
    # Update presenter event handlers to use journal monitor
    original_rescan = presenter.handle_rescan
    
    def enhanced_rescan():
        """Enhanced rescan that uses journal monitor"""
        presenter.add_comms_message("[SYSTEM] Rescan requested")
        journal_monitor.request_rescan()
    
    presenter.handle_rescan = enhanced_rescan
    
    # ========================================================================
    # WINDOW CLOSE HANDLER
    # ========================================================================
    
    def on_closing():
        """Clean shutdown of all components (bulletproof)"""
        # Prevent double-trigger (WM + programmatic)
        if getattr(on_closing, "_closing", False):
            return
        on_closing._closing = True

        logger.info("Shutting down...")

        # Unregister global hotkey (if active)
        try:
            if global_hotkey_handle is not None:
                global_hotkey_handle.unregister()
        except Exception as e:
            logger.debug("Shutdown: hotkey unregister: %s", e)
            pass

        # Close all observer overlays if open
        try:
            for overlay in observer_overlays.values():
                if overlay and overlay.is_visible():
                    overlay.hide()
        except Exception as e:
            logger.debug("Shutdown: overlay hide: %s", e)
            pass

        # Stop journal monitor (joins its thread)
        try:
            if journal_monitor:
                journal_monitor.stop()
        except Exception as e:
            logger.debug("Shutdown: journal_monitor.stop: %s", e)
            pass

        # Stop presenter (cancels any pending after() calls)
        try:
            if presenter:
                presenter.stop()
        except Exception as e:
            logger.debug("Shutdown: presenter.stop: %s", e)
            pass

        # Close databases (stops DB worker thread and joins)
        try:
            if db:
                db.close()
        except Exception as e:
            logger.debug("Shutdown: db.close: %s", e)
            pass

        try:
            if observer_storage:
                observer_storage.close()
        except Exception as e:
            logger.debug("Shutdown: observer_storage.close: %s", e)
            pass

        # Destroy window last
        try:
            if root:
                root.destroy()
        except Exception as e:
            logger.debug("Shutdown: root.destroy: %s", e)
            pass

        logger.info("Shutdown complete")

    
    # ========================================================================
    # START APPLICATION
    # ========================================================================
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    logger.info("Starting UI...")
    root.mainloop()
    
    logger.info("Application stopped")


# ============================================================================
# ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    main()
