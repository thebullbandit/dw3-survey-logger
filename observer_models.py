"""
Observer Models - Data structures for CMDR observation notes
============================================================

These models capture human-input data that supplements journal-derived data.
Used for stellar density sampling where CMDRs record:
- Slice completion status
- System counts and corrections
- Sampling methodology
- Quality flags and notes

Design principles:
- Journal data is source of truth for position/system/time
- Observer data is add-on annotation, never overwrites journal
- Append-only storage with amendment tracking
- Schema versioning for future compatibility
"""

# ============================================================================
# IMPORTS
# ============================================================================

import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any
import json


# =============================================================================
# ENUMS
# =============================================================================

class SliceStatus(Enum):
    """Status of a Z-slice observation"""
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    PARTIAL = "partial"
    DISCARD = "discard"


class SamplingMethod(Enum):
    """How the CMDR sampled the slice"""
    RANDOM = "random"
    GRID = "grid"
    ROUTE_FOLLOW = "route_follow"
    TARGETED = "targeted"
    OTHER = "other"


class RecordStatus(Enum):
    """Amendment tracking status"""
    ACTIVE = "active"
    AMENDED = "amended"
    DELETED = "deleted"


# =============================================================================
# FLAG DATACLASS
# =============================================================================

@dataclass
class ObservationFlags:
    """Quality and status flags for an observation"""
    bias_risk: bool = False          # Route bias suspected
    low_coverage: bool = False       # Incomplete coverage of slice
    anomaly_suspected: bool = False  # Unusual data pattern
    interrupted: bool = False        # AFK, crash, or other interruption
    repeat_needed: bool = False      # Slice should be re-sampled

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, bool]) -> 'ObservationFlags':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def any_set(self) -> bool:
        """Check if any flag is set"""
        return any([
            self.bias_risk,
            self.low_coverage,
            self.anomaly_suspected,
            self.interrupted,
            self.repeat_needed
        ])


# =============================================================================
# MAIN OBSERVER NOTE MODEL
# =============================================================================

@dataclass
class ObserverNote:
    """
    CMDR observation note for a stellar density sample.

    This captures human-input data that supplements journal-derived data.
    Each note is associated with a specific Z-slice sample.

    Auto-filled fields (from journal/system):
        - event_id, timestamp_utc, system_address, system_name
        - star_pos, z_bin, session_id, body_name

    CMDR-input fields:
        - slice_status, completeness_confidence, sampling_method
        - system_count, corrected_n, max_distance
        - flags, notes
    """

    # === Primary key ===
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # === Auto-filled from journal context ===
    event_id: str = ""                              # Deterministic hash linking to journal event
    timestamp_utc: str = ""                         # ISO format timestamp
    system_address: Optional[int] = None            # Game's unique system ID
    system_name: str = ""                           # Star system name
    star_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # X, Y, Z coordinates
    z_bin: int = 0                                  # Z-slice bin (e.g., round(z/50)*50)
    session_id: str = ""                            # Logger session ID
    body_name: Optional[str] = None                 # Body name if relevant

    # === Derived / storage metadata ===
    # Stable per (session_id, system, z_bin): the Nth sample taken in this slice.
    # Assigned by storage on first save. Preserved across amendments/deletions.
    sample_index: Optional[int] = None


    # System ordinal within the current slice sample run (resets when slice sample completes).
    # Assigned by storage on save.
    system_index: Optional[int] = None

    # === CMDR-input: Slice status ===
    slice_status: SliceStatus = SliceStatus.IN_PROGRESS
    completeness_confidence: int = 0                # 0-100 slider value
    sampling_method: SamplingMethod = SamplingMethod.OTHER

    # === CMDR-input: Density sampling data (from spreadsheet) ===
    system_count: Optional[int] = None              # Raw system count observed
    corrected_n: Optional[int] = None               # User-adjusted count (avoids zero, stabilizes calc)
    max_distance: Optional[float] = None            # Search radius in LY

    # === CMDR-input: Flags and notes ===
    flags: ObservationFlags = field(default_factory=ObservationFlags)
    notes: str = ""                                 # Free-form text

    # === Amendment tracking ===
    supersedes_id: Optional[str] = None             # ID of record this amends (None for new)
    record_status: RecordStatus = RecordStatus.ACTIVE

    # === Versioning ===
    schema_version: int = 1
    app_version: str = ""

    # === Hash chain (set during save) ===
    payload_hash: str = ""
    prev_hash: Optional[str] = None

    # === Timestamps ===
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_payload_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.
        Used for payload_json storage and hash calculation.
        """
        return {
            "id": self.id,
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc,
            "system_address": self.system_address,
            "system_name": self.system_name,
            "star_pos": list(self.star_pos),
            "z_bin": self.z_bin,
            "session_id": self.session_id,
            "body_name": self.body_name,
            "sample_index": self.sample_index,
            "system_index": self.system_index,
            "slice_status": self.slice_status.value,
            "completeness_confidence": self.completeness_confidence,
            "sampling_method": self.sampling_method.value,
            "system_count": self.system_count,
            "corrected_n": self.corrected_n,
            "max_distance": self.max_distance,
            "flags": self.flags.to_dict(),
            "notes": self.notes,
            "supersedes_id": self.supersedes_id,
            "record_status": self.record_status.value,
            "schema_version": self.schema_version,
            "app_version": self.app_version,
            "created_at_utc": self.created_at_utc,
        }

    def to_json(self, sort_keys: bool = True) -> str:
        """Serialize to JSON (deterministic for hashing)"""
        return json.dumps(self.to_payload_dict(), sort_keys=sort_keys, separators=(',', ':'))

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of payload"""
        return hashlib.sha256(self.to_json().encode('utf-8')).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ObserverNote':
        """Create ObserverNote from dictionary"""
        # Handle enum conversions
        if 'slice_status' in data and isinstance(data['slice_status'], str):
            data['slice_status'] = SliceStatus(data['slice_status'])
        if 'sampling_method' in data and isinstance(data['sampling_method'], str):
            data['sampling_method'] = SamplingMethod(data['sampling_method'])
        if 'record_status' in data and isinstance(data['record_status'], str):
            data['record_status'] = RecordStatus(data['record_status'])

        # Handle flags
        if 'flags' in data and isinstance(data['flags'], dict):
            data['flags'] = ObservationFlags.from_dict(data['flags'])

        # Handle star_pos tuple
        if 'star_pos' in data and isinstance(data['star_pos'], list):
            data['star_pos'] = tuple(data['star_pos'])

        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}

        return cls(**filtered_data)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the observation before saving.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Failsafe: corrected_n is always derived from system_count (N = system_count + 1)
        if self.system_count is not None:
            self.corrected_n = self.system_count + 1

        # Required fields
        if not self.system_name:
            errors.append("System name is required")

        # Discard requires reason
        if self.slice_status == SliceStatus.DISCARD and not self.notes.strip():
            errors.append("Discard status requires a reason in notes")

        # Completeness confidence range
        if not 0 <= self.completeness_confidence <= 100:
            errors.append("Completeness confidence must be 0-100")

        # Corrected n should be positive if set
        if self.corrected_n is not None and self.corrected_n < 0:
            errors.append("Corrected n must be non-negative")

        # System count should be non-negative if set
        if self.system_count is not None and self.system_count < 0:
            errors.append("System count must be non-negative")

        # Max distance should be positive if set
        if self.max_distance is not None and self.max_distance <= 0:
            errors.append("Max distance must be positive")

        return (len(errors) == 0, errors)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_event_id(journal_event: Dict[str, Any]) -> str:
    """
    Generate deterministic event ID from journal event data.
    Same input always produces same output.

    Args:
        journal_event: Dictionary from journal file

    Returns:
        16-character hex string
    """
    components = [
        journal_event.get('timestamp', ''),
        journal_event.get('event', ''),
        str(journal_event.get('SystemAddress', '')),
        str(journal_event.get('BodyID', '')),
    ]
    return hashlib.sha256('|'.join(components).encode()).hexdigest()[:16]


def calculate_z_bin(z_coordinate: float, bin_size: int = 50) -> int:
    """
    Calculate Z-bin from Z coordinate.

    Args:
        z_coordinate: Z position in light-years
        bin_size: Size of each bin (default 50 LY)

    Returns:
        Z-bin value (e.g., 350 for z=347)
    """
    return round(z_coordinate / bin_size) * bin_size


def create_observation_from_context(
    context: Dict[str, Any],
    session_id: str,
    app_version: str = ""
) -> ObserverNote:
    """
    Create a new ObserverNote pre-filled from journal context.

    Args:
        context: Dictionary with system_name, system_address, star_pos, etc.
        session_id: Current session ID
        app_version: Application version string

    Returns:
        New ObserverNote with auto-filled fields
    """
    star_pos = context.get('star_pos', (0.0, 0.0, 0.0))
    if isinstance(star_pos, list):
        star_pos = tuple(star_pos)

    return ObserverNote(
        event_id=context.get('event_id', ''),
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        system_address=context.get('system_address'),
        system_name=context.get('system_name', ''),
        star_pos=star_pos,
        z_bin=calculate_z_bin(star_pos[2]) if star_pos else 0,
        session_id=session_id,
        body_name=context.get('body_name'),
        app_version=app_version,
    )
