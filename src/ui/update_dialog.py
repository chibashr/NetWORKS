#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Update notification dialog for NetWORKS
"""

import os
import sys
import subprocess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QMessageBox, QDialogButtonBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QIcon
from loguru import logger

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
        
        release_notes = QTextEdit()
        release_notes.setReadOnly(True)
        release_notes.setHtml(self.release_notes.replace("\n", "<br>"))
        layout.addWidget(release_notes)
        
        # Buttons
        button_box = QDialogButtonBox()
        
        self.update_button = QPushButton("Update Now")
        self.update_button.setDefault(True)
        self.update_button.clicked.connect(self._on_update)
        
        self.remind_button = QPushButton("Remind Me Later")
        self.remind_button.clicked.connect(self.reject)
        
        self.skip_button = QPushButton("Skip This Version")
        self.skip_button.clicked.connect(self._on_skip)
        
        button_box.addButton(self.update_button, QDialogButtonBox.AcceptRole)
        button_box.addButton(self.remind_button, QDialogButtonBox.RejectRole)
        button_box.addButton(self.skip_button, QDialogButtonBox.RejectRole)
        
        layout.addWidget(button_box)
        
    def _on_update(self):
        """Handle update now button"""
        try:
            # Attempt to perform the update by pulling from git
            if self._update_from_git():
                QMessageBox.information(
                    self,
                    "Update Successful",
                    f"Update to version {self.new_version} successful.\n\n"
                    "Please restart the application to apply the changes."
                )
                self.accept()
            else:
                # _update_from_git() will show appropriate message for non-git installations
                # Only show generic message if git update failed for other reasons
                app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                git_dir = os.path.join(app_dir, ".git")
                if os.path.exists(git_dir):
                    # It's a git repo but update failed
                    QMessageBox.warning(
                        self,
                        "Update Failed",
                        "Failed to update. Please try again later or download the latest version manually."
                    )
        except Exception as e:
            logger.error(f"Error during update: {e}")
            QMessageBox.critical(
                self,
                "Update Error",
                f"An error occurred during the update:\n{str(e)}\n\n"
                "Please update manually by downloading the latest release from GitHub."
            )
            
    def _update_from_git(self):
        """Update the application using git
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the application directory
            app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            logger.info(f"Updating from git in directory: {app_dir}")
            
            # Check if this is a git repository
            git_dir = os.path.join(app_dir, ".git")
            if not os.path.exists(git_dir):
                logger.warning(f"Not a git repository: {app_dir}")
                # This is likely an installed/release version, not a development clone
                # Provide instructions for manual update
                self._show_manual_update_instructions()
                return False
            
            # Determine which branch to pull from
            branch = "stable"  # Default branch
            
            # Get branch from parent window's config if available
            parent = self.parent()
            if parent and hasattr(parent, 'config'):
                branch_map = {
                    "Stable": "stable",
                    "Beta": "beta",
                    "Alpha": "alpha", 
                    "Development": "main"
                }
                update_channel = parent.config.get("general.update_channel", "Stable")
                branch = branch_map.get(update_channel, "stable")
            
            logger.info(f"Pulling from branch: {branch}")
            
            # Run git pull
            result = subprocess.run(
                ["git", "pull", "origin", branch],
                cwd=app_dir,
                capture_output=True,
                text=True,
                check=False  # Don't raise exception on non-zero exit
            )
            
            # Check if successful
            if result.returncode == 0:
                logger.info(f"Git pull successful: {result.stdout}")
                return True
            else:
                logger.error(f"Git pull failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error updating from git: {e}")
            return False
    
    def _show_manual_update_instructions(self):
        """Show instructions for manually updating the application"""
        repo_url = "https://github.com/chibashr/NetWORKS"
        branch = "stable"
        
        # Get branch from parent window's config if available
        parent = self.parent()
        if parent and hasattr(parent, 'config'):
            branch_map = {
                "Stable": "stable",
                "Beta": "beta",
                "Alpha": "alpha",
                "Development": "main"
            }
            update_channel = parent.config.get("general.update_channel", "Stable")
            branch = branch_map.get(update_channel, "stable")
        
        release_url = f"{repo_url}/releases/latest" if branch == "stable" else f"{repo_url}/tree/{branch}"
        
        message = (
            f"This installation is not a git repository.\n\n"
            f"To update to version {self.new_version}:\n\n"
            f"1. Visit the releases page:\n   {release_url}\n\n"
            f"2. Download the latest release zip file\n\n"
            f"3. Extract and replace the application files\n\n"
            f"Alternatively, if you have a git clone, you can update by running:\n"
            f"   git pull origin {branch}"
        )
        
        QMessageBox.information(
            self,
            "Manual Update Required",
            message
        )
            
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
    app = QApplication(sys.argv)
    dialog = UpdateDialog(
        "0.8.44", 
        "0.8.45",
        "Added comprehensive settings dialog with multiple configurable options and implemented "
        "autosave functionality with backup support."
    )
    dialog.exec() 