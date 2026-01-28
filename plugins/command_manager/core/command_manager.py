#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Core Command Manager Plugin implementation
"""

import os
import json
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
from . import credential_api
from . import plugin_actions

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
        self.temporary_command_sets = set()  # (device_type, firmware_version) for template-loaded sets
        self.saved_command_sets = {}  # {set_name: [row_indices]} for "Save Selection as Set"
        self.temporary_saved_sets = {}  # {set_name: [{"command", "alias", "description"}, ...]} for template-loaded sets
        self.credential_store = None
        self.outputs = {}       # {device_id: {command_id: {timestamp: output}}}
        self.pending_custom_commands_text = ""  # prefill for Custom Commands dialog (e.g. from Template Manager)

        # Programmatic run (run_command_set): worker, thread, progress dialog; only one run at a time
        self._run_command_set_worker = None
        self._run_command_set_thread = None
        self._run_command_set_progress_dialog = None
        self._run_command_set_used_device_type = None
        self._run_command_set_used_firmware_version = None

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
        
        # Load user-saved command sets (named selections)
        self._load_saved_command_sets_from_disk()
        
        # Create credential store (per-workspace: credentials live under current workspace)
        try:
            def get_workspace_credentials_dir():
                ws = getattr(self.device_manager, "current_workspace", "default")
                base = Path(getattr(self.device_manager, "workspaces_dir", "."))
                return base / ws / "plugins" / "command_manager" / "credentials"
            self.credential_store = CredentialStore(get_workspace_credentials_dir, device_manager=self.device_manager)
            logger.debug(
                "Credential store initialized (per-workspace: %s)",
                get_workspace_credentials_dir(),
            )
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
            
            # Try to connect to device table highlight changes if not already connected
            # (in case device table wasn't available during initialize)
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'device_table'):
                device_table = self.main_window.device_table
                if device_table and device_table.selectionModel():
                    try:
                        # Check if already connected by trying to disconnect first
                        device_table.selectionModel().selectionChanged.disconnect(self._on_table_highlight_changed)
                        # If we get here, it was connected, so reconnect it
                        device_table.selectionModel().selectionChanged.connect(self._on_table_highlight_changed)
                    except (RuntimeError, TypeError):
                        # Not connected yet, so connect it now
                        device_table.selectionModel().selectionChanged.connect(self._on_table_highlight_changed)
                        logger.debug("Connected to device table highlight changes in start()")
            
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
            
            # Connect to device table highlight changes to handle highlighted (but unchecked) devices
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'device_table'):
                device_table = self.main_window.device_table
                if device_table and device_table.selectionModel():
                    device_table.selectionModel().selectionChanged.connect(self._on_table_highlight_changed)
                    logger.debug("Connected to device table highlight changes")
                else:
                    logger.warning("Device table or selection model not available for highlight tracking")
            else:
                logger.warning("Main window or device table not available for highlight tracking")
                
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
            
            # Disconnect from device table highlight changes
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'device_table'):
                device_table = self.main_window.device_table
                if device_table and device_table.selectionModel():
                    try:
                        device_table.selectionModel().selectionChanged.disconnect(self._on_table_highlight_changed)
                        logger.debug("Disconnected device table highlight changes")
                    except (RuntimeError, TypeError):
                        logger.debug("Device table highlight signal was not connected")
                    
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
        """Handle device selection changed (checked devices)"""
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
    
    def _on_table_highlight_changed(self, selected, deselected):
        """Handle device table highlight changes (for highlighted but unchecked devices)"""
        # Only respond to highlights when no devices are checked
        checked_devices = self.device_manager.get_selected_devices()
        if checked_devices:
            # If devices are checked, use those instead (handled by _on_selection_changed)
            return
        
        # Get highlighted devices from the table
        try:
            if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'device_table'):
                device_table = self.main_window.device_table
                if device_table:
                    # Use the table's get_selected_devices method which returns highlighted devices when none are checked
                    highlighted_devices = device_table.get_selected_devices()
                    
                    if highlighted_devices and len(highlighted_devices) > 0:
                        # Update the output panel with the highlighted device
                        if self.output_panel:
                            self.output_panel.set_device(highlighted_devices[0])
                        
                        # Update the commands panel if it exists
                        if hasattr(self, 'commands_panel_widget') and self.commands_panel_widget:
                            self.output_handler.update_commands_panel(highlighted_devices[0])
        except Exception as e:
            logger.error(f"Error updating panels from highlight: {e}")
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
        
        tools_menu_name = self.find_existing_menu("Tools")
        actions[tools_menu_name] = tools_menu
        
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
        
    # Event handlers for UI actions (delegate to plugin_actions)
    def _on_device_context_run_commands(self, devices):
        """Handle run commands context menu item"""
        plugin_actions.on_device_context_run_commands(self, devices)

    def _on_device_context_credentials(self, devices):
        """Handle credential manager context menu action for devices."""
        plugin_actions.on_device_context_credentials(self, devices)

    def _on_group_context_run_commands(self, groups):
        """Handle run commands on group context menu action"""
        plugin_actions.on_group_context_run_commands(self, groups)

    def _on_group_context_credentials(self, groups):
        """Handle credential manager context menu action for groups"""
        plugin_actions.on_group_context_credentials(self, groups)

    def _on_subnet_context_run_commands(self, subnets):
        """Handle run commands on subnet context menu action"""
        plugin_actions.on_subnet_context_run_commands(self, subnets)

    def _on_subnet_context_credentials(self, subnets):
        """Handle credential manager context menu action for subnets"""
        plugin_actions.on_subnet_context_credentials(self, subnets)

    # Credential API (delegate to credential_api)
    def get_all_device_credentials(self):
        """Get all device credentials"""
        return credential_api.get_all_device_credentials(self)

    def get_all_group_credentials(self):
        """Get all group credentials"""
        return credential_api.get_all_group_credentials(self)

    def get_all_subnet_credentials(self):
        """Get all subnet credentials"""
        return credential_api.get_all_subnet_credentials(self)

    def get_device_credentials(self, device_id, device_ip=None, groups=None):
        """Get credentials for a device with fallback to group/subnet."""
        return credential_api.get_device_credentials(self, device_id, device_ip, groups)

    def get_group_credentials(self, group_name):
        """Get credentials for a device group"""
        return credential_api.get_group_credentials(self, group_name)

    def get_subnet_credentials(self, subnet):
        """Get credentials for a subnet (CIDR notation)"""
        return credential_api.get_subnet_credentials(self, subnet)

    def set_device_credentials(self, device_id, credentials):
        """Set credentials for a device"""
        return credential_api.set_device_credentials(self, device_id, credentials)

    def set_group_credentials(self, group_name, credentials):
        """Set credentials for a group"""
        return credential_api.set_group_credentials(self, group_name, credentials)

    def set_subnet_credentials(self, subnet, credentials):
        """Set credentials for a subnet"""
        return credential_api.set_subnet_credentials(self, subnet, credentials)

    def delete_device_credentials(self, device_id):
        """Delete credentials for a device"""
        return credential_api.delete_device_credentials(self, device_id)

    def delete_group_credentials(self, group_name):
        """Delete credentials for a group"""
        return credential_api.delete_group_credentials(self, group_name)

    def delete_subnet_credentials(self, subnet):
        """Delete credentials for a subnet"""
        return credential_api.delete_subnet_credentials(self, subnet)

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

    def add_command_set(self, command_set, temporary=False):
        """Add or update a command set (public API for Template Manager and UI).
        If temporary=True, the set is not persisted and is unloaded when applied (run) in the dialog."""
        if not self.command_handler:
            return
        self.command_handler.add_command_set(command_set, temporary=temporary)
        if temporary:
            self.temporary_command_sets.add((command_set.device_type, command_set.firmware_version))

    def is_temporary_command_set(self, device_type, firmware_version):
        """Return True if this command set is temporary (e.g. from Template Manager)."""
        return (device_type, firmware_version) in getattr(self, "temporary_command_sets", set())

    def delete_command_set(self, device_type, firmware_version):
        """Remove a command set from memory and disk."""
        self.temporary_command_sets.discard((device_type, firmware_version))
        if self.command_handler:
            self.command_handler.delete_command_set(device_type, firmware_version)

    def _is_command_run_in_progress(self):
        """Return True if a command run is in progress (dialog or programmatic). Only one run at a time."""
        if self.command_dialog and getattr(self.command_dialog, "worker_thread", None) and self.command_dialog.worker_thread.isRunning():
            return True
        if getattr(self, "_run_command_set_thread", None) and self._run_command_set_thread.isRunning():
            return True
        return False

    def _normalize_commands_to_dicts(self, command_set):
        """Convert command set commands to list of dicts {command, alias, description} for CommandWorker."""
        out = []
        for c in command_set.commands:
            if hasattr(c, "to_dict"):
                out.append(c.to_dict())
            elif isinstance(c, dict) and "command" in c:
                out.append(c)
            else:
                out.append({"command": str(c), "alias": "", "description": ""})
        return out

    def run_command_set(self, devices, command_set=None, device_type=None, firmware_version=None, show_progress=True):
        """Run a command set on a list of devices without opening the dialog.

        Used by Template Manager (and others) to apply templates or run stored sets.
        Results go to the device Command Output tab via add_command_output.
        Only one run (dialog or this) is allowed at a time.

        Args:
            devices: List of device objects.
            command_set: Optional CommandSet to run (in-memory; not added to stored sets).
            device_type: If command_set is None, resolve set by device_type and firmware_version.
            firmware_version: If command_set is None, resolve set by device_type and firmware_version.
            show_progress: If True, show a non-modal progress indicator.

        Returns:
            True if the run was started, False if no devices/commands, or another run is in progress.
        """
        from PySide6.QtCore import QThread, Qt
        from plugins.command_manager.ui.command_worker import CommandWorker

        if not devices or not isinstance(devices, list):
            return False
        if self._is_command_run_in_progress():
            logger.warning("run_command_set: another command run is already in progress")
            return False

        resolved_set = command_set
        if resolved_set is None:
            if not device_type or not firmware_version:
                return False
            resolved_set = self.get_command_set(device_type, firmware_version)
            if not resolved_set or not getattr(resolved_set, "commands", None):
                return False
            self._run_command_set_used_device_type = device_type
            self._run_command_set_used_firmware_version = firmware_version
        else:
            self._run_command_set_used_device_type = None
            self._run_command_set_used_firmware_version = None

        commands_list = self._normalize_commands_to_dicts(resolved_set)
        if not commands_list:
            return False

        self._run_command_set_thread = QThread()
        self._run_command_set_worker = CommandWorker(self, devices, commands_list, resolved_set)
        self._run_command_set_worker.moveToThread(self._run_command_set_thread)
        self._run_command_set_thread.started.connect(self._run_command_set_worker.run)
        self._run_command_set_worker.all_commands_complete.connect(
            self._on_run_command_set_complete, Qt.QueuedConnection
        )
        total = len(devices) * len(commands_list)
        if show_progress and self.main_window:
            from PySide6.QtWidgets import QProgressDialog
            self._run_command_set_progress_dialog = QProgressDialog(
                "Running commands...", None, 0, total, self.main_window
            )
            self._run_command_set_progress_dialog.setWindowTitle("Command Manager")
            self._run_command_set_progress_dialog.setMinimumDuration(0)
            self._run_command_set_progress_dialog.setModal(False)
            self._run_command_set_worker.command_progress.connect(
                self._on_run_command_set_progress, Qt.QueuedConnection
            )
        self._run_command_set_thread.finished.connect(self._on_run_command_set_thread_finished)
        self._run_command_set_thread.start()
        logger.debug("run_command_set started: %d devices, %d commands", len(devices), len(commands_list))
        return True

    def _on_run_command_set_progress(self, current, total):
        """Update progress dialog for programmatic run."""
        if getattr(self, "_run_command_set_progress_dialog", None) and self._run_command_set_progress_dialog:
            self._run_command_set_progress_dialog.setValue(current)
            self._run_command_set_progress_dialog.setMaximum(total)

    def _on_run_command_set_complete(self, command_set):
        """Clean up after programmatic run; delete temporary set if it was resolved by device_type/firmware."""
        dt = getattr(self, "_run_command_set_used_device_type", None)
        fw = getattr(self, "_run_command_set_used_firmware_version", None)
        if dt and fw and self.is_temporary_command_set(dt, fw):
            self.delete_command_set(dt, fw)
        if getattr(self, "_run_command_set_progress_dialog", None) and self._run_command_set_progress_dialog:
            self._run_command_set_progress_dialog.close()
            self._run_command_set_progress_dialog = None
        self._run_command_set_used_device_type = None
        self._run_command_set_used_firmware_version = None
        if getattr(self, "_run_command_set_thread", None):
            self._run_command_set_thread.quit()
            self._run_command_set_thread.wait()
        # Worker/thread references are cleared in _on_run_command_set_thread_finished (deleteLater)

    def _on_run_command_set_thread_finished(self):
        """Clean up thread/worker references when thread finishes (deleteLater then clear)."""
        w = getattr(self, "_run_command_set_worker", None)
        t = getattr(self, "_run_command_set_thread", None)
        self._run_command_set_worker = None
        self._run_command_set_thread = None
        if w:
            w.deleteLater()
        if t:
            t.deleteLater()

    def _saved_command_sets_path(self):
        """Path to the JSON file storing user-saved command set names and row indices."""
        return (self.data_dir or Path(self.plugin_info.path) / "data") / "saved_command_sets.json"
    
    def _load_saved_command_sets_from_disk(self):
        """Load saved command sets (named selections) from disk."""
        p = self._saved_command_sets_path()
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.saved_command_sets = {k: list(v) if isinstance(v, list) else [] for k, v in data.items()}
        except Exception as e:
            logger.warning("Could not load saved command sets: %s", e)
    
    def _persist_saved_command_sets(self):
        """Write saved command sets to disk."""
        p = self._saved_command_sets_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.saved_command_sets, f, indent=2)
        except Exception as e:
            logger.warning("Could not persist saved command sets: %s", e)
    
    def get_saved_command_sets(self):
        """Return user-saved command set names and their command row indices. Used by the command dialog Saved Sets list."""
        return dict(getattr(self, "saved_command_sets", {}))

    def get_temporary_saved_set_names(self):
        """Return names of temporary saved sets (e.g. from Template Manager). Shown in Saved Sets dropdown."""
        return list(getattr(self, "temporary_saved_sets", {}).keys())

    def get_temporary_saved_set_commands(self, name):
        """Return list of command dicts for a temporary saved set, or None if not found."""
        sets = getattr(self, "temporary_saved_sets", {})
        if name not in sets:
            return None
        return list(sets[name])

    def add_temporary_saved_set(self, name, commands):
        """Add a temporary saved set (e.g. from Template Manager). Shown in Saved Sets; not persisted.
        commands: list of dicts with keys command, alias, description (or Command objects with to_dict())."""
        if not name or not commands:
            return
        normalized = []
        for c in commands:
            if hasattr(c, "to_dict"):
                normalized.append(c.to_dict())
            elif isinstance(c, dict) and "command" in c:
                normalized.append({"command": c["command"], "alias": c.get("alias", ""), "description": c.get("description", "")})
            else:
                normalized.append({"command": str(c), "alias": "", "description": ""})
        if not hasattr(self, "temporary_saved_sets"):
            self.temporary_saved_sets = {}
        self.temporary_saved_sets[name.strip()] = normalized
    
    def save_command_set(self, name, selected_rows):
        """Save a named command set (list of command row indices). Returns True on success."""
        if not name or not isinstance(selected_rows, (list, tuple)):
            return False
        self.saved_command_sets[name.strip()] = list(selected_rows)
        self._persist_saved_command_sets()
        return True

    def open_dialog(self, device_type=None, firmware_version=None, temporary_saved_set_name=None):
        """Show the Command Manager dialog, optionally with a command set or temporary saved set selected.
        If temporary_saved_set_name is set (e.g. from Template Manager), that set is selected in Saved Sets."""
        from PySide6.QtCore import QTimer
        from plugins.command_manager.core.plugin_setup import show_command_dialog
        show_command_dialog(self)
        if self.command_dialog:
            dialog = self.command_dialog
            if temporary_saved_set_name:
                QTimer.singleShot(0, lambda: dialog.set_temporary_saved_set_selection(temporary_saved_set_name))
            elif device_type and firmware_version:
                QTimer.singleShot(0, lambda: dialog.set_command_set_selection(device_type, firmware_version))

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
        devices = None
        if hasattr(self.main_window, "device_table") and self.main_window.device_table:
            devices = self.main_window.device_table.get_selected_devices()
        if not devices and self.device_manager:
            devices = self.device_manager.get_selected_devices()
        if not devices:
            QMessageBox.warning(
                self.main_window,
                "No Devices Selected",
                "Please select one or more devices to run commands on.",
            )
            return
        dialog = CommandDialog(self, devices, parent=self.main_window)
        dialog.exec()

    def _on_manage_credentials(self):
        """Handle manage credentials menu item"""
        devices = None
        if hasattr(self.main_window, "device_table") and self.main_window.device_table:
            devices = self.main_window.device_table.get_selected_devices()
        if not devices and self.device_manager:
            devices = self.device_manager.get_selected_devices()
        dialog = CredentialManager(self, devices=devices or [], parent=self.main_window)
        dialog.exec()

    def _on_edit_command_sets(self):
        """Handle edit command sets menu item"""
        dialog = CommandSetEditor(self, self.main_window)
        dialog.exec()
    
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