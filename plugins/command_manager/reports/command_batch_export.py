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
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QCheckBox, QListWidget,
    QDialogButtonBox, QLineEdit, QComboBox, QSplitter, QAbstractItemView,
    QProgressDialog, QApplication, QWidget, QListWidgetItem, QTabWidget,
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
        
        # Load targets (devices with outputs, groups, subnets)
        self._load_targets()
        
    def _create_ui(self):
        """Create the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create a splitter for better UI organization
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel (targets: devices, groups, or subnets)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.target_tabs = QTabWidget()

        # Devices tab
        device_tab = QWidget()
        device_tab_layout = QVBoxLayout(device_tab)
        device_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(2)
        self.device_table.setHorizontalHeaderLabels(["Device", "IP Address"])
        self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.MultiSelection)
        self.device_table.itemSelectionChanged.connect(self._on_target_selection_changed)
        device_tab_layout.addWidget(self.device_table)
        self.target_tabs.addTab(device_tab, "Devices")

        # Groups tab
        group_tab = QWidget()
        group_tab_layout = QVBoxLayout(group_tab)
        group_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.group_table = QTableWidget()
        self.group_table.setColumnCount(2)
        self.group_table.setHorizontalHeaderLabels(["Group Name", "Device Count"])
        self.group_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.group_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.group_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.group_table.setSelectionMode(QTableWidget.MultiSelection)
        self.group_table.itemSelectionChanged.connect(self._on_target_selection_changed)
        group_tab_layout.addWidget(self.group_table)
        self.target_tabs.addTab(group_tab, "Groups")

        # Subnets tab
        subnet_tab = QWidget()
        subnet_tab_layout = QVBoxLayout(subnet_tab)
        subnet_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.subnet_table = QTableWidget()
        self.subnet_table.setColumnCount(2)
        self.subnet_table.setHorizontalHeaderLabels(["Subnet", "Device Count"])
        self.subnet_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.subnet_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.subnet_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.subnet_table.setSelectionMode(QTableWidget.MultiSelection)
        self.subnet_table.itemSelectionChanged.connect(self._on_target_selection_changed)
        subnet_tab_layout.addWidget(self.subnet_table)
        self.target_tabs.addTab(subnet_tab, "Subnets")
        self.target_tabs.currentChanged.connect(self._on_target_selection_changed)

        left_layout.addWidget(self.target_tabs)
        
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
        
        self.preview_text = QLabel("Select devices/groups/subnets and commands to see export preview")
        self.preview_text.setAlignment(Qt.AlignCenter)
        _pal = self.preview_text.palette()
        self.preview_text.setStyleSheet(f"color: {_pal.color(QPalette.PlaceholderText).name()};")
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
        
    def _load_targets(self):
        """Load devices (with outputs), groups, and subnets into the target tabs."""
        devices = self.plugin.device_manager.get_devices() if self.plugin.device_manager else []

        self.device_table.setRowCount(0)
        self.device_commands.clear()

        for device in devices:
            alias = device.get_property("alias", "Unnamed Device")
            ip_address = device.get_property("ip_address", "")
            outputs = self.plugin.get_command_outputs(device.id)
            if not outputs:
                continue
            self.device_commands[device.id] = outputs
            row = self.device_table.rowCount()
            self.device_table.insertRow(row)
            alias_item = QTableWidgetItem(alias)
            alias_item.setData(Qt.UserRole, device.id)
            self.device_table.setItem(row, 0, alias_item)
            self.device_table.setItem(row, 1, QTableWidgetItem(ip_address))

        self._load_groups()
        self._load_subnets(devices)

    def _load_groups(self):
        """Populate the groups tab. Only shows groups that have at least one device with command outputs."""
        self.group_table.setRowCount(0)
        try:
            groups = self.plugin.device_manager.get_groups()
            devices_with_outputs_ids = set(self.device_commands.keys())
            for group in groups:
                name = None
                if isinstance(group, dict) and "name" in group:
                    name = group["name"]
                elif hasattr(group, "name"):
                    name = group.name
                elif hasattr(group, "get_name"):
                    name = group.get_name()
                else:
                    name = str(group)
                group_devices = []
                if hasattr(group, "get_all_devices"):
                    group_devices = group.get_all_devices()
                elif hasattr(group, "devices"):
                    group_devices = list(group.devices) if group.devices else []
                elif isinstance(group, dict) and "devices" in group:
                    for d in group["devices"]:
                        dev = self.plugin.device_manager.get_device(d) if isinstance(d, str) else d
                        if dev:
                            group_devices.append(dev)
                count = sum(1 for d in group_devices if getattr(d, "id", None) in devices_with_outputs_ids)
                if count == 0:
                    continue
                row = self.group_table.rowCount()
                self.group_table.insertRow(row)
                name_item = QTableWidgetItem(name)
                name_item.setData(Qt.UserRole, group)
                self.group_table.setItem(row, 0, name_item)
                self.group_table.setItem(row, 1, QTableWidgetItem(str(count)))
        except Exception as e:
            logger.error(f"Error loading groups for batch export: {e}")

    def _load_subnets(self, devices):
        """Populate the subnets tab from devices that have command outputs."""
        self.subnet_table.setRowCount(0)
        device_ids_with_outputs = set(self.device_commands.keys())
        subnets = {}
        for device in devices:
            if device.id not in device_ids_with_outputs:
                continue
            ip = device.get_property("ip_address", "") or ""
            parts = ip.split(".")
            if len(parts) != 4:
                continue
            try:
                int(parts[0])
                int(parts[1])
                int(parts[2])
            except (ValueError, IndexError):
                continue
            subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            if subnet not in subnets:
                subnets[subnet] = []
            subnets[subnet].append(device)
        for subnet, subnet_devices in subnets.items():
            row = self.subnet_table.rowCount()
            self.subnet_table.insertRow(row)
            subnet_item = QTableWidgetItem(subnet)
            subnet_item.setData(Qt.UserRole, {"subnet": subnet, "devices": subnet_devices})
            self.subnet_table.setItem(row, 0, subnet_item)
            self.subnet_table.setItem(row, 1, QTableWidgetItem(str(len(subnet_devices))))

    def _on_target_selection_changed(self, _tab_index=None):
        """Handle target (device/group/subnet) selection or tab change."""
        self.command_list.clear()
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
        """Get selected devices from the active tab (Devices, Groups, or Subnets)."""
        selected_devices = []
        tab = self.target_tabs.currentIndex()
        devices_with_outputs = set(self.device_commands.keys())

        if tab == 0:  # Devices
            for item in self.device_table.selectedItems():
                if item.column() == 0:
                    device_id = item.data(Qt.UserRole)
                    device = self.plugin.device_manager.get_device(device_id)
                    if device and device not in selected_devices:
                        selected_devices.append(device)
        elif tab == 1:  # Groups
            for item in self.group_table.selectedItems():
                if item.column() == 0:
                    group = item.data(Qt.UserRole)
                    if not group:
                        continue
                    group_devices = []
                    if hasattr(group, "get_all_devices"):
                        group_devices = group.get_all_devices()
                    elif hasattr(group, "devices"):
                        group_devices = list(group.devices) if group.devices else []
                    for device in group_devices:
                        if device and getattr(device, "id", None) in devices_with_outputs and device not in selected_devices:
                            selected_devices.append(device)
        elif tab == 2:  # Subnets
            for item in self.subnet_table.selectedItems():
                if item.column() == 0:
                    info = item.data(Qt.UserRole)
                    if not info or "devices" not in info:
                        continue
                    for device in info["devices"]:
                        if device and getattr(device, "id", None) in devices_with_outputs and device not in selected_devices:
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
        _pal = self.preview_text.palette()
        self.preview_text.setStyleSheet(f"color: {_pal.color(QPalette.Text).name()};")

    def _on_export(self):
        """Handle export button"""
        selected_devices = self._get_selected_devices()
        
        # Get selected commands
        selected_commands = []
        for item in self.command_list.selectedItems():
            cmd_id = item.data(Qt.UserRole)
            cmd_text = item.text()
            selected_commands.append((cmd_id, cmd_text))
        
        # Check if any targets (devices/groups/subnets) and commands are selected
        if not selected_devices:
            QMessageBox.warning(
                self,
                "No Targets Selected",
                "Please select one or more devices, groups, or subnets to export commands from."
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