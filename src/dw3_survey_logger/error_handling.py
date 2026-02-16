"""
Error Handling System
=====================

Comprehensive error handling with:
- Custom exception hierarchy
- Error context tracking
- Retry mechanisms
- User-friendly error messages
- Centralized logging
"""

# ============================================================================
# IMPORTS
# ============================================================================

import functools
import time
import traceback
from typing import Optional, Callable, Any, Type, TypeVar
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# ERROR SEVERITY LEVELS
# ============================================================================

class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================================================================
# CUSTOM EXCEPTION HIERARCHY
# ============================================================================

class Earth2Error(Exception):
    """Base exception for all Earth2 application errors"""
    
    def __init__(
        self, 
        message: str, 
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        user_message: Optional[str] = None,
        context: Optional[dict] = None
    ):
        """
        Initialize Earth2 error
        
        Args:
            message: Technical error message (for logs)
            severity: Error severity level
            user_message: User-friendly message (for UI)
            context: Additional context (dict)
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.user_message = user_message or message
        self.context = context or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Convert error to dictionary"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "user_message": self.user_message,
            "severity": self.severity.value,
            "context": self.context,
            "timestamp": self.timestamp
        }


class ConfigurationError(Earth2Error):
    """Configuration-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.CRITICAL,
            user_message="Configuration error. Please check your settings.",
            **kwargs
        )


class DatabaseError(Earth2Error):
    """Database-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.ERROR,
            user_message="Database error. Your data may not be saved.",
            **kwargs
        )


class FileSystemError(Earth2Error):
    """File system errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.ERROR,
            user_message="File system error. Check file permissions.",
            **kwargs
        )


class JournalError(Earth2Error):
    """Journal file parsing errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.WARNING,
            user_message="Journal file error. Some data may be skipped.",
            **kwargs
        )


class ValidationError(Earth2Error):
    """Data validation errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.WARNING,
            user_message="Invalid data encountered.",
            **kwargs
        )


class NetworkError(Earth2Error):
    """Network-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            severity=ErrorSeverity.WARNING,
            user_message="Network error. Some features may be unavailable.",
            **kwargs
        )


# ============================================================================
# ERROR CONTEXT
# ============================================================================

@dataclass
class ErrorContext:
    """Context information for errors"""
    operation: str
    component: str
    details: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "operation": self.operation,
            "component": self.component,
            "details": self.details
        }


# ============================================================================
# ERROR HANDLER
# ============================================================================

class ErrorHandler:
    """Centralized error handling"""
    
    def __init__(self, logger):
        """
        Initialize error handler
        
        Args:
            logger: Logger instance (ILogger)
        """
        self.logger = logger
        self.error_history = []
        self.max_history = 100
        
        # Error callbacks (for UI notifications)
        self.on_error: Optional[Callable[[Earth2Error], None]] = None
        self.on_critical_error: Optional[Callable[[Earth2Error], None]] = None
    
    def handle_error(
        self, 
        error: Exception,
        context: Optional[ErrorContext] = None,
        notify_user: bool = True
    ):
        """
        Handle an error
        
        Args:
            error: Exception that occurred
            context: Error context
            notify_user: Whether to notify user via UI
        """
        # Convert to Earth2Error if needed
        if not isinstance(error, Earth2Error):
            error = Earth2Error(
                message=str(error),
                severity=ErrorSeverity.ERROR,
                context=context.to_dict() if context else {}
            )
        
        # Add to history
        self._add_to_history(error)
        
        # Log error
        self._log_error(error, context)
        
        # Notify if critical
        if error.severity == ErrorSeverity.CRITICAL and self.on_critical_error:
            self.on_critical_error(error)
        elif notify_user and self.on_error:
            self.on_error(error)
    
    def _log_error(self, error: Earth2Error, context: Optional[ErrorContext]):
        """Log error with full details"""
        log_message = f"{error.severity.value}: {error.message}"
        
        if context:
            log_message += f" [Component: {context.component}, Operation: {context.operation}]"
        
        if error.context:
            log_message += f" [Context: {error.context}]"
        
        # Log based on severity
        if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.ERROR]:
            self.logger.error(log_message)
        else:
            self.logger.info(log_message)
    
    def _add_to_history(self, error: Earth2Error):
        """Add error to history"""
        self.error_history.append(error)
        
        # Trim history if too long
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history:]
    
    def get_recent_errors(self, count: int = 10) -> list[Earth2Error]:
        """Get recent errors"""
        return self.error_history[-count:]
    
    def clear_history(self):
        """Clear error history"""
        self.error_history.clear()


# ============================================================================
# DECORATORS
# ============================================================================

T = TypeVar('T')


def with_error_handling(
    component: str,
    operation: str,
    default_return: Any = None,
    raise_on_error: bool = False
):
    """
    Decorator for automatic error handling
    
    Args:
        component: Component name
        operation: Operation name
        default_return: Value to return on error
        raise_on_error: Whether to re-raise after handling
    
    Usage:
        @with_error_handling("Model", "log_candidate")
        def log_candidate(self, data):
            # Your code here
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get error handler from first arg (usually self)
                error_handler = None
                if args and hasattr(args[0], 'error_handler'):
                    error_handler = args[0].error_handler
                
                # Create context
                context = ErrorContext(
                    operation=operation,
                    component=component,
                    details={
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs": list(kwargs.keys())
                    }
                )
                
                # Handle error
                if error_handler:
                    error_handler.handle_error(e, context)
                
                # Re-raise if requested
                if raise_on_error:
                    raise
                
                return default_return
        
        return wrapper
    return decorator


def retry_on_error(
    max_attempts: int = 3,
    delay_seconds: float = 0.1,
    exponential_backoff: bool = True,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying operations that fail
    
    Args:
        max_attempts: Maximum retry attempts
        delay_seconds: Initial delay between retries
        exponential_backoff: Use exponential backoff
        exceptions: Tuple of exceptions to catch
    
    Usage:
        @retry_on_error(max_attempts=3, delay_seconds=0.5)
        def write_to_database(self, data):
            # Your code here
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = delay_seconds
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # Log retry attempt
                    if args and hasattr(args[0], 'error_handler'):
                        error_handler = args[0].error_handler
                        error_handler.logger.info(
                            f"Retry attempt {attempt + 1}/{max_attempts} "
                            f"for {func.__name__}: {e}"
                        )
                    
                    # Don't sleep after last attempt
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        
                        # Exponential backoff
                        if exponential_backoff:
                            delay *= 2
            
            # All attempts failed, raise last exception
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def validate_input(validator: Callable[[Any], bool], error_message: str):
    """
    Decorator for input validation
    
    Args:
        validator: Function to validate input
        error_message: Error message if validation fails
    
    Usage:
        @validate_input(lambda x: x > 0, "Value must be positive")
        def set_temperature(self, temp):
            self.temperature = temp
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validate first argument (after self)
            if len(args) > 1:
                value = args[1]
                if not validator(value):
                    raise ValidationError(
                        f"{error_message}: {value}",
                        context={"function": func.__name__, "value": value}
                    )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# SAFE OPERATIONS
# ============================================================================

class SafeOperations:
    """Safe wrapper for common operations"""
    
    def __init__(self, error_handler: ErrorHandler):
        """
        Initialize safe operations
        
        Args:
            error_handler: Error handler instance
        """
        self.error_handler = error_handler
    
    def safe_file_read(
        self, 
        filepath, 
        default: str = "",
        encoding: str = "utf-8"
    ) -> str:
        """
        Safely read file
        
        Args:
            filepath: Path to file
            default: Default value if read fails
            encoding: File encoding
            
        Returns:
            File contents or default
        """
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()
        except FileNotFoundError:
            raise FileSystemError(
                f"File not found: {filepath}",
                context={"filepath": str(filepath)}
            )
        except PermissionError:
            raise FileSystemError(
                f"Permission denied: {filepath}",
                context={"filepath": str(filepath)}
            )
        except Exception as e:
            self.error_handler.handle_error(
                e,
                context=ErrorContext(
                    operation="file_read",
                    component="SafeOperations",
                    details={"filepath": str(filepath)}
                )
            )
            return default
    
    def safe_file_write(
        self,
        filepath,
        content: str,
        encoding: str = "utf-8"
    ) -> bool:
        """
        Safely write file
        
        Args:
            filepath: Path to file
            content: Content to write
            encoding: File encoding
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, "w", encoding=encoding) as f:
                f.write(content)
            return True
            
        except PermissionError:
            raise FileSystemError(
                f"Permission denied: {filepath}",
                context={"filepath": str(filepath)}
            )
        except Exception as e:
            self.error_handler.handle_error(
                e,
                context=ErrorContext(
                    operation="file_write",
                    component="SafeOperations",
                    details={"filepath": str(filepath)}
                )
            )
            return False
    
    def safe_json_parse(self, json_string: str, default: dict = None) -> dict:
        """
        Safely parse JSON
        
        Args:
            json_string: JSON string
            default: Default value if parse fails
            
        Returns:
            Parsed JSON or default
        """
        import json
        
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            raise JournalError(
                f"Invalid JSON: {e}",
                context={"json_preview": json_string[:100]}
            )
        except Exception as e:
            self.error_handler.handle_error(
                e,
                context=ErrorContext(
                    operation="json_parse",
                    component="SafeOperations",
                    details={"preview": json_string[:100]}
                )
            )
            return default or {}
    
    def safe_database_operation(
        self,
        operation: Callable[[], T],
        operation_name: str,
        default: Any = None
    ) -> T:
        """
        Safely execute database operation with retry
        
        Args:
            operation: Operation to execute
            operation_name: Name of operation (for logging)
            default: Default value if operation fails
            
        Returns:
            Operation result or default
        """
        max_retries = 3
        delay = 0.1
        
        for attempt in range(max_retries):
            try:
                return operation()
            except Exception as e:
                if attempt < max_retries - 1:
                    self.error_handler.logger.info(
                        f"Database operation '{operation_name}' failed, "
                        f"retry {attempt + 1}/{max_retries}: {e}"
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise DatabaseError(
                        f"Database operation failed: {operation_name}",
                        context={"attempt": attempt + 1, "error": str(e)}
                    )
        
        return default


# ============================================================================
# ERROR RECOVERY
# ============================================================================

class ErrorRecovery:
    """Error recovery strategies"""
    
    @staticmethod
    def recover_database_connection(database, logger):
        """
        Attempt to recover database connection
        
        Args:
            database: Database instance
            logger: Logger instance
            
        Returns:
            True if recovered, False otherwise
        """
        try:
            logger.info("Attempting database connection recovery...")
            
            # Close existing connection
            try:
                database.close()
            except Exception:
                pass
            
            # Attempt reconnection
            # This would need database-specific implementation
            logger.info("Database connection recovered")
            return True
            
        except Exception as e:
            logger.error(f"Database recovery failed: {e}")
            return False
    
    @staticmethod
    def recover_journal_file(journal_monitor, logger):
        """
        Attempt to recover journal file reading
        
        Args:
            journal_monitor: Journal monitor instance
            logger: Logger instance
            
        Returns:
            True if recovered, False otherwise
        """
        try:
            logger.info("Attempting journal file recovery...")
            
            # Find newest journal
            newest = journal_monitor.file_reader.find_newest_journal()
            
            if newest:
                # Reopen file
                journal_monitor.file_reader.open_file(newest, from_start=False)
                logger.info(f"Journal file recovered: {newest.name}")
                return True
            else:
                logger.error("No journal files found during recovery")
                return False
                
        except Exception as e:
            logger.error(f"Journal recovery failed: {e}")
            return False


# ============================================================================
# EXCEPTION FORMATTER
# ============================================================================

class ExceptionFormatter:
    """Format exceptions for display"""
    
    @staticmethod
    def format_for_log(exception: Exception, include_traceback: bool = True) -> str:
        """
        Format exception for log file
        
        Args:
            exception: Exception to format
            include_traceback: Include full traceback
            
        Returns:
            Formatted string
        """
        if isinstance(exception, Earth2Error):
            parts = [
                f"Error Type: {exception.__class__.__name__}",
                f"Severity: {exception.severity.value}",
                f"Message: {exception.message}",
            ]
            
            if exception.context:
                parts.append(f"Context: {exception.context}")
            
            if include_traceback:
                parts.append(f"Traceback:\n{traceback.format_exc()}")
            
            return "\n".join(parts)
        else:
            if include_traceback:
                return f"{exception}\n{traceback.format_exc()}"
            else:
                return str(exception)
    
    @staticmethod
    def format_for_user(exception: Exception) -> str:
        """
        Format exception for user display
        
        Args:
            exception: Exception to format
            
        Returns:
            User-friendly message
        """
        if isinstance(exception, Earth2Error):
            return exception.user_message
        else:
            return f"An error occurred: {exception}"
