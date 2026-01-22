#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command Batch Export Dialog for Command Manager plugin
"""

import os
import datetime
from pathlib import Path
from loguru import logger

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QCheckBox, QListWidget,
    QDialogButtonBox, QLineEdit, QComboBox, QSplitter, QAbstractItemView,
    QProgressDialog, QApplication, QWidget, QListWidgetItem
)

from src.ui.plugin_ui_theme import mark_plugin_ui

class CommandBatchExport(QDialog):
    """Dialog for exporting commands from multiple devices"""
    
    def __init__(self, plugin, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.plugin = plugin
        
        # Set dialog properties
        self.setWindowTitle("Export Commands from Multiple Devices")
        self.resize(800, 600)
        
        # Map of device_id -> list of available commands
        self.device_commands = {}
        
        # Create UI components
        self._create_ui()
        
        # Load devices
        self._load_devices()
        
    def _create_ui(self):
        """Create the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create a splitter for better UI organization
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel (devices)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Device selection section
        device_group = QGroupBox("Select Devices")
        device_layout = QVBoxLayout(device_group)
        
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(2)
        self.device_table.setHorizontalHeaderLabels(["Device", "IP Address"])
        self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.MultiSelection)
        self.device_table.itemSelectionChanged.connect(self._on_device_selection_changed)
        
        device_layout.addWidget(self.device_table)
        
        # Add device group to left panel
        left_layout.addWidget(device_group)
        
        # Right panel (commands & export options)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Command selection section
        command_group = QGroupBox("Select Commands to Export")
        command_layout = QVBoxLayout(command_group)
        
        self.command_list = QListWidget()
        self.command_list.setSelectionMode(QAbstractItemView.MultiSelection)
        command_layout.addWidget(self.command_list)
        
        # Placeholder text when no devices selected
        self.command_placeholder = QLabel("Select one or more devices to see available commands")
        self.command_placeholder.setAlignment(Qt.AlignCenter)
        self.command_placeholder.setStyleSheet("color: #888;")
        command_layout.addWidget(self.command_placeholder)
        
        # Add command group to right panel
        right_layout.addWidget(command_group)
        
        # Export options section
        options_group = QGroupBox("Export Options")
        options_layout = QFormLayout(options_group)
        
        # Filename template settings
        self.template_edit = QLineEdit(self.plugin.settings["export_filename_template"]["value"])
        options_layout.addRow("Filename Template:", self.template_edit)
        
        # Template help
        template_help = QLabel(
            "Available variables: {hostname}, {ip}, {command}, {date}, {status}, plus any device property"
        )
        template_help.setWordWrap(True)
        options_layout.addRow("", template_help)
        
        # Date format
        self.date_format_edit = QLineEdit(self.plugin.settings["export_date_format"]["value"])
        options_layout.addRow("Date Format:", self.date_format_edit)
        
        # Command format
        self.command_format_combo = QComboBox()
        self.command_format_combo.addItems(["truncated", "full", "sanitized"])
        index = self.command_format_combo.findText(self.plugin.settings["export_command_format"]["value"])
        if index >= 0:
            self.command_format_combo.setCurrentIndex(index)
        options_layout.addRow("Command Format:", self.command_format_combo)
        
        # Save settings
        self.save_settings_cb = QCheckBox("Save these settings as default")
        options_layout.addRow("", self.save_settings_cb)
        
        # Include most recent only
        self.most_recent_only = QCheckBox("Export most recent output only")
        self.most_recent_only.setChecked(True)
        options_layout.addRow("", self.most_recent_only)
        
        # Add options group to right panel
        right_layout.addWidget(options_group)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Add splitter to main layout
        layout.addWidget(splitter)
        
        # Preview section
        preview_group = QGroupBox("Export Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QLabel("Select devices and commands to see export preview")
        self.preview_text.setAlignment(Qt.AlignCenter)
        self.preview_text.setStyleSheet("color: #888;")
        self.preview_text.setWordWrap(True)
        preview_layout.addWidget(self.preview_text)
        
        # Preview button
        preview_button = QPushButton("Generate Preview")
        preview_button.clicked.connect(self._update_preview)
        preview_layout.addWidget(preview_button)
        
        # Add preview group to main layout
        layout.addWidget(preview_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_export)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
        
    def _load_devices(self):
        """Load device list"""
        # Get all devices
        devices = self.plugin.device_manager.get_devices()
        
        # Add devices to table
        for device in devices:
            alias = device.get_property("alias", "Unnamed Device")
            ip_address = device.get_property("ip_address", "")
            
            # Skip devices without command outputs
            outputs = self.plugin.get_command_outputs(device.id)
            if not outputs:
                continue
                
            # Store available commands for this device
            self.device_commands[device.id] = outputs
                
            row = self.device_table.rowCount()
            self.device_table.insertRow(row)
            
            # Device info
            alias_item = QTableWidgetItem(alias)
            alias_item.setData(Qt.UserRole, device.id)
            
            ip_item = QTableWidgetItem(ip_address)
            
            # Add to table
            self.device_table.setItem(row, 0, alias_item)
            self.device_table.setItem(row, 1, ip_item)
    
    def _on_device_selection_changed(self):
        """Handle device selection change"""
        self.command_list.clear()
        
        # Get selected devices
        selected_devices = self._get_selected_devices()
        
        if not selected_devices:
            self.command_placeholder.setVisible(True)
            self.command_list.setVisible(False)
            return
        
        self.command_placeholder.setVisible(False)
        self.command_list.setVisible(True)
        
        # Find common commands across all selected devices
        common_commands = {}
        
        for idx, device in enumerate(selected_devices):
            # Get all available commands for this device
            if device.id not in self.device_commands:
                continue
                
            device_cmd_outputs = self.device_commands[device.id]
            
            # First device, add all commands
            if idx == 0:
                for cmd_id, timestamps in device_cmd_outputs.items():
                    # Get the most recent output
                    latest_timestamp = max(timestamps.keys())
                    cmd_data = timestamps[latest_timestamp]
                    cmd_text = cmd_data.get("command", cmd_id)
                    
                    common_commands[cmd_id] = cmd_text
            else:
                # Keep only commands that exist in this device
                for cmd_id in list(common_commands.keys()):
                    if cmd_id not in device_cmd_outputs:
                        del common_commands[cmd_id]
        
        # Add common commands to the list
        for cmd_id, cmd_text in common_commands.items():
            item = QListWidgetItem(cmd_text)
            item.setData(Qt.UserRole, cmd_id)
            self.command_list.addItem(item)
            
        # Update preview
        self._update_preview()
        
    def _get_selected_devices(self):
        """Get selected devices"""
        selected_devices = []
        for item in self.device_table.selectedItems():
            # Make sure we only count each row once
            if item.column() == 0:
                device_id = item.data(Qt.UserRole)
                device = self.plugin.device_manager.get_device(device_id)
                if device and device not in selected_devices:
                    selected_devices.append(device)
        return selected_devices
        
    def _update_preview(self):
        """Update the export preview"""
        selected_devices = self._get_selected_devices()
        
        # Get selected commands
        selected_commands = []
        for item in self.command_list.selectedItems():
            cmd_id = item.data(Qt.UserRole)
            cmd_text = item.text()
            selected_commands.append((cmd_id, cmd_text))
        
        if not selected_devices or not selected_commands:
            self.preview_text.setText("Select devices and commands to see export preview")
            self.preview_text.setStyleSheet("color: #888;")
            return
        
        # Create temporary plugin for preview
        class TempPlugin:
            def __init__(self, settings):
                self.settings = settings
        
        temp_settings = {
            "export_filename_template": {"value": self.template_edit.text()},
            "export_date_format": {"value": self.date_format_edit.text()},
            "export_command_format": {"value": self.command_format_combo.currentText()}
        }
        
        temp_plugin = TempPlugin(temp_settings)
        
        # Generate preview
        from plugins.command_manager.core.output_handler import OutputHandler
        temp_handler = OutputHandler(temp_plugin)
        
        preview_text = f"<b>Export Preview</b><br><br>"
        preview_text += f"Selected {len(selected_devices)} device(s) and {len(selected_commands)} command(s)<br><br>"
        preview_text += "Sample filenames:<br>"
        
        # Show up to 3 devices and 3 commands
        max_devices = min(3, len(selected_devices))
        max_commands = min(3, len(selected_commands))
        
        for i in range(max_devices):
            device = selected_devices[i]
            preview_text += f"<b>{device.get_property('alias', 'Device')}</b>:<br>"
            
            for j in range(max_commands):
                cmd_id, cmd_text = selected_commands[j]
                
                filename = temp_handler.generate_export_filename(device, cmd_id, cmd_text)
                if not filename.lower().endswith('.txt'):
                    filename += ".txt"
                    
                preview_text += f"&nbsp;&nbsp;• {cmd_text} → <code>{filename}</code><br>"
            
            if i < max_devices - 1:
                preview_text += "<br>"
        
        if len(selected_devices) > 3 or len(selected_commands) > 3:
            preview_text += "<br>... and more"
            
        self.preview_text.setText(preview_text)
        self.preview_text.setStyleSheet("color: #000;")
        
    def _on_export(self):
        """Handle export button"""
        selected_devices = self._get_selected_devices()
        
        # Get selected commands
        selected_commands = []
        for item in self.command_list.selectedItems():
            cmd_id = item.data(Qt.UserRole)
            cmd_text = item.text()
            selected_commands.append((cmd_id, cmd_text))
        
        # Check if any devices and commands are selected
        if not selected_devices:
            QMessageBox.warning(
                self,
                "No Devices Selected",
                "Please select one or more devices to export commands from."
            )
            return
            
        if not selected_commands:
            QMessageBox.warning(
                self,
                "No Commands Selected",
                "Please select one or more commands to export."
            )
            return
            
        # Ask for directory to save files
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Export Directory",
            ""
        )
        
        if not export_dir:
            return
            
        # Save settings if requested
        if self.save_settings_cb.isChecked():
            self.plugin.settings["export_filename_template"]["value"] = self.template_edit.text()
            self.plugin.settings["export_date_format"]["value"] = self.date_format_edit.text()
            self.plugin.settings["export_command_format"]["value"] = self.command_format_combo.currentText()
            
        # Create temporary plugin for export
        class TempPlugin:
            def __init__(self, settings):
                self.settings = settings
        
        temp_settings = {
            "export_filename_template": {"value": self.template_edit.text()},
            "export_date_format": {"value": self.date_format_edit.text()},
            "export_command_format": {"value": self.command_format_combo.currentText()}
        }
        
        temp_plugin = TempPlugin(temp_settings)
        
        # Create handler for filename generation
        from plugins.command_manager.core.output_handler import OutputHandler
        temp_handler = OutputHandler(temp_plugin)
            
        # Setup progress dialog
        total_exports = len(selected_devices) * len(selected_commands)
        progress = QProgressDialog("Exporting commands...", "Cancel", 0, total_exports, self)
        progress.setWindowTitle("Export Progress")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        # Export each command for each device
        exported_count = 0
        exported_files = []
        
        try:
            for device in selected_devices:
                device_id = device.id
                
                if device_id not in self.device_commands:
                    continue
                    
                device_cmd_outputs = self.device_commands[device_id]
                
                for cmd_id, cmd_text in selected_commands:
                    # Check if the user canceled the export
                    if progress.wasCanceled():
                        break
                        
                    # Update progress
                    progress.setValue(exported_count)
                    progress.setLabelText(f"Exporting: {device.get_property('alias', 'Device')} - {cmd_text}")
                    QApplication.processEvents()
                    
                    if cmd_id not in device_cmd_outputs:
                        exported_count += 1
                        continue
                        
                    # Get command output
                    cmd_outputs = device_cmd_outputs[cmd_id]
                    
                    if not cmd_outputs:
                        exported_count += 1
                        continue
                        
                    # Either export most recent or all
                    if self.most_recent_only.isChecked():
                        # Get most recent output
                        latest_timestamp = max(cmd_outputs.keys())
                        output_data = cmd_outputs[latest_timestamp]
                        output = output_data.get("output", "")
                        
                        # Generate filename
                        filename = temp_handler.generate_export_filename(device, cmd_id, cmd_text)
                        if not filename.lower().endswith('.txt'):
                            filename += ".txt"
                            
                        # Full path
                        file_path = os.path.join(export_dir, filename)
                        
                        # If file exists, add a number suffix to avoid overwriting
                        counter = 1
                        original_path = file_path
                        while os.path.exists(file_path):
                            file_name, file_ext = os.path.splitext(original_path)
                            file_path = f"{file_name}_{counter}{file_ext}"
                            counter += 1
                        
                        # Export to file
                        with open(file_path, "w") as f:
                            f.write(f"Device: {device.get_property('alias', 'Device')}\n")
                            f.write(f"IP: {device.get_property('ip_address', '')}\n")
                            f.write(f"Command: {cmd_text}\n")
                            f.write(f"Date/Time: {datetime.datetime.fromisoformat(latest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write("-" * 50 + "\n")
                            f.write(output)
                        
                        exported_count += 1
                        exported_files.append(os.path.basename(file_path))
                    else:
                        # Export all outputs for this command
                        for timestamp, output_data in cmd_outputs.items():
                            output = output_data.get("output", "")
                            
                            # Format timestamp for filename
                            dt = datetime.datetime.fromisoformat(timestamp)
                            timestamp_str = dt.strftime("%Y%m%d_%H%M%S")
                            
                            # Generate filename
                            filename = temp_handler.generate_export_filename(device, cmd_id, cmd_text)
                            file_name, file_ext = os.path.splitext(filename)
                            filename = f"{file_name}_{timestamp_str}{file_ext or '.txt'}"
                            
                            # Full path
                            file_path = os.path.join(export_dir, filename)
                            
                            # If file exists, add a number suffix to avoid overwriting
                            counter = 1
                            original_path = file_path
                            while os.path.exists(file_path):
                                file_name, file_ext = os.path.splitext(original_path)
                                file_path = f"{file_name}_{counter}{file_ext}"
                                counter += 1
                            
                            # Export to file
                            with open(file_path, "w") as f:
                                f.write(f"Device: {device.get_property('alias', 'Device')}\n")
                                f.write(f"IP: {device.get_property('ip_address', '')}\n")
                                f.write(f"Command: {cmd_text}\n")
                                f.write(f"Date/Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
                                f.write("-" * 50 + "\n")
                                f.write(output)
                            
                            exported_count += 1
                            exported_files.append(os.path.basename(file_path))
                
                # Check if the user canceled the export
                if progress.wasCanceled():
                    break
            
            # Complete the progress
            progress.setValue(total_exports)
            
            # Show success message with exported filenames
            if exported_count > 0:
                files_list = "\n".join(exported_files[:5])
                if len(exported_files) > 5:
                    files_list += f"\n... and {len(exported_files) - 5} more"
                    
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {exported_count} command outputs to {export_dir}\n\nFiles:\n{files_list}"
                )
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Failed to export any commands."
                )
        except Exception as e:
            logger.error(f"Error during batch export: {e}")
            QMessageBox.critical(
                self,
                "Export Error",
                f"An error occurred during export: {str(e)}"
            )
        finally:
            progress.close() 