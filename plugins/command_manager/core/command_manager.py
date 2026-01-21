#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Core Command Manager Plugin implementation
"""

import os
import datetime
from pathlib import Path
from loguru import logger

from PySide6.QtCore import Qt, Signal, Slot, QObject
from PySide6.QtWidgets import QMessageBox, QMenu, QDialog, QToolBar
from PySide6.QtGui import QIcon, QAction

# Import interfaces from the main application
from src.core.plugin_interface import PluginInterface

# Local imports
from plugins.command_manager.ui.command_dialog import CommandDialog
from plugins.command_manager.ui.credential_manager import CredentialManager
from plugins.command_manager.ui.command_output_panel import CommandOutputPanel
from plugins.command_manager.ui.command_set_editor import CommandSetEditor
from plugins.command_manager.ui.settings_dialog import SettingsDialog

# Import from core components
from .plugin_setup import register_ui, register_context_menu
from .command_handler import CommandHandler
from .output_handler import OutputHandler

# Import utilities
from plugins.command_manager.utils.credential_store import CredentialStore

class CommandManagerPlugin(PluginInterface):
    """Command Manager Plugin for NetWORKS"""
    
    def __init__(self):
        """Initialize the plugin"""
        super().__init__()
        
        logger.debug("Initializing Command Manager Plugin")
        
        # Plugin data directories
        self.data_dir = None
        self.commands_dir = None
        self.output_dir = None
        
        # Plugin settings
        self.settings = {
            "export_filename_template": {
                "name": "Export Filename Template",
                "description": "Template for exported command filenames. Available variables: {hostname}, {ip}, {command}, {date}, and any device property.",
                "type": "string",
                "default": "{hostname}_{command}_{date}",
                "value": "{hostname}_{command}_{date}"
            },
            "export_date_format": {
                "name": "Export Date Format",
                "description": "Date format for exported filenames (using Python strftime format)",
                "type": "string",
                "default": "%Y%m%d",
                "value": "%Y%m%d"
            },
            "export_command_format": {
                "name": "Export Command Format",
                "description": "How to format command names in exported filenames (truncated, full, etc.)",
                "type": "choice",
                "choices": ["truncated", "full", "sanitized"],
                "default": "truncated",
                "value": "truncated"
            }
        }
        
        # UI components
        self.command_dialog = None
        self.output_panel = None
        self.toolbar_action = None
        self.toolbar = None
        self.context_menu_actions = {}
        
        # Create handlers
        self.command_handler = None
        self.output_handler = None
        
        # Data components
        self.command_sets = {}  # {device_type: {firmware: CommandSet}}
        self.credential_store = None
        self.outputs = {}       # {device_id: {command_id: {timestamp: output}}}
        
        logger.debug("Command Manager Plugin instance initialized")
        
    def initialize(self, app, plugin_info):
        """Initialize the plugin"""
        self.app = app
        self.plugin_info = plugin_info
        self.main_window = app.main_window
        self.device_manager = app.device_manager
        
        logger.debug(f"Command Manager initialization started. App: {app}, plugin_info: {plugin_info}")
        
        # Create data directories
        self._create_data_directories()
        
        # Create credential store
        try:
            data_dir = Path(self.plugin_info.path) / "data"
            self.credential_store = CredentialStore(data_dir)
            # Set the device manager reference in the credential store
            self.credential_store.set_device_manager(self.device_manager)
            logger.debug(f"Credential store initialized with data_dir: {data_dir}")
        except Exception as e:
            logger.error(f"Error initializing credential store: {e}")
            logger.exception("Exception details:")
            self.credential_store = None
            
        # Initialize handlers
        self.command_handler = CommandHandler(self)
        self.output_handler = OutputHandler(self)
        
        # Load command outputs and command sets
        self.output_handler.load_command_outputs()
        self.command_handler.load_default_command_sets()
        
        # Create UI components and toolbar
        register_ui(self)
        
        # Register context menu items
        register_context_menu(self)
        
        # Connect signals
        self._connect_signals()
        
        # Mark as initialized
        self._initialized = True
        self.plugin_initialized.emit()
        
        logger.info("Command Manager plugin initialized successfully")
        return True
        
    def start(self):
        """Start the plugin"""
        logger.info(f"Starting {self.plugin_info.name} plugin")
        
        try:
            # Add toolbar to main window
            if self.toolbar is None:
                logger.error("Toolbar is None! Creating it now...")
                register_ui(self)
            
            if self.main_window is None:
                logger.error("Main window is None! Cannot add toolbar.")
            else:
                try:
                    self.main_window.addToolBar(self.toolbar)
                    logger.debug("Toolbar added to main window")
                    
                    # Apply style to reduce vertical margins on main toolbar buttons
                    main_toolbar = self.main_window.findChild(QToolBar)
                    if main_toolbar:
                        main_toolbar.setStyleSheet("""
                            QToolButton {
                                padding-top: 2px;
                                padding-bottom: 2px;
                                margin-top: 1px;
                                margin-bottom: 1px;
                            }
                        """)
                        logger.debug("Applied style to main toolbar")
                except Exception as e:
                    logger.error(f"Error adding toolbar to main window: {e}")
                    logger.exception("Exception details:")
            
            # Legacy device context menu items via device_manager (keeping for compatibility)
            logger.debug("Adding device context menu items via device_manager")
            try:
                if hasattr(self.device_manager, 'add_context_menu_item'):
                    self.device_manager.add_context_menu_item(
                        "Run Commands",
                        self._on_device_context_run_commands
                    )
                    
                    self.device_manager.add_context_menu_item(
                        "Manage Credentials",
                        self._on_device_context_credentials
                    )
                    logger.debug("Context menu items added via device_manager")
                else:
                    logger.debug("add_context_menu_item not found in device_manager")
            except Exception as e:
                logger.error(f"Error adding context menu items via device_manager: {e}")
                logger.exception("Exception details:")
            
            # Add tabs to device details
            logger.debug("Adding tabs to device details")
            try:
                self.device_manager.add_device_tab_provider(self)
                logger.debug("Tab provider added")
            except Exception as e:
                logger.error(f"Error adding tab provider: {e}")
                logger.exception("Exception details:")
            
            logger.info(f"{self.plugin_info.name} plugin started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting {self.plugin_info.name} plugin: {e}")
            logger.exception("Exception details:")
            return False
        
    def stop(self):
        """Stop the plugin"""
        if not super().stop():
            return False
            
        # Disconnect signals
        self._disconnect_signals()
        
        logger.info("Command Manager Plugin stopped")
        return True
        
    def cleanup(self):
        """Clean up plugin resources"""
        logger.info(f"{self.plugin_info.name} Plugin cleaned up")
        
        try:
            # Save command sets
            if self.command_handler:
                self.command_handler.save_command_sets()
            
            # Save command outputs
            if self.output_handler:
                self.output_handler.save_command_outputs()
            
            # Ensure credentials are saved
            # Device credentials are saved with workspace (via device properties)
            # Group and subnet credentials are saved to files immediately when set
            # But we'll ensure workspace is saved to persist device credentials
            if self.device_manager:
                try:
                    self.device_manager.save_workspace()
                    logger.debug("Workspace saved during plugin cleanup to persist device credentials")
                except Exception as e:
                    logger.warning(f"Could not save workspace during cleanup: {e}")
                    
            # Close command dialog if open
            if hasattr(self, 'command_dialog') and self.command_dialog:
                try:
                    self.command_dialog.close()
                    self.command_dialog = None
                except Exception as e:
                    logger.error(f"Error closing command dialog: {e}")
            
            # Clean up UI
            if hasattr(self, 'output_panel'):
                self.output_panel = None
            
            # Unregister context menu actions
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'device_table'):
                try:
                    # Unregister context menu actions
                    logger.debug("Unregistering context menu actions")
                    self.main_window.device_table.unregister_context_menu_action("Run Commands")
                    self.main_window.device_table.unregister_context_menu_action("Manage Credentials")
                    logger.debug("Context menu actions unregistered")
                except Exception as e:
                    logger.error(f"Error unregistering context menu actions: {e}")
                    logger.exception("Exception details:")
                    
            # Disconnect signals
            self._disconnect_signals()
            
            return True
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.exception("Exception details:")
            return False
    
    def _create_data_directories(self):
        """Create data directories for the plugin"""
        # Main data directory
        self.data_dir = Path(self.plugin_info.path) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Command sets directory
        self.commands_dir = self.data_dir / "commands"
        self.commands_dir.mkdir(exist_ok=True)
        
        # Command outputs directory
        self.output_dir = self.data_dir / "outputs"
        self.output_dir.mkdir(exist_ok=True)
        
    def _connect_signals(self):
        """Connect signals to slots"""
        logger.debug("Connecting signals")
        try:
            # Connect to device manager signals
            if hasattr(self.device_manager, 'device_added'):
                self.device_manager.device_added.connect(self._on_device_added)
            else:
                logger.warning("device_added signal not found")
                
            if hasattr(self.device_manager, 'device_removed'):
                self.device_manager.device_removed.connect(self._on_device_removed)
            else:
                logger.warning("device_removed signal not found")
                
            if hasattr(self.device_manager, 'device_changed'):
                self.device_manager.device_changed.connect(self._on_device_changed)
            else:
                logger.warning("device_changed signal not found")
                
            if hasattr(self.device_manager, 'selection_changed'):
                self.device_manager.selection_changed.connect(self._on_selection_changed)
            else:
                logger.warning("selection_changed signal not found")
                
            logger.debug("Signals connected successfully")
        except Exception as e:
            logger.error(f"Error connecting signals: {e}")
            logger.exception("Exception details:")
    
    def _disconnect_signals(self):
        """Disconnect signals from slots"""
        logger.debug("Disconnecting signals")
        try:
            # Only disconnect if the signal exists and we're connected
            if hasattr(self.device_manager, 'device_added'):
                try:
                    self.device_manager.device_added.disconnect(self._on_device_added)
                    logger.debug("Disconnected device_added signal")
                except (RuntimeError, TypeError):
                    logger.debug("device_added signal was not connected")
                    
            if hasattr(self.device_manager, 'device_removed'):
                try:
                    self.device_manager.device_removed.disconnect(self._on_device_removed)
                    logger.debug("Disconnected device_removed signal")
                except (RuntimeError, TypeError):
                    logger.debug("device_removed signal was not connected")
                    
            if hasattr(self.device_manager, 'device_changed'):
                try:
                    self.device_manager.device_changed.disconnect(self._on_device_changed)
                    logger.debug("Disconnected device_changed signal")
                except (RuntimeError, TypeError):
                    logger.debug("device_changed signal was not connected")
                    
            if hasattr(self.device_manager, 'selection_changed'):
                try:
                    self.device_manager.selection_changed.disconnect(self._on_selection_changed)
                    logger.debug("Disconnected selection_changed signal")
                except (RuntimeError, TypeError):
                    logger.debug("selection_changed signal was not connected")
                    
            logger.debug("Signals disconnected successfully")
        except Exception as e:
            logger.error(f"Error disconnecting signals: {e}")
            logger.exception("Exception details:")
    
    # Event handlers for device manager signals
    
    def _on_device_added(self, device):
        """Handle device added event"""
        # Update UI if necessary
        if self.command_dialog:
            self.command_dialog.refresh_devices()
            
        if self.output_panel:
            self.output_panel.refresh()
    
    def _on_device_removed(self, device):
        """Handle device removed event"""
        # Update UI if necessary
        if self.command_dialog:
            self.command_dialog.refresh_devices()
            
        if self.output_panel:
            self.output_panel.refresh()
    
    def _on_device_changed(self, device):
        """Handle device changed event"""
        # Update UI if necessary
        if self.command_dialog:
            self.command_dialog.refresh_devices()
            
        if self.output_panel:
            self.output_panel.refresh()
    
    def _on_selection_changed(self, devices):
        """Handle device selection changed"""
        # Update commands and output panels if available
        try:
            # Update the output panel with the selected device
            if self.output_panel and devices:
                self.output_panel.set_device(devices[0])
            
            # Update the commands panel if it exists
            if hasattr(self, 'commands_panel_widget') and self.commands_panel_widget and devices:
                self.output_handler.update_commands_panel(devices[0])
        except Exception as e:
            logger.error(f"Error updating panels: {e}")
            logger.exception("Exception details:")
    
    # Plugin API methods - to be called by other components
    
    def get_toolbar_actions(self):
        """Get actions to be added to the toolbar"""
        return [self.toolbar_action, self.batch_export_action, self.credential_manager_action]
        
    def find_existing_menu(self, menu_name):
        """Find an existing menu by name (case-insensitive)
        
        This method helps plugins integrate with existing menus rather than creating
        duplicate menus. It performs a case-insensitive search for standard menus
        like File, Edit, View, Tools, etc.
        
        Args:
            menu_name (str): The name of the menu to find
            
        Returns:
            str: The exact name of the menu if found, otherwise the original name
        """
        if not hasattr(self.main_window, 'menuBar') or not callable(self.main_window.menuBar):
            logger.warning("Main window does not have a menuBar() method")
            return menu_name
            
        menu_bar = self.main_window.menuBar()
        
        # Get all existing menu titles
        existing_menus = {}
        for menu in menu_bar.findChildren(QMenu):
            if menu.title():
                existing_menus[menu.title().lower()] = menu.title()
                
        logger.debug(f"Existing menus: {existing_menus}")
        
        # Look for a case-insensitive match
        menu_name_lower = menu_name.lower()
        if menu_name_lower in existing_menus:
            logger.debug(f"Found existing menu {existing_menus[menu_name_lower]} for {menu_name}")
            return existing_menus[menu_name_lower]
            
        return menu_name
        
    def get_menu_actions(self):
        """Get actions to be added to the main menu
        
        Returns:
            dict: Dictionary of menu name -> list of actions
        """
        logger.debug("Getting menu actions")
        
        # Create actions
        actions = {}
        
        # Tools menu
        tools_menu = []
        
        # Run Commands action
        run_commands_action = QAction("Run Commands", self.main_window)
        run_commands_action.triggered.connect(self._on_run_commands)
        tools_menu.append(run_commands_action)
        
        # Manage Credentials action
        credentials_action = QAction("Manage Credentials", self.main_window)
        credentials_action.triggered.connect(self._on_manage_credentials)
        tools_menu.append(credentials_action)
        
        # Edit Command Sets action
        edit_commands_action = QAction("Edit Command Sets", self.main_window)
        edit_commands_action.triggered.connect(self._on_edit_command_sets)
        tools_menu.append(edit_commands_action)
        
        # Batch Export action
        batch_export_action = QAction("Batch Command Export", self.main_window)
        batch_export_action.triggered.connect(self._on_batch_export)
        tools_menu.append(batch_export_action)
        
        # Settings action
        settings_action = QAction("Command Manager Settings", self.main_window)
        settings_action.triggered.connect(self._on_open_settings)
        tools_menu.append(settings_action)
        
        actions["Tools"] = tools_menu
        
        logger.debug(f"Returning {len(actions)} menu actions")
        return actions
        
    def get_device_context_menu_actions(self):
        """Get actions to be added to the device context menu"""
        return list(self.context_menu_actions.values())
        
    def get_device_tabs(self, device):
        """Get tabs to be added to the device details view
        
        Args:
            device: The device object
            
        Returns:
            list: List of (tab_name, tab_widget) tuples
        """
        # Create a commands tab for this device
        commands_tab = self.output_handler.create_device_command_tab(device)
        
        # Create a command output panel specifically for this device
        output_panel = CommandOutputPanel(self, device)
        
        # Return tabs with Commands tab first for better visibility
        return [
            ("Commands", commands_tab),
            ("Command Outputs", output_panel)
        ]
    
    def get_device_panels(self):
        """Get panels to be added to the device properties panel
        
        Returns:
            list: List of (panel_name, panel_widget) tuples
        """
        return self.output_handler.get_device_panels()
        
    # Event handlers for UI actions
    
    def _on_device_context_run_commands(self, devices):
        """Handle run commands context menu item"""
        # Fix: Check if devices is a single Device object or a list
        if not isinstance(devices, list):
            # Convert to a list with a single device
            devices = [devices]
        
        dialog = CommandDialog(self, devices, parent=self.main_window)
        dialog.exec()
        
    def _on_device_context_credentials(self, devices):
        """Handle credential manager context menu action
        
        Args:
            devices: List of selected devices
        """
        logger.debug(f"Opening credential manager for {len(devices)} devices")
        
        try:
            from plugins.command_manager.ui.credential_manager import CredentialManager
            dialog = CredentialManager(self, devices=devices, parent=self.main_window)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening credential manager: {e}")
            logger.exception("Exception details:")
            
            # Show error dialog
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An error occurred while opening the credential manager: {str(e)}"
            )
    
    def _on_group_context_run_commands(self, groups):
        """Handle run commands on group context menu action
        
        Args:
            groups: List of selected device groups
        """
        logger.debug(f"Opening command dialog for {len(groups)} device groups")
        
        try:
            # Get all devices from the selected groups
            all_devices = []
            for group in groups:
                try:
                    # Get all devices in this group (more reliable now with DeviceGroup class)
                    if hasattr(group, 'get_all_devices'):
                        group_devices = group.get_all_devices()
                    elif hasattr(group, 'devices'):
                        group_devices = group.devices
                    else:
                        logger.warning(f"Unknown group structure, cannot get devices: {group}")
                        continue
                        
                    # Add to all devices list, avoiding duplicates
                    for device in group_devices:
                        if device not in all_devices:
                            all_devices.append(device)
                            
                except Exception as e:
                    logger.error(f"Error getting devices from group: {e}")
            
            if not all_devices:
                logger.warning("No devices found in selected groups")
                QMessageBox.warning(
                    self.main_window,
                    "No Devices",
                    "No devices found in the selected groups."
                )
                return
                
            logger.debug(f"Found {len(all_devices)} unique devices in selected groups")
            
            # Open command dialog with these devices
            from plugins.command_manager.ui.command_dialog import CommandDialog
            self.command_dialog = CommandDialog(self, devices=all_devices, parent=self.main_window)
            self.command_dialog.show()
        except Exception as e:
            logger.error(f"Error opening command dialog for group: {e}")
            logger.exception("Exception details:")
            
            # Show error dialog
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An error occurred while opening the command dialog: {str(e)}"
            )
    
    def _on_group_context_credentials(self, groups):
        """Handle credential manager context menu action for groups
        
        Args:
            groups: List of selected device groups
        """
        logger.debug(f"Opening credential manager for {len(groups)} device groups")
        
        try:
            from plugins.command_manager.ui.credential_manager import CredentialManager
            dialog = CredentialManager(self, groups=groups, parent=self.main_window)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening credential manager for groups: {e}")
            logger.exception("Exception details:")
            
            # Show error dialog
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An error occurred while opening the credential manager: {str(e)}"
            )
    
    def _on_subnet_context_run_commands(self, subnets):
        """Handle run commands on subnet context menu action
        
        Args:
            subnets: List of selected subnets
        """
        logger.debug(f"Opening command dialog for {len(subnets)} subnets")
        
        try:
            # Get all devices from the selected subnets
            all_devices = []
            for subnet in subnets:
                if 'devices' in subnet:
                    for device in subnet['devices']:
                        if device not in all_devices:
                            all_devices.append(device)
            
            if not all_devices:
                QMessageBox.warning(
                    self.main_window,
                    "No Devices",
                    "The selected subnets do not contain any devices."
                )
                return
            
            # Open command dialog with these devices
            from plugins.command_manager.ui.command_dialog import CommandDialog
            if not hasattr(self, 'command_dialog') or not self.command_dialog:
                self.command_dialog = CommandDialog(self, all_devices, self.main_window)
            else:
                self.command_dialog.set_selected_devices(all_devices)
                
            self.command_dialog.show()
            self.command_dialog.raise_()
            self.command_dialog.activateWindow()
            
            # Switch to the Subnets tab and select the subnets
            self.command_dialog.target_tabs.setCurrentIndex(2)
            
            # Select the subnets in the subnet table
            self.command_dialog.subnet_table.clearSelection()
            for row in range(self.command_dialog.subnet_table.rowCount()):
                subnet_item = self.command_dialog.subnet_table.item(row, 0)
                if subnet_item and subnet_item.data(Qt.UserRole)['subnet'] in [s['subnet'] for s in subnets]:
                    self.command_dialog.subnet_table.selectRow(row)
            
        except Exception as e:
            logger.error(f"Error opening command dialog for subnets: {e}")
            logger.exception("Exception details:")
            
            # Show error dialog
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An error occurred while opening the command dialog: {str(e)}"
            )
    
    def _on_subnet_context_credentials(self, subnets):
        """Handle credential manager context menu action for subnets
        
        Args:
            subnets: List of selected subnets
        """
        logger.debug(f"Opening credential manager for {len(subnets)} subnets")
        
        try:
            from plugins.command_manager.ui.credential_manager import CredentialManager
            dialog = CredentialManager(self, subnets=subnets, parent=self.main_window)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening credential manager for subnets: {e}")
            logger.exception("Exception details:")
            
            # Show error dialog
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An error occurred while opening the credential manager: {str(e)}"
            )
    
    # Methods for credential handling
    
    def get_all_device_credentials(self):
        """Get all device credentials"""
        return self.credential_store.get_all_device_credentials() if self.credential_store else {}
        
    def get_all_group_credentials(self):
        """Get all group credentials"""
        return self.credential_store.get_all_group_credentials() if self.credential_store else {}
        
    def get_all_subnet_credentials(self):
        """Get all subnet credentials"""
        return self.credential_store.get_all_subnet_credentials() if self.credential_store else {}
        
    def get_device_credentials(self, device_id, device_ip=None, groups=None):
        """Get credentials for a device
        
        Args:
            device_id: The device ID
            device_ip: The device IP address (for subnet matching)
            groups: Optional list of group names the device belongs to
            
        Returns:
            dict: Credentials dictionary or None if not found
        """
        logger.debug(f"Getting credentials for device {device_id}")
        
        if not self.credential_store:
            logger.error("Credential store is not available")
            return None
        
        # 1. First try device-specific credentials
        device_credentials = self.credential_store.get_device_credentials(device_id)
        if device_credentials:
            logger.debug(f"Found device-specific credentials for {device_id}")
            return device_credentials
            
        # 2. If no device credentials, try group credentials
        if self.device_manager:
            try:
                # Get all groups this device belongs to using new method
                device_groups = self.device_manager.get_device_groups_for_device(device_id)
                
                if device_groups:
                    logger.debug(f"Found {len(device_groups)} groups for device {device_id}")
                    
                    # Try each group's credentials
                    for group in device_groups:
                        group_name = group.name if hasattr(group, 'name') else str(group)
                        group_credentials = self.credential_store.get_group_credentials(group_name)
                        if group_credentials:
                            logger.debug(f"Using credentials from group '{group_name}' for device {device_id}")
                            return group_credentials
            except Exception as e:
                logger.error(f"Error getting group credentials for device {device_id}: {e}")
                
        # 3. If still no credentials, try subnet matching
        if device_ip:
            try:
                # Extract subnet from IP
                parts = device_ip.split('.')
                if len(parts) == 4:
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                    subnet_credentials = self.credential_store.get_subnet_credentials(subnet)
                    if subnet_credentials:
                        logger.debug(f"Using credentials from subnet {subnet} for device {device_id}")
                        return subnet_credentials
            except Exception as e:
                logger.error(f"Error getting subnet credentials: {e}")
                
        logger.debug(f"No credentials found for device {device_id}")
        return None
        
    def get_group_credentials(self, group_name):
        """Get credentials for a device group
        
        Args:
            group_name: Name of the device group
            
        Returns:
            dict: Credentials dictionary or None if not found
        """
        logger.debug(f"Getting credentials for group {group_name}")
        
        if not self.credential_store:
            logger.error("Credential store is not available")
            return None
            
        return self.credential_store.get_group_credentials(group_name)
    
    def get_subnet_credentials(self, subnet):
        """Get credentials for a subnet
        
        Args:
            subnet: Subnet in CIDR notation (e.g. 192.168.1.0/24)
            
        Returns:
            dict: Credentials dictionary or None if not found
        """
        logger.debug(f"Getting credentials for subnet {subnet}")
        
        if not self.credential_store:
            logger.error("Credential store is not available")
            return None
            
        return self.credential_store.get_subnet_credentials(subnet)
    
    def set_device_credentials(self, device_id, credentials):
        """Set credentials for a device"""
        if hasattr(self, 'credential_store') and self.credential_store:
            return self.credential_store.set_device_credentials(device_id, credentials)
            
    def set_group_credentials(self, group_name, credentials):
        """Set credentials for a group"""
        if hasattr(self, 'credential_store') and self.credential_store:
            return self.credential_store.set_group_credentials(group_name, credentials)
            
    def set_subnet_credentials(self, subnet, credentials):
        """Set credentials for a subnet"""
        if hasattr(self, 'credential_store') and self.credential_store:
            return self.credential_store.set_subnet_credentials(subnet, credentials)
            
    def delete_device_credentials(self, device_id):
        """Delete credentials for a device"""
        if hasattr(self, 'credential_store') and self.credential_store:
            return self.credential_store.delete_device_credentials(device_id)
            
    def delete_group_credentials(self, group_name):
        """Delete credentials for a group"""
        if hasattr(self, 'credential_store') and self.credential_store:
            return self.credential_store.delete_group_credentials(group_name)
            
    def delete_subnet_credentials(self, subnet):
        """Delete credentials for a subnet"""
        if hasattr(self, 'credential_store') and self.credential_store:
            return self.credential_store.delete_subnet_credentials(subnet)
            
    # Methods for command set handling
    
    def get_device_types(self):
        """Get all available device types"""
        if hasattr(self, 'command_handler') and self.command_handler:
            return self.command_handler.get_device_types()
        return []
        
    def get_firmware_versions(self, device_type):
        """Get firmware versions for a device type"""
        if hasattr(self, 'command_handler') and self.command_handler:
            return self.command_handler.get_firmware_versions(device_type)
        return []
        
    def get_commands(self, device_type, firmware_version):
        """Get commands for a device type and firmware version"""
        if hasattr(self, 'command_handler') and self.command_handler:
            return self.command_handler.get_commands(device_type, firmware_version)
        return []
        
    def get_command_set(self, device_type, firmware_version):
        """Get command set for a device type and firmware version"""
        if hasattr(self, 'command_handler') and self.command_handler:
            return self.command_handler.get_command_set(device_type, firmware_version)
        return None
    
    def get_command_outputs(self, device_id):
        """Get command outputs for a device
        
        Args:
            device_id (str): The device ID
            
        Returns:
            dict: Dictionary of command_id -> {timestamp: output}
        """
        logger.debug(f"Getting command outputs for device {device_id}")
        
        # First try using the output handler if available
        if hasattr(self, 'output_handler') and self.output_handler:
            try:
                # Use the correct method name in OutputHandler
                device_outputs = self.output_handler.get_command_outputs(device_id)
                if device_outputs:
                    return device_outputs
            except Exception as e:
                logger.debug(f"Error getting outputs through handler: {e}")
                # Continue with direct access if handler fails
        
        # Fall back to direct access
        if hasattr(self, 'outputs') and device_id in self.outputs:
            return self.outputs.get(device_id, {})
            
        # Return empty dict if no outputs found
        return {}
    
    def add_command_output(self, device_id, command_id, output, command_text=None):
        """Add command output to history
        
        Args:
            device_id (str): Device ID
            command_id (str): Command ID
            output (str): Command output
            command_text (str, optional): Command text
        """
        logger.debug(f"Adding command output for device: {device_id}, command: {command_id}")
        
        # Delegate to output handler if available
        if hasattr(self, 'output_handler') and self.output_handler:
            try:
                self.output_handler.add_command_output(device_id, command_id, output, command_text)
                return True
            except Exception as e:
                logger.error(f"Error adding command output via handler: {e}")
                return False
        else:
            logger.error("No output handler available")
            return False
    
    def run_command(self, device, command, credentials=None):
        """Run a command on a device
        
        Args:
            device: Device to run command on
            command (str): Command to run
            credentials (dict, optional): Credentials to use
            
        Returns:
            dict: Command result with keys 'success' and 'output'
        """
        logger.debug(f"Running command on device: {device.id if hasattr(device, 'id') else 'Unknown'}")
        
        # Delegate to command handler if available
        if hasattr(self, 'command_handler') and self.command_handler:
            try:
                return self.command_handler.run_command(device, command, credentials)
            except Exception as e:
                logger.error(f"Error running command via handler: {e}")
                # Fall back to a basic error response
                return {
                    "success": False,
                    "output": f"Command: {command}\n\nError: {str(e)}"
                }
        else:
            # No command handler available
            logger.error("No command handler available")
            return {
                "success": False,
                "output": f"Command: {command}\n\nNo command handler available"
            }
    
    def _on_run_commands(self):
        """Handle run commands menu item"""
        # Implement the logic to open the command dialog
        pass
    
    def _on_manage_credentials(self):
        """Handle manage credentials menu item"""
        # Implement the logic to open the credential manager
        pass
    
    def _on_edit_command_sets(self):
        """Handle edit command sets menu item"""
        # Implement the logic to open the command set editor
        pass
    
    def _on_batch_export(self):
        """Open batch export dialog"""
        try:
            # Ensure the import is done properly with explicit import
            from PySide6.QtWidgets import QWidget
            from plugins.command_manager.reports.command_batch_export import CommandBatchExport
            
            dialog = CommandBatchExport(self, self.main_window)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening Command Batch Export: {e}")
            logger.exception("Exception details:")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.main_window,
                "Error Opening Command Batch Export",
                f"An error occurred while opening the Command Batch Export: {str(e)}"
            )
    
    def _on_open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self, self.main_window)
        result = dialog.exec()
        
        # If settings were changed, update UI components
        if result:
            logger.debug("Settings updated")
            # Refresh any UI components that depend on settings 