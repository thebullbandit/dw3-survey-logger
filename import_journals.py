"""
Journal Import Tool
===================

Import and process historical Elite Dangerous journal files.

This allows users to scan all their old journal files and import
existing discoveries into the database.
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   import_journals.py
#
# Connected modules (direct imports):
#   earth2_database, earth_similarity_score, error_handling, model
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import argparse

_logger = logging.getLogger("dw3.import_journals")


# ============================================================================
# CLASSES
# ============================================================================

class JournalImporter:
    """Import historical journal files"""
    
    def __init__(self, database, model, logger=None):
        """
        Initialize importer
        
        Args:
            database: Database instance
            model: Model instance
            logger: Logger instance (optional)
        """
        self.database = database
        self.model = model
        self.logger = logger
        
        # Statistics
        self.files_processed = 0
        self.events_processed = 0
        self.candidates_found = 0
        self.duplicates_skipped = 0
        self.errors = 0
    
    def _log(self, message):
        """Log message (if logger available)"""
        if self.logger:
            self.logger.info(message)
        else:
            print(message)
    
    def import_journal_directory(self, journal_dir: Path, cmdr_filter: str = None) -> Dict[str, int]:
        """
        Import all journal files from a directory
        
        Args:
            journal_dir: Directory containing journal files
            cmdr_filter: Only import files for this commander (None = all)
            
        Returns:
            Statistics dictionary
        """
        # Find all journal files
        journal_files = sorted(journal_dir.glob("Journal.*.log"))
        
        if not journal_files:
            self._log(f"No journal files found in {journal_dir}")
            return self._get_stats()
        
        self._log(f"Found {len(journal_files)} journal files")
        
        # Process each file
        for journal_file in journal_files:
            try:
                self._process_journal_file(journal_file, cmdr_filter)
            except Exception as e:
                self._log(f"Error processing {journal_file.name}: {e}")
                self.errors += 1
        
        return self._get_stats()
    
    def _process_journal_file(self, journal_file: Path, cmdr_filter: str = None):
        """Process a single journal file"""
        self._log(f"Processing: {journal_file.name}")
        
        current_cmdr = None
        current_system = None
        star_pos = None
        
        with open(journal_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # Parse JSON event
                    line = line.strip()
                    if not line:
                        continue
                    
                    event = json.loads(line)
                    event_type = event.get("event", "")
                    
                    self.events_processed += 1
                    
                    # Track commander
                    if event_type == "LoadGame":
                        current_cmdr = event.get("Commander", "")
                        self._log(f"  Commander: {current_cmdr}")
                    
                    # Skip if filtering by commander
                    if cmdr_filter and current_cmdr != cmdr_filter:
                        continue
                    
                    # Track current system
                    if event_type in ["FSDJump", "Location"]:
                        current_system = event.get("StarSystem", "")
                        star_pos = event.get("StarPos", [0, 0, 0])
                    
                    # Process scan events
                    if event_type == "Scan":
                        self._process_scan_event(event, current_cmdr, current_system, star_pos)
                    
                except json.JSONDecodeError as e:
                    self._log(f"  JSON error on line {line_num}: {e}")
                    self.errors += 1
                except Exception as e:
                    self._log(f"  Error processing line {line_num}: {e}")
                    self.errors += 1
        
        self.files_processed += 1
    
    def _format_atmosphere(self, event: Dict[str, Any]) -> str:
        """Format atmosphere information from scan event"""
        # Try to get atmosphere type first
        atmo_type = event.get("AtmosphereType", "")
        if atmo_type:
            return atmo_type
        
        # Try to get atmosphere description
        atmosphere = event.get("Atmosphere", "")
        if atmosphere:
            return atmosphere
        
        # Try to build from composition
        composition = event.get("AtmosphereComposition", [])
        if composition:
            # Get top 2 components
            components = []
            for comp in composition[:2]:
                name = comp.get("Name", "")
                percent = comp.get("Percent", 0)
                if name and percent > 5:  # Only show components > 5%
                    components.append(f"{name} {percent:.0f}%")
            
            if components:
                return ", ".join(components)
        
        return ""
    
    def _process_scan_event(
        self,
        event: Dict[str, Any],
        cmdr_name: str,
        system_name: str,
        star_pos: List[float]
    ):
        """Process a scan event"""
        # Check if it's a candidate
        body_name = event.get("BodyName", "")
        planet_class = event.get("PlanetClass", "")
        terraform_state = event.get("TerraformState", "")
        
        # Is it a candidate?
        is_elw = planet_class in {"Earthlike body", "Earth-like body"}
        is_terraformable = "Candidate for terraforming" in terraform_state
        
        if not (is_elw or is_terraformable):
            return  # Not a candidate
        
        # Build candidate data
        candidate_data = {
            "timestamp_utc": event.get("timestamp", ""),
            "event": "Scan",
            # Game's unique, stable system ID (used for de-dupe + observer linking)
            # IMPORTANT: earth2_database INSERT uses named binding :system_address,
            # so this key must ALWAYS exist even if value is None.
            "system_address": event.get("SystemAddress"),
            "star_system": system_name or "Unknown",
            "body_name": body_name,
            "body_id": event.get("BodyID", 0),
            "distance_from_arrival_ls": event.get("DistanceFromArrivalLS", 0.0),
            "candidate_type": "ELW" if is_elw else "Terraformable HMC/WW/RW/AW",
            "terraform_state": terraform_state,
            "planet_class": planet_class,
            "atmosphere": self._format_atmosphere(event),
            "volcanism": event.get("Volcanism", ""),
            "mass_em": event.get("MassEM", 0.0),
            "radius_km": event.get("Radius", 0.0) / 1000.0,
            "surface_gravity_g": event.get("SurfaceGravity", 0.0) / 9.81,
            "surface_temp_k": event.get("SurfaceTemperature", 0.0),
            "surface_pressure_atm": event.get("SurfacePressure", 0.0) / 101325.0,
            "landable": "Yes" if event.get("Landable", False) else "No",
            "tidal_lock": "Yes" if event.get("TidalLock", False) else "No",
            "rotation_period_days": event.get("RotationPeriod", 0.0) / 86400.0,
            "orbital_period_days": event.get("OrbitalPeriod", 0.0) / 86400.0,
            "semi_major_axis_au": event.get("SemiMajorAxis", 0.0) / 1.496e11,
            "orbital_eccentricity": event.get("Eccentricity", 0.0),
            "orbital_inclination_deg": event.get("OrbitalInclination", 0.0),
            "arg_of_periapsis_deg": event.get("Periapsis", 0.0),
            "ascending_node_deg": event.get("AscendingNode", 0.0),
            "mean_anomaly_deg": event.get("MeanAnomaly", 0.0),
            "axial_tilt_deg": event.get("AxialTilt", 0.0),
            "was_discovered": "True" if event.get("WasDiscovered", False) else "False",
            "was_mapped": "True" if event.get("WasMapped", False) else "False",
            "cmdr_name": cmdr_name or "Unknown",
            "session_id": "IMPORT"
        }
        
        # Add star position
        if star_pos:
            candidate_data["star_pos_x"] = star_pos[0]
            candidate_data["star_pos_y"] = star_pos[1]
            candidate_data["star_pos_z"] = star_pos[2]
            
            # Calculate distance from Sol
            distance = self.model.calculate_sol_distance(star_pos[0], star_pos[1], star_pos[2])
            candidate_data["distance_from_sol_ly"] = distance
        
        # Calculate rating
        temp_k = candidate_data["surface_temp_k"]
        gravity_g = candidate_data["surface_gravity_g"]
        dist_ly = candidate_data.get("distance_from_sol_ly", 0.0)
        dist_ls = candidate_data.get("distance_from_arrival_ls", 0.0)
        
        # Calculate rating using new similarity score system
        rating, similarity_score = self.model.calculate_earth2_rating(
            temp_k, gravity_g, dist_ls, candidate_data
        )
        candidate_data["earth2_rating"] = rating
        
        # Store similarity score if available
        if similarity_score >= 0:
            candidate_data["similarity_score"] = similarity_score
        
        # Calculate Goldilocks habitability score
        try:
            from earth_similarity_score import calculate_goldilocks_score
            goldilocks = calculate_goldilocks_score(candidate_data)
            if goldilocks["total"] >= 0:
                candidate_data["goldilocks_score"] = goldilocks["total"]
                candidate_data["goldilocks_category"] = goldilocks["category"]
        except Exception as e:
            _logger.debug("Goldilocks calculation failed: %s", e)
        
        # Calculate worth landing
        worth, reason = self.model.calculate_worth_landing(temp_k, gravity_g, dist_ly)
        candidate_data["worth_landing"] = worth
        candidate_data["worth_reason"] = reason
        
        # Try to insert into database
        try:
            was_new = self.database.log_candidate(candidate_data)
            
            if was_new:
                self.candidates_found += 1
                
                # Format output with both scores
                score_text = ""
                if similarity_score >= 0:
                    score_text += f" Sim:{similarity_score:.1f}"
                
                goldilocks_score = candidate_data.get("goldilocks_score", -1)
                if goldilocks_score >= 0:
                    stars = "⭐" * min(goldilocks_score // 3, 5)
                    score_text += f" | Gold:{goldilocks_score}/16 {stars}"
                
                self._log(f"    ✓ {body_name} ({rating}{score_text}) - {candidate_data['candidate_type']}")
            else:
                self.duplicates_skipped += 1
        
        except Exception as e:
            self._log(f"    ✗ Failed to log {body_name}: {e}")
            self.errors += 1
    
    def _get_stats(self) -> Dict[str, int]:
        """Get import statistics"""
        return {
            "files_processed": self.files_processed,
            "events_processed": self.events_processed,
            "candidates_found": self.candidates_found,
            "duplicates_skipped": self.duplicates_skipped,
# ============================================================================
# FUNCTIONS
# ============================================================================

            "errors": self.errors
        }


def main():
    """Main entry point for journal import"""
    parser = argparse.ArgumentParser(
        description="Import historical Elite Dangerous journal files"
    )
    parser.add_argument(
        "--journal-dir",
        type=Path,
        required=True,
        help="Directory containing journal files"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to database file"
    )
    parser.add_argument(
        "--cmdr",
        type=str,
        help="Only import journals for this commander"
    )
    
    args = parser.parse_args()
    
    # Setup
    from earth2_database import Earth2Database
    from model import Earth2Model
    from dependency_injection import FileLogger
    
    # Create logger
    logger = FileLogger(args.db_path.parent / "import.log")
    logger.info("=" * 60)
    logger.info("Journal Import Started")
    logger.info("=" * 60)
    
    # Create database
    database = Earth2Database(args.db_path)
    logger.info(f"Database: {args.db_path}")
    
    # Create model (for calculations)
    config = {
        "TEMP_A_MIN": 240.0, "TEMP_A_MAX": 320.0,
        "TEMP_B_MIN": 200.0, "TEMP_B_MAX": 360.0,
        "GRAV_A_MIN": 0.80, "GRAV_A_MAX": 1.30,
        "GRAV_B_MIN": 0.50, "GRAV_B_MAX": 1.80,
        "DIST_A_MAX": 5000.0, "DIST_B_MAX": 15000.0,
        "WORTH_DIST_MAX": 8000.0,
        "WORTH_TEMP_MIN": 210.0, "WORTH_TEMP_MAX": 340.0,
        "WORTH_GRAV_MAX": 1.60
    }
    
    model = Earth2Model(database, config)
    
    # Create importer
    importer = JournalImporter(database, model, logger)
    
    # Import
    logger.info(f"Journal directory: {args.journal_dir}")
    if args.cmdr:
        logger.info(f"Filtering by commander: {args.cmdr}")
    
    stats = importer.import_journal_directory(args.journal_dir, args.cmdr)
    
    # Print results
    logger.info("=" * 60)
    logger.info("Import Complete")
    logger.info("=" * 60)
    logger.info(f"Files processed: {stats['files_processed']}")
    logger.info(f"Events processed: {stats['events_processed']}")
    logger.info(f"Candidates found: {stats['candidates_found']}")
    logger.info(f"Duplicates skipped: {stats['duplicates_skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)
    
    print("\n" + "=" * 60)
    print("JOURNAL IMPORT COMPLETE")
    print("=" * 60)
    print(f"Files processed: {stats['files_processed']}")
    print(f"Events processed: {stats['events_processed']}")
# ============================================================================
# ENTRYPOINT
# ============================================================================

    print(f"Candidates found: {stats['candidates_found']}")
    print(f"Duplicates skipped: {stats['duplicates_skipped']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 60)
    
    database.close()


if __name__ == "__main__":
    main()
