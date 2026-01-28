"""
Observer Storage - Database operations for ObserverNote
========================================================

Handles storage and retrieval of CMDR observation notes with:
- Hybrid columns: Indexed fields for queries + JSON payload for flexibility
- Amendment tracking: Append-only with supersedes_id for corrections
- Hash chain: Tamper-evident logging with payload_hash and prev_hash
- WAL mode: Crash-safe writes

Design principles:
- Append-only: Never modify existing records, only add new ones
- Amendments: Corrections create new records that supersede old ones
- Hash chain: Each record links to previous via hash for integrity
- Schema versioning: payload includes schema_version for migrations
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   observer_storage.py
#
# Connected modules (direct imports):
#   observer_models
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import sqlite3
import json
from pathlib import Path
from threading import Lock
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from observer_models import (
    ObserverNote,
    SliceStatus,
    SamplingMethod,
    RecordStatus,
    ObservationFlags,
)


# ============================================================================
# CLASSES
# ============================================================================

class ObserverStorage:
    """
    Storage layer for ObserverNote objects.

    Can share a database with Earth2Database or use a separate file.
    Uses WAL mode for crash safety and supports concurrent reads.

    Usage:
        storage = ObserverStorage(db_path)

        # Save new observation
        note_id = storage.save(note)

        # Amend existing observation
        new_id = storage.amend(original_id, updated_note)

        # Query active observations
        notes = storage.get_by_z_bin(350)

        # Verify integrity
        is_valid, last_good = storage.verify_integrity()
    """

    TABLE_NAME = "observer_notes"

    def __init__(self, db_path: Path, enable_wal: bool = True):
        """
        Initialize observer storage.

        Args:
            db_path: Path to SQLite database file
            enable_wal: Enable WAL mode for crash safety (recommended)
        """
        self.db_path = Path(db_path)
        self._lock = Lock()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None  # Autocommit for WAL
        )
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode for crash safety
        if enable_wal:
            self.conn.execute("PRAGMA journal_mode=WAL")

        # Create tables and indexes
        self._create_tables()
        
        print("[OBSERVER STORAGE] loaded from:", __file__)
        print("[OBSERVER STORAGE] db_path:", self.db_path)


    def _create_tables(self):
        """Create observer_notes table with hybrid columns"""
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                -- Primary key
                id TEXT PRIMARY KEY,
                created_at_utc TEXT NOT NULL,

                -- Indexed columns for fast queries
                event_id TEXT NOT NULL,
                system_address INTEGER,
                system_name TEXT NOT NULL,
                z_bin INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                slice_status TEXT NOT NULL,
                completeness_confidence INTEGER,

                -- Density sampling data
                system_count INTEGER,
                corrected_n INTEGER,
                max_distance REAL,

                -- Stable per-slice ordinal (assigned on first save)
                sample_index INTEGER,

                -- Amendment tracking
                supersedes_id TEXT,
                record_status TEXT DEFAULT 'active',

                -- Full payload for flexibility and hash verification
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                prev_hash TEXT,

                schema_version INTEGER DEFAULT 1,

                FOREIGN KEY (supersedes_id) REFERENCES {self.TABLE_NAME}(id)
            )
        """)

        # Create indexes for common queries
        indexes = [
            ("idx_obs_record_status", "record_status"),
            ("idx_obs_system_address", "system_address"),
            ("idx_obs_system_name", "system_name"),
            ("idx_obs_z_bin", "z_bin"),
            ("idx_obs_session_id", "session_id"),
            ("idx_obs_event_id", "event_id"),
            ("idx_obs_slice_status", "slice_status"),
            ("idx_obs_created_at", "created_at_utc"),
        ]

        for idx_name, column in indexes:
            try:
                self.conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {self.TABLE_NAME}({column})"
                )
            except sqlite3.OperationalError:
                pass  # Index might already exist

        # Add sample_index column for existing databases (best effort)
        try:
            self.conn.execute(f"ALTER TABLE {self.TABLE_NAME} ADD COLUMN sample_index INTEGER")
        except sqlite3.OperationalError:
            pass

        # Index for sample_index (useful for ordering)
        try:
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_obs_sample_index ON {self.TABLE_NAME}(sample_index)"
            )
        except sqlite3.OperationalError:
            pass


    # =========================================================================
    # SAVE OPERATIONS
    # =========================================================================

    def save(self, note: ObserverNote) -> str:
        """
        Save a new observation note.

        Args:
            note: ObserverNote to save

        Returns:
            The note's ID

        Raises:
            ValueError: If validation fails
        """
        # Validate
        is_valid, errors = note.validate()
        if not is_valid:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        with self._lock:
            # Assign stable per-slice ordinal on first save
            if note.sample_index is None:
                note.sample_index = self._get_next_sample_index(note)

            # Get previous hash for chain
            prev_hash = self._get_latest_hash()

            # Set hash chain values
            note.prev_hash = prev_hash
            note.payload_hash = note.compute_hash()

            # Insert
            self._insert_note(note)

            return note.id

    def _get_next_sample_index(self, note: ObserverNote) -> int:
        """Compute next sample_index for (session_id, system, z_bin)."""
        # Prefer system_address when available (stable game ID)
        if note.system_address is not None:
            where = "session_id = ? AND system_address = ? AND z_bin = ?"
            params = (note.session_id, note.system_address, note.z_bin)
        else:
            where = "session_id = ? AND system_name = ? AND z_bin = ?"
            params = (note.session_id, note.system_name, note.z_bin)

        cursor = self.conn.execute(
            f"""
            SELECT COALESCE(MAX(sample_index), 0) + 1 AS next_idx
            FROM {self.TABLE_NAME}
            WHERE {where}
            """,
            params,
        )
        row = cursor.fetchone()
        return int(row["next_idx"]) if row and row["next_idx"] is not None else 1

    def amend(self, original_id: str, updated_note: ObserverNote) -> str:
        """
        Amend an existing observation (append-only correction).

        Creates a new record that supersedes the original.
        Original is marked as 'amended'.

        Args:
            original_id: ID of the note to amend
            updated_note: New note with updated values

        Returns:
            ID of the new (amended) note

        Raises:
            ValueError: If original not found or validation fails
        """
        # Validate new note
        is_valid, errors = updated_note.validate()
        if not is_valid:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        with self._lock:
            # Verify original exists and is active
            original = self._get_note_by_id(original_id)
            if not original:
                raise ValueError(f"Original note not found: {original_id}")

            if original.record_status != RecordStatus.ACTIVE:
                raise ValueError(f"Cannot amend non-active record: {original_id}")

            # Preserve stable ordinal
            updated_note.sample_index = original.sample_index

            # Mark original as amended
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET record_status = ? WHERE id = ?",
                (RecordStatus.AMENDED.value, original_id)
            )

            # Set up new note
            updated_note.supersedes_id = original_id
            updated_note.record_status = RecordStatus.ACTIVE

            # Get previous hash for chain
            prev_hash = self._get_latest_hash()
            updated_note.prev_hash = prev_hash
            updated_note.payload_hash = updated_note.compute_hash()

            # Insert new note
            self._insert_note(updated_note)

            return updated_note.id

    def delete(self, original_id: str, reason: str) -> str:
        """
        Soft-delete an observation (append-only).

        Creates a deletion record for audit trail.
        Original is marked as 'deleted'.

        Args:
            original_id: ID of the note to delete
            reason: Reason for deletion (required)

        Returns:
            ID of the deletion record

        Raises:
            ValueError: If original not found or reason empty
        """
        if not reason.strip():
            raise ValueError("Deletion reason is required")

        with self._lock:
            # Get original
            original = self._get_note_by_id(original_id)
            if not original:
                raise ValueError(f"Original note not found: {original_id}")

            if original.record_status != RecordStatus.ACTIVE:
                raise ValueError(f"Cannot delete non-active record: {original_id}")

            # Mark original as deleted
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET record_status = ? WHERE id = ?",
                (RecordStatus.DELETED.value, original_id)
            )

            # Create deletion record
            import uuid
            deletion_note = ObserverNote(
                id=str(uuid.uuid4()),
                event_id=original.event_id,
                timestamp_utc=original.timestamp_utc,
                system_address=original.system_address,
                system_name=original.system_name,
                star_pos=original.star_pos,
                z_bin=original.z_bin,
                session_id=original.session_id,
                sample_index=original.sample_index,
                slice_status=SliceStatus.DISCARD,
                notes=f"DELETED: {reason}",
                supersedes_id=original_id,
                record_status=RecordStatus.DELETED,
                schema_version=original.schema_version,
                app_version=original.app_version,
            )

            # Hash chain
            prev_hash = self._get_latest_hash()
            deletion_note.prev_hash = prev_hash
            deletion_note.payload_hash = deletion_note.compute_hash()

            # Insert deletion record
            self._insert_note(deletion_note)

            return deletion_note.id

    def _insert_note(self, note: ObserverNote):
        """Insert a note into the database"""
        self.conn.execute(f"""
            INSERT INTO {self.TABLE_NAME} (
                id, created_at_utc, event_id, system_address, system_name,
                z_bin, session_id, slice_status, completeness_confidence,
                system_count, corrected_n, max_distance,
                sample_index,
                supersedes_id, record_status,
                payload_json, payload_hash, prev_hash, schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note.id,
            note.created_at_utc,
            note.event_id,
            note.system_address,
            note.system_name,
            note.z_bin,
            note.session_id,
            note.slice_status.value,
            note.completeness_confidence,
            note.system_count,
            note.corrected_n,
            note.max_distance,
            note.sample_index,
            note.supersedes_id,
            note.record_status.value,
            note.to_json(),
            note.payload_hash,
            note.prev_hash,
            note.schema_version,
        ))

    def _get_latest_hash(self) -> Optional[str]:
        """Get hash of the most recent record for chain linking"""
        cursor = self.conn.execute(f"""
            SELECT payload_hash FROM {self.TABLE_NAME}
            ORDER BY created_at_utc DESC, id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return row['payload_hash'] if row else None

    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================

    def get_by_id(self, note_id: str) -> Optional[ObserverNote]:
        """Get a note by ID"""
        with self._lock:
            return self._get_note_by_id(note_id)

    def _get_note_by_id(self, note_id: str) -> Optional[ObserverNote]:
        """Internal: Get note by ID (no lock)"""
        cursor = self.conn.execute(
            f"SELECT payload_json FROM {self.TABLE_NAME} WHERE id = ?",
            (note_id,)
        )
        row = cursor.fetchone()
        if row:
            return ObserverNote.from_dict(json.loads(row['payload_json']))
        return None

    def get_active(self, limit: int = 100, offset: int = 0) -> List[ObserverNote]:
        """Get all active observations"""
        with self._lock:
            cursor = self.conn.execute(f"""
                SELECT payload_json FROM {self.TABLE_NAME}
                WHERE record_status = ?
                ORDER BY created_at_utc DESC
                LIMIT ? OFFSET ?
            """, (RecordStatus.ACTIVE.value, limit, offset))

            return [
                ObserverNote.from_dict(json.loads(row['payload_json']))
                for row in cursor.fetchall()
            ]

    def get_by_z_bin(
        self,
        z_bin: int,
        active_only: bool = True
    ) -> List[ObserverNote]:
        """Get observations for a specific Z-bin"""
        with self._lock:
            if active_only:
                cursor = self.conn.execute(f"""
                    SELECT payload_json FROM {self.TABLE_NAME}
                    WHERE z_bin = ? AND record_status = ?
                    ORDER BY created_at_utc DESC
                """, (z_bin, RecordStatus.ACTIVE.value))
            else:
                cursor = self.conn.execute(f"""
                    SELECT payload_json FROM {self.TABLE_NAME}
                    WHERE z_bin = ?
                    ORDER BY created_at_utc DESC
                """, (z_bin,))

            return [
                ObserverNote.from_dict(json.loads(row['payload_json']))
                for row in cursor.fetchall()
            ]

    def get_by_session(
        self,
        session_id: str,
        active_only: bool = True
    ) -> List[ObserverNote]:
        """Get observations for a session"""
        with self._lock:
            if active_only:
                cursor = self.conn.execute(f"""
                    SELECT payload_json FROM {self.TABLE_NAME}
                    WHERE session_id = ? AND record_status = ?
                    ORDER BY created_at_utc
                """, (session_id, RecordStatus.ACTIVE.value))
            else:
                cursor = self.conn.execute(f"""
                    SELECT payload_json FROM {self.TABLE_NAME}
                    WHERE session_id = ?
                    ORDER BY created_at_utc
                """, (session_id,))

            return [
                ObserverNote.from_dict(json.loads(row['payload_json']))
                for row in cursor.fetchall()
            ]

    def get_by_system(
        self,
        system_name: str = None,
        system_address: int = None,
        active_only: bool = True
    ) -> List[ObserverNote]:
        """Get observations for a system (by name or address)"""
        with self._lock:
            if system_address:
                where = "system_address = ?"
                params = [system_address]
            elif system_name:
                where = "system_name = ?"
                params = [system_name]
            else:
                return []

            if active_only:
                where += " AND record_status = ?"
                params.append(RecordStatus.ACTIVE.value)

            cursor = self.conn.execute(f"""
                SELECT payload_json FROM {self.TABLE_NAME}
                WHERE {where}
                ORDER BY created_at_utc DESC
            """, params)

            return [
                ObserverNote.from_dict(json.loads(row['payload_json']))
                for row in cursor.fetchall()
            ]

    def get_amendment_history(self, note_id: str) -> List[ObserverNote]:
        """Get full amendment history for a note"""
        with self._lock:
            # Find the root note (walk up supersedes chain)
            root_id = note_id
            while True:
                cursor = self.conn.execute(f"""
                    SELECT supersedes_id FROM {self.TABLE_NAME}
                    WHERE id = ?
                """, (root_id,))
                row = cursor.fetchone()
                if not row or not row['supersedes_id']:
                    break
                root_id = row['supersedes_id']

            # Now get all notes in the chain
            history = []
            current_id = root_id

            while current_id:
                note = self._get_note_by_id(current_id)
                if note:
                    history.append(note)

                # Find what supersedes this note
                cursor = self.conn.execute(f"""
                    SELECT id FROM {self.TABLE_NAME}
                    WHERE supersedes_id = ?
                """, (current_id,))
                row = cursor.fetchone()
                current_id = row['id'] if row else None

            return history

    def count_by_status(self) -> Dict[str, int]:
        """Get count of notes by status"""
        with self._lock:
            cursor = self.conn.execute(f"""
                SELECT record_status, COUNT(*) as count
                FROM {self.TABLE_NAME}
                GROUP BY record_status
            """)

            return {row['record_status']: row['count'] for row in cursor.fetchall()}

    def count_by_slice_status(self, active_only: bool = True) -> Dict[str, int]:
        """Get count of notes by slice status"""
        with self._lock:
            if active_only:
                cursor = self.conn.execute(f"""
                    SELECT slice_status, COUNT(*) as count
                    FROM {self.TABLE_NAME}
                    WHERE record_status = ?
                    GROUP BY slice_status
                """, (RecordStatus.ACTIVE.value,))
            else:
                cursor = self.conn.execute(f"""
                    SELECT slice_status, COUNT(*) as count
                    FROM {self.TABLE_NAME}
                    GROUP BY slice_status
                """)

            return {row['slice_status']: row['count'] for row in cursor.fetchall()}

    # =========================================================================
    # INTEGRITY VERIFICATION
    # =========================================================================

    def verify_integrity(self) -> Tuple[bool, Optional[str], List[str]]:
        """
        Verify hash chain integrity.

        Returns:
            Tuple of (is_valid, last_good_id, list of error messages)
        """
        with self._lock:
            cursor = self.conn.execute(f"""
                SELECT id, payload_json, payload_hash, prev_hash
                FROM {self.TABLE_NAME}
                ORDER BY created_at_utc, id
            """)

            expected_prev = None
            last_good_id = None
            errors = []

            for row in cursor.fetchall():
                note_id = row['id']
                stored_hash = row['payload_hash']
                stored_prev = row['prev_hash']

                # Verify prev_hash chain
                if stored_prev != expected_prev:
                    errors.append(
                        f"Hash chain break at {note_id}: "
                        f"expected prev={expected_prev}, got {stored_prev}"
                    )
                    # Don't continue checking after first break
                    return (False, last_good_id, errors)

                # Verify payload hash
                try:
                    payload = json.loads(row['payload_json'])
                    note = ObserverNote.from_dict(payload)
                    computed_hash = note.compute_hash()

                    if computed_hash != stored_hash:
                        errors.append(
                            f"Payload hash mismatch at {note_id}: "
                            f"stored={stored_hash}, computed={computed_hash}"
                        )
                        return (False, last_good_id, errors)
                except Exception as e:
                    errors.append(f"Failed to verify {note_id}: {e}")
                    return (False, last_good_id, errors)

                # This record is good
                expected_prev = stored_hash
                last_good_id = note_id

            return (True, last_good_id, [])

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_to_csv(
        self,
        csv_path: Path,
        active_only: bool = True,
        session_id: str = None
    ):
        """
        Export observations to CSV.

        Args:
            csv_path: Output path
            active_only: Only export active records
            session_id: Filter by session (None = all)
        """
        import csv

        with self._lock:
            # Build query
            where_clauses = []
            params = []

            if active_only:
                where_clauses.append("record_status = ?")
                params.append(RecordStatus.ACTIVE.value)

            if session_id:
                where_clauses.append("session_id = ?")
                params.append(session_id)

            where = " AND ".join(where_clauses) if where_clauses else "1=1"

            cursor = self.conn.execute(f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE {where}
                ORDER BY created_at_utc
            """, params)

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Write CSV
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open('w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(cursor.fetchall())

    def export_for_spreadsheet(
        self,
        csv_path: Path,
        session_id: str = None
    ):
        """
        Export in format matching the Stellar Density Scan Worksheet.

        Columns: System, Z Sample, System Count, Corrected n, Max Distance,
                 X, Y, Z, Slice Status, Confidence, Notes

        Args:
            csv_path: Output path
            session_id: Filter by session (None = all)
        """
        import csv

        with self._lock:
            where = "record_status = ?"
            params = [RecordStatus.ACTIVE.value]

            if session_id:
                where += " AND session_id = ?"
                params.append(session_id)

            cursor = self.conn.execute(f"""
                SELECT payload_json FROM {self.TABLE_NAME}
                WHERE {where}
                ORDER BY z_bin, created_at_utc
            """, params)

            # Write CSV with spreadsheet-compatible columns
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open('w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'System', 'Z Sample', 'System Count', 'Corrected n',
                    'Max Distance', 'X', 'Y', 'Z',
                    'Slice Status', 'Confidence', 'Method', 'Notes'
                ])

                for row in cursor.fetchall():
                    note = ObserverNote.from_dict(json.loads(row['payload_json']))
                    writer.writerow([
                        note.system_name,
                        note.z_bin,
                        note.system_count or '',
                        note.corrected_n or '',
                        note.max_distance or '',
                        note.star_pos[0],
                        note.star_pos[1],
                        note.star_pos[2],
                        note.slice_status.value,
                        note.completeness_confidence,
                        note.sampling_method.value,
                        note.notes,
                    ])

    # =========================================================================
    # CLEANUP
    # =========================================================================

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Ensure connection is closed"""
        self.close()
