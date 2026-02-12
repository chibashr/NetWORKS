#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Update notification dialog for NetWORKS.

Supports in-app git-based updates and an interactive "View on GitHub"
button for manual download when needed.
"""

import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QDialogButtonBox, QApplication, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QIcon, QDesktopServices
from loguru import logger
from ..core.update_manager import UpdateManager

class UpdateThread(QThread):
    """Thread for performing update operations"""
    
    progress = Signal(str)
    status = Signal(str)
    error = Signal(str)
    complete = Signal(bool, str)
    
    def __init__(self, update_manager, branch=None):
        super().__init__()
        self.update_manager = update_manager
        self.branch = branch
        
    def run(self):
        """Run the update operation"""
        try:
            # Perform the update
            # Note: UpdateManager signals are connected in main thread before starting this thread
            success, message = self.update_manager.perform_update(self.branch)
            
            # Emit completion signal (UpdateManager should have already emitted its signals)
            # But we ensure completion is always signaled
            if success:
                self.complete.emit(True, message)
            else:
                # If update failed and no error was emitted, emit it now
                if not message.startswith("Update completed"):
                    self.error.emit(message)
                self.complete.emit(False, message)
        except Exception as e:
            error_msg = f"Update thread error: {str(e)}"
            self.error.emit(error_msg)
            self.complete.emit(False, error_msg)


class UpdateDialog(QDialog):
    """Dialog for notifying users about available updates"""
    
    def __init__(self, current_version, new_version, release_notes, parent=None):
        """Initialize the update dialog
        
        Args:
            current_version: Current version string
            new_version: New version string
            release_notes: Release notes for the new version
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_version = current_version
        self.new_version = new_version
        self.release_notes = release_notes
        self.update_manager = None
        self.update_thread = None
        self.is_updating = False
        self._error_dialog_shown = False
        
        # Get config from parent if available
        self.config = None
        if parent and hasattr(parent, 'config'):
            self.config = parent.config
            self.update_manager = UpdateManager(self.config)
        else:
            self.update_manager = UpdateManager()
        
        # Set dialog properties
        self.setWindowTitle("Update Available")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        # Create UI
        self._create_ui()
        
    def _create_ui(self):
        """Create the user interface"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        
        # Icon (using a standard icon if custom icon not available)
        icon_label = QLabel()
        icon = QIcon.fromTheme("system-software-update")
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(48, 48))
        else:
            # Use text as fallback
            icon_label.setText("🔄")
            icon_label.setFont(QFont("Arial", 24))
        header_layout.addWidget(icon_label)
        
        # Header text
        header_text = QLabel(f"<h2>A new version of NetWORKS is available!</h2>")
        header_text.setTextFormat(Qt.RichText)
        header_layout.addWidget(header_text, 1)
        
        layout.addLayout(header_layout)
        
        # Version info
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("<b>Current version:</b>"))
        version_layout.addWidget(QLabel(self.current_version))
        version_layout.addStretch()
        version_layout.addWidget(QLabel("<b>New version:</b>"))
        version_layout.addWidget(QLabel(self.new_version))
        
        layout.addLayout(version_layout)
        
        # Release notes
        layout.addWidget(QLabel("<b>Release Notes:</b>"))
        
        self.release_notes_widget = QTextEdit()
        self.release_notes_widget.setReadOnly(True)
        self.release_notes_widget.setHtml(self.release_notes.replace("\n", "<br>"))
        layout.addWidget(self.release_notes_widget)
        
        # Progress section (initially hidden)
        self.progress_section = QVBoxLayout()
        self.progress_section.setSpacing(5)
        
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.progress_section.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setVisible(False)
        self.progress_section.addWidget(self.progress_bar)
        
        self.progress_text = QLabel("")
        self.progress_text.setWordWrap(True)
        self.progress_text.setVisible(False)
        self.progress_section.addWidget(self.progress_text)
        
        layout.addLayout(self.progress_section)
        
        # Buttons
        button_box = QDialogButtonBox()
        
        self.update_button = QPushButton("Update Now")
        self.update_button.setDefault(True)
        self.update_button.clicked.connect(self._on_update)
        
        self.view_github_button = QPushButton("View on GitHub")
        self.view_github_button.setToolTip("Open the releases page in your browser")
        self.view_github_button.clicked.connect(self._on_view_github)
        
        self.remind_button = QPushButton("Remind Me Later")
        self.remind_button.clicked.connect(self.reject)
        
        self.skip_button = QPushButton("Skip This Version")
        self.skip_button.clicked.connect(self._on_skip)
        
        button_box.addButton(self.update_button, QDialogButtonBox.AcceptRole)
        button_box.addButton(self.view_github_button, QDialogButtonBox.ActionRole)
        button_box.addButton(self.remind_button, QDialogButtonBox.RejectRole)
        button_box.addButton(self.skip_button, QDialogButtonBox.RejectRole)
        
        layout.addWidget(button_box)
        
    def _on_update(self):
        """Handle update now button"""
        if self.is_updating:
            return  # Already updating
        
        # Check if git is installed
        if not self.update_manager.is_git_installed():
            QMessageBox.warning(
                self,
                "Git Not Installed",
                "Git is required for automatic updates.\n\n"
                "Please install Git from https://git-scm.com/downloads\n\n"
                "After installing Git, restart NetWORKS and try updating again."
            )
            return
        
        # Check if repository needs initialization
        if not self.update_manager.is_git_repository():
            reply = QMessageBox.question(
                self,
                "Initialize Repository",
                "This installation is not a git repository.\n\n"
                "Would you like to initialize it for automatic updates?\n\n"
                "This will set up the repository to enable seamless updates in the future.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.No:
                self._show_manual_update_instructions()
                return
        
        # Start update process
        self._start_update()
    
    def _start_update(self):
        """Start the update process in a background thread"""
        self.is_updating = True
        
        # Show progress UI
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_label.setVisible(True)
        self.progress_text.setVisible(True)
        self.status_label.setText("Preparing update...")
        self.progress_text.setText("")
        
        # Disable buttons during update
        self.update_button.setEnabled(False)
        self.view_github_button.setEnabled(False)
        self.remind_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        
        # Get branch
        branch = None
        if self.config:
            branch_map = {
                "Stable": "stable",
                "Beta": "beta",
                "Alpha": "alpha",
                "Development": "main"
            }
            update_channel = self.config.get("general.update_channel", "Stable")
            branch = branch_map.get(update_channel, "stable")
        
        # Connect UpdateManager for progress/status/error only; completion from thread only to avoid double dialogs
        self.update_manager.progress.connect(self._on_progress, Qt.QueuedConnection)
        self.update_manager.status_changed.connect(self._on_status, Qt.QueuedConnection)
        self.update_manager.error_occurred.connect(self._on_error, Qt.QueuedConnection)
        
        self.update_thread = UpdateThread(self.update_manager, branch)
        self.update_thread.progress.connect(self._on_progress, Qt.QueuedConnection)
        self.update_thread.status.connect(self._on_status, Qt.QueuedConnection)
        self.update_thread.error.connect(self._on_error, Qt.QueuedConnection)
        self.update_thread.complete.connect(self._on_update_complete, Qt.QueuedConnection)
        self.update_thread.start()
    
    def _on_progress(self, message):
        """Handle progress updates"""
        self.progress_text.setText(message)
        logger.debug(f"Update progress: {message}")
    
    def _on_status(self, message):
        """Handle status updates"""
        self.status_label.setText(message)
        logger.info(f"Update status: {message}")
    
    def _on_error(self, message):
        """Handle errors during update."""
        logger.error(f"Update error: {message}")
        self._error_dialog_shown = True
        self._reset_ui()
        
        box = QMessageBox(self)
        box.setWindowTitle("Update Error")
        box.setText(f"An error occurred during the update:\n\n{message}\n\n"
                    "You can try again or update manually by downloading the latest release from GitHub.")
        box.setIcon(QMessageBox.Critical)
        open_btn = box.addButton("Open in Browser", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl(self._get_release_url()))
    
    def _on_update_complete(self, success, message):
        """Handle update completion (only thread.complete is connected to avoid double dialogs)."""
        self._reset_ui()
        
        if success:
            QMessageBox.information(
                self,
                "Update Successful",
                f"Update to version {self.new_version} successful.\n\n"
                "Please restart the application to apply the changes."
            )
            self.accept()
        else:
            # Error dialog is already shown by _on_error when manager emits error_occurred.
            # Only show a dialog if this failure wasn't reported via error_occurred (e.g. thread crash).
            if not getattr(self, "_error_dialog_shown", False):
                box = QMessageBox(self)
                box.setWindowTitle("Update Failed")
                box.setText(f"Update failed: {message}\n\n"
                            "You can try again or update manually by downloading the latest release from GitHub.")
                box.setIcon(QMessageBox.Warning)
                open_btn = box.addButton("Open in Browser", QMessageBox.ActionRole)
                box.addButton(QMessageBox.Ok)
                box.exec()
                if box.clickedButton() == open_btn:
                    QDesktopServices.openUrl(QUrl(self._get_release_url()))
            self._error_dialog_shown = False
    
    def _reset_ui(self):
        """Reset UI after update completes."""
        self.is_updating = False
        self.progress_bar.setVisible(False)
        self.progress_text.setVisible(False)
        self.status_label.setText("")
        self.update_button.setEnabled(True)
        self.view_github_button.setEnabled(True)
        self.remind_button.setEnabled(True)
        self.skip_button.setEnabled(True)
            
    
    def _show_manual_update_instructions(self):
        """Show instructions for manually updating the application."""
        release_url = self._get_release_url()
        message = (
            f"To update to version {self.new_version}:\n\n"
            f"1. Visit the releases page:\n   {release_url}\n\n"
            f"2. Download the latest release zip file\n\n"
            f"3. Extract and replace the application files\n\n"
            f"Alternatively, install Git to enable automatic updates:\n"
            f"   https://git-scm.com/downloads"
        )
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Manual Update Required")
        msg.setText(message)
        msg.setIcon(QMessageBox.Information)
        open_btn = msg.addButton("Open in Browser", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)
        msg.exec()
        if msg.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl(release_url))
    
    def _get_release_url(self):
        """Return the GitHub URL for the current channel (releases or tree/branch)."""
        repo_url = (self.update_manager.repository_url or "").rstrip("/")
        if not repo_url or "github.com" not in repo_url:
            return "https://github.com/chibashr/netWORKS/releases/latest"
        branch = "stable"
        if self.config:
            ch = self.config.get("general.update_channel", "Stable")
            branch = {"Stable": "stable", "Beta": "beta", "Alpha": "alpha", "Development": "main"}.get(ch, "stable")
        return f"{repo_url}/releases/latest" if branch == "stable" else f"{repo_url}/tree/{branch}"
    
    def _on_view_github(self):
        """Open the releases or branch page in the default browser."""
        url = self._get_release_url()
        QDesktopServices.openUrl(QUrl(url))
    
    def _on_skip(self):
        """Handle skip this version button"""
        # Store the skipped version in the config if available
        try:
            parent = self.parent()
            if parent and hasattr(parent, 'config'):
                parent.config.set("general.skipped_version", self.new_version)
                parent.config.save()
        except Exception as e:
            logger.error(f"Error saving skipped version: {e}")
            
        self.reject()


# For testing
if __name__ == "__main__":
    import json
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "manifest.json"
    )
    current_version = "0.0.0"
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            current_version = data.get("version_string", data.get("version", "0.0.0"))
    app = QApplication(sys.argv)
    dialog = UpdateDialog(
        current_version,
        "X.Y.Z",  # Simulated new version for testing
        "Sample release notes for testing the update dialog."
    )
    dialog.exec() 