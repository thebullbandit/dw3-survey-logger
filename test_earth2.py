"""
Unit Tests - Earth2 Logger
===========================

Comprehensive unit tests demonstrating testability of refactored code.

Tests cover:
- Model business logic
- Error handling
- Configuration
- Journal monitoring
- Database operations (mocked)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import time

# Import components to test
import sys
sys.path.insert(0, str(Path(__file__).parent))

from error_handling import (
    ErrorHandler,
    ErrorSeverity,
    Earth2Error,
    DatabaseError,
    ValidationError,
    with_error_handling,
    retry_on_error,
    SafeOperations
)

from dependency_injection import (
    AppConfig,
    PathConfig,
    RatingConfig,
    MonitoringConfig,
    UIConfig
)


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

class TestConfiguration(unittest.TestCase):
    """Test configuration classes"""
    
    def test_rating_config_defaults(self):
        """Test RatingConfig has correct defaults"""
        config = RatingConfig()
        
        self.assertEqual(config.temp_a_min, 240.0)
        self.assertEqual(config.temp_a_max, 320.0)
        self.assertEqual(config.grav_a_min, 0.80)
        self.assertEqual(config.grav_a_max, 1.30)
    
    def test_app_config_creation(self):
        """Test AppConfig can be created"""
        config = AppConfig.create_default()
        
        self.assertEqual(config.app_name, "DW3 Earth2 Logger")
        self.assertIsInstance(config.paths, PathConfig)
        self.assertIsInstance(config.rating, RatingConfig)
        self.assertIsInstance(config.monitoring, MonitoringConfig)
        self.assertIsInstance(config.ui, UIConfig)
    
    def test_config_to_dict(self):
        """Test config can be converted to dict"""
        config = AppConfig.create_default()
        config_dict = config.to_dict()
        
        self.assertIsInstance(config_dict, dict)
        self.assertIn("APP_NAME", config_dict)
        self.assertIn("TEMP_A_MIN", config_dict)
        self.assertEqual(config_dict["TEMP_A_MIN"], 240.0)


# ============================================================================
# TEST ERROR HANDLING
# ============================================================================

class TestErrorHandling(unittest.TestCase):
    """Test error handling system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_logger = Mock()
        self.error_handler = ErrorHandler(self.mock_logger)
    
    def test_earth2_error_creation(self):
        """Test Earth2Error creation"""
        error = Earth2Error(
            message="Test error",
            severity=ErrorSeverity.ERROR,
            user_message="User friendly message",
            context={"key": "value"}
        )
        
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.severity, ErrorSeverity.ERROR)
        self.assertEqual(error.user_message, "User friendly message")
        self.assertEqual(error.context["key"], "value")
    
    def test_database_error_severity(self):
        """Test DatabaseError has correct severity"""
        error = DatabaseError("DB failed")
        
        self.assertEqual(error.severity, ErrorSeverity.ERROR)
        self.assertIn("Database error", error.user_message)
    
    def test_validation_error_severity(self):
        """Test ValidationError has correct severity"""
        error = ValidationError("Invalid data")
        
        self.assertEqual(error.severity, ErrorSeverity.WARNING)
    
    def test_error_handler_logs_error(self):
        """Test ErrorHandler logs errors"""
        error = Earth2Error("Test error")
        
        self.error_handler.handle_error(error, notify_user=False)
        
        # Verify error was logged
        self.mock_logger.info.assert_called()
    
    def test_error_handler_tracks_history(self):
        """Test ErrorHandler tracks error history"""
        error1 = Earth2Error("Error 1")
        error2 = Earth2Error("Error 2")
        
        self.error_handler.handle_error(error1, notify_user=False)
        self.error_handler.handle_error(error2, notify_user=False)
        
        history = self.error_handler.get_recent_errors(count=2)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].message, "Error 1")
        self.assertEqual(history[1].message, "Error 2")
    
    def test_error_handler_critical_callback(self):
        """Test ErrorHandler calls callback for critical errors"""
        critical_callback = Mock()
        self.error_handler.on_critical_error = critical_callback
        
        from error_handling import ConfigurationError
        critical_error = ConfigurationError("Critical!")
        
        self.error_handler.handle_error(critical_error)
        
        # Verify callback was called
        critical_callback.assert_called_once()


class TestErrorDecorators(unittest.TestCase):
    """Test error handling decorators"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_logger = Mock()
        self.error_handler = ErrorHandler(self.mock_logger)
    
    def test_with_error_handling_decorator(self):
        """Test @with_error_handling decorator"""
        
        class TestClass:
            def __init__(self):
                self.error_handler = self.error_handler
            
            @with_error_handling("Test", "operation", default_return="default")
            def failing_method(self):
                raise Exception("Intentional failure")
        
        # Set error_handler for test
        TestClass.error_handler = self.error_handler
        obj = TestClass()
        
        # Call should return default instead of raising
        result = obj.failing_method()
        self.assertEqual(result, "default")
    
    def test_retry_decorator_succeeds_on_retry(self):
        """Test @retry_on_error succeeds on retry"""
        
        call_count = [0]
        
        @retry_on_error(max_attempts=3, delay_seconds=0.01)
        def flaky_function():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Fail on first call")
            return "success"
        
        result = flaky_function()
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 2)  # Failed once, succeeded on retry
    
    def test_retry_decorator_fails_after_max_attempts(self):
        """Test @retry_on_error fails after max attempts"""
        
        @retry_on_error(max_attempts=3, delay_seconds=0.01)
        def always_fails():
            raise ValueError("Always fails")
        
        with self.assertRaises(ValueError):
            always_fails()


class TestSafeOperations(unittest.TestCase):
    """Test safe operations wrapper"""
    
    def setUp(self):
        """Set up test fixtures"""
        mock_logger = Mock()
        self.error_handler = ErrorHandler(mock_logger)
        self.safe_ops = SafeOperations(self.error_handler)
    
    def test_safe_json_parse_valid(self):
        """Test safe JSON parse with valid JSON"""
        result = self.safe_ops.safe_json_parse('{"key": "value"}')
        
        self.assertEqual(result, {"key": "value"})
    
    def test_safe_json_parse_invalid(self):
        """Test safe JSON parse with invalid JSON"""
        result = self.safe_ops.safe_json_parse('invalid json', default={"default": True})
        
        self.assertEqual(result, {"default": True})


# ============================================================================
# TEST MODEL BUSINESS LOGIC
# ============================================================================

class TestModelCalculations(unittest.TestCase):
    """Test Model business logic calculations"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock dependencies
        self.mock_db = Mock()
        self.mock_logger = Mock()
        self.error_handler = ErrorHandler(self.mock_logger)
        
        # Create test config
        self.config = {
            "TEMP_A_MIN": 240.0,
            "TEMP_A_MAX": 320.0,
            "TEMP_B_MIN": 200.0,
            "TEMP_B_MAX": 360.0,
            "GRAV_A_MIN": 0.80,
            "GRAV_A_MAX": 1.30,
            "GRAV_B_MIN": 0.50,
            "GRAV_B_MAX": 1.80,
            "DIST_A_MAX": 5000.0,
            "DIST_B_MAX": 15000.0,
            "WORTH_DIST_MAX": 8000.0,
            "WORTH_TEMP_MIN": 210.0,
            "WORTH_TEMP_MAX": 340.0,
            "WORTH_GRAV_MAX": 1.60,
            "COMMS_MAX_LINES": 150
        }
        
        # Import and create model
        from model_with_errors import Earth2ModelWithErrorHandling
        self.model = Earth2ModelWithErrorHandling(
            database=self.mock_db,
            config=self.config,
            error_handler=self.error_handler
        )
    
    def test_calculate_sol_distance(self):
        """Test Sol distance calculation"""
        # Test known distance: Sol to Alpha Centauri (approximate)
        distance = self.model.calculate_sol_distance(0, 0, 4.37)
        
        self.assertAlmostEqual(distance, 4.37, places=2)
    
    def test_calculate_sol_distance_invalid(self):
        """Test Sol distance with invalid coordinates"""
        # Should raise ValidationError for coordinates outside galaxy
        with self.assertRaises(ValidationError):
            self.model.calculate_sol_distance(200000, 0, 0)
    
    def test_calculate_gravity_g(self):
        """Test gravity conversion"""
        # Earth gravity: 9.80665 m/s²
        result = self.model.calculate_gravity_g(9.80665)
        
        self.assertAlmostEqual(result, 1.0, places=2)
    
    def test_calculate_gravity_g_negative(self):
        """Test gravity with negative value"""
        # Should raise ValidationError
        with self.assertRaises(ValidationError):
            self.model.calculate_gravity_g(-5.0)
    
    def test_kelvin_to_celsius(self):
        """Test temperature conversion"""
        # 273.15K = 0°C
        result = self.model.kelvin_to_celsius(273.15)
        
        self.assertAlmostEqual(result, 0.0, places=2)
    
    def test_kelvin_to_celsius_invalid(self):
        """Test temperature with negative Kelvin"""
        with self.assertRaises(ValidationError):
            self.model.kelvin_to_celsius(-10.0)
    
    def test_calculate_earth2_rating_a(self):
        """Test A rating calculation"""
        # Perfect Earth-like conditions
        rating = self.model.calculate_earth2_rating(
            temp_k=280.0,  # 6.85°C
            gravity_g=1.0,
            distance_ls=3000.0
        )
        
        self.assertEqual(rating, "A")
    
    def test_calculate_earth2_rating_b(self):
        """Test B rating calculation"""
        # Acceptable conditions
        rating = self.model.calculate_earth2_rating(
            temp_k=350.0,  # Hot but acceptable
            gravity_g=1.5,
            distance_ls=10000.0
        )
        
        self.assertEqual(rating, "B")
    
    def test_calculate_earth2_rating_c(self):
        """Test C rating calculation"""
        # Outside acceptable ranges
        rating = self.model.calculate_earth2_rating(
            temp_k=500.0,  # Too hot
            gravity_g=3.0,  # Too heavy
            distance_ls=20000.0  # Too far
        )
        
        self.assertEqual(rating, "C")
    
    def test_calculate_earth2_rating_missing_data(self):
        """Test rating with missing data"""
        rating = self.model.calculate_earth2_rating(
            temp_k=None,
            gravity_g=1.0,
            distance_ls=3000.0
        )
        
        self.assertEqual(rating, "C")
    
    def test_calculate_worth_landing_yes(self):
        """Test worth landing - yes"""
        worth, reason = self.model.calculate_worth_landing(
            temp_k=280.0,
            gravity_g=1.0,
            distance_ls=5000.0
        )
        
        self.assertEqual(worth, "Yes")
        self.assertIn("Good", reason)
    
    def test_calculate_worth_landing_too_far(self):
        """Test worth landing - too far"""
        worth, reason = self.model.calculate_worth_landing(
            temp_k=280.0,
            gravity_g=1.0,
            distance_ls=10000.0  # Too far
        )
        
        self.assertEqual(worth, "No")
        self.assertIn("far", reason.lower())
    
    def test_calculate_worth_landing_high_gravity(self):
        """Test worth landing - high gravity"""
        worth, reason = self.model.calculate_worth_landing(
            temp_k=280.0,
            gravity_g=2.0,  # Too heavy
            distance_ls=5000.0
        )
        
        self.assertEqual(worth, "No")
        self.assertIn("gravity", reason.lower())
    
    def test_generate_inara_link(self):
        """Test Inara link generation"""
        link = self.model.generate_inara_link("Sol")
        
        self.assertIn("inara.cz", link)
        self.assertIn("Sol", link)
    
    def test_generate_inara_link_with_spaces(self):
        """Test Inara link with spaces in name"""
        link = self.model.generate_inara_link("Alpha Centauri")
        
        self.assertIn("inara.cz", link)
        # Spaces should be URL encoded
        self.assertIn("Alpha", link)


class TestModelDatabaseOperations(unittest.TestCase):
    """Test Model database operations with mocking"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_logger = Mock()
        self.error_handler = ErrorHandler(self.mock_logger)
        
        self.config = {
            "TEMP_A_MIN": 240.0,
            "TEMP_A_MAX": 320.0,
            "TEMP_B_MIN": 200.0,
            "TEMP_B_MAX": 360.0,
            "GRAV_A_MIN": 0.80,
            "GRAV_A_MAX": 1.30,
            "GRAV_B_MIN": 0.50,
            "GRAV_B_MAX": 1.80,
            "DIST_A_MAX": 5000.0,
            "DIST_B_MAX": 15000.0,
            "WORTH_DIST_MAX": 8000.0,
            "WORTH_TEMP_MIN": 210.0,
            "WORTH_TEMP_MAX": 340.0,
            "WORTH_GRAV_MAX": 1.60,
            "COMMS_MAX_LINES": 150
        }
        
        from model_with_errors import Earth2ModelWithErrorHandling
        self.model = Earth2ModelWithErrorHandling(
            database=self.mock_db,
            config=self.config,
            error_handler=self.error_handler
        )
    
    def test_load_stats_from_db_success(self):
        """Test loading stats from database"""
        # Mock database response
        self.mock_db.get_cmdr_stats.return_value = {
            "total_all": 100,
            "total_elw": 50,
            "total_terraformable": 30
        }
        
        # Load stats
        self.model.load_stats_from_db("TestCMDR")
        
        # Verify database was called
        self.mock_db.get_cmdr_stats.assert_called_with("TestCMDR")
        
        # Verify stats were updated
        stats = self.model.get_stats()
        self.assertEqual(stats["total_all"], 100)
        self.assertEqual(stats["total_elw"], 50)
    
    def test_load_stats_from_db_failure(self):
        """Test loading stats handles database errors"""
        # Mock database to raise error
        self.mock_db.get_cmdr_stats.side_effect = Exception("DB error")
        
        # Should handle error gracefully
        self.model.load_stats_from_db("TestCMDR")
        
        # Error should be logged
        self.assertTrue(len(self.error_handler.error_history) > 0)
    
    def test_log_candidate_success(self):
        """Test logging candidate successfully"""
        # Mock database to return True (new candidate)
        self.mock_db.log_candidate.return_value = True
        
        candidate_data = {
            "star_system": "Test System",
            "body_name": "Test Body",
            "candidate_type": "ELW",
            "earth2_rating": "A"
        }
        
        # Log candidate
        result = self.model.log_candidate(candidate_data)
        
        # Verify success
        self.assertTrue(result)
        self.mock_db.log_candidate.assert_called_with(candidate_data)
        
        # Verify stats updated
        stats = self.model.get_stats()
        self.assertEqual(stats["total_all"], 1)
        self.assertEqual(stats["total_elw"], 1)
    
    def test_log_candidate_duplicate(self):
        """Test logging duplicate candidate"""
        # Mock database to return False (duplicate)
        self.mock_db.log_candidate.return_value = False
        
        candidate_data = {
            "star_system": "Test System",
            "body_name": "Test Body"
        }
        
        # Log candidate
        result = self.model.log_candidate(candidate_data)
        
        # Should return False
        self.assertFalse(result)
        
        # Stats should not update
        stats = self.model.get_stats()
        self.assertEqual(stats["total_all"], 0)
    
    def test_log_candidate_with_retry(self):
        """Test logging candidate retries on failure"""
        # Mock database to fail twice, then succeed
        self.mock_db.log_candidate.side_effect = [
            Exception("DB locked"),
            Exception("DB locked"),
            True  # Success on third attempt
        ]
        
        candidate_data = {
            "star_system": "Test System",
            "body_name": "Test Body",
            "candidate_type": "ELW",
            "earth2_rating": "A"
        }
        
        # Should succeed after retries
        result = self.model.log_candidate(candidate_data)
        
        self.assertTrue(result)
        # Verify it was called 3 times
        self.assertEqual(self.mock_db.log_candidate.call_count, 3)
    
    def test_start_session(self):
        """Test starting a new session"""
        # Mock database to return session ID
        self.mock_db.start_session.return_value = "session_123"
        
        # Start session
        session_id = self.model.start_session("TestCMDR", "Journal.log")
        
        # Verify session started
        self.assertEqual(session_id, "session_123")
        self.mock_db.start_session.assert_called_with("TestCMDR", "Journal.log")
        
        # Verify status updated
        status_session = self.model.get_status("session_id")
        self.assertEqual(status_session, "session_123")


# ============================================================================
# TEST THREAD SAFETY
# ============================================================================

class TestThreadSafety(unittest.TestCase):
    """Test thread-safe operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        mock_db = Mock()
        mock_logger = Mock()
        error_handler = ErrorHandler(mock_logger)
        
        config = {
            "COMMS_MAX_LINES": 150,
            "TEMP_A_MIN": 240.0,
            "TEMP_A_MAX": 320.0,
            "TEMP_B_MIN": 200.0,
            "TEMP_B_MAX": 360.0,
            "GRAV_A_MIN": 0.80,
            "GRAV_A_MAX": 1.30,
            "GRAV_B_MIN": 0.50,
            "GRAV_B_MAX": 1.80,
            "DIST_A_MAX": 5000.0,
            "DIST_B_MAX": 15000.0,
            "WORTH_DIST_MAX": 8000.0,
            "WORTH_TEMP_MIN": 210.0,
            "WORTH_TEMP_MAX": 340.0,
            "WORTH_GRAV_MAX": 1.60,
        }
        
        from model_with_errors import Earth2ModelWithErrorHandling
        self.model = Earth2ModelWithErrorHandling(
            database=mock_db,
            config=config,
            error_handler=error_handler
        )
    
    def test_concurrent_stat_updates(self):
        """Test concurrent stat updates are thread-safe"""
        import threading
        
        def increment_stats():
            for _ in range(100):
                self.model.increment_stat("total_all")
        
        # Create multiple threads
        threads = [threading.Thread(target=increment_stats) for _ in range(10)]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify count is correct (10 threads * 100 increments = 1000)
        stats = self.model.get_stats()
        self.assertEqual(stats["total_all"], 1000)
    
    def test_concurrent_comms_updates(self):
        """Test concurrent COMMS updates are thread-safe"""
        import threading
        
        def add_messages():
            for i in range(50):
                self.model.add_comms_message(f"Message {i}")
        
        # Create multiple threads
        threads = [threading.Thread(target=add_messages) for _ in range(3)]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify messages were added (may be capped at COMMS_MAX_LINES)
        messages = self.model.get_comms_messages()
        self.assertGreater(len(messages), 0)
        self.assertLessEqual(len(messages), 150)


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
