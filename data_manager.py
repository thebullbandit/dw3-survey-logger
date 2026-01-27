"""
Database-First Data Management
===============================

Migrates from dual CSV/database writes to database-first approach.

Benefits:
- Single source of truth (database)
- CSV export on-demand
- Better data integrity
- Transactional operations
- Query capabilities
"""

# ============================================================================
# IMPORTS
# ============================================================================

from pathlib import Path
from typing import Optional, List, Dict, Any
import csv
from datetime import datetime


# ============================================================================
# FUNCTIONS
# ============================================================================

def _export_timestamp() -> str:
    """Timestamp for export filenames: YYYY-MM-DD_HH-MM (no seconds)."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")

from error_handling import (
    ErrorHandler,
    DatabaseError,
    FileSystemError,
    with_error_handling,
    retry_on_error
)


# ============================================================================
# CLASSES
# ============================================================================

class DataManager:
    """
    Database-first data management
    
    Replaces scattered CSV writes with centralized database operations
    and on-demand CSV export.
    """
    
    def __init__(self, database, error_handler: ErrorHandler, config: Dict[str, Any]):
        """
        Initialize data manager
        
        Args:
            database: Database instance (IDatabase)
            error_handler: Error handler
            config: Configuration dict
        """
        self.db = database
        self.error_handler = error_handler
        self.config = config
        
        # Export settings
        self.auto_export_csv = config.get("AUTO_EXPORT_CSV", False)
        self.csv_export_interval = config.get("CSV_EXPORT_INTERVAL", 100)  # Every N candidates
        
        # Track candidates for auto-export
        self._candidates_since_export = 0
    
    # ========================================================================
    # DATABASE OPERATIONS (Primary)
    # ========================================================================
    
    @with_error_handling("DataManager", "log_candidate", default_return=False)
    @retry_on_error(max_attempts=3, delay_seconds=0.1)
    def log_candidate(self, candidate_data: Dict[str, Any]) -> bool:
        """
        Log candidate to database
        
        Args:
            candidate_data: Candidate information
            
        Returns:
            True if logged successfully, False if duplicate
        """
        try:
            # Write to database
            was_new = self.db.log_candidate(candidate_data)
            
            if was_new:
                self._candidates_since_export += 1
                
                # Auto-export if configured
                if self.auto_export_csv and self._candidates_since_export >= self.csv_export_interval:
                    self._auto_export_csv()
                
                return True
            
            return False
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to log candidate: {e}",
                context={
                    "system": candidate_data.get("star_system"),
                    "body": candidate_data.get("body_name")
                }
            )
    
    @with_error_handling("DataManager", "get_all_candidates", default_return=[])
    def get_all_candidates(self, cmdr_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all candidates from database
        
        Args:
            cmdr_name: Filter by commander (None = all)
            
        Returns:
            List of candidate dictionaries
        """
        try:
            # Query database
            if cmdr_name:
                query = "SELECT * FROM candidates WHERE cmdr_name = ? ORDER BY timestamp_utc"
                cursor = self.db.conn.execute(query, (cmdr_name,))
            else:
                query = "SELECT * FROM candidates ORDER BY timestamp_utc"
                cursor = self.db.conn.execute(query)
            
            # Convert to list of dicts
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor:
                results.append(dict(zip(columns, row)))
            
            return results
            
        except Exception as e:
            raise DatabaseError(f"Failed to get candidates: {e}")
    
    @with_error_handling("DataManager", "get_candidates_by_rating", default_return=[])
    def get_candidates_by_rating(
        self,
        rating: str,
        cmdr_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get candidates by rating
        
        Args:
            rating: Rating to filter ("A", "B", or "C")
            cmdr_name: Filter by commander
            
        Returns:
            List of candidate dictionaries
        """
        try:
            if cmdr_name:
                query = """
                    SELECT * FROM candidates 
                    WHERE earth2_rating = ? AND cmdr_name = ?
                    ORDER BY timestamp_utc
                """
                cursor = self.db.conn.execute(query, (rating, cmdr_name))
            else:
                query = """
                    SELECT * FROM candidates 
                    WHERE earth2_rating = ?
                    ORDER BY timestamp_utc
                """
                cursor = self.db.conn.execute(query, (rating,))
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor:
                results.append(dict(zip(columns, row)))
            
            return results
            
        except Exception as e:
            raise DatabaseError(f"Failed to get candidates by rating: {e}")
    
    @with_error_handling("DataManager", "get_statistics", default_return={})
    def get_statistics(self, cmdr_name: Optional[str] = None) -> Dict[str, int]:
        """
        Get statistics from database
        
        Args:
            cmdr_name: Filter by commander
            
        Returns:
            Statistics dictionary
        """
        try:
            if cmdr_name:
                stats = self.db.get_cmdr_stats(cmdr_name)
                if stats:
                    return stats
            
            # Get all stats
            all_stats = self.db.get_all_cmdr_stats()
            
            return {
                "total_all": sum(s["total_all"] for s in all_stats),
                "total_elw": sum(s["total_elw"] for s in all_stats),
                "total_terraformable": sum(s["total_terraformable"] for s in all_stats),
                "total_a_rated": sum(s.get("total_a_rated", 0) for s in all_stats),
                "total_b_rated": sum(s.get("total_b_rated", 0) for s in all_stats),
                "total_c_rated": sum(s.get("total_c_rated", 0) for s in all_stats),
            }
            
        except Exception as e:
            raise DatabaseError(f"Failed to get statistics: {e}")
    
    # ========================================================================
    # CSV EXPORT (On-Demand)
    # ========================================================================


    def _resolve_export_path(self, output_path: Optional[Path], rating_filter: Optional[str]) -> Path:
        """Resolve export path.

        Rules:
        - If output_path is None: write to EXPORT_DIR (or OUTDIR/exports) with timestamped filename.
        - If output_path is a directory: write inside it with timestamped filename.
        - If output_path is a file: keep its directory, but make filename timestamped to avoid overwrite.
        """
        # Choose export directory
        export_dir = None

        if output_path is None:
            export_dir = Path(self.config.get("EXPORT_DIR") or self.config.get("OUTDIR", Path.cwd()) / "exports")
        else:
            output_path = Path(output_path)
            if output_path.exists() and output_path.is_dir():
                export_dir = output_path
            elif output_path.suffix == "":  # treat as directory-ish path
                export_dir = output_path
            else:
                export_dir = output_path.parent

        export_dir.mkdir(parents=True, exist_ok=True)

        stamp = _export_timestamp()

        # Prefix and optional rating
        prefix = self.config.get("ELW_EXPORT_PREFIX", "DW3_ELW")
        if rating_filter:
            filename = f"{prefix}_rating_{rating_filter}_{stamp}.csv"
        else:
            filename = f"{prefix}_{stamp}.csv"

        # If caller provided a file path, keep the base name prefix if they set it explicitly
        if output_path is not None:
            op = Path(output_path)
            if not (op.exists() and op.is_dir()) and op.suffix.lower() == ".csv":
                # Use provided stem as prefix (but still timestamp it)
                stem = op.stem
                if rating_filter:
                    filename = f"{stem}_rating_{rating_filter}_{stamp}.csv"
                else:
                    filename = f"{stem}_{stamp}.csv"

        return export_dir / filename

    
    @with_error_handling("DataManager", "export_to_csv", default_return=False)
    def export_to_csv(
        self,
        output_path: Optional[Path] = None,
        cmdr_name: Optional[str] = None,
        rating_filter: Optional[str] = None
    ) -> bool:
        """
        Export candidates to CSV file
        
        Args:
            output_path: Path to CSV file
            cmdr_name: Filter by commander
            rating_filter: Filter by rating ("A", "B", "C")
            
        Returns:
            True if successful
        """
        try:
            # Resolve output path and apply timestamped naming (no overwrite)
            output_path = self._resolve_export_path(output_path, rating_filter)

            # Get candidates from database
            if rating_filter:
                candidates = self.get_candidates_by_rating(rating_filter, cmdr_name)
            else:
                candidates = self.get_all_candidates(cmdr_name)
            
            if not candidates:
                self.error_handler.logger.info("No candidates to export")
                return True  # Success (no data is not an error)
            
            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write CSV
            with output_path.open('w', newline='', encoding='utf-8') as f:
                # Get field names from first candidate
                fieldnames = list(candidates[0].keys())
                
                # Remove internal fields
                fieldnames = [f for f in fieldnames if f not in ['id', 'created_at']]
                
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for candidate in candidates:
                    # Filter out internal fields
                    row = {k: v for k, v in candidate.items() if k in fieldnames}
                    writer.writerow(row)
            
            self.error_handler.logger.info(
                f"Exported {len(candidates)} candidates to {output_path}"
            )
            
            return True
            
        except IOError as e:
            raise FileSystemError(
                f"Failed to write CSV: {e}",
                context={"path": str(output_path)}
            )
        except Exception as e:
            raise DatabaseError(f"Export failed: {e}")
    
    def _auto_export_csv(self):
        """Auto-export CSV (background operation)"""
        try:
            # Export to timestamped file in EXPORT_DIR (or OUTDIR/exports)
            self.export_to_csv()
            self._candidates_since_export = 0
            
            self.error_handler.logger.info("Auto-export CSV completed")
            
        except Exception as e:
            self.error_handler.logger.error(f"Auto-export failed: {e}")
    
    # ========================================================================
    # IMPORT FROM CSV (Migration Helper)
    # ========================================================================
    
    @with_error_handling("DataManager", "import_from_csv", default_return=0)
    def import_from_csv(self, csv_path: Path) -> int:
        """
        Import candidates from CSV to database
        
        Useful for migrating from old CSV-only system.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Number of candidates imported
        """
        if not csv_path.exists():
            raise FileSystemError(
                f"CSV file not found: {csv_path}",
                context={"path": str(csv_path)}
            )
        
        try:
            imported_count = 0
            duplicate_count = 0
            
            with csv_path.open('r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Convert row to candidate format
                    # (CSV columns match database columns)
                    was_new = self.db.log_candidate(row)
                    
                    if was_new:
                        imported_count += 1
                    else:
                        duplicate_count += 1
            
            self.error_handler.logger.info(
                f"CSV import: {imported_count} new, {duplicate_count} duplicates"
            )
            
            return imported_count
            
        except Exception as e:
            raise DatabaseError(f"CSV import failed: {e}")
    
    # ========================================================================
    # SPECIALIZED QUERIES
    # ========================================================================
    
    @with_error_handling("DataManager", "get_top_systems", default_return=[])
    def get_top_systems(
        self,
        limit: int = 10,
        cmdr_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get systems with most candidates
        
        Args:
            limit: Maximum systems to return
            cmdr_name: Filter by commander
            
        Returns:
            List of (system_name, candidate_count) dicts
        """
        try:
            if cmdr_name:
                query = """
                    SELECT star_system, COUNT(*) as count
                    FROM candidates
                    WHERE cmdr_name = ? AND event = 'Scan'
                    GROUP BY star_system
                    ORDER BY count DESC
                    LIMIT ?
                """
                cursor = self.db.conn.execute(query, (cmdr_name, limit))
            else:
                query = """
                    SELECT star_system, COUNT(*) as count
                    FROM candidates
                    WHERE event = 'Scan'
                    GROUP BY star_system
                    ORDER BY count DESC
                    LIMIT ?
                """
                cursor = self.db.conn.execute(query, (limit,))
            
            results = []
            for row in cursor:
                results.append({
                    "system": row[0],
                    "count": row[1]
                })
            
            return results
            
        except Exception as e:
            raise DatabaseError(f"Failed to get top systems: {e}")
    
    @with_error_handling("DataManager", "get_recent_discoveries", default_return=[])
    def get_recent_discoveries(
        self,
        limit: int = 10,
        cmdr_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get most recent discoveries
        
        Args:
            limit: Maximum discoveries to return
            cmdr_name: Filter by commander
            
        Returns:
            List of recent candidate dicts
        """
        try:
            if cmdr_name:
                query = """
                    SELECT * FROM candidates
                    WHERE cmdr_name = ? AND event = 'Scan'
                    ORDER BY timestamp_utc DESC
                    LIMIT ?
                """
                cursor = self.db.conn.execute(query, (cmdr_name, limit))
            else:
                query = """
                    SELECT * FROM candidates
                    WHERE event = 'Scan'
                    ORDER BY timestamp_utc DESC
                    LIMIT ?
                """
                cursor = self.db.conn.execute(query, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor:
                results.append(dict(zip(columns, row)))
            
            return results
            
        except Exception as e:
            raise DatabaseError(f"Failed to get recent discoveries: {e}")
    
    @with_error_handling("DataManager", "search_candidates", default_return=[])
    def search_candidates(
        self,
        search_term: str,
        cmdr_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search candidates by system or body name
        
        Args:
            search_term: Search term (partial match)
            cmdr_name: Filter by commander
            
        Returns:
            List of matching candidates
        """
        try:
            search_pattern = f"%{search_term}%"
            
            if cmdr_name:
                query = """
                    SELECT * FROM candidates
                    WHERE (star_system LIKE ? OR body_name LIKE ?)
                    AND cmdr_name = ?
                    ORDER BY timestamp_utc DESC
                """
                cursor = self.db.conn.execute(query, (search_pattern, search_pattern, cmdr_name))
            else:
                query = """
                    SELECT * FROM candidates
                    WHERE star_system LIKE ? OR body_name LIKE ?
                    ORDER BY timestamp_utc DESC
                """
                cursor = self.db.conn.execute(query, (search_pattern, search_pattern))
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor:
                results.append(dict(zip(columns, row)))
            
            return results
            
        except Exception as e:
            raise DatabaseError(f"Search failed: {e}")
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    @with_error_handling("DataManager", "bulk_export", default_return={})
    def bulk_export(
        self,
        output_dir: Path,
        split_by_rating: bool = True,
        split_by_commander: bool = False
    ) -> Dict[str, str]:
        """
        Export candidates to multiple CSV files
        
        Args:
            output_dir: Directory for CSV files
            split_by_rating: Create separate files per rating
            split_by_commander: Create separate files per commander
            
        Returns:
            Dictionary of {filename: path} for created files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported_files = {}

        try:
            stamp = _export_timestamp()
            if split_by_rating:
                # Export by rating
                for rating in ["A", "B", "C"]:
                    filename = f"DW3_ELW_rating_{rating}_{stamp}.csv"
                    filepath = output_dir / filename
                    
                    if self.export_to_csv(filepath, rating_filter=rating):
                        exported_files[filename] = str(filepath)
            
            if split_by_commander:
                # Get all commanders
                all_stats = self.db.get_all_cmdr_stats()
                
                for stats in all_stats:
                    cmdr_name = stats["cmdr_name"]
                    safe_name = "".join(c for c in cmdr_name if c.isalnum() or c in (' ', '-', '_'))
                    filename = f"DW3_ELW_{safe_name}_{stamp}.csv"
                    filepath = output_dir / filename
                    
                    if self.export_to_csv(filepath, cmdr_name=cmdr_name):
                        exported_files[filename] = str(filepath)
            
            if not split_by_rating and not split_by_commander:
                # Export all to single file
                filename = f"DW3_ELW_all_{stamp}.csv"
                filepath = output_dir / filename
                
                if self.export_to_csv(filepath):
                    exported_files[filename] = str(filepath)
            
            return exported_files
            
        except Exception as e:
            raise DatabaseError(f"Bulk export failed: {e}")
