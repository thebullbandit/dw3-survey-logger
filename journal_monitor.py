"""
Journal Monitor - Refactored from Monolithic Function
=====================================================

Breaks down the 400-line journal_loop() function into:
- JournalFileReader: File operations and rotation detection
- EventProcessor: Event parsing and routing
- JournalMonitor: Main coordinator (replaces journal_loop)

Integration with JournalStateManager:
- JournalMonitor updates JournalStateManager on relevant events
- UI can query JournalStateManager for current context
- Z-bin change callbacks enable auto-trigger of overlay
"""

# ============================================================================
# IMPORTS
# ============================================================================

import os
import time
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable, TextIO, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    from journal_state_manager import JournalStateManager

from observer_models import generate_event_id


# ============================================================================
# JOURNAL FILE READER
# ============================================================================

class JournalFileReader:
    """Handles journal file operations, rotation detection, and reading"""
    
    def __init__(self, journal_dir: Path, seed_max_bytes: int = 2_000_000):
        """
        Initialize journal file reader
        
        Args:
            journal_dir: Directory containing journal files
            seed_max_bytes: Maximum bytes to pre-scan for initial state
        """
        self.journal_dir = journal_dir
        self.seed_max_bytes = seed_max_bytes
        self.current_file: Optional[Path] = None
        self.file_handle: Optional[TextIO] = None
    
    def find_newest_journal(self) -> Optional[Path]:
        """Find the newest journal file in the directory"""
        try:
            files = sorted(
                self.journal_dir.glob("Journal.*.log"),
                key=lambda p: p.stat().st_mtime
            )
            return files[-1] if files else None
        except Exception:
            return None
    
    def find_all_journals(self) -> list[Path]:
        """Find all journal files sorted by modification time"""
        try:
            return sorted(
                self.journal_dir.glob("Journal.*.log"),
                key=lambda p: p.stat().st_mtime
            )
        except Exception:
            return []
    
    def open_file(self, filepath: Path, from_start: bool = False) -> bool:
        """
        Open a journal file for reading
        
        Args:
            filepath: Path to journal file
            from_start: If True, read from beginning; if False, tail from end
            
        Returns:
            True if successfully opened
        """
        # Close existing file
        self.close()
        
        if not filepath.exists():
            return False
        
        try:
            self.file_handle = filepath.open("r", encoding="utf-8", errors="ignore")
            self.current_file = filepath
            
            # Seek to appropriate position
            if from_start:
                self.file_handle.seek(0, os.SEEK_SET)
            else:
                self.file_handle.seek(0, os.SEEK_END)
            
            return True
            
        except Exception:
            self.file_handle = None
            self.current_file = None
            return False
    
    def read_line(self) -> Optional[str]:
        """
        Read next line from current file
        
        Returns:
            Line string, or None if no data available or file closed
        """
        if not self.file_handle:
            return None
        
        try:
            line = self.file_handle.readline()
            return line if line else None
        except Exception:
            return None
    
    def is_rotated(self) -> bool:
        """
        Check if current file has been rotated or deleted
        
        Returns:
            True if file is no longer valid
        """
        if not self.file_handle or not self.current_file:
            return True
        
        try:
            return self.file_handle.closed or not self.current_file.exists()
        except Exception:
            return True
    
    def seed_initial_state(self, filepath: Path) -> list[Dict[str, Any]]:
        """
        Read initial events from file for state seeding
        
        Args:
            filepath: Journal file to seed from
            
        Returns:
            List of parsed events (Commander, Location, etc.)
        """
        events = []
        
        try:
            with filepath.open("r", encoding="utf-8", errors="ignore") as f:
                data = f.read(self.seed_max_bytes)
                
                for line in data.splitlines():
                    if not line.strip():
                        continue
                    
                    try:
                        evt = json.loads(line)
                        event_type = evt.get("event", "")
                        
                        # Only collect state-relevant events
                        if event_type in {"Commander", "LoadGame", "Location", "FSDJump"}:
                            events.append(evt)
                    except Exception:
                        continue
        except Exception:
            pass
        
        return events
    
    def extract_cmdr_name(self, filepath: Path) -> str:
        """
        Extract commander name from journal file
        
        Args:
            filepath: Journal file to extract from
            
        Returns:
            Commander name or "Unknown"
        """
        try:
            with filepath.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        evt = json.loads(line)
                        event_type = evt.get("event", "")
                        
                        if event_type in {"Commander", "LoadGame"}:
                            name = evt.get("Name") or evt.get("Commander")
                            if name:
                                return name
                    except Exception:
                        continue
        except Exception:
            pass
        
        return "Unknown"
    
    def close(self):
        """Close current file handle"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None
            self.current_file = None


# ============================================================================
# EVENT PROCESSOR
# ============================================================================

class EventProcessor:
    """Processes journal events and routes them appropriately"""
    
    def __init__(self):
        """Initialize event processor"""
        self.events_processed = 0
        self.events_skipped = 0
        
        # Event handlers (callbacks)
        self.on_commander_update: Optional[Callable[[str], None]] = None
        self.on_location_update: Optional[Callable[[Dict], None]] = None
        self.on_scan: Optional[Callable[[Dict], None]] = None
        self.on_saa_complete: Optional[Callable[[Dict], None]] = None
        self.on_fsd_jump: Optional[Callable[[Dict], None]] = None
    
    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a journal line into an event dictionary
        
        Args:
            line: Raw journal line
            
        Returns:
            Parsed event dict, or None if invalid
        """
        line = line.strip()
        if not line:
            return None
        
        try:
            evt = json.loads(line)
            
            # Validate required fields
            if "event" not in evt or "timestamp" not in evt:
                self.events_skipped += 1
                return None
            
            self.events_processed += 1
            return evt
            
        except Exception:
            self.events_skipped += 1
            return None
    
    def process_event(self, evt: Dict[str, Any]) -> bool:
        """
        Process an event and route to appropriate handler
        
        Args:
            evt: Event dictionary
            
        Returns:
            True if event was handled
        """
        event_type = evt.get("event", "")
        
        # Commander updates
        if event_type in {"Commander", "LoadGame"}:
            name = evt.get("Name") or evt.get("Commander")
            if name and self.on_commander_update:
                self.on_commander_update(name)
                return True
        
        # Location updates
        elif event_type in {"Location", "FSDJump"}:
            if self.on_location_update:
                self.on_location_update(evt)
            
            # Also handle FSD jump separately for system tracking
            if event_type == "FSDJump" and self.on_fsd_jump:
                self.on_fsd_jump(evt)
            return True
        
        # Scan events
        elif event_type == "Scan":
            if self.on_scan:
                self.on_scan(evt)
                return True
        
        # SAA scan complete
        elif event_type == "SAAScanComplete":
            if self.on_saa_complete:
                self.on_saa_complete(evt)
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics"""
        return {
            "events_processed": self.events_processed,
            "events_skipped": self.events_skipped
        }


# ============================================================================
# JOURNAL MONITOR (Main Coordinator)
# ============================================================================

class JournalMonitor:
    """
    Main journal monitoring coordinator
    Replaces the monolithic journal_loop() function

    Optionally integrates with JournalStateManager for overlay UI support.
    """

    def __init__(
        self,
        journal_dir: Path,
        model,
        presenter,
        config: Dict[str, Any],
        state_manager: Optional['JournalStateManager'] = None
    ):
        """
        Initialize journal monitor

        Args:
            journal_dir: Directory containing journal files
            model: Earth2Model instance
            presenter: Earth2Presenter instance
            config: Configuration dictionary
            state_manager: Optional JournalStateManager for overlay UI integration
        """
        self.journal_dir = journal_dir
        self.model = model
        self.presenter = presenter
        self.config = config
        self.state_manager = state_manager

        # Components
        self.file_reader = JournalFileReader(journal_dir)
        self.event_processor = EventProcessor()

        # State
        self.current_cmdr: Optional[str] = None
        self.current_session_id: Optional[str] = None
        self.current_system: Optional[str] = None
        self.system_address: Optional[int] = None
        self.star_pos: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.visited_systems: set[str] = set()

        # Control events
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.rescan_event = threading.Event()

        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None

        # Connect event processor callbacks
        self._setup_event_handlers()

        # Polling intervals
        self.poll_fast = config.get("POLL_SECONDS_FAST", 0.1)
        self.poll_slow = config.get("POLL_SECONDS_SLOW", 0.25)

    
    def _setup_event_handlers(self):
        """Setup event processor callbacks"""
        self.event_processor.on_commander_update = self._handle_commander_update
        self.event_processor.on_location_update = self._handle_location_update
        self.event_processor.on_scan = self._handle_scan
        self.event_processor.on_saa_complete = self._handle_saa_complete
        self.event_processor.on_fsd_jump = self._handle_fsd_jump
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    def _handle_commander_update(self, cmdr_name: str):
        """Handle commander name update"""
        if cmdr_name != self.current_cmdr:
            self.current_cmdr = cmdr_name
            self.presenter.update_cmdr(cmdr_name)
            self.presenter.add_comms_message(f"COMMANDER: {cmdr_name}")

            # Update state manager
            if self.state_manager:
                self.state_manager.on_commander({'Name': cmdr_name})
    
    def _handle_location_update(self, evt: Dict[str, Any]):
        """Handle location update (FSDJump or Location event)"""
        self.current_system = evt.get("StarSystem", self.current_system)
        self.system_address = evt.get("SystemAddress", self.system_address)

        # Update star position
        star_pos = evt.get("StarPos")
        if isinstance(star_pos, list) and len(star_pos) == 3:
            try:
                x, y, z = float(star_pos[0]), float(star_pos[1]), float(star_pos[2])

                # Validate coordinates
                if all(abs(coord) < 100000 for coord in [x, y, z]):
                    self.star_pos = (x, y, z)
            except (ValueError, TypeError):
                pass

        # Update model 'signal' + current context so Status/Target Lock can reflect jumps
        # (Add Observation uses JournalStateManager; the main panels use model status.)
        try:
            if self.current_system:
                self.model.update_status({
                    "last_signal_local": self.current_system,
                    # Populate target-lock context even when we haven't logged a candidate yet
                    "last_system": self.current_system,
                })
        except Exception:
            pass

        # Update state manager (Location event only, FSDJump handled separately)
        if self.state_manager and evt.get("event") == "Location":
            self.state_manager.on_location(evt)
    
    def _handle_fsd_jump(self, evt: Dict[str, Any]):
        """Handle FSD jump for system tracking"""
        system_name = evt.get("StarSystem")
        if system_name and system_name not in self.visited_systems:
            self.visited_systems.add(system_name)
            self.model.increment_status("session_systems_count")

        # Update state manager (triggers Z-bin change detection)
        if self.state_manager:
            self.state_manager.on_fsd_jump(evt)
    
    def _handle_scan(self, evt: Dict[str, Any]):
        """Handle scan event"""
        # Increment bodies scanned counter
        if evt.get("BodyName"):
            self.model.increment_status("session_bodies_scanned")

        # Update state manager
        if self.state_manager:
            self.state_manager.on_scan(evt)
        # Keep Target Lock in sync with what you're currently scanning.
        # If this scan turns into a candidate, presenter.log_candidate() will overwrite these fields.
        try:
            system = (evt.get("StarSystem") or self.current_system or "").strip()
            body_name = (evt.get("BodyName") or "").strip()
            planet_class = (evt.get("PlanetClass") or "").strip()
            if system:
                update = {"last_system": system}
                if body_name:
                    update.update({
                        "last_body": body_name,
                        "last_type": planet_class or "-",
                        "last_rating": "-",
                        "last_worth": "-",
                        "last_reason": "Scanning...",
                        "last_inara": self.model.generate_inara_link(system),
                    })
                self.model.update_status(update)
        except Exception:
            pass


        # Check if this is an Earth2 candidate
        candidate_data = self._parse_candidate(evt, "Scan")

        if candidate_data:
            # Log through presenter
            self.presenter.log_candidate(candidate_data)
    
    def _handle_saa_complete(self, evt: Dict[str, Any]):
        """Handle SAA scan complete event"""
        # Could track DSS mapping here
        pass
    
    def _parse_candidate(self, evt: Dict[str, Any], event_type: str) -> Optional[Dict[str, Any]]:
        """
        Parse scan event into candidate data
        
        Args:
            evt: Scan event dictionary
            event_type: Type of event ("Scan" or "SAAScanComplete")
            
        Returns:
            Candidate data dictionary, or None if not a candidate
        """
        # Check if Earth2 candidate
        planet_class = evt.get("PlanetClass", "")
        terraform_state = evt.get("TerraformState", "")
        
        is_elw = planet_class in {"Earthlike body", "Earth-like body"}
        is_terraformable = "Terraformable" in terraform_state
        
        if not (is_elw or is_terraformable):
            return None
        
        # Determine candidate type
        if is_elw:
            candidate_type = "ELW"
        else:
            candidate_type = f"{planet_class} - Terraformable"
        
        # Extract data
        system = evt.get("StarSystem") or self.current_system
        body_name = evt.get("BodyName", "")
        
        if not system or not body_name:
            return None
        
        # Get physical properties
        temp_k = self._to_float(evt.get("SurfaceTemperature"))
        gravity_ms2 = self._to_float(evt.get("SurfaceGravity"))
        gravity_g = self.model.calculate_gravity_g(gravity_ms2)
        dist_ls = self._to_float(evt.get("DistanceFromArrivalLS"))
        
        # Calculate ratings with similarity score
        rating, similarity_score = self.model.calculate_earth2_rating(temp_k, gravity_g, dist_ls)
        worth, reason = self.model.calculate_worth_landing(temp_k, gravity_g, dist_ls)
        
        # Build candidate data
        x, y, z = self.star_pos
        dist_sol = self.model.calculate_sol_distance(x, y, z)

        # Generate event_id for linking with observer_notes
        event_id = generate_event_id(evt)

        # Get system_address as integer
        system_address = evt.get("SystemAddress") or self.system_address

        candidate_data = {
            "timestamp_utc": evt.get("timestamp", ""),
            "event": event_type,
            "event_id": event_id,

            # Identity / session
            "cmdr_name": self.current_cmdr or "Unknown",
            "session_id": self.current_session_id or "",

            # System / body
            "star_system": system,
            "system_address": system_address,
            "body_name": body_name,
            "body_id": evt.get("BodyID"),

            # Classification
            "candidate_type": candidate_type,
            "terraform_state": terraform_state,
            "planet_class": planet_class,

            # Key scan properties
            "distance_from_arrival_ls": dist_ls,
            "surface_temp_k": temp_k,
            "surface_gravity_g": gravity_g,

            # Extra scan properties (may be missing in journal event depending on body)
            "atmosphere": evt.get("Atmosphere", ""),
            "volcanism": evt.get("Volcanism", ""),
            "mass_em": self._to_float(evt.get("MassEM")),
            "radius_km": self._to_float(evt.get("Radius")),
            "surface_pressure_atm": self._to_float(evt.get("SurfacePressure")),
            "landable": evt.get("Landable"),
            "tidal_lock": evt.get("TidalLock"),

            # Orbital / rotation (journal uses seconds for many of these; store as days when possible)
            "rotation_period_days": self._to_float(evt.get("RotationPeriod")) / 86400.0 if evt.get("RotationPeriod") not in (None, "") else None,
            "orbital_period_days": self._to_float(evt.get("OrbitalPeriod")) / 86400.0 if evt.get("OrbitalPeriod") not in (None, "") else None,
            "semi_major_axis_au": self._to_float(evt.get("SemiMajorAxis")) / 149597870700.0 if evt.get("SemiMajorAxis") not in (None, "") else None,
            "orbital_eccentricity": self._to_float(evt.get("Eccentricity")),
            "orbital_inclination_deg": self._to_float(evt.get("OrbitalInclination")),
            "arg_of_periapsis_deg": self._to_float(evt.get("Periapsis")),
            "ascending_node_deg": self._to_float(evt.get("AscendingNode")),
            "mean_anomaly_deg": self._to_float(evt.get("MeanAnomaly")),
            "axial_tilt_deg": self._to_float(evt.get("AxialTilt")),

            # Flags
            "was_discovered": evt.get("WasDiscovered"),
            "was_mapped": evt.get("WasMapped"),

            # Ratings
            "earth2_rating": rating,
            "similarity_score": similarity_score,

            # Worthiness
            "worth_landing": worth,
            "worth_reason": reason,

            # Location
            "distance_from_sol_ly": dist_sol,
            "star_pos_x": x,
            "star_pos_y": y,
            "star_pos_z": z,
        }
        
        return candidate_data
    
    @staticmethod
    def _to_float(value) -> Optional[float]:
        """Safely convert value to float"""
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None
    
    # ========================================================================
    # MONITORING OPERATIONS
    # ========================================================================
    
    def start(self):
        """Start journal monitoring in background thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.presenter.add_comms_message("[SYSTEM] Journal monitor started")
    
    def stop(self):
        """Stop journal monitoring"""
        self.stop_event.set()

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

        self.file_reader.close()

        # End current session
        if self.current_session_id:
            self.model.end_session()

        # Clear state manager session
        if self.state_manager:
            self.state_manager.clear_session()

        self.presenter.add_comms_message("[SYSTEM] Journal monitor stopped")
    
    def pause(self):
        """Pause monitoring"""
        self.pause_event.set()
        self.presenter.update_scan_status("PAUSED")
    
    def resume(self):
        """Resume monitoring"""
        self.pause_event.clear()
        self.presenter.update_scan_status("ACTIVE")
    
    def request_rescan(self):
        """Request a full journal rescan"""
        self.rescan_event.set()

    def set_journal_dir(self, journal_dir: Path):
        """Update the journal directory (applies live) and trigger a rescan."""
        journal_dir = Path(journal_dir).expanduser()
        self.journal_dir = journal_dir
        self.file_reader.journal_dir = journal_dir

        # Force file reopen on next loop
        try:
            self.file_reader.close()
        except Exception:
            pass

        # Trigger rescan to re-seed state (cmdr/system) from the new folder
        self.request_rescan()
    
    def _monitor_loop(self):
        """Main monitoring loop (runs in background thread)"""
        try:
            # Initialize
            self._initialize_monitoring()
            
            last_journal_check = time.time()
            
            # Main loop
            while not self.stop_event.is_set():
                # Handle pause
                if self.pause_event.is_set():
                    time.sleep(self.poll_slow)
                    continue
                
                # Handle rescan request
                if self.rescan_event.is_set():
                    self.rescan_event.clear()
                    self._perform_rescan()
                    continue
                
                # Check for journal rotation (every 5 seconds)
                if time.time() - last_journal_check > 5.0:
                    last_journal_check = time.time()
                    self._check_journal_rotation()

                # Check if file was rotated/deleted
                if self.file_reader.is_rotated():
                    self._reopen_current_file()
                
                # Read and process new line
                line = self.file_reader.read_line()
                
                if not line:
                    time.sleep(self.poll_fast)
                    continue
                
                # Parse and process event
                evt = self.event_processor.parse_line(line)
                
                if evt:
                    self.event_processor.process_event(evt)
                    
                    # Update statistics
                    stats = self.event_processor.get_stats()
                    self.model.update_status(stats)
                    
                    # Update heartbeat
                    self.presenter.update_scan_status("ACTIVE")
                    
        except Exception as e:
            self.presenter.add_comms_message(f"[ERROR] Monitor crashed: {e}")
        
        finally:
            self.file_reader.close()
    
    def _initialize_monitoring(self):
        """Initialize monitoring - find and open journal file"""
        journal_file = self.file_reader.find_newest_journal()
        
        if not journal_file:
            self.presenter.update_scan_status("NO SIGNAL")
            self.presenter.add_comms_message("[SYSTEM] Waiting for journal file...")
            
            # Wait for journal file to appear
            while not self.stop_event.is_set():
                time.sleep(self.poll_slow)
                journal_file = self.file_reader.find_newest_journal()
                if journal_file:
                    break
        
        if self.stop_event.is_set():
            return
        
        # Open journal file
        test_mode = self.config.get("TEST_MODE", False)
        from_start = test_mode and self.config.get("TEST_READ_FROM_START", False)
        
        if self.file_reader.open_file(journal_file, from_start=from_start):
            # Seed initial state
            seed_events = self.file_reader.seed_initial_state(journal_file)
            for evt in seed_events:
                self.event_processor.process_event(evt)
            
            # Extract commander and start session
            cmdr_name = self.file_reader.extract_cmdr_name(journal_file)
            if cmdr_name != "Unknown":
                self.current_cmdr = cmdr_name
                self.current_session_id = self.model.start_session(
                    cmdr_name,
                    journal_file.name
                )
                self.presenter.update_cmdr(cmdr_name)

                # Update state manager with session info
                if self.state_manager:
                    self.state_manager.set_session_info(
                        self.current_session_id,
                        cmdr_name
                    )
            
            # Update UI
            mode = "from start" if from_start else "tail"
            self.presenter.update_journal_status(journal_file.name, mode)
            self.presenter.update_scan_status("ARMED")
            self.presenter.add_comms_message(f"[JOURNAL] Monitoring {journal_file.name} ({mode})")
    
    def _check_journal_rotation(self):
        """Check if journal file has rotated to a new file"""
        newest = self.file_reader.find_newest_journal()
        
        if newest and newest != self.file_reader.current_file:
            self.presenter.add_comms_message(f"[JOURNAL] Rotation detected: {newest.name}")
            
            if self.file_reader.open_file(newest, from_start=False):
                # Extract new commander if changed
                cmdr_name = self.file_reader.extract_cmdr_name(newest)
                if cmdr_name != "Unknown" and cmdr_name != self.current_cmdr:
                    self._handle_commander_update(cmdr_name)
                
                self.presenter.update_journal_status(newest.name, "tail")
    
    def _reopen_current_file(self):
        """Reopen current file after rotation/deletion detected"""
        if self.file_reader.current_file:
            self.presenter.add_comms_message("[JOURNAL] Reopening file after rotation")
            self.file_reader.open_file(self.file_reader.current_file, from_start=False)

    def _perform_rescan(self):
        """Perform full rescan of all journal files"""
        self.presenter.update_scan_status("RESCANNING")
        self.presenter.add_comms_message("[RESCAN] Scanning full journal history...")
        
        journal_files = self.file_reader.find_all_journals()
        
        if not journal_files:
            self.presenter.add_comms_message("[RESCAN] No journal files found")
            return
        
        # Process each file from start
        for journal_file in journal_files:
            if self.stop_event.is_set():
                break
            
            self.presenter.add_comms_message(f"[RESCAN] Processing {journal_file.name}...")
            
            try:
                with journal_file.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if self.stop_event.is_set():
                            break
                        
                        evt = self.event_processor.parse_line(line)
                        if evt:
                            self.event_processor.process_event(evt)
            except Exception as e:
                self.presenter.add_comms_message(f"[RESCAN] Error reading {journal_file.name}: {e}")
        
        # Reopen newest file for tailing
        newest = self.file_reader.find_newest_journal()
        if newest:
            self.file_reader.open_file(newest, from_start=False)
            self.presenter.update_journal_status(newest.name, "tail")
        
        self.presenter.update_scan_status("ARMED")
        self.presenter.add_comms_message("[RESCAN] Complete")
        
        # Reload rating distribution
        self.model.load_rating_distribution(force_refresh=True)
