#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Report issue dialog for NetWORKS
"""

import os
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from loguru import logger
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QPixmap, QScreen, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, 
    QComboBox, QPushButton, QTabWidget, QWidget, QCheckBox, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QDialogButtonBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QStatusBar
)


class ReportIssueDialog(QDialog):
    """Dialog for reporting issues to GitHub with offline support"""
    
    def __init__(self, app, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        
        # Store application reference
        self.app = app
        
        # Get issue reporter instance
        if hasattr(self.app, 'issue_reporter'):
            self.issue_reporter = self.app.issue_reporter
        else:
            # Create issue reporter if it doesn't exist
            from src.core.issue_reporter import IssueReporter
            self.issue_reporter = IssueReporter(app.config, app)
            self.app.issue_reporter = self.issue_reporter
            
        # Connect signals
        self.issue_reporter.issue_submitted.connect(self._on_issue_submitted)
        self.issue_reporter.queue_processed.connect(self._on_queue_processed)
        
        # Check if GitHub token is set
        self.has_token = bool(self.issue_reporter.github_token)
        
        # Set dialog properties
        self.setWindowTitle("Report Issue")
        self.resize(800, 600)
        
        # Create UI
        self._create_ui()
        
        # Initialize online status check
        self._check_online_status()
        
        # Start automatic online status check timer
        self.status_check_timer = QTimer(self)
        self.status_check_timer.timeout.connect(self._check_online_status)
        self.status_check_timer.start(30000)  # Check every 30 seconds
    
    def _create_ui(self):
        """Create the dialog UI"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Report tab
        self.report_tab = QWidget()
        self.report_layout = QVBoxLayout(self.report_tab)
        
        # Create form for issue details
        form_layout = QFormLayout()
        
        # Issue title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter a descriptive title for the issue")
        form_layout.addRow("Title:", self.title_edit)
        
        # Category dropdown
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Bug", "Feature Request", "Question"])
        form_layout.addRow("Category:", self.category_combo)
        
        # Severity dropdown
        self.severity_combo = QComboBox()
        self.severity_combo.addItems(["Critical", "High", "Medium", "Low"])
        form_layout.addRow("Severity:", self.severity_combo)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Describe the issue in detail")
        self.description_edit.setMinimumHeight(80)
        form_layout.addRow("Description:", self.description_edit)
        
        # Steps to reproduce
        self.steps_edit = QTextEdit()
        self.steps_edit.setPlaceholderText("List the steps to reproduce the issue")
        self.steps_edit.setMinimumHeight(80)
        form_layout.addRow("Steps to Reproduce:", self.steps_edit)
        
        # Expected result
        self.expected_edit = QTextEdit()
        self.expected_edit.setPlaceholderText("What did you expect to happen?")
        self.expected_edit.setMinimumHeight(60)
        form_layout.addRow("Expected Result:", self.expected_edit)
        
        # Actual result
        self.actual_edit = QTextEdit()
        self.actual_edit.setPlaceholderText("What actually happened?")
        self.actual_edit.setMinimumHeight(60)
        form_layout.addRow("Actual Result:", self.actual_edit)
        
        # Additional options
        options_group = QGroupBox("Additional Information")
        options_layout = QVBoxLayout(options_group)
        
        self.include_system_info = QCheckBox("Include system information")
        self.include_system_info.setChecked(True)
        self.include_system_info.setToolTip("Include OS, Python, and Qt version information")
        
        self.include_logs = QCheckBox("Include recent application logs")
        self.include_logs.setChecked(True)
        self.include_logs.setToolTip("Include the most recent application log entries")
        
        self.screenshot_path = None
        self.take_screenshot_btn = QPushButton("Take Screenshot")
        self.take_screenshot_btn.setToolTip("Take a screenshot to include with the issue report")
        self.take_screenshot_btn.clicked.connect(self._on_take_screenshot)
        self.screenshot_label = QLabel("No screenshot attached")
        
        screenshot_layout = QHBoxLayout()
        screenshot_layout.addWidget(self.take_screenshot_btn)
        screenshot_layout.addWidget(self.screenshot_label)
        screenshot_layout.addStretch()
        
        options_layout.addWidget(self.include_system_info)
        options_layout.addWidget(self.include_logs)
        options_layout.addLayout(screenshot_layout)
        
        # Add form and options to report layout
        self.report_layout.addLayout(form_layout)
        self.report_layout.addWidget(options_group)
        
        # Status bar for report tab
        self.report_status = QStatusBar()
        self.report_status.setSizeGripEnabled(False)
        self.report_layout.addWidget(self.report_status)
        
        # Queue tab
        self.queue_tab = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_tab)
        
        # Create table for queued issues
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(4)
        self.queue_table.setHorizontalHeaderLabels(["Title", "Date", "Attempts", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setAlternatingRowColors(True)
        
        # Queue controls
        queue_controls = QHBoxLayout()
        self.refresh_queue_btn = QPushButton("Refresh")
        self.refresh_queue_btn.clicked.connect(self._refresh_queue)
        
        self.process_queue_btn = QPushButton("Process Queue")
        self.process_queue_btn.clicked.connect(self._process_queue)
        
        self.process_status = QLabel("Queue status: not processing")
        queue_controls.addWidget(self.refresh_queue_btn)
        queue_controls.addWidget(self.process_queue_btn)
        queue_controls.addStretch()
        queue_controls.addWidget(self.process_status)
        
        # Progress bar for queue processing
        self.queue_progress = QProgressBar()
        self.queue_progress.setVisible(False)
        
        # Add queue components to layout
        self.queue_layout.addWidget(self.queue_table)
        self.queue_layout.addLayout(queue_controls)
        self.queue_layout.addWidget(self.queue_progress)
        
        # History tab
        self.history_tab = QWidget()
        self.history_layout = QVBoxLayout(self.history_tab)
        
        # Create table for issue history
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["Title", "Date", "Status"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        
        # History controls
        history_controls = QHBoxLayout()
        self.refresh_history_btn = QPushButton("Refresh")
        self.refresh_history_btn.clicked.connect(self._refresh_history)
        
        self.open_issue_btn = QPushButton("Open Selected Issue")
        self.open_issue_btn.clicked.connect(self._open_selected_issue)
        self.open_issue_btn.setEnabled(False)
        
        history_controls.addWidget(self.refresh_history_btn)
        history_controls.addWidget(self.open_issue_btn)
        history_controls.addStretch()
        
        # Add history components to layout
        self.history_layout.addWidget(self.history_table)
        self.history_layout.addLayout(history_controls)
        
        # Settings tab
        self.settings_tab = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_tab)
        
        # GitHub token setting
        token_group = QGroupBox("GitHub Authentication")
        token_layout = QVBoxLayout(token_group)
        
        token_description = QLabel(
            "To submit issues directly to GitHub and enable offline submission, "
            "you need to set up a personal access token with appropriate permissions."
        )
        token_description.setWordWrap(True)
        
        token_instruction = QLabel(
            "<a href=\"https://github.com/settings/tokens\">Create a token</a> "
            "with the 'public_repo' scope to submit issues."
        )
        token_instruction.setOpenExternalLinks(True)
        token_instruction.setWordWrap(True)
        
        token_form = QFormLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Enter your GitHub personal access token")
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setText(self.issue_reporter.github_token or "")
        
        token_form.addRow("Token:", self.token_edit)
        
        self.save_token_btn = QPushButton("Save Token")
        self.save_token_btn.clicked.connect(self._save_token)
        
        token_layout.addWidget(token_description)
        token_layout.addWidget(token_instruction)
        token_layout.addLayout(token_form)
        token_layout.addWidget(self.save_token_btn)
        
        # Add settings components to layout
        self.settings_layout.addWidget(token_group)
        self.settings_layout.addStretch()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.report_tab, "Report Issue")
        self.tab_widget.addTab(self.queue_tab, "Offline Queue")
        self.tab_widget.addTab(self.history_tab, "Issue History")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Add tab widget to main layout
        layout.addWidget(self.tab_widget)
        
        # Add buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.submit_btn = buttons.button(QDialogButtonBox.Ok)
        self.submit_btn.setText("Submit Issue")
        self.submit_btn.clicked.connect(self._on_submit)
        
        buttons.button(QDialogButtonBox.Cancel).clicked.connect(self.reject)
        layout.addWidget(buttons)
        
        # Load data
        self._refresh_queue()
        self._refresh_history()
    
    def _on_submit(self):
        """Handle issue submission"""
        # Validate fields
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation Error", "Please enter an issue title.")
            return
            
        description = self.description_edit.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "Validation Error", "Please enter a description.")
            return
            
        # Get values from UI
        category = self.category_combo.currentText()
        severity = self.severity_combo.currentText()
        steps = self.steps_edit.toPlainText().strip()
        expected = self.expected_edit.toPlainText().strip()
        actual = self.actual_edit.toPlainText().strip()
        system_info = self.include_system_info.isChecked()
        app_logs = self.include_logs.isChecked()
        
        # Disable submit button while submitting
        self.submit_btn.setEnabled(False)
        self.report_status.showMessage("Submitting issue...")
        
        # Submit in a thread to avoid freezing UI
        def submit_thread():
            success, message = self.issue_reporter.submit_issue(
                title=title,
                description=description,
                category=category,
                severity=severity,
                steps_to_reproduce=steps,
                expected_result=expected,
                actual_result=actual,
                screenshot_path=self.screenshot_path,
                system_info=system_info,
                app_logs=app_logs
            )
            
            # Update UI in the main thread
            QTimer.singleShot(0, lambda: self._handle_submission_result(success, message))
        
        thread = threading.Thread(target=submit_thread)
        thread.daemon = True
        thread.start()
    
    def _handle_submission_result(self, success, message):
        """Handle submission result in UI thread"""
        self.submit_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Issue Submitted", f"Issue submitted successfully. You can view it at:\n{message}")
            self.accept()
        else:
            self.report_status.showMessage(message)
            
            # If the message indicates the issue is queued, show success dialog
            if "queued" in message.lower():
                QMessageBox.information(self, "Issue Queued", message)
                self.tab_widget.setCurrentIndex(1)  # Switch to queue tab
                self._refresh_queue()
            # If the message is about submitting directly to GitHub, ask if they want to open the page
            elif "submit your issue directly" in message.lower():
                url = message.split(":")[-1].strip()
                response = QMessageBox.question(
                    self,
                    "Submit Issue Manually",
                    f"Do you want to open the GitHub issue page in your browser?\n\nYou will need to copy and paste your issue details manually.",
                    QMessageBox.Yes | QMessageBox.No
                )
                if response == QMessageBox.Yes:
                    webbrowser.open(url)
    
    def _on_take_screenshot(self):
        """Handle screenshot button click"""
        self.hide()  # Hide dialog so it's not in the screenshot
        
        # Wait a bit for the window to hide
        QTimer.singleShot(500, self._take_screenshot)
    
    def _take_screenshot(self):
        """Take a screenshot and show preview"""
        try:
            # Take screenshot of primary screen
            screen = QGuiApplication.primaryScreen()
            pixmap = screen.grabWindow(0)
            
            # Save screenshot to temporary file
            screenshots_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "screenshots"
            )
            os.makedirs(screenshots_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.screenshot_path = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")
            pixmap.save(self.screenshot_path, "PNG")
            
            # Update UI
            self.screenshot_label.setText(f"Screenshot saved: {os.path.basename(self.screenshot_path)}")
            
            # Show the dialog again
            self.show()
            
            # Ask if user wants to edit/view the screenshot
            response = QMessageBox.question(
                self,
                "Screenshot Taken",
                "Screenshot saved. Do you want to view it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if response == QMessageBox.Yes:
                # Open with default image viewer
                import subprocess
                import sys
                if sys.platform == 'win32':
                    os.startfile(self.screenshot_path)
                elif sys.platform == 'darwin':
                    subprocess.call(['open', self.screenshot_path])
                else:
                    subprocess.call(['xdg-open', self.screenshot_path])
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            QMessageBox.warning(self, "Screenshot Error", f"Failed to take screenshot: {str(e)}")
            self.show()
    
    def _refresh_queue(self):
        """Refresh offline queue list"""
        # Get queue files
        queue_files = self.issue_reporter._get_queue_files()
        self.queue_table.setRowCount(0)
        
        if not queue_files:
            self.process_queue_btn.setEnabled(False)
            self.process_status.setText("Queue status: empty")
            return
        
        # Fill table
        self.queue_table.setRowCount(len(queue_files))
        for i, queue_file in enumerate(queue_files):
            try:
                with open(queue_file, 'r') as f:
                    queue_entry = json.load(f)
                    
                # Title column
                title_item = QTableWidgetItem(queue_entry["issue_data"]["title"])
                self.queue_table.setItem(i, 0, title_item)
                
                # Date column
                timestamp = queue_entry["timestamp"]
                date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
                self.queue_table.setItem(i, 1, QTableWidgetItem(date_str))
                
                # Attempts column
                attempts = queue_entry.get("attempts", 0)
                self.queue_table.setItem(i, 2, QTableWidgetItem(str(attempts)))
                
                # Status column
                last_attempt = queue_entry.get("last_attempt")
                if last_attempt:
                    last_attempt_str = datetime.fromtimestamp(last_attempt).strftime("%Y-%m-%d %H:%M")
                    status = f"Last attempt: {last_attempt_str}"
                else:
                    status = "Pending"
                self.queue_table.setItem(i, 3, QTableWidgetItem(status))
            except Exception as e:
                logger.error(f"Error loading queue entry: {e}")
                
                # Show error in table
                self.queue_table.setItem(i, 0, QTableWidgetItem("Error"))
                self.queue_table.setItem(i, 1, QTableWidgetItem("--"))
                self.queue_table.setItem(i, 2, QTableWidgetItem("--"))
                self.queue_table.setItem(i, 3, QTableWidgetItem(f"Error: {str(e)}"))
        
        # Update process button state
        self.process_queue_btn.setEnabled(True)
        self.process_status.setText(f"Queue status: {len(queue_files)} issue(s) pending")
    
    def _refresh_history(self):
        """Refresh issue history"""
        if not self.app.config:
            return
            
        recent_issues = self.app.config.get("issue_reporter.recent_issues", [])
        self.history_table.setRowCount(0)
        
        if not recent_issues:
            self.open_issue_btn.setEnabled(False)
            return
            
        # Fill table
        self.history_table.setRowCount(len(recent_issues))
        for i, issue in enumerate(recent_issues):
            # Title column
            title_item = QTableWidgetItem(issue["title"])
            title_item.setData(Qt.UserRole, issue["url"])
            self.history_table.setItem(i, 0, title_item)
            
            # Date column
            self.history_table.setItem(i, 1, QTableWidgetItem(issue.get("date", "--")))
            
            # Status column
            self.history_table.setItem(i, 2, QTableWidgetItem(issue.get("status", "open")))
        
        # Connect selection changed signal
        self.history_table.itemSelectionChanged.connect(self._update_history_buttons)
    
    def _update_history_buttons(self):
        """Update history tab buttons based on selection"""
        selected_rows = self.history_table.selectedItems()
        self.open_issue_btn.setEnabled(len(selected_rows) > 0)
    
    def _open_selected_issue(self):
        """Open selected issue in browser"""
        selected_rows = self.history_table.selectedIndexes()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        title_item = self.history_table.item(row, 0)
        url = title_item.data(Qt.UserRole)
        
        if url:
            webbrowser.open(url)
    
    def _process_queue(self):
        """Process the offline queue"""
        self.process_queue_btn.setEnabled(False)
        self.process_status.setText("Queue status: processing...")
        self.queue_progress.setVisible(True)
        self.queue_progress.setRange(0, 0)  # Indeterminate progress
        
        # Start processing in a background thread
        self.issue_reporter.process_queue()
    
    def _on_queue_processed(self, successful, failed):
        """Handle queue processed signal"""
        self.process_queue_btn.setEnabled(True)
        self.queue_progress.setVisible(False)
        
        if successful == 0 and failed == 0:
            self.process_status.setText("Queue status: empty")
        else:
            self.process_status.setText(f"Queue processed: {successful} successful, {failed} failed")
            
        # Refresh queue
        self._refresh_queue()
        
        # Also refresh history if any successful submissions
        if successful > 0:
            self._refresh_history()
    
    def _on_issue_submitted(self, success, message):
        """Handle issue submitted signal"""
        # This is handled by _handle_submission_result
        pass
    
    def _save_token(self):
        """Save GitHub token"""
        token = self.token_edit.text().strip()
        
        # Confirm if clearing token
        if self.issue_reporter.github_token and not token:
            response = QMessageBox.question(
                self,
                "Clear Token",
                "Are you sure you want to clear your GitHub token? This will disable direct issue submission.",
                QMessageBox.Yes | QMessageBox.No
            )
            if response != QMessageBox.Yes:
                return
        
        # Save token
        self.issue_reporter.set_github_token(token)
        self.has_token = bool(token)
        
        QMessageBox.information(
            self,
            "Token Saved",
            "GitHub token has been saved." if token else "GitHub token has been cleared."
        )
    
    def _check_online_status(self):
        """Check if we're online and update UI"""
        is_online = self.issue_reporter._is_online()
        queue_files = self.issue_reporter._get_queue_files()
        
        # Update report status
        online_status = "Online" if is_online else "Offline"
        token_status = "Authenticated" if self.has_token else "Anonymous"
        self.report_status.showMessage(f"Status: {online_status} | {token_status}")
        
        # Update process button state based on connectivity and queue contents
        if not is_online:
            if self.process_queue_btn.isEnabled():
                self.process_queue_btn.setEnabled(False)
            self.process_status.setText("Queue status: offline")
        else:
            if queue_files:
                self.process_queue_btn.setEnabled(True)
                self.process_status.setText(f"Queue status: {len(queue_files)} issue(s) pending")
            else:
                self.process_queue_btn.setEnabled(False)
                self.process_status.setText("Queue status: empty")

import json 