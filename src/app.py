#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main application class for NetWORKS
"""

import sys
import os
import json
from loguru import logger
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

from .config import Config
from .ui.splash_screen import SplashScreen
from .ui.main_window import MainWindow
from .ui.plugin_ui_theme import plugin_ui_stylesheet
from .ui.theme import apply_theme
from .core.plugin_manager import PluginManager
from .core.device_manager import DeviceManager
from .core import LoggingManager
from .core.crash_reporter import setup_global_exception_handler, show_crash_dialog


class Application(QApplication):
    """Main application class for NetWORKS"""

    def __init__(self, argv):
        """Initialize the application"""
        super().__init__(argv)
        
        # Load manifest
        self.manifest = self._load_manifest()
        
        # Initialize logging manager
        version = self.manifest.get("version", "0.1.0")
        self.logging_manager = LoggingManager(version)
        # Get the configured logger
        self.logger = self.logging_manager.get_logger()
        
        # Set up global exception handler
        setup_global_exception_handler()
        
        # Set application properties
        self.setApplicationName("NetWORKS")
        self.setApplicationVersion(self.manifest.get("version", "0.1.0"))
        self.setOrganizationName("NetWORKS")
        self.setOrganizationDomain("networks.app")
        
        # Use Fusion so custom styles are consistent across platforms
        self.setStyle("Fusion")

        # Initialize configuration and apply theme defaults early
        self.config = Config(self)
        self.config.config_changed.connect(self._on_config_changed)
        self._apply_theme_from_config()
        
        self.logger.info(f"Initializing NetWORKS application v{self.manifest.get('version', '0.1.0')}")
        
        # Log system information 
        self.logger.debug(f"Qt Version: {sys.modules['PySide6'].__version__}")
        
        # Create device manager
        self.device_manager = DeviceManager(self)
        
        # Create plugin manager
        self.plugin_manager = PluginManager(self)
        
        # Initialize splash screen
        self.splash = SplashScreen()
        self.splash.show()
        
        # Use a timer to give the splash screen time to display
        QTimer.singleShot(100, self.init_application)

    def _load_manifest(self):
        """Load the application manifest"""
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "manifest.json"
        )
        
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    data = json.load(f)
                    # Handle both new and old format
                    version = data.get("version_string", data.get("version", "0.1.0"))
                    return {
                        "name": data.get("name", "NetWORKS"),
                        "version": version,
                        "description": data.get("description", "An extensible device management application"),
                        "author": data.get("author", "NetWORKS Team"),
                        "changelog": data.get("version_history", data.get("changelog", []))
                    }
            else:
                self.logger.warning(f"Manifest file not found at {manifest_path}, using default values")
                return {
                    "name": "NetWORKS",
                    "version": "0.1.0",
                    "description": "An extensible device management application",
                    "author": "NetWORKS Team"
                }
        except Exception as e:
            self.logger.error(f"Error loading manifest: {e}")
            return {
                "name": "NetWORKS", 
                "version": "0.1.0"
            }

    def init_application(self):
        """Initialize application components"""
        self.logger.info("Initializing application")
        
        # Use the splash screen created in __init__
        splash = self.splash
        
        # Check environment for data directories
        self._ensure_data_directories()
        
        # Load configuration
        splash.update_progress(20, "Loading configuration...")
        self.config.load()
        self._apply_theme_from_config()
        
        # Initialize device manager
        splash.update_progress(40, "Initializing device manager...")
        self.device_manager = DeviceManager(self)
        
        # Initialize plugin manager
        splash.update_progress(60, "Loading plugins...")
        self.plugin_manager = PluginManager(self)
        
        # Check if we need to restore workspace after restart
        if hasattr(self.plugin_manager, '_check_and_restore_workspace_after_restart'):
            splash.update_progress(65, "Checking for workspace restoration...")
            self.plugin_manager._check_and_restore_workspace_after_restart()
        
        # Initialize issue reporter
        splash.update_progress(80, "Initializing issue reporting system...")
        from .core.issue_reporter import IssueReporter
        self.issue_reporter = IssueReporter(self.config, self)
        
        # Update logging configuration based on settings
        try:
            logging_level = self.config.get("logging.level", "INFO")
            diagnose = self.config.get("logging.diagnose", True)
            backtrace = self.config.get("logging.backtrace", True)
            
            self.logger.info(f"Updating logging configuration: level={logging_level}, diagnose={diagnose}, backtrace={backtrace}")
            if hasattr(self.logging_manager, 'update_configuration'):
                self.logging_manager.update_configuration(logging_level, diagnose, backtrace)
            else:
                self.logger.warning("LoggingManager does not have update_configuration method, skipping configuration update")
        except Exception as e:
            self.logger.warning(f"Failed to update logging configuration: {e}")
        
        # Create main window
        splash.update_progress(90, "Creating main window...")
        self.main_window = MainWindow(self)
        
        # Show workspace selection dialog before displaying the main window
        splash.update_progress(95, "Preparing workspace...")
        self.show_workspace_selection(is_startup=True)
        
        # Complete progress and close splash screen
        splash.update_progress(100, "Startup complete...")
        splash.close()
        
        # Now display the main window
        self.main_window.show()

        # Smoke test mode exits automatically after startup
        if os.environ.get("NETWORKS_SMOKE_TEST") == "1":
            self.logger.info("Smoke test mode active. Exiting after startup.")
            QTimer.singleShot(2000, self.quit)
        
        # Check for first run
        if self.config.is_first_run():
            self.logger.info("First run detected")
            # Mark as having been run to prevent showing on next startup
            self.config.mark_as_run()
            
            # Show first run dialog after a short delay to ensure main window is visible
            QTimer.singleShot(500, self.on_first_run)
            
        # Check for queued issues if we have a token
        if hasattr(self, 'issue_reporter') and self.issue_reporter.github_token:
            QTimer.singleShot(10000, self._check_issue_queue)
            
    def show_workspace_selection(self, is_startup=False):
        """Show workspace selection dialog at startup or from the main menu."""
        from PySide6.QtCore import QUrl, Qt
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel,
            QGroupBox, QLineEdit, QTextEdit, QSplitter, QWidget, QFormLayout, QMessageBox
        )
        
        self.logger.info("Showing workspace selection dialog")
        
        dialog = QDialog(self.main_window if hasattr(self, "main_window") else None)
        dialog.setWindowTitle("Workspace Manager")
        dialog.resize(720, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        header = QLabel("Workspace Manager")
        header.setStyleSheet("font-size: 14pt; font-weight: 600;")
        layout.addWidget(header)
        
        layout.addWidget(QLabel("Select a workspace to open, or create a new one:"))
        
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)
        
        # Workspace list
        list_group = QGroupBox("Workspace List")
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(4)
        workspaces_list = QListWidget()
        list_layout.addWidget(workspaces_list)
        splitter.addWidget(list_group)
        
        # Details panel
        details_group = QGroupBox("Workspace Details")
        details_layout = QVBoxLayout(details_group)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)
        
        details_form = QFormLayout()
        details_form.setHorizontalSpacing(8)
        details_form.setVerticalSpacing(2)
        details_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_name = QLabel("—")
        details_description = QLabel("—")
        details_created = QLabel("—")
        details_last_saved = QLabel("—")
        details_device_count = QLabel("—")
        details_group_count = QLabel("—")
        details_path = QLabel("—")
        
        details_description.setWordWrap(True)
        details_path.setWordWrap(True)
        
        details_form.addRow("Name:", details_name)
        details_form.addRow("Description:", details_description)
        details_form.addRow("Created:", details_created)
        details_form.addRow("Last Saved:", details_last_saved)
        details_form.addRow("Devices:", details_device_count)
        details_form.addRow("Groups:", details_group_count)
        details_form.addRow("Path:", details_path)
        details_layout.addLayout(details_form)
        
        plugins_label = QLabel("Enabled Plugins")
        plugins_label.setStyleSheet("font-weight: 600;")
        details_layout.addWidget(plugins_label)
        details_plugins = QListWidget()
        details_plugins.setMaximumHeight(90)
        details_layout.addWidget(details_plugins)
        
        splitter.addWidget(details_group)
        splitter.setSizes([240, 520])
        
        workspaces = self.device_manager.list_workspaces()
        for workspace in workspaces:
            name = workspace.get("name", "Unknown")
            description = workspace.get("description", "")
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            if description:
                item.setToolTip(description)
            workspaces_list.addItem(item)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        browse_button = QPushButton("Browse Folder")
        create_button = QPushButton("Create Workspace")
        open_button = QPushButton("Open Workspace")
        delete_button = QPushButton("Delete Workspace")
        cancel_button = QPushButton("Cancel" if is_startup else "Close")
        
        button_layout.addWidget(browse_button)
        button_layout.addWidget(create_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch()
        button_layout.addWidget(open_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        def clear_details():
            details_name.setText("—")
            details_description.setText("—")
            details_created.setText("—")
            details_last_saved.setText("—")
            details_device_count.setText("—")
            details_group_count.setText("—")
            details_path.setText("—")
            details_plugins.clear()

        def update_details():
            current_item = workspaces_list.currentItem()
            if not current_item:
                clear_details()
                return
            workspace_name = current_item.data(Qt.UserRole) or current_item.text()
            workspace_data = None
            for ws in workspaces:
                if ws.get("name") == workspace_name:
                    workspace_data = ws
                    break
            if not workspace_data:
                clear_details()
                return
            
            details_name.setText(workspace_data.get("name", "—"))
            details_description.setText(workspace_data.get("description", "—") or "—")
            details_created.setText(workspace_data.get("created", "—"))
            details_last_saved.setText(workspace_data.get("last_saved", "—"))
            details_device_count.setText(str(len(workspace_data.get("devices", []))))
            details_group_count.setText(str(len(workspace_data.get("groups", []))))
            details_path.setText(os.path.join(self.device_manager.workspaces_dir, workspace_name))
            
            details_plugins.clear()
            plugins = workspace_data.get("enabled_plugins", [])
            if plugins:
                for plugin_id in plugins:
                    details_plugins.addItem(plugin_id)
        
        def on_browse():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.device_manager.workspaces_dir))
        
        def on_open():
            current_item = workspaces_list.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "No Selection", "Please select a workspace to open.")
                return
            
            workspace_name = current_item.data(Qt.UserRole) or current_item.text()
            if not is_startup:
                if hasattr(self, "main_window") and hasattr(self.main_window, "_save_workspace_layout"):
                    self.main_window._save_workspace_layout()
                self.device_manager.save_workspace()
            success = self.device_manager.load_workspace(workspace_name)
            if success:
                if hasattr(self, "main_window"):
                    self.main_window.refresh_workspace_ui()
                dialog.accept()
            else:
                QMessageBox.critical(dialog, "Error", f"Failed to load workspace: {workspace_name}")
        
        def on_create():
            create_dialog = QDialog(dialog)
            create_dialog.setWindowTitle("Create Workspace")
            create_dialog.resize(420, 240)
            
            create_layout = QVBoxLayout(create_dialog)
            create_layout.setContentsMargins(8, 8, 8, 8)
            create_layout.setSpacing(6)

            create_header = QLabel("Create Workspace")
            create_header.setStyleSheet("font-size: 12pt; font-weight: 600;")
            create_layout.addWidget(create_header)
            
            form_layout = QFormLayout()
            form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            name_edit = QLineEdit()
            desc_edit = QTextEdit()
            desc_edit.setMaximumHeight(80)
            form_layout.addRow("Name:", name_edit)
            form_layout.addRow("Description:", desc_edit)
            create_layout.addLayout(form_layout)
            
            create_button_inner = QPushButton("Create")
            cancel_button_inner = QPushButton("Cancel")
            inner_buttons = QHBoxLayout()
            inner_buttons.addStretch()
            inner_buttons.addWidget(create_button_inner)
            inner_buttons.addWidget(cancel_button_inner)
            create_layout.addLayout(inner_buttons)
            
            def on_create_confirm():
                name = name_edit.text().strip()
                description = desc_edit.toPlainText().strip()
                
                if not name:
                    QMessageBox.warning(create_dialog, "Missing Name", "Please enter a workspace name.")
                    return
                
                if any(ws.get("name") == name for ws in workspaces):
                    QMessageBox.warning(create_dialog, "Name Exists", f"A workspace named '{name}' already exists.")
                    return
                
                if not self.device_manager.create_workspace(name, description):
                    QMessageBox.critical(create_dialog, "Error", f"Failed to create workspace: {name}")
                    return
                
                workspaces.append({"name": name, "description": description})
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, name)
                if description:
                    item.setToolTip(description)
                workspaces_list.addItem(item)
                workspaces_list.setCurrentRow(workspaces_list.count() - 1)
                update_details()
                create_dialog.accept()
            
            create_button_inner.clicked.connect(on_create_confirm)
            cancel_button_inner.clicked.connect(create_dialog.reject)
            create_dialog.exec()

        def on_delete():
            current_item = workspaces_list.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "No Selection", "Please select a workspace to delete.")
                return
            workspace_name = current_item.data(Qt.UserRole) or current_item.text()
            if workspace_name == "default":
                QMessageBox.warning(dialog, "Delete Workspace", "The default workspace cannot be deleted.")
                return
            if workspace_name == self.device_manager.current_workspace:
                QMessageBox.warning(
                    dialog,
                    "Delete Workspace",
                    "Switch to another workspace before deleting the current one."
                )
                return
            response = QMessageBox.question(
                dialog,
                "Confirm Deletion",
                f"Are you sure you want to delete workspace '{workspace_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if response != QMessageBox.Yes:
                return
            if self.device_manager.delete_workspace(workspace_name):
                workspaces[:] = [ws for ws in workspaces if ws.get("name") != workspace_name]
                workspaces_list.takeItem(workspaces_list.currentRow())
                update_details()
            else:
                QMessageBox.critical(dialog, "Error", f"Failed to delete workspace: {workspace_name}")
        
        def on_cancel():
            if not is_startup:
                dialog.reject()
                return
            self.device_manager.load_workspace("default")
            if hasattr(self, "main_window"):
                self.main_window.refresh_workspace_ui()
            dialog.reject()
        
        browse_button.clicked.connect(on_browse)
        open_button.clicked.connect(on_open)
        cancel_button.clicked.connect(on_cancel)
        create_button.clicked.connect(on_create)
        delete_button.clicked.connect(on_delete)
        workspaces_list.currentItemChanged.connect(lambda _current, _previous: update_details())

        if workspaces_list.count() > 0:
            current_workspace = self.device_manager.current_workspace
            selected = False
            for i in range(workspaces_list.count()):
                item = workspaces_list.item(i)
                if (item.data(Qt.UserRole) or item.text()) == current_workspace:
                    workspaces_list.setCurrentRow(i)
                    selected = True
                    break
            if not selected:
                workspaces_list.setCurrentRow(0)
            update_details()
        else:
            clear_details()
        
        dialog.setModal(True)
        dialog.exec()
        return




    def _apply_theme_from_config(self):
        """Apply theme based on configuration."""
        theme_name = self.config.get("ui.theme", "light") if self.config else "light"
        font_size = self.config.get("ui.font_size", 10) if self.config else 10
        row_height = self.config.get("ui.row_height", 22) if self.config else 22
        accent_color = self.config.get("ui.accent_color", "") if self.config else ""
        tokens = apply_theme(
            self,
            theme_name,
            font_size=font_size,
            row_height=row_height,
            accent_override=accent_color,
        )
        self.setStyleSheet(self.styleSheet() + plugin_ui_stylesheet(tokens))

    def _on_config_changed(self):
        """Handle configuration changes."""
        self._apply_theme_from_config()

    def _ensure_data_directories(self):
        """Ensure data directories exist"""
        data_dirs = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "downloads"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "screenshots"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "issue_queue")
        ]
        
        for directory in data_dirs:
            os.makedirs(directory, exist_ok=True)

    def _check_issue_queue(self):
        """Check for queued issues and try to process them"""
        if hasattr(self, 'issue_reporter'):
            queue_size, is_processing = self.issue_reporter.get_queue_status()
            if queue_size > 0 and not is_processing:
                self.logger.info(f"Found {queue_size} queued issues. Attempting to process...")
                self.issue_reporter.process_queue()

    def run(self):
        """Run the application"""
        try:
            return self.exec()
        except Exception as e:
            self.logger.exception(f"Uncaught exception in main event loop: {e}")
            return 1

    def get_version(self):
        """Get the application version"""
        return self.manifest.get("version", "0.1.0")
        
    def get_changelog(self):
        """Get the application changelog"""
        # First try the new format
        changelog = self.manifest.get("changelog", [])
        if changelog:
            return changelog
        
        # If empty, try the old format (version_history)
        version_history = self.manifest.get("version_history", [])
        return version_history 

    def handle_exception(self, title, e, context=None):
        """
        Handle exceptions in a consistent way
        
        Args:
            title: Title for the error dialog
            e: The exception
            context: Additional context for the crash report
        """
        self.logger.exception(f"{title}: {str(e)}")
        show_crash_dialog(title, e, context)
        
    def on_first_run(self):
        """Handle first run setup and welcome"""
        try:
            self.logger.info("First run detected - performing initial setup")
            
            # Show welcome message
            welcome = QMessageBox()
            welcome.setWindowTitle("Welcome to NetWORKS")
            welcome.setText("Welcome to NetWORKS!")
            welcome.setInformativeText(
                "Thank you for installing NetWORKS. This is your first time running the application. "
                "Would you like to see a quick tour of the features?"
            )
            welcome.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            welcome.setDefaultButton(QMessageBox.Yes)
            
            # Show the dialog
            result = welcome.exec()
            
            # If user wants a tour, show it
            if result == QMessageBox.Yes:
                # TODO: Implement tour - for now just show a simple message
                QMessageBox.information(
                    None, 
                    "Tour", 
                    "The tour feature will be available in a future update. "
                    "For now, please explore the application at your own pace."
                )
            
            # Mark as not first run
            self.config.mark_as_run()
            
        except Exception as e:
            self.logger.error(f"Error during first run setup: {e}")
            # Don't crash if first run setup fails 