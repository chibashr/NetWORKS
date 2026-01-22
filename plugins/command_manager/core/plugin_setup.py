#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin UI setup and registration functions
"""

from loguru import logger
from PySide6.QtWidgets import QWidget, QStyle
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction

from plugins.command_manager.ui.command_dialog import CommandDialog
from plugins.command_manager.ui.command_set_editor import CommandSetEditor
from plugins.command_manager.ui.settings_dialog import SettingsDialog
from plugins.command_manager.reports.command_batch_export import CommandBatchExport
from src.ui.material_icons import material_icon
from src.ui.scalable_toolbar import ScalableToolbar

def register_ui(plugin):
    """Create and register UI components for the plugin
    
    Args:
        plugin: The CommandManagerPlugin instance
    """
    logger.debug("Creating UI components")
    
    # Create toolbar action
    plugin.toolbar_action = QAction("Command Manager", plugin.main_window)
    plugin.toolbar_action.setToolTip("Manage and run commands on devices")
    plugin.toolbar_action.triggered.connect(lambda: show_command_dialog(plugin))
    logger.debug(f"Created toolbar_action: {plugin.toolbar_action}")
    
    # Create a prominent Credential Manager action for the main toolbar
    plugin.credential_manager_action = QAction("Credential Manager", plugin.main_window)
    plugin.credential_manager_action.setToolTip("Manage device credentials and access settings")
    plugin.credential_manager_action.triggered.connect(lambda: on_manage_credentials(plugin))
    plugin.credential_manager_action.setObjectName("CredentialManagerAction")
    logger.debug(f"Created credential_manager_action: {plugin.credential_manager_action}")
    
    # Create a batch export action for the main toolbar
    plugin.batch_export_action = QAction("Batch Export", plugin.main_window)
    plugin.batch_export_action.setToolTip("Export command outputs from multiple devices")
    plugin.batch_export_action.triggered.connect(lambda: on_batch_export(plugin))
    plugin.batch_export_action.setObjectName("BatchExportAction")
    logger.debug(f"Created batch_export_action: {plugin.batch_export_action}")
    
    # Create settings action
    plugin.settings_action = QAction("Settings", plugin.main_window)
    plugin.settings_action.setToolTip("Configure Command Manager settings")
    plugin.settings_action.triggered.connect(lambda: on_open_settings(plugin))
    plugin.settings_action.setObjectName("SettingsAction")
    logger.debug(f"Created settings_action: {plugin.settings_action}")
    
    if plugin.main_window:
        style = plugin.main_window.style()
        plugin.toolbar_action.setIcon(material_icon("devices", plugin.main_window, QStyle.SP_ComputerIcon))
        plugin.credential_manager_action.setIcon(material_icon("vpn_key", plugin.main_window, QStyle.SP_DialogApplyButton))
        plugin.batch_export_action.setIcon(material_icon("file_upload", plugin.main_window, QStyle.SP_DialogSaveButton))
        plugin.settings_action.setIcon(material_icon("settings", plugin.main_window, QStyle.SP_FileDialogDetailedView))
    
    # Create toolbar
    plugin.toolbar = create_toolbar(plugin)
    
    # Create context menu actions
    plugin.context_menu_actions = {}
    
    run_action = QAction("Run Commands", plugin.main_window)
    run_action.triggered.connect(lambda: on_context_run_commands(plugin))
    plugin.context_menu_actions["run_commands"] = run_action
    
    # Enhance the credential management action
    manage_creds_action = QAction("Manage Device Credentials", plugin.main_window)
    manage_creds_action.setToolTip("Configure username, password and connection settings")
    manage_creds_action.triggered.connect(lambda: on_context_manage_credentials(plugin))
    manage_creds_action.setObjectName("ContextMenuCredentialAction")
    plugin.context_menu_actions["manage_credentials"] = manage_creds_action
    
    logger.debug(f"Created context menu actions: {list(plugin.context_menu_actions.keys())}")
    
def create_toolbar(plugin):
    """Create plugin toolbar
    
    Args:
        plugin: The CommandManagerPlugin instance
        
    Returns:
        QToolBar: The created toolbar
    """
    logger.debug("Creating Command Manager toolbar")
    toolbar = ScalableToolbar("Command Manager")
    toolbar.setObjectName("CommandManagerToolbar")
    toolbar.setIconSize(plugin.main_window.toolbar.iconSize() if plugin.main_window else toolbar.iconSize())
    toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
    
    # Reduce vertical margins on toolbar buttons
    toolbar.setStyleSheet("""
        QToolBar {
            spacing: 2px;
            padding: 1px;
        }
        QToolButton {
            padding-top: 2px;
            padding-bottom: 2px;
            margin-top: 1px;
            margin-bottom: 1px;
        }
    """)
    
    try:
        # Action to run commands
        run_action = QAction("Run Commands", plugin.main_window)
        run_action.setToolTip("Run commands on devices")
        run_action.triggered.connect(lambda: on_run_commands(plugin))
        logger.debug(f"Created run_action: {run_action}")
        toolbar.add_toolbar_action(run_action)
        
        # Action to manage command sets
        sets_action = QAction("Command Sets", plugin.main_window)
        sets_action.setToolTip("Manage command sets")
        sets_action.triggered.connect(lambda: on_manage_sets(plugin))
        logger.debug(f"Created sets_action: {sets_action}")
        toolbar.add_toolbar_action(sets_action)
        
        # Action to batch export commands
        batch_export_action = QAction("Export Multiple Devices", plugin.main_window)
        batch_export_action.setToolTip("Export command outputs from multiple devices")
        batch_export_action.triggered.connect(lambda: on_batch_export(plugin))
        if plugin.main_window:
            batch_export_action.setIcon(material_icon("file_upload", plugin.main_window, QStyle.SP_DialogSaveButton))
        logger.debug(f"Created batch_export_action: {batch_export_action}")
        toolbar.add_toolbar_action(batch_export_action)
        
        # Add a separator before the credential management button to make it stand out
        toolbar.add_toolbar_separator()
        
        # Add the standalone credential manager action (this will be in both toolbar and main window toolbar)
        toolbar.add_toolbar_action(plugin.credential_manager_action)
        
        # Add a separator after the credential management button
        toolbar.add_toolbar_separator()
        
        # Action to generate reports
        report_action = QAction("Generate Report", plugin.main_window)
        report_action.setToolTip("Generate command output reports")
        report_action.triggered.connect(lambda: on_generate_report(plugin))
        if plugin.main_window:
            report_action.setIcon(material_icon("description", plugin.main_window, QStyle.SP_FileDialogDetailedView))
        logger.debug(f"Created report_action: {report_action}")
        toolbar.add_toolbar_action(report_action)
        
        # Settings action
        toolbar.add_toolbar_action(plugin.settings_action)
        
    except Exception as e:
        logger.error(f"Error creating toolbar actions: {e}")
        logger.exception("Exception details:")
    
    # Ensure the toolbar has some actions
    if not toolbar.actions():
        logger.warning("Toolbar has no actions - applying fallback action")
        fallback = QAction("Command Manager", plugin.main_window)
        fallback.setToolTip("Command Manager")
        fallback.triggered.connect(lambda: logger.info("Fallback action triggered"))
        if plugin.main_window:
            fallback.setIcon(material_icon("devices", plugin.main_window, QStyle.SP_ComputerIcon))
        toolbar.add_toolbar_action(fallback)
    
    logger.debug(f"Toolbar created with {len(toolbar.actions())} actions")
    return toolbar

def register_context_menu(plugin):
    """Register context menu items for the plugin
    
    Args:
        plugin: The CommandManagerPlugin instance
    """
    logger.debug("Registering context menu actions with device table")
    try:
        # Check if device_table is available
        if hasattr(plugin.main_window, 'device_table'):
            # Register command manager action
            plugin.main_window.device_table.register_context_menu_action(
                "Run Commands",
                plugin._on_device_context_run_commands,
                priority=550
            )
            
            # Register credential manager action
            plugin.main_window.device_table.register_context_menu_action(
                "Manage Credentials",
                plugin._on_device_context_credentials,
                priority=560
            )
            
            logger.debug("Context menu actions registered successfully")
        else:
            logger.warning("device_table not found in main_window")
        
        # Register context menu actions for device groups if available
        if hasattr(plugin.main_window, 'device_group_table'):
            logger.debug("Registering context menu actions with device group table")
            # Register command manager action for groups
            plugin.main_window.device_group_table.register_context_menu_action(
                "Run Commands on Group",
                plugin._on_group_context_run_commands,
                priority=550
            )
            
            # Register credential manager action for groups
            plugin.main_window.device_group_table.register_context_menu_action(
                "Manage Group Credentials",
                plugin._on_group_context_credentials,
                priority=560
            )
            
            logger.debug("Group context menu actions registered successfully")
        
        # Register context menu actions for subnets view if available
        if hasattr(plugin.main_window, 'subnet_table'):
            logger.debug("Registering context menu actions with subnet table")
            # Register command manager action for subnets
            plugin.main_window.subnet_table.register_context_menu_action(
                "Run Commands on Subnet",
                plugin._on_subnet_context_run_commands,
                priority=550
            )
            
            # Register credential manager action for subnets
            plugin.main_window.subnet_table.register_context_menu_action(
                "Manage Subnet Credentials",
                plugin._on_subnet_context_credentials,
                priority=560
            )
            
            logger.debug("Subnet context menu actions registered successfully")
    except Exception as e:
        logger.error(f"Error registering context menu actions: {e}")
        logger.exception("Exception details:")

# Action handlers

def show_command_dialog(plugin):
    """Show the command dialog"""
    if not plugin.command_dialog:
        plugin.command_dialog = CommandDialog(plugin, parent=plugin.main_window)
        
    # Show dialog (non-modal)
    plugin.command_dialog.show()
    plugin.command_dialog.raise_()
    plugin.command_dialog.activateWindow()

def on_context_run_commands(plugin):
    """Handle run commands context menu action"""
    from PySide6.QtWidgets import QMessageBox
    
    # Get selected devices
    devices = plugin.device_manager.get_selected_devices()
    
    if not devices:
        QMessageBox.warning(
            plugin.main_window,
            "No Devices Selected",
            "Please select one or more devices to run commands on."
        )
        return
    
    # Show command dialog with selected devices
    show_command_dialog(plugin)
    plugin.command_dialog.set_selected_devices(devices)

def on_context_manage_credentials(plugin):
    """Handle manage credentials context menu action"""
    from PySide6.QtWidgets import QMessageBox
    from plugins.command_manager.ui.credential_manager import CredentialManager
    
    # Get selected devices
    devices = plugin.device_manager.get_selected_devices()
    
    if not devices:
        QMessageBox.warning(
            plugin.main_window,
            "No Devices Selected",
            "Please select one or more devices to manage credentials for."
        )
        return
    
    # Show credential manager dialog
    cred_manager = CredentialManager(plugin, devices=devices, parent=plugin.main_window)
    cred_manager.exec()

def on_run_commands(plugin):
    """Handle run commands action"""
    from PySide6.QtWidgets import QMessageBox
    from plugins.command_manager.ui.command_dialog import CommandDialog
    
    # Get selected devices
    devices = plugin.device_manager.get_selected_devices()
    if not devices:
        QMessageBox.warning(
            plugin.main_window,
            "No Devices Selected",
            "Please select one or more devices to run commands on."
        )
        return
        
    # Open command dialog
    dialog = CommandDialog(plugin, devices, parent=plugin.main_window)
    dialog.exec()

def on_manage_sets(plugin):
    """Handle manage command sets action"""
    dialog = CommandSetEditor(plugin)
    dialog.exec()

def on_generate_report(plugin):
    """Handle generate report action"""
    from plugins.command_manager.reports.report_generator import ReportGenerator
    
    # Create report generation dialog
    dialog = ReportGenerator(plugin, plugin.main_window)
    dialog.exec()

def on_manage_credentials(plugin):
    """Handle manage credentials action"""
    from PySide6.QtWidgets import QDialog, QMessageBox
    from plugins.command_manager.ui.credential_manager import CredentialManager
    
    logger.info("Opening Credential Manager")
    
    # Create and display the credential manager dialog
    try:
        dialog = CredentialManager(plugin)
        logger.debug("Credential Manager dialog created successfully")
        
        # Set window title to be more descriptive
        dialog.setWindowTitle("Device Credential Manager")
        
        # Make the dialog a bit larger for better usability
        dialog.resize(700, 550)
        
        # Execute the dialog
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            logger.info("Credential changes saved")
        else:
            logger.info("Credential Manager closed without saving")
            
    except Exception as e:
        logger.error(f"Error opening Credential Manager: {e}")
        logger.exception("Exception details:")
        QMessageBox.critical(
            plugin.main_window,
            "Error Opening Credential Manager",
            f"An error occurred while opening the Credential Manager: {str(e)}"
        )

def on_batch_export(plugin):
    """Handle batch export action"""
    logger.info("Opening Command Batch Export")
    
    try:
        # Explicitly import required components to ensure they're available
        from PySide6.QtWidgets import QWidget, QMessageBox
        from plugins.command_manager.reports.command_batch_export import CommandBatchExport
        
        # Create and display the batch export dialog
        dialog = CommandBatchExport(plugin, plugin.main_window)
        
        # Set window title to be more descriptive
        dialog.setWindowTitle("Export Commands from Multiple Devices")
        
        # Execute the dialog
        dialog.exec()
        
    except Exception as e:
        logger.error(f"Error opening Command Batch Export: {e}")
        logger.exception("Exception details:")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            plugin.main_window,
            "Error Opening Command Batch Export",
            f"An error occurred while opening the Command Batch Export: {str(e)}"
        )

def on_open_settings(plugin):
    """Handle open settings action"""
    from plugins.command_manager.ui.settings_dialog import SettingsDialog
    
    try:
        # Create and display the settings dialog
        dialog = SettingsDialog(plugin, plugin.main_window)
        
        # Execute the dialog
        result = dialog.exec()
        
        if result:
            logger.info("Settings updated")
            # Could refresh UI components if needed
    except Exception as e:
        logger.error(f"Error opening settings dialog: {e}")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            plugin.main_window,
            "Error Opening Settings",
            f"An error occurred while opening the Settings dialog: {str(e)}"
        ) 