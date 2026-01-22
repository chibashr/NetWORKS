#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command Set Editor for Command Manager plugin
"""

import os
import json
import copy

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QLineEdit, QTextEdit, QDialogButtonBox, QSplitter,
    QTabWidget, QWidget, QMessageBox, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QMenu, QFileDialog
)
from PySide6.QtGui import QIcon, QAction

from ..utils.command_set import CommandSet, Command
from src.ui.plugin_ui_theme import mark_plugin_ui


class CommandDialog(QDialog):
    """Dialog for editing a command"""
    
    def __init__(self, command=None, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.command = command or Command("", "", "")
        
        # Set dialog properties
        self.setWindowTitle("Edit Command")
        self.resize(400, 300)
        
        # Create UI components
        self._create_ui()
        
    def _create_ui(self):
        """Create the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        # Command fields
        self.alias = QLineEdit(self.command.alias)
        form.addRow("Alias:", self.alias)
        
        self.command_text = QLineEdit(self.command.command)
        form.addRow("Command:", self.command_text)
        
        self.description = QTextEdit(self.command.description)
        form.addRow("Description:", self.description)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
        
    def _on_accept(self):
        """Handle dialog acceptance"""
        # Validate input
        alias = self.alias.text().strip()
        command_text = self.command_text.text().strip()
        description = self.description.toPlainText().strip()
        
        if not alias:
            QMessageBox.warning(self, "Missing Alias", "Please enter a command alias.")
            return
            
        if not command_text:
            QMessageBox.warning(self, "Missing Command", "Please enter a command.")
            return
            
        # Update command
        self.command.alias = alias
        self.command.command = command_text
        self.command.description = description
        
        # Accept the dialog
        self.accept()
        
    def get_command(self):
        """Get the edited command"""
        return self.command


class CommandSetSettingsDialog(QDialog):
    """Dialog for editing command set settings"""
    
    def __init__(self, command_set=None, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.command_set = command_set or CommandSet("", "")
        
        # Set dialog properties
        self.setWindowTitle("Command Set Settings")
        self.resize(400, 200)
        
        # Create UI components
        self._create_ui()
        
    def _create_ui(self):
        """Create the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        # Command set fields
        self.device_type = QLineEdit(self.command_set.device_type)
        form.addRow("Device Type:", self.device_type)
        
        self.firmware = QLineEdit(self.command_set.firmware_version)
        form.addRow("Firmware Version:", self.firmware)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
        
    def _on_accept(self):
        """Handle dialog acceptance"""
        # Validate input
        device_type = self.device_type.text().strip()
        firmware = self.firmware.text().strip()
        
        if not device_type:
            QMessageBox.warning(self, "Missing Device Type", "Please enter a device type.")
            return
            
        if not firmware:
            QMessageBox.warning(self, "Missing Firmware", "Please enter a firmware version.")
            return
            
        # Update command set
        self.command_set.device_type = device_type
        self.command_set.firmware_version = firmware
        
        # Accept the dialog
        self.accept()
        
    def get_command_set(self):
        """Get the edited command set"""
        return self.command_set


class CommandSetEditor(QDialog):
    """Dialog for editing command sets"""
    
    def __init__(self, plugin, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.plugin = plugin
        self.current_command_set = None
        
        # Set dialog properties
        self.setWindowTitle("Command Set Editor")
        self.resize(800, 600)
        
        # Create UI components
        self._create_ui()
        
        # Refresh command sets
        self.refresh_command_sets()
        
    def _create_ui(self):
        """Create the UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Command set list panel
        command_set_panel = QWidget()
        command_set_layout = QVBoxLayout(command_set_panel)
        
        # Title and buttons
        command_set_header = QWidget()
        command_set_header_layout = QHBoxLayout(command_set_header)
        command_set_header_layout.setContentsMargins(0, 0, 0, 0)
        
        command_set_label = QLabel("Command Sets:")
        command_set_header_layout.addWidget(command_set_label)
        
        # Add buttons
        new_set_button = QPushButton("New")
        new_set_button.clicked.connect(self._on_new_set)
        command_set_header_layout.addWidget(new_set_button)
        
        self.edit_set_button = QPushButton("Edit")
        self.edit_set_button.clicked.connect(self._on_edit_set)
        self.edit_set_button.setEnabled(False)
        command_set_header_layout.addWidget(self.edit_set_button)
        
        self.delete_set_button = QPushButton("Delete")
        self.delete_set_button.clicked.connect(self._on_delete_set)
        self.delete_set_button.setEnabled(False)
        command_set_header_layout.addWidget(self.delete_set_button)
        
        command_set_layout.addWidget(command_set_header)
        
        # Command set list
        self.command_set_list = QListWidget()
        self.command_set_list.setSelectionMode(QListWidget.SingleSelection)
        self.command_set_list.currentItemChanged.connect(self._on_command_set_selected)
        self.command_set_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.command_set_list.customContextMenuRequested.connect(self._on_command_set_context_menu)
        command_set_layout.addWidget(self.command_set_list)
        
        # Command list panel
        command_panel = QWidget()
        command_layout = QVBoxLayout(command_panel)
        
        # Title and buttons
        command_header = QWidget()
        command_header_layout = QHBoxLayout(command_header)
        command_header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.command_label = QLabel("Commands:")
        command_header_layout.addWidget(self.command_label)
        
        # Add buttons
        self.new_command_button = QPushButton("Add")
        self.new_command_button.clicked.connect(self._on_new_command)
        self.new_command_button.setEnabled(False)
        command_header_layout.addWidget(self.new_command_button)
        
        self.edit_command_button = QPushButton("Edit")
        self.edit_command_button.clicked.connect(self._on_edit_command)
        self.edit_command_button.setEnabled(False)
        command_header_layout.addWidget(self.edit_command_button)
        
        self.delete_command_button = QPushButton("Delete")
        self.delete_command_button.clicked.connect(self._on_delete_command)
        self.delete_command_button.setEnabled(False)
        command_header_layout.addWidget(self.delete_command_button)
        
        command_layout.addWidget(command_header)
        
        # Command table
        self.command_table = QTableWidget()
        self.command_table.setColumnCount(3)
        self.command_table.setHorizontalHeaderLabels(["Alias", "Command", "Description"])
        self.command_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.command_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.command_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.command_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.command_table.setSelectionMode(QTableWidget.SingleSelection)
        self.command_table.itemSelectionChanged.connect(self._on_command_selection_changed)
        self.command_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.command_table.customContextMenuRequested.connect(self._on_command_context_menu)
        command_layout.addWidget(self.command_table)
        
        # Add panels to splitter
        splitter.addWidget(command_set_panel)
        splitter.addWidget(command_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._on_export)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self._on_import)
        button_layout.addWidget(self.import_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
    def refresh_command_sets(self):
        """Refresh the command set list"""
        # Remember current selection
        current_device_type = None
        current_firmware = None
        
        if self.current_command_set:
            current_device_type = self.current_command_set.device_type
            current_firmware = self.current_command_set.firmware_version
            
        # Clear the list
        self.command_set_list.clear()
        
        # Get device types
        device_types = self.plugin.get_device_types()
        
        # Build command set list
        for device_type in device_types:
            # Get firmware versions
            firmware_versions = self.plugin.get_firmware_versions(device_type)
            
            # Add items
            for firmware in firmware_versions:
                # Create item
                item_text = f"{device_type} ({firmware})"
                item = QListWidgetItem(item_text)
                
                # Store data
                item.setData(Qt.UserRole, {
                    "device_type": device_type,
                    "firmware": firmware
                })
                
                # Add to list
                self.command_set_list.addItem(item)
                
                # Select if this was the previous selection
                if device_type == current_device_type and firmware == current_firmware:
                    self.command_set_list.setCurrentItem(item)
                    
        # Update UI state
        self._update_ui_state()
        
    def refresh_commands(self):
        """Refresh the command table"""
        # Clear the table
        self.command_table.setRowCount(0)
        
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Update label
        self.command_label.setText(f"Commands for {self.current_command_set.device_type} ({self.current_command_set.firmware_version}):")
        
        # Add commands to table
        for i, command in enumerate(self.current_command_set.commands):
            row = self.command_table.rowCount()
            self.command_table.insertRow(row)
            
            # Command info
            alias = QTableWidgetItem(command.alias)
            command_text = QTableWidgetItem(command.command)
            description = QTableWidgetItem(command.description)
            
            # Store command index
            alias.setData(Qt.UserRole, i)
            
            # Add to table
            self.command_table.setItem(row, 0, alias)
            self.command_table.setItem(row, 1, command_text)
            self.command_table.setItem(row, 2, description)
            
    def _update_ui_state(self):
        """Update the UI state based on selections"""
        # Command set buttons
        has_command_set = self.command_set_list.currentItem() is not None
        self.edit_set_button.setEnabled(has_command_set)
        self.delete_set_button.setEnabled(has_command_set)
        self.export_button.setEnabled(has_command_set)
        
        # Command buttons
        self.new_command_button.setEnabled(has_command_set)
        
        has_command = self.command_table.currentRow() >= 0
        self.edit_command_button.setEnabled(has_command)
        self.delete_command_button.setEnabled(has_command)
        
    def _on_command_set_selected(self, current, previous):
        """Handle command set selection"""
        # Clear current command set
        self.current_command_set = None
        
        # Clear command table
        self.command_table.setRowCount(0)
        
        # Check if an item is selected
        if not current:
            self._update_ui_state()
            return
            
        # Get item data
        item_data = current.data(Qt.UserRole)
        
        if not item_data:
            self._update_ui_state()
            return
            
        # Get command set
        device_type = item_data.get("device_type", "")
        firmware = item_data.get("firmware", "")
        
        if device_type and firmware:
            self.current_command_set = self.plugin.get_command_set(device_type, firmware)
            
        # Refresh commands
        self.refresh_commands()
        
        # Update UI state
        self._update_ui_state()
        
    def _on_command_selection_changed(self):
        """Handle command selection change"""
        self._update_ui_state()
        
    def _on_new_set(self):
        """Handle new command set button"""
        # Create dialog
        dialog = CommandSetSettingsDialog(parent=self)
        
        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Get command set
            command_set = dialog.get_command_set()
            
            # Check if command set already exists
            if command_set.device_type in self.plugin.command_sets and command_set.firmware_version in self.plugin.command_sets[command_set.device_type]:
                result = QMessageBox.question(
                    self,
                    "Command Set Exists",
                    f"A command set for {command_set.device_type} ({command_set.firmware_version}) already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if result != QMessageBox.Yes:
                    return
            
            # Add command set
            self.plugin.add_command_set(command_set)
            
            # Refresh command sets
            self.refresh_command_sets()
            
            # Try to select the new command set
            for i in range(self.command_set_list.count()):
                item = self.command_set_list.item(i)
                data = item.data(Qt.UserRole)
                
                if data.get("device_type") == command_set.device_type and data.get("firmware") == command_set.firmware_version:
                    self.command_set_list.setCurrentItem(item)
                    break
                    
    def _on_edit_set(self):
        """Handle edit command set button"""
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Create dialog
        dialog = CommandSetSettingsDialog(self.current_command_set, self)
        
        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Get command set
            edited_command_set = dialog.get_command_set()
            
            # Check if name or firmware changed
            old_device_type = self.current_command_set.device_type
            old_firmware = self.current_command_set.firmware_version
            
            if edited_command_set.device_type != old_device_type or edited_command_set.firmware_version != old_firmware:
                # Check if command set already exists
                if edited_command_set.device_type in self.plugin.command_sets and edited_command_set.firmware_version in self.plugin.command_sets[edited_command_set.device_type]:
                    result = QMessageBox.question(
                        self,
                        "Command Set Exists",
                        f"A command set for {edited_command_set.device_type} ({edited_command_set.firmware_version}) already exists. Overwrite?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if result != QMessageBox.Yes:
                        return
                        
                # Delete old command set
                self.plugin.delete_command_set(old_device_type, old_firmware)
            
            # Add edited command set
            self.plugin.add_command_set(edited_command_set)
            
            # Update current command set
            self.current_command_set = edited_command_set
            
            # Refresh command sets
            self.refresh_command_sets()
            
            # Try to select the edited command set
            for i in range(self.command_set_list.count()):
                item = self.command_set_list.item(i)
                data = item.data(Qt.UserRole)
                
                if data.get("device_type") == edited_command_set.device_type and data.get("firmware") == edited_command_set.firmware_version:
                    self.command_set_list.setCurrentItem(item)
                    break
                    
    def _on_delete_set(self):
        """Handle delete command set button"""
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the command set for {self.current_command_set.device_type} ({self.current_command_set.firmware_version})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete command set
        self.plugin.delete_command_set(self.current_command_set.device_type, self.current_command_set.firmware_version)
        
        # Clear current command set
        self.current_command_set = None
        
        # Refresh command sets
        self.refresh_command_sets()
        
    def _on_new_command(self):
        """Handle new command button"""
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Create dialog
        dialog = CommandDialog(parent=self)
        
        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Get command
            command = dialog.get_command()
            
            # Add to command set
            self.current_command_set.commands.append(command)
            
            # Update command set
            self.plugin.add_command_set(self.current_command_set)
            
            # Refresh commands
            self.refresh_commands()
            
            # Select the new command
            last_row = self.command_table.rowCount() - 1
            if last_row >= 0:
                self.command_table.selectRow(last_row)
                
    def _on_edit_command(self):
        """Handle edit command button"""
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Check if a command is selected
        current_row = self.command_table.currentRow()
        if current_row < 0:
            return
            
        # Get command index
        command_index = self.command_table.item(current_row, 0).data(Qt.UserRole)
        
        # Get command
        command = self.current_command_set.commands[command_index]
        
        # Create dialog
        dialog = CommandDialog(copy.deepcopy(command), self)
        
        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Get edited command
            edited_command = dialog.get_command()
            
            # Update command
            self.current_command_set.commands[command_index] = edited_command
            
            # Update command set
            self.plugin.add_command_set(self.current_command_set)
            
            # Refresh commands
            self.refresh_commands()
            
            # Select the edited command
            self.command_table.selectRow(current_row)
            
    def _on_delete_command(self):
        """Handle delete command button"""
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Check if a command is selected
        current_row = self.command_table.currentRow()
        if current_row < 0:
            return
            
        # Get command index
        command_index = self.command_table.item(current_row, 0).data(Qt.UserRole)
        
        # Get command
        command = self.current_command_set.commands[command_index]
        
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the command '{command.alias}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Delete command
        del self.current_command_set.commands[command_index]
        
        # Update command set
        self.plugin.add_command_set(self.current_command_set)
        
        # Refresh commands
        self.refresh_commands()
        
    def _on_export(self):
        """Handle export button"""
        # Check if we have a command set
        if not self.current_command_set:
            return
            
        # Create suggested filename
        filename = f"{self.current_command_set.device_type}_{self.current_command_set.firmware_version.replace('.', '_')}.json"
        filename = ''.join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])
        
        # Show file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Command Set",
            filename,
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        # Export command set
        try:
            with open(file_path, "w") as f:
                json.dump(self.current_command_set.to_dict(), f, indent=2)
                
            QMessageBox.information(
                self,
                "Export Successful",
                f"Command set exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export command set: {e}"
            )
            
    def _on_import(self):
        """Handle import button"""
        # Show file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Command Set",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        # Import command set
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                
            # Validate command set
            required_fields = ["device_type", "firmware_version", "commands"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
                    
            # Create command set
            command_set = CommandSet.from_dict(data)
            
            # Check if command set already exists
            if command_set.device_type in self.plugin.command_sets and command_set.firmware_version in self.plugin.command_sets[command_set.device_type]:
                result = QMessageBox.question(
                    self,
                    "Command Set Exists",
                    f"A command set for {command_set.device_type} ({command_set.firmware_version}) already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if result != QMessageBox.Yes:
                    return
            
            # Add command set
            self.plugin.add_command_set(command_set)
            
            # Refresh command sets
            self.refresh_command_sets()
            
            # Try to select the imported command set
            for i in range(self.command_set_list.count()):
                item = self.command_set_list.item(i)
                data = item.data(Qt.UserRole)
                
                if data.get("device_type") == command_set.device_type and data.get("firmware") == command_set.firmware_version:
                    self.command_set_list.setCurrentItem(item)
                    break
                    
            # Show success message
            QMessageBox.information(
                self,
                "Import Successful",
                f"Command set '{command_set.device_type} ({command_set.firmware_version})' imported successfully."
            )
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Import Failed",
                f"Failed to import command set: {e}"
            )
            
    def _on_command_set_context_menu(self, pos):
        """Handle context menu on command set list"""
        # Get the item under the cursor
        item = self.command_set_list.itemAt(pos)
        
        if not item:
            return
            
        # Create context menu
        menu = QMenu(self)
        
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._on_edit_set)
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._on_delete_set)
        
        export_action = QAction("Export", self)
        export_action.triggered.connect(self._on_export)
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addAction(export_action)
        
        # Show the menu
        menu.exec(self.command_set_list.mapToGlobal(pos))
        
    def _on_command_context_menu(self, pos):
        """Handle context menu on command table"""
        # Get the item under the cursor
        item = self.command_table.itemAt(pos)
        
        if not item:
            return
            
        # Create context menu
        menu = QMenu(self)
        
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._on_edit_command)
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._on_delete_command)
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        
        # Show the menu
        menu.exec(self.command_table.mapToGlobal(pos)) 