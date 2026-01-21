#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Output handler for managing command outputs and device command panels
"""

import os
import json
import datetime
from pathlib import Path
from collections import Counter
from loguru import logger

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QSplitter, QTabWidget, QTextEdit, QStackedWidget,
    QDialog, QListWidget, QAbstractItemView, QCheckBox, QGroupBox, QFormLayout, QLineEdit, QComboBox
)
from PySide6.QtGui import QFont, QColor

class OutputHandler:
    """Handler for command outputs and device command panels"""
    
    def __init__(self, plugin):
        """Initialize the handler
        
        Args:
            plugin: The CommandManagerPlugin instance
        """
        self.plugin = plugin
        self.outputs = {}  # {device_id: {command_id: {timestamp: output}}}
        
    def load_command_outputs(self):
        """Load command outputs from disk"""
        logger.debug("Loading command outputs from disk")
        
        # Check if the outputs directory exists
        if not self.plugin.output_dir.exists():
            logger.debug(f"Output directory does not exist: {self.plugin.output_dir}")
            # Create it if not exists
            self.plugin.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize outputs
        self.outputs = {}
        
        # First, try to load device-specific output files from plugin data directory
        device_dirs = [d for d in self.plugin.output_dir.iterdir() if d.is_dir()]
        for device_dir in device_dirs:
            device_id = device_dir.name
            output_file = device_dir / "command_outputs.json"
            
            if output_file.exists():
                try:
                    with open(output_file, "r") as f:
                        device_outputs = json.load(f)
                        self.outputs[device_id] = device_outputs
                        
                    logger.debug(f"Loaded command outputs for device {device_id} from {output_file}")
                except Exception as e:
                    logger.error(f"Error loading command outputs for device {device_id}: {e}")
                    logger.exception("Exception details:")
        
        # Next, try to load from workspace device folders
        workspace_device_dir = Path("config/workspaces/default/devices")
        if workspace_device_dir.exists():
            for device_dir in workspace_device_dir.iterdir():
                if device_dir.is_dir():
                    device_id = device_dir.name
                    commands_dir = device_dir / "commands"
                    if commands_dir.exists():
                        output_file = commands_dir / "command_outputs.json"
                        if output_file.exists():
                            try:
                                with open(output_file, "r") as f:
                                    device_outputs = json.load(f)
                                    # Only load if we don't already have outputs for this device
                                    if device_id not in self.outputs:
                                        self.outputs[device_id] = device_outputs
                                        logger.debug(f"Loaded command outputs for device {device_id} from workspace: {output_file}")
                            except Exception as e:
                                logger.error(f"Error loading command outputs for device {device_id} from workspace: {e}")
                                logger.exception("Exception details:")
            
        # If no device-specific outputs found, try to load from the legacy file
        if not self.outputs:
            legacy_file = self.plugin.output_dir / "command_outputs.json"
            if legacy_file.exists():
                try:
                    with open(legacy_file, "r") as f:
                        self.outputs = json.load(f)
                    
                    logger.debug(f"Loaded command outputs from legacy file {legacy_file}")
                    
                    # Migrate to new format
                    self.save_command_outputs()
                except Exception as e:
                    logger.error(f"Error loading legacy command outputs: {e}")
                    logger.exception("Exception details:")
        
        # Log some statistics
        device_count = len(self.outputs)
        command_count = 0
        output_count = 0
        
        for device_id, commands in self.outputs.items():
            command_count += len(commands)
            for cmd_id, timestamps in commands.items():
                output_count += len(timestamps)
                
        logger.info(f"Loaded {output_count} command outputs for {command_count} commands across {device_count} devices")
        
        # Update plugin's outputs reference
        self.plugin.outputs = self.outputs
    
    def save_command_outputs(self):
        """Save command outputs to disk"""
        logger.debug("Saving command outputs to disk")
        # Check if the outputs directory exists
        if not self.plugin.output_dir.exists():
            self.plugin.output_dir.mkdir(parents=True, exist_ok=True)
            
        # No outputs to save
        if not self.outputs:
            logger.debug("No command outputs to save")
            return
            
        # Save outputs for each device in its own folder in the plugin directory
        for device_id, commands in self.outputs.items():
            try:
                # Create device output directory in plugin folder
                device_dir = self.plugin.output_dir / device_id
                device_dir.mkdir(exist_ok=True)
                
                # Save the outputs to disk
                output_file = device_dir / "command_outputs.json"
                with open(output_file, "w") as f:
                    json.dump(commands, f, indent=2)
                    
                logger.debug(f"Saved command outputs for device {device_id} to {output_file}")
                
                # Also save to workspace device folder
                try:
                    # Get workspace device directory
                    workspace_device_dir = Path("config/workspaces/default/devices") / device_id
                    if workspace_device_dir.exists():
                        # Create commands directory if it doesn't exist
                        commands_dir = workspace_device_dir / "commands"
                        commands_dir.mkdir(exist_ok=True)
                        
                        # Save command outputs to workspace
                        workspace_output_file = commands_dir / "command_outputs.json"
                        with open(workspace_output_file, "w") as f:
                            json.dump(commands, f, indent=2)
                            
                        logger.debug(f"Saved command outputs to workspace: {workspace_output_file}")
                except Exception as e:
                    logger.error(f"Error saving command outputs to workspace for device {device_id}: {e}")
                    logger.exception("Exception details:")
                
            except Exception as e:
                logger.error(f"Error saving command outputs for device {device_id}: {e}")
                logger.exception("Exception details:")
        
        # Also save the full outputs file for backward compatibility
        try:
            # Save the outputs to disk
            output_file = self.plugin.output_dir / "command_outputs.json"
            with open(output_file, "w") as f:
                json.dump(self.outputs, f, indent=2)
                
            logger.debug(f"Saved command outputs to {output_file}")
        except Exception as e:
            logger.error(f"Error saving command outputs: {e}")
            logger.exception("Exception details:")
    
    def get_command_outputs(self, device_id, command_id=None):
        """Get command outputs for a device
        
        Args:
            device_id (str): Device ID to get outputs for
            command_id (str, optional): Command ID to get outputs for
            
        Returns:
            dict: Command outputs
        """
        logger.debug(f"Getting command outputs for device: {device_id}")
        
        # Check if we have outputs for this device
        if device_id not in self.outputs:
            logger.debug(f"No outputs found for device: {device_id}")
            return {}
            
        # If command_id is provided, get only those outputs
        if command_id:
            if command_id in self.outputs[device_id]:
                return self.outputs[device_id][command_id]
            else:
                logger.debug(f"No outputs found for device: {device_id}, command: {command_id}")
                return {}
                
        # Otherwise return all outputs for the device
        return self.outputs[device_id]
        
    def add_command_output(self, device_id, command_id, output, command_text=None):
        """Add command output to history
        
        Args:
            device_id (str): Device ID
            command_id (str): Command ID
            output (str): Command output
            command_text (str, optional): Command text
        """
        logger.debug(f"Adding command output for device: {device_id}, command: {command_id}")
        
        # Create device entry if it doesn't exist
        if device_id not in self.outputs:
            self.outputs[device_id] = {}
            
        # Create command entry if it doesn't exist
        if command_id not in self.outputs[device_id]:
            self.outputs[device_id][command_id] = {}
            
        # Add output with timestamp
        timestamp = datetime.datetime.now().isoformat()
        self.outputs[device_id][command_id][timestamp] = {
            "output": output,
            "success": True,
            "command": command_text if command_text else command_id
        }
        
        # Save outputs
        self.save_command_outputs()
        
        logger.debug(f"Added command output for device: {device_id}, command: {command_id}")
        
    def delete_command_output(self, device_id, command_id, timestamp=None):
        """Delete a command output from history
        
        Args:
            device_id (str): Device ID
            command_id (str): Command ID
            timestamp (str, optional): Specific timestamp to delete, or None to delete all
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        logger.debug(f"Deleting command output for device: {device_id}, command: {command_id}, timestamp: {timestamp}")
        
        # Check if we have outputs for this device
        if device_id not in self.outputs:
            logger.warning(f"No outputs found for device: {device_id}")
            return False
            
        # Check if we have outputs for this command
        if command_id not in self.outputs[device_id]:
            logger.warning(f"No outputs found for device: {device_id}, command: {command_id}")
            return False
            
        # If timestamp is provided, delete only that timestamp
        if timestamp:
            if timestamp in self.outputs[device_id][command_id]:
                del self.outputs[device_id][command_id][timestamp]
                
                # If no more timestamps for this command, delete the command
                if not self.outputs[device_id][command_id]:
                    del self.outputs[device_id][command_id]
                    
                # If no more commands for this device, delete the device
                if not self.outputs[device_id]:
                    del self.outputs[device_id]
                    
                # Save outputs
                self.save_command_outputs()
                
                logger.debug(f"Deleted command output for device: {device_id}, command: {command_id}, timestamp: {timestamp}")
                return True
            else:
                logger.warning(f"No output found for device: {device_id}, command: {command_id}, timestamp: {timestamp}")
                return False
        # If no timestamp, delete all outputs for this command
        else:
            del self.outputs[device_id][command_id]
            
            # If no more commands for this device, delete the device
            if not self.outputs[device_id]:
                del self.outputs[device_id]
                
            # Save outputs
            self.save_command_outputs()
            
            logger.debug(f"Deleted all command outputs for device: {device_id}, command: {command_id}")
            return True
            
    def create_device_command_tab(self, device):
        """Create a tab to display device command history"""
        # Create widget
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Create a splitter for command list and output view
        splitter = QSplitter(Qt.Vertical)
        
        # Create a widget for the command list section
        command_list_widget = QWidget()
        command_list_layout = QVBoxLayout(command_list_widget)
        command_list_layout.setContentsMargins(0, 0, 0, 0)
        
        # Command output list
        device_command_list = QTableWidget()
        device_command_list.setColumnCount(3)  # Removed View column
        device_command_list.setHorizontalHeaderLabels(["Command", "Date/Time", "Success"])
        device_command_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        device_command_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        device_command_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        device_command_list.setSelectionBehavior(QTableWidget.SelectRows)
        device_command_list.setSortingEnabled(True)
        
        # Store device for reference
        device_command_list.setProperty("device", device)
        
        # Add command list to layout
        command_list_layout.addWidget(device_command_list)
        
        # Button bar
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self._refresh_device_commands(device_command_list))
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(lambda: self._export_device_commands(device))
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self._delete_device_commands(device_command_list))
        
        run_btn = QPushButton("Run Command")
        run_btn.clicked.connect(lambda: self._run_command_for_device(device))
        
        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(run_btn)
        button_layout.addWidget(export_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        
        # Add buttons to layout
        command_list_layout.addLayout(button_layout)
        
        # Create output view widget
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        
        # Output display options
        display_options = QHBoxLayout()
        
        # Label for the output
        output_label = QLabel("Command Output:")
        
        # Toggle button for table view
        table_view_toggle = QPushButton("Table View")
        table_view_toggle.setCheckable(True)
        table_view_toggle.setProperty("is_table_view", False)
        table_view_toggle.setEnabled(False)  # Initially disabled until we have selectable content
        table_view_toggle.setToolTip("Toggle between text and table view (only available for tabular output)")
        
        display_options.addWidget(output_label)
        display_options.addStretch()
        display_options.addWidget(table_view_toggle)
        
        output_layout.addLayout(display_options)
        
        # Create stacked widget to switch between text and table views
        output_stack = QStackedWidget()
        
        # Raw output view (text)
        raw_output = QTextEdit()
        raw_output.setReadOnly(True)
        raw_output.setFont(QFont("Courier New", 10))
        raw_output.setPlaceholderText("Select a command to view its output")
        
        # Table output view
        table_output = QTableWidget()
        table_output.setSortingEnabled(True)
        table_output.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
        
        # Add widgets to stack
        output_stack.addWidget(raw_output)
        output_stack.addWidget(table_output)
        
        output_layout.addWidget(output_stack)
        
        # Connect the toggle button
        table_view_toggle.clicked.connect(
            lambda checked: self._toggle_output_format(device_command_list, output_stack, raw_output, table_output, checked)
        )
        
        # Add widgets to splitter
        splitter.addWidget(command_list_widget)
        splitter.addWidget(output_widget)
        
        # Set initial sizes (60% command list, 40% output view)
        splitter.setSizes([600, 400])
        
        # Add the splitter to the main layout
        layout.addWidget(splitter)
        
        # Connect selection changed signal
        device_command_list.itemSelectionChanged.connect(
            lambda: self._on_command_selection_changed(device_command_list, output_stack, raw_output, table_output, table_view_toggle)
        )
        
        # Set up device command list
        self._refresh_device_commands(device_command_list)
        
        return widget
        
    def _refresh_device_commands(self, command_list):
        """Refresh the device command list"""
        # Clear the table
        command_list.setRowCount(0)
        
        # Get device
        device = command_list.property("device")
        if not device:
            return
            
        # Get command outputs for device
        outputs = self.get_command_outputs(device.id)
        
        # Add rows for each command output
        for cmd_id, cmd_outputs in outputs.items():
            for timestamp, data in cmd_outputs.items():
                row = command_list.rowCount()
                command_list.insertRow(row)
                
                # Command
                cmd_text = data.get("command", cmd_id)
                cmd_item = QTableWidgetItem(cmd_text)
                
                # Store metadata in the item
                cmd_item.setData(Qt.UserRole, {
                    "device_id": device.id,
                    "command_id": cmd_id,
                    "timestamp": timestamp,
                    "output": data.get("output", "")
                })
                
                # Date/time
                dt = datetime.datetime.fromisoformat(timestamp)
                dt_item = QTableWidgetItem(dt.strftime("%Y-%m-%d %H:%M:%S"))
                
                # Success
                success = "Yes" if data.get("success", True) else "No"
                success_item = QTableWidgetItem(success)
                
                # Add to row
                command_list.setItem(row, 0, cmd_item)
                command_list.setItem(row, 1, dt_item)
                command_list.setItem(row, 2, success_item)
        
    def _on_command_selection_changed(self, command_list, output_stack, raw_output, table_output, table_view_toggle):
        """Handle command selection changed
        
        Args:
            command_list: The command list widget
            output_stack: The stacked widget containing raw and table outputs
            raw_output: The raw output text edit widget
            table_output: The table output widget
            table_view_toggle: The toggle button for table view
        """
        # Get selected items
        selected_items = command_list.selectedItems()
        if not selected_items:
            raw_output.clear()
            table_output.setRowCount(0)
            table_output.setColumnCount(0)
            table_view_toggle.setEnabled(False)
            table_view_toggle.setChecked(False)
            return
            
        # Get the first selected row
        row = selected_items[0].row()
        
        # Get the command item (first column)
        command_item = command_list.item(row, 0)
        if not command_item:
            return
            
        # Get the stored data
        data = command_item.data(Qt.UserRole)
        if not data:
            return
            
        # Get the output
        output_text = data.get("output", "")
        
        # Store output text for later use
        raw_output.setProperty("current_output", output_text)
        
        # Check if output can be displayed as a table
        can_be_table = self._can_display_as_table(output_text)
        table_view_toggle.setEnabled(can_be_table)
        
        # Check if we should maintain table view (if it was previously enabled and new output supports it)
        was_table_view = table_view_toggle.isChecked() and can_be_table
        
        if was_table_view:
            # Parse and show as table
            self._parse_output_to_table(output_text, table_output)
            output_stack.setCurrentWidget(table_output)
            table_view_toggle.setChecked(True)
        else:
            # Show raw output
            raw_output.setPlainText(output_text)
            output_stack.setCurrentWidget(raw_output)
            table_view_toggle.setChecked(False)
            
    def _toggle_output_format(self, command_list, output_stack, raw_output, table_output, is_table_view):
        """Toggle between raw and table output formats
        
        Args:
            command_list: The command list widget
            output_stack: The stacked widget containing raw and table outputs
            raw_output: The raw output text edit widget
            table_output: The table output widget
            is_table_view: Whether table view is enabled
        """
        # Get the current output text
        output_text = raw_output.property("current_output")
        if not output_text:
            return
            
        if is_table_view:
            # Parse the output into a table and show it
            self._parse_output_to_table(output_text, table_output)
            output_stack.setCurrentWidget(table_output)
        else:
            # Switch to raw view
            output_stack.setCurrentWidget(raw_output)
    
    def _update_output_display(self, output_text, is_table_view):
        """Update the output display based on the selected format
        
        Args:
            output_text: The output text edit widget
            is_table_view: Whether to show as table format
        """
        # Get the current output text
        current_output = output_text.property("current_output")
        if not current_output:
            return
            
        if is_table_view:
            # Try to format as table
            try:
                # Simple table formatting - add bold for headers and ensure alignment
                lines = current_output.strip().split('\n')
                if len(lines) > 2:
                    # Check if this looks like a table
                    if '|' in lines[0] or '  ' in lines[0]:
                        formatted_output = "<pre>"
                        # Format the first line as a header
                        if '|' in lines[0]:
                            # For pipe-separated tables
                            headers = [h.strip() for h in lines[0].split('|')]
                            formatted_output += "<b>" + " | ".join(headers) + "</b>\n"
                            formatted_output += "-" * len(lines[0]) + "\n"
                        else:
                            # For space-separated tables
                            formatted_output += "<b>" + lines[0] + "</b>\n"
                            formatted_output += "-" * len(lines[0]) + "\n"
                            
                        # Add the rest of the lines
                        for line in lines[1:]:
                            formatted_output += line + "\n"
                            
                        formatted_output += "</pre>"
                        output_text.setHtml(formatted_output)
                        return
                    
                # If we get here, it doesn't look like a table
                output_text.setText("Cannot display this output as a formatted table.")
            except Exception as e:
                logger.error(f"Error formatting output as table: {e}")
                output_text.setText(f"Error formatting as table: {str(e)}")
        else:
            # Raw format
            output_text.setPlainText(current_output)
        
    def _run_command_for_device(self, device):
        """Run a command for a specific device
        
        Args:
            device: The device to run a command on
        """
        from plugins.command_manager.ui.command_dialog import CommandDialog
        
        # Create and show the command dialog with the selected device
        dialog = CommandDialog(self.plugin, [device], parent=self.plugin.main_window)
        result = dialog.exec()
        
        # Refresh the commands panel if a command was run
        if result and hasattr(self.plugin, 'commands_panel_widget') and self.plugin.commands_panel_widget:
            self.update_commands_panel(device)
        
    def _export_device_commands(self, device):
        """Export device commands to file"""
        # Get selected device
        devices = self.plugin.device_manager.get_selected_devices()
        if not devices:
            return
            
        device = devices[0]
        
        # Get command outputs for device
        all_outputs = self.get_command_outputs(device.id)
        if not all_outputs:
            QMessageBox.information(
                self.plugin.main_window,
                "No Outputs",
                f"No command outputs found for {device.get_property('alias', 'Device')}"
            )
            return
        
        # Create a dialog to select which commands to export
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QAbstractItemView, 
            QCheckBox, QGroupBox, QFormLayout, QLineEdit, QPushButton
        )
        select_dialog = QDialog(self.plugin.main_window)
        select_dialog.setWindowTitle("Export Commands")
        select_dialog.resize(600, 500)
        
        layout = QVBoxLayout(select_dialog)
        
        # Command selection section
        command_group = QGroupBox("Select Commands to Export")
        command_layout = QVBoxLayout(command_group)
        
        # Create a list widget for commands
        command_list = QListWidget()
        command_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        command_layout.addWidget(command_list)
        
        # Add command entries to the list
        for cmd_id, timestamps in all_outputs.items():
            # Get the most recent output
            latest_timestamp = max(timestamps.keys())
            cmd_data = timestamps[latest_timestamp]
            cmd_text = cmd_data.get("command", cmd_id)
            
            # Add to list
            command_list.addItem(cmd_text)
            # Store the command_id and timestamp as data
            item = command_list.item(command_list.count() - 1)
            item.setData(Qt.UserRole, {"command_id": cmd_id, "timestamp": latest_timestamp})
        
        # Select all items by default
        for i in range(command_list.count()):
            command_list.item(i).setSelected(True)
            
        command_layout.addWidget(command_list)
        
        # Output format options
        export_options_group = QGroupBox("Export Options")
        export_options_layout = QVBoxLayout(export_options_group)
        
        # Add a checkbox for "Export to individual files"
        individual_files_cb = QCheckBox("Export each command to a separate file")
        individual_files_cb.setChecked(True)
        export_options_layout.addWidget(individual_files_cb)
        
        # Export format selection
        format_label = QLabel("Export Format:")
        export_format_combo = QComboBox()
        export_format_combo.addItems(["Auto (Text/Table)", "Text", "CSV (Table)", "HTML"])
        export_options_layout.addWidget(format_label)
        export_options_layout.addWidget(export_format_combo)
        
        # Filename template settings
        template_group = QGroupBox("Filename Template")
        template_layout = QFormLayout(template_group)
        
        # Template edit
        template_edit = QLineEdit(self.plugin.settings["export_filename_template"]["value"])
        template_layout.addRow("Template:", template_edit)
        
        # Template help
        template_help = QLabel(
            "Available variables: {hostname}, {ip}, {command}, {date}, {status}, plus any device property"
        )
        template_help.setWordWrap(True)
        template_layout.addRow("", template_help)
        
        # Date format
        date_format_edit = QLineEdit(self.plugin.settings["export_date_format"]["value"])
        template_layout.addRow("Date Format:", date_format_edit)
        
        # Command format
        command_format_combo = QComboBox()
        command_format_combo.addItems(["truncated", "full", "sanitized"])
        index = command_format_combo.findText(self.plugin.settings["export_command_format"]["value"])
        if index >= 0:
            command_format_combo.setCurrentIndex(index)
        template_layout.addRow("Command Format:", command_format_combo)
        
        # Add preview section
        preview_group = QGroupBox("Export Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        # Preview button
        preview_button = QPushButton("Generate Preview")
        preview_layout.addWidget(preview_button)
        
        # Preview text
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setMaximumHeight(100)
        preview_layout.addWidget(preview_text)
        
        # Function to update the preview
        def update_preview():
            selected_items = command_list.selectedItems()
            if not selected_items:
                preview_text.setPlainText("No commands selected")
                return
                
            # Create a temporary handler with the current settings
            class TempPlugin:
                def __init__(self):
                    self.settings = {
                        "export_filename_template": {"value": template_edit.text()},
                        "export_date_format": {"value": date_format_edit.text()},
                        "export_command_format": {"value": command_format_combo.currentText()}
                    }
                    
            temp_plugin = TempPlugin()
            temp_handler = OutputHandler(temp_plugin)
            
            # Generate preview
            preview_content = "Filename preview:\n\n"
            
            for i, item in enumerate(selected_items):
                if i >= 5:  # Limit preview to 5 items
                    preview_content += f"... and {len(selected_items) - 5} more\n"
                    break
                    
                data = item.data(Qt.UserRole)
                cmd_id = data["command_id"]
                cmd_text = item.text()
                
                filename = temp_handler.generate_export_filename(device, cmd_id, cmd_text)
                if not filename.lower().endswith('.txt'):
                    filename += ".txt"
                    
                preview_content += f"{cmd_text} → {filename}\n"
                
            preview_text.setPlainText(preview_content)
        
        # Connect preview button
        preview_button.clicked.connect(update_preview)
        
        # Add checkbox to save settings
        save_settings_cb = QCheckBox("Save these settings as default")
        preview_layout.addWidget(save_settings_cb)
        
        # Add all option groups to the layout
        layout.addWidget(command_group)
        layout.addWidget(export_options_group)
        layout.addWidget(template_group)
        layout.addWidget(preview_group)
        
        # Add buttons
        button_layout = QHBoxLayout()
        from PySide6.QtWidgets import QPushButton
        
        export_btn = QPushButton("Export")
        cancel_btn = QPushButton("Cancel")
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)
        
        # Connect buttons
        cancel_btn.clicked.connect(select_dialog.reject)
        export_btn.clicked.connect(select_dialog.accept)
        
        # Generate initial preview
        update_preview()
        
        # Show dialog
        if not select_dialog.exec():
            return
        
        # Save settings if requested
        if save_settings_cb.isChecked():
            self.plugin.settings["export_filename_template"]["value"] = template_edit.text()
            self.plugin.settings["export_date_format"]["value"] = date_format_edit.text()
            self.plugin.settings["export_command_format"]["value"] = command_format_combo.currentText()
        
        # Get selected commands
        selected_items = command_list.selectedItems()
        if not selected_items:
            return
            
        selected_commands = []
        for item in selected_items:
            data = item.data(Qt.UserRole)
            selected_commands.append((data["command_id"], data["timestamp"], item.text()))
        
        # Create a temporary handler with the current dialog settings
        class TempPlugin:
            def __init__(self):
                self.settings = {
                    "export_filename_template": {"value": template_edit.text()},
                    "export_date_format": {"value": date_format_edit.text()},
                    "export_command_format": {"value": command_format_combo.currentText()}
                }
                
        temp_plugin = TempPlugin()
        temp_handler = OutputHandler(temp_plugin)
        
        # Get export format
        export_format = export_format_combo.currentText()
        
        # Handle export to individual files or a single file
        if individual_files_cb.isChecked():
            # Ask for directory to save files
            export_dir = QFileDialog.getExistingDirectory(
                self.plugin.main_window,
                "Select Export Directory",
                ""
            )
            
            if not export_dir:
                return
                
            # Export each command to a separate file
            exported_count = 0
            exported_files = []
            
            for cmd_id, timestamp, cmd_text in selected_commands:
                try:
                    # Get the command output
                    output_data = all_outputs[cmd_id][timestamp]
                    output = output_data.get("output", "")
                    
                    # Determine file extension and format
                    file_ext = ".txt"
                    if export_format == "CSV (Table)":
                        file_ext = ".csv"
                    elif export_format == "HTML":
                        file_ext = ".html"
                    elif export_format == "Auto (Text/Table)":
                        # Check if output can be displayed as table
                        if self._can_display_as_table(output):
                            file_ext = ".csv"
                    
                    # Generate filename based on template
                    filename = temp_handler.generate_export_filename(device, cmd_id, cmd_text)
                    # Remove existing extension if present
                    if '.' in filename:
                        filename = os.path.splitext(filename)[0]
                    filename += file_ext
                        
                    # Full path
                    file_path = os.path.join(export_dir, filename)
                    
                    # If file exists, add a number suffix to avoid overwriting
                    counter = 1
                    original_path = file_path
                    while os.path.exists(file_path):
                        file_name, file_ext = os.path.splitext(original_path)
                        file_path = f"{file_name}_{counter}{file_ext}"
                        counter += 1
                    
                    # Export to file based on format
                    if file_ext == ".csv":
                        self._export_table_to_csv(file_path, output, device, cmd_text, timestamp)
                    elif file_ext == ".html":
                        self._export_to_html(file_path, output, device, cmd_text, timestamp)
                    else:
                        # Text export
                        with open(file_path, "w", encoding='utf-8') as f:
                            f.write(f"Device: {device.get_property('alias', 'Device')}\n")
                            f.write(f"Command: {cmd_text}\n")
                            f.write(f"Date/Time: {datetime.datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write("-" * 50 + "\n")
                            f.write(output)
                    
                    exported_count += 1
                    exported_files.append(os.path.basename(file_path))
                    
                except Exception as e:
                    logger.error(f"Error exporting command {cmd_id}: {e}")
            
            # Show success message with exported filenames
            if exported_count > 0:
                files_list = "\n".join(exported_files[:5])
                if len(exported_files) > 5:
                    files_list += f"\n... and {len(exported_files) - 5} more"
                    
                QMessageBox.information(
                    self.plugin.main_window,
                    "Export Successful",
                    f"Exported {exported_count} command outputs to {export_dir}\n\nFiles:\n{files_list}"
                )
            else:
                QMessageBox.warning(
                    self.plugin.main_window,
                    "Export Failed",
                    "Failed to export any commands."
                )
            
        else:
            # Export all to a single file
            # Determine file filter based on export format
            if export_format == "CSV (Table)":
                file_filter = "CSV Files (*.csv);;All Files (*.*)"
            elif export_format == "HTML":
                file_filter = "HTML Files (*.html);;All Files (*.*)"
            else:
                file_filter = "Text Files (*.txt);;CSV Files (*.csv);;HTML Files (*.html);;All Files (*.*)"
            
            # Ask for file to save to
            file_path, _ = QFileDialog.getSaveFileName(
                self.plugin.main_window,
                "Export Command Outputs",
                "",
                file_filter
            )
            
            if not file_path:
                return
                
            try:
                # Determine export format from file extension or selection
                if file_path.lower().endswith(".csv") or export_format == "CSV (Table)":
                    # CSV export - export each command as a separate sheet or combine
                    self._export_multiple_tables_to_csv(file_path, selected_commands, all_outputs, device)
                elif file_path.lower().endswith(".html") or export_format == "HTML":
                    # HTML export
                    with open(file_path, "w", encoding='utf-8') as f:
                        f.write("<html><head><title>Command Outputs</title></head><body>\n")
                        f.write(f"<h1>Command Outputs for {device.get_property('alias', 'Device')}</h1>\n")
                        
                        for cmd_id, timestamp, cmd_text in selected_commands:
                            output_data = all_outputs[cmd_id][timestamp]
                            output = output_data.get("output", "")
                            dt = datetime.datetime.fromisoformat(timestamp)
                            
                            f.write(f"<h2>{cmd_text}</h2>\n")
                            f.write(f"<p>Date/Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
                            
                            # Check if output can be displayed as table
                            if export_format == "Auto (Text/Table)" and self._can_display_as_table(output):
                                # Export as HTML table
                                f.write(self._output_to_html_table(output))
                            else:
                                f.write("<pre>\n")
                                f.write(output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                                f.write("\n</pre>\n")
                            f.write("<hr>\n")
                            
                        f.write("</body></html>")
                else:
                    # Text export
                    with open(file_path, "w", encoding='utf-8') as f:
                        f.write(f"Command Outputs for {device.get_property('alias', 'Device')}\n")
                        f.write("=" * 50 + "\n\n")
                        
                        for cmd_id, timestamp, cmd_text in selected_commands:
                            output_data = all_outputs[cmd_id][timestamp]
                            output = output_data.get("output", "")
                            dt = datetime.datetime.fromisoformat(timestamp)
                            
                            f.write(f"Command: {cmd_text}\n")
                            f.write(f"Date/Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write("-" * 50 + "\n")
                            f.write(output)
                            f.write("\n\n" + "=" * 80 + "\n\n")
                
                # Show success message
                QMessageBox.information(
                    self.plugin.main_window,
                    "Export Successful",
                    f"Command outputs exported to {file_path}"
                )
                
            except Exception as e:
                # Show error message
                QMessageBox.critical(
                    self.plugin.main_window,
                    "Export Failed",
                    f"Failed to export command outputs: {str(e)}"
                )
            
    def _delete_device_commands(self, command_list):
        """Delete selected device commands"""
        # Get selected rows
        selected_rows = command_list.selectedItems()
        if not selected_rows:
            return
            
        # Get selected device
        devices = self.plugin.device_manager.get_selected_devices()
        if not devices:
            return
            
        device = devices[0]
        
        # Confirm deletion
        result = QMessageBox.question(
            self.plugin.main_window,
            "Confirm Deletion",
            "Are you sure you want to delete the selected command outputs?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete selected outputs
        deleted = 0
        rows_to_delete = set()
        
        for item in selected_rows:
            row = item.row()
            rows_to_delete.add(row)
            
        for row in sorted(rows_to_delete, reverse=True):
            # Get the command item (first column)
            cmd_item = command_list.item(row, 0)
            if cmd_item:
                # Get the metadata from the item
                data = cmd_item.data(Qt.UserRole)
                if data:
                    device_id = data.get("device_id")
                    command_id = data.get("command_id")
                    timestamp = data.get("timestamp")
                    
                    if device_id and command_id and timestamp:
                        if self.delete_command_output(device_id, command_id, timestamp):
                            deleted += 1
                    
        # Refresh the list
        self._refresh_device_commands(command_list)
        
        # Show success message
        QMessageBox.information(
            self.plugin.main_window,
            "Deletion Successful",
            f"Deleted {deleted} command output(s)"
        )
            
    def get_device_panels(self):
        """Get panels to be added to the device properties panel
        
        Returns:
            list: List of (panel_name, panel_widget) tuples
        """
        logger.debug("Getting device panels for Command Manager plugin")
        
        # Create a device-agnostic commands tab initially - it will update when a device is selected
        commands_tab = QWidget()
        layout = QVBoxLayout(commands_tab)
        
        # Add info label
        info_label = QLabel("Select a device to view and manage commands for that device.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # We'll store this widget to update it later when a device is selected
        self.plugin.commands_panel_widget = commands_tab
        
        return [
            ("Commands", commands_tab)
        ]
            
    def update_commands_panel(self, device):
        """Update the commands panel with the selected device
        
        Args:
            device: The selected device
        """
        logger.debug(f"Updating commands panel for device: {device.id}")
        
        if not hasattr(self.plugin, 'commands_panel_widget') or not self.plugin.commands_panel_widget:
            logger.warning("Commands panel widget not found")
            return
            
        # Clear existing widgets from the panel
        panel = self.plugin.commands_panel_widget
        
        # Remove all widgets from layout
        if panel.layout():
            while panel.layout().count():
                item = panel.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            # Create layout if none exists
            panel.setLayout(QVBoxLayout())
            
        layout = panel.layout()
        
        # Get command outputs for the device
        outputs = self.get_command_outputs(device.id)
        
        # Create a splitter for command list and output view
        splitter = QSplitter(Qt.Vertical)
        
        # Create a widget for the command list section
        command_list_widget = QWidget()
        command_list_layout = QVBoxLayout(command_list_widget)
        command_list_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a table for command history
        command_list = QTableWidget()
        command_list.setColumnCount(3)  # Removed View column
        command_list.setHorizontalHeaderLabels(["Command", "Date/Time", "Success"])
        command_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        command_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        command_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        command_list.setSelectionBehavior(QTableWidget.SelectRows)
        command_list.setSortingEnabled(True)
        
        # Store device for reference
        command_list.setProperty("device", device)
        
        # Add command outputs to the table
        for cmd_id, cmd_outputs in outputs.items():
            for timestamp, data in cmd_outputs.items():
                row = command_list.rowCount()
                command_list.insertRow(row)
                
                # Command
                cmd_text = data.get("command", cmd_id)
                cmd_item = QTableWidgetItem(cmd_text)
                
                # Store metadata in the item
                cmd_item.setData(Qt.UserRole, {
                    "device_id": device.id,
                    "command_id": cmd_id,
                    "timestamp": timestamp,
                    "output": data.get("output", "")
                })
                
                # Date/time
                dt = datetime.datetime.fromisoformat(timestamp)
                dt_item = QTableWidgetItem(dt.strftime("%Y-%m-%d %H:%M:%S"))
                
                # Success
                success = "Yes" if data.get("success", True) else "No"
                success_item = QTableWidgetItem(success)
                
                # Add to row
                command_list.setItem(row, 0, cmd_item)
                command_list.setItem(row, 1, dt_item)
                command_list.setItem(row, 2, success_item)
        
        # Add the table to the layout
        command_list_layout.addWidget(command_list)
        
        # Button bar
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self._refresh_device_commands(command_list))
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(lambda: self._export_device_commands(device))
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self._delete_device_commands(command_list))
        
        run_btn = QPushButton("Run Command")
        run_btn.clicked.connect(lambda: self._run_command_for_device(device))
        
        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(run_btn)
        button_layout.addWidget(export_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        
        # Add buttons to the layout
        command_list_layout.addLayout(button_layout)
        
        # Create output view widget
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        
        # Output display options
        display_options = QHBoxLayout()
        
        # Label for the output
        output_label = QLabel("Command Output:")
        
        # Toggle button for table view
        table_view_toggle = QPushButton("Table View")
        table_view_toggle.setCheckable(True)
        table_view_toggle.setProperty("is_table_view", False)
        table_view_toggle.setEnabled(False)  # Initially disabled until we have selectable content
        table_view_toggle.setToolTip("Toggle between text and table view (only available for tabular output)")
        
        display_options.addWidget(output_label)
        display_options.addStretch()
        display_options.addWidget(table_view_toggle)
        
        output_layout.addLayout(display_options)
        
        # Create stacked widget to switch between text and table views
        output_stack = QStackedWidget()
        
        # Raw output view (text)
        raw_output = QTextEdit()
        raw_output.setReadOnly(True)
        raw_output.setFont(QFont("Courier New", 10))
        raw_output.setPlaceholderText("Select a command to view its output")
        
        # Table output view
        table_output = QTableWidget()
        table_output.setSortingEnabled(True)
        table_output.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
        
        # Add widgets to stack
        output_stack.addWidget(raw_output)
        output_stack.addWidget(table_output)
        
        output_layout.addWidget(output_stack)
        
        # Connect the toggle button
        table_view_toggle.clicked.connect(
            lambda checked: self._toggle_output_format(command_list, output_stack, raw_output, table_output, checked)
        )
        
        # Add widgets to splitter
        splitter.addWidget(command_list_widget)
        splitter.addWidget(output_widget)
        
        # Set initial sizes (60% command list, 40% output view)
        splitter.setSizes([600, 400])
        
        # Add the splitter to the main layout
        layout.addWidget(splitter)
        
        # Connect selection changed signal
        command_list.itemSelectionChanged.connect(
            lambda: self._on_command_selection_changed(command_list, output_stack, raw_output, table_output, table_view_toggle)
        )
        
        # Display a message if no commands found
        if command_list.rowCount() == 0:
            info_label = QLabel(f"No command history found for device: {device.get_property('alias', device.id)}")
            info_label.setWordWrap(True)
            layout.insertWidget(0, info_label)
    
    def _can_display_as_table(self, text):
        """Determine if text can be displayed as a table
        
        Args:
            text: The text to check
            
        Returns:
            bool: Whether the text can be displayed as a table
        """
        if not text or len(text.strip()) == 0:
            return False
            
        lines = [line.rstrip() for line in text.strip().split('\n') if line.strip()]
        if len(lines) < 2:  # Need at least header and one data row
            return False
            
        # Look for common table formats
        
        # Check for pipe-separated format
        if '|' in lines[0]:
            # Count pipes in header and make sure they're consistent
            pipe_count = lines[0].count('|')
            if pipe_count < 1:  # Need at least one separator
                return False
                
            # Check a sample of lines to ensure consistent format
            consistent_count = 0
            for i in range(1, min(10, len(lines))):
                if i < len(lines) and lines[i].strip():
                    # Allow some variation (within 1 pipe difference for edge cases)
                    if abs(lines[i].count('|') - pipe_count) <= 1:
                        consistent_count += 1
                    elif lines[i].count('|') == 0:
                        # Empty line or separator line, skip
                        continue
                    else:
                        # Too different, probably not a table
                        return False
                        
            # Need at least 2 consistent data rows
            return consistent_count >= 1
            
        # Check for space-aligned columns (at least 2 spaces between columns)
        # Look for multiple consecutive spaces that indicate column separation
        if '  ' in lines[0]:
            # Count occurrences of 2+ spaces in header
            header_spaces = len([i for i in range(len(lines[0]) - 1) 
                                if lines[0][i:i+2] == '  '])
            
            if header_spaces >= 1:  # At least one column separator
                # Check if subsequent lines have similar structure
                consistent_rows = 0
                for i in range(1, min(10, len(lines))):
                    if not lines[i].strip():
                        continue  # Skip empty lines
                    if len(lines[i]) < 10:
                        continue  # Skip very short lines
                    
                    # Check if line has similar spacing pattern
                    line_spaces = len([j for j in range(len(lines[i]) - 1) 
                                      if lines[i][j:j+2] == '  '])
                    # Allow some variation
                    if abs(line_spaces - header_spaces) <= 2:
                        consistent_rows += 1
                        
                # Need at least 1 consistent data row
                if consistent_rows >= 1:
                    return True
                    
        # Check for tab-separated format
        if '\t' in lines[0]:
            tab_count = lines[0].count('\t')
            if tab_count >= 1:
                # Check consistency
                consistent_count = 0
                for i in range(1, min(10, len(lines))):
                    if i < len(lines) and lines[i].strip():
                        if abs(lines[i].count('\t') - tab_count) <= 1:
                            consistent_count += 1
                return consistent_count >= 1
                
        # Check for comma-separated format (CSV-like)
        if ',' in lines[0] and lines[0].count(',') >= 2:
            comma_count = lines[0].count(',')
            consistent_count = 0
            for i in range(1, min(10, len(lines))):
                if i < len(lines) and lines[i].strip():
                    if abs(lines[i].count(',') - comma_count) <= 2:
                        consistent_count += 1
            if consistent_count >= 1:
                return True
                
        # Check if output looks structured (multiple words per line, consistent structure)
        # This is a fallback for outputs that might be tables but don't match above patterns
        if len(lines) >= 3:
            # Check if first few lines have similar word counts (indicating columns)
            word_counts = [len(line.split()) for line in lines[:5] if line.strip()]
            if len(word_counts) >= 3:
                # Check if word counts are similar (within 2 words)
                min_words = min(word_counts)
                max_words = max(word_counts)
                # If all lines have similar word counts and at least 3 words, might be a table
                if max_words - min_words <= 2 and min_words >= 3:
                    # Additional check: see if lines have similar length
                    line_lengths = [len(line) for line in lines[:5] if line.strip()]
                    if len(line_lengths) >= 3:
                        avg_length = sum(line_lengths) / len(line_lengths)
                        # If lengths are reasonably consistent (within 50% of average)
                        if all(abs(len(line) - avg_length) < avg_length * 0.5 
                               for line in lines[:5] if line.strip()):
                            return True
                
        return False
    
    def _parse_output_to_table(self, text, table_widget):
        """Parse text output into a table format
        
        Args:
            text: The text to parse
            table_widget: The table widget to populate
        """
        table_widget.clear()
        table_widget.setRowCount(0)
        table_widget.setColumnCount(0)
        
        lines = [line.rstrip() for line in text.strip().split('\n') if line.strip()]
        if len(lines) < 2:
            return
            
        # Determine table format and parse accordingly
        if '|' in lines[0]:
            # Pipe-separated format
            self._parse_pipe_separated_table(lines, table_widget)
        elif '\t' in lines[0]:
            # Tab-separated format
            self._parse_tab_separated_table(lines, table_widget)
        elif ',' in lines[0] and lines[0].count(',') >= 2:
            # CSV-like format (comma-separated)
            self._parse_csv_table(lines, table_widget)
        else:
            # Space-separated format
            self._parse_space_separated_table(lines, table_widget)
            
    def _parse_pipe_separated_table(self, lines, table_widget):
        """Parse pipe-separated text into a table
        
        Args:
            lines: List of text lines
            table_widget: The table widget to populate
        """
        # Get headers (first line) - include empty cells between pipes
        header_parts = lines[0].split('|')
        headers = [h.strip() for h in header_parts]
        # Remove empty headers at start/end if they're just from leading/trailing pipes
        if headers and not headers[0]:
            headers = headers[1:]
        if headers and not headers[-1]:
            headers = headers[:-1]
            
        if not headers:
            return
            
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        
        # Set up header
        for col in range(len(headers)):
            table_widget.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
            )
        
        # Skip any separator line after header (containing only dashes, plusses, pipes, spaces)
        start_row = 1
        if len(lines) > 1:
            separator_line = lines[1].strip()
            if separator_line and all(c in '-+| ' for c in separator_line):
                start_row = 2
            
        # Add data rows
        for i in range(start_row, len(lines)):
            if not lines[i].strip():
                continue  # Skip empty lines
                
            # Split by pipe and include empty cells
            row_parts = lines[i].split('|')
            row_data = [d.strip() for d in row_parts]
            # Remove empty cells at start/end if they're just from leading/trailing pipes
            if row_data and not row_data[0]:
                row_data = row_data[1:]
            if row_data and not row_data[-1]:
                row_data = row_data[:-1]
                
            if not row_data:
                continue
                
            row_idx = table_widget.rowCount()
            table_widget.insertRow(row_idx)
            
            # Pad row_data to match header count if needed
            while len(row_data) < len(headers):
                row_data.append("")
            # Truncate if too long
            row_data = row_data[:len(headers)]
            
            for col, data in enumerate(row_data):
                item = QTableWidgetItem(data)
                table_widget.setItem(row_idx, col, item)
        
    def _parse_space_separated_table(self, lines, table_widget):
        """Parse space-separated text into a table
        
        Args:
            lines: List of text lines
            table_widget: The table widget to populate
        """
        if len(lines) < 2:
            return
        
        header_line = lines[0]
        
        # Method 1: Use header to determine column boundaries
        # Find where each header word starts and ends
        header_words = header_line.split()
        if len(header_words) < 2:
            return

        # Special-case common switch port status tables where the Name column
        # can include spaces and the trailing columns are fixed.
        normalized_headers = [h.strip().lower() for h in header_words]
        if normalized_headers == ["port", "name", "status", "vlan", "duplex", "speed", "type"]:
            headers = header_words
            table_widget.setColumnCount(len(headers))
            table_widget.setHorizontalHeaderLabels(headers)

            for col in range(len(headers)):
                table_widget.horizontalHeader().setSectionResizeMode(
                    col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
                )

            header_line_normalized = header_line.strip().lower()
            for i in range(1, len(lines)):
                line = lines[i].strip()
                if not line:
                    continue
                # Skip repeated header lines inside the output
                if line.lower() == header_line_normalized:
                    continue

                parts = line.split()
                if len(parts) < 5:
                    continue

                port = parts[0]

                # Some platforms omit the Type column (e.g., port-channels).
                last_token = parts[-1]
                looks_like_type = (
                    last_token.lower() == "unknown"
                    or "base" in last_token.lower()
                    or ("/" in last_token and any(ch.isalpha() for ch in last_token))
                )

                if looks_like_type and len(parts) >= 6:
                    type_value = last_token
                    speed = parts[-2]
                    duplex = parts[-3]
                    vlan = parts[-4]
                    status = parts[-5]
                    name = " ".join(parts[1:-5]).strip()
                else:
                    type_value = ""
                    speed = parts[-1]
                    duplex = parts[-2] if len(parts) >= 3 else ""
                    vlan = parts[-3] if len(parts) >= 4 else ""
                    status = parts[-4] if len(parts) >= 5 else ""
                    name = " ".join(parts[1:-4]).strip() if len(parts) >= 5 else ""

                row_data = [port, name, status, vlan, duplex, speed, type_value]
                row_idx = table_widget.rowCount()
                table_widget.insertRow(row_idx)
                for col, data in enumerate(row_data):
                    item = QTableWidgetItem(data)
                    table_widget.setItem(row_idx, col, item)
            return
        
        # Find the start position of each header word in the original string
        word_positions = []
        search_start = 0
        for word in header_words:
            pos = header_line.find(word, search_start)
            if pos == -1:
                break
            word_positions.append((pos, pos + len(word), word))
            search_start = pos + len(word)
        
        if len(word_positions) < 2:
            return
        
        # Determine column boundaries
        # Each column starts where its header word starts
        # But we need to find where the next column's data starts in data rows
        col_boundaries = [0]  # First column always starts at 0
        
        # For each header word (except the last), find where the next column starts
        # This is typically where the next header word starts, but we'll refine with data
        for i in range(len(word_positions) - 1):
            current_word_end = word_positions[i][1]
            next_word_start = word_positions[i + 1][0]
            # The boundary is typically where the next word starts
            col_boundaries.append(next_word_start)
        
        # Verify and refine boundaries with data rows
        refined_boundaries = self._refine_column_boundaries(col_boundaries, lines[:min(10, len(lines))])
        
        if len(refined_boundaries) >= len(header_words):
            # Extract headers
            headers = []
            for i in range(len(refined_boundaries)):
                start = refined_boundaries[i]
                end = len(header_line) if i == len(refined_boundaries) - 1 else refined_boundaries[i + 1]
                header = header_line[start:end].strip()
                if header:
                    headers.append(header)
            
            # Ensure we have the right number of headers
            while len(headers) < len(header_words):
                # Add missing headers from split
                if len(headers) < len(header_words):
                    headers.append(header_words[len(headers)])
            headers = headers[:len(header_words)]
            
            if len(headers) >= 2:
                table_widget.setColumnCount(len(headers))
                table_widget.setHorizontalHeaderLabels(headers)
                
                # Set up header
                for col in range(len(headers)):
                    table_widget.horizontalHeader().setSectionResizeMode(
                        col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
                    )
                    
                # Add data rows
                for i in range(1, len(lines)):
                    if not lines[i].strip():
                        continue
                    if lines[i].strip().lower() == header_line.strip().lower():
                        continue
                        
                    row_data = []
                    for j in range(len(refined_boundaries)):
                        start = refined_boundaries[j]
                        end = len(lines[i]) if j == len(refined_boundaries) - 1 else refined_boundaries[j + 1]
                        if start < len(lines[i]):
                            cell_data = lines[i][start:end].strip()
                            row_data.append(cell_data)
                        else:
                            row_data.append("")
                    
                    # Pad or truncate to match header count
                    while len(row_data) < len(headers):
                        row_data.append("")
                    row_data = row_data[:len(headers)]
                            
                    if not any(row_data):  # Skip empty rows
                        continue
                        
                    row_idx = table_widget.rowCount()
                    table_widget.insertRow(row_idx)
                    
                    for col, data in enumerate(row_data):
                        item = QTableWidgetItem(data)
                        table_widget.setItem(row_idx, col, item)
                return
        
        # Method 2: Fallback - split by multiple spaces (2+ spaces)
        header_line = lines[0]
        # Try splitting by 2+ spaces first
        headers = []
        parts = header_line.split('  ')
        for part in parts:
            # Further split by single spaces if needed
            subparts = [p.strip() for p in part.split() if p.strip()]
            headers.extend(subparts)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_headers = []
        for h in headers:
            if h not in seen:
                seen.add(h)
                unique_headers.append(h)
        headers = unique_headers
        
        if len(headers) < 2:
            # Last resort: split by any whitespace
            headers = [h for h in header_line.split() if h.strip()]
        
        if not headers:
            return
            
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        
        # Set up header
        for col in range(len(headers)):
            table_widget.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
            )
            
        # Add data rows - use smart splitting
        for i in range(1, len(lines)):
            if not lines[i].strip():
                continue
                
            # Try to split intelligently
            row_data = self._smart_split_row(lines[i], len(headers))
            
            if not row_data or not any(row_data):
                continue
                
            # Pad or truncate to match header count
            while len(row_data) < len(headers):
                row_data.append("")
            row_data = row_data[:len(headers)]
                
            row_idx = table_widget.rowCount()
            table_widget.insertRow(row_idx)
            
            for col, data in enumerate(row_data):
                item = QTableWidgetItem(data.strip())
                table_widget.setItem(row_idx, col, item)
    
    def _refine_column_boundaries(self, initial_boundaries, sample_lines):
        """Refine column boundaries by analyzing data rows
        
        Args:
            initial_boundaries: Initial column boundary positions from header
            sample_lines: Sample data lines to analyze
            
        Returns:
            list: Refined column boundary positions
        """
        if len(initial_boundaries) < 2 or not sample_lines:
            return initial_boundaries
        
        # For each boundary position, check if data rows consistently have
        # text starting near that position
        refined = [initial_boundaries[0]]  # First boundary is always 0
        
        for boundary_idx in range(1, len(initial_boundaries)):
            boundary_pos = initial_boundaries[boundary_idx]
            
            # Check data rows to see where columns actually start
            column_starts = []
            for line in sample_lines[1:]:  # Skip header
                if boundary_pos < len(line):
                    # Look for where text starts near this boundary
                    # Check positions around the boundary
                    for offset in range(-2, 3):  # Check ±2 positions
                        check_pos = boundary_pos + offset
                        if 0 < check_pos < len(line):
                            if check_pos > 0 and line[check_pos-1] == ' ' and line[check_pos] != ' ':
                                column_starts.append(check_pos)
            
            # Use the most common start position
            if column_starts:
                # Count occurrences
                pos_counts = Counter(column_starts)
                most_common_pos = pos_counts.most_common(1)[0][0]
                refined.append(most_common_pos)
            else:
                # Keep original boundary
                refined.append(boundary_pos)
        
        return refined
    
    def _find_column_boundaries(self, lines):
        """Find column boundary positions by analyzing multiple rows
        
        Args:
            lines: List of text lines
            
        Returns:
            list: List of column start positions
        """
        if len(lines) < 2:
            return [0]
        
        # Strategy: Find positions where multiple rows have text starting after spaces
        # This indicates column alignment
        
        # First, find the maximum line length to analyze
        sample_lines = lines[:min(20, len(lines))]  # Analyze up to 20 rows
        max_line_length = max(len(line) for line in sample_lines) if sample_lines else 0
        
        if max_line_length == 0:
            return [0]
        
        # Track positions where columns start (space-to-text transitions)
        # Count how many rows have a column start at each position
        position_scores = {}
        
        for line in sample_lines:
            if not line.strip():
                continue
                
            # Find all positions where text starts (space before, non-space at)
            for pos in range(1, len(line)):
                if line[pos-1] == ' ' and line[pos] != ' ':
                    # This is a potential column start
                    # Check that there's at least one space before (not just a single space in a word)
                    spaces_before = 0
                    for i in range(max(0, pos-5), pos):
                        if line[i] == ' ':
                            spaces_before += 1
                        elif line[i] != ' ':
                            spaces_before = 0  # Reset if we hit non-space
                    
                    # If we have multiple spaces before, this is likely a column boundary
                    if spaces_before >= 1:
                        position_scores[pos] = position_scores.get(pos, 0) + 1
        
        # Also analyze the header line more carefully
        # Headers often have clear word boundaries
        header_line = lines[0]
        header_word_starts = [0]
        in_word = False
        for i in range(1, len(header_line)):
            if header_line[i-1] == ' ' and header_line[i] != ' ':
                # Potential word start
                if i - header_word_starts[-1] > 2:  # At least 2 chars from previous start
                    header_word_starts.append(i)
        
        # Combine header analysis with data row analysis
        # Positions that appear in both are very likely column boundaries
        col_candidates = set([0])  # First column always starts at 0
        
        # Add positions that score highly (appear in many rows)
        threshold = max(2, len(sample_lines) // 3)  # At least 1/3 of rows
        for pos, score in position_scores.items():
            if score >= threshold:
                col_candidates.add(pos)
        
        # Also add header word starts that are confirmed by data rows
        for pos in header_word_starts[1:]:  # Skip first (already added)
            if pos in position_scores and position_scores[pos] >= 2:
                col_candidates.add(pos)
        
        # Sort positions
        col_positions = sorted(col_candidates)
        
        # Filter: remove positions that are too close together
        # Use a dynamic threshold based on average column width
        if len(col_positions) > 1:
            avg_gap = (col_positions[-1] - col_positions[0]) / max(1, len(col_positions) - 1)
            min_gap = max(2, avg_gap * 0.3)  # At least 30% of average gap
            
            filtered_positions = [col_positions[0]]
            for pos in col_positions[1:]:
                if pos - filtered_positions[-1] >= min_gap:
                    filtered_positions.append(pos)
            
            # If we have a reasonable number of columns (2-20), return them
            if 2 <= len(filtered_positions) <= 20:
                return filtered_positions
        
        return [0]  # Fallback: couldn't determine columns
    
    def _smart_split_row(self, line, expected_columns):
        """Split a row intelligently to extract columns
        
        Args:
            line: The line to split
            expected_columns: Expected number of columns
            
        Returns:
            list: List of column values
        """
        # Strategy: look for patterns of spaces
        # Multiple spaces (2+) likely indicate column boundaries
        row_data = []
        
        # First, try splitting by 2+ spaces
        parts = line.split('  ')
        if len(parts) >= expected_columns:
            # This might work, but need to handle cases where single spaces exist within values
            result = []
            for part in parts:
                part = part.strip()
                if part:
                    # If part contains single spaces, it might be a single value
                    # or multiple values separated by single spaces
                    # For now, treat it as a single value
                    result.append(part)
            if len(result) >= expected_columns:
                return result[:expected_columns]
        
        # Fallback: split by any whitespace and try to group
        all_parts = line.split()
        if len(all_parts) >= expected_columns:
            return all_parts[:expected_columns]
        elif len(all_parts) > 0:
            # Pad with empty strings
            return all_parts + [''] * (expected_columns - len(all_parts))
        
        return []
    
    def _parse_tab_separated_table(self, lines, table_widget):
        """Parse tab-separated text into a table
        
        Args:
            lines: List of text lines
            table_widget: The table widget to populate
        """
        # Get headers (first line)
        headers = [h.strip() for h in lines[0].split('\t') if h.strip() or True]  # Include empty cells
        if not headers:
            return
            
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        
        # Set up header
        for col in range(len(headers)):
            table_widget.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
            )
        
        # Add data rows
        for i in range(1, len(lines)):
            if not lines[i].strip():
                continue
                
            row_data = [d.strip() for d in lines[i].split('\t')]
            # Pad or truncate to match header count
            while len(row_data) < len(headers):
                row_data.append("")
            row_data = row_data[:len(headers)]
            
            row_idx = table_widget.rowCount()
            table_widget.insertRow(row_idx)
            
            for col, data in enumerate(row_data):
                item = QTableWidgetItem(data)
                table_widget.setItem(row_idx, col, item)
    
    def _parse_csv_table(self, lines, table_widget):
        """Parse CSV-like (comma-separated) text into a table
        
        Args:
            lines: List of text lines
            table_widget: The table widget to populate
        """
        import csv
        from io import StringIO
        
        # Try to parse as CSV
        try:
            csv_reader = csv.reader(StringIO('\n'.join(lines)))
            rows = list(csv_reader)
            
            if not rows:
                return
                
            # First row is headers
            headers = [h.strip() for h in rows[0]]
            if not headers:
                return
                
            table_widget.setColumnCount(len(headers))
            table_widget.setHorizontalHeaderLabels(headers)
            
            # Set up header
            for col in range(len(headers)):
                table_widget.horizontalHeader().setSectionResizeMode(
                    col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
                )
            
            # Add data rows
            for row_data in rows[1:]:
                if not any(row_data):  # Skip empty rows
                    continue
                    
                # Pad or truncate to match header count
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                
                row_idx = table_widget.rowCount()
                table_widget.insertRow(row_idx)
                
                for col, data in enumerate(row_data):
                    item = QTableWidgetItem(str(data).strip())
                    table_widget.setItem(row_idx, col, item)
        except Exception as e:
            logger.warning(f"Failed to parse as CSV, trying simple split: {e}")
            # Fallback to simple comma split
            headers = [h.strip() for h in lines[0].split(',')]
            if not headers:
                return
                
            table_widget.setColumnCount(len(headers))
            table_widget.setHorizontalHeaderLabels(headers)
            
            for col in range(len(headers)):
                table_widget.horizontalHeader().setSectionResizeMode(
                    col, QHeaderView.ResizeToContents if col < len(headers) - 1 else QHeaderView.Stretch
                )
            
            for i in range(1, len(lines)):
                if not lines[i].strip():
                    continue
                    
                row_data = [d.strip() for d in lines[i].split(',')]
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                
                row_idx = table_widget.rowCount()
                table_widget.insertRow(row_idx)
                
                for col, data in enumerate(row_data):
                    item = QTableWidgetItem(data)
                    table_widget.setItem(row_idx, col, item)
    
    def _export_table_to_csv(self, file_path, output_text, device, cmd_text, timestamp):
        """Export a single table output to CSV file
        
        Args:
            file_path: Path to save the CSV file
            output_text: The output text to parse and export
            device: The device object
            cmd_text: The command text
            timestamp: The timestamp string
        """
        import csv
        
        # Parse the output into a table structure
        lines = [line.rstrip() for line in output_text.strip().split('\n') if line.strip()]
        if len(lines) < 2:
            # Not a table, export as text with metadata
            with open(file_path, "w", encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Device", device.get_property('alias', 'Device')])
                writer.writerow(["Command", cmd_text])
                writer.writerow(["Date/Time", datetime.datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                writer.writerow(["Output"])
                for line in lines:
                    writer.writerow([line])
            return
        
        # Determine table format and parse
        headers = []
        rows = []
        
        if '|' in lines[0]:
            # Pipe-separated
            header_parts = lines[0].split('|')
            headers = [h.strip() for h in header_parts]
            if headers and not headers[0]:
                headers = headers[1:]
            if headers and not headers[-1]:
                headers = headers[:-1]
            
            start_row = 1
            if len(lines) > 1:
                separator_line = lines[1].strip()
                if separator_line and all(c in '-+| ' for c in separator_line):
                    start_row = 2
            
            for i in range(start_row, len(lines)):
                if not lines[i].strip():
                    continue
                row_parts = lines[i].split('|')
                row_data = [d.strip() for d in row_parts]
                if row_data and not row_data[0]:
                    row_data = row_data[1:]
                if row_data and not row_data[-1]:
                    row_data = row_data[:-1]
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                rows.append(row_data)
        elif '\t' in lines[0]:
            # Tab-separated
            headers = [h.strip() for h in lines[0].split('\t')]
            for i in range(1, len(lines)):
                if not lines[i].strip():
                    continue
                row_data = [d.strip() for d in lines[i].split('\t')]
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                rows.append(row_data)
        elif ',' in lines[0] and lines[0].count(',') >= 2:
            # CSV-like
            import csv as csv_module
            from io import StringIO
            try:
                csv_reader = csv_module.reader(StringIO('\n'.join(lines)))
                all_rows = list(csv_reader)
                if all_rows:
                    headers = [h.strip() for h in all_rows[0]]
                    for row_data in all_rows[1:]:
                        while len(row_data) < len(headers):
                            row_data.append("")
                        row_data = row_data[:len(headers)]
                        rows.append(row_data)
            except:
                # Fallback to simple split
                headers = [h.strip() for h in lines[0].split(',')]
                for i in range(1, len(lines)):
                    if not lines[i].strip():
                        continue
                    row_data = [d.strip() for d in lines[i].split(',')]
                    while len(row_data) < len(headers):
                        row_data.append("")
                    row_data = row_data[:len(headers)]
                    rows.append(row_data)
        else:
            # Space-separated - use simple split by multiple spaces
            headers = [h for h in lines[0].split('  ') if h.strip()]
            for i in range(1, len(lines)):
                if not lines[i].strip():
                    continue
                row_data = [d.strip() for d in lines[i].split('  ') if d.strip()]
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                rows.append(row_data)
        
        # Write to CSV
        with open(file_path, "w", encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # Write metadata
            writer.writerow(["Device", device.get_property('alias', 'Device')])
            writer.writerow(["Command", cmd_text])
            writer.writerow(["Date/Time", datetime.datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            # Write headers
            if headers:
                writer.writerow(headers)
            # Write data rows
            for row in rows:
                writer.writerow(row)
    
    def _export_multiple_tables_to_csv(self, file_path, selected_commands, all_outputs, device):
        """Export multiple command outputs to a single CSV file
        
        Args:
            file_path: Path to save the CSV file
            selected_commands: List of (cmd_id, timestamp, cmd_text) tuples
            all_outputs: Dictionary of all outputs
            device: The device object
        """
        import csv
        
        with open(file_path, "w", encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            for cmd_id, timestamp, cmd_text in selected_commands:
                output_data = all_outputs[cmd_id][timestamp]
                output = output_data.get("output", "")
                
                # Write command header
                writer.writerow([])
                writer.writerow(["Command", cmd_text])
                writer.writerow(["Date/Time", datetime.datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                
                # Check if output can be displayed as table
                if self._can_display_as_table(output):
                    # Parse and write as table
                    lines = [line.rstrip() for line in output.strip().split('\n') if line.strip()]
                    if len(lines) >= 2:
                        # Determine format and parse (similar to _export_table_to_csv)
                        if '|' in lines[0]:
                            header_parts = lines[0].split('|')
                            headers = [h.strip() for h in header_parts]
                            if headers and not headers[0]:
                                headers = headers[1:]
                            if headers and not headers[-1]:
                                headers = headers[:-1]
                            
                            start_row = 1
                            if len(lines) > 1:
                                separator_line = lines[1].strip()
                                if separator_line and all(c in '-+| ' for c in separator_line):
                                    start_row = 2
                            
                            if headers:
                                writer.writerow(headers)
                            for i in range(start_row, len(lines)):
                                if not lines[i].strip():
                                    continue
                                row_parts = lines[i].split('|')
                                row_data = [d.strip() for d in row_parts]
                                if row_data and not row_data[0]:
                                    row_data = row_data[1:]
                                if row_data and not row_data[-1]:
                                    row_data = row_data[:-1]
                                while len(row_data) < len(headers):
                                    row_data.append("")
                                row_data = row_data[:len(headers)]
                                writer.writerow(row_data)
                        else:
                            # Simple space-separated
                            headers = [h for h in lines[0].split('  ') if h.strip()]
                            if headers:
                                writer.writerow(headers)
                            for i in range(1, len(lines)):
                                if not lines[i].strip():
                                    continue
                                row_data = [d.strip() for d in lines[i].split('  ') if d.strip()]
                                while len(row_data) < len(headers):
                                    row_data.append("")
                                row_data = row_data[:len(headers)]
                                writer.writerow(row_data)
                else:
                    # Write as text
                    writer.writerow(["Output"])
                    for line in output.split('\n'):
                        writer.writerow([line])
                
                writer.writerow([])
                writer.writerow(["=" * 80])
    
    def _export_to_html(self, file_path, output, device, cmd_text, timestamp):
        """Export a single output to HTML file
        
        Args:
            file_path: Path to save the HTML file
            output: The output text
            device: The device object
            cmd_text: The command text
            timestamp: The timestamp string
        """
        with open(file_path, "w", encoding='utf-8') as f:
            f.write("<html><head><title>Command Output</title></head><body>\n")
            f.write(f"<h1>Command Output</h1>\n")
            f.write(f"<p><strong>Device:</strong> {device.get_property('alias', 'Device')}</p>\n")
            f.write(f"<p><strong>Command:</strong> {cmd_text}</p>\n")
            f.write(f"<p><strong>Date/Time:</strong> {datetime.datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
            
            if self._can_display_as_table(output):
                f.write(self._output_to_html_table(output))
            else:
                f.write("<pre>\n")
                f.write(output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                f.write("\n</pre>\n")
            
            f.write("</body></html>")
    
    def _output_to_html_table(self, output_text):
        """Convert table output to HTML table format
        
        Args:
            output_text: The output text to convert
            
        Returns:
            str: HTML table string
        """
        lines = [line.rstrip() for line in output_text.strip().split('\n') if line.strip()]
        if len(lines) < 2:
            return f"<pre>{output_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</pre>"
        
        html = "<table border='1' cellpadding='5' cellspacing='0'>\n"
        
        # Parse headers
        if '|' in lines[0]:
            header_parts = lines[0].split('|')
            headers = [h.strip() for h in header_parts]
            if headers and not headers[0]:
                headers = headers[1:]
            if headers and not headers[-1]:
                headers = headers[:-1]
            
            start_row = 1
            if len(lines) > 1:
                separator_line = lines[1].strip()
                if separator_line and all(c in '-+| ' for c in separator_line):
                    start_row = 2
            
            html += "<thead><tr>"
            for header in headers:
                html += f"<th>{header.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</th>"
            html += "</tr></thead>\n<tbody>\n"
            
            for i in range(start_row, len(lines)):
                if not lines[i].strip():
                    continue
                row_parts = lines[i].split('|')
                row_data = [d.strip() for d in row_parts]
                if row_data and not row_data[0]:
                    row_data = row_data[1:]
                if row_data and not row_data[-1]:
                    row_data = row_data[:-1]
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                
                html += "<tr>"
                for cell in row_data:
                    html += f"<td>{cell.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</td>"
                html += "</tr>\n"
        else:
            # Space-separated
            headers = [h for h in lines[0].split('  ') if h.strip()]
            html += "<thead><tr>"
            for header in headers:
                html += f"<th>{header.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</th>"
            html += "</tr></thead>\n<tbody>\n"
            
            for i in range(1, len(lines)):
                if not lines[i].strip():
                    continue
                row_data = [d.strip() for d in lines[i].split('  ') if d.strip()]
                while len(row_data) < len(headers):
                    row_data.append("")
                row_data = row_data[:len(headers)]
                
                html += "<tr>"
                for cell in row_data:
                    html += f"<td>{cell.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</td>"
                html += "</tr>\n"
        
        html += "</tbody></table>\n"
        return html
        
    def generate_export_filename(self, device, command, command_text=None):
        """Generate a filename for exporting command output using template
        
        Args:
            device: The device to generate a filename for
            command: The command ID
            command_text: The actual command text (optional)
            
        Returns:
            str: The generated filename
        """
        template = self.plugin.settings["export_filename_template"]["value"]
        date_format = self.plugin.settings["export_date_format"]["value"]
        command_format = self.plugin.settings["export_command_format"]["value"]
        
        # Get the date formatted according to settings
        current_date = datetime.datetime.now().strftime(date_format)
        
        # Handle command formatting
        cmd_text = command_text or command
        if command_format == "truncated":
            # Replace spaces with hyphens and limit to 15 chars instead of truncating at first space
            cmd_text = cmd_text.replace(" ", "-")[:15]
        elif command_format == "sanitized":
            # Remove special characters, convert spaces to hyphens
            cmd_text = "".join(c if c.isalnum() or c == " " else "-" for c in cmd_text)
            cmd_text = cmd_text.replace(" ", "-").replace("--", "-").strip("-")[:25]  # Limit length and clean up
        else:  # "full" format - still replace spaces with hyphens for filename safety
            cmd_text = cmd_text.replace(" ", "-")
        
        # Create placeholder values
        placeholders = {
            "command": cmd_text,
            "date": current_date,
            "hostname": device.get_property("hostname", "unknown"),
            "ip": device.get_property("ip_address", "unknown"),
            "status": device.get_property("status", "unknown"),
        }
        
        # Add all device properties as potential placeholders
        for key, value in device.get_properties().items():
            # Only add simple values, not lists or dicts
            if isinstance(value, (str, int, float, bool)):
                placeholders[key] = str(value)
        
        # Apply the template
        try:
            filename = template.format(**placeholders)
            # Sanitize filename to remove characters that aren't allowed in filenames
            return self._sanitize_filename(filename)
        except KeyError as e:
            logger.error(f"Error in filename template: Unknown placeholder {e}")
            # Fallback to a simple filename
            return f"{device.get_property('hostname', 'device')}_{cmd_text}_{current_date}.txt"
        except Exception as e:
            logger.error(f"Error generating filename from template: {e}")
            # Fallback to a simple filename
            return f"command_output_{current_date}.txt"
    
    def _sanitize_filename(self, filename):
        """Sanitize a filename to remove illegal characters
        
        Args:
            filename (str): The filename to sanitize
            
        Returns:
            str: The sanitized filename
        """
        # Replace characters that are not allowed in filenames
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '-')
        
        # Replace spaces with hyphens for better filenames
        filename = filename.replace(' ', '-')
        
        # Clean up multiple consecutive hyphens
        while '--' in filename:
            filename = filename.replace('--', '-')
        
        # Ensure the filename is not too long
        if len(filename) > 240:  # Leave room for extension
            filename = filename[:240]
            
        # Remove any trailing hyphens
        filename = filename.rstrip('-')
            
        return filename
        