"""
Main Application - Updated with Journal Monitor and Observer System
===================================================================

Integrates the refactored JournalMonitor with the MVP architecture,
plus the Observer Note system for CMDR observations.

"""

# ============================================================================
# IMPORTS
# ============================================================================

import tkinter as tk
from utils import resource_path
from pathlib import Path
import sys
import os
import json

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent.parent))

from earth2_database import Earth2Database
from model import Earth2Model
from view import Earth2View
from presenter import Earth2Presenter
from journal_monitor import JournalMonitor
from journal_state_manager import JournalStateManager
from observer_storage import ObserverStorage
from observer_overlay import ObserverOverlay
from observer_models import ObserverNote


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_config() -> dict:
    """
    Get application configuration
    
    In the future, this could load from a config file (Step 6 of refactoring)
    """
    USERPROFILE = Path(os.environ.get("USERPROFILE", "")) or Path.home()

    # Bootstrap settings (stable location so users can relocate OUTDIR)
    # Windows: %USERPROFILE%/.dw3_survey_logger/settings.json
    # Linux/macOS: ~/.dw3_survey_logger/settings.json
    BOOTSTRAP_SETTINGS_PATH = Path.home() / ".dw3_survey_logger" / "settings.json"

    # Default storage directory (can be overridden by bootstrap settings)
    OUTDIR = USERPROFILE / "Documents" / "DW3" / "Earth2"

    # Apply bootstrap overrides (data_dir + optional export_dir)
    bootstrap_data_dir = None
    bootstrap_export_dir = None
    bootstrap_hotkey_label = None
    try:
        if BOOTSTRAP_SETTINGS_PATH.exists():
            data = json.loads(BOOTSTRAP_SETTINGS_PATH.read_text(encoding="utf-8"))
            bootstrap_data_dir = data.get("data_dir")
            bootstrap_export_dir = data.get("export_dir")
            bootstrap_hotkey_label = data.get("hotkey_label")
    except Exception:
        # Bootstrap settings are optional; ignore if missing/corrupted
        pass

    if bootstrap_data_dir:
        OUTDIR = Path(bootstrap_data_dir)

    config = {
        # Application info
        "APP_NAME": "DW3 Survey Logger",
        "VERSION": "0.9.2 BETA",
        
        # Hotkey
        "HOTKEY_LABEL": bootstrap_hotkey_label or "Ctrl+Alt+O",

        
        # Paths
        "JOURNAL_DIR": USERPROFILE / "Saved Games" / "Frontier Developments" / "Elite Dangerous",
        "OUTDIR": OUTDIR,
        "EXPORT_DIR": OUTDIR / "exports",
        "SETTINGS_PATH": OUTDIR / "settings.json",
        "BOOTSTRAP_SETTINGS_PATH": BOOTSTRAP_SETTINGS_PATH,
        "DB_PATH": OUTDIR / "DW3_Earth2.db",
        "OUTCSV": OUTDIR / "exports",  # directory; exporter will create timestamped files
        "LOGFILE": OUTDIR / "DW3_Earth2_Logger.log",
        "ASSET_PATH": resource_path("assets"),
        "ICON_NAME": "earth2.ico",
        
        # Monitoring settings
        "POLL_SECONDS_FAST": 0.1,
        "POLL_SECONDS_SLOW": 0.25,
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
        
        # Color scheme
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

    # Apply user settings overrides (portable, stored next to the DB)
    # Priority:
    #   1) OUTDIR/settings.json (portable with the DB)
    #   2) Bootstrap settings (~/.dw3_survey_logger/settings.json)
    try:
        settings_path = config.get("SETTINGS_PATH")
        if settings_path and Path(settings_path).exists():
            data = json.loads(Path(settings_path).read_text(encoding="utf-8"))
            export_dir = data.get("export_dir")
            if export_dir:
                config["EXPORT_DIR"] = Path(export_dir)
                config["OUTCSV"] = Path(export_dir)
            hotkey_label = data.get("hotkey_label")
            if hotkey_label:
                config["HOTKEY_LABEL"] = str(hotkey_label)
        elif bootstrap_export_dir:
            config["EXPORT_DIR"] = Path(bootstrap_export_dir)
            config["OUTCSV"] = Path(bootstrap_export_dir)
    except Exception:
        # Settings are optional; ignore if corrupted
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
    observer_overlay = None
    global_hotkey_handle = None

    # Initialize database (DB worker thread)
    try:
        db = Earth2Database(config["DB_PATH"])
        print(f"[MAIN] Database initialized: {config['DB_PATH']}")
    except Exception as e:
        import traceback
        print(f"[MAIN ERROR] Database initialization failed: {e}")
        traceback.print_exc()
        db = None


    if db is None:
        print("[MAIN] Cannot start without a working database. Exiting.")
        return

    # ========================================================================
    # CREATE OBSERVER STORAGE (Step 3a)
    # ========================================================================
    observer_db_path = config["OUTDIR"] / "DW3_Earth2_Observations.db"
    try:
        observer_storage = ObserverStorage(observer_db_path)
        print(f"[MAIN] Observer storage initialized: {observer_db_path}")
    except Exception as e:
        print(f"[MAIN ERROR] Observer storage initialization failed: {e}")
        observer_storage = None

    # ========================================================================
    # CREATE JOURNAL STATE MANAGER (Step 3b)
    # ========================================================================
    state_manager = JournalStateManager()
    print("[MAIN] Journal state manager initialized")

    # Create Tkinter root
    root = tk.Tk()

    # ========================================================================
    # CREATE MVP COMPONENTS (Step 1)
    # ========================================================================
    model = Earth2Model(db, config)
    view = Earth2View(root, config)
    presenter = Earth2Presenter(model, view, config)

    # Build UI
    view.build_ui()

    # Start presenter (begins UI refresh loop)
    presenter.start()

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
                if note.sample_index is not None:
                    presenter.add_comms_message(
                        f"[OBSERVER] Saved: {note.slice_status.value} | Sample #{note.sample_index} | System #{note.system_index}"
                    )
                    
                else:
                    presenter.add_comms_message(f"[OBSERVER] Saved: {note.slice_status.value}")
                print(f"[MAIN] Observation saved with ID: {note_id}")
            except Exception as e:
                presenter.add_comms_message(f"[OBSERVER ERROR] Failed to save: {e}")
                print(f"[MAIN ERROR] Failed to save observation: {e}")
        else:
            presenter.add_comms_message("[OBSERVER ERROR] Storage not available")

    # Create overlay (initially hidden)
    observer_overlay = ObserverOverlay(
        parent=root,
        config=config,
        on_save=on_observation_saved,
        session_id=journal_monitor.current_session_id or "",
        app_version=config["VERSION"]
    )

    def open_observer_overlay():
        """Open the observer overlay with current context"""
        context = state_manager.get_context()
        # Update session_id in case it changed
        observer_overlay.session_id = journal_monitor.current_session_id or ""
        observer_overlay.show(context)
        presenter.add_comms_message("[OBSERVER] Overlay opened")

    # ========================================================================
    # ADD OBSERVATION BUTTON TO UI
    # ========================================================================

    # Add button to control frame
    btn_observation = tk.Button(
        view.widgets["btn_export_csv"].master,  # Same parent as other buttons
        text="Add Observation",
        font=("Consolas", 9),
        bg=config["GREEN"],
        fg="#000000",
        command=open_observer_overlay,
        cursor="hand2"
    )
    btn_observation.pack(side="left", padx=5)

    # ========================================================================
    # HOTKEY: Global (best effort) with in-app fallback
    # ========================================================================
    # Goal: minimal friction. If a system-wide hotkey can be registered, use it.
    # If not (missing pynput, Wayland, permissions), fall back to an in-app bind.

    from hotkey_manager import try_register_global_hotkey

    # Preferred hotkey label (user-configurable via Options)
    # Default chosen to avoid NVIDIA overlay (Ctrl+Shift+O).
    from hotkey_manager import parse_hotkey_label

    HOTKEY_LABEL = str(config.get("HOTKEY_LABEL") or "Ctrl+Alt+O")
    try:
        GLOBAL_HOTKEY_PYNPUT, FALLBACK_TK_SEQS, HOTKEY_LABEL = parse_hotkey_label(HOTKEY_LABEL)
        config["HOTKEY_LABEL"] = HOTKEY_LABEL  # store normalized
    except Exception:
        # If config is invalid, fall back safely
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
            except Exception:
                pass

    if hk_status.ok:
        observer_overlay.hotkey_hint = f"{GLOBAL_HOTKEY_LABEL} (global)"
        presenter.add_comms_message(f"[SYSTEM] Observer hotkey: {GLOBAL_HOTKEY_LABEL} (global)")
    else:
        _bind_fallback_hotkey()
        observer_overlay.hotkey_hint = f"{GLOBAL_HOTKEY_LABEL} (in-app)"
        presenter.add_comms_message(f"[SYSTEM] Observer hotkey: {GLOBAL_HOTKEY_LABEL} (in-app)")
        # Keep the error quiet, but useful for debugging in console.
        if hk_status.error:
            print(f"[HOTKEY] Global hotkey unavailable, using fallback. Reason: {hk_status.error}")

    # ========================================================================
    # OPTIONAL: AUTO-TRIGGER ON Z-BIN CHANGE
    # ========================================================================

    # Uncomment below to auto-open overlay when crossing Z-bin boundaries
    # def on_z_bin_change(event):
    #     """Auto-open overlay when Z-bin changes"""
    #     presenter.add_comms_message(f"[OBSERVER] Z-bin changed: {event.old_z_bin} -> {event.new_z_bin}")
    #     # Optionally auto-open: open_observer_overlay()
    #
    # state_manager.register_z_bin_callback(on_z_bin_change)

    # Add startup messages
    presenter.add_comms_message("[SYSTEM] Application started")
    presenter.add_comms_message("[SYSTEM] MVP architecture active")
    presenter.add_comms_message("[SYSTEM] Journal monitor active")
    presenter.add_comms_message(f"[SYSTEM] Observer system active ({observer_overlay.hotkey_hint})")
    presenter.add_comms_message("[SYSTEM] Scanning for journal files...")
    
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

        print("[MAIN] Shutting down...")

        # Unregister global hotkey (if active)
        try:
            if global_hotkey_handle is not None:
                global_hotkey_handle.unregister()
        except Exception:
            pass

        # Close observer overlay if open
        try:
            if observer_overlay and observer_overlay.is_visible():
                observer_overlay.hide()
        except Exception:
            pass

        # Stop journal monitor (joins its thread)
        try:
            if journal_monitor:
                journal_monitor.stop()
        except Exception:
            pass

        # Stop presenter (cancels any pending after() calls)
        try:
            if presenter:
                presenter.stop()
        except Exception:
            pass

        # Close databases (stops DB worker thread and joins)
        try:
            if db:
                db.close()
        except Exception:
            pass

        try:
            if observer_storage:
                observer_storage.close()
        except Exception:
            pass

        # Destroy window last
        try:
            if root:
                root.destroy()
        except Exception:
            pass

        print("[MAIN] Shutdown complete")

    
    # ========================================================================
    # START APPLICATION
    # ========================================================================
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("[MAIN] Starting UI...")
    root.mainloop()
    
    print("[MAIN] Application stopped")


# ============================================================================
# ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    main()
