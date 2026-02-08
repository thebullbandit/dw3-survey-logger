"""
Presenter Layer - Coordinates Model and View
============================================

Acts as intermediary between Model (business logic) and View (UI).
Handles UI events and updates the view based on model state.
"""

# ============================================================================
# IMPORTS
# ============================================================================

import logging
import time
import threading
from typing import Dict, Any

logger = logging.getLogger("dw3.presenter")


# ============================================================================
# CLASSES
# ============================================================================

class Earth2Presenter:
    """Presenter layer - coordinates between Model and View"""

    def __init__(self, model, view, config: Dict[str, Any], journal_monitor=None, observer_storage=None):
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

        self.observer_storage = observer_storage

        # Connect view callbacks to presenter methods
        self.view.on_export_csv = self.handle_export_csv
        self.view.on_export_db = self.handle_export_db
        self.view.on_export_density_xlsx = self.handle_export_density_xlsx
        self.view.on_export_boxel_xlsx = self.handle_export_boxel_xlsx
        self.view.on_export_all = self.handle_export_all
        self.view.on_export_diagnostics = self.handle_export_diagnostics
        self.view.on_rescan = self.handle_rescan
        self.view.on_import_journals = self.handle_import_journals
        self.view.on_options = self.handle_options
        self.view.on_journal_folder = self.handle_journal_folder
        self.view.on_about = self.handle_about
        self.view.on_reset_observer_progress = self.handle_reset_observer_progress

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
        except Exception as e:
            logger.debug("after_cancel failed: %s", e)
            pass
        finally:
            self._refresh_after_id = None



    def notify_observer_context_changed(self):
        """Notify UI listeners (e.g., Observer overlay) that journal context changed.

        Safe to call from any thread; schedules Tk event generation on the main thread.
        """
        try:
            root = getattr(self.view, "root", None)
            if root is None:
                return

            def _emit():
                try:
                    root.event_generate("<<ObserverContextChanged>>", when="tail")
                except Exception as e:
                    logger.debug("event_generate ObserverContextChanged failed: %s", e)
                    pass

            # Ensure we're on Tk main thread
            root.after(0, _emit)
        except Exception as e:
            logger.debug("notify_observer_context_changed failed: %s", e)
            pass

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
            logger.error("Refresh loop: %s", e, exc_info=True)

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
            logger.error("after(): %s", e)
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
            logger.error("UI refresh: %s", e, exc_info=True)

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
                    logger.error("Export CSV: %s", e, exc_info=True)

            # Run in background thread
            thread = threading.Thread(target=export_thread, daemon=True)
            thread.start()

        except Exception as e:
            logger.error("Export CSV: %s", e, exc_info=True)

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
                    logger.error("Export DB: %s", e, exc_info=True)

            # Run in background thread
            thread = threading.Thread(target=export_thread, daemon=True)
            thread.start()

        except Exception as e:
            logger.error("Export DB (outer): %s", e, exc_info=True)

    def handle_export_all(self):
        """Handle export all formats (CSV + DB + XLSX) with folder picker"""
        try:
            from pathlib import Path
            from datetime import datetime
            import threading
            import shutil
            from tkinter import filedialog

            # Ask user to select export folder
            initial_dir = self.config.get("EXPORT_DIR") or self.config.get("OUTDIR") or str(Path.home() / "Documents")
            export_dir = filedialog.askdirectory(
                title="Select Export Folder",
                initialdir=initial_dir,
                parent=self.view.root
            )

            if not export_dir:
                # User cancelled
                return

            export_dir = Path(export_dir)

            # Save this directory for next time
            self.config["EXPORT_DIR"] = str(export_dir)

            self.model.add_comms_message(f"[SYSTEM] Exporting all formats to: {export_dir}")

            def export_thread():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_count = 0

                # 1. Export CSV
                try:
                    csv_path = export_dir / f"DW3_Earth2_Candidates_{timestamp}.csv"
                    self.model.db.export_to_csv(csv_path)
                    self.model.add_comms_message(f"[✓] CSV exported: {csv_path.name}")
                    export_count += 1
                except Exception as e:
                    self.model.add_comms_message(f"[✗] CSV export failed: {e}")

                # 2. Export Database Backup
                try:
                    db_path_str = self.config.get("DB_PATH", "")
                    if db_path_str:
                        db_path = Path(db_path_str)
                        if db_path.exists():
                            backup_path = export_dir / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
                            shutil.copy2(db_path, backup_path)
                            size_mb = backup_path.stat().st_size / (1024 * 1024)
                            self.model.add_comms_message(f"[✓] Database backup exported: {backup_path.name} ({size_mb:.2f} MB)")
                            export_count += 1
                        else:
                            self.model.add_comms_message("[✗] Database file not found")
                    else:
                        self.model.add_comms_message("[✗] Database path not configured")
                except Exception as e:
                    self.model.add_comms_message(f"[✗] Database backup failed: {e}")

                # 3. Export Density XLSX (multiple files, one per sample)
                try:
                    if not self.observer_storage:
                        self.model.add_comms_message("[✗] Observer storage not available (XLSX skipped)")
                    else:
                        from density_worksheet_exporter_multi_file import export_density_worksheet_from_notes_multi_file, resource_path
                        template_path = resource_path("templates", "Stellar Density Scan Worksheet.xlsx")

                        notes = self.observer_storage.get_active()

                        if not notes:
                            self.model.add_comms_message("[✗] No observer notes to export (XLSX skipped)")
                        else:
                            # Get CMDR name and metadata
                            cmdr = (self.model.get_status("cmdr_name") or "").strip() or "UnknownCMDR"

                            z_bin = None
                            sample_indexes = []

                            for n in notes:
                                zb = getattr(n, "z_bin", None) if not isinstance(n, dict) else n.get("z_bin")
                                si = getattr(n, "sample_index", None) if not isinstance(n, dict) else n.get("sample_index")
                                if z_bin is None and zb is not None:
                                    try:
                                        z_bin = int(zb)
                                    except Exception as e:
                                        logger.debug("z_bin parse failed: %s", e)
                                        pass
                                if si is not None:
                                    try:
                                        sample_indexes.append(int(si))
                                    except Exception as e:
                                        logger.debug("sample_index parse failed: %s", e)
                                        pass

                            sample_tag = ""
                            if sample_indexes:
                                s_min, s_max = min(sample_indexes), max(sample_indexes)
                                sample_tag = f"S{s_min:02d}-S{s_max:02d}" if s_min != s_max else f"S{s_min:02d}"

                            # Export as multiple files (one per sample)
                            created_files = export_density_worksheet_from_notes_multi_file(
                                notes,
                                template_path,
                                export_dir,  # Directory, not specific file
                                cmdr_name=cmdr,
                                sample_tag=sample_tag,
                                z_bin=z_bin,
                            )

                            num_files = len(created_files)
                            self.model.add_comms_message(f"[✓] Density XLSX exported: {num_files} sample file(s) created")
                            for fp in created_files:
                                self.model.add_comms_message(f"    - {fp.name}")
                            export_count += num_files
                except Exception as e:
                    self.model.add_comms_message(f"[✗] Density XLSX export failed: {e}")
                    import traceback
                    traceback.print_exc()

                # 4. Export Boxel Sheet XLSX
                try:
                    if not self.observer_storage:
                        self.model.add_comms_message("[✗] Observer storage not available (Boxel sheet skipped)")
                    else:
                        from boxel_sheet_exporter import export_boxel_sheet
                        boxel_entries = self.observer_storage.get_boxel_entries()
                        boxel_result = export_boxel_sheet(
                            boxel_entries,
                            export_dir,
                            cmdr_name=cmdr,
                        )
                        if boxel_result:
                            self.model.add_comms_message(f"[✓] Boxel sheet exported: {boxel_result.name}")
                            export_count += 1
                        else:
                            self.model.add_comms_message("[✗] No boxel data to export (Boxel sheet skipped)")
                except Exception as e:
                    self.model.add_comms_message(f"[✗] Boxel sheet export failed: {e}")

                # Summary
                self.model.add_comms_message(f"[SYSTEM] Export complete: {export_count} files exported to {export_dir}")

            # Run in background thread
            threading.Thread(target=export_thread, daemon=True).start()

        except Exception as e:
            self.model.add_comms_message(f"[ERROR] Export all failed: {e}")
            logger.error("Export all: %s", e, exc_info=True)

    def handle_export_diagnostics(self):
        """Export a diagnostics ZIP bundle (logs/settings/db + manifest)."""
        try:
            import threading
            from datetime import datetime
            from pathlib import Path
            from tkinter import filedialog, messagebox

            # Default suggested filename
            export_dir = self.config.get("EXPORT_DIR") or Path(self.config.get("OUTDIR", Path.home()))
            export_dir = Path(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"DW3_Survey_Logger_Diagnostics_{ts}.zip"
            default_path = export_dir / default_name

            zip_path_str = filedialog.asksaveasfilename(
                title="Save Diagnostics Bundle",
                defaultextension=".zip",
                initialdir=str(export_dir),
                initialfile=default_name,
                filetypes=[("ZIP archive", "*.zip")],
            )
            if not zip_path_str:
                return

            zip_path = Path(zip_path_str)

            # Friendly privacy heads-up
            try:
                if not messagebox.askyesno(
                    "Include data?",
                    "Diagnostics can include your database and may contain survey data.\n\nDo you want to include the databases in the bundle?",
                    icon="warning",
                ):
                    include_db = False
                else:
                    include_db = True
            except Exception as e:
                logger.debug("include_db dialog failed: %s", e)
                include_db = True

            self.model.add_comms_message("[SYSTEM] Building diagnostics bundle...")

            def _worker():
                try:
                    from diagnostics_exporter import export_diagnostics_zip
                    out = export_diagnostics_zip(
                        zip_path=zip_path,
                        config=self.config,
                        model=self.model,
                        include_db=include_db,
                    )
                    self.model.add_comms_message(f"[INFO] Diagnostics saved: {out.name}")
                    self.model.add_comms_message(f"[INFO] Full path: {out}")
                except Exception as e:
                    self.model.add_comms_message(f"[ERROR] Diagnostics export failed: {e}")
                    import traceback
                    traceback.print_exc()

            threading.Thread(target=_worker, daemon=True).start()

        except Exception as e:
            logger.error("Export Diagnostics: %s", e, exc_info=True)
            try:
                self.model.add_comms_message(f"[ERROR] Diagnostics export failed: {e}")
            except Exception as e2:
                logger.debug("Failed to report diagnostics error to comms: %s", e2)
                pass

    def handle_export_density_xlsx(self, survey_type=None):
            """Handle DW3 density worksheet XLSX export request with folder picker - creates one file per sample

            Args:
                survey_type: Optional SurveyType to filter exports. If None, exports all density observations.
            """
            try:
                from pathlib import Path
                from datetime import datetime
                import threading
                from tkinter import filedialog
                from observer_models import SurveyType

                if not self.observer_storage:
                    self.model.add_comms_message("[OBSERVER] No observer DB available (worksheet export disabled).")
                    return

                # Ask user to select export folder
                initial_dir = self.config.get("EXPORT_DIR") or self.config.get("OUTDIR") or str(Path.home() / "Documents")
                export_dir = filedialog.askdirectory(
                    title="Select Export Folder for Density Worksheets",
                    initialdir=initial_dir,
                    parent=self.view.root
                )

                if not export_dir:
                    # User cancelled
                    return

                export_dir = Path(export_dir)

                # Save this directory for next time
                self.config["EXPORT_DIR"] = str(export_dir)

                self.model.add_comms_message("[SYSTEM] Starting density worksheet export (one file per sample)...")

                def export_thread():
                    try:
                        # Template ships with the app under ./templates
                        from density_worksheet_exporter_multi_file import export_density_worksheet_from_notes_multi_file, resource_path
                        template_path = resource_path("templates", "Stellar Density Scan Worksheet.xlsx")

                        notes = self.observer_storage.get_active()

                        # CMDR name for filename (DW3 wants it visible without opening the sheet)
                        cmdr = (self.model.get_status("cmdr_name") or "").strip() or "UnknownCMDR"

                        # Optional metadata for filename: Z-bin + sample range
                        z_bin = None
                        sample_indexes = []

                        for n in notes:
                            # notes are ObserverNote objects, but be defensive in case dicts slip through
                            zb = getattr(n, "z_bin", None) if not isinstance(n, dict) else n.get("z_bin")
                            si = getattr(n, "sample_index", None) if not isinstance(n, dict) else n.get("sample_index")
                            if z_bin is None and zb is not None:
                                try:
                                    z_bin = int(zb)
                                except Exception as e:
                                    logger.debug("z_bin parse failed: %s", e)
                                    z_bin = None
                            if si is not None:
                                try:
                                    sample_indexes.append(int(si))
                                except Exception as e:
                                    logger.debug("sample_index parse failed: %s", e)
                                    pass

                        sample_tag = ""
                        if sample_indexes:
                            s_min, s_max = min(sample_indexes), max(sample_indexes)
                            sample_tag = f"S{s_min:02d}-S{s_max:02d}" if s_min != s_max else f"S{s_min:02d}"

                        # Export as multiple files (one per sample)
                        created_files = export_density_worksheet_from_notes_multi_file(
                            notes,
                            template_path,
                            export_dir,  # Directory, not specific file
                            cmdr_name=cmdr,
                            sample_tag=sample_tag,
                            z_bin=z_bin,
                            survey_type=survey_type,
                        )

                        num_files = len(created_files)
                        survey_label = survey_type.value if survey_type else "all"
                        self.model.add_comms_message(f"[SYSTEM] Density worksheets exported ({survey_label}): {num_files} sample file(s)")
                        for fp in created_files:
                            self.model.add_comms_message(f"    - {fp.name}")
                    except Exception as e:
                        self.model.add_comms_message(f"[ERROR] Density worksheet export failed: {e}")

                threading.Thread(target=export_thread, daemon=True).start()

            except Exception as e:
                self.model.add_comms_message(f"[ERROR] Density worksheet export error: {e}")





    def handle_export_boxel_xlsx(self):
        """Handle Boxel Sheet XLSX export request"""
        try:
            from pathlib import Path
            import threading
            from tkinter import filedialog

            if not self.observer_storage:
                self.model.add_comms_message("[OBSERVER] No observer DB available (boxel export disabled).")
                return

            # Ask user to select export folder
            initial_dir = self.config.get("EXPORT_DIR") or self.config.get("OUTDIR") or str(Path.home() / "Documents")
            export_dir = filedialog.askdirectory(
                title="Select Export Folder for Boxel Sheet",
                initialdir=initial_dir,
                parent=self.view.root
            )

            if not export_dir:
                return

            export_dir = Path(export_dir)
            self.config["EXPORT_DIR"] = str(export_dir)

            self.model.add_comms_message("[SYSTEM] Starting boxel sheet export...")

            def export_thread():
                try:
                    from boxel_sheet_exporter import export_boxel_sheet

                    entries = self.observer_storage.get_boxel_entries()
                    cmdr = (self.model.get_status("cmdr_name") or "").strip() or "UnknownCMDR"

                    result = export_boxel_sheet(
                        entries,
                        export_dir,
                        cmdr_name=cmdr,
                    )

                    if result:
                        self.model.add_comms_message(f"[SYSTEM] Boxel sheet exported: {result.name}")
                    else:
                        self.model.add_comms_message("[INFO] No boxel data to export. Enter a highest system in the observation overlay first.")
                except Exception as e:
                    self.model.add_comms_message(f"[ERROR] Boxel sheet export failed: {e}")

            threading.Thread(target=export_thread, daemon=True).start()

        except Exception as e:
            self.model.add_comms_message(f"[ERROR] Boxel sheet export error: {e}")

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
            logger.error("Rescan: %s", e, exc_info=True)

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
                        # Show error details if available
                        error_details = stats.get('error_details', [])
                        if error_details:
                            for detail in error_details[:5]:  # Show first 5 errors
                                self.model.add_comms_message(f"[WARNING] - {detail}")

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
                    logger.error("Import: %s", e, exc_info=True)

            # Start import thread
            thread = threading.Thread(target=import_thread, daemon=True)
            thread.start()

        except Exception as e:
            logger.error("Import journals: %s", e, exc_info=True)


    def handle_journal_folder(self):
        """Let the user choose their Elite Dangerous journal folder (applies live)."""
        try:
            from tkinter import filedialog, messagebox
            from pathlib import Path
            import json

            current = self.config.get("JOURNAL_DIR", "")
            initial = ""
            try:
                if current:
                    initial = str(Path(current))
            except Exception as e:
                logger.debug("journal folder path resolve: %s", e)
                initial = ""

            folder = filedialog.askdirectory(
                title="Select Elite Dangerous Journal Folder",
                initialdir=initial or None,
                mustexist=True
            )
            if not folder:
                return  # cancelled

            journal_dir = Path(folder).expanduser()

            if not journal_dir.exists():
                try:
                    messagebox.showwarning(
                        "Journal Folder",
                        f"Folder not found:\n{journal_dir}",
                        parent=self.view.root
                    )
                except Exception as e:
                    logger.debug("messagebox.showwarning failed: %s", e)
                    pass
                return

            # Update config (in-memory)
            self.config["JOURNAL_DIR"] = journal_dir

            # Persist to bootstrap settings file (stable across OUTDIR changes)
            settings_path = self.config.get("BOOTSTRAP_SETTINGS_PATH", "")
            try:
                sp = Path(settings_path) if settings_path else (Path.home() / ".dw3_survey_logger" / "settings.json")
                sp.parent.mkdir(parents=True, exist_ok=True)

                data = {}
                if sp.exists():
                    try:
                        data = json.loads(sp.read_text(encoding="utf-8"))
                    except Exception as e:
                        logger.warning("Failed to load settings file: %s", e)
                        data = {}

                data["journal_dir"] = str(journal_dir)

                # Preserve other known keys if they exist in config
                outdir = self.config.get("OUTDIR")
                export_dir = self.config.get("EXPORT_DIR")
                hotkey_label = self.config.get("HOTKEY_LABEL")
                if outdir:
                    data.setdefault("data_dir", str(outdir))
                if export_dir:
                    data.setdefault("export_dir", str(export_dir))
                if hotkey_label:
                    data.setdefault("hotkey_label", str(hotkey_label))

                sp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                self.model.add_comms_message(f"[WARN] Could not save journal folder: {e}")

            # Apply live to monitor + trigger rescan
            try:
                if self.journal_monitor and hasattr(self.journal_monitor, "set_journal_dir"):
                    self.journal_monitor.set_journal_dir(journal_dir)
            except Exception as e:
                self.model.add_comms_message(f"[WARN] Journal monitor update failed: {e}")

            self.model.add_comms_message(f"[OPTIONS] Journal folder set to: {journal_dir}")
        except Exception as e:
            self.model.add_comms_message(f"[ERROR] Journal folder selection failed: {e}")

    def handle_options(self):
        """Handle Options button (now just hotkey settings)."""
        try:
            current_hotkey = str(self.config.get("HOTKEY_LABEL") or "Ctrl+Alt+O")

            # Show simplified hotkey-only dialog
            new_hotkey = self.view.show_hotkey_dialog()
            if not new_hotkey:
                return  # User cancelled

            # Validate and normalize the hotkey
            try:
                from hotkey_manager import parse_hotkey_label
                _p, _tk, normalized = parse_hotkey_label(new_hotkey)
                self.config["HOTKEY_LABEL"] = normalized
            except Exception as e:
                # Show error and keep previous hotkey
                try:
                    from tkinter import messagebox
                    messagebox.showwarning(
                        "Hotkey Settings",
                        f"Invalid hotkey: {e}\n\nKeeping: {current_hotkey}",
                        parent=self.view.root
                    )
                except Exception as e2:
                    logger.debug("messagebox.showwarning failed: %s", e2)
                    pass
                self.config["HOTKEY_LABEL"] = current_hotkey
                return

            # Save to bootstrap settings file (stable across OUTDIR changes)
            try:
                from pathlib import Path
                import json

                settings_path = self.config.get("BOOTSTRAP_SETTINGS_PATH", "")
                sp = Path(settings_path) if settings_path else (Path.home() / ".dw3_survey_logger" / "settings.json")
                sp.parent.mkdir(parents=True, exist_ok=True)

                data = {}
                if sp.exists():
                    try:
                        data = json.loads(sp.read_text(encoding="utf-8"))
                    except Exception:
                        data = {}

                data["hotkey_label"] = self.config["HOTKEY_LABEL"]
                sp.write_text(json.dumps(data, indent=2), encoding="utf-8")

                self.model.add_comms_message(
                    f"[OPTIONS] Hotkey updated to: {self.config['HOTKEY_LABEL']}\n"
                    "Restart required for changes to take effect."
                )
            except Exception as e:
                self.model.add_comms_message(f"[ERROR] Failed to save hotkey: {e}")

        except Exception as e:
            self.model.add_comms_message(f"[ERROR] Options failed: {e}")

    def handle_reset_observer_progress(self):
        """Reset all observer sample + boxel progress after user confirmation."""
        try:
            from tkinter import messagebox
            if not self.observer_storage:
                self.model.add_comms_message("[OPTIONS] Observer storage not available.")
                return
            confirmed = messagebox.askyesno(
                "Reset Observer Progress",
                "This will reset ALL observer data back to 0:\n\n"
                "  • Density sample progress (all samples)\n"
                "  • Boxel size survey entries\n\n"
                "Your data is NOT permanently deleted, records\n"
                "are marked as 'reset' and can be recovered\n"
                "from the database if needed.\n\n"
                "Are you sure you want to reset?",
            )
            if not confirmed:
                return
            obs_count = self.observer_storage.reset_sample_progress()
            boxel_count = self.observer_storage.reset_boxel_entries()
            self.model.add_comms_message(
                f"[OPTIONS] Observer progress reset ({obs_count} samples, {boxel_count} boxel entries)."
            )
        except Exception as e:
            logger.error("Failed to reset observer progress: %s", e)
            self.model.add_comms_message(f"[OPTIONS] Failed to reset progress: {e}")

    def handle_about(self):
        """Handle About dialog."""
        try:
            version = self.config.get("VERSION", "")

            about_text = "\n".join([
                f"DW3 Survey Logger v{version} (Beta)\n",
                "by CMDR Frank Elgyn\n",
                "A companion tool for the Distant Worlds 3 expedition.",
                "Tracks Earth-like world candidates, stellar density",
                "sampling, and boxel size survey data.\n",
                "All data is stored locally, nothing is uploaded.\n",
                "Features:",
                "  - Real-time journal monitoring",
                "  - Earth Similarity and Goldilocks scoring",
                "  - XLSX exports",
                "  - Observer overlay with global hotkey support\n",
                "               Fly Safe CMDR o7",
            ])

            self.view.show_about_dialog(about_text)
        except Exception as e:
            logger.error("About: %s", e, exc_info=True)

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
                    except Exception as e:
                        logger.debug("get_similarity_breakdown failed: %s", e)
                        pass

                if goldilocks_score >= 0:
                    try:
                        from earth_similarity_score import calculate_goldilocks_score
                        goldilocks_data = calculate_goldilocks_score(candidate_data)
                        goldilocks_breakdown = goldilocks_data.get("breakdown", {})
                    except Exception as e:
                        logger.debug("calculate_goldilocks_score failed: %s", e)
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
            logger.error("Log candidate: %s", e, exc_info=True)

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
