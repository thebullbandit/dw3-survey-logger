"""
Graceful Shutdown Manager
=========================

Ensures clean shutdown of all components with proper resource cleanup.

Benefits:
- No data loss
- Proper resource cleanup
- Session tracking
- Clean state on restart
- Error recovery
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   shutdown_manager.py
#
# Connected modules (direct imports):
#   error_handling
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import threading
import time
import signal
import sys
from typing import List, Callable, Optional
from dataclasses import dataclass
from enum import Enum

from error_handling import ErrorHandler


# ============================================================================
# CLASSES
# ============================================================================

class ShutdownPriority(Enum):
    """Shutdown priority levels (higher numbers = higher priority)"""
    CRITICAL = 100   # Must complete (database, sessions)
    HIGH = 75        # Should complete (file writes)
    NORMAL = 50      # Normal cleanup (thread stops)
    LOW = 25         # Optional (cache clear)


@dataclass
class ShutdownTask:
    """A task to execute during shutdown"""
    name: str
    callback: Callable[[], None]
    priority: ShutdownPriority
    timeout: float = 5.0  # Maximum time to wait
    

class ShutdownManager:
    """
    Manages graceful application shutdown
    
    Ensures all components stop cleanly and resources are released.
    """
    
    def __init__(self, error_handler: ErrorHandler):
        """
        Initialize shutdown manager
        
        Args:
            error_handler: Error handler for logging
        """
        self.error_handler = error_handler
        self.logger = error_handler.logger
        
        # Shutdown tasks (ordered by priority)
        self._tasks: List[ShutdownTask] = []
        
        # Shutdown state
        self._shutdown_initiated = False
        self._shutdown_complete = False
        self._shutdown_lock = threading.Lock()
        
        # Signal handlers
        self._original_sigint = None
        self._original_sigterm = None
        
        # Callbacks
        self.on_shutdown_start: Optional[Callable[[], None]] = None
        self.on_shutdown_complete: Optional[Callable[[], None]] = None
    
    def register_task(
        self,
        name: str,
        callback: Callable[[], None],
        priority: ShutdownPriority = ShutdownPriority.NORMAL,
        timeout: float = 5.0
    ):
        """
        Register a shutdown task
        
        Args:
            name: Task name (for logging)
            callback: Function to call during shutdown
            priority: Task priority
            timeout: Maximum time to wait for task
        """
        task = ShutdownTask(
            name=name,
            callback=callback,
            priority=priority,
            timeout=timeout
        )
        
        self._tasks.append(task)
        self.logger.info(f"Registered shutdown task: {name} (priority: {priority.name})")
    
    def register_component(self, component_name: str, component):
        """
        Register a component with standard shutdown methods
        
        Looks for common shutdown methods:
        - stop()
        - close()
        - cleanup()
        - shutdown()
        
        Args:
            component_name: Component name (for logging)
            component: Component instance
        """
        # Check for stop() method
        if hasattr(component, 'stop') and callable(component.stop):
            self.register_task(
                f"{component_name}.stop()",
                component.stop,
                priority=ShutdownPriority.NORMAL,
                timeout=3.0
            )
        
        # Check for close() method
        if hasattr(component, 'close') and callable(component.close):
            self.register_task(
                f"{component_name}.close()",
                component.close,
                priority=ShutdownPriority.HIGH,
                timeout=2.0
            )
        
        # Check for cleanup() method
        if hasattr(component, 'cleanup') and callable(component.cleanup):
            self.register_task(
                f"{component_name}.cleanup()",
                component.cleanup,
                priority=ShutdownPriority.CRITICAL,
                timeout=5.0
            )
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            self.logger.info(f"Received {signal_name} signal")
            self.initiate_shutdown()
        
        # Save original handlers
        self._original_sigint = signal.signal(signal.SIGINT, signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, signal_handler)
        
        self.logger.info("Signal handlers installed")
    
    def restore_signal_handlers(self):
        """Restore original signal handlers"""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)
    
    def initiate_shutdown(self, exit_code: int = 0):
        """
        Initiate graceful shutdown
        
        Args:
            exit_code: Exit code for sys.exit()
        """
        with self._shutdown_lock:
            if self._shutdown_initiated:
                self.logger.info("Shutdown already in progress")
                return
            
            self._shutdown_initiated = True
        
        self.logger.info("=" * 60)
        self.logger.info("GRACEFUL SHUTDOWN INITIATED")
        self.logger.info("=" * 60)
        
        # Callback for shutdown start
        if self.on_shutdown_start:
            try:
                self.on_shutdown_start()
            except Exception as e:
                self.logger.error(f"Shutdown start callback failed: {e}")
        
        # Execute shutdown
        self._execute_shutdown()
        
        # Callback for shutdown complete
        if self.on_shutdown_complete:
            try:
                self.on_shutdown_complete()
            except Exception as e:
                self.logger.error(f"Shutdown complete callback failed: {e}")
        
        self._shutdown_complete = True
        
        self.logger.info("=" * 60)
        self.logger.info("GRACEFUL SHUTDOWN COMPLETE")
        self.logger.info("=" * 60)
        
        # Exit application
        sys.exit(exit_code)
    
    def _execute_shutdown(self):
        """Execute all shutdown tasks in priority order"""
        # Sort tasks by priority (highest first)
        sorted_tasks = sorted(
            self._tasks,
            key=lambda t: t.priority.value,
            reverse=True
        )
        
        # Group by priority for logging
        current_priority = None
        
        for task in sorted_tasks:
            # Log priority group
            if task.priority != current_priority:
                current_priority = task.priority
                self.logger.info(f"\n--- Priority: {current_priority.name} ---")
            
            # Execute task
            self._execute_task(task)
        
        self.logger.info("\nAll shutdown tasks completed")
    
    def _execute_task(self, task: ShutdownTask):
        """Execute a single shutdown task with timeout"""
        self.logger.info(f"Executing: {task.name}")
        
        # Create thread for task
        task_thread = threading.Thread(
            target=task.callback,
            name=f"shutdown-{task.name}"
        )
        
        try:
            # Start task
            start_time = time.time()
            task_thread.start()
            
            # Wait with timeout
            task_thread.join(timeout=task.timeout)
            
            # Check if completed
            if task_thread.is_alive():
                elapsed = time.time() - start_time
                self.logger.error(
                    f"Task '{task.name}' did not complete within {task.timeout}s "
                    f"(elapsed: {elapsed:.2f}s)"
                )
                # Task still running, but we continue anyway
            else:
                elapsed = time.time() - start_time
                self.logger.info(f"✓ {task.name} completed ({elapsed:.2f}s)")
        
        except Exception as e:
            self.logger.error(f"Task '{task.name}' failed: {e}")
    
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress"""
        with self._shutdown_lock:
            return self._shutdown_initiated
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown to complete
        
        Args:
            timeout: Maximum time to wait (None = forever)
            
        Returns:
            True if shutdown completed, False if timeout
        """
        start_time = time.time()
        
        while not self._shutdown_complete:
            if timeout and (time.time() - start_time) > timeout:
                return False
            
            time.sleep(0.1)
        
        return True


class ComponentShutdownHelper:
    """Helper for components to handle shutdown gracefully"""
    
    def __init__(self, component_name: str, shutdown_manager: ShutdownManager):
        """
        Initialize component shutdown helper
        
        Args:
            component_name: Name of component
            shutdown_manager: Shutdown manager instance
        """
        self.component_name = component_name
        self.shutdown_manager = shutdown_manager
        self.logger = shutdown_manager.logger
        
        # Shutdown flags
        self._should_stop = threading.Event()
        self._is_stopped = threading.Event()
    
    def should_stop(self) -> bool:
        """Check if component should stop"""
        return self._should_stop.is_set() or self.shutdown_manager.is_shutting_down()
    
    def signal_stop(self):
        """Signal that component should stop"""
        self._should_stop.set()
    
    def wait_for_stop(self, timeout: float = 1.0) -> bool:
        """Wait for stop signal"""
        return self._should_stop.wait(timeout)
    
    def mark_stopped(self):
        """Mark component as stopped"""
        self._is_stopped.set()
        self.logger.info(f"{self.component_name} stopped cleanly")
    
    def is_stopped(self) -> bool:
        """Check if component has stopped"""
        return self._is_stopped.is_set()


class SessionManager:
    """Manages session lifecycle for graceful shutdown"""
    
    def __init__(self, database, logger):
        """
        Initialize session manager
        
        Args:
            database: Database instance
            logger: Logger instance
        """
        self.db = database
        self.logger = logger
        self.current_session_id: Optional[str] = None
        self.session_lock = threading.Lock()
    
    def start_session(self, cmdr_name: str, journal_file: str) -> str:
        """Start a new session"""
        with self.session_lock:
            # End previous session if exists
            if self.current_session_id:
                self.end_session()
            
            # Start new session
            try:
                session_id = self.db.start_session(cmdr_name, journal_file)
                self.current_session_id = session_id
                self.logger.info(f"Session started: {session_id}")
                return session_id
            except Exception as e:
                self.logger.error(f"Failed to start session: {e}")
                return ""
    
    def end_session(self):
        """End current session"""
        with self.session_lock:
            if not self.current_session_id:
                return
            
            try:
                self.db.end_session(self.current_session_id)
                self.logger.info(f"Session ended: {self.current_session_id}")
                self.current_session_id = None
            except Exception as e:
                self.logger.error(f"Failed to end session: {e}")
    
    def get_current_session_id(self) -> Optional[str]:
        """Get current session ID"""
        with self.session_lock:
            return self.current_session_id
    
    def shutdown(self):
        """Shutdown - end current session"""
        self.logger.info("SessionManager shutdown: ending current session")
        self.end_session()


class ResourceTracker:
    """Tracks open resources for cleanup"""
    
    def __init__(self, logger):
        """
        Initialize resource tracker
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.resources = []
        self.lock = threading.Lock()
    
    def track(self, resource, name: str, cleanup_callback: Callable):
        """
        Track a resource
        
        Args:
            resource: Resource object
            name: Resource name
            cleanup_callback: Function to cleanup resource
        """
        with self.lock:
            self.resources.append({
                "resource": resource,
                "name": name,
                "cleanup": cleanup_callback
            })
            self.logger.info(f"Tracking resource: {name}")
    
    def cleanup_all(self):
        """Cleanup all tracked resources"""
        with self.lock:
            self.logger.info(f"Cleaning up {len(self.resources)} resources")
            
            for res in reversed(self.resources):  # Cleanup in reverse order
                try:
                    self.logger.info(f"Cleaning up: {res['name']}")
                    res['cleanup']()
                except Exception as e:
                    self.logger.error(f"Failed to cleanup {res['name']}: {e}")
            
            self.resources.clear()
            self.logger.info("All resources cleaned up")


# ============================================================================
# FUNCTIONS
# ============================================================================

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """Example of using ShutdownManager"""
    from error_handling import ErrorHandler, FileLogger
    
    # Create logger and error handler
    logger = FileLogger(Path("app.log"))
    error_handler = ErrorHandler(logger)
    
    # Create shutdown manager
    shutdown_manager = ShutdownManager(error_handler)
    
    # Setup signal handlers (Ctrl+C, etc.)
    shutdown_manager.setup_signal_handlers()
    
    # Register shutdown tasks
    
    # Critical tasks (run first)
    shutdown_manager.register_task(
        "Save database",
        lambda: print("Saving database..."),
        priority=ShutdownPriority.CRITICAL,
        timeout=5.0
    )
    
    shutdown_manager.register_task(
        "End session",
        lambda: print("Ending session..."),
        priority=ShutdownPriority.CRITICAL,
        timeout=3.0
    )
    
    # Normal tasks
    shutdown_manager.register_task(
        "Stop journal monitor",
        lambda: print("Stopping monitor..."),
        priority=ShutdownPriority.NORMAL,
        timeout=2.0
    )
    
    shutdown_manager.register_task(
        "Stop presenter",
        lambda: print("Stopping presenter..."),
        priority=ShutdownPriority.NORMAL,
        timeout=2.0
    )
    
    # Low priority tasks
    shutdown_manager.register_task(
        "Clear cache",
        lambda: print("Clearing cache..."),
# ============================================================================
# ENTRYPOINT
# ============================================================================

        priority=ShutdownPriority.LOW,
        timeout=1.0
    )
    
    # Initiate shutdown
    shutdown_manager.initiate_shutdown()


if __name__ == "__main__":
    example_usage()
