"""
Configuration File Loader
==========================

Load configuration from external YAML or JSON files.

Benefits:
- No code changes for config updates
- Easy deployment to different environments
- User-customizable settings
- Version-controlled configuration
"""

# ============================================================================
# MODULE OVERVIEW
# ============================================================================
# Purpose:
#   config_loader.py
#
# Connected modules (direct imports):
#   dependency_injection, error_handling
#
# Notes:
#   - This file is part of the Logger Beta build.
#   - Section dividers below are comments only (no logic changes).
# ============================================================================

import yaml
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import asdict

from dependency_injection import (
    AppConfig,
    PathConfig,
    RatingConfig,
    MonitoringConfig,
    UIConfig
)
from error_handling import ConfigurationError


# ============================================================================
# CLASSES
# ============================================================================

class ConfigLoader:
    """Load and validate configuration from files"""
    
    SUPPORTED_FORMATS = {'.yaml', '.yml', '.json'}
    
    @classmethod
    def load_from_file(cls, filepath: Path) -> AppConfig:
        """
        Load configuration from file
        
        Args:
            filepath: Path to config file (.yaml, .yml, or .json)
            
        Returns:
            AppConfig instance
            
        Raises:
            ConfigurationError: If file not found or invalid
        """
        filepath = Path(filepath)
        
        # Check file exists
        if not filepath.exists():
            raise ConfigurationError(
                f"Configuration file not found: {filepath}",
                context={"filepath": str(filepath)}
            )
        
        # Check file extension
        if filepath.suffix not in cls.SUPPORTED_FORMATS:
            raise ConfigurationError(
                f"Unsupported config format: {filepath.suffix}. "
                f"Supported: {', '.join(cls.SUPPORTED_FORMATS)}",
                context={"filepath": str(filepath), "suffix": filepath.suffix}
            )
        
        # Load file
        try:
            with filepath.open('r', encoding='utf-8') as f:
                if filepath.suffix == '.json':
                    data = json.load(f)
                else:  # YAML
                    data = yaml.safe_load(f)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to parse config file: {e}",
                context={"filepath": str(filepath), "error": str(e)}
            )
        
        # Convert to AppConfig
        return cls._dict_to_config(data)
    
    @classmethod
    def _dict_to_config(cls, data: Dict[str, Any]) -> AppConfig:
        """Convert dictionary to AppConfig"""
        try:
            # Extract sections
            app_section = data.get('application', {})
            paths_section = data.get('paths', {})
            rating_section = data.get('rating', {})
            monitoring_section = data.get('monitoring', {})
            ui_section = data.get('ui', {})
            
            # Create PathConfig
            paths = PathConfig(
                user_profile=Path(paths_section.get('user_profile', Path.home())),
                journal_dir=Path(paths_section.get('journal_dir', '')),
                output_dir=Path(paths_section.get('output_dir', '')),
                db_path=Path(paths_section.get('db_path', '')),
                csv_path=Path(paths_section.get('csv_path', '')),
                log_path=Path(paths_section.get('log_path', '')),
                asset_path=Path(paths_section.get('asset_path', '')),
                icon_name=paths_section.get('icon_name', 'earth2.ico')
            )
            
            # Create RatingConfig
            rating = RatingConfig(
                temp_a_min=rating_section.get('temp_a_min', 240.0),
                temp_a_max=rating_section.get('temp_a_max', 320.0),
                temp_b_min=rating_section.get('temp_b_min', 200.0),
                temp_b_max=rating_section.get('temp_b_max', 360.0),
                grav_a_min=rating_section.get('grav_a_min', 0.80),
                grav_a_max=rating_section.get('grav_a_max', 1.30),
                grav_b_min=rating_section.get('grav_b_min', 0.50),
                grav_b_max=rating_section.get('grav_b_max', 1.80),
                dist_a_max=rating_section.get('dist_a_max', 5000.0),
                dist_b_max=rating_section.get('dist_b_max', 15000.0),
                worth_dist_max=rating_section.get('worth_dist_max', 8000.0),
                worth_temp_min=rating_section.get('worth_temp_min', 210.0),
                worth_temp_max=rating_section.get('worth_temp_max', 340.0),
                worth_grav_max=rating_section.get('worth_grav_max', 1.60)
            )
            
            # Create MonitoringConfig
            monitoring = MonitoringConfig(
                poll_fast_seconds=monitoring_section.get('poll_fast_seconds', 0.1),
                poll_slow_seconds=monitoring_section.get('poll_slow_seconds', 0.25),
                journal_seed_max_bytes=monitoring_section.get('journal_seed_max_bytes', 2_000_000),
                test_mode=monitoring_section.get('test_mode', False),
                test_read_from_start=monitoring_section.get('test_read_from_start', True)
            )
            
            # Create UIConfig
            ui = UIConfig(
                refresh_fast_ms=ui_section.get('refresh_fast_ms', 100),
                refresh_slow_ms=ui_section.get('refresh_slow_ms', 250),
                comms_max_lines=ui_section.get('comms_max_lines', 150),
                bg=ui_section.get('bg', '#0a0a0f'),
                bg_panel=ui_section.get('bg_panel', '#12121a'),
                bg_field=ui_section.get('bg_field', '#1a1a28'),
                text=ui_section.get('text', '#e0e0ff'),
                muted=ui_section.get('muted', '#6a6a8a'),
                border_outer=ui_section.get('border_outer', '#2a2a3f'),
                border_inner=ui_section.get('border_inner', '#1f1f2f'),
                orange=ui_section.get('orange', '#ff8833'),
                orange_dim=ui_section.get('orange_dim', '#cc6622'),
                green=ui_section.get('green', '#44ff88'),
                red=ui_section.get('red', '#ff4444'),
                led_active=ui_section.get('led_active', '#00ff88'),
                led_idle=ui_section.get('led_idle', '#888888')
            )
            
            # Create AppConfig
            return AppConfig(
                app_name=app_section.get('name', 'DW3 Earth2 Logger'),
                version=app_section.get('version', '2.2.0'),
                paths=paths,
                rating=rating,
                monitoring=monitoring,
                ui=ui
            )
            
        except Exception as e:
            raise ConfigurationError(
                f"Failed to convert config data: {e}",
                context={"error": str(e)}
            )
    
    @classmethod
    def save_to_file(cls, config: AppConfig, filepath: Path):
        """
        Save configuration to file
        
        Args:
            config: AppConfig to save
            filepath: Path to save to (.yaml or .json)
        """
        filepath = Path(filepath)
        
        # Convert config to dict
        data = cls._config_to_dict(config)
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        try:
            with filepath.open('w', encoding='utf-8') as f:
                if filepath.suffix == '.json':
                    json.dump(data, f, indent=2)
                else:  # YAML
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to save config file: {e}",
                context={"filepath": str(filepath), "error": str(e)}
            )
    
    @classmethod
    def _config_to_dict(cls, config: AppConfig) -> Dict[str, Any]:
        """Convert AppConfig to dictionary"""
        return {
            'application': {
                'name': config.app_name,
                'version': config.version
            },
            'paths': {
                'user_profile': str(config.paths.user_profile),
                'journal_dir': str(config.paths.journal_dir),
                'output_dir': str(config.paths.output_dir),
                'db_path': str(config.paths.db_path),
                'csv_path': str(config.paths.csv_path),
                'log_path': str(config.paths.log_path),
                'asset_path': str(config.paths.asset_path),
                'icon_name': config.paths.icon_name
            },
            'rating': {
                'temp_a_min': config.rating.temp_a_min,
                'temp_a_max': config.rating.temp_a_max,
                'temp_b_min': config.rating.temp_b_min,
                'temp_b_max': config.rating.temp_b_max,
                'grav_a_min': config.rating.grav_a_min,
                'grav_a_max': config.rating.grav_a_max,
                'grav_b_min': config.rating.grav_b_min,
                'grav_b_max': config.rating.grav_b_max,
                'dist_a_max': config.rating.dist_a_max,
                'dist_b_max': config.rating.dist_b_max,
                'worth_dist_max': config.rating.worth_dist_max,
                'worth_temp_min': config.rating.worth_temp_min,
                'worth_temp_max': config.rating.worth_temp_max,
                'worth_grav_max': config.rating.worth_grav_max
            },
            'monitoring': {
                'poll_fast_seconds': config.monitoring.poll_fast_seconds,
                'poll_slow_seconds': config.monitoring.poll_slow_seconds,
                'journal_seed_max_bytes': config.monitoring.journal_seed_max_bytes,
                'test_mode': config.monitoring.test_mode,
                'test_read_from_start': config.monitoring.test_read_from_start
            },
            'ui': {
                'refresh_fast_ms': config.ui.refresh_fast_ms,
                'refresh_slow_ms': config.ui.refresh_slow_ms,
                'comms_max_lines': config.ui.comms_max_lines,
                'bg': config.ui.bg,
                'bg_panel': config.ui.bg_panel,
                'bg_field': config.ui.bg_field,
                'text': config.ui.text,
                'muted': config.ui.muted,
                'border_outer': config.ui.border_outer,
                'border_inner': config.ui.border_inner,
                'orange': config.ui.orange,
                'orange_dim': config.ui.orange_dim,
                'green': config.ui.green,
                'red': config.ui.red,
                'led_active': config.ui.led_active,
                'led_idle': config.ui.led_idle
            }
        }
    
    @classmethod
    def find_config_file(cls, search_paths: list[Path]) -> Optional[Path]:
        """
        Search for config file in multiple locations
        
        Args:
            search_paths: List of paths to search
            
        Returns:
            Path to first config file found, or None
        """
        for search_path in search_paths:
            for ext in cls.SUPPORTED_FORMATS:
                config_file = search_path / f"config{ext}"
                if config_file.exists():
                    return config_file
        
        return None
    
    @classmethod
    def create_default_config_file(cls, filepath: Path):
        """
        Create a default configuration file
        
        Args:
            filepath: Where to create the file
        """
        # Create default config
        config = AppConfig.create_default()
        
        # Save to file
        cls.save_to_file(config, filepath)


class ConfigValidator:
    """Validate configuration values"""
    
    @staticmethod
    def validate(config: AppConfig) -> list[str]:
        """
        Validate configuration
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate rating ranges
        if config.rating.temp_a_min >= config.rating.temp_a_max:
            errors.append("temp_a_min must be less than temp_a_max")
        
        if config.rating.temp_b_min >= config.rating.temp_b_max:
            errors.append("temp_b_min must be less than temp_b_max")
        
        if config.rating.grav_a_min >= config.rating.grav_a_max:
            errors.append("grav_a_min must be less than grav_a_max")
        
        if config.rating.grav_b_min >= config.rating.grav_b_max:
            errors.append("grav_b_min must be less than grav_b_max")
        
        # Validate positive values
        if config.rating.dist_a_max <= 0:
            errors.append("dist_a_max must be positive")
        
        if config.rating.dist_b_max <= 0:
            errors.append("dist_b_max must be positive")
        
        # Validate monitoring settings
        if config.monitoring.poll_fast_seconds <= 0:
            errors.append("poll_fast_seconds must be positive")
        
        if config.monitoring.poll_slow_seconds <= 0:
            errors.append("poll_slow_seconds must be positive")
        
        # Validate UI settings
        if config.ui.refresh_fast_ms <= 0:
            errors.append("refresh_fast_ms must be positive")
        
        if config.ui.refresh_slow_ms <= 0:
            errors.append("refresh_slow_ms must be positive")
        
        if config.ui.comms_max_lines <= 0:
            errors.append("comms_max_lines must be positive")
        
        return errors
