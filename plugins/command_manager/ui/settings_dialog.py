#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Settings dialog for Command Manager plugin
"""

import os
import datetime
from pathlib import Path
from loguru import logger

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QGroupBox, QFormLayout, QTabWidget,
    QTextEdit, QMessageBox
)
from PySide6.QtGui import QFont

from src.ui.plugin_ui_theme import mark_plugin_ui


class SettingsDialog(QDialog):
    """Settings dialog for Command Manager plugin"""
    
    def __init__(self, plugin, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.plugin = plugin
        self.setWindowTitle("Command Manager Settings")
        self.resize(600, 400)
        
        # Create UI components
        self._create_ui()
        
        # Load current settings
        self._load_settings()
        
    def _create_ui(self):
        """Create the dialog UI"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create Export Settings tab
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        
        export_group = QGroupBox("Export Filename Settings")
        export_form = QFormLayout(export_group)
        
        # Filename template
        self.template_edit = QLineEdit()
        export_form.addRow("Filename Template:", self.template_edit)
        
        # Template help text
        template_help = QLabel(
            "Available variables: {hostname}, {ip}, {command}, {date}, {status}, "
            "plus any device property.\nExample: {hostname}_{command}_{date}.txt"
        )
        template_help.setWordWrap(True)
        export_form.addRow("", template_help)
        
        # Date format
        self.date_format_edit = QLineEdit()
        export_form.addRow("Date Format:", self.date_format_edit)
        
        # Date format help
        date_help = QLabel(
            "Python strftime format, e.g. %Y%m%d for 20230401, %Y-%m-%d for 2023-04-01"
        )
        date_help.setWordWrap(True)
        export_form.addRow("", date_help)
        
        # Command format
        self.command_format_combo = QComboBox()
        self.command_format_combo.addItems(["truncated", "full", "sanitized"])
        export_form.addRow("Command Format:", self.command_format_combo)
        
        # Command format help
        command_help = QLabel(
            "- truncated: first word or 15 chars\n"
            "- full: complete command text\n"
            "- sanitized: replace special chars with hyphens, limit to 25 chars"
        )
        command_help.setWordWrap(True)
        export_form.addRow("", command_help)
        
        # Preview section
        preview_group = QGroupBox("Filename Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        # Update button
        preview_button = QPushButton("Generate Preview")
        preview_button.clicked.connect(self._update_preview)
        preview_layout.addWidget(preview_button)
        
        # Preview label
        self.preview_label = QLabel("Enter values and click 'Generate Preview'")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("font-family: monospace; padding: 5px; border: 1px solid #ccc; background-color: #f9f9f9;")
        self.preview_label.setMinimumHeight(80)
        preview_layout.addWidget(self.preview_label)
        
        # Add groups to layout
        export_layout.addWidget(export_group)
        export_layout.addWidget(preview_group)
        export_layout.addStretch()
        
        # Add tab
        self.tab_widget.addTab(export_tab, "Export Settings")
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_settings)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        
    def _load_settings(self):
        """Load current settings into the dialog"""
        # Get settings from plugin
        settings = self.plugin.settings
        
        # Set export filename settings
        self.template_edit.setText(settings["export_filename_template"]["value"])
        self.date_format_edit.setText(settings["export_date_format"]["value"])
        
        # Set command format
        index = self.command_format_combo.findText(settings["export_command_format"]["value"])
        if index >= 0:
            self.command_format_combo.setCurrentIndex(index)
            
    def _save_settings(self):
        """Save settings to the plugin"""
        # Get values from UI
        template = self.template_edit.text()
        date_format = self.date_format_edit.text()
        command_format = self.command_format_combo.currentText()
        
        # Validate template
        if not template:
            QMessageBox.warning(
                self,
                "Invalid Settings",
                "Filename template cannot be empty"
            )
            return
            
        # Validate date format
        try:
            datetime.datetime.now().strftime(date_format)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Invalid Settings",
                f"Invalid date format: {e}"
            )
            return
            
        # Update plugin settings
        self.plugin.settings["export_filename_template"]["value"] = template
        self.plugin.settings["export_date_format"]["value"] = date_format
        self.plugin.settings["export_command_format"]["value"] = command_format
        
        # Close dialog
        self.accept()
        
    def _update_preview(self):
        """Update the filename preview"""
        # Get settings from dialog
        template = self.template_edit.text()
        date_format = self.date_format_edit.text()
        command_format = self.command_format_combo.currentText()
        
        # Create sample device properties
        properties = {
            "hostname": "SAMPLE-SWITCH",
            "ip_address": "192.168.1.1",
            "alias": "Sample Switch",
            "status": "active",
            "mac_address": "00:11:22:33:44:55",
            "location": "Server Room",
            "model": "SampleModel-2000"
        }
        
        # Sample commands
        commands = [
            ("show running-config", "show running-config"),
            ("show interface status", "show interface status"),
            ("show version", "show version")
        ]
        
        # Try to generate some previews
        preview_text = "Preview examples:\n\n"
        
        from plugins.command_manager.core.output_handler import OutputHandler
        
        class MockDevice:
            def __init__(self, props):
                self.props = props
                
            def get_property(self, key, default=None):
                return self.props.get(key, default)
                
            def get_properties(self):
                return self.props
                
        mock_device = MockDevice(properties)
        
        # Create a temporary handler
        class MockPlugin:
            def __init__(self):
                self.settings = {
                    "export_filename_template": {"value": template},
                    "export_date_format": {"value": date_format},
                    "export_command_format": {"value": command_format}
                }
                
        mock_plugin = MockPlugin()
        handler = OutputHandler(mock_plugin)
        
        # Generate previews
        for cmd_id, cmd_text in commands:
            try:
                filename = handler.generate_export_filename(mock_device, cmd_id, cmd_text)
                if not filename.lower().endswith('.txt'):
                    filename += ".txt"
                preview_text += f"{cmd_text} → {filename}\n"
            except Exception as e:
                preview_text += f"{cmd_text} → ERROR: {str(e)}\n"
        
        # Update preview label
        self.preview_label.setText(preview_text) 