"""
Journal State Manager - Current CMDR Context for Overlay UI
============================================================

Maintains the current state of the CMDR's position and context,
providing thread-safe access for the overlay UI to pre-fill fields.

This is a prerequisite for the Observer Note overlay system.
The JournalMonitor updates this state, and the UI reads from it.

Design:
- Thread-safe: UI and journal watcher run on different threads
- Immutable snapshots: get_context() returns a frozen copy
- Callbacks: Register for Z-bin changes to auto-trigger overlay
"""

# ============================================================================
# IMPORTS
# ============================================================================

import hashlib
from threading import Lock, RLock
from typing import Optional, Tuple, List, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from observer_models import calculate_z_bin, generate_event_id


# =============================================================================
# CURRENT CONTEXT (Immutable Snapshot)
# =============================================================================

@dataclass(frozen=True)
class CurrentContext:
    """
    Immutable snapshot of current CMDR state.

    This is what the overlay UI receives when it opens.
    All fields are read-only after creation.
    """
    # System info
    system_name: Optional[str] = None
    system_address: Optional[int] = None  # Game's unique system ID
    star_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # X, Y, Z coordinates

    # Derived values
    z_bin: int = 0  # Calculated from star_pos[2]

    # Last activity
    last_scan_body: Optional[str] = None
    last_event_id: Optional[str] = None
    last_event_timestamp: Optional[str] = None

    # Session info
    session_id: Optional[str] = None
    cmdr_name: Optional[str] = None

    # Z-target tracking (for Next Z Target indicator)
    last_sample_z_bin: Optional[int] = None
    z_direction: int = 1  # +1 for +Z, -1 for -Z

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ObserverNote creation"""
        return {
            'system_name': self.system_name,
            'system_address': self.system_address,
            'star_pos': self.star_pos,
            'z_bin': self.z_bin,
            'body_name': self.last_scan_body,
            'event_id': self.last_event_id,
            'session_id': self.session_id,
            'cmdr_name': self.cmdr_name,
        }


# =============================================================================
# Z-BIN CHANGE EVENT
# =============================================================================

@dataclass
class ZBinChangeEvent:
    """Event fired when CMDR crosses into a new Z-bin"""
    old_z_bin: int
    new_z_bin: int
    system_name: str
    star_pos: Tuple[float, float, float]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =============================================================================
# JOURNAL STATE MANAGER
# =============================================================================

class JournalStateManager:
    """
    Maintains current CMDR context for overlay UI.

    Thread-safe for access from UI and journal watcher threads.
    Updates come from JournalMonitor, reads come from overlay UI.

    Usage:
        # In JournalMonitor setup:
        state_manager = JournalStateManager()
        state_manager.set_session_info(session_id, cmdr_name)

        # When processing events:
        state_manager.on_fsd_jump(event)
        state_manager.on_scan(event)
        state_manager.on_location(event)

        # In overlay UI:
        context = state_manager.get_context()
        # Use context to pre-fill ObserverNote fields

        # For auto-trigger on Z-bin change:
        state_manager.register_z_bin_callback(my_callback)
    """

    def __init__(self, z_bin_size: int = 50):
        """
        Initialize state manager.

        Args:
            z_bin_size: Size of Z-bins in light-years (default 50)
        """
        self._lock = RLock()  # Reentrant lock for nested calls
        self._z_bin_size = z_bin_size

        # Internal mutable state
        self._system_name: Optional[str] = None
        self._system_address: Optional[int] = None
        self._star_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._z_bin: int = 0
        self._last_scan_body: Optional[str] = None
        self._last_event_id: Optional[str] = None
        self._last_event_timestamp: Optional[str] = None
        self._session_id: Optional[str] = None
        self._cmdr_name: Optional[str] = None

        # Z-target tracking
        self._last_sample_z_bin: Optional[int] = None
        self._z_direction: int = 1  # +1 for +Z, -1 for -Z

        # Callbacks for Z-bin changes
        self._z_bin_callbacks: List[Callable[[ZBinChangeEvent], None]] = []

        # History for debugging/analytics (optional, bounded)
        self._z_bin_history: List[ZBinChangeEvent] = []
        self._max_history = 100


    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def set_session_info(self, session_id: str, cmdr_name: str):
        """
        Set session information (called when session starts).

        Args:
            session_id: Current session ID
            cmdr_name: Commander name
        """
        with self._lock:
            self._session_id = session_id
            self._cmdr_name = cmdr_name

    def clear_session(self):
        """Clear session info (called when session ends)"""
        with self._lock:
            self._session_id = None
            # Keep cmdr_name as it persists across sessions

    # =========================================================================
    # EVENT HANDLERS (called by JournalMonitor)
    # =========================================================================

    def on_fsd_jump(self, event: Dict[str, Any]):
        """
        Handle FSDJump event - updates system and position.

        This is the primary trigger for Z-bin changes.

        Args:
            event: FSDJump event dictionary from journal
        """
        with self._lock:
            old_z_bin = self._z_bin

            # Extract position
            star_pos = event.get('StarPos')
            if isinstance(star_pos, list) and len(star_pos) == 3:
                try:
                    x, y, z = float(star_pos[0]), float(star_pos[1]), float(star_pos[2])
                    self._star_pos = (x, y, z)
                    self._z_bin = calculate_z_bin(z, self._z_bin_size)
                except (ValueError, TypeError):
                    pass

            # Update system info
            self._system_name = event.get('StarSystem', self._system_name)
            self._system_address = event.get('SystemAddress', self._system_address)

            # Clear last scan body (we're in a new system)
            self._last_scan_body = None

            # Update event tracking
            self._last_event_id = generate_event_id(event)
            self._last_event_timestamp = event.get('timestamp')

            # Check for Z-bin change
            new_z_bin = self._z_bin
            if old_z_bin != 0 and new_z_bin != old_z_bin:
                self._fire_z_bin_change(old_z_bin, new_z_bin)

    def on_location(self, event: Dict[str, Any]):
        """
        Handle Location event - initial position on game load.

        Args:
            event: Location event dictionary from journal
        """
        with self._lock:
            # Extract position
            star_pos = event.get('StarPos')
            if isinstance(star_pos, list) and len(star_pos) == 3:
                try:
                    x, y, z = float(star_pos[0]), float(star_pos[1]), float(star_pos[2])
                    self._star_pos = (x, y, z)
                    self._z_bin = calculate_z_bin(z, self._z_bin_size)
                except (ValueError, TypeError):
                    pass

            # Update system info
            self._system_name = event.get('StarSystem', self._system_name)
            self._system_address = event.get('SystemAddress', self._system_address)

            # Update event tracking
            self._last_event_id = generate_event_id(event)
            self._last_event_timestamp = event.get('timestamp')

    def on_scan(self, event: Dict[str, Any]):
        """
        Handle Scan event - tracks last scanned body.

        Args:
            event: Scan event dictionary from journal
        """
        with self._lock:
            self._last_scan_body = event.get('BodyName')
            self._last_event_id = generate_event_id(event)
            self._last_event_timestamp = event.get('timestamp')

    def on_commander(self, event: Dict[str, Any]):
        """
        Handle Commander/LoadGame event - updates CMDR name.

        Args:
            event: Commander or LoadGame event dictionary
        """
        with self._lock:
            name = event.get('Name') or event.get('Commander')
            if name:
                self._cmdr_name = name

    # =========================================================================
    # CONTEXT ACCESS (called by UI)
    # =========================================================================

    def get_context(self) -> CurrentContext:
        """
        Get immutable snapshot of current context.

        Thread-safe. Returns a frozen copy that won't change.

        Returns:
            CurrentContext with all current state
        """
        with self._lock:
            return CurrentContext(
                system_name=self._system_name,
                system_address=self._system_address,
                star_pos=self._star_pos,
                z_bin=self._z_bin,
                last_scan_body=self._last_scan_body,
                last_event_id=self._last_event_id,
                last_event_timestamp=self._last_event_timestamp,
                session_id=self._session_id,
                cmdr_name=self._cmdr_name,
                last_sample_z_bin=self._last_sample_z_bin,
                z_direction=self._z_direction,
            )

    # =========================================================================
    # Z-TARGET TRACKING
    # =========================================================================

    def set_last_sample_z_bin(self, z_bin: int):
        """Update the last saved sample's Z-bin (called after a sample is saved)."""
        with self._lock:
            old = self._last_sample_z_bin
            self._last_sample_z_bin = int(z_bin)
            # Auto-detect direction if we have a previous sample
            if old is not None and z_bin != old:
                self._z_direction = 1 if z_bin > old else -1

    def set_z_direction(self, direction: int):
        """Set Z direction: +1 for +Z, -1 for -Z."""
        with self._lock:
            self._z_direction = 1 if direction >= 0 else -1

    def get_z_target(self) -> Dict[str, Any]:
        """Get current Z-target info for the overlay."""
        with self._lock:
            current_z = self._star_pos[2]
            last = self._last_sample_z_bin
            direction = self._z_direction
            if last is not None:
                target_z = last + (50 * direction)
            else:
                # No sample yet: target is current z_bin + 50 in the current direction
                target_z = self._z_bin + (50 * direction)
            return {
                "last_sample_z_bin": last,
                "target_z": target_z,
                "direction": direction,
                "current_z": current_z,
            }

    def get_z_bin(self) -> int:
        """Get current Z-bin (thread-safe convenience method)"""
        with self._lock:
            return self._z_bin

    def get_system_name(self) -> Optional[str]:
        """Get current system name (thread-safe convenience method)"""
        with self._lock:
            return self._system_name

    # =========================================================================
    # Z-BIN CHANGE CALLBACKS
    # =========================================================================

    def register_z_bin_callback(self, callback: Callable[[ZBinChangeEvent], None]):
        """
        Register callback for Z-bin changes.

        Callback is invoked when CMDR jumps to a system in a different Z-bin.
        Use this to auto-trigger the overlay UI.

        Args:
            callback: Function that receives ZBinChangeEvent
        """
        with self._lock:
            if callback not in self._z_bin_callbacks:
                self._z_bin_callbacks.append(callback)

    def unregister_z_bin_callback(self, callback: Callable[[ZBinChangeEvent], None]):
        """
        Remove a Z-bin change callback.

        Args:
            callback: Previously registered callback
        """
        with self._lock:
            if callback in self._z_bin_callbacks:
                self._z_bin_callbacks.remove(callback)

    def _fire_z_bin_change(self, old_z_bin: int, new_z_bin: int):
        """
        Fire Z-bin change event to all registered callbacks.

        Called internally when Z-bin changes. Lock is already held.
        """
        event = ZBinChangeEvent(
            old_z_bin=old_z_bin,
            new_z_bin=new_z_bin,
            system_name=self._system_name or "",
            star_pos=self._star_pos,
        )

        # Store in history
        self._z_bin_history.append(event)
        if len(self._z_bin_history) > self._max_history:
            self._z_bin_history.pop(0)

        # Make copy of callbacks to avoid issues if callback modifies list
        callbacks = self._z_bin_callbacks.copy()

        # Fire callbacks (outside lock to prevent deadlocks)
        # Note: We release lock briefly for callbacks
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                # Don't let callback errors break the state manager
                pass

    def get_z_bin_history(self) -> List[ZBinChangeEvent]:
        """
        Get history of Z-bin changes (for debugging/analytics).

        Returns:
            List of recent ZBinChangeEvent objects
        """
        with self._lock:
            return self._z_bin_history.copy()

    # =========================================================================
    # UTILITY
    # =========================================================================

    def reset(self):
        """Reset all state (for testing or re-initialization)"""
        with self._lock:
            self._system_name = None
            self._system_address = None
            self._star_pos = (0.0, 0.0, 0.0)
            self._z_bin = 0
            self._last_scan_body = None
            self._last_event_id = None
            self._last_event_timestamp = None
            self._session_id = None
            self._cmdr_name = None
            self._z_bin_history.clear()
