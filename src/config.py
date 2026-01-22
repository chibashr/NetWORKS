#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration manager for NetWORKS
"""

import os
import json
import yaml
from loguru import logger  # Keep this for type hints and as a fallback
from PySide6.QtCore import QObject, Signal


class Config(QObject):
    """Configuration manager for NetWORKS"""
    
    config_changed = Signal()
    
    def __init__(self, app=None):
        """Initialize the configuration manager
        
        Args:
            app: Application instance to use its logger. If None, uses global logger.
        """
        super().__init__()
        
        # Use application logger if available, otherwise fallback to global logger
        self.logger = getattr(app, 'logger', logger) if app else logger
        self.logger.debug("Initializing configuration manager")
        
        # Set default config paths
        self.config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
        self.user_config_path = os.path.join(self.config_dir, "user.yaml")
        self.plugins_config_path = os.path.join(self.config_dir, "plugins.yaml")
        self.default_config_path = os.path.join(self.config_dir, "default.yaml")
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Default configuration
        self.default_config = {
            "application": {
                "theme": "light",
                "plugins_enabled": True,
                "logs_level": "INFO",
                "plugins_directory": os.path.abspath(os.path.join(os.path.dirname(__file__), "plugins")),
                "external_plugins_directory": os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")),
                "auto_install_plugin_requirements": True,
                "auto_enable_discovered_plugins": True
            },
            "ui": {
                "theme": "light",
                "accent_color": "#E87722",
                "font_size": 10,
                "row_height": 22,
                "toolbar_position": "top",
                "show_statusbar": True,
                "device_table": {
                    "default_columns": ["name", "ip", "status"]
                }
            },
            "devices": {
                "auto_discover": True,
                "refresh_interval": 60  # seconds
            },
            "logging": {
                "level": "INFO",
                "retention_days": 7,
                "file_rotation_size": "10 MB",
                "diagnose": True,
                "backtrace": True
            }
        }
        
        # Plugins configuration
        self.plugins_config = {}
        
        # User configuration (will override defaults)
        self.user_config = {}
        
        # Combined configuration
        self.config = {}
        
    def load(self):
        """Load configuration from files"""
        self.logger.debug("Loading configuration")
        
        # Create default configuration file if it doesn't exist
        if not os.path.exists(self.default_config_path):
            self.logger.debug("Creating default configuration file")
            self._save_yaml(self.default_config_path, self.default_config)
        
        # Load default configuration
        self.default_config = self._load_yaml(self.default_config_path)
        
        # Load plugins configuration if it exists
        if os.path.exists(self.plugins_config_path):
            self.plugins_config = self._load_yaml(self.plugins_config_path)
        else:
            self.logger.debug("Plugins configuration file not found")
            self.plugins_config = {}
            
        # Load user configuration if it exists
        if os.path.exists(self.user_config_path):
            self.user_config = self._load_yaml(self.user_config_path)
        else:
            self.logger.debug("User configuration file not found")
            self.user_config = {}
            
        # Merge configurations (user config overrides plugins, which override defaults)
        self.config = self._merge_dicts(self.default_config, self.plugins_config)
        self.config = self._merge_dicts(self.config, self.user_config)
        
        self.logger.info("Configuration loaded successfully")
    
    def save(self):
        """Save user configuration to file"""
        self.logger.debug("Saving user configuration")
        self._save_yaml(self.user_config_path, self.user_config)
        self.config_changed.emit()
        
    def get(self, key, default=None):
        """Get a configuration value by key"""
        # Support hierarchical keys like "ui.theme"
        if '.' in key:
            keys = key.split('.')
            value = self.config
            for k in keys:
                if k in value:
                    value = value[k]
                else:
                    return default
            return value
        
        return self.config.get(key, default)
        
    def set(self, key, value):
        """Set a configuration value by key"""
        self.logger.debug(f"Setting configuration: {key} = {value}")
        
        # Support hierarchical keys like "ui.theme"
        if '.' in key:
            keys = key.split('.')
            target = self.user_config
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
        else:
            self.user_config[key] = value
            
        # Update combined configuration
        self.config = self._merge_dicts(self.default_config, self.plugins_config)
        self.config = self._merge_dicts(self.config, self.user_config)
        
        # Save the changes
        self.save()
        
    def update_plugin_config(self, plugin_id, config):
        """Update configuration for a plugin"""
        self.logger.debug(f"Updating plugin configuration: {plugin_id}")
        
        if 'plugins' not in self.plugins_config:
            self.plugins_config['plugins'] = {}
            
        self.plugins_config['plugins'][plugin_id] = config
        self._save_yaml(self.plugins_config_path, self.plugins_config)
        
        # Update combined configuration
        self.config = self._merge_dicts(self.default_config, self.plugins_config)
        self.config = self._merge_dicts(self.config, self.user_config)
        
        self.config_changed.emit()
        
    def get_plugin_config(self, plugin_id):
        """Get configuration for a plugin"""
        if 'plugins' in self.plugins_config and plugin_id in self.plugins_config['plugins']:
            return self.plugins_config['plugins'][plugin_id]
        return {}
        
    def is_first_run(self):
        """Check if this is the first time the application is run"""
        # If user config file doesn't exist, it's probably the first run
        if not os.path.exists(self.user_config_path):
            return True
            
        # Alternatively, check for a specific flag in the config
        return self.get('application.first_run', True)
        
    def mark_as_run(self):
        """Mark the application as having been run at least once"""
        self.set('application.first_run', False)
        self.save()
        
    def _load_yaml(self, path):
        """Load YAML configuration from a file"""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"Error loading configuration from {path}: {e}")
        return {}
        
    def _save_yaml(self, path, data):
        """Save YAML configuration to a file"""
        try:
            with open(path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"Error saving configuration to {path}: {e}")
            
    def _merge_dicts(self, dict1, dict2):
        """Recursively merge two dictionaries"""
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
                
        return result 