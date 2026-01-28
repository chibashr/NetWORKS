#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Network Scanner Plugin for NetWORKS

This plugin adds network scanning capabilities to NetWORKS using Nmap.
It allows scanning network ranges and adding discovered devices to the
device inventory.
"""

from loguru import logger
import sys
import os
import time
import datetime
import ipaddress
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

# Try to import nmap with error handling
try:
    import nmap
    HAS_NMAP = True
except ImportError as e:
    logger.error(f"Could not import python-nmap: {e}")
    HAS_NMAP = False

# Try to import psutil for interface detection (preferred, wheels available on most platforms)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError as e:
    logger.error(f"Could not import psutil for interface detection: {e}")
    HAS_PSUTIL = False

from PySide6.QtWidgets import (
    QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QDockWidget,
    QPushButton, QTabWidget, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QGridLayout, QFormLayout, QGroupBox, QCheckBox, QComboBox,
    QSplitter, QProgressBar, QMessageBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QDialog, QDialogButtonBox, QMenu, QFileDialog,
    QRadioButton, QInputDialog, QHeaderView, QSizePolicy, QListWidget,
    QListWidgetItem, QStyle, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QThread, QObject
from PySide6.QtGui import QIcon, QAction, QFont, QColor, QIntValidator


# Import the plugin interface (project root when run from plugin package)
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _root not in sys.path:
    sys.path.insert(0, _root)
from src.core.plugin_interface import PluginInterface
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.material_icons import material_icon

from .scanner_worker import ScannerWorker
from .nmap_detection import find_nmap_executable, test_python_nmap_works
from ..ui.panel import build_scan_panel
from ..ui.scan_dialog import show_scan_dialog
from ..ui.profile_manager_dialog import show_scan_type_manager_dialog
from ..ui.settings_pages import get_settings_pages as get_settings_pages_impl
from ..utils.helpers import safe_action_wrapper




class NetworkScannerPlugin(PluginInterface):
    """
    Network Scanner Plugin for NetWORKS
    
    This plugin provides network scanning capabilities for discovering
    and adding devices to the NetWORKS inventory.
    """
    
    # Custom signals
    scan_started = Signal(str)  # network_range
    scan_progress = Signal(int, int)  # current, total
    scan_device_found = Signal(object)  # device
    scan_completed = Signal(dict)  # results_dict
    scan_error = Signal(str)  # error_message
    
    def __init__(self):
        """Initialize the plugin"""
        super().__init__()
        self.name = "Network Scanner"
        self.version = "10.6"
        self.description = "Scan network segments for devices and add them to NetWORKS"
        self.author = "NetWORKS Team"
        
        # Internal state
        self._connected_signals = set()  # Track connected signals for safe disconnection
        self._scanner_thread = None
        self._scanner_worker = None
        self._is_scanning = False
        self._scan_results = {}
        self._scan_log = []
        self._batch_scan_queue = []
        self._batch_scan_total = 0
        self._batch_scan_index = 0
        self._batch_scan_current = None
        self._batch_scan_active = False
        self._batch_scan_slots = []  # for parallel batch: list of {"thread", "worker", "target", "index"}
        
        # Plugin settings
        self.settings = {
            "scan_profiles": {
                "name": "Scan Profiles",
                "description": "Customizable scan profiles with predefined settings",
                "type": "json",
                "default": {
                    "quick": {"name": "Quick Scan", "description": "Fast ping scan to discover hosts (minimal network impact)", "arguments": "-sn -T4", "timeout": 120},
                    "standard": {"name": "Standard Scan", "description": "Balanced scan with basic port scanning and OS detection", "arguments": "-sn -F -O -T4", "timeout": 300},
                    "comprehensive": {"name": "Comprehensive Scan", "description": "In-depth scan with full port scanning and OS fingerprinting", "arguments": "-sS -p 1-1000 -O -A -T4", "timeout": 600},
                    "stealth": {"name": "Stealth Scan", "description": "Quiet TCP SYN scan with minimal footprint", "arguments": "-sS -T2", "timeout": 480},
                    "service": {"name": "Service Detection", "description": "Focused on detecting services on common ports", "arguments": "-sV -p 21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080 -T4", "timeout": 480}
                },
                "value": {
                    "quick": {"name": "Quick Scan", "description": "Fast ping scan to discover hosts (minimal network impact)", "arguments": "-sn -T4", "timeout": 120},
                    "standard": {"name": "Standard Scan", "description": "Balanced scan with basic port scanning and OS detection", "arguments": "-sn -F -O -T4", "timeout": 300},
                    "comprehensive": {"name": "Comprehensive Scan", "description": "In-depth scan with full port scanning and OS fingerprinting", "arguments": "-sS -p 1-1000 -O -A -T4", "timeout": 600},
                    "stealth": {"name": "Stealth Scan", "description": "Quiet TCP SYN scan with minimal footprint", "arguments": "-sS -T2", "timeout": 480},
                    "service": {"name": "Service Detection", "description": "Focused on detecting services on common ports", "arguments": "-sV -p 21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080 -T4", "timeout": 480}
                }
            },
            "scan_type": {
                "name": "Default Scan Type",
                "description": "The default scan type to use",
                "type": "choice",
                "default": "quick",
                "value": "quick",
                "choices": ["quick", "standard", "comprehensive", "stealth", "service"]
            },
            "preferred_interface": {
                "name": "Preferred Interface",
                "description": "The preferred network interface to use for scanning",
                "type": "choice",
                "default": "",
                "value": "",
                "choices": []  # Will be populated during initialization
            },
            "scan_timeout": {
                "name": "Default Scan Timeout",
                "description": "Default timeout in seconds for scan operations",
                "type": "int",
                "default": 600,
                "value": 600
            },
            "use_sudo": {
                "name": "Use Elevated Permissions",
                "description": "Run scans with elevated permissions (improves accuracy but requires admin/sudo)",
                "type": "bool",
                "default": False,
                "value": False
            },
            "custom_scan_args": {
                "name": "Custom Scan Arguments",
                "description": "Advanced: Custom nmap arguments (use with caution)",
                "type": "string",
                "default": "",
                "value": ""
            },
            "auto_tag": {
                "name": "Auto Tag",
                "description": "Automatically tag discovered devices",
                "type": "bool",
                "default": True,
                "value": True
            },
            "batch_scan_threads": {
                "name": "Batch scan threads",
                "description": "Number of devices to scan in parallel during batch scans (1 = sequential)",
                "type": "int",
                "default": 1,
                "value": 1
            }
        }
        
        # Create UI components
        self._create_actions()
        self._create_widgets()

    def _check_nmap_executable(self):
        """
        Locate the nmap executable using shared detection helpers.

        Returns:
            str or None: Absolute or discovered path to the nmap executable,
            or None if not found.
        """
        try:
            return find_nmap_executable()
        except Exception as exc:
            logger.error(f"Error while checking for nmap executable: {exc}")
            return None
        
    def initialize(self, app, plugin_info):
        """Initialize the plugin"""
        try:
            logger.info(f"Initializing {self.name} v{self.version}")
            
            # Store app reference and set up plugin interface
            self.app = app
            self.device_manager = app.device_manager
            self.main_window = app.main_window
            self.config = app.config
            self.plugin_info = plugin_info

            # Set toolbar action icons (main_window required for material_icon)
            self._set_action_icons()

            # Initialize nmap availability flag
            self.nmap_available = False
            
            # Check if nmap module was successfully imported
            if not HAS_NMAP:
                warning_msg = (
                    "The python-nmap module is not available. Network scanning features will be disabled.\n\n"
                    "To enable scanning, install python-nmap using:\n"
                    "pip install python-nmap"
                )
                logger.warning(warning_msg)
                if hasattr(self, "main_window") and self.main_window:
                    QMessageBox.warning(
                        self.main_window,
                        "Network Scanner Warning",
                        warning_msg
                    )
                
            # Check if nmap is available
            try:
                # Check if the nmap executable is available and get its path
                nmap_path = self._check_nmap_executable()
                
                if not nmap_path:
                    warning_msg = (
                        "The nmap executable was not found on your system.\n\n"
                        "Network scanning features will be disabled until nmap is installed.\n\n"
                        "To install nmap:\n"
                        "  • Windows: Download from https://nmap.org/download.html\n"
                        "    (Typical installation: C:\\Program Files\\Nmap\\nmap.exe)\n"
                        "  • macOS: brew install nmap\n"
                        "  • Linux: sudo apt install nmap (or equivalent)\n\n"
                        "After installing, make sure nmap is accessible (either in your system PATH\n"
                        "or in a standard installation location) and restart NetWORKS."
                    )
                    logger.warning(warning_msg)
                    if hasattr(self, "main_window") and self.main_window:
                        QMessageBox.warning(
                            self.main_window,
                            "Network Scanner Warning",
                            warning_msg
                        )
                    # Don't raise - allow plugin to load but disable scanning
                    self.nmap_available = False
                    return
                
                # Store the nmap path for later use
                self.nmap_path = nmap_path
                logger.info(f"Nmap executable found at: {nmap_path}")
                
                # Ensure we have an absolute path and normalize it
                if not os.path.isabs(nmap_path):
                    nmap_path = os.path.abspath(nmap_path)
                    self.nmap_path = nmap_path
                    logger.debug(f"Converted to absolute path: {nmap_path}")
                
                # Normalize the path (handle Windows path separators, etc.)
                nmap_path = os.path.normpath(nmap_path)
                self.nmap_path = nmap_path
                
                # Verify the path still exists
                if not os.path.exists(nmap_path):
                    warning_msg = (
                        f"Nmap was found at {nmap_path} but the file no longer exists.\n\n"
                        "Network scanning features will be disabled.\n\n"
                        "Please reinstall nmap or check the installation."
                    )
                    logger.warning(warning_msg)
                    if hasattr(self, "main_window") and self.main_window:
                        QMessageBox.warning(
                            self.main_window,
                            "Network Scanner Warning",
                            warning_msg
                        )
                    self.nmap_available = False
                    return
                
                # Log additional diagnostic information and add to PATH if needed
                import platform
                nmap_dir = os.path.dirname(nmap_path)
                # Normalize the directory path as well
                nmap_dir = os.path.normpath(nmap_dir)
                current_path = os.environ.get("PATH", "")
                
                # CRITICAL: Add nmap directory to PATH BEFORE creating PortScanner
                # python-nmap looks for nmap in PATH when it initializes
                # Normalize PATH entries for comparison
                path_entries = [os.path.normpath(p) for p in current_path.split(os.pathsep) if p.strip()]
                
                if nmap_dir and nmap_dir not in path_entries:
                    logger.info(f"Nmap directory ({nmap_dir}) is not in system PATH - adding it now")
                    # Add to the beginning of PATH so it's found first
                    os.environ["PATH"] = nmap_dir + os.pathsep + current_path
                    logger.debug(f"Updated PATH to include nmap directory. New PATH starts with: {nmap_dir}")
                    # Verify it was added
                    updated_path = os.environ.get("PATH", "")
                    if nmap_dir in updated_path:
                        logger.debug("Successfully verified nmap directory is now in PATH")
                    else:
                        logger.warning(f"Warning: nmap directory may not have been added to PATH correctly")
                else:
                    logger.info(f"Nmap directory ({nmap_dir}) is already in system PATH")
                
                # Now try to create a scanner - nmap should be in PATH now
                # This is especially important on Windows where nmap might not be in PATH
                logger.debug("Creating nmap.PortScanner() instance...")
                try:
                    test_scanner = nmap.PortScanner()
                    logger.debug("nmap.PortScanner() created successfully")
                    
                    # Try to set the nmap path directly if python-nmap supports it
                    if hasattr(test_scanner, 'nmap_path'):
                        test_scanner.nmap_path = nmap_path
                        logger.debug(f"Set python-nmap path attribute to: {nmap_path}")
                except Exception as port_scanner_error:
                    # If PortScanner creation fails, it might be because python-nmap
                    # checked PATH before we modified it. Try to work around this.
                    error_msg = str(port_scanner_error).lower()
                    if 'not found' in error_msg or 'path' in error_msg:
                        logger.warning(f"PortScanner creation failed: {port_scanner_error}")
                        logger.info("Attempting to work around PATH issue...")
                        
                        # Try creating PortScanner again - PATH should be updated now
                        # Sometimes python-nmap caches PATH, so we need to force it
                        try:
                            test_scanner = nmap.PortScanner()
                            logger.info("Successfully created PortScanner on retry")
                        except Exception as retry_error:
                            # If it still fails, re-raise the original error
                            logger.error(f"PortScanner creation failed even after PATH update: {retry_error}")
                            raise port_scanner_error
                    else:
                        # Some other error, re-raise it
                        raise
                
                # Actually test if python-nmap can use nmap by trying to get version
                try:
                    # Try a simple operation to verify python-nmap can use nmap
                    # We'll use the scanner's command_line method or try a minimal scan
                    # But first, let's just verify the scanner was created successfully
                    logger.debug("Nmap Python module initialized successfully")
                    
                    # Try to verify python-nmap can actually execute nmap
                    # This is a more reliable test than just checking if the file exists
                    test_result = test_python_nmap_works(nmap_path)
                    if not test_result:
                        warning_msg = (
                            f"Nmap was found at {nmap_path}, but python-nmap cannot execute it.\n\n"
                            "This may be due to:\n"
                            "  • Permission issues\n"
                            "  • Missing dependencies\n"
                            "  • Corrupted nmap installation\n\n"
                            "Try reinstalling nmap or check the logs for more details."
                        )
                        logger.warning(warning_msg)
                        if hasattr(self, "main_window") and self.main_window:
                            QMessageBox.warning(
                                self.main_window,
                                "Network Scanner Warning",
                                warning_msg
                            )
                        self.nmap_available = False
                        return
                    
                    logger.info("Nmap is available and ready to use")
                    self.nmap_available = True
                    
                except Exception as test_error:
                    logger.error(f"Failed to verify python-nmap can use nmap: {test_error}")
                    warning_msg = (
                        f"Nmap was found but cannot be used by python-nmap: {str(test_error)}\n\n"
                        "Network scanning features will be disabled.\n\n"
                        "Try reinstalling nmap or check the logs for more details."
                    )
                    logger.warning(warning_msg)
                    if hasattr(self, "main_window") and self.main_window:
                        QMessageBox.warning(
                            self.main_window,
                            "Network Scanner Warning",
                            warning_msg
                        )
                    self.nmap_available = False
                    return
                    
            except Exception as e:
                # Provide more helpful error message
                error_str = str(e)
                nmap_path_info = ""
                if hasattr(self, 'nmap_path') and self.nmap_path:
                    nmap_path_info = f"\n\nNmap was found at: {self.nmap_path}\n"
                    nmap_dir = os.path.dirname(self.nmap_path)
                    current_path = os.environ.get("PATH", "")
                    if nmap_dir not in current_path.split(os.pathsep):
                        nmap_path_info += f"However, the nmap directory ({nmap_dir}) is not in PATH.\n"
                        nmap_path_info += "The plugin attempted to add it, but python-nmap may have already initialized.\n"
                        nmap_path_info += "Try restarting NetWORKS after ensuring nmap is installed."
                
                warning_msg = (
                    f"Nmap initialization failed: {error_str}{nmap_path_info}\n\n"
                    "Network scanning features will be disabled.\n\n"
                    "To fix this:\n"
                    "1. Install the nmap executable (see https://nmap.org/download.html)\n"
                    "2. Make sure nmap is in your system PATH, or install it in a standard location:\n"
                    "   • Windows: C:\\Program Files\\Nmap\\nmap.exe\n"
                    "3. Restart NetWORKS"
                )
                logger.warning(warning_msg)
                logger.debug(f"Current PATH: {os.environ.get('PATH', '')}")
                if hasattr(self, 'nmap_path'):
                    logger.debug(f"Found nmap at: {self.nmap_path}")
                self.nmap_available = False
                if hasattr(self, "main_window") and self.main_window:
                    QMessageBox.warning(
                        self.main_window,
                        "Network Scanner Warning",
                        warning_msg
                    )
            
            # Update network interfaces
            self._update_interface_choices()
            
            # Update the interface dropdown if it exists already
            if hasattr(self, "interface_combo") and self.interface_combo is not None:
                self.interface_combo.clear()
                self.interface_combo.addItems(self.settings["preferred_interface"]["choices"])
                if self.settings["preferred_interface"]["value"] in self.settings["preferred_interface"]["choices"]:
                    self.interface_combo.setCurrentText(self.settings["preferred_interface"]["value"])
                # Set a default network range based on the selected interface
                selected_if_text = self.interface_combo.currentText()
                if selected_if_text and selected_if_text != "Any (default)" and hasattr(self, "network_range_edit"):
                    self._update_network_range_from_interface(0)  # 0 is dummy index

            # Refresh group choices if available
            if hasattr(self, "group_combo") and self.group_combo is not None:
                self._refresh_group_choices()
                self._update_group_scan_ui_state()
            
            # Initialize threading system
            self._initialize_scanner()
            
            # We're going to defer UI setup a bit to allow the main window to fully initialize
            QTimer.singleShot(300, self._setup_device_context_menu)
            
            # Connect to application signals
            QTimer.singleShot(500, self._connect_signals)
            
            # Mark plugin as initialized
            self._initialized = True
            
            logger.info(f"{self.name} initialization complete")
            return True
        except Exception as e:
            error_msg = f"Plugin initialization failed: {e}"
            logger.error(error_msg, exc_info=True)
            # Try to show a message box if we have a main window
            try:
                if hasattr(self, "main_window") and self.main_window:
                    QMessageBox.critical(
                        self.main_window,
                        f"{self.name} Initialization Failed",
                        f"The plugin could not be initialized.\n\nError: {str(e)}"
                    )
            except Exception:
                pass  # If we can't show a message box, just continue
                
            # Re-raise the exception to signal failure
            raise
        
    def _connect_to_signal(self, signal, slot, signal_name):
        """Connect to a signal and track the connection"""
        if signal and slot:
            try:
                signal.connect(slot)
                self._connected_signals.add((signal, slot, signal_name))
                logger.debug(f"Connected to signal: {signal_name}")
                return True
            except Exception as e:
                logger.error(f"Error connecting to signal {signal_name}: {e}")
                return False
        return False
    
    def _connect_signals(self):
        """Connect to application signals"""
        # Connect to device manager signals
        self._connect_to_signal(
            self.device_manager.device_added, 
            self.on_device_added,
            "device_added"
        )
        
        self._connect_to_signal(
            self.device_manager.device_removed,
            self.on_device_removed,
            "device_removed"
        )
        
        self._connect_to_signal(
            self.device_manager.device_changed,
            self.on_device_changed,
            "device_changed"
        )

        self._connect_to_signal(
            self.device_manager.group_added,
            self._refresh_group_choices,
            "group_added"
        )
        
        self._connect_to_signal(
            self.device_manager.group_removed,
            self._refresh_group_choices,
            "group_removed"
        )
        
        self._connect_to_signal(
            self.device_manager.group_changed,
            self._refresh_group_choices,
            "group_changed"
        )

        self._connect_to_signal(
            self.device_manager.selection_changed,
            self.on_device_selected,
            "selection_changed"
        )

        # Sync UI with current state (groups may have been loaded before we connected)
        self._refresh_group_choices()
        self._update_selected_devices_ui()
        
    def cleanup(self):
        """Clean up the plugin"""
        logger.info(f"Cleaning up {self.name}")
        
        # Stop any running scan first
        self.stop_scan()
        
        # Safe disconnection function
        def safe_disconnect(signal, handler=None, signal_name=""):
            """Safely disconnect a signal handler"""
            if not signal:
                logger.debug(f"Signal object is None for {signal_name}, skipping disconnect")
                return False
                
            try:
                if handler:
                    # Try with handler
                    signal.disconnect(handler)
                else:
                    # Try to disconnect all connections
                    try:
                        signal.disconnect()
                    except TypeError:
                        # If disconnect() fails, the signal might require a handler
                        pass
                return True
            except Exception as e:
                # This is expected sometimes due to how Qt handles signals
                logger.debug(f"Non-critical: Failed to disconnect {signal_name}: {e}")
                return False
        
        # Disconnect all tracked signals
        for signal, slot, signal_name in list(self._connected_signals):
            safe_disconnect(signal, slot, signal_name)
            
        # Clear the tracked signals
        self._connected_signals.clear()
        
        # Clean up any running scan threads
        self._cleanup_previous_scan()
        
        # Null out references that might cause reference cycles
        self.app = None
        self.device_manager = None
        self.main_window = None
        self.config = None
                
        logger.info(f"{self.name} cleanup complete")
        
    def _create_actions(self):
        """Create plugin actions"""
        self.scan_action = QAction("Scan Network")
        self.scan_action.triggered.connect(self.on_scan_action)
        
        self.scan_selected_action = QAction("Scan from Selected Device")
        self.scan_selected_action.triggered.connect(self.on_scan_selected_action)
        
        # Add a scan type manager action for toolbar
        self.scan_type_manager_action = QAction("Scan Type Manager")
        self.scan_type_manager_action.setToolTip("Manage scan profiles and types")
        self.scan_type_manager_action.triggered.connect(self.on_scan_type_manager_action)
        self._set_action_icons()

    def _set_action_icons(self):
        """Set icons on toolbar actions. Requires main_window (called from initialize())."""
        if not getattr(self, "main_window", None):
            return
        self.scan_action.setIcon(material_icon("refresh", self.main_window, QStyle.SP_BrowserReload))
        self.scan_selected_action.setIcon(material_icon("play_arrow", self.main_window, QStyle.SP_ArrowRight))
        self.scan_type_manager_action.setIcon(material_icon("tune", self.main_window, QStyle.SP_FileDialogDetailedView))

    def _create_widgets(self):
        """Create plugin widgets (delegated to ui.panel)."""
        build_scan_panel(self)

    def _initialize_scanner(self):
        """Initialize the scanner thread and worker"""
        # We don't create the worker or thread here
        # These will be created on-demand when a scan is started
        self._scanner_thread = None
        self._scanner_worker = None
        
        # Just note that we're ready for scanning
        logger.debug("Scanner thread system initialized")
        
    def _setup_device_context_menu(self):
        """Set up context menu integration with device table"""
        # Defer context menu setup to a point when UI components are fully initialized
        # Use a QTimer to schedule this after the UI is fully loaded
        QTimer.singleShot(500, self._register_context_menu_actions)
        
    def _register_context_menu_actions(self):
        """Register context menu actions for device table"""
        try:
            # First try to get the device table directly from the main window
            if not hasattr(self.main_window, 'device_table'):
                logger.warning("Device table not found, cannot register context menu actions")
                return
                
            device_table = self.main_window.device_table
            
            # Check if table has register_context_menu_action method
            if not hasattr(device_table, 'register_context_menu_action'):
                logger.warning("Device table does not support context menu action registration")
                return
                
            # Register our scan actions with the device table
            device_table.register_context_menu_action(
                "Scan Network...", 
                self._on_scan_network_action, 
                priority=151
            )
            
            device_table.register_context_menu_action(
                "Scan Interface Subnet...", 
                self._on_scan_subnet_action, 
                priority=152
            )
            
            device_table.register_context_menu_action(
                "Scan Device's Network...", 
                self._on_scan_from_device_action, 
                priority=153
            )
            
            device_table.register_context_menu_action(
                "Rescan Selected Device(s)...", 
                self._on_rescan_device_action, 
                priority=154
            )
            
            logger.debug("Successfully registered context menu actions")
            
        except Exception as e:
            logger.error(f"Error registering context menu actions: {e}", exc_info=True)
            
    def log_message(self, message):
        """Add a message to the scan log"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self._scan_log.append(log_entry)
        
        if hasattr(self, "results_text"):
            self.results_text.append(log_entry)
            
        logger.info(message)
        
    def get_dock_widgets(self):
        """Get plugin dock widgets"""
        # Panel title should match the plugin name for easy identification
        dock = QDockWidget("Network Scanner")
        dock.setWidget(self.main_widget)
        dock.setObjectName("NetworkScannerDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # Set minimum width to prevent controls from being too cramped
        self.main_widget.setMinimumWidth(300)
        
        # Return a list of tuples: (widget_name, widget, area)
        return [("Network Scanner", dock, Qt.RightDockWidgetArea)]
        
    def get_toolbar_actions(self):
        """Get actions for the toolbar"""
        return [self.scan_action, self.scan_type_manager_action]
        
    def get_menu_actions(self):
        """Get plugin menu actions"""
        return {"Network": [self.scan_action, self.scan_selected_action, self.scan_type_manager_action]}
        
    def _execute_scan(self, target_type, target_data, scan_type):
        """
        Single entry point for all scan starts. Used by panel, dialog, toolbar, and context menus.
        
        Args:
            target_type: "interface" | "custom" | "devices" | "group"
            target_data: For interface/custom, str (network_range). For devices, list of devices or dicts.
                        For group, group object.
            scan_type: Scan profile name (e.g. "quick", "standard").
        Returns:
            bool: True if scan started successfully, False otherwise.
        """
        if not getattr(self, "nmap_available", False):
            QMessageBox.warning(
                self.main_window,
                "Nmap Not Available",
                "Nmap is not available. Network scanning features are disabled.\n\n"
                "To enable scanning:\n"
                "1. Install the nmap executable (see https://nmap.org/download.html)\n"
                "2. Make sure nmap is in your system PATH\n"
                "3. Restart NetWORKS"
            )
            return False

        if target_type == "devices":
            devices = target_data if isinstance(target_data, list) else []
            if not devices:
                QMessageBox.warning(
                    self.main_window,
                    "No Devices Selected",
                    "Please select one or more devices to scan."
                )
                return False
            # Normalize to objects or dicts with ip/label; _start_batch_device_scan accepts both
            return self._start_batch_device_scan(devices, scan_type)

        if target_type == "group":
            group = target_data
            devices = self._get_group_devices(group) if group else []
            if not devices:
                QMessageBox.warning(
                    self.main_window,
                    "No Devices in Group",
                    "The selected group has no devices to scan."
                )
                return False
            return self._start_batch_device_scan(devices, scan_type)

        if target_type in ("interface", "custom"):
            network_range = (target_data or "").strip()
            if not network_range:
                QMessageBox.warning(
                    self.main_window,
                    "Missing Network Range",
                    "Please enter a network range or select a valid interface."
                )
                return False
            return self.scan_network(network_range, scan_type)

        return False

    def scan_network(self, network_range, scan_type="quick"):
        """
        Start a network scan of the specified range
        
        Args:
            network_range: The network range to scan (e.g., 192.168.1.0/24)
            scan_type: The type of scan to perform (quick, standard, comprehensive, etc.)
            
        Returns:
            bool: True if scan started successfully, False otherwise
        """
        # Check if nmap is available
        if not hasattr(self, 'nmap_available') or not self.nmap_available:
            logger.error("Cannot start scan: nmap is not available")
            if hasattr(self, "main_window") and self.main_window:
                QMessageBox.warning(
                    self.main_window,
                    "Nmap Not Available",
                    "Nmap is not available. Network scanning features are disabled.\n\n"
                    "To enable scanning:\n"
                    "1. Install the nmap executable (see https://nmap.org/download.html)\n"
                    "2. Make sure nmap is in your system PATH\n"
                    "3. Restart NetWORKS"
                )
            return False
            
        # Check if already scanning
        if self._is_scanning:
            logger.warning("Scan already in progress")
            return False
            
        # Clean up any previous scan
        self._cleanup_previous_scan()
        
        # Update scan type in settings
        self.settings["scan_type"]["value"] = scan_type
        
        # Get scan profile settings if available
        scan_profiles = self.settings["scan_profiles"]["value"]
        custom_args = self.settings["custom_scan_args"]["value"]
        use_sudo = self.settings["use_sudo"]["value"]
        timeout = self.settings["scan_timeout"]["value"]
        
        # If the scan type has a profile, use those settings unless overridden
        if scan_type in scan_profiles:
            profile = scan_profiles[scan_type]
            
            # Only use profile settings if not explicitly set by the user
            if not custom_args:
                custom_args = profile.get("arguments", "")
            
            if timeout == self.settings["scan_timeout"]["default"]:
                timeout = profile.get("timeout", timeout)
        
        # Create a new worker thread
        try:
            # Log start of scan
            logger.info(f"Starting {scan_type} scan of {network_range}")
            
            # Create a new thread
            self._scanner_thread = QThread()
            
            # Create a worker and move it to the thread
            nmap_path = getattr(self, 'nmap_path', None)
            self._scanner_worker = ScannerWorker(
                network_range=network_range,
                scan_type=scan_type,
                timeout=timeout,
                use_sudo=use_sudo,
                custom_scan_args=custom_args,
                nmap_path=nmap_path
            )
            self._scanner_worker.moveToThread(self._scanner_thread)
            
            # Connect signals
            self._scanner_thread.started.connect(self._scanner_worker.run)
            self._scanner_worker.progress.connect(self._on_scan_progress)
            self._scanner_worker.device_found.connect(self._on_device_found)
            self._scanner_worker.scan_complete.connect(self._on_scan_complete)
            self._scanner_worker.scan_error.connect(self._on_scan_error)
            self._scanner_thread.finished.connect(self._thread_finished)
            
            # Set scanning flag
            self._is_scanning = True
            
            # Start the thread
            self._scanner_thread.start()
            
            # Update UI
            self.scan_started.emit(network_range)
            
            # Clear the scan log and reset progress
            self._scan_log = []
            self.log_message(f"Starting {scan_type} scan of {network_range}")
            self._scan_results = {}
            self._update_scan_button_state()
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
                
            return True
        except Exception as e:
            logger.error(f"Error starting scan: {e}", exc_info=True)
            self._is_scanning = False
            self._cleanup_previous_scan()
            self.scan_error.emit(f"Error starting scan: {e}")
            return False

    def _start_batch_device_scan(self, devices, scan_type):
        """Start a batch scan for a list of devices sequentially"""
        if self._is_scanning:
            QMessageBox.information(
                self.main_window,
                "Scan in Progress",
                "A scan is already in progress. Please wait for it to complete before starting a batch scan."
            )
            return False

        batch_targets = []
        for device in devices:
            if isinstance(device, dict):
                ip = device.get("ip", "")
                label = device.get("label", "").strip() or ip
                if not ip and device.get("device") is not None:
                    ip = device["device"].get_property("ip_address", "")
                    alias = device["device"].get_property("alias", "").strip()
                    label = label or alias or ip
                if not ip:
                    continue
                batch_targets.append({"ip": ip, "label": label})
                continue

            ip = device.get_property("ip_address", "")
            if not ip:
                continue
            alias = device.get_property("alias", "").strip() if hasattr(device, "get_property") else ""
            label = alias if alias else ip
            batch_targets.append({"ip": ip, "label": label})

        if not batch_targets:
            QMessageBox.warning(
                self.main_window,
                "No Valid Devices",
                "None of the selected devices have valid IP addresses."
            )
            return False

        self._batch_scan_queue = batch_targets
        self._batch_scan_total = len(batch_targets)
        self._batch_scan_index = 0
        self._batch_scan_current = None
        self._batch_scan_active = True
        threads = max(1, min(8, int(self.settings.get("batch_scan_threads", {}).get("value", 1) or 1)))

        self.log_message(f"Starting batch scan for {self._batch_scan_total} device(s)" + (f" ({threads} parallel)" if threads > 1 else ""))

        if threads > 1:
            self._is_scanning = True
            self._update_scan_button_state()
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
            self._refill_batch_slots(scan_type)
            return True
        return self._start_next_batch_scan(scan_type)

    def _start_next_batch_scan(self, scan_type):
        """Start the next scan in the batch queue"""
        if not self._batch_scan_active or not self._batch_scan_queue:
            self._clear_batch_scan()
            return False

        if self._is_scanning:
            return False

        self._batch_scan_index += 1
        self._batch_scan_current = self._batch_scan_queue.pop(0)
        current_ip = self._batch_scan_current["ip"]
        current_label = self._batch_scan_current["label"]

        if hasattr(self, "status_label"):
            self.status_label.setText(
                f"Scanning device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
            )

        self.log_message(
            f"Starting device {self._batch_scan_index}/{self._batch_scan_total} scan: {current_label}"
        )

        return self.scan_network(current_ip, scan_type)

    def _clear_batch_scan(self):
        """Reset batch scan state"""
        for slot in list(self._batch_scan_slots):
            try:
                if slot.get("worker"):
                    slot["worker"].stop()
                if slot.get("thread") and slot["thread"].isRunning():
                    slot["thread"].quit()
                    slot["thread"].wait(500)
            except Exception as e:
                logger.debug(f"Error clearing batch slot: {e}")
        self._batch_scan_slots = []
        self._batch_scan_queue = []
        self._batch_scan_total = 0
        self._batch_scan_index = 0
        self._batch_scan_current = None
        self._batch_scan_active = False
        
    def _create_worker_for_target(self, ip, scan_type):
        """Create (thread, worker) for a single target. Caller connects signals and starts thread."""
        scan_profiles = self.settings["scan_profiles"]["value"]
        custom_args = self.settings["custom_scan_args"]["value"]
        use_sudo = self.settings["use_sudo"]["value"]
        timeout = self.settings["scan_timeout"]["value"]
        if scan_type in scan_profiles:
            profile = scan_profiles[scan_type]
            if not custom_args:
                custom_args = profile.get("arguments", "")
            if timeout == self.settings["scan_timeout"]["default"]:
                timeout = profile.get("timeout", timeout)
        nmap_path = getattr(self, "nmap_path", None)
        thread = QThread()
        worker = ScannerWorker(
            network_range=ip,
            scan_type=scan_type,
            timeout=timeout,
            use_sudo=use_sudo,
            custom_scan_args=custom_args,
            nmap_path=nmap_path
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        return thread, worker
        
    def _refill_batch_slots(self, scan_type):
        """Start up to batch_scan_threads workers for queued targets."""
        max_n = max(1, min(8, int(self.settings.get("batch_scan_threads", {}).get("value", 1) or 1)))
        while self._batch_scan_active and self._batch_scan_queue and len(self._batch_scan_slots) < max_n:
            target = self._batch_scan_queue.pop(0)
            self._batch_scan_index += 1
            self._batch_scan_current = target
            current_ip = target["ip"]
            current_label = target["label"]
            if hasattr(self, "status_label"):
                self.status_label.setText(
                    f"Scanning device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
                )
            self.log_message(
                f"Starting device {self._batch_scan_index}/{self._batch_scan_total} scan: {current_label}"
            )
            thread, worker = self._create_worker_for_target(current_ip, scan_type)
            slot = {"thread": thread, "worker": worker, "target": target, "index": self._batch_scan_index}
            worker.progress.connect(self._on_scan_progress)
            worker.device_found.connect(self._on_device_found)
            worker.scan_complete.connect(
                lambda results, s=slot, st=scan_type: self._on_batch_slot_complete(s, results, st)
            )
            worker.scan_error.connect(
                lambda msg, s=slot, st=scan_type: self._on_batch_slot_error(s, msg, st)
            )
            self._batch_scan_slots.append(slot)
            thread.start()
        if self._batch_scan_active and not self._batch_scan_queue and not self._batch_scan_slots:
            self._batch_scan_done()
        
    def _on_batch_slot_complete(self, slot, results, scan_type):
        """Handle completion of one batch slot (parallel batch)."""
        try:
            if slot.get("worker"):
                slot["worker"].stop()
            if slot.get("thread") and slot["thread"].isRunning():
                slot["thread"].quit()
                slot["thread"].wait(1000)
        except Exception as e:
            logger.debug(f"Error cleaning batch slot: {e}")
        if slot in self._batch_scan_slots:
            self._batch_scan_slots.remove(slot)
        # Merge results
        if isinstance(results, dict) and results.get("devices"):
            self._scan_results.update({d.get("ip_address", str(i)): d for i, d in enumerate(results["devices"])})
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setValue(min(100, int(100 * (self._batch_scan_total - len(self._batch_scan_queue) - len(self._batch_scan_slots)) / max(1, self._batch_scan_total))))
        self._refill_batch_slots(scan_type)
        
    def _on_batch_slot_error(self, slot, error_message, scan_type):
        """Handle error from one batch slot (parallel batch)."""
        try:
            if slot.get("worker"):
                slot["worker"].stop()
            if slot.get("thread") and slot["thread"].isRunning():
                slot["thread"].quit()
                slot["thread"].wait(1000)
        except Exception as e:
            logger.debug(f"Error cleaning batch slot: {e}")
        if slot in self._batch_scan_slots:
            self._batch_scan_slots.remove(slot)
        label = slot.get("target", {}).get("label", "device")
        self.log_message(f"Batch scan error: {label} - {error_message}")
        self._refill_batch_slots(scan_type)
        
    def _batch_scan_done(self):
        """Called when all parallel batch slots and queue are empty."""
        self._clear_batch_scan()
        self._is_scanning = False
        self._update_scan_button_state()
        if hasattr(self, "status_label"):
            self.status_label.setText("Batch scan complete")
        self._update_results_footer(f"Batch scan complete | {len(self._scan_results)} devices")
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setValue(100)
        self.scan_completed.emit({"devices_found": len(self._scan_results), "scan_time": 0, "devices": list(self._scan_results.values())})
        
    def _cleanup_previous_scan(self):
        """Clean up any previous scan thread and worker"""
        # Stop thread if running
        if self._scanner_thread and self._scanner_thread.isRunning():
            logger.debug("Cleaning up previous thread")
            try:
                # Try to stop the worker if it exists
                if self._scanner_worker:
                    self._scanner_worker.stop()
                
                # Quit and wait for the thread
                self._scanner_thread.quit()
                success = self._scanner_thread.wait(1000)  # 1 second timeout
                
                if not success:
                    logger.warning("Thread did not exit cleanly, forcing termination")
                    self._scanner_thread.terminate()
                    self._scanner_thread.wait(1000)
            except Exception as e:
                logger.error(f"Error cleaning up previous scan: {e}")
                
        # Reset references
        self._scanner_thread = None
        self._scanner_worker = None
        self._is_scanning = False
        
    def _thread_finished(self):
        """Handle thread finished signal"""
        logger.debug("Scanner thread finished")
        
        # The actual scan results are handled by the _on_scan_complete or _on_scan_error callbacks
        # This is just an extra safeguard to ensure thread resources are cleaned up
        if self._is_scanning:
            # If we get here and still think we're scanning, something went wrong
            logger.warning("Thread finished while still scanning - cleanup needed")
            self._is_scanning = False
            
            # Update UI
            self._update_scan_button_state()
            if hasattr(self, "status_label"):
                self.status_label.setText("Scan interrupted unexpectedly")
            self._update_results_footer("Ready | 0 devices")
                
            self.log_message("Scan interrupted unexpectedly")
        
    def is_scanning(self):
        """
        Check if a scan is currently in progress
        
        Returns:
            bool: True if a scan is in progress, False otherwise
        """
        return self._is_scanning
        
    def stop_scan(self):
        """
        Stop any currently running scan
        
        Returns:
            bool: True if scan was stopped, False if no scan was running
        """
        if not self.is_scanning():
            logger.debug("No scan running to stop")
            if self._batch_scan_active:
                self._clear_batch_scan()
            return False
            
        logger.info("Stopping scan...")
        
        # Update UI first to give immediate feedback
        if hasattr(self, "status_label"):
            self.status_label.setText("Stopping scan...")
            
        # Try to stop ping scan if it's running
        stopped_ping = self.stop_ping_scan()
        
        # Signal the worker to stop
        try:
            if self._scanner_worker:
                self._scanner_worker.stop()
                logger.debug("Worker stop signal sent")
                
                # Force nmap to terminate if possible
                try:
                    # The python-nmap library sometimes doesn't properly terminate the nmap process
                    # We attempt to directly terminate it by accessing the internal scanner object
                    if hasattr(self._scanner_worker, 'scanner') and self._scanner_worker.scanner:
                        # Try to terminate the nmap process directly
                        if hasattr(self._scanner_worker.scanner, '_nmap_last_proc') and self._scanner_worker.scanner._nmap_last_proc:
                            try:
                                process = self._scanner_worker.scanner._nmap_last_proc
                                if process.poll() is None:  # Check if still running
                                    logger.info("Forcibly terminating nmap process")
                                    process.terminate()
                                    # Wait briefly for termination
                                    import time
                                    time.sleep(0.5)
                                    # If still running, kill it
                                    if process.poll() is None:
                                        process.kill()
                                        logger.info("Killed nmap process")
                            except Exception as e:
                                logger.error(f"Error terminating nmap process: {e}")
                except Exception as e:
                    logger.error(f"Error accessing nmap process: {e}")
                
        except Exception as e:
            logger.error(f"Error signaling worker to stop: {e}")
        
        # Wait a bit before trying to terminate the thread
        try:
            if self._scanner_thread and self._scanner_thread.isRunning():
                # Try to quit gracefully first
                self._scanner_thread.quit()
                logger.debug("Thread quit signal sent")
                
                # Wait for the thread to finish with timeout
                if not self._scanner_thread.wait(3000):  # 3 second timeout
                    logger.warning("Thread did not exit within timeout, forcing termination")
                    try:
                        self._scanner_thread.terminate()
                        logger.debug("Thread terminate signal sent")
                        # Short wait for termination to take effect
                        self._scanner_thread.wait(1000)
                    except Exception as term_error:
                        logger.error(f"Error terminating thread: {term_error}")
        except Exception as e:
            logger.error(f"Error stopping thread: {e}")
                
        # Mark as not scanning
        self._is_scanning = False
        self._update_scan_button_state()
        if hasattr(self, "status_label"):
            self.status_label.setText("Scan stopped by user")
            
        self.log_message("Scan stopped by user")

        if self._batch_scan_active:
            self._clear_batch_scan()
        
        return True
        
    def get_scan_results(self):
        """
        Get the results of the most recent scan
        
        Returns:
            dict: Dictionary containing scan results with statistics
        """
        return self._scan_results
        
    def _on_scan_progress(self, current, total):
        """Handle scan progress updates"""
        # Calculate percentage
        if total > 0:
            percentage = int((current / total) * 100)
        else:
            percentage = 0
            
        # Update progress bar
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(percentage)
            self.progress_bar.setTextVisible(True)
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                remaining = max(0, self._batch_scan_total - self._batch_scan_index)
                self.progress_bar.setFormat(
                    f"Device {self._batch_scan_index}/{self._batch_scan_total} "
                    f"({remaining} remaining): {current_label} - %p%"
                )
            else:
                self.progress_bar.setFormat("Scanning - %p%")
            
        # Update status label
        if hasattr(self, "status_label"):
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                self.status_label.setText(
                    f"Scanning device {self._batch_scan_index}/{self._batch_scan_total}: "
                    f"{current_label} ({current}/{total} hosts, {percentage}%)"
                )
            else:
                self.status_label.setText(f"Scanning: {current}/{total} hosts processed ({percentage}%)")
            
        # Emit the scan progress signal
        self.scan_progress.emit(current, total)
        
    def _on_device_found(self, host_data):
        """
        Handle a device found during scanning
        
        This method is called when the scanner worker finds a device.
        It creates a new device or updates an existing one.
        """
        try:
            # Check if this is a status update rather than a device
            if "status_update" in host_data:
                # Update the status label with the status message
                if hasattr(self, "status_label"):
                    self.status_label.setText(host_data["status_update"])
                
                # Log the status update
                self.log_message(host_data["status_update"])
                return None
                
            # Use a local copy of host_data to avoid memory corruption
            device_data = host_data.copy()
            
            # Verify we have an IP address at minimum - if not, this isn't a valid device
            if not device_data.get("ip_address"):
                logger.debug("Received device data without IP address, ignoring")
                return None
                
            # For non-ping scans, ensure the device has some meaningful data
            if device_data.get("scan_source") != "ping":
                # Check if this device has any meaningful properties to add
                has_meaningful_data = False
                # Look for properties that would make this device worth adding
                for key in ["hostname", "mac_address", "open_ports", "services", "os"]:
                    if key in device_data and device_data[key]:
                        has_meaningful_data = True
                        break
                        
                # If a device is up but has no additional data, it's still worth adding
                # But we should log this situation for debugging
                if not has_meaningful_data:
                    logger.debug(f"Device at {device_data['ip_address']} is up but has no additional data")
            
            # Check if this device already exists based on IP or MAC
            existing_device = None
            if "ip_address" in device_data and device_data["ip_address"]:
                # Try to find by IP address
                for device in self.device_manager.get_devices():
                    if device.get_property("ip_address") == device_data["ip_address"]:
                        existing_device = device
                        break
                        
            if not existing_device and "mac_address" in device_data and device_data["mac_address"]:
                # Try to find by MAC address
                for device in self.device_manager.get_devices():
                    if device.get_property("mac_address") == device_data["mac_address"]:
                        existing_device = device
                        break
            
            if existing_device:
                # Update existing device (one property at a time to prevent race conditions)
                for key, value in device_data.items():
                    if key == "tags":
                        # Merge tags rather than replace
                        current_tags = existing_device.get_property("tags", [])
                        new_tags = []
                        for tag in value:
                            if tag not in current_tags and tag not in new_tags:
                                new_tags.append(tag)
                        
                        # Only update if there are new tags to add
                        if new_tags:
                            updated_tags = current_tags.copy()  # Make a copy to avoid modifying original
                            updated_tags.extend(new_tags)
                            existing_device.set_property("tags", updated_tags)
                    else:
                        # Only update if value is different to minimize device_changed events
                        current_value = existing_device.get_property(key, None)
                        if current_value != value:
                            existing_device.set_property(key, value)
                
                # Log the update
                self.log_message(f"Updated existing device: {existing_device.get_property('alias')}")
                
                # Emit the device found signal
                self.scan_device_found.emit(existing_device)
                
                return existing_device
            else:
                # Create a new device
                new_device = self.device_manager.create_device(
                    device_type="scanned",
                    **device_data
                )
                
                # Add it to the device manager
                self.device_manager.add_device(new_device)
                
                # Allow table to repaint when devices are added during nmap/chunked scan
                if device_data.get("scan_source") == "nmap":
                    QApplication.processEvents()
                
                # Log the addition
                self.log_message(f"Added new device: {new_device.get_property('alias')}")
                
                # Emit the device found signal
                self.scan_device_found.emit(new_device)
                
                return new_device
                
        except Exception as e:
            logger.error(f"Error adding/updating device: {e}", exc_info=True)
            self.log_message(f"Error adding/updating device: {e}")
            return None
            
    def _on_scan_complete(self, results):
        """Handle scan completion"""
        self._is_scanning = False
        # Store the results
        self._scan_results = results
        self._update_scan_button_state()
        # Update status
        if hasattr(self, "status_label"):
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                if self._batch_scan_queue:
                    self.status_label.setText(
                        f"Completed device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
                    )
                else:
                    self.status_label.setText("Batch scan complete")
                    self._update_results_footer(f"Batch scan complete | {len(self._scan_results)} devices")
            else:
                self.status_label.setText("Scan complete")
                self._update_results_footer(f"Scan complete | {results.get('devices_found', 0)} devices")
            
        # Set progress to 100%
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(100)
            
        # Log results
        scan_time = round(results["scan_time"], 1)
        self.log_message(f"Scan complete: Found {results['devices_found']} devices in {scan_time} seconds")
        
        # Stop the thread and ensure proper cleanup
        if self._scanner_thread and self._scanner_thread.isRunning():
            self._scanner_thread.quit()
            success = self._scanner_thread.wait(1000)  # 1 second timeout
            
            if not success:
                logger.warning("Thread did not exit cleanly after scan completion, forcing termination")
                self._scanner_thread.terminate()
                self._scanner_thread.wait(1000)
            
            # Reset references to help garbage collection
            self._scanner_worker = None
            self._scanner_thread = None
        
        # Force a garbage collection cycle to clean up lingering objects
        try:
            import gc
            gc.collect()
        except Exception as e:
            logger.warning(f"Error during garbage collection: {e}")
        
        # Emit the scan completed signal
        self.scan_completed.emit(results)

        if self._batch_scan_active:
            if self._batch_scan_queue:
                scan_type = self.settings["scan_type"]["value"]
                QTimer.singleShot(200, lambda: self._start_next_batch_scan(scan_type))
            else:
                self._clear_batch_scan()
        
    def _on_scan_error(self, error_message):
        """Handle scan errors"""
        self._is_scanning = False
        self._update_scan_button_state()
        # Update status
        if hasattr(self, "status_label"):
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                self.status_label.setText(
                    f"Error on device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
                )
            else:
                self.status_label.setText(f"Error: {error_message}")
            
        # Log the error
        self.log_message(f"Scan error: {error_message}")

        if self._batch_scan_active and self._batch_scan_current:
            current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
            self.log_message(
                f"Batch scan error on device {self._batch_scan_index}/{self._batch_scan_total}: "
                f"{current_label} - {error_message}"
            )
        
        # Stop the thread
        if self._scanner_thread and self._scanner_thread.isRunning():
            self._scanner_thread.quit()
            self._scanner_thread.wait()
            
        # Emit the scan error signal
        self.scan_error.emit(error_message) 

        if self._batch_scan_active:
            if self._batch_scan_queue:
                scan_type = self.settings["scan_type"]["value"]
                QTimer.singleShot(200, lambda: self._start_next_batch_scan(scan_type))
            else:
                self._clear_batch_scan()

    @safe_action_wrapper
    def on_scan_action(self):
        """Handle main scan action"""
        # Update network interfaces before showing dialog
        self._update_interface_choices()
        
        # Show scan dialog
        dialog_result = self._show_scan_dialog()
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
            
    @safe_action_wrapper
    def on_scan_selected_action(self):
        """Handle scanning selected devices"""
        # Find the device table
        from src.ui.device_table import DeviceTableView
        device_table = self.main_window.findChild(DeviceTableView)
        
        if not device_table:
            QMessageBox.warning(
                self.main_window,
                "Device Table Not Found",
                "Could not find the device table view."
            )
            return
            
        # Get selected devices
        selected_devices = device_table.get_selected_devices()
        
        if not selected_devices:
            QMessageBox.warning(
                self.main_window,
                "No Devices Selected",
                "Please select one or more devices to scan."
            )
            return

        # Update network interfaces before showing dialog
        self._update_interface_choices()

        dialog_result = self._show_scan_dialog(selected_devices)
        if not dialog_result:
            return

        # Get scan type from settings
        scan_type = self.settings["scan_type"]["value"]

        self._handle_scan_target(dialog_result, scan_type)
        
    def _update_scan_button_state(self):
        """Update scan button label and state: 'Stop' when scanning, 'Start Scan' when idle."""
        if hasattr(self, "scan_button") and self.scan_button:
            if self._is_scanning:
                self.scan_button.setText("Stop")
            else:
                self.scan_button.setText("Start Scan")
            self.scan_button.setEnabled(True)

    def _update_results_footer(self, text):
        """Update the one-line footer below the results area (e.g. 'Ready | 0 devices')."""
        if hasattr(self, "results_footer") and self.results_footer:
            self.results_footer.setText(text)

    def on_scan_stop_button_clicked(self):
        """Single handler: start scan when idle, stop scan when running."""
        if self._is_scanning:
            self.stop_scan()
            return
        self._do_start_scan_from_panel()

    def _do_start_scan_from_panel(self):
        """Start a scan using current panel target/range/type (called when Start Scan is clicked). Uses _execute_scan as single logic."""
        target = (hasattr(self, "target_combo") and self.target_combo.currentData()) or "interface"
        scan_type = self.scan_type_combo.currentText() if hasattr(self, "scan_type_combo") else self.settings["scan_type"]["value"]
        
        if target == "devices":
            from src.ui.device_table import DeviceTableView
            device_table = self.main_window.findChild(DeviceTableView) if self.main_window else None
            selected = (device_table.get_selected_devices() if device_table else []) or (self.device_manager.get_selected_devices() or [])
            devices_with_ips = [d for d in selected if hasattr(d, "get_property") and d.get_property("ip_address", "")]
            return self._execute_scan("devices", devices_with_ips, scan_type)
        if target == "group":
            group = None
            if hasattr(self, "group_combo") and self.group_combo and self.group_combo.count():
                group = self.group_combo.currentData()
            return self._execute_scan("group", group, scan_type)
        if target == "interface":
            network_range = self._get_interface_subnet(self.interface_combo.currentText()) if hasattr(self, "interface_combo") else ""
            return self._execute_scan("interface", network_range or "", scan_type)
        if target == "custom":
            network_range = (self.network_range_edit.text() or "").strip() if hasattr(self, "network_range_edit") else ""
            return self._execute_scan("custom", network_range, scan_type)
        # Fallback: treat as interface then custom
        network_range = (self.network_range_edit.text() or "").strip() if hasattr(self, "network_range_edit") else ""
        if not network_range and hasattr(self, "interface_combo"):
            network_range = self._get_interface_subnet(self.interface_combo.currentText()) or ""
        return self._execute_scan("interface", network_range, scan_type)

    @safe_action_wrapper
    def on_advanced_scan_button_clicked(self):
        """Handle advanced scan button click - opens the full scan dialog"""
        # Check if scan already in progress
        if self._is_scanning:
            QMessageBox.information(
                self.main_window,
                "Scan in Progress",
                "A scan is already in progress. Please wait for it to complete or click Stop to cancel it."
            )
            return
            
        # Update network interfaces before showing dialog
        self._update_interface_choices()
        
        # Show scan dialog
        dialog_result = self._show_scan_dialog()
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
        
    @safe_action_wrapper
    def on_stop_button_clicked(self):
        """Handle stop button click"""
        self.stop_scan()
        
    def _show_scan_dialog(self, selected_devices=None):
        """Show scan dialog (delegated to ui.scan_dialog)."""
        return show_scan_dialog(self, selected_devices)

    def _handle_scan_target(self, dialog_result, scan_type):
        """Convert dialog result to (target_type, target_data) and run the unified scan logic."""
        if not dialog_result:
            return False
        if isinstance(dialog_result, dict):
            target_type = dialog_result.get("target_type")
            if target_type == "devices":
                return self._execute_scan("devices", dialog_result.get("selected_devices", []), scan_type)
            if target_type == "group":
                return self._execute_scan("group", dialog_result.get("group"), scan_type)
            if target_type == "interface":
                return self._execute_scan("interface", (dialog_result.get("network_range") or "").strip(), scan_type)
        if isinstance(dialog_result, str):
            return self._execute_scan("custom", dialog_result.strip(), scan_type)
        return False

    @safe_action_wrapper
    def _on_scan_subnet_action(self, device_or_devices=None):
        """Handle Scan Interface Subnet action from context menu"""
        # Update the interface list
        self._update_interface_choices()
        
        selected_if_text = self.settings["preferred_interface"]["value"]
        
        # If no interface is selected or it's the "Any" option, show the dialog
        if not selected_if_text or selected_if_text == "Any (default)":
            dialog_result = self._show_scan_dialog()
        else:
            # Get the interface name
            selected_if = selected_if_text.split(":")[0].strip()
            subnet = self._get_interface_subnet(selected_if)
            
            if not subnet:
                # If we couldn't determine the subnet, show the dialog
                dialog_result = self._show_scan_dialog()
            else:
                # Show confirmation dialog
                result = QMessageBox.question(
                    self.main_window,
                    "Confirm Subnet Scan",
                    f"Do you want to scan the subnet {subnet} from interface {selected_if}?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if result == QMessageBox.Yes:
                    dialog_result = subnet
                else:
                    dialog_result = None
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
            
    @safe_action_wrapper
    def _on_rescan_device_action(self, device_or_devices):
        """Handle Rescan Selected Device action from context menu"""
        # Get the device(s)
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            # If no devices were passed, try to get selected devices from device manager
            devices = self.device_manager.get_selected_devices()
            
        # Check if we have any devices
        if not devices:
            QMessageBox.warning(
                self.main_window,
                "No Devices Selected",
                "Please select one or more devices to rescan."
            )
            return
            
        # Show scan dialog for selected devices
        dialog_result = self._show_scan_dialog(devices)

        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            self._handle_scan_target(dialog_result, scan_type)
                    
    @safe_action_wrapper
    def _on_scan_network_action(self, device_or_devices):
        """Handle Scan Network action from context menu"""
        # This action doesn't need the selected device, just show the scan dialog
        dialog_result = self._show_scan_dialog()
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
            
    @safe_action_wrapper
    def _on_scan_from_device_action(self, device_or_devices):
        """Handle Scan from Selected Device action from context menu"""
        # Get the device(s)
        if isinstance(device_or_devices, list):
            if not device_or_devices:
                QMessageBox.warning(
                    self.main_window,
                    "No Device Selected",
                    "Please select a device to scan its network."
                )
                return
            device = device_or_devices[0]  # Use the first device
        else:
            device = device_or_devices
            
        if not device:
            QMessageBox.warning(
                self.main_window,
                "No Device Selected",
                "Please select a device to scan its network."
            )
            return
            
        # Get the IP address
        ip_address = device.get_property("ip_address", "")
        
        if not ip_address:
            QMessageBox.warning(
                self.main_window,
                "No IP Address",
                "The selected device does not have an IP address."
            )
            return
            
        try:
            # Parse the IP address to get the network
            ip = ipaddress.ip_address(ip_address)
            
            # For IPv4, assume /24 subnet
            if isinstance(ip, ipaddress.IPv4Address):
                network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
                network_range = str(network)
            else:
                # For IPv6, assume /64 subnet
                network = ipaddress.IPv6Network(f"{ip_address}/64", strict=False)
                network_range = str(network)
                
            # Show the scan dialog with the device's network pre-filled
            dialog_result = self._show_scan_dialog()
            if dialog_result:
                # Get scan type from settings
                scan_type = self.settings["scan_type"]["value"]
                
                # Start the scan
                self._handle_scan_target(dialog_result, scan_type)
                
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Error determining network range: {e}"
            )

    def on_device_added(self, device):
        """Handle device added signal"""
        # Check if this device was added by this plugin
        if device.get_property("scan_source", "") == "nmap":
            logger.debug(f"Device added by this plugin: {device.get_property('alias')}")
            
    def on_device_removed(self, device):
        """Handle device removed signal"""
        # Nothing specific to do for removed devices
        pass
        
    def on_device_changed(self, device):
        """Handle device changed signal"""
        # Nothing specific to do for changed devices
        pass
        
    def get_settings(self):
        """Get plugin settings"""
        return self.settings
        
    def update_setting(self, setting_id, value):
        """Update a plugin setting"""
        if setting_id in self.settings:
            self.settings[setting_id]["value"] = value
            logger.debug(f"Updated setting {setting_id} to {value}")
            
            # Special handling for certain settings
            if setting_id == "scan_profiles":
                # Update the scan type choices if profiles changed
                scan_types = list(value.keys())
                self.settings["scan_type"]["choices"] = scan_types
                
            return True
        return False

    def _get_network_interfaces(self):
        """Get a list of available network interfaces with their details"""
        interfaces = []

        # Preferred path: use psutil (pure Python interface, wheels available on most platforms)
        if not HAS_PSUTIL:
            logger.warning("psutil is not available; cannot enumerate network interfaces")
            return interfaces

        try:
            for iface, addrs in psutil.net_if_addrs().items():
                try:
                    # Skip loopback and common virtual interfaces
                    if iface == "lo" or iface.startswith("vbox") or iface.startswith("docker"):
                        continue

                    for addr in addrs:
                        # AF_INET == IPv4; use numeric literal to avoid importing socket here
                        if addr.family == 2 and addr.address and not addr.address.startswith("127."):
                            ip = addr.address
                            netmask = addr.netmask

                            # Try to get a friendly name/alias for the interface
                            interface_alias = self._get_interface_friendly_name(iface)

                            # Create interface info
                            interface_info = {
                                "name": iface,
                                "alias": interface_alias,
                                "ip": ip,
                                "netmask": netmask,
                                "display": f"{interface_alias}: {ip}",
                            }

                            # Try to get subnet in CIDR format
                            try:
                                if netmask:
                                    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                    interface_info["network"] = str(network)
                                    interface_info["display"] = f"{interface_alias}: {ip} ({network})"
                            except Exception as e:
                                logger.debug(f"Error calculating network for {iface}: {e}")

                            interfaces.append(interface_info)
                except Exception as e:
                    logger.debug(f"Error processing interface {iface} via psutil: {e}")
                    continue
            return interfaces
        except Exception as e:
            logger.error(f"Error getting network interfaces via psutil: {e}")

        return interfaces

    def _get_interface_friendly_name(self, interface_name):
        """Get a friendly name for the interface"""
        # This is a platform-dependent function
        try:
            import platform
            
            if platform.system() == "Windows":
                # On Windows, try to get friendly name using WMI
                try:
                    import wmi
                    c = wmi.WMI()
                    for adapter in c.Win32_NetworkAdapter():
                        if adapter.NetConnectionID and interface_name.lower() in adapter.NetConnectionID.lower():
                            return adapter.NetConnectionID
                        # Sometimes we need to match on the GUID
                        elif adapter.GUID and interface_name.lower() in adapter.GUID.lower():
                            return adapter.NetConnectionID or adapter.Name
                except Exception as e:
                    logger.debug(f"Error getting Windows interface name: {e}")
                    
                # If we couldn't get it from WMI, try some heuristics
                if "Local Area Connection" in interface_name:
                    return "Ethernet"
                elif "Wireless" in interface_name:
                    return "Wi-Fi"
                
            elif platform.system() == "Linux":
                # On Linux, try to get interface type
                if interface_name.startswith("eth"):
                    return "Ethernet"
                elif interface_name.startswith("wlan") or interface_name.startswith("wifi"):
                    return "Wi-Fi"
                elif interface_name.startswith("en"):
                    return "Ethernet"  # Modern naming scheme
                elif interface_name.startswith("wl"):
                    return "Wi-Fi"  # Modern naming scheme
            
            # If we got here, use the interface name as the alias
            return interface_name
            
        except Exception as e:
            logger.debug(f"Error getting interface friendly name: {e}")
            return interface_name
        
    def _update_interface_choices(self):
        """Update the interface choices in settings"""
        interfaces = self._get_network_interfaces()
        
        # Update the choices in settings
        if "preferred_interface" in self.settings:
            choices = [f"{iface['display']}" for iface in interfaces]
            self.settings["preferred_interface"]["choices"] = choices
            
            # Add a blank option for "any interface"
            self.settings["preferred_interface"]["choices"].insert(0, "Any (default)")
            
            # Store the interface data for later use
            self._network_interfaces = interfaces
            
        return interfaces
        
    def _get_interface_subnet(self, interface_name=None):
        """Get the subnet for the specified interface or the preferred interface"""
        # If no interface specified, use the preferred interface from settings
        if not interface_name:
            preferred = self.settings.get("preferred_interface", {}).get("value", "")
            if preferred and preferred != "Any (default)":
                # Extract interface info from the display string format: "Alias: IP (Network)"
                try:
                    # First check if we have stored interface data
                    if hasattr(self, "_network_interfaces") and self._network_interfaces:
                        # Find the interface with matching display string
                        for iface in self._network_interfaces:
                            if iface["display"] == preferred:
                                interface_name = iface["name"]
                                # If we found a match, we can return the network directly
                                if "network" in iface:
                                    return iface["network"]
                                break
                    
                    # If we didn't find it, try to extract from the display string
                    if not interface_name:
                        # Parse the interface name from the display string
                        parts = preferred.split(": ")
                        if len(parts) >= 2:
                            # Extract IP address from second part
                            ip_part = parts[1].split(" ")[0]
                            # Look for interface with this IP
                            if hasattr(self, "_network_interfaces") and self._network_interfaces:
                                for iface in self._network_interfaces:
                                    if iface["ip"] == ip_part:
                                        interface_name = iface["name"]
                                        # If we found a match, we can return the network directly
                                        if "network" in iface:
                                            return iface["network"]
                                        break
                except Exception as e:
                    logger.error(f"Error extracting interface name from {preferred}: {e}")
                    return None
        
        # If we have an interface name, find its subnet
        if interface_name:
            try:
                # Make sure we have network interface data
                if not hasattr(self, "_network_interfaces") or not self._network_interfaces:
                    # Try to update interfaces
                    logger.debug("Network interfaces not loaded, attempting to load them now")
                    self._update_interface_choices()
                
                # Search for the interface in our stored data (match by display or name;
                # interface_name is often the combo's currentText, i.e. the display string)
                for iface in getattr(self, "_network_interfaces", []):
                    if iface.get("display") == interface_name or iface.get("name") == interface_name:
                        network = iface.get('network', None)
                        if network:
                            logger.debug(f"Found subnet {network} for interface {interface_name}")
                            return network
                        else:
                            logger.debug(f"Interface {interface_name} found but has no subnet information")
                            # Try to calculate it if we have IP and netmask
                            if 'ip' in iface and 'netmask' in iface:
                                try:
                                    network = ipaddress.IPv4Network(f"{iface['ip']}/{iface['netmask']}", strict=False)
                                    logger.debug(f"Calculated subnet {network} for interface {interface_name}")
                                    return str(network)
                                except Exception as e:
                                    logger.debug(f"Error calculating network for {interface_name}: {e}")
                
                logger.debug(f"No matching interface found for {interface_name}")
            except Exception as e:
                logger.error(f"Error getting subnet for interface {interface_name}: {e}")
        
        return None

    def get_settings_pages(self):
        """Get plugin settings pages (delegated to ui.settings_pages)."""
        return get_settings_pages_impl(self)

    def _update_interface_choices_and_refresh_ui(self):
        """Update interface choices and refresh the UI"""
        try:
            # Update the interface choices
            interfaces = self._update_interface_choices()
            
            # Update the UI combobox if it exists
            if hasattr(self, "interface_combo") and self.interface_combo is not None:
                # Remember current selection to restore it if possible
                current_selection = self.interface_combo.currentText()
                
                # Clear and repopulate
                self.interface_combo.clear()
                self.interface_combo.addItems(self.settings["preferred_interface"]["choices"])
                
                # Try to restore previous selection, otherwise use the default
                if current_selection and current_selection in self.settings["preferred_interface"]["choices"]:
                    self.interface_combo.setCurrentText(current_selection)
                elif self.settings["preferred_interface"]["value"] in self.settings["preferred_interface"]["choices"]:
                    self.interface_combo.setCurrentText(self.settings["preferred_interface"]["value"])
                
                # Log the update
                logger.debug(f"Updated interface list, found {len(interfaces)} interfaces")
                
                # Update network range based on selected interface
                self._update_network_range_from_interface(self.interface_combo.currentIndex())
                
            return True
        except Exception as e:
            logger.error(f"Error updating interface choices: {e}")
            return False

    def _update_network_range_from_interface(self, index):
        """Update network range based on selected interface"""
        try:
            # Check if the UI elements exist
            if not hasattr(self, "interface_combo") or not hasattr(self, "network_range_edit"):
                logger.debug("UI elements not yet created, skipping network range update")
                return
            
            selected_if_text = self.interface_combo.currentText()
            
            # Skip "Any (default)" option
            if not selected_if_text or selected_if_text == "Any (default)":
                logger.debug("No specific interface selected, not updating network range")
                return
            
            # Log the selected interface for debugging
            logger.debug(f"Updating network range from selected interface: {selected_if_text}")
                
            # Try to directly find the network from stored interface data
            if hasattr(self, "_network_interfaces") and self._network_interfaces:
                for iface in self._network_interfaces:
                    if iface["display"] == selected_if_text:
                        # Check if network information is available
                        if "network" in iface:
                            network = iface["network"]
                            self.network_range_edit.setText(network)
                            logger.debug(f"Updated network range to {network} from interface {iface['alias']}")
                            return True
                        # Try IP with netmask
                        elif "ip" in iface and "netmask" in iface:
                            try:
                                network = ipaddress.IPv4Network(f"{iface['ip']}/{iface['netmask']}", strict=False)
                                network_str = str(network)
                                self.network_range_edit.setText(network_str)
                                logger.debug(f"Updated network range to {network_str} from interface {iface['alias']}")
                                return True
                            except Exception as e:
                                logger.debug(f"Error calculating network for {iface['alias']}: {e}")

            # If we get here, try getting the subnet using the standard method as fallback
            subnet = self._get_interface_subnet(selected_if_text)
            
            if subnet:
                # Set the network range text field and log it
                self.network_range_edit.setText(subnet)
                logger.debug(f"Updated network range to {subnet} from interface")
                return True
            else:
                logger.warning(f"Could not determine subnet for interface {selected_if_text}")
        
            # If no subnet was found from interface, try to get one from local IP
            try:
                import socket
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
                network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
                self.network_range_edit.setText(str(network))
                logger.debug(f"Used default network {network} from local IP {ip_address}")
                return True
            except Exception as e:
                logger.debug(f"Error determining default network range: {e}")
        except Exception as e:
            logger.error(f"Error updating network range from interface: {e}")
            
        return False

    def _refresh_group_choices(self):
        """Refresh the group selection dropdown"""
        if not hasattr(self, "device_manager") or not self.device_manager:
            return
        if not hasattr(self, "group_combo") or self.group_combo is None:
            return
            
        current_group = self.group_combo.currentData() if self.group_combo.count() else None
        current_name = current_group.name if current_group else None
        
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        
        root_group = self.device_manager.root_group
        self.group_combo.addItem("All Devices", root_group)
        
        groups = [g for g in self.device_manager.get_groups() if g != root_group]
        groups.sort(key=lambda g: self._format_group_path(g).lower())
        for group in groups:
            label = self._format_group_path(group)
            self.group_combo.addItem(label, group)
        
        # Restore previous selection if possible
        if current_name:
            for index in range(self.group_combo.count()):
                group = self.group_combo.itemData(index)
                if group and group.name == current_name:
                    self.group_combo.setCurrentIndex(index)
                    break
        
        self.group_combo.blockSignals(False)

    def _format_group_path(self, group):
        """Return a display path for a group"""
        parts = [group.name]
        parent = group.parent
        while parent and parent != self.device_manager.root_group:
            parts.append(parent.name)
            parent = parent.parent
        parts.reverse()
        return " / ".join(parts)

    def _update_group_scan_ui_state(self):
        """Toggle UI state when group scan is enabled (deprecated - now handled by radio buttons)"""
        # This method is kept for backward compatibility but functionality
        # is now handled by the update_target_ui_state function in _create_widgets
        pass

    def _get_selected_group(self):
        """Return the selected group from the UI"""
        if not hasattr(self, "group_combo") or self.group_combo.count() == 0:
            return None
        return self.group_combo.currentData()

    def _get_group_devices(self, group):
        """Return devices for a group including subgroups"""
        if not group:
            return []
        try:
            return group.get_all_devices()
        except Exception:
            return []

    def _get_group_ip_list(self, group):
        """Return a list of IPs for devices in the group"""
        devices = self._get_group_devices(group)
        ip_list = []
        for device in devices:
            ip = device.get_property("ip_address", "") if hasattr(device, "get_property") else ""
            if ip:
                ip_list.append(ip)
        # De-duplicate while preserving order
        seen = set()
        unique_ips = []
        for ip in ip_list:
            if ip in seen:
                continue
            seen.add(ip)
            unique_ips.append(ip)
        return unique_ips

    def _set_selected_devices_label_style(self, role):
        """Apply theme-aware style to selected_devices_label. role: 'muted'|'warning'|'normal'."""
        if not hasattr(self, "selected_devices_label") or not self.selected_devices_label:
            return
        label = self.selected_devices_label
        label.setProperty("plugin_ui_muted", "true" if role == "muted" else "")
        label.setProperty("plugin_ui_warning", "true" if role == "warning" else "")
        label.style().unpolish(label)
        label.style().polish(label)

    def _update_selected_devices_ui(self):
        """Update the selected devices UI when device selection changes. Updates the
        'Selected Devices (N)' label in target_combo and keeps the info label in sync."""
        if not hasattr(self, "target_combo") or not hasattr(self, "selected_devices_label"):
            return
        
        if not getattr(self, "device_manager", None):
            self._set_target_combo_devices_item(0)
            self.selected_devices_label.setText("Device manager unavailable")
            self._set_selected_devices_label_style("muted")
            self.selected_devices_label.setVisible(
                (self.target_combo.currentData() or "interface") == "devices"
            )
            return
        
        selected_devices = self.device_manager.get_selected_devices()
        
        if selected_devices:
            # Filter devices with IP addresses
            devices_with_ips = [d for d in selected_devices 
                              if (d.get_property("ip_address", "") if hasattr(d, "get_property") else "")]
            count = len(devices_with_ips)
            
            self._set_target_combo_devices_item(count)
            
            if count > 0:
                device_names = []
                for device in devices_with_ips[:5]:  # Show first 5
                    name = device.get_property("alias", "") if hasattr(device, "get_property") else ""
                    ip = device.get_property("ip_address", "") if hasattr(device, "get_property") else ""
                    if name and ip:
                        device_names.append(f"{name} ({ip})")
                    elif ip:
                        device_names.append(ip)
                    elif name:
                        device_names.append(name)
                
                if count > 5:
                    device_names.append(f"... and {count - 5} more")

                self.selected_devices_label.setText(f"Selected: {', '.join(device_names)}")
                self._set_selected_devices_label_style("normal")
            else:
                self.selected_devices_label.setText("Selected devices have no IP addresses")
                self._set_selected_devices_label_style("warning")
            
            target = self.target_combo.currentData() if self.target_combo.currentData() is not None else "interface"
            self.selected_devices_label.setVisible(target == "devices")
        else:
            self._set_target_combo_devices_item(0)
            self.selected_devices_label.setText("No devices selected")
            self._set_selected_devices_label_style("muted")
            self.selected_devices_label.setVisible(
                (self.target_combo.currentData() or "interface") == "devices"
            )
    
    def _target_combo_devices_index(self):
        """Return the index of the 'Selected Devices' item in target_combo, or -1."""
        for i in range(self.target_combo.count()):
            if self.target_combo.itemData(i) == "devices":
                return i
        return -1
    
    def _set_target_combo_devices_item(self, count):
        """Update the 'Selected Devices' item text to show (N) when count > 0."""
        idx = self._target_combo_devices_index()
        text = f"Selected Devices ({count})" if count > 0 else "Selected Devices"
        if idx >= 0:
            self.target_combo.setItemText(idx, text)
    
    def on_device_selected(self, devices):
        """Handle device selection changed signal"""
        self._update_selected_devices_ui()

    @safe_action_wrapper
    def on_scan_type_manager_action(self):
        """Handle scan type manager action"""
        self._show_scan_type_manager_dialog()
        
    def _show_scan_type_manager_dialog(self):
        layout.addWidget(dialog_buttons)
        
        # Handle selection change
        def on_selection_changed():
            selected_indexes = profile_table.selectedIndexes()
            if selected_indexes:
                row = selected_indexes[0].row()
                profile_id = profile_table.item(row, 0).data(Qt.UserRole)
                is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
                
                edit_button.setEnabled(True)
                delete_button.setEnabled(not is_builtin)
            else:
                edit_button.setEnabled(False)
                delete_button.setEnabled(False)
        
        profile_table.itemSelectionChanged.connect(on_selection_changed)
        
        # Show edit dialog for a profile
        def edit_profile_dialog(profile_id=None, is_new=False):
            edit_dialog = QDialog(dialog)
            mark_plugin_ui(edit_dialog)
            edit_dialog.setWindowTitle("New Scan Profile" if is_new else "Edit Scan Profile")
            edit_dialog.setMinimumWidth(450)
            
            edit_layout = QVBoxLayout(edit_dialog)
            
            # Form layout
            form_layout = QFormLayout()
            form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            
            # Profile ID (for new profiles only)
            profile_id_edit = QLineEdit()
            if is_new:
                form_layout.addRow("Profile ID:", profile_id_edit)
                profile_id_edit.setPlaceholderText("e.g., custom_scan (no spaces, lowercase)")
            
            # Name
            profile_name_edit = QLineEdit()
            form_layout.addRow("Display Name:", profile_name_edit)
            
            # Description
            profile_desc_edit = QLineEdit()
            form_layout.addRow("Description:", profile_desc_edit)
            
            # Arguments
            profile_args_edit = QLineEdit()
            form_layout.addRow("Arguments:", profile_args_edit)
            profile_args_edit.setPlaceholderText("e.g., -sn -F")
            
            # Timeout
            profile_timeout_edit = QLineEdit()
            profile_timeout_edit.setValidator(QIntValidator(30, 600))
            form_layout.addRow("Timeout (seconds):", profile_timeout_edit)
            
            # If editing, populate with existing values
            if not is_new and profile_id:
                profile = self.settings["scan_profiles"]["value"].get(profile_id, {})
                profile_name_edit.setText(profile.get("name", ""))
                profile_desc_edit.setText(profile.get("description", ""))
                profile_args_edit.setText(profile.get("arguments", ""))
                profile_timeout_edit.setText(str(profile.get("timeout", 300)))
            
            edit_layout.addLayout(form_layout)
            
            # Add dialog buttons
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(edit_dialog.accept)
            button_box.rejected.connect(edit_dialog.reject)
            edit_layout.addWidget(button_box)
            
            # Show dialog and handle result
            if edit_dialog.exec() == QDialog.Accepted:
                # Get values from form
                if is_new:
                    new_id = profile_id_edit.text().strip().lower().replace(" ", "_")
                    if not new_id:
                        QMessageBox.warning(dialog, "Invalid ID", "Profile ID cannot be empty.")
                        return
                    
                    # Check if ID exists
                    if new_id in self.settings["scan_profiles"]["value"]:
                        QMessageBox.warning(dialog, "Profile Exists", f"A profile with ID '{new_id}' already exists.")
                        return
                    
                    profile_id = new_id
                
                # Create updated profile
                updated_profile = {
                    "name": profile_name_edit.text(),
                    "description": profile_desc_edit.text(),
                    "arguments": profile_args_edit.text(),
                    "timeout": int(profile_timeout_edit.text() or "300")
                }
                
                # Update settings
                profiles = self.settings["scan_profiles"]["value"].copy()
                profiles[profile_id] = updated_profile
                self.settings["scan_profiles"]["value"] = profiles
                
                # Update scan type choices if needed
                if profile_id not in self.settings["scan_type"]["choices"]:
                    choices = list(self.settings["scan_type"]["choices"])
                    choices.append(profile_id)
                    self.settings["scan_type"]["choices"] = choices
                    
                    # Update the scan type combo box
                    if hasattr(self, "scan_type_combo") and self.scan_type_combo is not None:
                        current_text = self.scan_type_combo.currentText()
                        self.scan_type_combo.clear()
                        self.scan_type_combo.addItems(choices)
                        # Restore selection if possible
                        if current_text in choices:
                            self.scan_type_combo.setCurrentText(current_text)
                
                # Refresh the table
                refresh_table()
                
                return True
            
            return False
            
        # Handle new profile button
        def on_new_profile():
            edit_profile_dialog(is_new=True)
            
        # Handle edit profile button
        def on_edit_profile():
            selected_indexes = profile_table.selectedIndexes()
            if not selected_indexes:
                return
                
            row = selected_indexes[0].row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            
            edit_profile_dialog(profile_id, is_new=False)
            
        # Handle delete profile button
        def on_delete_profile():
            selected_indexes = profile_table.selectedIndexes()
            if not selected_indexes:
                return
                
            row = selected_indexes[0].row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            
            # Check if built-in
            if profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]:
                QMessageBox.warning(dialog, "Cannot Delete", "Built-in profiles cannot be deleted.")
                return
                
            # Confirm deletion
            result = QMessageBox.question(
                dialog, 
                "Confirm Deletion",
                f"Are you sure you want to delete the profile '{profile_id}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                # Delete the profile
                profiles = self.settings["scan_profiles"]["value"].copy()
                if profile_id in profiles:
                    del profiles[profile_id]
                
                # Update settings
                self.settings["scan_profiles"]["value"] = profiles
                
                # Remove from choices if present
                if profile_id in self.settings["scan_type"]["choices"]:
                    choices = list(self.settings["scan_type"]["choices"])
                    choices.remove(profile_id)
                    self.settings["scan_type"]["choices"] = choices
                    
                    # Update the scan type combo box
                    if hasattr(self, "scan_type_combo") and self.scan_type_combo is not None:
                        current_text = self.scan_type_combo.currentText()
                        self.scan_type_combo.clear()
                        self.scan_type_combo.addItems(choices)
                        # Restore selection if possible, otherwise select first
                        if current_text in choices:
                            self.scan_type_combo.setCurrentText(current_text)
                        elif choices:
                            self.scan_type_combo.setCurrentIndex(0)
                        # Trigger description update
                        if self.scan_type_combo.count() > 0:
                            self.scan_type_combo.currentIndexChanged.emit(self.scan_type_combo.currentIndex())
                
                # Refresh the table
                refresh_table()
        
        # Connect button signals
        new_button.clicked.connect(on_new_profile)
        edit_button.clicked.connect(on_edit_profile)
        delete_button.clicked.connect(on_delete_profile)
        
        # Allow double-click to edit
        def on_double_click(item):
            row = item.row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            edit_profile_dialog(profile_id, is_new=False)
            
        profile_table.itemDoubleClicked.connect(on_double_click)
        
        # Show the dialog
        dialog.exec_()

    def quick_ping_scan(self, network_range, display_label=None):
        """
        Perform a quick ping scan using system commands
        
        This provides an alternative to nmap for fast scanning, especially
        when just checking if hosts are alive.
        
        Args:
            network_range: Network range or list of IPs to scan
            display_label: Optional label for logging/status
            
        Returns:
            bool: True if scan started successfully, False otherwise
        """
        # Check if already scanning
        if self._is_scanning:
            logger.warning("Scan already in progress")
            return False
            
        # Clean up any previous scan
        self._cleanup_previous_scan()
        
        # Convert network range to list of IPs to ping
        try:
            import ipaddress
            import subprocess
            import threading
            import platform
            from PySide6.QtCore import QObject, Signal, QThread
            
            # Create a worker object with signals for thread-safe UI updates
            class PingScanWorker(QObject):
                progress_updated = Signal(int, int)  # current, total
                status_updated = Signal(str)  # status message
                device_found = Signal(dict)  # device data
                scan_complete = Signal(dict)  # scan results
                
                def __init__(self, ip_list, network_range):
                    super().__init__()
                    self.ip_list = ip_list
                    self.network_range = network_range
                    self.should_stop = False
                    
                def stop(self):
                    self.should_stop = True
                    
                def run(self):
                    self._run_scan()
                    
                def _ping_host(self, ip, index):
                    if self.should_stop:
                        return
                        
                    # Determine ping command based on OS
                    system = platform.system().lower()
                    if system == "windows":
                        ping_cmd = ["ping", "-n", "1", "-w", "500", str(ip)]
                        ping_success = lambda proc: proc.returncode == 0
                    else:  # Linux and macOS
                        ping_cmd = ["ping", "-c", "1", "-W", "1", str(ip)]
                        ping_success = lambda proc: proc.returncode == 0
                        
                    try:
                        # Execute ping command
                        proc = subprocess.run(
                            ping_cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=1
                        )
                        
                        # Check result
                        if ping_success(proc):
                            # Log success
                            self.status_updated.emit(f"Host {ip} is up")
                            
                            # Create device data
                            host_data = {
                                "ip_address": str(ip),
                                "scan_source": "ping",
                                "alias": f"Device at {ip}",
                                "tags": ["scanned", "ping"]
                            }
                            
                            # Try to get hostname
                            try:
                                import socket
                                hostname = socket.getfqdn(str(ip))
                                if hostname and hostname != str(ip):
                                    host_data["hostname"] = hostname
                                    host_data["alias"] = hostname
                            except Exception:
                                pass
                                
                            # Emit device found signal
                            self.device_found.emit(host_data)
                        else:
                            # Host is not up, don't add it
                            logger.debug(f"Host {ip} did not respond to ping")
                            
                    except Exception as e:
                        logger.debug(f"Error pinging {ip}: {e}")
                        
                    finally:
                        # Update progress through signal
                        if not self.should_stop:
                            self.progress_updated.emit(index + 1, len(self.ip_list))
                            
                def _run_scan(self):
                    start_time = time.time()
                    alive_hosts = []
                    threads = []
                    max_concurrent = min(50, len(self.ip_list))  # Limit concurrent threads
                    
                    try:
                        for i, ip in enumerate(self.ip_list):
                            if self.should_stop:
                                break
                                
                            # Create and start thread
                            t = threading.Thread(target=self._ping_host, args=(ip, i))
                            t.daemon = True
                            threads.append(t)
                            t.start()
                            
                            # Limit concurrent threads
                            while len([t for t in threads if t.is_alive()]) >= max_concurrent:
                                time.sleep(0.01)
                                
                            # Update status periodically
                            if i % 10 == 0:
                                self.status_updated.emit(f"Scanned {i} of {len(self.ip_list)} addresses...")
                                
                        # Wait for all threads to complete
                        for t in threads:
                            if self.should_stop:
                                break
                            t.join(timeout=0.5)
                            
                        # Scan complete
                        scan_time = time.time() - start_time
                        self.status_updated.emit(f"Scan complete: Found {len(alive_hosts)} devices in {round(scan_time, 1)} seconds")
                        
                        # Store results
                        scan_results = {
                            "network_range": self.network_range,
                            "scan_type": "quick_ping",
                            "total_hosts": len(self.ip_list),
                            "devices_found": len(alive_hosts),
                            "scan_time": scan_time,
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # Emit scan complete signal
                        self.scan_complete.emit(scan_results)
                        
                    except Exception as e:
                        logger.error(f"Error during ping scan: {e}")
                        self.status_updated.emit(f"Error during scan: {e}")
            
            # Set scanning flag
            self._is_scanning = True
            self._update_scan_button_state()
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
            
            # Clear the scan log and reset progress
            self._scan_log = []
            label = display_label or (network_range if isinstance(network_range, str) else "Selected devices")
            self.log_message(f"Starting quick ping scan of {label}")
            self._scan_results = {}
            
            # Extract IP addresses from network range or list
            ip_list = []
            try:
                if isinstance(network_range, (list, tuple, set)):
                    for entry in network_range:
                        if not entry:
                            continue
                        try:
                            ip_list.append(ipaddress.ip_address(str(entry)))
                        except Exception:
                            continue
                else:
                    # For CIDR notation like 192.168.1.0/24
                    if '/' in network_range:
                        net = ipaddress.ip_network(network_range, strict=False)
                        ip_list = list(net.hosts())
                        
                    # For range notation like 192.168.1.1-10
                    elif '-' in network_range:
                        parts = network_range.split('-')
                        if len(parts) == 2:
                            start_ip = parts[0].strip()
                            
                            # Check if the second part is a full IP or just the last octet
                            if '.' in parts[1]:
                                end_ip = parts[1].strip()
                            else:
                                # Assume it's just the last octet
                                start_parts = start_ip.split('.')
                                end_ip = f"{start_parts[0]}.{start_parts[1]}.{start_parts[2]}.{parts[1].strip()}"
                                
                            # Generate IP range
                            start = int(ipaddress.IPv4Address(start_ip))
                            end = int(ipaddress.IPv4Address(end_ip))
                            
                            for i in range(start, end + 1):
                                ip_list.append(ipaddress.IPv4Address(i))
                    
                    # Single IP address
                    else:
                        ip_list = [ipaddress.ip_address(network_range)]
            except Exception as e:
                self.log_message(f"Error parsing network range: {e}")
                self._is_scanning = False
                return False
                
            if not ip_list:
                self.log_message("No valid IP addresses to scan")
                self._is_scanning = False
                return False
                
            self.log_message(f"Scanning {len(ip_list)} addresses...")
            
            # Update progress bar
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setRange(0, len(ip_list))
                self.progress_bar.setValue(0)
            
            # Create worker thread
            self._ping_scan_thread = QThread()
            self._ping_scan_worker = PingScanWorker(ip_list, label)
            self._ping_scan_worker.moveToThread(self._ping_scan_thread)
            
            # Connect worker signals
            self._ping_scan_worker.progress_updated.connect(self._on_ping_scan_progress)
            self._ping_scan_worker.status_updated.connect(self.log_message)
            self._ping_scan_worker.device_found.connect(self._on_device_found)
            self._ping_scan_worker.scan_complete.connect(self._on_ping_scan_complete)
            
            # Connect thread signals
            self._ping_scan_thread.started.connect(self._ping_scan_worker.run)
            
            # Start the worker thread
            self._ping_scan_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting ping scan: {e}")
            self._is_scanning = False
            self.log_message(f"Error starting scan: {e}")
            return False
            
    def _on_ping_scan_progress(self, current, total):
        """Handle ping scan progress updates in a thread-safe way"""
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setValue(current)
            
        if hasattr(self, "status_label") and self.status_label:
            percentage = int((current / total) * 100) if total > 0 else 0
            self.status_label.setText(f"Scanning: {current}/{total} ({percentage}%)")
            
    def _on_ping_scan_complete(self, results):
        """Handle ping scan completion in a thread-safe way"""
        self._is_scanning = False
        self._scan_results = results
        self._update_scan_button_state()
        # Update status
        if hasattr(self, "status_label"):
            self.status_label.setText("Scan complete")
        self._update_results_footer(f"Scan complete | {results.get('devices_found', 0)} devices")
            
        # Set progress to 100%
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(self.progress_bar.maximum())
            
        # Clean up thread
        if hasattr(self, "_ping_scan_thread") and self._ping_scan_thread.isRunning():
            self._ping_scan_thread.quit()
            self._ping_scan_thread.wait(1000)
            
        # Emit the scan completed signal
        self.scan_completed.emit(results)
            
    def stop_ping_scan(self):
        """Stop the ping scan if it's running"""
        if hasattr(self, "_ping_scan_worker"):
            self._ping_scan_worker.stop()
            self.log_message("Stopping ping scan...")
            return True
        return False

# Create plugin instance (will be loaded by the plugin manager)
logger.info("Creating Network Scanner plugin instance")
plugin_instance = NetworkScannerPlugin()
logger.info("Network Scanner plugin instance created") 