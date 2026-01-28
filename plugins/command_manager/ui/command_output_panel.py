#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command Output Panel for Command Manager plugin
"""

import os
import json
import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QSortFilterProxyModel, QDateTime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QSplitter, QTextEdit, QMenu, QFileDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, QLineEdit, QGroupBox, QCheckBox
)
from PySide6.QtGui import QAction, QIcon, QFont, QPalette

from src.ui.plugin_ui_theme import mark_plugin_ui


class CommandOutputPanel(QWidget):
    """Panel for displaying command outputs"""
    
    def __init__(self, plugin, device=None, parent=None):
        """Initialize the panel"""
        super().__init__(parent)
        
        self.plugin = plugin
        self.device = device
        
        # Create UI components
        self._create_ui()
        
        # Set up initial state
        if device:
            self.set_device(device)
            
    def _create_ui(self):
        """Create the panel UI"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Output table
        self.output_table = QTableWidget()
        self.output_table.setColumnCount(4)
        self.output_table.setHorizontalHeaderLabels(["Command", "Timestamp", "View", "Delete"])
        self.output_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.output_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.output_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.output_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        # Button bar
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        
        self.export_all_btn = QPushButton("Export All")
        self.export_all_btn.clicked.connect(self._on_export_all)
        
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.export_all_btn)
        button_layout.addStretch()
        
        # Add to main layout
        layout.addWidget(self.output_table)
        layout.addLayout(button_layout)
        
    def set_device(self, device):
        """Set the device for this panel"""
        self.device = device
        
        # Refresh the output list
        self.refresh()
            
    def refresh(self):
        """Refresh the output list"""
        # Clear output table
        self.output_table.setRowCount(0)
        
        # If no device is set, return
        if not self.device:
            return
            
        # Get outputs for the device
        outputs = self.plugin.get_command_outputs(self.device.id)
        
        # Add entries to table
        row = 0
        for command_id, timestamps in outputs.items():
            # Get the latest output for each command
            latest_ts = max(timestamps.keys())
            data = timestamps[latest_ts]
            
            # Extract data
            command_text = data.get("command", command_id)
            output_text = data.get("output", "")
            dt = datetime.datetime.fromisoformat(latest_ts)
            
            # Add row
            self.output_table.insertRow(row)
            
            # Add items
            cmd_item = QTableWidgetItem(command_text)
            date_item = QTableWidgetItem(dt.strftime("%Y-%m-%d %H:%M:%S"))
            
            view_btn = QPushButton("View")
            view_btn.setProperty("command_id", command_id)
            view_btn.setProperty("timestamp", latest_ts)
            view_btn.clicked.connect(self._on_view_output)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setProperty("command_id", command_id)
            delete_btn.setProperty("timestamp", latest_ts)
            delete_btn.clicked.connect(self._on_delete_output)
            
            # Set items in row
            self.output_table.setItem(row, 0, cmd_item)
            self.output_table.setItem(row, 1, date_item)
            self.output_table.setCellWidget(row, 2, view_btn)
            self.output_table.setCellWidget(row, 3, delete_btn)
            
            row += 1
        
    def _on_view_output(self):
        """Handle view output button click"""
        sender = self.sender()
        if not sender:
            return
            
        command_id = sender.property("command_id")
        timestamp = sender.property("timestamp")
        
        if not command_id or not timestamp:
            return
            
        # Get output data
        outputs = self.plugin.get_command_outputs(self.device.id, command_id)
        if timestamp not in outputs:
            return
            
        output_data = outputs[timestamp]
        command_text = output_data.get("command", command_id)
        output_text = output_data.get("output", "")
        
        # Show output dialog
        dialog = QDialog(self)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle(f"Command Output: {command_text}")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Output text
        output_edit = QTextEdit()
        output_edit.setReadOnly(True)
        output_edit.setFont(QFont("Courier New", 10))
        output_edit.setText(output_text)
        
        # Export button
        button_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(lambda: self._export_single_output(command_id, timestamp))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        
        button_layout.addWidget(export_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addWidget(output_edit)
        layout.addLayout(button_layout)
        
        dialog.exec()
        
    def _on_delete_output(self):
        """Handle delete output button click"""
        sender = self.sender()
        if not sender:
            return
            
        command_id = sender.property("command_id")
        timestamp = sender.property("timestamp")
        
        if not command_id or not timestamp:
            return
            
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this command output?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete the output
        if self.plugin.delete_command_output(self.device.id, command_id, timestamp):
            # Refresh the panel
            self.refresh()
        else:
            QMessageBox.warning(
                self,
                "Delete Failed",
                "Failed to delete the command output."
            )
            
    def _export_single_output(self, command_id, timestamp):
        """Export a single command output to a file"""
        # Get output data
        outputs = self.plugin.get_command_outputs(self.device.id, command_id)
        if timestamp not in outputs:
            return
            
        output_data = outputs[timestamp]
        command_text = output_data.get("command", command_id)
        output_text = output_data.get("output", "")
        
        # Create a dialog to customize the export filename
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
            QGroupBox, QLabel, QHBoxLayout, QTextEdit, QPushButton, QCheckBox
        )
        
        template_dialog = QDialog(self)
        mark_plugin_ui(template_dialog)
        template_dialog.setWindowTitle(f"Export: {command_text}")
        template_dialog.resize(500, 400)
        
        layout = QVBoxLayout(template_dialog)
        
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
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        # Preview button
        preview_button = QPushButton("Update Preview")
        preview_layout.addWidget(preview_button)
        
        # Preview label
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setMaximumHeight(60)
        preview_layout.addWidget(preview_text)
        
        # Function to update the preview
        def update_preview():
            # Create a temporary handler with the current settings
            class TempPlugin:
                def __init__(self):
                    self.settings = {
                        "export_filename_template": {"value": template_edit.text()},
                        "export_date_format": {"value": date_format_edit.text()},
                        "export_command_format": {"value": command_format_combo.currentText()}
                    }
            
            temp_plugin = TempPlugin()
            from plugins.command_manager.core.output_handler import OutputHandler
            temp_handler = OutputHandler(temp_plugin)
            
            # Generate filename
            filename = temp_handler.generate_export_filename(self.device, command_id, command_text)
            if not filename.lower().endswith('.txt'):
                filename += ".txt"
                
            preview_text.setPlainText(f"Preview:\n{filename}")
            
            return filename
            
        # Connect preview button
        preview_button.clicked.connect(update_preview)
        
        # Add checkbox to save settings
        save_settings_cb = QCheckBox("Save these settings as default")
        preview_layout.addWidget(save_settings_cb)
        
        # Add groups to layout
        layout.addWidget(template_group)
        layout.addWidget(preview_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        cancel_btn = QPushButton("Cancel")
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)
        
        # Connect buttons
        cancel_btn.clicked.connect(template_dialog.reject)
        export_btn.clicked.connect(template_dialog.accept)
        
        # Generate initial preview
        filename = update_preview()
        
        # Show dialog
        if not template_dialog.exec():
            return
            
        # Save settings if requested
        if save_settings_cb.isChecked():
            self.plugin.settings["export_filename_template"]["value"] = template_edit.text()
            self.plugin.settings["export_date_format"]["value"] = date_format_edit.text()
            self.plugin.settings["export_command_format"]["value"] = command_format_combo.currentText()
        
        # Create a temporary handler with the current dialog settings
        class TempPlugin:
            def __init__(self):
                self.settings = {
                    "export_filename_template": {"value": template_edit.text()},
                    "export_date_format": {"value": date_format_edit.text()},
                    "export_command_format": {"value": command_format_combo.currentText()}
                }
                
        temp_plugin = TempPlugin()
        from plugins.command_manager.core.output_handler import OutputHandler
        temp_handler = OutputHandler(temp_plugin)
        
        # Generate filename
        filename = temp_handler.generate_export_filename(self.device, command_id, command_text)
        if not filename.lower().endswith('.txt'):
            filename += ".txt"
        
        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Command Output",
            filename,
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        # Save output to file
        try:
            with open(file_path, "w") as f:
                f.write(f"Command: {command_text}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Device: {self.device.get_property('alias', 'device')}\n")
                f.write("-" * 80 + "\n\n")
                f.write(output_text)
                
            QMessageBox.information(
                self,
                "Export Successful",
                f"Output exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export output: {str(e)}"
            )
            
    def _on_export_all(self):
        """Export all command outputs for the device"""
        # Use the plugin's output_handler to export all device commands
        # This will use the template-based filenames and support multi-command export
        if hasattr(self.plugin, 'output_handler') and self.plugin.output_handler:
            self.plugin.output_handler._export_device_commands(self.device)
        else:
            # Fallback to legacy export method
            self._legacy_export_all()
            
    def _legacy_export_all(self):
        """Export all command outputs for the device using legacy method"""
        if not self.device:
            return
            
        # Create suggested filename
        device_name = self.device.get_property("alias", "device")
        filename = f"{device_name}_all_commands.txt"
        filename = ''.join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])
        
        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All Command Outputs",
            filename,
            "Text Files (*.txt);;HTML Files (*.html);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        # Get all outputs for the device
        all_outputs = self.plugin.get_command_outputs(self.device.id)
        if not all_outputs:
            QMessageBox.warning(
                self,
                "No Outputs",
                "No command outputs available for this device."
            )
            return
            
        # Save outputs to file
        try:
            # Determine export format
            if file_path.lower().endswith(".html"):
                self._export_all_html(file_path, all_outputs)
            else:
                self._export_all_text(file_path, all_outputs)
                
            QMessageBox.information(
                self,
                "Export Successful",
                f"All outputs exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export outputs: {str(e)}"
            )
            
    def _export_all_text(self, file_path, all_outputs):
        """Export all outputs to a text file"""
        device_name = self.device.get_property("alias", "device")
        
        with open(file_path, "w") as f:
            f.write(f"Command Outputs for {device_name}\n")
            f.write("=" * 80 + "\n\n")
            
            for command_id, outputs in all_outputs.items():
                for timestamp, output_data in sorted(outputs.items(), reverse=True):
                    command_text = output_data.get("command", command_id)
                    output_text = output_data.get("output", "")
                    
                    # Format timestamp
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp)
                        friendly_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        friendly_time = timestamp
                    
                    f.write(f"Command: {command_text}\n")
                    f.write(f"Timestamp: {friendly_time}\n")
                    f.write("-" * 80 + "\n")
                    f.write(output_text)
                    f.write("\n\n" + "=" * 80 + "\n\n")
                    
    def _export_all_html(self, file_path, all_outputs):
        """Export all outputs to an HTML file (colors from palette for theme consistency)."""
        device_name = self.device.get_property("alias", "device")
        win = getattr(self.plugin, "main_window", None) if self.plugin else None
        pal = win.palette() if win else self.palette()
        text_c = pal.color(QPalette.Text).name()
        base_c = pal.color(QPalette.Base).name()
        border_c = pal.color(QPalette.Mid).name()
        muted_c = pal.color(QPalette.PlaceholderText).name()
        with open(file_path, "w") as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>Command Outputs for {device_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; color: {text_c}; }}
        h1 {{ color: {text_c}; }}
        h2 {{ color: {text_c}; }}
        pre {{ background-color: {base_c}; padding: 10px; border: 1px solid {border_c}; overflow-x: auto; }}
        .command {{ margin-bottom: 30px; }}
        .timestamp {{ color: {muted_c}; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Command Outputs for {device_name}</h1>
""")
            
            for command_id, outputs in all_outputs.items():
                for timestamp, output_data in sorted(outputs.items(), reverse=True):
                    command_text = output_data.get("command", command_id)
                    output_text = output_data.get("output", "")
                    
                    # Format timestamp
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp)
                        friendly_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        friendly_time = timestamp
                    
                    f.write(f"""    <div class="command">
        <h2>{command_text}</h2>
        <p class="timestamp">Timestamp: {friendly_time}</p>
        <pre>{output_text}</pre>
    </div>
""")
            
            f.write("</body>\n</html>") 