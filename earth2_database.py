"""
Earth2 Database Module
======================

SQLite database for storing candidate discoveries.

This module was referenced in the refactored code but needs to be created
# ============================================================================
# IMPORTS
# ============================================================================

from the original database implementation.

Integration with ObserverNote:
- Candidates now include event_id for linking to observer_notes
- Use get_candidates_with_observations() for merged data
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   earth2_database.py
#
# Connected modules (direct imports):
#   (none)
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import sqlite3
import time
import hashlib
import threading
import queue
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Tuple
from datetime import datetime


# ============================================================================
# SQL INSERT BINDING KEYS
# ============================================================================
# Keep this list in sync with the named placeholders used in the INSERT inside
# Earth2Database.log_candidate(). Prefilling these keys prevents sqlite3 from
# raising: "You did not supply a value for binding parameter :<name>"
CANDIDATE_INSERT_KEYS = [
    "timestamp_utc",
    "event",
    "event_id",
    "system_address",
    "star_system",
    "body_name",
    "body_id",
    "distance_from_arrival_ls",
    "candidate_type",
    "terraform_state",
    "planet_class",
    "atmosphere",
    "volcanism",
    "mass_em",
    "radius_km",
    "surface_gravity_g",
    "surface_temp_k",
    "surface_pressure_atm",
    "landable",
    "tidal_lock",
    "rotation_period_days",
    "orbital_period_days",
    "semi_major_axis_au",
    "orbital_eccentricity",
    "orbital_inclination_deg",
    "arg_of_periapsis_deg",
    "ascending_node_deg",
    "mean_anomaly_deg",
    "axial_tilt_deg",
    "was_discovered",
    "was_mapped",
    "earth2_rating",
    "similarity_score",
    "goldilocks_score",
    "goldilocks_category",
    "worth_landing",
    "worth_reason",
    "distance_from_sol_ly",
    "star_pos_x",
    "star_pos_y",
    "star_pos_z",
    "cmdr_name",
    "session_id",
]
 

# ============================================================================
# INTERNAL TASK TYPES
# ============================================================================

@dataclass
class _DBTask:
    fn: Callable[[sqlite3.Connection], Any]
    reply_q: "queue.Queue[Tuple[bool, Any]]"


# ============================================================================
# CLASSES
# ============================================================================

class Earth2Database:
    """SQLite database wrapper backed by a single dedicated DB worker thread.

    This implements the 'Option B' architecture:
      - Only ONE thread ever touches the SQLite connection.
      - All reads/writes are funneled through a task queue.
      - Removes intermittent concurrency bugs when journal ingest, UI, export, etc.
        happen at the same time.

    Public API is intentionally kept compatible with your existing code.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._task_q = queue.Queue()
        self._closed = False

        self._worker = threading.Thread(
            target=self._worker_loop,
            name="Earth2DBWorker",
            daemon=True
        )
        self._worker.start()

        # Initialize schema on worker (raises if schema creation fails)
        self._submit(lambda conn: self._create_tables(conn))

    # ------------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------------
    def _worker_loop(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Pragmas: stable + fast enough, and avoids 'database is locked' spikes
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            # WAL can fail on some unusual filesystems; continue anyway.
            pass
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")

        while True:
            task = self._task_q.get()
            if task is None:
                break

            try:
                result = task.fn(conn)
                task.reply_q.put((True, result))
            except Exception as e:
                task.reply_q.put((False, e))

        try:
            conn.close()
        except Exception:
            pass

    def _submit(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        if self._closed:
            raise RuntimeError("Earth2Database is closed")

        reply_q: "queue.Queue[Tuple[bool, Any]]" = queue.Queue(maxsize=1)
        self._task_q.put(_DBTask(fn=fn, reply_q=reply_q))

        ok, payload = reply_q.get()
        if ok:
            return payload
        raise payload

    # ------------------------------------------------------------------------
    # Schema / helpers
    # ------------------------------------------------------------------------
    def _create_tables(self, conn: sqlite3.Connection):
                """Create database tables if they don't exist"""
        
                # Candidates table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS candidates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp_utc TEXT,
                        event TEXT,
                        event_id TEXT,
                        system_address INTEGER,
                        star_system TEXT,
                        body_name TEXT,
                        body_id INTEGER,
                        distance_from_arrival_ls REAL,
                        candidate_type TEXT,
                        terraform_state TEXT,
                        planet_class TEXT,
                        atmosphere TEXT,
                        volcanism TEXT,
                        mass_em REAL,
                        radius_km REAL,
                        surface_gravity_g REAL,
                        surface_temp_k REAL,
                        surface_pressure_atm REAL,
                        landable TEXT,
                        tidal_lock TEXT,
                        rotation_period_days REAL,
                        orbital_period_days REAL,
                        semi_major_axis_au REAL,
                        orbital_eccentricity REAL,
                        orbital_inclination_deg REAL,
                        arg_of_periapsis_deg REAL,
                        ascending_node_deg REAL,
                        mean_anomaly_deg REAL,
                        axial_tilt_deg REAL,
                        was_discovered TEXT,
                        was_mapped TEXT,
                        earth2_rating TEXT,
                        similarity_score REAL,
                        goldilocks_score INTEGER,
                        goldilocks_category TEXT,
                        worth_landing TEXT,
                        worth_reason TEXT,
                        distance_from_sol_ly REAL,
                        star_pos_x REAL,
                        star_pos_y REAL,
                        star_pos_z REAL,
                        cmdr_name TEXT,
                        session_id TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(star_system, body_name, cmdr_name)
                    )
                """)
        
                # Add similarity_score column if it doesn't exist (for existing databases)
                try:
                    conn.execute("ALTER TABLE candidates ADD COLUMN similarity_score REAL")
                    conn.commit()
                except:
                    pass  # Column already exists

                # Add goldilocks columns if they don't exist
                try:
                    conn.execute("ALTER TABLE candidates ADD COLUMN goldilocks_score INTEGER")
                    conn.commit()
                except:
                    pass

                try:
                    conn.execute("ALTER TABLE candidates ADD COLUMN goldilocks_category TEXT")
                    conn.commit()
                except:
                    pass

                # Add event_id column for linking to observer_notes
                try:
                    conn.execute("ALTER TABLE candidates ADD COLUMN event_id TEXT")
                    conn.commit()
                except:
                    pass

                # Add system_address column (game's unique system ID)
                try:
                    conn.execute("ALTER TABLE candidates ADD COLUMN system_address INTEGER")
                    conn.commit()
                except:
                    pass

                # Create index on event_id for fast joins with observer_notes
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_event_id ON candidates(event_id)")
                    conn.commit()
                except:
                    pass

                # Create index on system_address
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_system_address ON candidates(system_address)")
                    conn.commit()
                except:
                    pass
        
                # Sessions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        cmdr_name TEXT,
                        journal_file TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        
                # Commander stats table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS commander_stats (
                        cmdr_name TEXT PRIMARY KEY,
                        total_all INTEGER DEFAULT 0,
                        total_elw INTEGER DEFAULT 0,
                        total_terraformable INTEGER DEFAULT 0,
                        total_earth_twin INTEGER DEFAULT 0,
                        total_excellent INTEGER DEFAULT 0,
                        total_very_good INTEGER DEFAULT 0,
                        total_good INTEGER DEFAULT 0,
                        total_fair INTEGER DEFAULT 0,
                        total_marginal INTEGER DEFAULT 0,
                        total_poor INTEGER DEFAULT 0,
                        total_unknown INTEGER DEFAULT 0,
                        last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        
                conn.commit()
    
            # ========================================================================
            # CANDIDATE OPERATIONS
            # ========================================================================

    def _generate_event_id(self, candidate_data: Dict[str, Any]) -> str:
                """
                Generate deterministic event ID from candidate data.

                Uses the same algorithm as observer_models.generate_event_id()
                to ensure consistent linking.

                Args:
                    candidate_data: Candidate information dictionary

                Returns:
                    16-character hex string
                """
                components = [
                    candidate_data.get('timestamp_utc', ''),
                    candidate_data.get('event', ''),
                    str(candidate_data.get('system_address', '')),
                    str(candidate_data.get('body_id', '')),
                ]
                return hashlib.sha256('|'.join(components).encode()).hexdigest()[:16]

            # ========================================================================
            # OBSERVER NOTE INTEGRATION
            # ========================================================================



    def _update_commander_stats(self, conn: sqlite3.Connection, candidate_data: Dict[str, Any]):
                """Update commander statistics"""
                cmdr_name = candidate_data.get("cmdr_name", "")
                if not cmdr_name:
                    return
        
                # Ensure commander exists
                conn.execute("""
                    INSERT OR IGNORE INTO commander_stats (cmdr_name, total_all)
                    VALUES (?, 0)
                """, (cmdr_name,))
        
                # Update counts
                conn.execute("""
                    UPDATE commander_stats
                    SET total_all = total_all + 1,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE cmdr_name = ?
                """, (cmdr_name,))
        
                # Update type-specific counts
                candidate_type = candidate_data.get("candidate_type", "")
                if "ELW" in candidate_type:
                    conn.execute("""
                        UPDATE commander_stats
                        SET total_elw = total_elw + 1
                        WHERE cmdr_name = ?
                    """, (cmdr_name,))
                elif "Terraformable" in candidate_type:
                    conn.execute("""
                        UPDATE commander_stats
                        SET total_terraformable = total_terraformable + 1
                        WHERE cmdr_name = ?
                    """, (cmdr_name,))
        
                # Update rating counts (using new category system)
                rating = candidate_data.get("earth2_rating", "Unknown")
        
                # Map category to database column
                rating_columns = {
                    "Earth Twin": "total_earth_twin",
                    "Excellent": "total_excellent",
                    "Very Good": "total_very_good",
                    "Good": "total_good",
                    "Fair": "total_fair",
                    "Marginal": "total_marginal",
                    "Poor": "total_poor",
                    "Unknown": "total_unknown"
                }
        
                column_name = rating_columns.get(rating, "total_unknown")
        
                conn.execute(f"""
                    UPDATE commander_stats
                    SET {column_name} = {column_name} + 1
                    WHERE cmdr_name = ?
                """, (cmdr_name,))
        
                conn.commit()



    # ------------------------------------------------------------------------
    # Public API (same as before)
    # ------------------------------------------------------------------------
    def log_candidate(self, candidate_data: Dict[str, Any]) -> bool:
        """Log a candidate to database. Returns True if new candidate, False if duplicate."""
        # Compute deterministic event_id outside worker (pure function)
        event_id = candidate_data.get("event_id")
        if not event_id:
            event_id = self._generate_event_id(candidate_data)
        candidate_data = dict(candidate_data)
        candidate_data["event_id"] = event_id

        # Defensive defaults for named SQL bindings.
        # If a key used in the INSERT is missing, sqlite3 raises:
        #   "You did not supply a value for binding parameter :<name>"
        # Import paths (e.g. import_journals.py) may omit newer fields.
        for key in CANDIDATE_INSERT_KEYS:
            candidate_data.setdefault(key, None)

        def _task(conn: sqlite3.Connection):
            try:
                cursor = conn.execute("""
                    INSERT INTO candidates (
                        timestamp_utc, event, event_id, system_address,
                        star_system, body_name, body_id,
                        distance_from_arrival_ls, candidate_type, terraform_state,
                        planet_class, atmosphere, volcanism, mass_em, radius_km,
                        surface_gravity_g, surface_temp_k, surface_pressure_atm,
                        landable, tidal_lock, rotation_period_days, orbital_period_days,
                        semi_major_axis_au, orbital_eccentricity, orbital_inclination_deg,
                        arg_of_periapsis_deg, ascending_node_deg, mean_anomaly_deg,
                        axial_tilt_deg, was_discovered, was_mapped,
                        earth2_rating, similarity_score, goldilocks_score,
                        goldilocks_category, worth_landing, worth_reason,
                        distance_from_sol_ly, star_pos_x, star_pos_y, star_pos_z,
                        cmdr_name, session_id
                    ) VALUES (
                        :timestamp_utc, :event, :event_id, :system_address,
                        :star_system, :body_name, :body_id,
                        :distance_from_arrival_ls, :candidate_type, :terraform_state,
                        :planet_class, :atmosphere, :volcanism, :mass_em, :radius_km,
                        :surface_gravity_g, :surface_temp_k, :surface_pressure_atm,
                        :landable, :tidal_lock, :rotation_period_days, :orbital_period_days,
                        :semi_major_axis_au, :orbital_eccentricity, :orbital_inclination_deg,
                        :arg_of_periapsis_deg, :ascending_node_deg, :mean_anomaly_deg,
                        :axial_tilt_deg, :was_discovered, :was_mapped,
                        :earth2_rating, :similarity_score, :goldilocks_score,
                        :goldilocks_category, :worth_landing, :worth_reason,
                        :distance_from_sol_ly, :star_pos_x, :star_pos_y, :star_pos_z,
                        :cmdr_name, :session_id
                    )
                """, candidate_data)
                conn.commit()

                # Update stats in same transaction window
                self._update_commander_stats(conn, candidate_data)
                conn.commit()

                return True
            except sqlite3.IntegrityError:
                # Duplicate due to UNIQUE constraint
                return False

        return bool(self._submit(_task))

    def get_candidates_with_observations(
        self,
        observer_db_path: Optional[Path] = None,
        z_bin: Optional[int] = None,
        session_id: Optional[str] = None,
        cmdr_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get candidates merged with their observer notes (if available)."""

        def _task(conn: sqlite3.Connection):
            # Build WHERE clause
            where_clauses = []
            params: List[Any] = []

            if z_bin is not None:
                where_clauses.append("c.star_pos_z BETWEEN ? AND ?")
                params.extend([z_bin - 25, z_bin + 25])

            if session_id:
                where_clauses.append("c.session_id = ?")
                params.append(session_id)

            if cmdr_name:
                where_clauses.append("c.cmdr_name = ?")
                params.append(cmdr_name)

            where = " AND ".join(where_clauses) if where_clauses else "1=1"

            def _candidates_only():
                cursor = conn.execute(f"""
                    SELECT c.*, NULL AS obs_slice_status, NULL AS obs_confidence,
                           NULL AS obs_system_count, NULL AS obs_corrected_n,
                           NULL AS obs_max_distance, NULL AS obs_payload_json
                    FROM candidates c
                    WHERE {where}
                    ORDER BY c.timestamp_utc DESC
                """, params)
                return [dict(row) for row in cursor.fetchall()]

            # Same DB: try join only if table exists
            if observer_db_path is None or Path(observer_db_path) == self.db_path:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='observer_notes'
                """)
                if not cursor.fetchone():
                    return _candidates_only()

                cursor = conn.execute(f"""
                    SELECT
                        c.*,
                        o.slice_status AS obs_slice_status,
                        o.completeness_confidence AS obs_confidence,
                        o.system_count AS obs_system_count,
                        o.corrected_n AS obs_corrected_n,
                        o.max_distance AS obs_max_distance,
                        o.payload_json AS obs_payload_json
                    FROM candidates c
                    LEFT JOIN observer_notes o
                        ON c.event_id = o.event_id
                        AND o.record_status = 'active'
                    WHERE {where}
                    ORDER BY c.timestamp_utc DESC
                """, params)
                return [dict(row) for row in cursor.fetchall()]

            # External observer DB
            conn.execute("ATTACH DATABASE ? AS obs_db", (str(observer_db_path),))
            try:
                cursor = conn.execute(f"""
                    SELECT
                        c.*,
                        o.slice_status AS obs_slice_status,
                        o.completeness_confidence AS obs_confidence,
                        o.system_count AS obs_system_count,
                        o.corrected_n AS obs_corrected_n,
                        o.max_distance AS obs_max_distance,
                        o.payload_json AS obs_payload_json
                    FROM candidates c
                    LEFT JOIN obs_db.observer_notes o
                        ON c.event_id = o.event_id
                        AND o.record_status = 'active'
                    WHERE {where}
                    ORDER BY c.timestamp_utc DESC
                """, params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.execute("DETACH DATABASE obs_db")

        return self._submit(_task)

    def get_candidates_by_event_ids(self, event_ids: List[str]) -> List[Dict[str, Any]]:
        """Get candidates by their event_ids."""
        if not event_ids:
            return []

        def _task(conn: sqlite3.Connection):
            placeholders = ",".join(["?"] * len(event_ids))
            cursor = conn.execute(f"""
                SELECT * FROM candidates
                WHERE event_id IN ({placeholders})
                ORDER BY timestamp_utc DESC
            """, event_ids)
            return [dict(row) for row in cursor.fetchall()]

        return self._submit(_task)

    def backfill_event_ids(self) -> int:
        def _task(conn: sqlite3.Connection):
                    """
                    Backfill event_id for existing candidates that don't have one.

                    Call this once after upgrading to add event_id support.

                    Returns:
                        Number of candidates updated
                    """
                    cursor = conn.execute("""
                        SELECT id, timestamp_utc, event, system_address, body_id
                        FROM candidates
                        WHERE event_id IS NULL OR event_id = ''
                    """)

                    count = 0
                    for row in cursor.fetchall():
                        event_id = self._generate_event_id({
                            'timestamp_utc': row['timestamp_utc'],
                            'event': row['event'],
                            'system_address': row['system_address'],
                            'body_id': row['body_id'],
                        })

                        conn.execute(
                            "UPDATE candidates SET event_id = ? WHERE id = ?",
                            (event_id, row['id'])
                        )
                        count += 1

                    conn.commit()
                    return count

                # ========================================================================
                # SESSION OPERATIONS
                # ========================================================================


        return int(self._submit(_task))

    def start_session(self, cmdr_name: str, journal_file: str) -> str:
        def _task(conn: sqlite3.Connection):
                    """
                    Start a new exploration session
        
                    Args:
                        cmdr_name: Commander name
                        journal_file: Journal file name
            
                    Returns:
                        Session ID
                    """
                    session_id = f"{cmdr_name}_{int(time.time())}"
        
                    conn.execute("""
                        INSERT INTO sessions (session_id, cmdr_name, journal_file, start_time)
                        VALUES (?, ?, ?, ?)
                    """, (session_id, cmdr_name, journal_file, datetime.utcnow().isoformat()))
        
                    conn.commit()
        
                    return session_id
    

        return str(self._submit(_task))

    def end_session(self, session_id: str):
        def _task(conn: sqlite3.Connection):
                    """
                    End an exploration session
        
                    Args:
                        session_id: Session ID
                    """
                    conn.execute("""
                        UPDATE sessions
                        SET end_time = ?
                        WHERE session_id = ?
                    """, (datetime.utcnow().isoformat(), session_id))
        
                    conn.commit()
    
                # ========================================================================
                # STATISTICS
                # ========================================================================
    

        self._submit(_task)

    def get_cmdr_stats(self, cmdr_name: str) -> Optional[Dict[str, Any]]:
        def _task(conn: sqlite3.Connection):
                    """
                    Get statistics for a commander
        
                    Args:
                        cmdr_name: Commander name
            
                    Returns:
                        Statistics dictionary or None
                    """
                    cursor = conn.execute("""
                        SELECT * FROM commander_stats
                        WHERE cmdr_name = ?
                    """, (cmdr_name,))
        
                    row = cursor.fetchone()
                    if row:
                        return dict(row)
        
                    return None
    

        return self._submit(_task)

    def get_all_cmdr_stats(self) -> List[Dict[str, Any]]:
        def _task(conn: sqlite3.Connection):
                    """
                    Get statistics for all commanders
        
                    Returns:
                        List of statistics dictionaries
                    """
                    cursor = conn.execute("""
                        SELECT * FROM commander_stats
                        ORDER BY total_all DESC
                    """)
        
                    return [dict(row) for row in cursor.fetchall()]
    
                # ========================================================================
                # EXPORT
                # ========================================================================
    

        return self._submit(_task)

    def export_to_csv(self, csv_path: Path, cmdr_name: Optional[str] = None):
        """Export candidates to CSV. Query happens in worker, file write happens in caller thread."""
        import csv

        def _fetch(conn: sqlite3.Connection):
            if cmdr_name:
                cursor = conn.execute("""
                    SELECT * FROM candidates
                    WHERE cmdr_name = ?
                    ORDER BY timestamp_utc
                """, (cmdr_name,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM candidates
                    ORDER BY timestamp_utc
                """)
            columns = [description[0] for description in cursor.description]
            rows = [dict(row) for row in cursor.fetchall()]
            return columns, rows

        columns, rows = self._submit(_fetch)

        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def close(self):
        """Stop the DB worker thread and close down safely.

        Bulletproof shutdown goals:
          - Always send a stop signal
          - Join the worker thread (best-effort, without hanging forever)
        """
        if self._closed:
            return
        self._closed = True

        # Stop worker
        try:
            self._task_q.put(None)
        except Exception:
            pass

        # Join worker (best effort)
        try:
            self._worker.join(timeout=10.0)
        except Exception:
            pass


    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
