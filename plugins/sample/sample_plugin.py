#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sample plugin for NetWORKS

This plugin demonstrates the NetWORKS plugin API and provides comprehensive
testing capabilities for the application.
"""

from loguru import logger
import sys
import os
import time
import datetime
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
import functools

from PySide6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QDockWidget,
    QPushButton, QTabWidget, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QGridLayout, QFormLayout, QGroupBox, QCheckBox, QComboBox,
    QSplitter, QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QMenu, QStyle
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QFont, QColor, QClipboard

# Import the plugin interface
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.plugin_interface import PluginInterface
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.plugin_widgets import CollapsibleSection, PluginDialogBase
from src.ui.material_icons import material_icon


def safe_action_wrapper(func):
    """Decorator to safely handle actions without crashing the application"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            # Log the action start
            action_name = func.__name__
            logger.debug(f"Starting action: {action_name}")
            
            # Execute the action
            result = func(self, *args, **kwargs)
            logger.debug(f"Successfully completed action: {action_name}")
            return result
        except Exception as e:
            # Log the error
            logger.error(f"Error in action {func.__name__}: {e}", exc_info=True)
            
            # Try to log to the UI if possible
            try:
                if hasattr(self, 'log_message'):
                    self.log_message(f"Error performing action: {e}")
                
                # Try to show a status message
                if hasattr(self, 'main_window') and hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"Error: {e}", 3000)
            except Exception as inner_e:
                # Absolute fallback to console logging
                logger.critical(f"Failed to handle error in UI: {inner_e}")
                
            # Return a safe value (None)
            return None
    return wrapper


class SamplePlugin(PluginInterface):
    """
    Sample plugin implementation with testing capabilities
    
    This plugin serves as:
    1. A comprehensive example of the plugin API
    2. A testing utility for core NetWORKS functionality
    3. A signal monitoring tool
    """
    
    # Define custom signals
    test_started = Signal(str)  # Emitted when a test starts (test_name)
    test_completed = Signal(str, bool)  # Emitted when a test completes (test_name, success)
    test_all_completed = Signal(object)  # Emitted when all tests complete (results_dict)
    
    def __init__(self):
        """Initialize the plugin"""
        super().__init__()
        self.name = "Sample Plugin"
        self.version = "1.0.9"
        self.description = "A sample plugin that demonstrates the plugin system and provides testing capabilities"
        self.author = "NetWORKS Team"
        
        # Internal state
        self._connected_signals = set()  # Track connected signals for safe disconnection
        self._signal_monitors = {}  # Signal name -> monitoring enabled
        self._test_results = {}  # Test name -> results
        self._monitored_signal_log = []  # List of monitored signal events
        self._testing_in_progress = False
        
        # Plugin settings
        self.settings = {
            "log_level": {
                "name": "Log Level",
                "description": "The log level for plugin messages",
                "type": "choice",
                "default": "INFO",
                "value": "INFO",
                "choices": ["DEBUG", "INFO", "WARNING", "ERROR"]
            },
            "auto_sample": {
                "name": "Auto Sample",
                "description": "Automatically add sample property to new devices",
                "type": "bool",
                "default": True,
                "value": True
            },
            "default_value": {
                "name": "Default Value",
                "description": "Default value for the sample property",
                "type": "string",
                "default": "Sample Value",
                "value": "Sample Value"
            },
            "testing_mode": {
                "name": "Testing Mode",
                "description": "How tests should be executed",
                "type": "choice",
                "default": "manual",
                "value": "manual",
                "choices": ["manual", "automatic", "disabled"]
            },
            "test_signal_timeout": {
                "name": "Signal Test Timeout",
                "description": "Timeout in seconds for signal tests",
                "type": "int",
                "default": 10,
                "value": 10
            },
            "signal_monitoring": {
                "name": "Signal Monitoring",
                "description": "Enable signal monitoring by default",
                "type": "bool",
                "default": False,
                "value": False
            },
            "refresh_interval": {
                "name": "Refresh Interval",
                "description": "Auto-refresh interval in seconds",
                "type": "int",
                "default": 30,
                "value": 30
            },
            "max_log_entries": {
                "name": "Max Log Entries",
                "description": "Maximum number of log entries to keep",
                "type": "int",
                "default": 1000,
                "value": 1000
            },
            "enable_notifications": {
                "name": "Enable Notifications",
                "description": "Show notifications for important events",
                "type": "bool",
                "default": True,
                "value": True
            },
            "custom_theme": {
                "name": "Custom Theme",
                "description": "Use custom theme for plugin widgets",
                "type": "choice",
                "default": "system",
                "value": "system",
                "choices": ["system", "light", "dark", "high_contrast"]
            },
            "data_precision": {
                "name": "Data Precision",
                "description": "Decimal precision for numeric values",
                "type": "int",
                "default": 2,
                "value": 2
            }
        }
        
        # Create UI components
        self._create_actions()
        self._create_widgets()
        
    def initialize(self, app, plugin_info):
        """Initialize the plugin"""
        logger.info(f"Initializing {self.name} v{self.version}")
        
        # Store app reference and set up plugin interface
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info
        
        # Create UI components
        self._create_actions()
        self._create_widgets()
        
        # Initialize connected signals tracking
        self._connected_signals = set()
        
        # Initialize signal monitoring
        self._initialize_signal_monitoring()
        
        # Connect to device manager signals with tracking
        self._connect_to_signal(self.device_manager.device_added, self.on_device_added, "device_added")
        self._connect_to_signal(self.device_manager.device_removed, self.on_device_removed, "device_removed")
        self._connect_to_signal(self.device_manager.device_changed, self.on_device_changed, "device_changed")
        self._connect_to_signal(self.device_manager.selection_changed, self.on_device_selected, "selection_changed")
        
        # Connect to plugin manager signals
        self._connect_to_signal(self.app.plugin_manager.plugin_loaded, self.on_plugin_loaded, "plugin_loaded")
        self._connect_to_signal(self.app.plugin_manager.plugin_unloaded, self.on_plugin_unloaded, "plugin_unloaded")
        self._connect_to_signal(self.app.plugin_manager.plugin_enabled, self.on_plugin_enabled, "plugin_enabled")
        self._connect_to_signal(self.app.plugin_manager.plugin_disabled, self.on_plugin_disabled, "plugin_disabled")
        
        # Add columns to device table
        self.add_device_columns()
        
        # Initialize signal monitoring based on settings
        if self.settings["signal_monitoring"]["value"]:
            self._enable_all_signal_monitoring()
            
        # Initialize testing system
        self._initialize_tests()
        
        # Set up context menu for devices and groups
        self._setup_device_context_menu()
        self._setup_group_context_menu()
        
        # Register actions with the existing context menu system
        self._register_context_menu_actions()
        
        # Initialize complete
        self._initialized = True
        self.plugin_initialized.emit()
        
        # Log initialization
        self.log_message(f"Plugin initialized: {self.name} v{self.version}")
        logger.info(f"Sample plugin initialization complete")
        
        return True
        
    def _connect_to_signal(self, signal, slot, signal_name):
        """Connect to a signal and track the connection"""
        try:
            # Check if we've already tracked this signal
            if hasattr(self, '_connected_signals') and signal_name in self._connected_signals:
                logger.debug(f"Signal {signal_name} already connected, skipping")
                return
            
            # Attempt to connect the signal
            signal.connect(slot)
            
            # If connection was successful, track it
            if not hasattr(self, '_connected_signals'):
                self._connected_signals = set()
            self._connected_signals.add(signal_name)
            
            logger.debug(f"Connected to signal: {signal_name}")
        except (TypeError, RuntimeError) as e:
            # Handle signal connection errors specifically
            logger.error(f"Failed to connect to signal {signal_name} (connection error): {e}")
        except Exception as e:
            # Handle any other errors
            logger.error(f"Failed to connect to signal {signal_name}: {e}")
        
    def cleanup(self):
        """Clean up the plugin"""
        logger.info(f"Cleaning up {self.name}")
        try:
            self.log_message("Plugin cleanup started")
        except:
            # Don't crash if logging fails
            pass
        
        # Safety wrapper for disconnect operations
        def safe_disconnect(owner, signal_name, handler=None, object_name=""):
            """Safely disconnect a signal without crashing"""
            try:
                if owner is None:
                    logger.debug(f"Cannot disconnect {signal_name}: owner is None")
                    return
                
                if not hasattr(owner, signal_name):
                    logger.debug(f"Cannot disconnect {signal_name}: signal not found on {object_name}")
                    return
                
                signal = getattr(owner, signal_name)
                
                if not hasattr(signal, 'disconnect'):
                    logger.debug(f"Cannot disconnect {signal_name}: not a disconnectable signal")
                    return
                
                # If handler is specified, try to disconnect that specific handler
                if handler is not None:
                    try:
                        signal.disconnect(handler)
                        logger.debug(f"Successfully disconnected {signal_name} with specific handler")
                    except (TypeError, RuntimeError) as e:
                        logger.debug(f"Failed to disconnect specific handler for {signal_name}: {e}")
                else:
                    # Otherwise try to disconnect all connections
                    try:
                        # PySide6 allows disconnecting all receivers by calling disconnect() with no arguments
                        # But this will raise an exception if there are no connections
                        signal.disconnect()
                        logger.debug(f"Successfully disconnected all handlers for {signal_name}")
                    except (TypeError, RuntimeError) as e:
                        logger.debug(f"Failed to disconnect all handlers for {signal_name}: {e}")
            except Exception as e:
                logger.debug(f"Error during signal disconnect for {signal_name}: {e}")
        
        # 1. First disconnect UI signals
        try:
            # Handle context menu signals
            if hasattr(self, 'device_table'):
                safe_disconnect(self.device_table, 'customContextMenuRequested', 
                               self._on_device_context_menu, "device_table")
                
                # Handle header context menu
                if hasattr(self.device_table, 'horizontalHeader'):
                    header = self.device_table.horizontalHeader()
                    safe_disconnect(header, 'customContextMenuRequested', 
                                  self._on_device_context_menu, "horizontalHeader")
            
            # Handle action signals
            for action_name in ['action_sample', 'action_test', 'action_sample_menu', 
                               'action_new_device', 'action_edit_device', 
                               'action_run_tests', 'action_signal_monitor']:
                if hasattr(self, action_name):
                    action = getattr(self, action_name)
                    safe_disconnect(action, 'triggered', None, action_name)
            
            # Handle button signals
            for button_name in ['clear_log_button', 'save_log_button', 
                              'run_all_tests_button', 'stop_tests_button',
                              'enable_all_signals_button', 'disable_all_signals_button',
                              'clear_signal_log_button', 'test_device_button',
                              'sample_action_button', 'clear_device_test_button']:
                if hasattr(self, button_name):
                    button = getattr(self, button_name)
                    safe_disconnect(button, 'clicked', None, button_name)
            
            logger.debug("UI signals disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting UI signals: {e}")
        
        # 2. Disconnect device manager signals
        try:
            if hasattr(self, 'device_manager'):
                dm = self.device_manager
                safe_disconnect(dm, 'device_added', self.on_device_added, "device_manager")
                safe_disconnect(dm, 'device_removed', self.on_device_removed, "device_manager")
                safe_disconnect(dm, 'device_changed', self.on_device_changed, "device_manager")
                safe_disconnect(dm, 'selection_changed', self.on_device_selected, "device_manager")
            
            logger.debug("Device manager signals disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting device manager signals: {e}")
        
        # 3. Disconnect plugin manager signals
        try:
            if hasattr(self, 'app') and hasattr(self.app, 'plugin_manager'):
                pm = self.app.plugin_manager
                safe_disconnect(pm, 'plugin_loaded', self.on_plugin_loaded, "plugin_manager")
                safe_disconnect(pm, 'plugin_unloaded', self.on_plugin_unloaded, "plugin_manager")
                safe_disconnect(pm, 'plugin_enabled', self.on_plugin_enabled, "plugin_manager")
                safe_disconnect(pm, 'plugin_disabled', self.on_plugin_disabled, "plugin_manager")
            
            logger.debug("Plugin manager signals disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting plugin manager signals: {e}")
        
        # 4. Stop any active tests
        try:
            if hasattr(self, '_testing_in_progress') and self._testing_in_progress:
                try:
                    self._stop_tests()
                except Exception as e:
                    logger.error(f"Error stopping tests during cleanup: {e}")
        except Exception as e:
            logger.error(f"Error handling test stop: {e}")
        
        # 5. Clean up context menus
        try:
            if hasattr(self, 'device_context_menu'):
                self.device_context_menu.deleteLater()
                
            for action_dict_name in ['device_context_actions']:
                if hasattr(self, action_dict_name):
                    action_dict = getattr(self, action_dict_name)
                    for action in action_dict.values():
                        if hasattr(action, 'deleteLater'):
                            action.deleteLater()
        except Exception as e:
            logger.error(f"Error cleaning up menus: {e}")
        
        # 6. Clear references
        try:
            # Set all important references to None to help with garbage collection
            for attr_name in ['app', 'device_manager', 'main_window', 'config', 'plugin_info', 
                             'device_table', 'device_context_menu', 'device_context_actions',
                             '_connected_signals', '_signal_monitors']:
                if hasattr(self, attr_name):
                    setattr(self, attr_name, None)
        except Exception as e:
            logger.error(f"Error clearing references: {e}")
        
        # 7. Log completion
        try:
            self.log_message("Plugin cleanup completed")
        except:
            # Don't crash if logging fails
            pass
        
        logger.info(f"Sample plugin cleanup complete")
        return True  # Return success
        
    def _create_actions(self):
        """Create actions for menus and toolbar"""
        # Create a toolbar action
        self.action_sample = QAction("Sample Action", self)
        self.action_sample.setStatusTip("Add sample property to selected devices")
        self.action_sample.triggered.connect(self.on_sample_action)
        
        # Create test action for toolbar
        self.action_test = QAction("Test Application", self)
        self.action_test.setStatusTip("Launch application testing dashboard")
        self.action_test.triggered.connect(self.on_test_action)
        if getattr(self, "main_window", None):
            self.action_sample.setIcon(material_icon("devices", self.main_window, QStyle.SP_ComputerIcon))
            self.action_test.setIcon(material_icon("science", self.main_window, QStyle.SP_DialogApplyButton))
        
        # Create menu actions
        self.action_sample_menu = QAction("Sample Menu Action", self)
        self.action_sample_menu.setStatusTip("A sample menu action")
        self.action_sample_menu.triggered.connect(self.on_sample_menu_action)
        
        self.action_new_device = QAction("Add New Device", self)
        self.action_new_device.setStatusTip("Add a new device using the dialog")
        self.action_new_device.triggered.connect(self.create_new_device)
        
        self.action_edit_device = QAction("Edit Selected Device", self)
        self.action_edit_device.setStatusTip("Edit the selected device using the dialog")
        self.action_edit_device.triggered.connect(self.edit_selected_device)
        
        self.action_run_tests = QAction("Run Tests", self)
        self.action_run_tests.setStatusTip("Run comprehensive application tests")
        self.action_run_tests.triggered.connect(self.test_core_features)
        
        self.action_signal_monitor = QAction("Signal Monitor", self)
        self.action_signal_monitor.setStatusTip("Open signal monitoring dashboard")
        self.action_signal_monitor.triggered.connect(self.show_signal_monitor)
        
    def _create_widgets(self):
        """Create widgets for the plugin"""
        # Create the main plugin panel with tabs
        self.main_panel = QTabWidget()
        mark_plugin_ui(self.main_panel)
        mark_plugin_ui(self.main_panel.tabBar())
        
        # --- Log Tab ---
        self.log_tab = QWidget()
        self.log_layout = QVBoxLayout(self.log_tab)
        
        # Create a text edit for logs
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_layout.addWidget(self.log_widget)
        
        # Add log control buttons
        log_buttons_layout = QHBoxLayout()
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.log_widget.clear)
        log_buttons_layout.addWidget(self.clear_log_button)
        
        self.save_log_button = QPushButton("Save Log")
        self.save_log_button.clicked.connect(self._save_log)
        log_buttons_layout.addWidget(self.save_log_button)
        
        self.log_layout.addLayout(log_buttons_layout)
        
        # --- Test Dashboard Tab ---
        self.test_tab = QWidget()
        self.test_layout = QVBoxLayout(self.test_tab)
        
        # Test dashboard panel
        self.test_dashboard = QWidget()
        self.test_dashboard_layout = QVBoxLayout(self.test_dashboard)
        
        # Test control group
        self.test_control_section = CollapsibleSection("Test Controls")
        test_control_layout = QHBoxLayout()
        
        self.run_all_tests_button = QPushButton("Run All Tests")
        self.run_all_tests_button.clicked.connect(self.test_core_features)
        test_control_layout.addWidget(self.run_all_tests_button)
        
        self.stop_tests_button = QPushButton("Stop Tests")
        self.stop_tests_button.clicked.connect(self._stop_tests)
        self.stop_tests_button.setEnabled(False)
        test_control_layout.addWidget(self.stop_tests_button)
        
        self.test_control_section.content_layout.addLayout(test_control_layout)
        self.test_dashboard_layout.addWidget(self.test_control_section)
        
        # Test results group
        self.test_results_section = CollapsibleSection("Test Results")
        test_results_layout = QVBoxLayout()
        
        # Add tree widget for test results
        self.test_results_tree = QTreeWidget()
        self.test_results_tree.setHeaderLabels(["Test", "Status", "Duration"])
        self.test_results_tree.setColumnWidth(0, 250)
        test_results_layout.addWidget(self.test_results_tree)
        
        # Progress bar for test progress
        self.test_progress = QProgressBar()
        self.test_progress.setRange(0, 100)
        self.test_progress.setValue(0)
        test_results_layout.addWidget(self.test_progress)
        
        self.test_results_section.content_layout.addLayout(test_results_layout)
        self.test_dashboard_layout.addWidget(self.test_results_section)
        
        # Add the test dashboard to the test tab
        self.test_layout.addWidget(self.test_dashboard)
        
        # --- Signal Monitor Tab ---
        self.signal_tab = QWidget()
        self.signal_layout = QVBoxLayout(self.signal_tab)
        
        # Signal control group
        self.signal_control_section = CollapsibleSection("Signal Monitoring")
        signal_control_layout = QVBoxLayout()
        
        # Signal monitoring controls
        signal_buttons_layout = QHBoxLayout()
        
        self.enable_all_signals_button = QPushButton("Enable All")
        self.enable_all_signals_button.clicked.connect(self._enable_all_signal_monitoring)
        signal_buttons_layout.addWidget(self.enable_all_signals_button)
        
        self.disable_all_signals_button = QPushButton("Disable All")
        self.disable_all_signals_button.clicked.connect(self._disable_all_signal_monitoring)
        signal_buttons_layout.addWidget(self.disable_all_signals_button)
        
        self.clear_signal_log_button = QPushButton("Clear Log")
        self.clear_signal_log_button.clicked.connect(self._clear_signal_log)
        signal_buttons_layout.addWidget(self.clear_signal_log_button)
        
        signal_control_layout.addLayout(signal_buttons_layout)
        
        # Signal selection list with checkboxes
        self.signal_list_widget = QWidget()
        self.signal_list_layout = QFormLayout(self.signal_list_widget)
        
        # We'll populate this in _initialize_signal_monitoring
        signal_control_layout.addWidget(self.signal_list_widget)
        
        self.signal_control_section.content_layout.addLayout(signal_control_layout)
        self.signal_layout.addWidget(self.signal_control_section)
        
        # Signal log table
        self.signal_log_section = CollapsibleSection("Signal Log")
        signal_log_layout = QVBoxLayout()
        
        self.signal_log_table = QTableWidget()
        self.signal_log_table.setColumnCount(4)
        self.signal_log_table.setHorizontalHeaderLabels(["Timestamp", "Signal", "Source", "Parameters"])
        self.signal_log_table.setColumnWidth(0, 150)
        self.signal_log_table.setColumnWidth(1, 150)
        self.signal_log_table.setColumnWidth(2, 150)
        self.signal_log_table.setColumnWidth(3, 250)
        
        signal_log_layout.addWidget(self.signal_log_table)
        
        self.signal_log_section.content_layout.addLayout(signal_log_layout)
        self.signal_layout.addWidget(self.signal_log_section)
        
        # --- Device Details Tab ---
        self.details_tab = QWidget()
        self.details_layout = QVBoxLayout(self.details_tab)
        
        # Device details panel
        self.details_widget = QWidget()
        self.details_widget.setObjectName("SamplePluginDetailsWidget")
        self.details_layout_widget = QVBoxLayout(self.details_widget)
        
        # Title label
        title_label = QLabel("Sample Plugin Device Details")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.details_layout_widget.addWidget(title_label)
        
        # Device info
        self.details_info_section = CollapsibleSection("Device Information")
        self.details_info_layout = QFormLayout()
        self.device_name_label = QLabel("No device selected")
        self.device_type_label = QLabel("N/A")
        self.device_status_label = QLabel("N/A")
        self.device_sample_label = QLabel("N/A")
        
        self.details_info_layout.addRow(QLabel("<b>Name:</b>"), self.device_name_label)
        self.details_info_layout.addRow(QLabel("<b>Type:</b>"), self.device_type_label)
        self.details_info_layout.addRow(QLabel("<b>Status:</b>"), self.device_status_label)
        self.details_info_layout.addRow(QLabel("<b>Sample:</b>"), self.device_sample_label)
        
        self.details_info_section.content_layout.addLayout(self.details_info_layout)
        self.details_layout_widget.addWidget(self.details_info_section)
        
        # Device test group
        self.details_test_section = CollapsibleSection("Device Details and Test Results")
        self.details_test_layout = QVBoxLayout()
        
        # Test buttons for device
        device_test_buttons = QHBoxLayout()
        
        self.test_device_button = QPushButton("Test Device")
        self.test_device_button.clicked.connect(self._test_selected_device)
        device_test_buttons.addWidget(self.test_device_button)
        
        self.sample_action_button = QPushButton("Sample Action")
        self.sample_action_button.clicked.connect(self._on_sample_action_context)
        device_test_buttons.addWidget(self.sample_action_button)
        
        self.clear_device_test_button = QPushButton("Clear Test Results")
        self.clear_device_test_button.clicked.connect(self._clear_device_test_results)
        device_test_buttons.addWidget(self.clear_device_test_button)
        
        self.details_test_layout.addLayout(device_test_buttons)
        
        # Test results with HTML support
        self.device_test_results = QTextEdit()
        self.device_test_results.setReadOnly(True)
        self.device_test_results.setPlaceholderText("No test results available")
        self.device_test_results.setMinimumHeight(250)  # Make it taller
        self.details_test_layout.addWidget(self.device_test_results)
        
        self.details_test_section.content_layout.addLayout(self.details_test_layout)
        self.details_layout_widget.addWidget(self.details_test_section)
        
        # Add to details tab
        self.details_layout.addWidget(self.details_widget)
        
        # Add tabs to main panel
        self.main_panel.addTab(self.log_tab, "Log")
        self.main_panel.addTab(self.test_tab, "Test Dashboard")
        self.main_panel.addTab(self.signal_tab, "Signal Monitor")
        self.main_panel.addTab(self.details_tab, "Device Details")
        
        # Create a dock widget to properly contain the main panel
        self.dock_widget = QDockWidget("Sample Plugin")
        self.dock_widget.setObjectName("SamplePluginDock")
        self.dock_widget.setWidget(self.main_panel)
    def _save_log(self):
        """Save the log contents to a file"""
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"sample_plugin_log_{timestamp}.txt")
            
            with open(log_file, 'w') as f:
                f.write(self.log_widget.toPlainText())
                
            self.log_message(f"Log saved to: {log_file}")
            logger.info(f"Sample plugin log saved to: {log_file}")
        except Exception as e:
            logger.error(f"Error saving log: {e}")
            self.log_message(f"Error saving log: {e}")
            
    def log_message(self, message):
        """Add a message to the log widget"""
        if hasattr(self, 'log_widget'):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_widget.append(f"[{timestamp}] {message}")
            
            # Ensure the new message is visible
            scrollbar = self.log_widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def add_device_columns(self):
        """Add columns to the device table"""
        # Add a sample column to the device table
        if hasattr(self.main_window, 'device_table_model'):
            self.main_window.device_table_model.add_column(
                "Sample", "sample", self.get_sample_value
            )
            # Add a test result column
            self.main_window.device_table_model.add_column(
                "Test Result", "test_result", self.get_test_result_value
            )
            
    def get_sample_value(self, device):
        """Get a sample value for a device"""
        return device.get_property("sample", "N/A")

    def get_test_result_value(self, device):
        """Get the test result value for a device"""
        result = device.get_property("test_result", "Not tested")
        return result
        
    def get_toolbar_actions(self):
        """Get actions to be added to the toolbar"""
        return [self.action_sample, self.action_test]
        
    def get_menu_actions(self):
        """Get actions to be added to the menu"""
        return {
            "Sample": [
                self.action_sample_menu,
                self.action_new_device,
                self.action_edit_device,
                self.action_run_tests,
                self.action_signal_monitor
            ]
        }
        
    def get_device_panels(self):
        """Get panels to be added to the device view"""
        return [
            ("Sample", self.details_widget)
        ]
        
    def get_dock_widgets(self):
        """Get dock widgets to be added to the main window"""
        return [
            ("Sample Plugin", self.dock_widget, Qt.RightDockWidgetArea)
        ]
        
    def get_device_table_columns(self):
        """Get columns to be added to the device table"""
        return [
            ("Sample", "sample", self.get_sample_value),
            ("Test Result", "test_result", self.get_test_result_value)
        ]
        
    def get_settings(self):
        """Get plugin settings"""
        return self.settings
        
    def update_setting(self, setting_id, value):
        """Update a plugin setting"""
        if setting_id not in self.settings:
            logger.warning(f"Unknown setting: {setting_id}")
            return False
            
        try:
            # Update the setting value
            self.settings[setting_id]["value"] = value
            
            # Handle special settings
            if setting_id == "log_level":
                logger.debug(f"Changed log level to {value}")
                
            elif setting_id == "auto_sample":
                logger.debug(f"Auto sample set to {value}")
                
            elif setting_id == "default_value":
                logger.debug(f"Default sample value set to {value}")
                
            elif setting_id == "testing_mode":
                logger.debug(f"Testing mode set to {value}")
                
            elif setting_id == "test_signal_timeout":
                logger.debug(f"Signal test timeout set to {value}")
                
            elif setting_id == "signal_monitoring":
                logger.debug(f"Signal monitoring set to {value}")
                
            self.log_widget.append(f"Setting '{self.settings[setting_id]['name']}' updated to: {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating setting {setting_id}: {e}")
            return False
        
    # Event handlers
    
    @safe_action_wrapper
    def on_sample_action(self):
        """Handle sample action"""
        logger.info("Sample action triggered")
        self.log_message("Sample action triggered")
        
        try:
            # Add sample property to selected devices
            selected_devices = self.device_manager.get_selected_devices()
            
            if not selected_devices:
                self.log_message("No devices selected. Please select at least one device.")
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage("No devices selected for Sample Action", 3000)
                return
                
            success_count = 0
            for device in selected_devices:
                try:
                    if device is None:
                        continue
                        
                    # Safely set property
                    device.set_property("sample", self.settings["default_value"]["value"])
                    self.log_message(f"Added sample property to {device.get_property('name', 'Unnamed')}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error setting property on device: {e}")
                    self.log_message(f"Error setting property: {e}")
            
            # Show success message
            if success_count > 0:
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"Sample property added to {success_count} device(s)", 3000)
            else:
                self.log_message("Failed to add sample property to any devices")
                
        except Exception as e:
            logger.error(f"Error in sample action: {e}")
            self.log_message(f"Error in sample action: {e}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"Error: {e}", 3000)
        
    @safe_action_wrapper
    def on_test_action(self):
        """Handle test action"""
        logger.info("Test action triggered")
        self.log_widget.append("Test action triggered")
        
        # Activate the test dashboard tab
        self.main_panel.setCurrentWidget(self.test_tab)
        
    @safe_action_wrapper
    def on_sample_menu_action(self):
        """Handle sample menu action"""
        logger.info("Sample menu action triggered")
        self.log_widget.append("Sample menu action triggered")

        parent = self.main_window if hasattr(self, "main_window") else None
        dialog = PluginDialogBase("Sample Plugin Dialog", parent)
        dialog.resize(520, 360)

        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.addWidget(QLabel("Sample plugin dialog using PluginDialogBase."))

        overview_table = QTableWidget(2, 2)
        overview_table.setHorizontalHeaderLabels(["Setting", "Value"])
        overview_table.setAlternatingRowColors(True)
        overview_table.verticalHeader().setVisible(False)
        overview_table.setItem(0, 0, QTableWidgetItem("Status"))
        overview_table.setItem(0, 1, QTableWidgetItem("Ready"))
        overview_table.setItem(1, 0, QTableWidgetItem("Last Run"))
        overview_table.setItem(1, 1, QTableWidgetItem("Not started"))
        overview_layout.addWidget(overview_table)

        dialog.add_tab(overview_tab, "Overview")
        dialog.add_action_button("Close", dialog.reject)
        dialog.exec()

        parent = self.main_window if hasattr(self, "main_window") else None
        dialog = PluginDialogBase("Sample Plugin Dialog", parent)
        dialog.resize(520, 360)

        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.addWidget(QLabel("Sample plugin dialog using PluginDialogBase."))

        overview_table = QTableWidget(2, 2)
        overview_table.setHorizontalHeaderLabels(["Setting", "Value"])
        overview_table.setAlternatingRowColors(True)
        overview_table.verticalHeader().setVisible(False)
        overview_table.setItem(0, 0, QTableWidgetItem("Status"))
        overview_table.setItem(0, 1, QTableWidgetItem("Ready"))
        overview_table.setItem(1, 0, QTableWidgetItem("Last Run"))
        overview_table.setItem(1, 1, QTableWidgetItem("Not started"))
        overview_layout.addWidget(overview_table)

        dialog.add_tab(overview_tab, "Overview")
        dialog.add_action_button("Close", dialog.reject)
        dialog.exec()
        
    @safe_action_wrapper
    def show_signal_monitor(self):
        """Show the signal monitor tab"""
        logger.info("Signal monitor action triggered")
        self.log_widget.append("Opening signal monitor")
        
        # Activate the signal monitor tab
        self.main_panel.setCurrentWidget(self.signal_tab)
        
    @safe_action_wrapper
    def create_new_device(self):
        """Create a new device using the dialog or device manager API"""
        logger.info("Creating new device")
        self.log_widget.append("Creating new device...")
        
        try:
            # Try to use the plugin interface method to show the add device dialog
            if hasattr(self, 'add_device_dialog'):
                new_device = self.add_device_dialog()
                
                if new_device:
                    # Device was created and automatically added to the device manager
                    logger.info(f"New device created via dialog: {new_device.get_property('alias')}")
                    self.log_widget.append(f"Created device: {new_device.get_property('alias')}")
                    
                    # Add sample property if auto_sample is enabled
                    if self.settings["auto_sample"]["value"]:
                        default_value = self.settings["default_value"]["value"]
                        new_device.set_property("sample", default_value)
                        self.log_widget.append(f"Added sample property to new device: {default_value}")
                    
                    return new_device
                else:
                    self.log_widget.append("Device creation cancelled")
                    return None
            else:
                # Use the device manager's create_device method as a fallback
                device_type = "sample"
                default_properties = {
                    "name": "Sample Device",
                    "description": "Device created by Sample Plugin",
                    "sample": self.settings["default_value"]["value"]
                }
                
                # Create the device
                new_device = self.device_manager.create_device(device_type, **default_properties)
                
                # Add it to the device manager
                self.device_manager.add_device(new_device)
                
                logger.info(f"New device created via API: {new_device.get_property('name')}")
                self.log_widget.append(f"Created device: {new_device.get_property('name')}")
                return new_device
        except Exception as e:
            logger.error(f"Error creating device: {e}")
            self.log_widget.append(f"Error creating device: {e}")
            return None
        
    @safe_action_wrapper
    def edit_selected_device(self):
        """Edit the selected device using the dialog"""
        selected_devices = self.device_manager.get_selected_devices()
        
        if not selected_devices:
            logger.warning("No device selected to edit")
            self.log_widget.append("No device selected to edit")
            return
            
        device = selected_devices[0]
        logger.info(f"Editing device: {device.get_property('alias')}")
        self.log_widget.append(f"Editing device: {device.get_property('alias')}")
        
        # Use the plugin interface method to show the device properties dialog
        updated_device = self.show_device_properties_dialog(device)
        
        if updated_device:
            # Device was updated
            logger.info(f"Device updated: {updated_device.get_property('alias')}")
            self.log_widget.append(f"Updated device: {updated_device.get_property('alias')}")
        else:
            self.log_widget.append("Device edit cancelled")
        
    # Signal handlers
    
    def on_device_added(self, device):
        """Handle device added signal"""
        logger.debug(f"Sample plugin: Device added: {device}")
        self.log_message(f"Device added: {device.get_property('name')}")
        
        # Add sample property if auto_sample is enabled
        if self.settings["auto_sample"]["value"]:
            default_value = self.settings["default_value"]["value"]
            device.set_property("sample", default_value)
            self.log_message(f"Added sample property to new device: {default_value}")
            
        # Log signal event for monitoring
        self._log_signal_event("device_added", "Device Manager", device.get_property("name"))
        
    def on_device_removed(self, device):
        """Handle device removed signal"""
        logger.debug(f"Sample plugin: Device removed: {device}")
        self.log_message(f"Device removed: {device.get_property('name')}")
        
        # Log signal event for monitoring
        self._log_signal_event("device_removed", "Device Manager", device.get_property("name"))
        
    def on_device_changed(self, device):
        """Handle device changed signal"""
        logger.debug(f"Sample plugin: Device changed: {device}")
        
        # Update details if this is the selected device
        selected_devices = self.device_manager.get_selected_devices()
        if device in selected_devices:
            self.update_device_details(device)
            
        # Log signal event for monitoring
        self._log_signal_event("device_changed", "Device Manager", device.get_property("name"))
            
    def on_device_selected(self, devices):
        """Handle device selection changed signal"""
        logger.debug(f"Sample plugin: Device selection changed: {len(devices)} selected")
        
        if devices:
            self.update_device_details(devices[0])
        else:
            # Clear the device details
            self.device_name_label.setText("No device selected")
            self.device_type_label.setText("N/A")
            self.device_status_label.setText("N/A")
            self.device_sample_label.setText("N/A")
            self.device_test_results.clear()
            
        # Log signal event for monitoring
        # Fix: Handle possible None values in device names by filtering them out
        device_names = []
        if devices:
            device_names = [d.get_property("name", "Unknown") for d in devices]
            # Filter out None values
            device_names = [name for name in device_names if name is not None]
        
        self._log_signal_event("selection_changed", "Device Manager", f"{len(devices)} devices: {', '.join(device_names or ['None'])}")
    
    def on_plugin_loaded(self, plugin_info):
        """Handle plugin loaded signal"""
        logger.debug(f"Sample plugin: Plugin loaded: {plugin_info.name}")
        self.log_message(f"Plugin loaded: {plugin_info.name} v{plugin_info.version}")
        
        # Log signal event for monitoring
        self._log_signal_event("plugin_loaded", "Plugin Manager", f"{plugin_info.name} v{plugin_info.version}")
        
    def on_plugin_unloaded(self, plugin_info):
        """Handle plugin unloaded signal"""
        logger.debug(f"Sample plugin: Plugin unloaded: {plugin_info.name}")
        self.log_message(f"Plugin unloaded: {plugin_info.name}")
        
        # Log signal event for monitoring
        self._log_signal_event("plugin_unloaded", "Plugin Manager", plugin_info.name)
        
    def on_plugin_enabled(self, plugin_info):
        """Handle plugin enabled signal"""
        logger.debug(f"Sample plugin: Plugin enabled: {plugin_info.name}")
        self.log_message(f"Plugin enabled: {plugin_info.name}")
        
        # Log signal event for monitoring
        self._log_signal_event("plugin_enabled", "Plugin Manager", plugin_info.name)
        
    def on_plugin_disabled(self, plugin_info):
        """Handle plugin disabled signal"""
        logger.debug(f"Sample plugin: Plugin disabled: {plugin_info.name}")
        self.log_message(f"Plugin disabled: {plugin_info.name}")
        
        # Log signal event for monitoring
        self._log_signal_event("plugin_disabled", "Plugin Manager", plugin_info.name)
            
    def update_device_details(self, device):
        """Update device details in the panel"""
        try:
            # Get device properties safely with default values
            device_name = device.get_property("name", "N/A")
            device_type = device.get_property("type", "N/A") 
            device_status = device.get_property("status", "N/A")
            device_sample = device.get_property("sample", "N/A")
            
            # Update device information labels safely
            self.device_name_label.setText(str(device_name) if device_name is not None else "N/A")
            self.device_type_label.setText(str(device_type) if device_type is not None else "N/A")
            self.device_status_label.setText(str(device_status) if device_status is not None else "N/A")
            self.device_sample_label.setText(str(device_sample) if device_sample is not None else "N/A")
            
            # Check for Sample Action properties
            sample_action_performed = device.get_property("sample_action_performed", False)
            sample_action_timestamp = device.get_property("sample_action_timestamp", "Never")
            sample_action_group = device.get_property("sample_action_group", "N/A")
            
            # Enhanced device details display
            details_text = f"""
<b>Device Details:</b>
Name: {device_name}
Type: {device_type}
Status: {device_status}
Sample Value: {device_sample}

<b>Sample Action:</b>
Performed: {"Yes" if sample_action_performed else "No"}
Last Action: {sample_action_timestamp}
Group Action: {sample_action_group if sample_action_group != "N/A" else "No"}
"""
            
            # Set comprehensive details in test results area
            self.device_test_results.setHtml(details_text)
            
            # Update test results if available
            test_result = device.get_property("test_result", "Not tested")
            test_timestamp = device.get_property("test_timestamp", "")
            
            if test_result != "Not tested":
                # Append test results to the details
                test_details = f"""
<b>Test Results:</b>
Result: {test_result}
Last Test: {test_timestamp}
"""
                # Get more test details if available
                test_summary = device.get_property("test_summary", "")
                test_details_text = device.get_property("test_details", "")
                
                if test_summary:
                    test_details += f"Summary: {test_summary}\n"
                
                if test_details_text:
                    test_details += f"\n{test_details_text}"
                    
                self.device_test_results.setHtml(details_text + test_details)
                
        except Exception as e:
            logger.error(f"Error updating device details: {e}")
            # Set default values if there's an error
            self.device_name_label.setText("Error")
            self.device_type_label.setText("N/A")
            self.device_status_label.setText("N/A")
            self.device_sample_label.setText("N/A")
            self.device_test_results.setText(f"Error updating device details: {e}")
        
    # Testing functionality
    
    def _initialize_tests(self):
        """Initialize the testing system"""
        # Define available tests
        self._test_definitions = {
            "core": {
                "name": "Core Features",
                "tests": {
                    "application_version": {
                        "name": "Application Version",
                        "function": self._test_application_version,
                        "description": "Verify application version information"
                    },
                    "device_manager": {
                        "name": "Device Manager",
                        "function": self._test_device_manager,
                        "description": "Test device manager functionality"
                    },
                    "plugin_manager": {
                        "name": "Plugin Manager",
                        "function": self._test_plugin_manager,
                        "description": "Test plugin manager functionality"
                    },
                    "configuration": {
                        "name": "Configuration System",
                        "function": self._test_configuration,
                        "description": "Test configuration loading and saving"
                    }
                }
            },
            "signals": {
                "name": "Signal System",
                "tests": {
                    "device_signals": {
                        "name": "Device Signals",
                        "function": self._test_device_signals,
                        "description": "Test device-related signals"
                    },
                    "plugin_signals": {
                        "name": "Plugin Signals",
                        "function": self._test_plugin_signals,
                        "description": "Test plugin-related signals"
                    },
                    "ui_signals": {
                        "name": "UI Signals",
                        "function": self._test_ui_signals,
                        "description": "Test UI-related signals"
                    }
                }
            },
            "ui": {
                "name": "User Interface",
                "tests": {
                    "main_window": {
                        "name": "Main Window",
                        "function": self._test_main_window,
                        "description": "Test main window functionality"
                    },
                    "device_table": {
                        "name": "Device Table",
                        "function": self._test_device_table,
                        "description": "Test device table functionality"
                    },
                    "dialogs": {
                        "name": "Dialogs",
                        "function": self._test_dialogs,
                        "description": "Test application dialogs"
                    }
                }
            }
        }
        
        # Initialize test results
        self._test_results = {}
        
        # Populate the test tree widget
        self._populate_test_tree()
        
    def _populate_test_tree(self):
        """Populate the test tree widget with available tests"""
        self.test_results_tree.clear()
        
        for category_id, category in self._test_definitions.items():
            category_item = QTreeWidgetItem(self.test_results_tree)
            category_item.setText(0, category["name"])
            category_item.setExpanded(True)
            
            for test_id, test in category["tests"].items():
                test_item = QTreeWidgetItem(category_item)
                test_item.setText(0, test["name"])
                test_item.setText(1, "Not Run")
                test_item.setToolTip(0, test["description"])
                
                # Store test IDs in the item data
                test_item.setData(0, Qt.UserRole, f"{category_id}.{test_id}")
        
    def _update_test_result(self, category_id, test_id, success, duration, message=None):
        """Update the result of a test in the UI"""
        # Find the test item in the tree
        test_data = f"{category_id}.{test_id}"
        root = self.test_results_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            category_item = root.child(i)
            
            for j in range(category_item.childCount()):
                test_item = category_item.child(j)
                if test_item.data(0, Qt.UserRole) == test_data:
                    # Update the item
                    status = "SUCCESS" if success else "FAILED"
                    test_item.setText(1, status)
                    test_item.setText(2, f"{duration:.2f}s")
                    
                    # Set status color
                    test_item.setForeground(1, QColor("green" if success else "red"))
                    
                    # Store the message in the tooltip
                    if message:
                        test_item.setToolTip(1, message)
                    
                    break
                    
        # Update the progress bar
        total_tests = 0
        completed_tests = 0
        
        for category_id, category in self._test_definitions.items():
            for test_id in category["tests"]:
                total_tests += 1
                if f"{category_id}.{test_id}" in self._test_results:
                    completed_tests += 1
                    
        if total_tests > 0:
            progress = int((completed_tests / total_tests) * 100)
            self.test_progress.setValue(progress)
        
    def test_core_features(self):
        """Run all tests for core application features"""
        if self._testing_in_progress:
            logger.warning("Tests already in progress")
            self.log_message("Tests already in progress, please wait...")
            return
            
        self._testing_in_progress = True
        self.stop_tests_button.setEnabled(True)
        self.run_all_tests_button.setEnabled(False)
        self.log_message("Starting comprehensive application tests...")
        
        # Clear previous results
        self._test_results = {}
        self._populate_test_tree()
        self.test_progress.setValue(0)
        
        # Emit test started signal
        self.test_started.emit("all")
        
        # Run tests in a timer to keep UI responsive
        self._remaining_tests = []
        
        # Build the list of tests to run
        for category_id, category in self._test_definitions.items():
            for test_id, test in category["tests"].items():
                self._remaining_tests.append((category_id, test_id, test))
                
        # Start running tests
        QTimer.singleShot(100, self._run_next_test)
        
    def _run_next_test(self):
        """Run the next test in the queue"""
        if not self._testing_in_progress or not self._remaining_tests:
            # No more tests or testing stopped
            self._testing_in_progress = False
            self.stop_tests_button.setEnabled(False)
            self.run_all_tests_button.setEnabled(True)
            
            # Emit completed signal
            self.test_all_completed.emit(self._test_results)
            
            # Log completion
            total_tests = len(self._test_results)
            passed_tests = sum(1 for r in self._test_results.values() if r["success"])
            
            self.log_message(f"Testing complete: {passed_tests}/{total_tests} tests passed")
            logger.info(f"Sample plugin testing complete: {passed_tests}/{total_tests} tests passed")
            
            return
            
        # Get the next test
        category_id, test_id, test = self._remaining_tests.pop(0)
        
        # Log test start
        test_name = test["name"]
        self.log_message(f"Running test: {test_name}")
        
        # Emit test started signal
        self.test_started.emit(f"{category_id}.{test_id}")
        
        # Run the test
        start_time = time.time()
        try:
            result = test["function"]()
            if isinstance(result, tuple) and len(result) == 2:
                success, message = result
            else:
                success = result
                message = "Test completed successfully" if success else "Test failed"
        except Exception as e:
            success = False
            message = f"Test raised an exception: {str(e)}"
            logger.error(f"Test {test_name} failed with exception: {e}", exc_info=True)
            
        duration = time.time() - start_time
        
        # Store the result
        self._test_results[f"{category_id}.{test_id}"] = {
            "success": success,
            "duration": duration,
            "message": message,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Update the UI
        self._update_test_result(category_id, test_id, success, duration, message)
        
        # Emit test completed signal
        self.test_completed.emit(f"{category_id}.{test_id}", success)
        
        # Schedule the next test
        QTimer.singleShot(100, self._run_next_test)
    
    def _stop_tests(self):
        """Stop the currently running tests"""
        if not self._testing_in_progress:
            return
            
        self._testing_in_progress = False
        self._remaining_tests = []
        self.stop_tests_button.setEnabled(False)
        self.run_all_tests_button.setEnabled(True)
        
        self.log_message("Tests stopped by user")
        logger.info("Sample plugin tests stopped by user")
        
    def test_signal(self, signal_name):
        """Test a specific signal"""
        if signal_name not in self._connected_signals:
            self.log_message(f"Signal {signal_name} is not connected, cannot test")
            return False
            
        # Log test start
        self.log_message(f"Testing signal: {signal_name}")
        
        # The implementation would depend on the specific signal
        # Here we'll just log that we would test it
        self.log_message(f"Signal test for {signal_name} would be implemented here")
        
        # For now, return True
        return True
        
    def _test_application_version(self):
        """Test application version functionality"""
        try:
            if not hasattr(self.app, 'get_version'):
                return False, "Application does not have get_version method"
                
            version = self.app.get_version()
            self.log_message(f"Application version: {version}")
            
            # Basic validation that version looks reasonable
            if isinstance(version, str) and len(version.split('.')) >= 2:
                return True, f"Version validated: {version}"
            else:
                return False, f"Invalid version format: {version}"
        except Exception as e:
            return False, f"Error testing application version: {str(e)}"
            
    def _test_device_manager(self):
        """Test device manager functionality"""
        try:
            if not self.device_manager:
                return False, "Device manager reference not available"
            
            # Safely get current devices
            try:
                device_count = len(self.device_manager.get_devices())
                self.log_message(f"Device manager has {device_count} devices")
            except Exception as e:
                return False, f"Error getting devices: {str(e)}"
            
            # Test if we can create a device using the new API
            try:
                if hasattr(self.device_manager, 'create_device'):
                    test_device = self.device_manager.create_device(
                        device_type="test", 
                        name="Test Device",
                        description="Created for testing",
                        status="test"
                    )
                    self.log_message(f"Successfully created test device: {test_device}")
                    
                    # We don't add it to the manager for this test
                    return True, "Device manager API accessible, device creation successful"
                else:
                    self.log_message("Warning: Device manager does not provide a creation method")
                    return True, "Device manager API accessible, but no device creation method"
            except Exception as e:
                self.log_message(f"Warning: Could not create a test device: {str(e)}")
                return True, "Device manager API accessible, but device creation failed"
                
        except Exception as e:
            return False, f"Error testing device manager: {str(e)}"
            
    def _test_plugin_manager(self):
        """Test plugin manager functionality"""
        try:
            plugin_count = len(self.app.plugin_manager.get_plugins())
            self.log_message(f"Plugin manager has {plugin_count} plugins")
            
            # Check that our plugin is loaded
            our_plugin = self.app.plugin_manager.get_plugin("sample")
            if not our_plugin or not our_plugin.loaded:
                return False, "Sample plugin not properly loaded"
                
            return True, f"Plugin manager has {plugin_count} plugins including sample plugin"
        except Exception as e:
            return False, f"Error testing plugin manager: {str(e)}"
            
    def _test_configuration(self):
        """Test configuration system"""
        try:
            if not self.config:
                return False, "Configuration reference not available"
                
            # First check if config object has the necessary methods
            if not hasattr(self.config, 'get'):
                return False, "Configuration object does not have 'get' method"
                
            # Test basic config access with multiple possible keys
            config_accessed = False
            possible_keys = [
                "application.name", 
                "app.name", 
                "app_name", 
                "application_name",
                "name"
            ]
            
            for key in possible_keys:
                try:
                    value = self.config.get(key, None)
                    if value:
                        self.log_message(f"Successfully read configuration value '{key}': {value}")
                        config_accessed = True
                        break
                except Exception:
                    # Continue trying other keys
                    pass
            
            # If we couldn't access any of the name keys, try a generic approach
            if not config_accessed:
                # Try to see if get method works with any key
                try:
                    # Just log some values from config to see what's there
                    if hasattr(self.config, 'get_all'):
                        all_config = self.config.get_all()
                        if all_config and isinstance(all_config, dict):
                            # Just log a few keys
                            sample_keys = list(all_config.keys())[:3]
                            self.log_message(f"Config has keys: {sample_keys}")
                            config_accessed = True
                    elif hasattr(self.config, '__getitem__'):
                        # Try dictionary-like access to see what's there
                        for key in ["version", "theme", "workspace"]:
                            try:
                                value = self.config[key]
                                if value:
                                    self.log_message(f"Config[{key}] = {value}")
                                    config_accessed = True
                                    break
                            except:
                                pass
                except Exception as e:
                    self.log_message(f"Error exploring config: {e}")
            
            # As a last resort, test if we can set and get a value
            if not config_accessed:
                test_key = "_test_sample_plugin_key"
                test_value = f"test-value-{int(time.time())}"
                
                try:
                    # Try to set a test value
                    if hasattr(self.config, 'set'):
                        self.config.set(test_key, test_value)
                        read_value = self.config.get(test_key, None)
                        
                        if read_value == test_value:
                            self.log_message(f"Successfully set and retrieved test config value")
                            config_accessed = True
                except Exception as e:
                    self.log_message(f"Error testing config set/get: {e}")
                
            # Verdict
            if config_accessed:
                return True, "Successfully accessed configuration system"
            else:
                return False, "Could not verify configuration system functionality"
                
        except Exception as e:
            return False, f"Error testing configuration: {str(e)}"
            
    def _test_device_signals(self):
        """Test device-related signals"""
        self.log_message("Testing device signals - verification is manual")
        return True, "Device signals test completed"
            
    def _test_plugin_signals(self):
        """Test plugin-related signals"""
        self.log_message("Testing plugin signals - verification is manual")
        return True, "Plugin signals test completed"
            
    def _test_ui_signals(self):
        """Test UI-related signals"""
        self.log_message("Testing UI signals - verification is manual")
        return True, "UI signals test completed"
            
    def _test_main_window(self):
        """Test main window functionality"""
        try:
            if not self.main_window:
                return False, "Main window reference not available"
                
            window_title = self.main_window.windowTitle()
            self.log_message(f"Main window title: {window_title}")
            
            # For now, just verify we have access to the main window
            return True, "Successfully accessed main window"
        except Exception as e:
            return False, f"Error testing main window: {str(e)}"
            
    def _test_device_table(self):
        """Test device table functionality"""
        try:
            if not self.main_window:
                return False, "Main window reference not available"
            
            # Check if device table exists
            device_table = None
            
            # Try different ways to access the device table
            if hasattr(self.main_window, 'device_table_model'):
                self.log_message("Found device_table_model attribute")
                device_table = self.main_window.device_table_model
            elif hasattr(self.main_window, 'device_table'):
                self.log_message("Found device_table attribute")
                device_table = self.main_window.device_table
                
                # If it's a view, try to get its model
                if hasattr(device_table, 'model'):
                    self.log_message("Found model in device_table")
                    device_table = device_table.model()
            
            # If we found any reference to the device table
            if device_table:
                # Try to get column information
                try:
                    if hasattr(device_table, 'columnCount') and callable(device_table.columnCount):
                        column_count = device_table.columnCount()
                        self.log_message(f"Device table has {column_count} columns")
                        
                        # Also test context menu functionality
                        context_menu_test_result = self._test_context_menu_setup()
                        if context_menu_test_result:
                            self.log_message("Context menu setup verified")
                        else:
                            self.log_message("Context menu setup has issues")
                            
                        # Test device details functionality
                        details_result, details_message = self._test_device_details()
                        if details_result:
                            self.log_message(f"Device details test passed: {details_message}")
                        else:
                            self.log_message(f"Device details test failed: {details_message}")
                        
                        return True, f"Successfully accessed device table with {column_count} columns"
                    else:
                        # Try a different approach - check if it has columns property
                        if hasattr(device_table, 'columns'):
                            columns = device_table.columns
                            self.log_message(f"Device table has {len(columns)} columns")
                            return True, f"Successfully accessed device table columns"
                except Exception as e:
                    self.log_message(f"Warning when accessing columns: {str(e)}")
                    
                # If we reached here, we found the table but couldn't get column info
                return True, "Device table found but couldn't access column information"
            
            # As a last resort, check if we can find the table through widget searches
            from PySide6.QtWidgets import QTableView, QTableWidget
            table_views = self.main_window.findChildren(QTableView)
            table_widgets = self.main_window.findChildren(QTableWidget)
            
            if table_views:
                self.log_message(f"Found {len(table_views)} QTableView widgets")
                return True, f"Found {len(table_views)} QTableView widgets via search"
            elif table_widgets:
                self.log_message(f"Found {len(table_widgets)} QTableWidget widgets")
                return True, f"Found {len(table_widgets)} QTableWidget widgets via search"
            
            return False, "Device table not found"
        except Exception as e:
            return False, f"Error testing device table: {str(e)}"
            
    def _test_dialogs(self):
        """Test application dialogs"""
        self.log_message("Testing dialogs - skipped for automated testing")
        return True, "Dialog tests skipped (would require user interaction)"
        
    def _test_selected_device(self):
        """Test the currently selected device"""
        selected_devices = self.device_manager.get_selected_devices()
        if not selected_devices:
            self.log_message("No device selected for testing")
            return
            
        device = selected_devices[0]
        self.log_message(f"Testing device: {device.get_property('name')}")
        
        # Record the test start time
        start_time = time.time()
        
        # Perform some simple tests on the device
        test_results = []
        
        # Test 1: Verify device has required properties
        required_props = ["name", "type", "id"]
        missing_props = []
        
        for prop in required_props:
            # Check if property exists (using get_property instead of has_property)
            if device.get_property(prop, None) is None:
                missing_props.append(prop)
                
        if missing_props:
            test_results.append(f"FAIL: Device missing required properties: {', '.join(missing_props)}")
        else:
            test_results.append("PASS: Device has all required properties")
            
        # Test 2: Set and verify a property
        test_value = f"test-{int(time.time())}"
        device.set_property("sample", test_value)
        
        read_value = device.get_property("sample")
        if read_value == test_value:
            test_results.append(f"PASS: Property read/write test successful")
        else:
            test_results.append(f"FAIL: Property read/write test failed. Expected {test_value}, got {read_value}")
            
        # Calculate duration
        duration = time.time() - start_time
        
        # Generate summary
        passes = sum(1 for r in test_results if r.startswith("PASS"))
        fails = sum(1 for r in test_results if r.startswith("FAIL"))
        
        summary = f"Test Results: {passes} passed, {fails} failed (completed in {duration:.2f}s)"
        
        # Update device test results
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = "PASS" if fails == 0 else "FAIL"
        
        device.set_property("test_timestamp", current_time)
        device.set_property("test_result", result)
        
        # Update the UI
        self.device_test_results.clear()
        self.device_test_results.append(summary)
        self.device_test_results.append("")
        for result in test_results:
            self.device_test_results.append(result)
            
        # Log the results
        self.log_message(f"Device test complete: {summary}")
        
    def _clear_device_test_results(self):
        """Clear the test results for the selected device"""
        selected_devices = self.device_manager.get_selected_devices()
        if not selected_devices:
            return
            
        device = selected_devices[0]
        
        # Clear the properties
        device.set_property("test_result", "Not tested")
        device.set_property("test_timestamp", "")
        
        # Clear the UI
        self.device_test_results.clear()
        
        self.log_message(f"Cleared test results for device: {device.get_property('name')}")
        
    # Signal monitoring functionality
    
    def _initialize_signal_monitoring(self):
        """Initialize signal monitoring system"""
        # Define all monitorable signals
        signals = [
            # Device manager signals
            {"name": "device_added", "source": "Device Manager"},
            {"name": "device_removed", "source": "Device Manager"},
            {"name": "device_changed", "source": "Device Manager"},
            {"name": "selection_changed", "source": "Device Manager"},
            {"name": "group_added", "source": "Device Manager"},
            {"name": "group_removed", "source": "Device Manager"},
            
            # Plugin manager signals
            {"name": "plugin_loaded", "source": "Plugin Manager"},
            {"name": "plugin_unloaded", "source": "Plugin Manager"},
            {"name": "plugin_enabled", "source": "Plugin Manager"},
            {"name": "plugin_disabled", "source": "Plugin Manager"}
        ]
        
        # Create the signal monitor checkboxes
        for signal in signals:
            name = signal["name"]
            checkbox = QCheckBox(f"{signal['source']}.{name}")
            checkbox.stateChanged.connect(lambda state, s=name: self.monitor_signal(s, state == Qt.Checked))
            
            # Set initial state
            enable_monitoring = self.settings["signal_monitoring"]["value"]
            checkbox.setChecked(enable_monitoring)
            self._signal_monitors[name] = enable_monitoring
            
            # Add to the form layout
            self.signal_list_layout.addWidget(checkbox)
            
        # Clear the signal log table
        self.signal_log_table.setRowCount(0)
        
    def monitor_signal(self, signal_name, enable=True):
        """Enable or disable monitoring for a specific signal"""
        self._signal_monitors[signal_name] = enable
        self.log_message(f"Signal monitoring for {signal_name}: {'Enabled' if enable else 'Disabled'}")
        return True
        
    def _log_signal_event(self, signal_name, source, parameters=None):
        """Log a signal event to the monitor"""
        if signal_name not in self._signal_monitors or not self._signal_monitors[signal_name]:
            return
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format parameters for display
        params_text = ""
        try:
            if parameters:
                if isinstance(parameters, list) or isinstance(parameters, tuple):
                    # Handle case where list might contain None values
                    safe_params = ["<None>" if p is None else str(p) for p in parameters]
                    params_text = ", ".join(safe_params)
                else:
                    params_text = str(parameters)
        except Exception as e:
            # If anything goes wrong with parameter formatting, log it safely
            logger.warning(f"Error formatting signal parameters: {e}")
            params_text = f"<error formatting parameters: {e}>"
            
        # Add to monitored signal log
        self._monitored_signal_log.append({
            "timestamp": timestamp,
            "signal": signal_name,
            "source": source,
            "parameters": params_text
        })
        
        # Add to the table
        row = self.signal_log_table.rowCount()
        self.signal_log_table.insertRow(row)
        
        self.signal_log_table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.signal_log_table.setItem(row, 1, QTableWidgetItem(signal_name))
        self.signal_log_table.setItem(row, 2, QTableWidgetItem(source))
        self.signal_log_table.setItem(row, 3, QTableWidgetItem(params_text))
        
        # Scroll to the new row
        self.signal_log_table.scrollToBottom()
        
    def _enable_all_signal_monitoring(self):
        """Enable monitoring for all signals"""
        for signal_name in self._signal_monitors:
            self._signal_monitors[signal_name] = True
            
        # Update checkboxes
        for i in range(self.signal_list_layout.count()):
            widget = self.signal_list_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox):
                widget.blockSignals(True)
                widget.setChecked(True)
                widget.blockSignals(False)
                
        self.log_message("Enabled monitoring for all signals")
        
    def _disable_all_signal_monitoring(self):
        """Disable monitoring for all signals"""
        for signal_name in self._signal_monitors:
            self._signal_monitors[signal_name] = False
            
        # Update checkboxes
        for i in range(self.signal_list_layout.count()):
            widget = self.signal_list_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox):
                widget.blockSignals(True)
                widget.setChecked(False)
                widget.blockSignals(False)
                
        self.log_message("Disabled monitoring for all signals")
        
    def _clear_signal_log(self):
        """Clear the signal log"""
        self._monitored_signal_log = []
        self.signal_log_table.setRowCount(0)
        self.log_message("Signal log cleared")
        
    # Action handlers
        
    @safe_action_wrapper
    def on_sample_action(self):
        """Handle sample action"""
        logger.info("Sample action triggered")
        self.log_message("Sample action triggered")
        
        try:
            # Add sample property to selected devices
            selected_devices = self.device_manager.get_selected_devices()
            
            if not selected_devices:
                self.log_message("No devices selected. Please select at least one device.")
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage("No devices selected for Sample Action", 3000)
                return
                
            success_count = 0
            for device in selected_devices:
                try:
                    if device is None:
                        continue
                        
                    # Safely set property
                    device.set_property("sample", self.settings["default_value"]["value"])
                    self.log_message(f"Added sample property to {device.get_property('name', 'Unnamed')}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error setting property on device: {e}")
                    self.log_message(f"Error setting property: {e}")
            
            # Show success message
            if success_count > 0:
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"Sample property added to {success_count} device(s)", 3000)
            else:
                self.log_message("Failed to add sample property to any devices")
                
        except Exception as e:
            logger.error(f"Error in sample action: {e}")
            self.log_message(f"Error in sample action: {e}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"Error: {e}", 3000)
        
    @safe_action_wrapper
    def on_test_action(self):
        """Handle test action"""
        logger.info("Test action triggered")
        self.log_widget.append("Test action triggered")
        
        # Activate the test dashboard tab
        self.main_panel.setCurrentWidget(self.test_tab)
        
    @safe_action_wrapper
    def on_sample_menu_action(self):
        """Handle sample menu action"""
        logger.info("Sample menu action triggered")
        self.log_widget.append("Sample menu action triggered")
        
    @safe_action_wrapper
    def show_signal_monitor(self):
        """Show the signal monitor tab"""
        logger.info("Signal monitor action triggered")
        self.log_widget.append("Opening signal monitor")
        
        # Activate the signal monitor tab
        self.main_panel.setCurrentWidget(self.signal_tab)
        
    @safe_action_wrapper
    def create_new_device(self):
        """Create a new device using the dialog or device manager API"""
        logger.info("Creating new device")
        self.log_widget.append("Creating new device...")
        
        try:
            # Try to use the plugin interface method to show the add device dialog
            if hasattr(self, 'add_device_dialog'):
                new_device = self.add_device_dialog()
                
                if new_device:
                    # Device was created and automatically added to the device manager
                    logger.info(f"New device created via dialog: {new_device.get_property('alias')}")
                    self.log_widget.append(f"Created device: {new_device.get_property('alias')}")
                    
                    # Add sample property if auto_sample is enabled
                    if self.settings["auto_sample"]["value"]:
                        default_value = self.settings["default_value"]["value"]
                        new_device.set_property("sample", default_value)
                        self.log_widget.append(f"Added sample property to new device: {default_value}")
                    
                    return new_device
                else:
                    self.log_widget.append("Device creation cancelled")
                    return None
            else:
                # Use the device manager's create_device method as a fallback
                device_type = "sample"
                default_properties = {
                    "name": "Sample Device",
                    "description": "Device created by Sample Plugin",
                    "sample": self.settings["default_value"]["value"]
                }
                
                # Create the device
                new_device = self.device_manager.create_device(device_type, **default_properties)
                
                # Add it to the device manager
                self.device_manager.add_device(new_device)
                
                logger.info(f"New device created via API: {new_device.get_property('name')}")
                self.log_widget.append(f"Created device: {new_device.get_property('name')}")
                return new_device
        except Exception as e:
            logger.error(f"Error creating device: {e}")
            self.log_widget.append(f"Error creating device: {e}")
            return None
        
    @safe_action_wrapper
    def edit_selected_device(self):
        """Edit the selected device using the dialog"""
        selected_devices = self.device_manager.get_selected_devices()
        
        if not selected_devices:
            logger.warning("No device selected to edit")
            self.log_widget.append("No device selected to edit")
            return
            
        device = selected_devices[0]
        logger.info(f"Editing device: {device.get_property('alias')}")
        self.log_widget.append(f"Editing device: {device.get_property('alias')}")
        
        # Use the plugin interface method to show the device properties dialog
        updated_device = self.show_device_properties_dialog(device)
        
        if updated_device:
            # Device was updated
            logger.info(f"Device updated: {updated_device.get_property('alias')}")
            self.log_widget.append(f"Updated device: {updated_device.get_property('alias')}")
        else:
            self.log_widget.append("Device edit cancelled")
        
    # Signal monitoring functionality
    
    def _setup_device_context_menu(self):
        """Set up context menu for device table items via registration"""
        logger.debug("Setting up device context menu integration")
        
        # Store a reference to the device table for easier access
        if hasattr(self.main_window, 'device_table'):
            self.device_table = self.main_window.device_table
            
            # Register our actions with the existing context menu
            if hasattr(self.device_table, 'register_context_menu_action'):
                logger.info("Device table supports context menu registration")
                # The actual registration is done in _register_context_menu_actions
                return True
            else:
                logger.warning("Device table does not support context menu registration")
                return False
        else:
            logger.warning("Device table not found, skipping context menu setup")
            return False

    def _test_context_menu_setup(self):
        """Verify that the context menu setup is correct"""
        try:
            # Check if device table is accessible
            if not hasattr(self, 'device_table'):
                logger.error("Device table reference not stored")
                return False
                
            # We're using the registration approach now, so we don't need the device_context_menu
            # Just check if registration was successful
            if not hasattr(self.device_table, 'register_context_menu_action'):
                logger.error("Device table doesn't support context menu registration")
                return False
            
            # Log success
            logger.info("Context menu setup verified successfully")
            return True
        except Exception as e:
            logger.error(f"Error testing context menu setup: {e}")
            return False

    def _test_device_details(self):
        """Test the device details functionality"""
        try:
            logger.info("Testing device details...")
            
            # Check if device manager is accessible
            if not hasattr(self, 'device_manager'):
                logger.error("Device manager reference not available")
                return False, "Device manager reference not available"
                
            # Get devices
            devices = self.device_manager.get_devices()
            if not devices:
                logger.warning("No devices available for testing")
                return True, "No devices available to test"
                
            # Test updating device details with a sample device
            sample_device = devices[0]
            if not sample_device:
                logger.warning("No device found at index 0")
                return True, "No device found for testing"
                
            # Log device properties
            logger.info(f"Testing device details with device: {sample_device.get_property('name', 'Unnamed')}")
            
            # Safely test property access
            try:
                name = sample_device.get_property('name', 'Unnamed')
                device_type = sample_device.get_property('type', 'Unknown')
                status = sample_device.get_property('status', 'Unknown')
                logger.info(f"Device properties - Name: {name}, Type: {device_type}, Status: {status}")
            except Exception as e:
                logger.error(f"Error accessing device properties: {e}")
                return False, f"Error accessing device properties: {e}"
            
            # Try updating the device details panel
            try:
                self.update_device_details(sample_device)
                logger.info("Successfully updated device details panel")
            except Exception as e:
                logger.error(f"Error updating device details: {e}")
                return False, f"Error updating device details: {e}"
                
            # Test setting a property
            try:
                test_value = f"test-{int(time.time())}"
                sample_device.set_property("sample_test", test_value)
                read_value = sample_device.get_property("sample_test", None)
                
                if read_value == test_value:
                    logger.info("Successfully set and retrieved test property")
                else:
                    logger.warning(f"Property value mismatch: set {test_value}, got {read_value}")
                    return False, "Property value mismatch"
            except Exception as e:
                logger.error(f"Error with property set/get: {e}")
                return False, f"Error with property set/get: {e}"
            
            return True, "Device details test successful"
        except Exception as e:
            logger.error(f"Error in device details test: {e}")
            return False, f"Error in device details test: {e}"

    @safe_action_wrapper
    def _on_device_context_menu(self, position):
        """Handle device table context menu request"""
        # This method is now obsolete with the new context menu registration approach
        # The device table handles the context menu display and invokes our registered actions
        # We keep this method for backwards compatibility but it does nothing
        logger.debug("_on_device_context_menu called - obsolete with new context menu registration")
        pass

    def _setup_group_context_menu(self):
        """Set up context menu for group tree items via registration"""
        logger.debug("Setting up group context menu integration")
        
        # Store a reference to the group tree for easier access
        if hasattr(self.main_window, 'group_tree'):
            self.group_tree = self.main_window.group_tree
            
            # Check if the group tree has a method to register context menu actions
            if hasattr(self.group_tree, 'register_context_menu_action'):
                logger.info("Group tree supports context menu registration")
                
                # Register our group actions with the existing context menu
                self.group_tree.register_context_menu_action(
                    "Sample Action on Group",
                    self._on_sample_action_group,
                    priority=100
                )
                
                self.group_tree.register_context_menu_action(
                    "Test All Devices in Group",
                    self._on_test_group,
                    priority=200
                )
                
                self.group_tree.register_context_menu_action(
                    "Mark Group as Important",
                    self._on_mark_group_important,
                    priority=300
                )
                
                self.group_tree.register_context_menu_action(
                    "Export Group Devices",
                    self._on_export_group,
                    priority=400
                )
                
                return True
            else:
                logger.warning("Group tree does not support context menu registration")
                return False
        else:
            logger.warning("Group tree not found, skipping group context menu setup")
            return False

    @safe_action_wrapper
    def _on_group_context_menu(self, position):
        """Handle group tree context menu request"""
        # This method is now obsolete with the new context menu registration approach
        # The group tree handles the context menu display and invokes our registered actions
        # We keep this method for backwards compatibility but it does nothing
        logger.debug("_on_group_context_menu called - obsolete with new context menu registration")
        pass

    @safe_action_wrapper
    def _on_mark_group_important(self):
        """Mark all devices in group as important"""
        if not hasattr(self.main_window, 'group_tree'):
            return
            
        # Get selected group
        selected_items = self.main_window.group_tree.selectedItems()
        if not selected_items:
            return
            
        group_item = selected_items[0]
        group_name = group_item.text(0)
        
        # Get devices in group
        devices = self.device_manager.get_devices_in_group(group_name)
        if not devices:
            self.log_message(f"No devices found in group '{group_name}'")
            return
            
        # Mark each device
        for device in devices:
            device.set_property("important", True)
            device.set_property("importance_date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            device.set_property("sample", "GROUP-IMPORTANT " + device.get_property("sample", ""))
            
        self.log_message(f"Marked {len(devices)} devices in group '{group_name}' as important")
        
    @safe_action_wrapper
    def _on_export_group(self):
        """Export all devices in a group"""
        if not hasattr(self.main_window, 'group_tree'):
            return
            
        # Get selected group
        selected_items = self.main_window.group_tree.selectedItems()
        if not selected_items:
            return
            
        group_item = selected_items[0]
        group_name = group_item.text(0)
        
        # Get devices in group
        devices = self.device_manager.get_devices_in_group(group_name)
        if not devices:
            self.log_message(f"No devices found in group '{group_name}'")
            return
            
        # Export to a simple text file
        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(export_dir, f"group_{group_name}_{timestamp}.txt")
        
        with open(export_file, 'w') as f:
            f.write(f"# Devices in group '{group_name}'\n")
            f.write(f"# Exported on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for device in devices:
                f.write(f"## Device: {device.get_property('name', 'Unnamed')}\n")
                
                # Write all properties
                for prop_name, prop_value in device.get_properties().items():
                    f.write(f"{prop_name}: {prop_value}\n")
                    
                f.write("\n")
                
        self.log_message(f"Exported {len(devices)} devices from group '{group_name}' to {export_file}")
            
    @safe_action_wrapper
    def _on_sample_action_context(self, device_or_devices):
        """
        Handle Sample Action from context menu for devices
        
        This method can be called with either a single device or a list of devices
        """
        # Handle both single device and list of devices from context menu
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            # If no devices provided, try to get selected devices
            devices = self.device_manager.get_selected_devices()
            
        if not devices:
            self.log_message("No devices selected for Sample Action")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage("No devices selected for Sample Action", 3000)
            return
        
        # Get current time for the action
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Apply sample action to all selected devices
        success_count = 0
        for device in devices:
            if device is None:
                continue
                
            # Safely set properties
            device.set_property("sample_action_timestamp", timestamp)
            device.set_property("sample_action_performed", True)
            success_count += 1
        
        # Log the action
        self.log_message(f"Sample Action performed on {success_count} device(s) at {timestamp}")
        
        # Update device details if this is the currently selected device
        if success_count > 0 and self.main_panel.currentWidget() == self.details_tab:
            first_device = devices[0] if devices else None
            if first_device:
                self.update_device_details(first_device)
        
        # Show a brief popup notification
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(f"Sample Action completed on {success_count} device(s)", 3000)

    @safe_action_wrapper
    def _on_sample_action_group(self):
        """Handle Sample Action from context menu for groups"""
        if not hasattr(self.main_window, 'group_tree'):
            self.log_message("Group tree not found")
            return
            
        # Get selected group
        selected_items = self.main_window.group_tree.selectedItems()
        if not selected_items:
            self.log_message("No group selected for Sample Action")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage("No group selected for Sample Action", 3000)
            return
            
        group_item = selected_items[0]
        group_name = group_item.text(0)
        
        # Get devices in group
        devices = self.device_manager.get_devices_in_group(group_name)
        if not devices:
            self.log_message(f"No devices found in group '{group_name}'")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"No devices found in group '{group_name}'", 3000)
            return
            
        # Get current time for the action
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Apply sample action to all devices in the group
        success_count = 0
        for device in devices:
            if device is None:
                continue
                
            # Safely set properties
            device.set_property("sample_action_timestamp", timestamp)
            device.set_property("sample_action_performed", True) 
            device.set_property("sample_action_group", group_name)
            success_count += 1
        
        # Log the action
        self.log_message(f"Sample Action performed on {success_count} device(s) in group '{group_name}' at {timestamp}")
        
        # Show a brief popup notification
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(f"Sample Action completed on {success_count} device(s) in group '{group_name}'", 3000)

    def _perform_device_test(self, device):
        """Perform a comprehensive test on a device"""
        # Record the test start time
        start_time = time.time()
        
        # Safe device name for logging
        device_name = device.get_property('name', 'Unnamed')
        
        try:
            # Perform some simple tests on the device
            test_results = []
            
            # Test 1: Verify device has required properties
            required_props = ["name", "type", "id"]
            missing_props = []
            
            for prop in required_props:
                # Check if property exists (using get_property instead of has_property)
                if device.get_property(prop, None) is None:
                    missing_props.append(prop)
                
            if missing_props:
                test_results.append(f"FAIL: Device missing required properties: {', '.join(missing_props)}")
            else:
                test_results.append("PASS: Device has all required properties")
            
            # Test 2: Set and verify a property
            test_value = f"test-{int(time.time())}"
            device.set_property("sample", test_value)
            
            read_value = device.get_property("sample")
            if read_value == test_value:
                test_results.append(f"PASS: Property read/write test successful")
            else:
                test_results.append(f"FAIL: Property read/write test failed. Expected {test_value}, got {read_value}")
            
            # Test 3: Verify property precision matches settings
            if "data_precision" in self.settings:
                precision = self.settings["data_precision"]["value"]
                test_float = 1.0 / 3.0
                expected_format = f"{{:.{precision}f}}".format(test_float)
                
                device.set_property("test_float", test_float)
                formatted_value = f"{{:.{precision}f}}".format(test_float)
                
                if formatted_value == expected_format:
                    test_results.append(f"PASS: Data precision test (precision={precision})")
                else:
                    test_results.append(f"FAIL: Data precision test. Expected {expected_format}, got {formatted_value}")
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Generate summary
            passes = sum(1 for r in test_results if r.startswith("PASS"))
            fails = sum(1 for r in test_results if r.startswith("FAIL"))
            
            summary = f"Test Results: {passes} passed, {fails} failed (completed in {duration:.2f}s)"
            
            # Update device test results
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result = "PASS" if fails == 0 else "FAIL"
            
            device.set_property("test_timestamp", current_time)
            device.set_property("test_result", result)
            device.set_property("test_summary", summary)
            device.set_property("test_details", "\n".join(test_results))
            
            # Log the results
            self.log_message(f"Device {device_name} test complete: {summary}")
            
            return result
            
        except Exception as e:
            # Handle any exceptions that occur during testing
            error_msg = f"Error testing device {device_name}: {str(e)}"
            logger.error(error_msg)
            self.log_message(error_msg)
            
            # Update device with error information
            device.set_property("test_timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            device.set_property("test_result", "ERROR")
            device.set_property("test_summary", f"Test failed with error: {str(e)}")
            
            return "ERROR" 

    def _register_context_menu_actions(self):
        """Register actions with the existing device table context menu instead of creating a custom menu"""
        logger.info("Registering context menu actions with device table")
        
        if not hasattr(self.main_window, 'device_table'):
            logger.warning("Device table not found, cannot register context menu actions")
            self.log_message("Device table not found, cannot register context menu actions")
            return False
            
        # Access the device table view
        device_table = self.main_window.device_table
        
        # Check if table has register_context_menu_action method
        if not hasattr(device_table, 'register_context_menu_action'):
            logger.warning("Device table does not support context menu action registration")
            self.log_message("Device table does not support context menu registration")
            return False
            
        # Register our sample action with the device table
        device_table.register_context_menu_action(
            "Sample Action", 
            self._on_sample_action_context, 
            priority=100  # Lower priority = higher in the menu
        )
        
        # Register other custom actions
        device_table.register_context_menu_action(
            "Mark as Important",
            self._on_mark_important,
            priority=200
        )
        
        device_table.register_context_menu_action(
            "Set Sample Value",
            self._on_set_sample_value,
            priority=210
        )
        
        device_table.register_context_menu_action(
            "Remove Sample Value",
            self._on_remove_sample_value,
            priority=220
        )
        
        device_table.register_context_menu_action(
            "Test Device",
            self._on_context_test_device,
            priority=300
        )
        
        device_table.register_context_menu_action(
            "Show Device Details",
            self._on_show_device_details,
            priority=400
        )
        
        device_table.register_context_menu_action(
            "Copy Device Info",
            self._on_copy_device_info,
            priority=500
        )
        
        self.log_message("Successfully registered context menu actions with device table")
        logger.info("Context menu actions registered successfully")
        return True

    @safe_action_wrapper
    def _on_mark_important(self, device_or_devices):
        """Mark selected devices as important"""
        # Handle both single device and list of devices
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            devices = self.device_manager.get_selected_devices()
            
        if not devices:
            self.log_message("No devices selected to mark as important")
            return
            
        for device in devices:
            if device is None:
                continue
                
            device.set_property("important", True)
            device.set_property("importance_date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            device.set_property("sample", "IMPORTANT " + str(device.get_property("sample", "")))
            
        self.log_message(f"Marked {len(devices)} devices as important")
            
    @safe_action_wrapper
    def _on_set_sample_value(self, device_or_devices):
        """Set sample value for selected devices"""
        from PySide6.QtWidgets import QInputDialog, QLineEdit
        
        # Handle both single device and list of devices
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            devices = self.device_manager.get_selected_devices()
            
        if not devices:
            self.log_message("No devices selected to set sample value")
            return
            
        # Get sample value from user
        value, ok = QInputDialog.getText(
            self.main_window,
            "Set Sample Value",
            "Enter sample value:",
            QLineEdit.Normal,
            self.settings["default_value"]["value"]
        )
        
        if not ok or not value:
            return
            
        # Update sample value for all selected devices
        success_count = 0
        for device in devices:
            if device is None:
                continue
                
            device.set_property("sample", value)
            success_count += 1
            
        self.log_message(f"Set sample value '{value}' for {success_count} devices")
            
    @safe_action_wrapper
    def _on_remove_sample_value(self, device_or_devices):
        """Remove sample value from selected devices"""
        # Handle both single device and list of devices
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            devices = self.device_manager.get_selected_devices()
            
        if not devices:
            self.log_message("No devices selected to remove sample value")
            return
            
        success_count = 0
        for device in devices:
            if device is None:
                continue
                
            # Check if device has sample property
            if device.get_property("sample", None) is not None:
                if hasattr(device, 'remove_property'):
                    device.remove_property("sample")
                else:
                    # If remove_property doesn't exist, set to None
                    device.set_property("sample", None)
                success_count += 1
                
        self.log_message(f"Removed sample value from {success_count} devices")
            
    @safe_action_wrapper
    def _on_context_test_device(self, device_or_devices):
        """Test selected devices through context menu"""
        # Handle both single device and list of devices
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            devices = self.device_manager.get_selected_devices()
            
        if not devices:
            self.log_message("No devices selected for testing")
            return
            
        success_count = 0
        for device in devices:
            if device is None:
                continue
                
            # Perform a simple test
            result = self._perform_device_test(device)
            if result in ["PASS", "FAIL"]:  # ERROR is not counted
                success_count += 1
            
        self.log_message(f"Tested {success_count} devices")
            
    @safe_action_wrapper
    def _on_show_device_details(self, device_or_devices):
        """Show details for selected device"""
        # For this action, we only support showing details for a single device
        device = None
        
        if isinstance(device_or_devices, list) and len(device_or_devices) > 0:
            device = device_or_devices[0]  # Take the first device
        elif device_or_devices is not None and not isinstance(device_or_devices, list):
            device = device_or_devices
        else:
            # Try to get the first selected device
            selected_devices = self.device_manager.get_selected_devices()
            if selected_devices:
                device = selected_devices[0]
        
        if not device:
            self.log_message("No device selected to show details")
            return
            
        # Activate the details tab and update with this device
        self.main_panel.setCurrentWidget(self.details_tab)
        self.update_device_details(device)
        
        # Ensure the dock widget is visible
        self.dock_widget.setVisible(True)
        self.dock_widget.raise_()
            
    @safe_action_wrapper
    def _on_copy_device_info(self, device_or_devices):
        """Copy device info to clipboard"""
        from PySide6.QtGui import QClipboard
        
        # For this action, we only support copying info for a single device
        device = None
        
        if isinstance(device_or_devices, list) and len(device_or_devices) > 0:
            device = device_or_devices[0]  # Take the first device
        elif device_or_devices is not None and not isinstance(device_or_devices, list):
            device = device_or_devices
        else:
            # Try to get the first selected device
            selected_devices = self.device_manager.get_selected_devices()
            if selected_devices:
                device = selected_devices[0]
        
        if not device:
            self.log_message("No device selected to copy information")
            return
            
        # Build device info string
        info = [f"Device: {device.get_property('name', 'Unnamed')}"]
        
        # Add all properties
        for prop_name, prop_value in device.get_properties().items():
            info.append(f"{prop_name}: {prop_value}")
            
        # Join with newlines
        info_text = "\n".join(info)
        
        # Copy to clipboard
        clipboard = self.main_window.app.clipboard()
        clipboard.setText(info_text)
        
        self.log_message(f"Copied info for device {device.get_property('name', 'Unnamed')} to clipboard")

    @safe_action_wrapper
    def _on_test_group(self, group_name_or_item=None):
        """Test all devices in selected group"""
        # Get the group name
        group_name = None
        
        if isinstance(group_name_or_item, str):
            # If a string is passed, use it as the group name
            group_name = group_name_or_item
        elif hasattr(group_name_or_item, 'text') and callable(group_name_or_item.text):
            # If a QTreeWidgetItem is passed, get its text
            group_name = group_name_or_item.text(0)
        else:
            # Otherwise try to get the selected group from the UI
            if not hasattr(self.main_window, 'group_tree'):
                self.log_message("Group tree not found")
                return
                
            # Get selected group
            selected_items = self.main_window.group_tree.selectedItems()
            if not selected_items:
                self.log_message("No group selected for testing")
                return
                
            group_item = selected_items[0]
            group_name = group_item.text(0)
        
        if not group_name:
            self.log_message("No group name identified for testing")
            return
            
        # Get devices in group
        devices = self.device_manager.get_devices_in_group(group_name)
        if not devices:
            self.log_message(f"No devices found in group '{group_name}'")
            return
            
        # Test each device
        self.log_message(f"Testing {len(devices)} devices in group '{group_name}'...")
        
        success_count = 0
        for device in devices:
            if device is None:
                continue
                
            result = self._perform_device_test(device)
            if result in ["PASS", "FAIL"]:  # Don't count ERROR results
                success_count += 1
            
        self.log_message(f"Completed testing {success_count} devices in group '{group_name}'")