"""
Model Layer - Business Logic and Data Management
=================================================

Handles all data operations, calculations, and business rules.
No UI dependencies - pure business logic.
"""

# ============================================================================
# IMPORTS
# ============================================================================

import logging
import time
import json
import threading

logger = logging.getLogger("dw3.model")
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from urllib.parse import quote_plus
from collections import deque


# ============================================================================
# CLASSES
# ============================================================================

class Earth2Model:
    """Model layer - manages all business logic and data"""
    
    def __init__(self, database, config: Dict[str, Any]):
        """
        Initialize the model
        
        Args:
            database: Earth2Database instance
            config: Configuration dictionary
        """
        self.db = database
        self.config = config
        
        # Thread-safe state
        self._stats_lock = threading.Lock()
        self._status_lock = threading.Lock()
        
        # Shared state dictionaries
        self._stats = {
            "total_all": 0,
            "total_elw": 0,
            "total_terraformable": 0
        }
        
        self._status = {
            "scan_status": "INITIALIZING",
            "events_skipped": 0,
            "current_journal": "",
            "journal_mode": "",
            "cmdr_name": "",
            "last_signal_local": "",
            "session_start": time.time(),
            "session_candidates": 0,
            "session_elw": 0,
            "session_terraformable": 0,
            "session_systems_count": 0,
            "session_bodies_scanned": 0,
            "session_id": "",
            "last_system": "",
            "last_body": "",
            "last_type": "",
            "last_rating": "",
            "last_worth": "",
            "last_reason": "",
            "last_inara": "",
            "last_similarity_score": -1,
            "last_similarity_breakdown": {},
            "last_goldilocks_score": -1,
            "last_goldilocks_breakdown": {},
            "last_log_time": 0,
            "comms": deque(maxlen=self.config.get("COMMS_MAX_LINES", 150))
        }
        
        # Session ratings tracking (using new category system)
        self._session_ratings = {
            "Earth Twin": 0,
            "Excellent": 0,
            "Very Good": 0,
            "Good": 0,
            "Fair": 0,
            "Marginal": 0,
            "Poor": 0,
            "Unknown": 0
        }
        
        # Cache for expensive operations
        self._rating_cache = None
        self._rating_cache_time = 0
        self._rating_cache_ttl = 60  # Cache for 60 seconds
        
    # ========================================================================
    # THREAD-SAFE STATE ACCESS
    # ========================================================================
    
    def get_stats(self) -> Dict[str, int]:
        """Get current statistics (thread-safe)"""
        with self._stats_lock:
            return self._stats.copy()
    
    def update_stats(self, updates: Dict[str, Any]):
        """Update statistics (thread-safe)"""
        with self._stats_lock:
            self._stats.update(updates)
    
    def get_status(self, key: Optional[str] = None) -> Any:
        """Get status value(s) (thread-safe)"""
        with self._status_lock:
            if key:
                return self._status.get(key)
            return self._status.copy()
    
    def update_status(self, updates: Dict[str, Any]):
        """Update status (thread-safe)"""
        with self._status_lock:
            for key, value in updates.items():
                if key == "comms":
                    # Special handling for deque
                    continue
                self._status[key] = value
    
    def add_comms_message(self, message: str):
        """Add message to COMMS feed (thread-safe)"""
        with self._status_lock:
            self._status["comms"].append(message)
    
    def get_comms_messages(self) -> List[str]:
        """Get all COMMS messages (thread-safe)"""
        with self._status_lock:
            return list(self._status["comms"])
    
    def increment_stat(self, stat_name: str, amount: int = 1):
        """Increment a statistic (thread-safe)"""
        with self._stats_lock:
            self._stats[stat_name] = self._stats.get(stat_name, 0) + amount
    
    def increment_status(self, status_name: str, amount: int = 1):
        """Increment a status counter (thread-safe)"""
        with self._status_lock:
            self._status[status_name] = self._status.get(status_name, 0) + amount
    
    # ========================================================================
    # BUSINESS LOGIC - CALCULATIONS
    # ========================================================================
    
    def calculate_sol_distance(self, x: float, y: float, z: float) -> float:
        """Calculate distance from Sol"""
        return (x * x + y * y + z * z) ** 0.5
    
    def calculate_gravity_g(self, surface_gravity_ms2: Optional[float]) -> Optional[float]:
        """
        Convert surface gravity from m/s² to Earth gravities (G)
        
        Args:
            surface_gravity_ms2: Surface gravity in m/s²
            
        Returns:
            Gravity in Earth G, or None if invalid
        """
        if surface_gravity_ms2 is None:
            return None
        
        EARTH_G_MS2 = 9.80665
        return surface_gravity_ms2 / EARTH_G_MS2
    
    def kelvin_to_celsius(self, kelvin: Optional[float]) -> Optional[float]:
        """Convert Kelvin to Celsius"""
        return None if kelvin is None else (kelvin - 273.15)
    
    def calculate_earth2_rating(
        self, 
        temp_k: Optional[float],
        gravity_g: Optional[float], 
        distance_ls: Optional[float],
        candidate_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, float]:
        """
        Calculate Earth 2.0 rating based on conditions
        
        Now uses Earth Similarity Score (Cmdr Coddiwompler's system)
        Returns descriptive category instead of A/B/C
        
        Args:
            temp_k: Surface temperature in Kelvin
            gravity_g: Gravity in Earth G
            distance_ls: Distance to arrival in light-seconds
            candidate_data: Full candidate data dict (for similarity score)
            
        Returns:
            Tuple of (Category string, Similarity score: float)
            Category examples: "Earth Twin", "Excellent", "Very Good", "Good", etc.
        """
        # Calculate similarity score if we have full data
        similarity_score = -1.0
        if candidate_data:
            try:
                from earth_similarity_score import compute_similarity_score, score_to_category
                similarity_score = compute_similarity_score(candidate_data)
                
                # If similarity score is available and valid, use it for rating
                if similarity_score >= 0:
                    category = score_to_category(similarity_score)
                    return category, similarity_score
            except Exception as e:
                # Fall back to old system if similarity calculation fails
                pass
        
        # Fall back to simple categorization based on basic params
        if temp_k is None or gravity_g is None or distance_ls is None:
            return "Unknown", similarity_score
        
        cfg = self.config
        
        # Simple categorization based on temperature and gravity only
        temp_good = cfg["TEMP_A_MIN"] <= temp_k <= cfg["TEMP_A_MAX"]
        grav_good = cfg["GRAV_A_MIN"] <= gravity_g <= cfg["GRAV_A_MAX"]
        
        if temp_good and grav_good:
            return "Good", similarity_score
        else:
            return "Fair", similarity_score
    
    def calculate_worth_landing(
        self,
        temp_k: Optional[float],
        gravity_g: Optional[float],
        distance_ls: Optional[float]
    ) -> Tuple[str, str]:
        """
        Determine if a body is worth landing on
        
        Args:
            temp_k: Surface temperature in Kelvin
            gravity_g: Gravity in Earth G
            distance_ls: Distance to arrival in light-seconds
            
        Returns:
            Tuple of (worth_landing: "Yes"/"No", reason: str)
        """
        cfg = self.config
        
        if temp_k is None or gravity_g is None or distance_ls is None:
            return "No", "Missing data"
        
        # Check all criteria
        if distance_ls > cfg["WORTH_DIST_MAX"]:
            return "No", f"Too far ({distance_ls:.0f} LS)"
        
        if not (cfg["WORTH_TEMP_MIN"] <= temp_k <= cfg["WORTH_TEMP_MAX"]):
            temp_c = self.kelvin_to_celsius(temp_k)
            return "No", f"Temperature extreme ({temp_c:.0f}°C)"
        
        if gravity_g > cfg["WORTH_GRAV_MAX"]:
            return "No", f"High gravity ({gravity_g:.2f}G)"
        
        return "Yes", "Good landing conditions"
    
    def generate_inara_link(self, system_name: str) -> str:
        """Generate Inara system link"""
        return f"https://inara.cz/elite/starsystem/?search={quote_plus(system_name or '')}"
    
    # ========================================================================
    # DATA OPERATIONS
    # ========================================================================
    
    def load_stats_from_db(self, cmdr_name: Optional[str] = None):
        """Load statistics from database"""
        try:
            if cmdr_name:
                cmdr_stats = self.db.get_cmdr_stats(cmdr_name)
                if cmdr_stats:
                    self.update_stats({
                        "total_all": cmdr_stats["total_all"],
                        "total_elw": cmdr_stats["total_elw"],
                        "total_terraformable": cmdr_stats["total_terraformable"],
                    })
                    return
            
            # If no CMDR or multi-CMDR, sum all
            all_stats = self.db.get_all_cmdr_stats()
            self.update_stats({
                "total_all": sum(s["total_all"] for s in all_stats),
                "total_elw": sum(s["total_elw"] for s in all_stats),
                "total_terraformable": sum(s["total_terraformable"] for s in all_stats),
            })
        except Exception as e:
            self._log_error(f"Failed to load stats from database: {e}")
    
    def load_rating_distribution(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        Load rating distribution with caching
        
        Args:
            force_refresh: If True, bypass cache
            
        Returns:
            Dictionary with counts for each rating
        """
        # Check cache
        current_time = time.time()
        if not force_refresh and self._rating_cache is not None:
            if current_time - self._rating_cache_time < self._rating_cache_ttl:
                return self._rating_cache
        
        # Load from database - count candidates by their stored ratings
        # Now using descriptive categories
        ratings = {
            "Earth Twin": 0,
            "Excellent": 0,
            "Very Good": 0,
            "Good": 0,
            "Fair": 0,
            "Marginal": 0,
            "Poor": 0,
            "Unknown": 0
        }
        
        try:
            # Query database for all commander stats
            all_stats = self.db.get_all_cmdr_stats()
            
            # Sum up ratings from all commanders
            for cmdr_stats in all_stats:
                ratings["Earth Twin"] += cmdr_stats.get("total_earth_twin", 0)
                ratings["Excellent"] += cmdr_stats.get("total_excellent", 0)
                ratings["Very Good"] += cmdr_stats.get("total_very_good", 0)
                ratings["Good"] += cmdr_stats.get("total_good", 0)
                ratings["Fair"] += cmdr_stats.get("total_fair", 0)
                ratings["Marginal"] += cmdr_stats.get("total_marginal", 0)
                ratings["Poor"] += cmdr_stats.get("total_poor", 0)
                ratings["Unknown"] += cmdr_stats.get("total_unknown", 0)
            
        except Exception as e:
            self._log_error(f"Failed to load rating distribution: {e}")
        
        # Update cache
        self._rating_cache = ratings
        self._rating_cache_time = current_time
        
        return ratings
    
    def log_candidate(self, candidate_data: Dict[str, Any]) -> bool:
        """
        Log a candidate to the database
        
        Args:
            candidate_data: Dictionary with candidate information
            
        Returns:
            True if successfully logged, False otherwise
        """
        try:
            was_new = self.db.log_candidate(candidate_data)
            
            if was_new:
                # Update statistics
                self.increment_stat("total_all")
                self.increment_status("session_candidates")
                self.increment_status("session_bodies_scanned")
                
                # Update type-specific counters
                cand_type = candidate_data.get("candidate_type", "")
                if cand_type == "ELW":
                    self.increment_stat("total_elw")
                    self.increment_status("session_elw")
                elif "Terraformable" in cand_type:
                    self.increment_stat("total_terraformable")
                    self.increment_status("session_terraformable")
                
                # Update rating counters
                rating = candidate_data.get("earth2_rating", "Unknown")
                if rating in self._session_ratings:
                    with self._status_lock:
                        self._session_ratings[rating] += 1
                
                # Update last log time
                self.update_status({"last_log_time": time.time()})
                
                # Invalidate rating cache
                self._rating_cache = None
                
                return True
            
            return False
            
        except Exception as e:
            self._log_error(f"Failed to log candidate: {e}")
            return False
    
    def start_session(self, cmdr_name: str, journal_file: str) -> str:
        """Start a new exploration session"""
        try:
            session_id = self.db.start_session(cmdr_name, journal_file)
            self.update_status({
                "session_id": session_id,
                "session_start": time.time(),
                "session_candidates": 0,
                "session_elw": 0,
                "session_terraformable": 0,
                "session_systems_count": 0,
                "session_bodies_scanned": 0,
            })
            # Reset session ratings
            with self._status_lock:
                self._session_ratings = {
                    "Earth Twin": 0, "Excellent": 0, "Very Good": 0,
                    "Good": 0, "Fair": 0, "Marginal": 0, "Poor": 0, "Unknown": 0,
                }
            
            return session_id
        except Exception as e:
            self._log_error(f"Failed to start session: {e}")
            return ""
    
    def end_session(self):
        """End the current session"""
        try:
            session_id = self.get_status("session_id")
            if session_id:
                self.db.end_session(session_id)
        except Exception as e:
            self._log_error(f"Failed to end session: {e}")
    
    # ========================================================================
    # SESSION TRACKING
    # ========================================================================
    
    def get_session_ratings(self) -> Dict[str, int]:
        """Get session rating distribution"""
        with self._status_lock:
            return self._session_ratings.copy()
    
    def get_session_duration(self) -> Tuple[int, int]:
        """
        Get session duration
        
        Returns:
            Tuple of (hours, minutes)
        """
        session_start = self.get_status("session_start")
        duration = time.time() - session_start
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        return hours, minutes
    
    def get_session_rate(self) -> float:
        """
        Get candidate discovery rate per hour
        
        Returns:
            Candidates per hour
        """
        session_start = self.get_status("session_start")
        duration = time.time() - session_start
        candidates = self.get_status("session_candidates") or 0
        
        if duration > 0:
            return (candidates / (duration / 3600))
        return 0.0
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    def _log_error(self, message: str):
        """Log error message (can be expanded to write to log file)"""
        logger.error(message)
    
    def reset_session_stats(self):
        """Reset session statistics"""
        self.update_status({
            "session_candidates": 0,
            "session_elw": 0,
            "session_terraformable": 0,
            "session_systems_count": 0,
            "session_bodies_scanned": 0,
            "session_start": time.time(),
        })
        with self._status_lock:
            self._session_ratings = {
                    "Earth Twin": 0, "Excellent": 0, "Very Good": 0,
                    "Good": 0, "Fair": 0, "Marginal": 0, "Poor": 0, "Unknown": 0,
                }
