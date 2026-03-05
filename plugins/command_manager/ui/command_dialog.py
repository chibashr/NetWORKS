#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command Dialog for Command Manager plugin
"""

import os
import json
import datetime
from pathlib import Path
import threading

from PySide6.QtCore import Qt, Signal, Slot, QThread, QObject
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSplitter, QTextEdit, QMenu, QFileDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QWidget,
    QCheckBox, QGroupBox, QFormLayout, QDialogButtonBox, QTabWidget,
    QLineEdit, QInputDialog, QPlainTextEdit
)
from PySide6.QtGui import QAction, QIcon, QFont, QTextCursor, QShowEvent, QPainter, QTextFormat

from src.ui.plugin_ui_theme import mark_plugin_ui

from .command_worker import CommandWorker
from .command_target_tabs import (
    build_target_tabs,
    refresh_target_tables,
    safe_str,
    get_selected_devices_from_dialog,
)
from .command_dialog_saved_sets import load_saved_command_sets_into_dialog


class _LineNumberArea(QWidget):
    """Auxiliary widget used to draw line numbers for LineNumberedPlainTextEdit."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return self._editor.lineNumberAreaSize()

    def paintEvent(self, event):
        self._editor.lineNumberAreaPaintEvent(event)


class LineNumberedPlainTextEdit(QPlainTextEdit):
    """Plain text editor with simple line numbers in the left margin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_number_area = _LineNumberArea(self)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_line_number_area_width(0)
        self._highlight_current_line()

    # --- Line number area sizing/updates ---
    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        # Extra padding around the digits
        return 3 + self.fontMetrics().horizontalAdvance("9" * digits) + 6

    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(),
            cr.top(),
            self.lineNumberAreaWidth(),
            cr.height(),
        )

    def lineNumberAreaSize(self):
        return self._line_number_area.sizeHint()

    # --- Painting ---
    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), self.palette().alternateBase())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.palette().color(self.foregroundRole()))
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = self.palette().alternateBase().color()
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)


class CommandDialog(QDialog):
    """Dialog for running commands on devices"""
    
    def __init__(self, plugin, devices=None, parent=None):
        """Initialize the dialog
        
        Args:
            plugin: The command manager plugin
            devices: Optional list of devices to pre-select
            parent: Parent widget
        """
        super().__init__(parent)
        mark_plugin_ui(self)
        
        self.plugin = plugin
        self.worker_thread = None
        self.worker = None
        self.selected_devices = devices or []
        self.temporary_saved_set_names = set()
        self._current_temporary_set_name = None

        # Set dialog properties
        self.setWindowTitle("Command Manager")
        # Give the three-panel layout enough default width
        self.resize(1200, 650)
        
        # Create UI components
        self._create_ui()
        
        # Refresh devices
        self.refresh_devices()
        
        # Refresh command sets
        self.refresh_command_sets()
        
        # Pre-select devices if provided
        if self.selected_devices:
            self.set_selected_devices(self.selected_devices)

    def showEvent(self, event):
        """Refresh devices, groups, and saved command sets when the dialog is shown.
        Ensures the dialog always displays current data, not cached data from a
        previous session or an earlier time the dialog was open.
        """
        super().showEvent(event)
        self.refresh_devices()
        self.refresh_command_sets()
        self._sync_custom_commands_prefill()
        
    def _create_ui(self):
        """Create the UI components.
        Layout: left = devices, middle = commands and options, right = command output.
        """
        # Main layout
        layout = QVBoxLayout(self)
        
        # Horizontal splitter: left (devices) | middle (commands) | right (output)
        splitter = QSplitter(Qt.Horizontal)
        
        # ==================
        # Left panel: devices
        # ==================
        device_panel = QWidget()
        device_layout = QVBoxLayout(device_panel)
        device_layout.setContentsMargins(0, 0, 0, 0)
        
        self.target_tabs, self.device_table, self.group_table, self.subnet_table = build_target_tabs(self)
        
        device_cred_layout = QHBoxLayout()
        self.manage_credentials_btn = QPushButton("👤 Manage Credentials")
        self.manage_credentials_btn.setToolTip("Configure device credentials")
        self.manage_credentials_btn.clicked.connect(self._on_manage_credentials)
        
        self.batch_export_btn = QPushButton("📊 Batch Export")
        self.batch_export_btn.setToolTip("Export commands from multiple devices")
        self.batch_export_btn.clicked.connect(self._on_batch_export)
        
        device_cred_layout.addWidget(self.manage_credentials_btn)
        device_cred_layout.addWidget(self.batch_export_btn)
        device_cred_layout.addStretch()
        
        device_layout.addWidget(self.target_tabs)
        device_layout.addLayout(device_cred_layout)
        
        # ==================
        # Middle panel: tabbed commands
        # ==================
        command_panel = QWidget()
        command_layout = QVBoxLayout(command_panel)
        command_layout.setContentsMargins(0, 0, 0, 0)
        
        # Panel-level search bar (top of command panel; stays visible and synced with table search)
        panel_search_layout = QHBoxLayout()
        self.panel_search = QLineEdit()
        self.panel_search.setPlaceholderText("Search commands...")
        self.panel_search.textChanged.connect(self._on_panel_search_changed)
        panel_search_layout.addWidget(QLabel("Search:"))
        panel_search_layout.addWidget(self.panel_search, 1)
        command_layout.addLayout(panel_search_layout)
        
        self.command_tabs = QTabWidget()
        
        # ---- Tab 1: Preloaded commands ----
        preloaded_tab = QWidget()
        preloaded_layout = QVBoxLayout(preloaded_tab)
        preloaded_layout.setContentsMargins(0, 0, 0, 0)
        
        command_set_widget = QWidget()
        command_set_layout = QHBoxLayout(command_set_widget)
        command_set_layout.setContentsMargins(0, 0, 0, 0)
        
        device_type_label = QLabel("Device Type:")
        self.device_type_combo = QComboBox()
        self.device_type_combo.currentIndexChanged.connect(self._on_device_type_changed)
        
        firmware_label = QLabel("Firmware:")
        self.firmware_combo = QComboBox()
        self.firmware_combo.currentIndexChanged.connect(self._on_firmware_changed)
        
        manage_button = QPushButton("Manage Sets")
        manage_button.clicked.connect(self._on_manage_sets)

        import_button = QPushButton("Import")
        import_button.clicked.connect(self._on_import_set)

        command_set_layout.addWidget(device_type_label)
        command_set_layout.addWidget(self.device_type_combo, 1)
        command_set_layout.addWidget(firmware_label)
        command_set_layout.addWidget(self.firmware_combo, 1)
        command_set_layout.addWidget(manage_button)
        command_set_layout.addWidget(import_button)
        
        command_header_layout = QHBoxLayout()
        command_label = QLabel("Commands:")
        
        saved_sets_label = QLabel("Saved Sets:")
        self.saved_sets_combo = QComboBox()
        self.saved_sets_combo.setMinimumWidth(150)
        self.saved_sets_combo.currentIndexChanged.connect(self._on_saved_set_selected)
        
        self.run_saved_set_btn = QPushButton("Run Set")
        self.run_saved_set_btn.clicked.connect(self._on_run_saved_set)
        self.run_saved_set_btn.setEnabled(False)
        
        self.save_selection_btn = QPushButton("Save Selection as Set")
        self.save_selection_btn.clicked.connect(self._on_save_selection)
        
        command_header_layout.addWidget(command_label)
        command_header_layout.addStretch()
        command_header_layout.addWidget(saved_sets_label)
        command_header_layout.addWidget(self.saved_sets_combo)
        command_header_layout.addWidget(self.run_saved_set_btn)
        command_header_layout.addWidget(self.save_selection_btn)
        
        search_layout = QHBoxLayout()
        self.command_search = QLineEdit()
        self.command_search.setPlaceholderText("Search commands...")
        self.command_search.textChanged.connect(self._on_command_search_changed)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.command_search, 1)
        
        self.command_table = QTableWidget()
        self.command_table.setColumnCount(3)
        self.command_table.setHorizontalHeaderLabels(["Alias", "Command", "Description"])
        self.command_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.command_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.command_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.command_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.command_table.setSelectionMode(QTableWidget.MultiSelection)
        
        preloaded_layout.addWidget(command_set_widget)
        preloaded_layout.addLayout(command_header_layout)
        preloaded_layout.addLayout(search_layout)
        preloaded_layout.addWidget(self.command_table)

        # ---- Tab 2: Custom commands (inline with line numbers) ----
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        # Light padding so content breathes but stays visually in-line with the tab surface
        custom_layout.setContentsMargins(4, 4, 4, 4)

        custom_header = QWidget()
        custom_header_layout = QHBoxLayout(custom_header)
        custom_header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Custom commands are treated as a single pasted block per device.
        custom_label = QLabel("Commands executed as a pasted block per device (top to bottom):")
        custom_header_layout.addWidget(custom_label)

        # Quick-access variable insertion button for custom commands.
        self.custom_insert_var_btn = QPushButton("Insert Variable")
        self.custom_insert_var_btn.setToolTip(
            "Insert a device variable like {alias}, {hostname}, {ip_address}, {ip-address} at the cursor position."
        )
        self.custom_insert_var_btn.clicked.connect(self._on_insert_variable_clicked)
        custom_header_layout.addWidget(self.custom_insert_var_btn)

        custom_header_layout.addStretch()
        
        self.custom_clear_btn = QPushButton("Clear")
        self.custom_clear_btn.clicked.connect(self._on_clear_custom_commands)
        custom_header_layout.addWidget(self.custom_clear_btn)
        
        self.custom_commands_text = LineNumberedPlainTextEdit()
        self.custom_commands_text.setPlaceholderText(
            "show version\n"
            "show interfaces\n"
            "# You can also use device variables like {alias}, {Alias}, {hostname}, {ip_address}, {ip-address}."
        )
        self.custom_commands_text.setFont(QFont("Courier New", 9))
        # Enable context menu hook so we can add "Insert Variable" on right-click.
        self.custom_commands_text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.custom_commands_text.customContextMenuRequested.connect(
            self._on_custom_commands_context_menu
        )

        custom_options = QWidget()
        custom_options_layout = QHBoxLayout(custom_options)
        custom_options_layout.setContentsMargins(0, 0, 0, 0)

        self.show_only_check = QCheckBox("Allow 'show' only")
        self.show_only_check.setChecked(True)
        self.show_only_check.setToolTip("When checked, only commands starting with 'show' will be allowed")
        custom_options_layout.addWidget(self.show_only_check)
        custom_options_layout.addStretch()

        # Native tab content: header, editor, and options live directly on the tab surface
        custom_layout.addWidget(custom_header)
        custom_layout.addWidget(self.custom_commands_text, 1)
        custom_layout.addWidget(custom_options)

        # Tabs
        self.command_tabs.addTab(preloaded_tab, "Preloaded Commands")
        self.command_tabs.addTab(custom_tab, "Custom Commands")
        self.command_tabs.currentChanged.connect(self._on_command_tab_changed)

        command_layout.addWidget(self.command_tabs)
        
        # ==================
        # Right panel: command output
        # ==================
        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        
        output_header = QWidget()
        output_header_layout = QHBoxLayout(output_header)
        output_header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.output_label = QLabel("Command Output:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        output_header_layout.addWidget(self.output_label, 1)
        output_header_layout.addWidget(self.progress_bar)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        font = QFont("Courier New", 9)
        self.output_text.setFont(font)
        
        output_layout.addWidget(output_header)
        output_layout.addWidget(self.output_text)
        
        # Add three panels to horizontal splitter (left | middle | right)
        splitter.addWidget(device_panel)
        splitter.addWidget(command_panel)
        splitter.addWidget(output_panel)
        splitter.setStretchFactor(0, 1)   # devices
        splitter.setStretchFactor(1, 3)   # commands (widest)
        splitter.setStretchFactor(2, 2)   # output
        # Initial sizes to keep each panel functional on first open
        splitter.setSizes([280, 640, 480])
        
        layout.addWidget(splitter)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.run_selected_button = QPushButton("Run Selected Commands")
        self.run_selected_button.clicked.connect(self._on_run_selected)
        
        self.run_all_button = QPushButton("Run All Commands")
        self.run_all_button.clicked.connect(self._on_run_all)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop)

        self.clear_button = QPushButton("Clear Output")
        self.clear_button.clicked.connect(self._on_clear_output)
        
        self.export_button = QPushButton("Export Output")
        self.export_button.clicked.connect(self._on_export_output)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.run_selected_button)
        button_layout.addWidget(self.run_all_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self._on_command_tab_changed(self.command_tabs.currentIndex())
        self._sync_custom_commands_prefill()

    def _sync_custom_commands_prefill(self):
        """If the plugin has pending custom commands, prefill the inline editor and switch tabs."""
        pending = ""
        if hasattr(self.plugin, "pending_custom_commands_text") and self.plugin.pending_custom_commands_text:
            pending = (self.plugin.pending_custom_commands_text or "").strip()
        if pending and hasattr(self, "custom_commands_text"):
            # Only prefill if the editor is empty to avoid clobbering user edits
            if not self.custom_commands_text.toPlainText().strip():
                self.custom_commands_text.setPlainText(pending)
            # Bring the user to the custom tab when something was preloaded
            if hasattr(self, "command_tabs"):
                self.command_tabs.setCurrentIndex(1)

    def _on_command_tab_changed(self, index):
        """Update button labels based on active commands tab."""
        is_custom = (index == 1)
        if is_custom:
            self.run_selected_button.setText("Run Custom Commands")
            self.run_all_button.setEnabled(False)
            self.run_all_button.setToolTip("Not applicable for Custom Commands")
        else:
            self.run_selected_button.setText("Run Selected Commands")
            self.run_all_button.setEnabled(True)
            self.run_all_button.setToolTip("")

    def _on_clear_custom_commands(self):
        if hasattr(self, "custom_commands_text"):
            self.custom_commands_text.clear()

    # --- Custom commands variable insertion helpers ---

    def _available_custom_variables(self):
        """Return a list of (label, placeholder) tuples for all available device fields.

        Fields are discovered dynamically from the current environment:
        - Core/base program fields (id, alias, hostname, ip_address, etc.)
        - Any additional properties attached to devices in this workspace (including plugin fields).
        """
        keys = []

        # Prefer currently targeted devices; if none, fall back to all devices in the workspace.
        try:
            devices = self._get_selected_devices()
        except Exception:
            devices = []

        if (not devices) and hasattr(self.plugin, "device_manager") and self.plugin.device_manager:
            try:
                devices = self.plugin.device_manager.get_devices()
            except Exception:
                devices = []

        for device in devices or []:
            if not hasattr(device, "get_properties"):
                continue
            try:
                props = device.get_properties() or {}
            except Exception:
                continue
            for key in props.keys():
                if not isinstance(key, str):
                    continue
                if key not in keys:
                    keys.append(key)

        # If we couldn't discover anything (e.g. no devices yet), fall back to known core fields.
        if not keys:
            keys = [
                "id",
                "alias",
                "hostname",
                "ip_address",
                "mac_address",
                "status",
                "notes",
                "tags",
                "type",
                "name",
                "created",
            ]

        # Ensure core/base fields are presented first in a sensible order.
        core_order = [
            "id",
            "alias",
            "hostname",
            "ip_address",
            "mac_address",
            "status",
            "notes",
            "tags",
            "type",
            "name",
            "created",
        ]
        ordered = []
        seen = set()
        for core_key in core_order:
            if core_key in keys and core_key not in seen:
                ordered.append(core_key)
                seen.add(core_key)
        for key in sorted(keys):
            if key not in seen:
                ordered.append(key)
                seen.add(key)

        # Build menu entries: one placeholder per underlying field, using the canonical {field_name}.
        items = []
        for key in ordered:
            placeholder = f"{{{key}}}"
            label = f"{key} ({placeholder})"
            items.append((label, placeholder))
        return items

    def _insert_variable_placeholder(self, placeholder: str):
        """Insert a variable placeholder into the custom commands editor."""
        if not hasattr(self, "custom_commands_text") or not self.custom_commands_text:
            return
        cursor = self.custom_commands_text.textCursor()
        cursor.insertText(placeholder)
        self.custom_commands_text.setTextCursor(cursor)

    def _build_variable_menu(self, parent_widget):
        """Create a QMenu populated with available variable placeholders."""
        menu = QMenu(parent_widget)
        for label, placeholder in self._available_custom_variables():
            action = menu.addAction(label)
            # Use lambda with default arg to capture current placeholder
            action.triggered.connect(lambda _checked=False, p=placeholder: self._insert_variable_placeholder(p))
        return menu

    def _on_insert_variable_clicked(self):
        """Show a popup menu to insert a variable at the cursor in custom commands."""
        if not hasattr(self, "custom_insert_var_btn"):
            return
        menu = self._build_variable_menu(self.custom_insert_var_btn)
        global_pos = self.custom_insert_var_btn.mapToGlobal(
            self.custom_insert_var_btn.rect().bottomLeft()
        )
        menu.exec(global_pos)

    def _on_custom_commands_context_menu(self, pos):
        """Augment the default context menu with an 'Insert Variable' section."""
        if not hasattr(self, "custom_commands_text") or not self.custom_commands_text:
            return
        # Start with the standard context menu for the editor
        menu = self.custom_commands_text.createStandardContextMenu()
        menu.addSeparator()
        var_menu = menu.addMenu("Insert Variable")
        for label, placeholder in self._available_custom_variables():
            action = var_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, p=placeholder: self._insert_variable_placeholder(p))
        global_pos = self.custom_commands_text.mapToGlobal(pos)
        menu.exec(global_pos)
        menu.deleteLater()
        
    def refresh_devices(self):
        refresh_target_tables(self)

    def refresh_command_sets(self):
        """Refresh the command set selectors"""
        # Block signals
        self.device_type_combo.blockSignals(True)
        self.firmware_combo.blockSignals(True)
        
        # Store current selections
        current_device_type = self.device_type_combo.currentText()
        current_firmware = self.firmware_combo.currentText()
        
        # Clear existing items
        self.device_type_combo.clear()
        self.firmware_combo.clear()
        
        # Get available device types
        device_types = self.plugin.get_device_types()
        
        # Add device types
        self.device_type_combo.addItems(device_types)
        
        # Restore selection or select first item
        index = self.device_type_combo.findText(current_device_type)
        if index >= 0:
            self.device_type_combo.setCurrentIndex(index)
        elif self.device_type_combo.count() > 0:
            self.device_type_combo.setCurrentIndex(0)
        
        # Unblock signals
        self.device_type_combo.blockSignals(False)
        self.firmware_combo.blockSignals(False)
        
        # Refresh firmware versions
        self._on_device_type_changed()
        
        # Restore firmware selection
        index = self.firmware_combo.findText(current_firmware)
        if index >= 0:
            self.firmware_combo.setCurrentIndex(index)
            
        # Load saved command sets
        self._load_saved_command_sets()

    def set_command_set_selection(self, device_type, firmware_version):
        """Select a command set by device type and firmware. Call after refresh_command_sets()."""
        if not device_type or not firmware_version:
            return
        idx = self.device_type_combo.findText(device_type)
        if idx >= 0:
            self.device_type_combo.setCurrentIndex(idx)
            self._on_device_type_changed()
            fw_idx = self.firmware_combo.findText(firmware_version)
            if fw_idx >= 0:
                self.firmware_combo.setCurrentIndex(fw_idx)

    def set_temporary_saved_set_selection(self, name):
        """Select a temporary saved set (e.g. from Template Manager) in the Saved Sets combo. Call after refresh_command_sets()."""
        if not name:
            return
        idx = self.saved_sets_combo.findText(name)
        if idx >= 0:
            self.saved_sets_combo.setCurrentIndex(idx)
            self._on_saved_set_selected(idx)

    def _load_saved_command_sets(self):
        load_saved_command_sets_into_dialog(self)

    def _on_saved_set_selected(self, index):
        """Handle selection of a saved command set (persistent = row indices; temporary = full command list)."""
        self.run_saved_set_btn.setEnabled(index > 0)
        self._current_temporary_set_name = None
        if index <= 0:
            return
        set_name = self.saved_sets_combo.currentText()
        temporary_names = getattr(self, "temporary_saved_set_names", set())
        if set_name in temporary_names and hasattr(self.plugin, "get_temporary_saved_set_commands"):
            commands_list = self.plugin.get_temporary_saved_set_commands(set_name)
            if commands_list is not None:
                self._fill_command_table_from_list(commands_list)
                self._current_temporary_set_name = set_name
            return
        if hasattr(self.plugin, "get_saved_command_sets"):
            command_sets = self.plugin.get_saved_command_sets()
            if command_sets and set_name in command_sets:
                command_indices = command_sets[set_name]
                self.command_table.clearSelection()
                for idx in command_indices:
                    if 0 <= idx < self.command_table.rowCount():
                        self.command_table.selectRow(idx)
        
    def _on_run_saved_set(self):
        """Handle running a saved command set (persistent = row indices; temporary = all rows in table)."""
        index = self.saved_sets_combo.currentIndex()
        if index <= 0:
            return
        set_name = self.saved_sets_combo.currentText()
        temporary_names = getattr(self, "temporary_saved_set_names", set())
        selected_commands = []
        if set_name in temporary_names:
            for row in range(self.command_table.rowCount()):
                command_item = self.command_table.item(row, 0)
                if command_item:
                    command_data = command_item.data(Qt.UserRole)
                    if command_data:
                        command_data = dict(command_data)
                        command_data["row"] = row
                        selected_commands.append(command_data)
        elif hasattr(self.plugin, "get_saved_command_sets"):
            command_sets = self.plugin.get_saved_command_sets()
            if command_sets and set_name in command_sets:
                for idx in command_sets[set_name]:
                    if 0 <= idx < self.command_table.rowCount():
                        command_item = self.command_table.item(idx, 0)
                        if command_item:
                            command_data = command_item.data(Qt.UserRole)
                            if command_data:
                                command_data = dict(command_data)
                                command_data["row"] = idx
                                selected_commands.append(command_data)
        if not selected_commands:
            QMessageBox.warning(
                self, "No Commands Found",
                f"No valid commands found in set '{set_name}'."
            )
            return
        selected_devices = self._get_selected_devices()
        if not selected_devices:
            QMessageBox.warning(
                self, "No Devices Selected",
                "Please select at least one device to run commands on."
            )
            return
        command_set = None
        if not getattr(self, "_current_temporary_set_name", None):
            device_type = self.device_type_combo.currentText()
            firmware = self.firmware_combo.currentText()
            if device_type and firmware:
                command_set = self.plugin.get_command_set(device_type, firmware)
        self._run_commands(selected_devices, selected_commands, command_set)
        
    def _on_save_selection(self):
        """Handle saving the current command selection as a set"""
        # Get selected commands
        selected_rows = []
        for item in self.command_table.selectedItems():
            row = item.row()
            if row not in selected_rows:
                selected_rows.append(row)
        
        if not selected_rows:
            QMessageBox.warning(
                self,
                "No Commands Selected",
                "Please select at least one command to save as a set."
            )
            return
        
        # Sort rows for consistent ordering
        selected_rows.sort()
        
        # Ask for a name
        name, ok = QInputDialog.getText(
            self,
            "Save Command Set",
            "Enter a name for this command set:",
            text="New Command Set"
        )
        
        if not ok or not name:
            return
        
        # Save the set
        if hasattr(self.plugin, 'save_command_set'):
            if self.plugin.save_command_set(name, selected_rows):
                # Refresh the combo box
                self._load_saved_command_sets()
                
                # Select the new set
                index = self.saved_sets_combo.findText(name)
                if index >= 0:
                    self.saved_sets_combo.setCurrentIndex(index)
                
                QMessageBox.information(
                    self,
                    "Command Set Saved",
                    f"Command set '{name}' saved successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Save Failed",
                    f"Failed to save command set '{name}'."
                )
                
    def _get_selected_devices(self):
        """Get selected devices based on the active tab (delegates to command_target_tabs)."""
        return get_selected_devices_from_dialog(self)
                                
    def _on_run_selected(self):
        """Run selected commands on selected devices"""
        from loguru import logger

        # If the user is on the Custom Commands tab, run the inline custom editor instead
        if hasattr(self, "command_tabs") and self.command_tabs.currentIndex() == 1:
            self._run_inline_custom_commands()
            return
        
        # Get selected commands
        selected_commands = []
        for item in self.command_table.selectedItems():
            row = item.row()
            # Only process each row once (in case multiple cells in the row are selected)
            if row not in [command["row"] for command in selected_commands]:
                command_item = self.command_table.item(row, 0)
                if command_item:
                    command_data = command_item.data(Qt.UserRole)
                    if command_data:
                        command_data["row"] = row
                        selected_commands.append(command_data)
        
        if not selected_commands:
            QMessageBox.warning(self, "No Commands Selected", "Please select at least one command to run.")
            return
        
        # Get selected devices
        selected_devices = self._get_selected_devices()
        
        if not selected_devices:
            QMessageBox.warning(self, "No Devices Selected", "Please select at least one device to run commands on.")
            return
        
        # Get current command set (None when running a temporary saved set)
        command_set = None
        if not getattr(self, "_current_temporary_set_name", None):
            device_type = self.device_type_combo.currentText()
            firmware = self.firmware_combo.currentText()
            if device_type and firmware:
                command_set = self.plugin.get_command_set(device_type, firmware)
        self._run_commands(selected_devices, selected_commands, command_set)

    def _on_run_all(self):
        """Run all commands on selected devices"""
        from loguru import logger

        # Not applicable for Custom Commands tab (button disabled, but keep safe)
        if hasattr(self, "command_tabs") and self.command_tabs.currentIndex() == 1:
            QMessageBox.information(
                self,
                "Not Available",
                "Run All is not applicable for Custom Commands. Use 'Run Custom Commands' instead.",
            )
            return
        
        # Get all commands
        all_commands = []
        for row in range(self.command_table.rowCount()):
            command_item = self.command_table.item(row, 0)
            if command_item:
                command_data = command_item.data(Qt.UserRole)
                if command_data:
                    command_data["row"] = row
                    all_commands.append(command_data)
        
        if not all_commands:
            QMessageBox.warning(self, "No Commands Available", "There are no commands available to run.")
            return
        
        # Get selected devices
        selected_devices = self._get_selected_devices()
        
        if not selected_devices:
            QMessageBox.warning(self, "No Devices Selected", "Please select at least one device to run commands on.")
            return
        
        # Get current command set (None when running a temporary saved set)
        command_set = None
        if not getattr(self, "_current_temporary_set_name", None):
            device_type = self.device_type_combo.currentText()
            firmware = self.firmware_combo.currentText()
            if device_type and firmware:
                command_set = self.plugin.get_command_set(device_type, firmware)
        self._run_commands(selected_devices, all_commands, command_set)

    def _on_device_type_changed(self):
        """Handle device type selection change"""
        self._current_temporary_set_name = None
        # Block signals
        self.firmware_combo.blockSignals(True)
        
        # Clear firmware combo
        self.firmware_combo.clear()
        
        # Get selected device type
        device_type = self.device_type_combo.currentText()
        
        if device_type:
            # Get firmware versions for selected device type
            firmware_versions = self.plugin.get_firmware_versions(device_type)
            
            # Add firmware versions
            self.firmware_combo.addItems(firmware_versions)
            
        # Unblock signals
        self.firmware_combo.blockSignals(False)
        
        # Refresh commands
        self._on_firmware_changed()
        
    def _on_firmware_changed(self):
        """Handle firmware selection change"""
        self._current_temporary_set_name = None
        self.command_table.setRowCount(0)
        device_type = self.device_type_combo.currentText()
        firmware = self.firmware_combo.currentText()
        if not device_type or not firmware:
            return
        command_set = self.plugin.get_command_set(device_type, firmware)
        if not command_set:
            return
        for command in command_set.commands:
            if hasattr(command, "alias"):
                cmd, al, desc = command.command, command.alias, command.description
            elif isinstance(command, dict):
                cmd = command.get("command", "")
                al = command.get("alias", "")
                desc = command.get("description", "")
            else:
                continue
            row = self.command_table.rowCount()
            self.command_table.insertRow(row)
            alias = QTableWidgetItem(safe_str(al, ""))
            command_text = QTableWidgetItem(safe_str(cmd, ""))
            description = QTableWidgetItem(safe_str(desc, ""))
            alias.setData(Qt.UserRole, {"command": cmd, "alias": al, "description": desc})
            self.command_table.setItem(row, 0, alias)
            self.command_table.setItem(row, 1, command_text)
            self.command_table.setItem(row, 2, description)
        self._on_search_commands(self.panel_search.text())

    def _fill_command_table_from_list(self, commands_list):
        """Clear the command table and fill from a list of dicts {command, alias, description} (e.g. temporary saved set)."""
        self.command_table.setRowCount(0)
        for c in commands_list or []:
            cmd = c.get("command", "") if isinstance(c, dict) else ""
            al = c.get("alias", "") if isinstance(c, dict) else ""
            desc = c.get("description", "") if isinstance(c, dict) else ""
            row = self.command_table.rowCount()
            self.command_table.insertRow(row)
            alias = QTableWidgetItem(safe_str(al, ""))
            command_text = QTableWidgetItem(safe_str(cmd, ""))
            description = QTableWidgetItem(safe_str(desc, ""))
            alias.setData(Qt.UserRole, {"command": cmd, "alias": al, "description": desc})
            self.command_table.setItem(row, 0, alias)
            self.command_table.setItem(row, 1, command_text)
            self.command_table.setItem(row, 2, description)
        self._on_search_commands(self.panel_search.text())

    def _on_manage_sets(self):
        """Handle manage command sets button"""
        # Open command set editor
        from .command_set_editor import CommandSetEditor
        editor = CommandSetEditor(self.plugin, self)
        
        if editor.exec() == QDialog.Accepted:
            # Refresh command sets
            self.refresh_command_sets()
            
    def _on_import_set(self):
        """Handle import command set button"""
        # Show file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Command Set",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        # Load file
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                
            # Validate command set
            required_fields = ["device_type", "firmware_version", "commands"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
                    
            # Create command set
            from ..utils.command_set import CommandSet
            command_set = CommandSet.from_dict(data)
            
            # Add command set
            self.plugin.add_command_set(command_set)
            
            # Refresh command sets
            self.refresh_command_sets()
            
            # Select the imported command set
            device_type_index = self.device_type_combo.findText(command_set.device_type)
            if device_type_index >= 0:
                self.device_type_combo.setCurrentIndex(device_type_index)
                
                firmware_index = self.firmware_combo.findText(command_set.firmware_version)
                if firmware_index >= 0:
                    self.firmware_combo.setCurrentIndex(firmware_index)
                    
            # Show success message
            QMessageBox.information(
                self,
                "Import Successful",
                f"Command set '{command_set.device_type} {command_set.firmware_version}' imported successfully."
            )
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Import Failed",
                f"Failed to import command set: {e}"
            )
            
    def _run_commands(self, devices, commands, command_set):
        """Run commands on devices using a background worker
        
        Args:
            devices: List of device objects to run commands on
            commands: List of command dictionaries to run
            command_set: Optional CommandSet object
        """
        from loguru import logger
        
        # Check if a worker is already running
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(
                self,
                "Commands Already Running",
                "Commands are already running. Please wait for them to complete or stop them first."
            )
            return
        
        # Clear previous output
        self.output_text.clear()
        
        # Create a new thread for the worker
        self.worker_thread = QThread()
        
        # Create the worker
        self.worker = CommandWorker(self.plugin, devices, commands, command_set)
        
        # Move worker to thread
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals (use QueuedConnection to ensure thread-safe signal delivery)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.command_started.connect(self._on_command_started, Qt.QueuedConnection)
        self.worker.command_complete.connect(self._on_command_complete, Qt.QueuedConnection)
        self.worker.command_progress.connect(self._on_command_progress, Qt.QueuedConnection)
        self.worker.all_commands_complete.connect(self._on_all_commands_complete, Qt.QueuedConnection)  # passes command_set
        self.worker_thread.finished.connect(self._on_worker_finished)
        
        # Update UI
        self.run_selected_button.setEnabled(False)
        self.run_all_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(devices) * len(commands))
        
        # Start the thread
        self.worker_thread.start()
        
        logger.debug(f"Started command execution for {len(devices)} devices and {len(commands)} commands")
    
    def _on_command_started(self, device, command):
        """Handle command started signal"""
        device_name = device.get_property("alias", device.get_property("hostname", "Unknown Device"))
        device_ip = device.get_property("ip_address", "Unknown IP")
        hostname = device.get_property("hostname", "")
        device_id = getattr(device, "id", "Unknown ID")
        command_alias = command.get("alias", command.get("command", "Unknown Command"))
        
        self.output_text.append(f"\n{'='*80}")
        self.output_text.append(f"Device: {device_name}")
        details_parts = []
        if hostname:
            details_parts.append(f"Hostname: {hostname}")
        if device_ip:
            details_parts.append(f"IP: {device_ip}")
        if device_id:
            details_parts.append(f"ID: {device_id}")
        if details_parts:
            self.output_text.append(" | ".join(details_parts))
        self.output_text.append(f"Command: {command_alias}")
        self.output_text.append(f"{'='*80}\n")
        
        # Scroll to bottom
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)
    
    def _on_command_complete(self, device, command, result, command_set):
        """Handle command complete signal"""
        if result.get("success", False):
            output = result.get("output", "")
            self.output_text.append(output)
        else:
            error_msg = result.get("output", "Unknown error")
            self.output_text.append(f"ERROR: {error_msg}")
        
        self.output_text.append("\n")
        
        # Scroll to bottom
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)
    
    def _on_command_progress(self, current, total):
        """Handle command progress signal"""
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)
        self.output_label.setText(f"Command Output: {current}/{total} commands completed")
    
    def _on_all_commands_complete(self, command_set=None):
        """Handle all commands complete signal. Unload temporary (template) command set if one was run."""
        from loguru import logger
        logger.debug("All commands completed")
        
        # Unload temporary command set (from Template Manager) when it was just applied
        if command_set and hasattr(self.plugin, "is_temporary_command_set") and self.plugin.is_temporary_command_set(command_set.device_type, command_set.firmware_version):
            self.plugin.delete_command_set(command_set.device_type, command_set.firmware_version)
            self.refresh_command_sets()
        
        # Update UI
        self.run_selected_button.setEnabled(True)
        self.run_all_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.output_label.setText("Command Output: All commands completed")
        
        # Clean up worker
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None
    
    def _on_worker_finished(self):
        """Handle worker thread finished signal"""
        # Clean up
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None
    
    def _on_stop(self):
        """Handle stop button"""
        # Stop the worker
        if self.worker:
            self.worker.stop()
            
        # Update UI
        self.stop_button.setEnabled(False)
        
    def _on_clear_output(self):
        """Handle clear output button"""
        self.output_text.clear()
        
    def _on_export_output(self):
        """Handle export output button"""
        # Check if there's output to export
        if not self.output_text.toPlainText():
            QMessageBox.warning(
                self,
                "No Output",
                "There is no output to export."
            )
            return
            
        # Show file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Output",
            "command_output.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        # Save output to file
        try:
            with open(file_path, "w") as f:
                f.write(self.output_text.toPlainText())
                
            QMessageBox.information(
                self,
                "Export Successful",
                f"Output exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export output: {e}"
            )
            
    def set_selected_devices(self, devices):
        """Set the selected devices in the table
        
        Args:
            devices: List of device objects to select
        """
        # Switch to the Devices tab
        self.target_tabs.setCurrentIndex(0)
        
        # Select the devices in the table
        self.device_table.clearSelection()
        
        for row in range(self.device_table.rowCount()):
            device_item = self.device_table.item(row, 0)
            if device_item and device_item.data(Qt.UserRole) in devices:
                self.device_table.selectRow(row)
                    
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Stop any running commands
        if self.worker:
            self.worker.stop()
            
        # Clean up
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None
            
        # Accept the event
        event.accept()

    def _on_manage_credentials(self):
        """Handle manage credentials button"""
        # Get the selected devices
        selected_devices = []
        for item in self.device_table.selectedItems():
            # Make sure we only count each row once
            if item.column() == 0:
                device_id = item.data(Qt.UserRole)
                device = self.plugin.device_manager.get_device(device_id)
                if device and device not in selected_devices:
                    selected_devices.append(device)
        
        # Open the credential manager with the selected devices
        from ..ui.credential_manager import CredentialManager
        cred_manager = CredentialManager(self.plugin, devices=selected_devices, parent=self)
        cred_manager.setWindowTitle("Device Credential Manager")
        cred_manager.resize(700, 550)
        cred_manager.exec()

    def _on_batch_export(self):
        """Handle batch export button"""
        from plugins.command_manager.reports.command_batch_export import CommandBatchExport
        
        try:
            # Create and display the batch export dialog
            dialog = CommandBatchExport(self.plugin, self)
            
            # Set window title to be more descriptive
            dialog.setWindowTitle("Export Commands from Multiple Devices")
            
            # Execute the dialog
            dialog.exec()
            
        except Exception as e:
            from loguru import logger
            logger.error(f"Error opening Command Batch Export: {e}")
            logger.exception("Exception details:")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error Opening Command Batch Export",
                f"An error occurred while opening the Command Batch Export: {str(e)}"
            )

    def _on_panel_search_changed(self, text):
        """Sync panel search to table search and apply filter."""
        self.command_search.blockSignals(True)
        self.command_search.setText(text)
        self.command_search.blockSignals(False)
        self._on_search_commands(text)

    def _on_command_search_changed(self, text):
        """Sync table search to panel search and apply filter."""
        self.panel_search.blockSignals(True)
        self.panel_search.setText(text)
        self.panel_search.blockSignals(False)
        self._on_search_commands(text)

    def _on_search_commands(self, text):
        """Filter command table based on search text"""
        search_text = text.lower().strip()
        
        # Show all rows if search is empty
        if not search_text:
            for row in range(self.command_table.rowCount()):
                self.command_table.setRowHidden(row, False)
            return
        
        # Hide rows that don't match the search
        for row in range(self.command_table.rowCount()):
            match_found = False
            
            # Check all columns
            for col in range(self.command_table.columnCount()):
                item = self.command_table.item(row, col)
                if item and search_text in item.text().lower():
                    match_found = True
                    break
            
            # Show or hide the row
            self.command_table.setRowHidden(row, not match_found)
            
    def _run_inline_custom_commands(self):
        """Run inline custom commands as a single pasted block per device."""
        selected_devices = self._get_selected_devices()
        if not selected_devices:
            QMessageBox.warning(
                self,
                "No Devices Selected",
                "Please select at least one device to run commands on.",
            )
            return

        text = ""
        if hasattr(self, "custom_commands_text"):
            text = self.custom_commands_text.toPlainText()
        lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
        if not lines:
            QMessageBox.warning(self, "Empty Commands", "Please enter one or more commands.")
            return

        if self.show_only_check.isChecked():
            offenders = [ln for ln in lines if not ln.lower().startswith("show ")]
            if offenders:
                result = QMessageBox.warning(
                    self,
                    "Non-Show Commands",
                    "One or more commands do not start with 'show'. Non-show commands may modify device configuration.\n\n"
                    "Are you sure you want to run these commands?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if result != QMessageBox.Yes:
                    return

        # Treat the entire editor contents as a single pasted block per device.
        block_text = "\n".join(lines)
        commands = [
            {
                "command": block_text,
                "alias": "Custom block",
                "description": "Custom commands (pasted block)",
                "row": -1,
            }
        ]

        # Runs block per device, then next device (like pasting config).
        self._run_commands(selected_devices, commands, None)

        # Clear pending prefill once successfully started.
        if hasattr(self.plugin, "pending_custom_commands_text"):
            self.plugin.pending_custom_commands_text = ""