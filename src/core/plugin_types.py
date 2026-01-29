#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin state enum and PluginInfo model for NetWORKS.

Extracted from plugin_manager to keep types separate from manager logic.
"""

import gc
from enum import Enum, auto

from loguru import logger


class PluginState(Enum):
    """Enum representing possible plugin states"""

    DISCOVERED = auto()  # Plugin is discovered, not loaded (can be loaded)
    LOADED = auto()  # Plugin is loaded and active
    DISABLED = auto()  # Plugin is explicitly disabled (user chose Disable)
    ERROR = auto()  # Plugin has an error

    @staticmethod
    def from_enabled_loaded(enabled, loaded):
        """Create a PluginState from legacy enabled/loaded flags (e.g. registry)."""
        if not enabled:
            return PluginState.DISABLED
        elif loaded:
            return PluginState.LOADED
        else:
            return PluginState.DISCOVERED

    @property
    def is_enabled(self):
        """True if plugin is not disabled (DISCOVERED or LOADED). Kept for compatibility."""
        return self in (PluginState.DISCOVERED, PluginState.LOADED)

    @property
    def is_loaded(self):
        """Check if the state represents a loaded plugin"""
        return self == PluginState.LOADED

    @property
    def is_disabled(self):
        """Check if the state represents a disabled plugin"""
        return self == PluginState.DISABLED

    @staticmethod
    def validate_transition(current_state, target_state):
        """
        Validate if a state transition is allowed

        Args:
            current_state: The current PluginState
            target_state: The desired target PluginState

        Returns:
            bool: True if the transition is valid, False otherwise
        """
        # Valid transitions: DISCOVERED <-> LOADED (load/unload), -> DISABLED;
        # LOADED -> DISCOVERED (unload), DISABLED; DISABLED -> LOADED. Any -> ERROR.
        if target_state == PluginState.ERROR:
            return True
        allowed_transitions = {
            PluginState.DISCOVERED: [PluginState.LOADED, PluginState.DISABLED],
            PluginState.LOADED: [PluginState.DISCOVERED, PluginState.DISABLED],
            PluginState.DISABLED: [PluginState.LOADED],
            PluginState.ERROR: [PluginState.LOADED, PluginState.DISABLED],
        }

        # State can always transition to itself
        if current_state == target_state:
            return True

        # Check if the transition is allowed
        return target_state in allowed_transitions.get(current_state, [])


class PluginInfo:
    """Information about a plugin"""

    def __init__(self, id, name, version, description, author, entry_point, path=None):
        """Initialize plugin info"""
        self.id = id
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.entry_point = entry_point
        self.path = path
        self.icon_path = None
        self._state = PluginState.DISCOVERED
        self.instance = None

        # Optional fields
        self.min_app_version = None
        self.max_app_version = None
        self.dependencies = []
        self.requirements = {"python": [], "system": []}
        self.changelog = []

        # State fields
        self.error = None
        self.missing_docs = False

        # Validation fields
        self.validation_result = None  # Dict with validation results
        self.last_validated = None  # Timestamp of last validation
        self.validation_errors = []  # List of validation error messages
        self.validation_warnings = []  # List of validation warning messages

        # UI components registered by this plugin
        self.registered_components = {
            "menu_items": [],
            "toolbar_actions": [],
            "dock_widgets": [],
            "settings": {},
            "device_panels": [],
            "signal_connections": [],
        }

    @property
    def state(self):
        """Get the current state of the plugin"""
        return self._state

    @state.setter
    def state(self, value):
        """Set the state of the plugin"""
        if not isinstance(value, PluginState):
            raise TypeError("Expected PluginState value")

        # Previous state for logging
        previous_state = self._state

        # Always clear the instance when transitioning to DISABLED or ERROR state
        if value in (PluginState.DISABLED, PluginState.ERROR) and self.instance is not None:
            logger.debug(
                f"Clearing instance for plugin {self.id} during transition to {value.name}"
            )

            # Call cleanup if possible
            if hasattr(self.instance, "cleanup") and callable(self.instance.cleanup):
                try:
                    logger.debug(
                        f"Calling cleanup for plugin {self.id} during state transition"
                    )
                    self.instance.cleanup()
                except Exception as e:
                    logger.error(f"Error during cleanup in state transition: {e}")

            # Force clear instance
            self.instance = None

            # Force garbage collection
            gc.collect()

        # Set the new state
        self._state = value

        # Log the transition
        if previous_state != self._state:
            logger.debug(
                f"Plugin {self.id} state transition: {previous_state.name} -> {self._state.name}"
            )

            # If transitioning to DISABLED, enforce instance is None
            if self._state == PluginState.DISABLED and self.instance is not None:
                logger.warning(
                    f"Plugin {self.id} instance still exists after transition to DISABLED - forcing clear"
                )
                self.instance = None

                # Run garbage collection again
                gc.collect()

    @property
    def enabled(self):
        """Check if the plugin is enabled"""
        return self.state.is_enabled

    @enabled.setter
    def enabled(self, value):
        """Set the enabled status of the plugin"""
        current_state = self.state

        if value and self.state == PluginState.DISABLED:
            self.state = PluginState.DISCOVERED
            logger.debug(f"Plugin {self.id} set to DISCOVERED via enabled setter")
        elif not value and self.state != PluginState.DISABLED:
            # Disabling an enabled or loaded plugin

            # If loaded and has an instance, perform cleanup
            if self.instance is not None:
                if hasattr(self.instance, "cleanup") and callable(self.instance.cleanup):
                    try:
                        logger.debug(
                            f"Calling cleanup for plugin {self.id} via enabled setter"
                        )
                        self.instance.cleanup()
                    except Exception as e:
                        logger.error(f"Error cleaning up plugin {self.id}: {e}")

                # Always clear the instance when disabling
                logger.debug(f"Clearing instance for plugin {self.id} via enabled setter")
                self.instance = None

            # Set to disabled state
            self.state = PluginState.DISABLED
            logger.debug(f"Plugin {self.id} disabled via enabled setter")

    @property
    def loaded(self):
        """Check if the plugin is loaded"""
        return self.state.is_loaded

    @loaded.setter
    def loaded(self, value):
        """Set the loaded status of the plugin"""
        if value and self.is_enabled:
            self._state = PluginState.LOADED
        elif not value and self.state == PluginState.LOADED:
            self._state = PluginState.DISCOVERED

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry_point": self.entry_point,
            "path": self.path,
            "enabled": self.enabled,
            "loaded": self.loaded,
            "state": self.state.name,
        }

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        plugin_info = cls(
            data["id"],
            data["name"],
            data["version"],
            data.get("description", ""),
            data.get("author", ""),
            data["entry_point"],
            data.get("path"),
        )
        # Handle state (legacy "ENABLED" mapped to DISCOVERED)
        state_name = data.get("state")
        if state_name == "ENABLED":
            state_name = "DISCOVERED"
        if state_name and state_name in PluginState.__members__:
            plugin_info._state = PluginState[state_name]
        else:
            # Backward compatibility with old registry format
            enabled = data.get("enabled", True)
            loaded = data.get("loaded", False)
            plugin_info._state = PluginState.from_enabled_loaded(enabled, loaded)

        return plugin_info

    def __str__(self):
        """String representation"""
        return f"{self.name} v{self.version} ({self.id}, {self.state.name})"
