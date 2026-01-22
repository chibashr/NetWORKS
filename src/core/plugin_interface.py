#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin interface for NetWORKS
"""

from abc import ABC, abstractmethod
from loguru import logger
from PySide6.QtCore import QObject, Signal
import six

# Create a metaclass that resolves the conflict between QObject and ABC metaclasses
ABCQObjectMeta = type('ABCQObjectMeta', (type(QObject), type(ABC)), {})

class PluginInterface(six.with_metaclass(ABCQObjectMeta, QObject, ABC)):
    """
    Base interface that all plugins must implement.
    Provides methods for initializing, running, and cleaning up plugins.
    """
    
    # Signals that plugins can emit
    plugin_initialized = Signal()
    plugin_starting = Signal()
    plugin_running = Signal()
    plugin_stopping = Signal()
    plugin_cleaned_up = Signal()
    plugin_error = Signal(str)
    
    def __init__(self):
        """Initialize the plugin interface"""
        super().__init__()
        
        # These will be set in the initialize method
        self.app = None
        self.device_manager = None
        self.main_window = None
        self.config = None
        self.plugin_info = None
        
        # Track initialization state
        self._initialized = False
        self._running = False
        
    @property
    def plugin_manager(self):
        """Get the plugin manager"""
        if self.app:
            return self.app.plugin_manager
        return None
        
    def show_device_properties_dialog(self, device=None):
        """
        Show the device properties dialog for an existing device or to create a new one.
        
        Args:
            device: The device to edit, or None to create a new device
            
        Returns:
            The modified or new device if accepted, None if cancelled
        """
        if not self.main_window:
            logger.error("Main window not available")
            return None
            
        # Find the device table view
        from ..ui.device_table import DeviceTableView
        device_table = self.main_window.findChild(DeviceTableView)
        
        if device_table:
            return device_table.device_properties_dialog(device)
        else:
            logger.error("Device table not found")
            return None
    
    def add_device_dialog(self):
        """
        Show a dialog to add a new device
        
        Returns:
            The new device if added, None if cancelled
        """
        if not self.main_window:
            logger.error("Main window not available")
            return None
            
        # Find the device table view
        from ..ui.device_table import DeviceTableView
        device_table = self.main_window.findChild(DeviceTableView)
        
        if device_table:
            new_device = device_table.device_properties_dialog(None)
            if new_device:
                self.device_manager.add_device(new_device)
                return new_device
        else:
            logger.error("Device table not found")
        
        return None
        
    @abstractmethod
    def initialize(self, app, plugin_info):
        """
        Initialize the plugin. This is called when the plugin is loaded.
        
        Args:
            app: The application instance
            plugin_info: The PluginInfo object for this plugin
            
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        pass
        
    def start(self):
        """
        Start the plugin. Called when the plugin should start its operation.
        
        This method should:
        - Start any background threads or processes
        - Begin any active operations
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if not self._initialized:
            logger.warning(f"Cannot start plugin {self.__class__.__name__}: not initialized")
            return False
            
        if self._running:
            logger.debug(f"Plugin {self.__class__.__name__} already running")
            return True
            
        self.plugin_starting.emit()
        self._running = True
        self.plugin_running.emit()
        return True
        
    def stop(self):
        """
        Stop the plugin. Called when the plugin should stop its operation.
        
        This method should:
        - Stop any background threads or processes
        - End any active operations
        
        It should NOT clean up resources or disconnect signals.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self._running:
            logger.debug(f"Plugin {self.__class__.__name__} not running")
            return True
            
        self.plugin_stopping.emit()
        self._running = False
        return True
        
    def cleanup(self):
        """
        Clean up the plugin. Called when the plugin is unloaded.
        
        This method should:
        - Release any resources
        - Disconnect any signals
        - Unregister any UI components
        - Unregister any device types
        
        Returns:
            bool: True if cleaned up successfully, False otherwise
        """
        if self._running:
            logger.debug(f"Plugin {self.__class__.__name__} still running, stopping first")
            self.stop()
            
        self._initialized = False
        self.plugin_cleaned_up.emit()
        return True
        
    def get_toolbar_actions(self):
        """
        Get actions to be added to the toolbar
        
        Returns:
            list: List of QAction objects
        
        Notes:
            Actions may set `toolbar_priority` (int) to influence overflow order.
            Higher values stay visible longer when the toolbar is crowded.
        """
        return []
        
    def get_menu_actions(self):
        """
        Get actions to be added to the menu
        
        Returns:
            dict: Dictionary mapping menu names to lists of QAction objects
        """
        return {}
        
    def get_device_panels(self):
        """
        Get panels to be added to the device view
        
        Returns:
            list: List of (panel_name, widget) tuples
        """
        return []
        
    def get_device_table_columns(self):
        """
        Get columns to be added to the device table
        
        Returns:
            list: List of (column_id, column_name, callback) tuples
                 where callback is a function that takes a device and returns the value
        """
        return []
        
    def get_device_context_menu_actions(self):
        """
        Get actions to be added to the device context menu
        
        Returns:
            list: List of QAction objects
        """
        return []
        
    def get_device_tabs(self):
        """
        Get tabs to be added to the device details view
        
        Returns:
            list: List of (tab_name, widget) tuples
        """
        return []
        
    def get_dock_widgets(self):
        """
        Get dock widgets to be added to the main window
        
        Returns:
            list: List of (widget_name, widget, area) tuples where area is a Qt.DockWidgetArea
        """
        return []
        
    def get_settings(self):
        """
        Get plugin settings to be displayed in the plugin manager dialog
        
        Returns:
            dict: Dictionary of setting objects with the following structure:
            {
                "setting_id": {
                    "name": "Human-readable name",
                    "description": "Setting description",
                    "type": "string|int|float|bool|choice",
                    "default": default_value,
                    "value": current_value,
                    "choices": ["choice1", "choice2"] # Only for type "choice"
                }
            }
        """
        return {}

    def update_setting(self, setting_id, value):
        """
        Update a plugin setting value
        
        Args:
            setting_id: The ID of the setting to update
            value: The new value for the setting
            
        Returns:
            bool: True if the setting was updated successfully, False otherwise
        """
        return False
        
    def get_setting_value(self, setting_id):
        """
        Get the current value of a plugin setting
        
        Args:
            setting_id: The ID of the setting to get
            
        Returns:
            The current value of the setting, or None if the setting does not exist
        """
        settings = self.get_settings()
        if settings and setting_id in settings:
            return settings[setting_id].get("value")
        return None
        
    def get_settings_pages(self):
        """
        Get settings pages to be added to the settings dialog
        
        Returns:
            list: List of (page_name, widget) tuples
        """
        return []
        
    def on_device_added(self, device):
        """
        Called when a device is added
        
        Args:
            device: The device that was added
        """
        pass
        
    def on_device_removed(self, device):
        """
        Called when a device is removed
        
        Args:
            device: The device that was removed
        """
        pass
        
    def on_device_changed(self, device):
        """
        Called when a device is changed
        
        Args:
            device: The device that was changed
        """
        pass
        
    def on_device_selected(self, devices):
        """
        Called when devices are selected
        
        Args:
            devices: List of selected devices
        """
        pass
        
    def on_group_added(self, group):
        """
        Called when a group is added
        
        Args:
            group: The group that was added
        """
        pass
        
    def on_group_removed(self, group):
        """
        Called when a group is removed
        
        Args:
            group: The group that was removed
        """
        pass
        
    def on_plugin_loaded(self, plugin_info):
        """
        Called when a plugin is loaded
        
        Args:
            plugin_info: Information about the plugin that was loaded
        """
        pass
        
    def on_plugin_unloaded(self, plugin_info):
        """
        Called when a plugin is unloaded
        
        Args:
            plugin_info: Information about the plugin that was unloaded
        """
        pass
        
    def __str__(self):
        """String representation of the plugin"""
        return f"{self.__class__.__name__} ({'initialized' if self._initialized else 'not initialized'}, {'running' if self._running else 'not running'})" 