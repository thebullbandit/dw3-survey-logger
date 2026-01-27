"""
Dependency Injection System
============================

Provides proper dependency injection for the application.

Benefits:
- Clear dependencies for each component
- Easy to mock for testing
- Configuration as objects (not dicts)
- Centralized dependency management
"""

# ============================================================================
# IMPORTS
# ============================================================================

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Optional
import os
import logging


# ============================================================================
# CONFIGURATION CLASSES
# ============================================================================

@dataclass
class PathConfig:
    """File paths configuration"""
    user_profile: Path
    journal_dir: Path
    output_dir: Path
    db_path: Path
    csv_path: Path
    log_path: Path
    asset_path: Path
    icon_name: str = "earth2.ico"
    
    @classmethod
    def from_environment(cls) -> 'PathConfig':
        """Create path configuration from environment"""
        user_profile = Path(os.environ.get("USERPROFILE", ""))
        output_dir = user_profile / "Documents" / "DW3" / "Earth2"
        
        return cls(
            user_profile=user_profile,
            journal_dir=user_profile / "Saved Games" / "Frontier Developments" / "Elite Dangerous",
            output_dir=output_dir,
            db_path=output_dir / "DW3_Earth2.db",
            csv_path=output_dir / "DW3_Earth2_Candidates.csv",
            log_path=output_dir / "DW3_Earth2_Logger.log",
            asset_path=Path(__file__).parent / "assets",
            icon_name="earth2.ico"
        )


@dataclass
class RatingConfig:
    """Earth 2.0 rating criteria configuration"""
    # Temperature ranges (Kelvin)
    temp_a_min: float = 240.0
    temp_a_max: float = 320.0
    temp_b_min: float = 200.0
    temp_b_max: float = 360.0
    
    # Gravity ranges (Earth G)
    grav_a_min: float = 0.80
    grav_a_max: float = 1.30
    grav_b_min: float = 0.50
    grav_b_max: float = 1.80
    
    # Distance ranges (light-seconds)
    dist_a_max: float = 5000.0
    dist_b_max: float = 15000.0
    
    # Worth landing criteria
    worth_dist_max: float = 8000.0
    worth_temp_min: float = 210.0
    worth_temp_max: float = 340.0
    worth_grav_max: float = 1.60


@dataclass
class MonitoringConfig:
    """Journal monitoring configuration"""
    poll_fast_seconds: float = 0.1
    poll_slow_seconds: float = 0.25
    journal_seed_max_bytes: int = 2_000_000
    test_mode: bool = False
    test_read_from_start: bool = True


@dataclass
class UIConfig:
    """UI configuration"""
    refresh_fast_ms: int = 100
    refresh_slow_ms: int = 250
    comms_max_lines: int = 150
    
    # Color scheme
    bg: str = "#0a0a0f"
    bg_panel: str = "#12121a"
    bg_field: str = "#1a1a28"
    text: str = "#e0e0ff"
    muted: str = "#6a6a8a"
    border_outer: str = "#2a2a3f"
    border_inner: str = "#1f1f2f"
    orange: str = "#ff8833"
    orange_dim: str = "#cc6622"
    green: str = "#44ff88"
    red: str = "#ff4444"
    led_active: str = "#00ff88"
    led_idle: str = "#888888"


@dataclass
class AppConfig:
    """Complete application configuration"""
    app_name: str
    version: str
    paths: PathConfig
    rating: RatingConfig
    monitoring: MonitoringConfig
    ui: UIConfig
    
    @classmethod
    def create_default(cls) -> 'AppConfig':
        """Create default application configuration"""
        return cls(
            app_name="DW3 Earth2 Logger",
            version="2.1.0-DI",
            paths=PathConfig.from_environment(),
            rating=RatingConfig(),
            monitoring=MonitoringConfig(),
            ui=UIConfig()
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary (for backward compatibility)"""
        return {
            # Application info
            "APP_NAME": self.app_name,
            "VERSION": self.version,
            
            # Paths
            "JOURNAL_DIR": self.paths.journal_dir,
            "OUTDIR": self.paths.output_dir,
            "DB_PATH": self.paths.db_path,
            "OUTCSV": self.paths.csv_path,
            "LOGFILE": self.paths.log_path,
            "ASSET_PATH": self.paths.asset_path,
            "ICON_NAME": self.paths.icon_name,
            
            # Monitoring
            "POLL_SECONDS_FAST": self.monitoring.poll_fast_seconds,
            "POLL_SECONDS_SLOW": self.monitoring.poll_slow_seconds,
            "TEST_MODE": self.monitoring.test_mode,
            "TEST_READ_FROM_START": self.monitoring.test_read_from_start,
            
            # UI
            "UI_REFRESH_FAST_MS": self.ui.refresh_fast_ms,
            "UI_REFRESH_SLOW_MS": self.ui.refresh_slow_ms,
            "COMMS_MAX_LINES": self.ui.comms_max_lines,
            
            # Rating criteria
            "TEMP_A_MIN": self.rating.temp_a_min,
            "TEMP_A_MAX": self.rating.temp_a_max,
            "TEMP_B_MIN": self.rating.temp_b_min,
            "TEMP_B_MAX": self.rating.temp_b_max,
            "GRAV_A_MIN": self.rating.grav_a_min,
            "GRAV_A_MAX": self.rating.grav_a_max,
            "GRAV_B_MIN": self.rating.grav_b_min,
            "GRAV_B_MAX": self.rating.grav_b_max,
            "DIST_A_MAX": self.rating.dist_a_max,
            "DIST_B_MAX": self.rating.dist_b_max,
            "WORTH_DIST_MAX": self.rating.worth_dist_max,
            "WORTH_TEMP_MIN": self.rating.worth_temp_min,
            "WORTH_TEMP_MAX": self.rating.worth_temp_max,
            "WORTH_GRAV_MAX": self.rating.worth_grav_max,
            
            # Colors
            "BG": self.ui.bg,
            "BG_PANEL": self.ui.bg_panel,
            "BG_FIELD": self.ui.bg_field,
            "TEXT": self.ui.text,
            "MUTED": self.ui.muted,
            "BORDER_OUTER": self.ui.border_outer,
            "BORDER_INNER": self.ui.border_inner,
            "ORANGE": self.ui.orange,
            "ORANGE_DIM": self.ui.orange_dim,
            "GREEN": self.ui.green,
            "RED": self.ui.red,
            "LED_ACTIVE": self.ui.led_active,
            "LED_IDLE": self.ui.led_idle,
        }


# ============================================================================
# INTERFACE PROTOCOLS (Dependency Inversion)
# ============================================================================

class IDatabase(Protocol):
    """Database interface (follows Interface Segregation Principle)"""
    
    def start_session(self, cmdr_name: str, journal_file: str) -> str:
        """Start a new session"""
        ...
    
    def end_session(self, session_id: str) -> None:
        """End a session"""
        ...
    
    def log_candidate(self, data: dict) -> bool:
        """Log a candidate"""
        ...
    
    def get_cmdr_stats(self, cmdr_name: str) -> Optional[dict]:
        """Get commander statistics"""
        ...
    
    def get_all_cmdr_stats(self) -> list[dict]:
        """Get all commander statistics"""
        ...
    
    def load_seen_bodies(self, cmdr_name: Optional[str] = None) -> tuple[set, set]:
        """Load seen bodies"""
        ...
    
    def export_to_csv(self, output_path: Path, cmdr_name: Optional[str] = None) -> None:
        """Export to CSV"""
        ...
    
    def close(self) -> None:
        """Close database connection"""
        ...


class ILogger(Protocol):
    """Logger interface"""
    
    def log(self, message: str) -> None:
        """Log a message"""
        ...
    
    def error(self, message: str) -> None:
        """Log an error"""
        ...
    
    def info(self, message: str) -> None:
        """Log info"""
        ...


# ============================================================================
# SIMPLE FILE LOGGER IMPLEMENTATION
# ============================================================================

class FileLogger:
    """Rotating file-based logger (thread-safe + bounded disk usage).

    This keeps the original FileLogger interface (log/info/error), but uses Python's
    logging subsystem with a RotatingFileHandler so logs don't grow forever and the
    file handle isn't reopened on every message.
    """

    def __init__(
        self,
        log_path: Path,
        *,
        max_bytes: int = 5 * 1024 * 1024,   # 5 MB per file
        backup_count: int = 5,              # keep last 5 files
    ):
        self.log_path = log_path
        self._ensure_directory()

        # Use a deterministic logger name per path to avoid duplicate handlers
        logger_name = f"dw3.filelogger:{str(self.log_path)}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            from logging.handlers import RotatingFileHandler

            handler = RotatingFileHandler(
                filename=str(self.log_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
                delay=False,   # open once and keep it open
            )
            formatter = logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def _ensure_directory(self):
        """Ensure log directory exists"""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def log(self, message: str):
        """Log a message"""
        try:
            self._logger.info(message)
        except Exception:
            pass

    def info(self, message: str):
        """Log info"""
        try:
            self._logger.info(message)
        except Exception:
            pass

    def error(self, message: str):
        """Log an error"""
        try:
            self._logger.error(message)
        except Exception:
            pass

# ============================================================================
# DEPENDENCY CONTAINER
# ============================================================================

@dataclass
class DependencyContainer:
    """
    Container for all application dependencies
    
    This is the central registry for dependency injection.
    All components receive their dependencies from this container.
    """
    config: AppConfig
    database: IDatabase
    logger: ILogger
    error_handler: Optional['ErrorHandler'] = None
    
    @classmethod
    def create(cls, config: Optional[AppConfig] = None) -> 'DependencyContainer':
        """
        Create dependency container with all dependencies
        
        Args:
            config: Application configuration (uses default if None)
            
        Returns:
            Configured dependency container
        """
        # Use default config if not provided
        if config is None:
            config = AppConfig.create_default()
        
        # Ensure output directory exists
        config.paths.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        logger = FileLogger(config.paths.log_path)
        logger.info(f"Application starting: {config.app_name} v{config.version}")
        
        # Import and create database
        # (Import here to avoid circular dependencies)
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from earth2_database import Earth2Database
            
            database = Earth2Database(config.paths.db_path)
            logger.info(f"Database initialized: {config.paths.db_path}")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        
        # Create error handler
        from error_handling import ErrorHandler
        error_handler = ErrorHandler(logger)
        
        return cls(
            config=config,
            database=database,
            logger=logger,
            error_handler=error_handler
        )
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self.database.close()
            self.logger.info("Application shutdown complete")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


# ============================================================================
# DEPENDENCY INJECTION HELPERS
# ============================================================================

def inject_dependencies(container: DependencyContainer):
    """
    Decorator to inject dependencies into a class
    
    Usage:
        @inject_dependencies(container)
        class MyClass:
            def __init__(self, config: AppConfig, database: IDatabase):
                self.config = config
                self.database = database
    """
    def decorator(cls):
        original_init = cls.__init__
        
        def new_init(self, *args, **kwargs):
            # Inject dependencies from container
            if 'config' not in kwargs:
                kwargs['config'] = container.config
            if 'database' not in kwargs:
                kwargs['database'] = container.database
            if 'logger' not in kwargs:
                kwargs['logger'] = container.logger
            
            original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        return cls
    
    return decorator


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_model(container: DependencyContainer):
    """
    Factory function to create Model with injected dependencies
    
    Args:
        container: Dependency container
        
    Returns:
        Configured Earth2Model instance
    """
    from model import Earth2Model
    
    return Earth2Model(
        database=container.database,
        config=container.config.to_dict()  # Model still uses dict for now
    )


def create_view(container: DependencyContainer, root):
    """
    Factory function to create View with injected dependencies
    
    Args:
        container: Dependency container
        root: Tkinter root window
        
    Returns:
        Configured Earth2View instance
    """
    from view import Earth2View
    
    return Earth2View(
        root=root,
        config=container.config.to_dict()  # View still uses dict for now
    )


def create_presenter(container: DependencyContainer, model, view, journal_monitor=None):
    """
    Factory function to create Presenter with injected dependencies
    
    Args:
        container: Dependency container
        model: Model instance
        view: View instance
        journal_monitor: JournalMonitor instance (optional)
        
    Returns:
        Configured Earth2Presenter instance
    """
    from presenter import Earth2Presenter
    
    return Earth2Presenter(
        model=model,
        view=view,
        config=container.config.to_dict(),  # Presenter still uses dict for now
        journal_monitor=journal_monitor
    )


def create_journal_monitor(container: DependencyContainer, model, presenter):
    """
    Factory function to create JournalMonitor with injected dependencies
    
    Args:
        container: Dependency container
        model: Model instance
        presenter: Presenter instance
        
    Returns:
        Configured JournalMonitor instance
    """
    from journal_monitor import JournalMonitor
    
    return JournalMonitor(
        journal_dir=container.config.paths.journal_dir,
        model=model,
        presenter=presenter,
        config=container.config.to_dict()  # JournalMonitor still uses dict for now
    )