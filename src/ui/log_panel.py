#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Log panel for NetWORKS
"""

import os
import re
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLabel, QComboBox, QPushButton, QSplitter,
    QCheckBox, QGroupBox, QTabWidget, QLineEdit,
    QToolButton, QFileDialog, QMenu, QScrollBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont
from .responsive_toolbar import ResponsiveToolbar

class LogPanel(QWidget):
    """Panel for viewing application logs"""
    
    def __init__(self, parent=None):
        """Initialize the log panel"""
        super().__init__(parent)
        
        # Initialize UI
        self._setup_ui()
        
        # Initialize log polling
        self._setup_log_polling()
        
        # Store log filters and settings
        self._log_filters = {
            "levels": {
                "TRACE": False,
                "DEBUG": True,
                "INFO": True,
                "SUCCESS": True,
                "WARNING": True,
                "ERROR": True,
                "CRITICAL": True
            },
            "text": "",
            "auto_scroll": True,
            "wrap_text": True,
            "current_file": "recent_logs.log"
        }
        
        # Level colors
        self._level_colors = {
            "TRACE": QColor(150, 150, 150),  # Gray
            "DEBUG": QColor(100, 100, 255),  # Blue
            "INFO": QColor(0, 0, 0),         # Black
            "SUCCESS": QColor(0, 128, 0),    # Green
            "WARNING": QColor(255, 165, 0),  # Orange
            "ERROR": QColor(255, 0, 0),      # Red
            "CRITICAL": QColor(128, 0, 128)  # Purple
        }
        
        # Initial log load
        self._load_log_file()
    
    def _setup_ui(self):
        """Set up the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Control panel
        control_panel = ResponsiveToolbar(breakpoint=900)
        control_panel.setContentsMargins(5, 5, 5, 5)
        control_panel.setSpacing(6)
        
        # File selector
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(200)
        self.file_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        control_panel.addWidget(QLabel("Log File:"))
        control_panel.addWidget(self.file_combo)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_logs)
        control_panel.addWidget(self.refresh_button)
        
        # Save button
        self.save_button = QPushButton("Save As...")
        self.save_button.clicked.connect(self._save_logs)
        control_panel.addWidget(self.save_button)
        
        # Level filters
        level_group = QGroupBox("Log Levels")
        level_layout = QHBoxLayout(level_group)
        
        self.level_checkboxes = {}
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            cb = QCheckBox(level)
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_filters)
            self.level_checkboxes[level] = cb
            level_layout.addWidget(cb)
        
        control_panel.addWidget(level_group)
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search logs...")
        self.search_box.textChanged.connect(self._update_filters)
        self.search_button = QToolButton()
        self.search_button.setText("X")
        self.search_button.clicked.connect(lambda: self.search_box.setText(""))
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.search_button)
        search_container = QWidget()
        search_container.setLayout(search_layout)
        search_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        control_panel.addWidget(search_container)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QHBoxLayout(options_group)
        
        self.auto_scroll_check = QCheckBox("Auto Scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self._on_auto_scroll_changed)
        options_layout.addWidget(self.auto_scroll_check)
        
        self.wrap_text_check = QCheckBox("Wrap Text")
        self.wrap_text_check.setChecked(True)
        self.wrap_text_check.stateChanged.connect(self._on_wrap_text_changed)
        options_layout.addWidget(self.wrap_text_check)
        
        control_panel.addWidget(options_group)
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_log_view)
        control_panel.addWidget(self.clear_button)
        
        # Add control panel to main layout
        main_layout.addWidget(control_panel)
        
        # Log content view
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.WidgetWidth)
        self.log_view.setFont(QFont("Courier New", 9))
        
        # Add log view to main layout
        main_layout.addWidget(self.log_view)
    
    def _setup_log_polling(self):
        """Set up polling for log file changes"""
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(1000)  # Poll every second
        self.log_timer.timeout.connect(self._poll_log_file)
        self.log_timer.start()
        
        # File positions
        self.log_file_positions = {}
        
        # Discover logs
        self._discover_logs()
    
    def _discover_logs(self):
        """Discover available log files"""
        log_dir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(log_dir):
            return
        
        # Clear current items
        self.file_combo.clear()
        
        # Add recent logs first
        recent_log_path = os.path.join(log_dir, "recent_logs.log")
        if os.path.exists(recent_log_path):
            self.file_combo.addItem("Recent Logs", "recent_logs.log")
        
        # Add session logs
        for filename in sorted(os.listdir(log_dir), reverse=True):
            if filename.startswith("networks_") and filename.endswith(".log"):
                # Parse date from filename
                try:
                    date_str = filename.split("_")[1]
                    date = datetime.strptime(date_str, "%Y%m%d")
                    display_name = f"Session {date.strftime('%Y-%m-%d')}"
                    self.file_combo.addItem(display_name, filename)
                except (ValueError, IndexError):
                    self.file_combo.addItem(filename, filename)
    
    def _load_log_file(self):
        """Load the currently selected log file"""
        log_file = self._log_filters["current_file"]
        log_path = os.path.join(os.getcwd(), "logs", log_file)
        
        if not os.path.exists(log_path):
            self.log_view.setPlainText(f"Log file not found: {log_path}")
            return
        
        # Clear current content
        self.log_view.clear()
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Store file position for polling
                self.log_file_positions[log_file] = len(content)
                
                # Process and display logs with filtering
                self._process_and_display_logs(content)
                
                # Scroll to end if auto-scroll is enabled
                if self._log_filters["auto_scroll"]:
                    self.log_view.moveCursor(QTextCursor.End)
        except Exception as e:
            self.log_view.setPlainText(f"Error loading log file: {str(e)}")
    
    def _poll_log_file(self):
        """Check for changes in the log file and update if needed"""
        log_file = self._log_filters["current_file"]
        log_path = os.path.join(os.getcwd(), "logs", log_file)
        
        if not os.path.exists(log_path):
            return
        
        # Get current file size
        file_size = os.path.getsize(log_path)
        last_position = self.log_file_positions.get(log_file, 0)
        
        # If file has grown, read new content
        if file_size > last_position:
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    
                    # Update file position
                    self.log_file_positions[log_file] = file_size
                    
                    # Process and append new content
                    if new_content:
                        self._process_and_display_logs(new_content, append=True)
                        
                        # Scroll to end if auto-scroll is enabled
                        if self._log_filters["auto_scroll"]:
                            self.log_view.moveCursor(QTextCursor.End)
            except Exception as e:
                print(f"Error polling log file: {str(e)}")
    
    def _process_and_display_logs(self, content, append=False):
        """Process log content with filters and display in the view"""
        # If no filters are active and we're displaying the whole file,
        # we can just set the text directly for better performance
        if not self._log_filters["text"] and all(self._log_filters["levels"].values()) and not append:
            self.log_view.setPlainText(content)
            return
        
        # Split into lines for filtering
        lines = content.splitlines()
        
        # Apply filters
        filtered_lines = []
        for line in lines:
            # Check log level filter
            level_match = re.search(r'\|\s*(\w+)\s*\|', line)
            if level_match:
                level = level_match.group(1).strip().upper()
                if level in self._log_filters["levels"] and not self._log_filters["levels"][level]:
                    continue
            
            # Check text filter
            if self._log_filters["text"] and self._log_filters["text"].lower() not in line.lower():
                continue
            
            filtered_lines.append(line)
        
        # Join filtered lines
        filtered_content = "\n".join(filtered_lines)
        
        # Set or append text
        if append:
            cursor = self.log_view.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(filtered_content + "\n")
        else:
            self.log_view.setPlainText(filtered_content)
        
        # Apply syntax highlighting
        self._apply_syntax_highlighting()
    
    def _apply_syntax_highlighting(self):
        """Apply syntax highlighting to log text"""
        pass  # We'll implement basic coloring in a future version
    
    def _update_filters(self):
        """Update filters based on UI state"""
        # Update level filters
        for level, checkbox in self.level_checkboxes.items():
            self._log_filters["levels"][level] = checkbox.isChecked()
        
        # Update text filter
        self._log_filters["text"] = self.search_box.text()
        
        # Reload logs with new filters
        self._load_log_file()
    
    def _on_file_changed(self, index):
        """Handle log file change"""
        if index >= 0 and hasattr(self, "_log_filters"):
            file_data = self.file_combo.itemData(index)
            if file_data:
                self._log_filters["current_file"] = file_data
                self._load_log_file()
    
    def _on_auto_scroll_changed(self, state):
        """Handle auto-scroll setting change"""
        self._log_filters["auto_scroll"] = (state == Qt.Checked)
        
        # If enabled, immediately scroll to the bottom
        if self._log_filters["auto_scroll"]:
            self.log_view.moveCursor(QTextCursor.End)
    
    def _on_wrap_text_changed(self, state):
        """Handle word wrap setting change"""
        self._log_filters["wrap_text"] = (state == Qt.Checked)
        self.log_view.setLineWrapMode(
            QTextEdit.WidgetWidth if self._log_filters["wrap_text"] else QTextEdit.NoWrap
        )
    
    def _refresh_logs(self):
        """Manually refresh logs"""
        self._discover_logs()
        self._load_log_file()
    
    def _clear_log_view(self):
        """Clear the log view (doesn't affect the actual log file)"""
        self.log_view.clear()
    
    def _save_logs(self):
        """Save the current log content to a file"""
        # Get the current log file name for default save name
        current_file = self._log_filters["current_file"]
        default_name = os.path.splitext(current_file)[0]
        
        # Create file dialog
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Log File",
            f"{default_name}_export",
            "Text Files (*.txt);;JSON Files (*.json)"
        )
        
        if not file_path:
            return
            
        try:
            # Determine file format based on selected filter or extension
            is_json = selected_filter == "JSON Files (*.json)" or file_path.lower().endswith('.json')
            
            if is_json:
                self._save_as_json(file_path)
            else:
                self._save_as_text(file_path)
                
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, 
                "Save Error", 
                f"Error saving log file: {str(e)}"
            )
            
    def _save_as_text(self, file_path):
        """Save logs as plain text file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.log_view.toPlainText())
            
    def _save_as_json(self, file_path):
        """Save logs as JSON file with structured data"""
        import json
        import re
        import datetime
        
        # Parse log entries
        log_entries = []
        for line in self.log_view.toPlainText().splitlines():
            if not line.strip():
                continue
                
            # Try to parse log format: YYYY-MM-DD HH:MM:SS.mmm | LEVEL | module:function:line | session:id | version | os | message
            match = re.match(
                r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \| (\w+)\s* \| ([^|]+) \| session:(\d+) \| ([^|]+) \| ([^|]+) \| (.*)', 
                line
            )
            
            if match:
                timestamp, level, source, session, version, os_info, message = match.groups()
                entry = {
                    "timestamp": timestamp,
                    "level": level.strip(),
                    "source": source.strip(),
                    "session": session.strip(),
                    "version": version.strip(),
                    "os": os_info.strip(),
                    "message": message.strip()
                }
                log_entries.append(entry)
            else:
                # For lines that don't match the format, add as raw text
                log_entries.append({"raw": line})
        
        # Write to JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            export_time = datetime.datetime.now().isoformat()
            json.dump({
                "log_file": self._log_filters["current_file"],
                "export_time": export_time,
                "entries": log_entries,
                "filters": {
                    "levels": self._log_filters["levels"],
                    "text": self._log_filters["text"]
                }
            }, f, indent=2) 