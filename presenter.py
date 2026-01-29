"""
Presenter Layer - Coordinates Model and View
============================================

Acts as intermediary between Model (business logic) and View (UI).
Handles UI events and updates the view based on model state.
"""

# ============================================================================
# IMPORTS
# ============================================================================

import time
import threading
from typing import Dict, Any


# ============================================================================
# CLASSES
# ============================================================================

class Earth2Presenter:
    """Presenter layer - coordinates between Model and View"""
    
    def __init__(self, model, view, config: Dict[str, Any], journal_monitor=None):
        """
        Initialize the presenter
        
        Args:
            model: Earth2Model instance
            view: Earth2View instance
            config: Configuration dictionary
            journal_monitor: JournalMonitor instance (optional)
        """
        self.model = model
        self.view = view
        self.config = config
        self.journal_monitor = journal_monitor
        
        # Connect view callbacks to presenter methods
        self.view.on_export_csv = self.handle_export_csv
        self.view.on_export_db = self.handle_export_db
        self.view.on_rescan = self.handle_rescan
        self.view.on_import_journals = self.handle_import_journals
        self.view.on_options = self.handle_options
        self.view.on_about = self.handle_about
        
        # UI refresh control
        self._stop_refresh = threading.Event()
        # IMPORTANT: Tkinter is not thread-safe. All widget updates must run on
        # the Tk main thread.
        # We therefore schedule refreshes using root.after(...) instead of a
        # background "UI thread".
        self._refresh_after_id = None
    
    def start(self):
        """Start the presenter (begins UI refresh loop)"""
        # Load initial data
        self.model.load_stats_from_db()

        # Start UI refresh loop on the Tk main thread
        self._stop_refresh.clear()
        self._schedule_refresh()
    
    def stop(self):
        """Stop the presenter"""
        self._stop_refresh.set()

        # Cancel any pending after() callback
        try:
            if self._refresh_after_id is not None:
                self.view.root.after_cancel(self._refresh_after_id)
        except Exception:
            pass
        finally:
            self._refresh_after_id = None
    
    # ========================================================================
    # UI REFRESH LOOP
    # ========================================================================
    
    def _schedule_refresh(self):
        """Schedule the next UI refresh via Tk's event loop (main thread)."""
        if self._stop_refresh.is_set():
            return

        try:
            self._refresh_ui()
        except Exception as e:
            print(f"[PRESENTER ERROR] Refresh loop: {e}")

        # Adaptive refresh rate (in milliseconds)
        last_log_time = self.model.get_status("last_log_time") or 0
        if time.time() - last_log_time < 5:
            delay_ms = int(self.config.get("UI_REFRESH_FAST_MS", 100))
        else:
            delay_ms = int(self.config.get("UI_REFRESH_SLOW_MS", 250))

        # Schedule next tick
        try:
            self._refresh_after_id = self.view.root.after(delay_ms, self._schedule_refresh)
        except Exception as e:
            # If the window is already destroyed, after() will throw.
            print(f"[PRESENTER ERROR] after(): {e}")
            self._refresh_after_id = None
    
    def _refresh_ui(self):
        """Refresh all UI components from model state"""
        try:
            # Get current state from model
            stats = self.model.get_stats()
            status = self.model.get_status()
            
            # Update feed status and LED
            self._update_feed_status(status)
            
            # Update status panel
            self._update_status_panel(status)
            
            # Update target lock
            self._update_target_lock(status)

            # Update drift guardrail (if available)
            self._update_drift_guardrail(status)
            
            # Update statistics
            self._update_statistics(stats, status)
            
            # Update COMMS
            comms_messages = self.model.get_comms_messages()
            self.view.update_comms(comms_messages)
            
            # Update footer
            self.view.update_footer(
                stats.get("total_all", 0),
                stats.get("total_elw", 0),
                stats.get("total_terraformable", 0)
            )
            
        except Exception as e:
            print(f"[PRESENTER ERROR] UI refresh: {e}")
    
    def _update_feed_status(self, status: Dict[str, Any]):
        """Update feed status and LED indicator"""
        # Determine feed status text and LED color
        scan_status = status.get("scan_status", "")
        
        if "ACTIVE" in scan_status or "LOGGING" in scan_status:
            feed_text = "ACTIVE"
            led_color = self.view.colors["LED_ACTIVE"]
        elif "NO SIGNAL" in scan_status or "INITIALIZING" in scan_status:
            feed_text = "IDLE"
            led_color = self.view.colors["LED_IDLE"]
        else:
            feed_text = scan_status or "IDLE"
            led_color = self.view.colors["LED_IDLE"]
        
        self.view.update_feed_status(feed_text, led_color)
    
    def _update_status_panel(self, status: Dict[str, Any]):
        """Update status panel fields"""
        # Prepare status data for view
        scan_status = (status.get("scan_status") or "").strip() or "NO SIGNAL"
        
        journal_name = (status.get("current_journal") or "").strip()
        journal_mode = (status.get("journal_mode") or "").strip()
        if journal_name:
            journal_text = f"{journal_name}  ({journal_mode})" if journal_mode else journal_name
        else:
            journal_text = "-"
        
        cmdr = (status.get("cmdr_name") or "").strip() or "-"
        signal = (status.get("last_signal_local") or "").strip() or "-"
        skipped = str(status.get("events_skipped", 0))
        
        status_data = {
            "scan_status": scan_status,
            "journal": journal_text,
            "cmdr_name": cmdr,
            "signal": signal,
            "skipped": skipped,
        }
        
        self.view.update_status_panel(status_data)
    
    def _update_target_lock(self, status: Dict[str, Any]):
        """Update target lock panel"""
        last_system = (status.get("last_system") or "").strip()
        last_body = (status.get("last_body") or "").strip()
        last_type = (status.get("last_type") or "").strip()
        last_rating = (status.get("last_rating") or "").strip()
        last_worth = (status.get("last_worth") or "").strip()
        last_reason = (status.get("last_reason") or "").strip()
        last_inara = (status.get("last_inara") or "").strip()
        
        # Get similarity data if available
        similarity_score = status.get("last_similarity_score", -1)
        similarity_breakdown = status.get("last_similarity_breakdown", {})
        
        # Get Goldilocks data if available
        goldilocks_score = status.get("last_goldilocks_score", -1)
        goldilocks_breakdown = status.get("last_goldilocks_breakdown", {})
        
        # Determine reason text
        if last_reason:
            reason_text = last_reason
        elif last_system and last_body:
            reason_text = "Standing by..."
        else:
            reason_text = "-"
        
        target_data = {
            "system": last_system if last_system else "-",
            "body": last_body if last_body else "-",
            "type": last_type if last_type else "-",
            "rating": last_rating if last_rating else "-",
            "worth": last_worth if last_worth else "-",
            "reason": reason_text,
            "inara_link": last_inara if last_inara else "-",
            "similarity_score": similarity_score,
            "similarity_breakdown": similarity_breakdown,
            "goldilocks_score": goldilocks_score,
            "goldilocks_breakdown": goldilocks_breakdown,
        }
        
        self.view.update_target_lock(target_data)
    
    def _update_statistics(self, stats: Dict[str, int], status: Dict[str, Any]):
        """Update statistics panel"""
        # Session duration
        hours, minutes = self.model.get_session_duration()
        session_time = f"Session: {hours}h {minutes}m"
        
        # Session counts
        sess_candidates = status.get("session_candidates", 0)
        sess_elw = status.get("session_elw", 0)
        sess_tf = status.get("session_terraformable", 0)
        sess_systems = status.get("session_systems_count", 0)
        sess_scanned = status.get("session_bodies_scanned", 0)
        
        session_candidates_text = f"Candidates: {sess_candidates} ({sess_elw} ELW, {sess_tf} TF)"
        session_systems_text = f"Systems: {sess_systems}"
        session_scanned_text = f"Bodies Scanned: {sess_scanned}"
        
        # Session rate
        rate = self.model.get_session_rate()
        session_rate_text = f"Rate: {rate:.1f}/hour"
        
        # Get rating distributions
        session_ratings = self.model.get_session_ratings()
        alltime_ratings = self.model.load_rating_distribution()
        alltime_total_candidates = sum(alltime_ratings.values()) if isinstance(alltime_ratings, dict) else 0
        
        stats_data = {
            "session_time": session_time,
            "session_candidates": session_candidates_text,
            "session_systems": session_systems_text,
            "session_scanned": session_scanned_text,
            "session_rate": session_rate_text,
            "session_ratings": session_ratings,
            "alltime_ratings": alltime_ratings,
            "session_candidate_count": sess_candidates,
            "alltime_candidate_count": alltime_total_candidates,
        }
        
        self.view.update_statistics(stats_data)

    def _update_drift_guardrail(self, status: Dict[str, Any]):
        """Update Drift Guardrail section (NavRoute guidance)."""
        try:
            drift_status = status.get("drift_status", "-")
            candidates = status.get("drift_candidates", []) or []
            meta = status.get("drift_meta", {}) or {}
            if hasattr(self.view, "update_drift_guardrail"):
                self.view.update_drift_guardrail(drift_status, candidates, meta)
        except Exception as e:
            print(f"[PRESENTER ERROR] Drift guardrail: {e}")
    
    # ========================================================================
    # EVENT HANDLERS - Called from View
    # ========================================================================
    
    def handle_export_csv(self):
        """Handle CSV export request"""
        try:
            from pathlib import Path
            from datetime import datetime
            import threading
            import os
            
            self.model.add_comms_message("[SYSTEM] Starting CSV export...")
            
            def export_thread():
                try:
                    # Determine export directory (Options can override)
                    export_dir = self.config.get("EXPORT_DIR")
                    if not export_dir:
                        db_path_str = self.config.get("DB_PATH", "")
                        export_dir = Path(db_path_str).parent if db_path_str else Path(os.path.expanduser("~")) / "Documents" / "DW3" / "Earth2" / "exports"

                    export_dir = Path(export_dir)

                    # Timestamp (no seconds)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    timestamped_path = export_dir / f"DW3_Earth2_Candidates_{timestamp}.csv"
                    
                    # Ensure directory exists
                    export_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Export using database method
                    self.model.db.export_to_csv(timestamped_path)
                    
                    self.model.add_comms_message(f"[INFO] CSV saved: {timestamped_path.name}")
                    self.model.add_comms_message(f"[INFO] Full path: {timestamped_path}")
                    
                except Exception as e:
                    self.model.add_comms_message(f"[ERROR] CSV export failed: {e}")
                    print(f"[PRESENTER ERROR] Export CSV: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Run in background thread
            thread = threading.Thread(target=export_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            print(f"[PRESENTER ERROR] Export CSV: {e}")

    def handle_export_db(self):
        """Handle database export request"""
        try:
            from pathlib import Path
            from datetime import datetime
            import shutil
            import threading

            self.model.add_comms_message("[SYSTEM] Starting database backup...")

            def export_thread():
                backup_path = None
                try:
                    # Get database path from config
                    db_path_str = self.config.get("DB_PATH", "")
                    if not db_path_str:
                        self.model.add_comms_message("[ERROR] Database path not configured")
                        return

                    db_path = Path(db_path_str)
                    if not db_path.exists():
                        self.model.add_comms_message(f"[ERROR] Database file not found at: {db_path}")
                        return

                    # Create backup with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"

                    # Copy database file
                    shutil.copy2(db_path, backup_path)

                    # Get file size
                    size_mb = backup_path.stat().st_size / (1024 * 1024)

                    self.model.add_comms_message(f"[INFO] Database backup saved: {backup_path.name}")
                    self.model.add_comms_message(f"[INFO] Size: {size_mb:.2f} MB")
                    self.model.add_comms_message(f"[INFO] Full path: {backup_path}")

                except Exception as e:
                    self.model.add_comms_message("[ERROR] Database backup failed. See logs for details.")
                    print(f"[PRESENTER ERROR] Export DB: {e}")
                    import traceback
                    traceback.print_exc()

            # Run in background thread
            thread = threading.Thread(target=export_thread, daemon=True)
            thread.start()

        except Exception as e:
            print(f"[PRESENTER ERROR] Export DB (outer): {e}")


    
    def handle_rescan(self):
        """Handle rescan current journal request"""
        try:
            if self.journal_monitor:
                self.model.add_comms_message("[SYSTEM] Rescanning current journal from start...")
                self.journal_monitor.request_rescan()
            else:
                self.model.add_comms_message("[INFO] Live journal monitoring is not active – rescan unavailable")
        except Exception as e:
            self.model.add_comms_message("[ERROR] Rescan failed due to an internal error. See logs for details.")
            print(f"[PRESENTER ERROR] Rescan: {e}")
    
    def handle_import_journals(self):
        """Handle import old journals request"""
        try:
            self.model.add_comms_message("[SYSTEM] Starting journal import...")
            self.model.add_comms_message("[INFO] This may take a few minutes...")
            
            # Run import in background thread to not block UI
            import threading
            
            def import_thread():
                try:
                    from import_journals import JournalImporter
                    from pathlib import Path
                    
                    # Get journal directory from config
                    journal_dir = Path(self.config.get("JOURNAL_DIR", ""))
                    
                    if not journal_dir.exists():
                        self.model.add_comms_message("[ERROR] Journal directory not found!")
                        return
                    
                    # Create importer (use self.model.db, not self.model.database)
                    importer = JournalImporter(
                        self.model.db,  # Changed from self.model.database
                        self.model,
                        self.model.error_handler.logger if hasattr(self.model, 'error_handler') else None
                    )
                    
                    # Import all journals
                    stats = importer.import_journal_directory(journal_dir)
                    
                    # Report results
                    self.model.add_comms_message(f"[INFO] Files processed: {stats['files_processed']}")
                    self.model.add_comms_message(f"[INFO] Candidates found: {stats['candidates_found']}")
                    self.model.add_comms_message(f"[INFO] Duplicates skipped: {stats['duplicates_skipped']}")
                    
                    if stats['errors'] > 0:
                        self.model.add_comms_message(f"[WARNING] Errors encountered: {stats['errors']}")
                    
                    self.model.add_comms_message("[INFO] Import complete!")
                    
                    # Reload ALL stats and data to show new data
                    self.model.load_stats_from_db()
                    self.model.load_rating_distribution(force_refresh=True)
                    
                    # Show current stats for debugging
                    current_stats = self.model.get_stats()
                    self.model.add_comms_message(f"[INFO] Total in DB: {current_stats.get('total_all', 0)}")
                    self.model.add_comms_message(f"[INFO] ELW in DB: {current_stats.get('total_elw', 0)}")
                    
                    # Force UI refresh (it will auto-refresh in the next cycle)
                    # No need to manually call _update_statistics as it runs in refresh loop
                    
                    self.model.add_comms_message("[INFO] Statistics updated!")
                    
                except Exception as e:
                    self.model.add_comms_message(f"[ERROR] Import failed: {e}")
                    print(f"[PRESENTER ERROR] Import: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start import thread
            thread = threading.Thread(target=import_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            print(f"[PRESENTER ERROR] Import journals: {e}")

    def handle_options(self):
        """Handle Options button. Supports setting Data folder (DB/logs) + Export folder."""
        try:
            from pathlib import Path
            import json

            current_export = str(self.config.get("EXPORT_DIR") or "")
            current_data = str(self.config.get("OUTDIR") or "")
            current_hotkey = str(self.config.get("HOTKEY_LABEL") or "Ctrl+Alt+O")
            current_journal = str(self.config.get("JOURNAL_DIR") or "")

            result = self.view.show_options_dialog(current_export, current_data, current_hotkey, current_journal)
            if not result:
                return

            data_dir = Path(result["data_dir"]).expanduser()
            export_dir = Path(result["export_dir"]).expanduser()
            journal_dir = Path(result.get("journal_dir") or current_journal or "").expanduser()

            # Hotkey
            requested_hotkey = str(result.get("hotkey_label") or result.get("hotkey") or "").strip() or current_hotkey
            try:
                from hotkey_manager import parse_hotkey_label
                _p, _tk, normalized = parse_hotkey_label(requested_hotkey)
                self.config["HOTKEY_LABEL"] = normalized
            except Exception as e:
                # Keep previous if invalid
                try:
                    from tkinter import messagebox
                    messagebox.showwarning("Options", f"Invalid hotkey: {e}\n\nKeeping: {current_hotkey}", parent=self.view.root)
                except Exception:
                    pass
                self.config["HOTKEY_LABEL"] = current_hotkey

            old_data_dir = Path(self.config.get("OUTDIR") or data_dir)

            # Update runtime config (exports can apply immediately)
            self.config["EXPORT_DIR"] = export_dir
            # Journal directory can apply immediately
            if str(journal_dir).strip():
                self.config["JOURNAL_DIR"] = journal_dir
            self.config["OUTCSV"] = export_dir

            # If data folder changed, update derived paths in config.
            # NOTE: the database + observer storage are already open, so relocation requires restart.
            if data_dir != old_data_dir:
                self.config["OUTDIR"] = data_dir
                self.config["SETTINGS_PATH"] = data_dir / "settings.json"
                self.config["DB_PATH"] = data_dir / "DW3_Earth2.db"
                self.config["LOGFILE"] = data_dir / "DW3_Earth2_Logger.log"

                self.model.add_comms_message(f"[SYSTEM] Data folder set to: {data_dir}")
                self.model.add_comms_message("[SYSTEM] Restart required to move the live database to the new folder.")
            else:
                self.model.add_comms_message(f"[SYSTEM] Data folder unchanged: {data_dir}")

            self.model.add_comms_message(f"[SYSTEM] Export folder set to: {export_dir}")

            # Persist settings (portable, stored next to DB)
            settings_path = self.config.get("SETTINGS_PATH")
            if settings_path:
                settings_path = Path(settings_path)
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {"export_dir": str(export_dir), "hotkey_label": str(self.config.get("HOTKEY_LABEL") or "Ctrl+Alt+O")}
                settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            # Persist bootstrap settings (stable location so OUTDIR can be relocated)
            bootstrap_path = self.config.get("BOOTSTRAP_SETTINGS_PATH")
            if bootstrap_path:
                bootstrap_path = Path(bootstrap_path)
                bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {"data_dir": str(data_dir), "export_dir": str(export_dir), "journal_dir": str(self.config.get("JOURNAL_DIR") or journal_dir or ""), "hotkey_label": str(self.config.get("HOTKEY_LABEL") or "Ctrl+Alt+O")}
                bootstrap_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        except Exception as e:
            self.model.add_comms_message(f"[ERROR] Failed to save options: {e}")
            print(f"[PRESENTER ERROR] Options: {e}")

    def handle_about(self):
        """Handle About dialog (includes copyable diagnostics)."""
        try:
            from pathlib import Path
            import os

            db_path = self.config.get("DB_PATH", "")
            outdir = self.config.get("OUTDIR", "")
            export_dir = self.config.get("EXPORT_DIR", "")
            journal_dir = self.config.get("JOURNAL_DIR", "")
            settings_path = self.config.get("SETTINGS_PATH", "")

            def _size(p: str) -> str:
                try:
                    pp = Path(p)
                    if pp.exists():
                        return f"{pp.stat().st_size} bytes"
                except Exception:
                    pass
                return "-"

            about_text = "\n".join([
                "DW3 Earth2 Logger Beta\n",
                "Local-first: stores data in SQLite on your machine (no uploads).",
                "\nPaths:",
                f"  OUTDIR:      {outdir}",
                f"  Export dir:  {export_dir}",
                f"  DB:          {db_path}",
                f"  Journals:    {journal_dir}",
                f"  Settings:    {settings_path}",
                "\nNotes:",
                "- If something looks odd, use 'Copy diagnostics' and paste it into Discord.",
            ])

            diagnostics = "\n".join([
                f"app={self.config.get('APP_NAME','')}",
                f"version={self.config.get('VERSION','')}",
                f"outdir={outdir}",
                f"export_dir={export_dir}",
                f"db_path={db_path}",
                f"db_size={_size(str(db_path))}",
                f"journal_dir={journal_dir}",
                f"settings_path={settings_path}",
                f"python={os.sys.version.split()[0]}",
            ])

            self.view.show_about_dialog(about_text, copy_text=diagnostics)
        except Exception as e:
            print(f"[PRESENTER ERROR] About: {e}")
    
    # ========================================================================
    # PUBLIC METHODS - Called from external components (e.g., journal monitor)
    # ========================================================================
    
    def log_candidate(self, candidate_data: Dict[str, Any]):
        """
        Log a new candidate body
        
        Args:
            candidate_data: Dictionary with candidate information
        """
        try:
            # Update model
            was_logged = self.model.log_candidate(candidate_data)
            
            if was_logged:
                # Add COMMS message
                body_name = candidate_data.get("body_name", "Unknown")
                rating = candidate_data.get("earth2_rating", "-")
                similarity_score = candidate_data.get("similarity_score", -1)
                goldilocks_score = candidate_data.get("goldilocks_score", -1)
                
                # Format COMMS message with both scores
                score_parts = []
                if similarity_score >= 0:
                    score_parts.append(f"Sim:{similarity_score:.1f}")
                if goldilocks_score >= 0:
                    stars = "⭐" * min(goldilocks_score // 3, 5)
                    score_parts.append(f"Gold:{goldilocks_score}/16 {stars}")
                
                if score_parts:
                    score_text = " | ".join(score_parts)
                    self.model.add_comms_message(f"[INFO] {body_name} | {rating} | {score_text}")
                else:
                    self.model.add_comms_message(f"[INFO] {body_name} | {rating}")
                
                # Calculate similarity breakdown if score is available
                similarity_breakdown = {}
                goldilocks_breakdown = {}
                
                if similarity_score >= 0:
                    try:
                        from earth_similarity_score import get_similarity_breakdown
                        similarity_breakdown = get_similarity_breakdown(candidate_data)
                    except Exception:
                        pass
                
                if goldilocks_score >= 0:
                    try:
                        from earth_similarity_score import calculate_goldilocks_score
                        goldilocks_data = calculate_goldilocks_score(candidate_data)
                        goldilocks_breakdown = goldilocks_data.get("breakdown", {})
                    except Exception:
                        pass
                
                # Update target lock with latest candidate
                self.model.update_status({
                    "last_system": candidate_data.get("star_system", ""),
                    "last_body": candidate_data.get("body_name", ""),
                    "last_type": candidate_data.get("candidate_type", ""),
                    "last_rating": candidate_data.get("earth2_rating", ""),
                    "last_worth": candidate_data.get("worth_landing", ""),
                    "last_reason": candidate_data.get("worth_landing_reason", ""),
                    "last_inara": candidate_data.get("inara_system_link", ""),
                    "last_similarity_score": similarity_score,
                    "last_similarity_breakdown": similarity_breakdown,
                    "last_goldilocks_score": goldilocks_score,
                    "last_goldilocks_breakdown": goldilocks_breakdown,
                })
        
        except Exception as e:
            print(f"[PRESENTER ERROR] Log candidate: {e}")
    
    def update_journal_status(self, journal_file: str, mode: str):
        """Update current journal file status"""
        self.model.update_status({
            "current_journal": journal_file,
            "journal_mode": mode,
        })
    
    def update_scan_status(self, status_text: str):
        """Update scan status text"""
        self.model.update_status({"scan_status": status_text})
    
    def update_cmdr(self, cmdr_name: str):
        """Update current commander"""
        self.model.update_status({"cmdr_name": cmdr_name})
        self.model.load_stats_from_db(cmdr_name)
    
    def add_comms_message(self, message: str):
        """Add message to COMMS feed"""
        self.model.add_comms_message(message)
