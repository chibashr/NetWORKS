#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device table view and internal widgets for NetWORKS.
"""

from .device_table_model import DeviceTableModel
from .device_table_filter import (
    IPSortFilterProxyModel,
    parse_filter_syntax,
    filter_state_to_syntax,
    _default_header_to_short,
)
from .device_table_dialogs import AdvancedFilterDialog

from loguru import logger
from PySide6.QtCore import Qt, QSize, Signal, Slot, QRect, QSettings
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QAbstractItemView, QMenu, QApplication, QWidget,
    QVBoxLayout, QFormLayout, QLineEdit, QLabel, QTextEdit, QPushButton, QHBoxLayout,
    QComboBox, QTabWidget, QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QFileDialog, QWizard, QWizardPage,
    QScrollArea, QRadioButton, QSizePolicy, QGridLayout, QToolButton, QInputDialog,
    QStyle, QStyleOptionButton, QDialog, QDialogButtonBox,
)
from PySide6.QtGui import QAction, QIcon
from ...core.device_manager import Device
from ..material_icons import material_icon
from ..responsive_toolbar import ResponsiveToolbar
import csv
import io
import re
import json
import os


class _WrappingButtonGroup(QWidget):
    """Keep action buttons on a single line in the device table toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = []
        self._columns = 0
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(6)
        self._layout.setVerticalSpacing(4)

    def addButton(self, button):
        button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._buttons.append(button)
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self):
        if not self._buttons:
            return

        # Keep the buttons on one row to avoid vertical stacking.
        columns = max(1, len(self._buttons))
        if columns == self._columns:
            return

        self._columns = columns

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(self)

        for index, button in enumerate(self._buttons):
            row = index // columns
            col = index % columns
            self._layout.addWidget(button, row, col)


class _SelectionHeader(QHeaderView):
    """Header with a master checkbox for row selection."""

    toggled = Signal(Qt.CheckState)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._check_state = Qt.Unchecked
        self.setSectionsClickable(True)

    def set_check_state(self, state):
        """Update checkbox state and repaint."""
        if state == self._check_state:
            return
        self._check_state = state
        self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        if self.orientation() != Qt.Horizontal or logicalIndex != 0:
            return

        option = QStyleOptionButton()
        option.state = QStyle.State_Enabled
        if self._check_state == Qt.Checked:
            option.state |= QStyle.State_On
        elif self._check_state == Qt.PartiallyChecked:
            option.state |= QStyle.State_NoChange
        else:
            option.state |= QStyle.State_Off

        option.rect = self._checkbox_rect_for_section(rect)
        self.style().drawControl(QStyle.CE_CheckBox, option, painter, self)

    def mousePressEvent(self, event):
        if self.orientation() == Qt.Horizontal:
            rect = QRect(
                self.sectionViewportPosition(0),
                0,
                self.sectionSize(0),
                self.height()
            )
            checkbox_rect = self._checkbox_rect_for_section(rect)
            if checkbox_rect.contains(event.pos()):
                next_state = Qt.Unchecked if self._check_state == Qt.Checked else Qt.Checked
                self.set_check_state(next_state)
                self.toggled.emit(next_state)
                event.accept()
                return
        super().mousePressEvent(event)

    def _checkbox_rect_for_section(self, rect):
        indicator = self.style().pixelMetric(QStyle.PM_IndicatorWidth)
        x = rect.x() + (rect.width() - indicator) // 2
        y = rect.y() + (rect.height() - indicator) // 2
        return QRect(x, y, indicator, indicator)


class DeviceTableView(QTableView):
    """Custom table view for devices"""
    
    double_clicked = Signal(object)
    context_menu_requested = Signal(object, QMenu)
    
    def __init__(self, device_manager):
        """Initialize the view"""
        super().__init__()
        
        self.device_manager = device_manager
        self._context_menu_actions = []  # List of (name, callback, priority) tuples
        self._ignore_selection_changes = False  # Flag to prevent recursive selection updates
        self._group_list = []
        self._group_filter_name = None
        self._advanced_filter_state = {"logic": "AND", "rules": []}
        self._advanced_filter_dialog = None
        
        # Create and set the model
        self.table_model = DeviceTableModel(self.device_manager)
        
        # Create a custom proxy model for filtering and sorting
        self.proxy_model = IPSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Filter on all columns
        
        # Set the proxy model
        self.setModel(self.proxy_model)
        self.proxy_model.modelReset.connect(self._update_header_checkbox_state)
        self.proxy_model.rowsInserted.connect(lambda *_: self._update_header_checkbox_state())
        self.proxy_model.rowsRemoved.connect(lambda *_: self._update_header_checkbox_state())
        self.table_model.layoutChanged.connect(self.proxy_model.reset_ip_column)
        self.table_model.layoutChanged.connect(lambda: self.horizontalHeader().resizeSection(0, 28))
        
        # Set up the view
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        # Keep row heights uniform for smoother resizing on large tables.
        if hasattr(self, "setUniformRowHeights"):
            self.setUniformRowHeights(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Set up the horizontal header with a master selection checkbox
        header = _SelectionHeader(Qt.Horizontal, self)
        self.setHorizontalHeader(header)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setStretchLastSection(True)
        header.resizeSection(0, 28)
        header.setSortIndicator(1, Qt.AscendingOrder)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)
        header.toggled.connect(self._on_header_checkbox_toggled)
        header.sortIndicatorChanged.connect(self._save_sort_state)
        
        # Filter bar: Filter text, Add filter (icon-only, small), Group. Enter initiates search.
        self.filter_widget = QWidget()
        filter_layout = QHBoxLayout(self.filter_widget)
        filter_layout.setContentsMargins(5, 5, 5, 5)
        filter_layout.setSpacing(8)

        search_label = QLabel("Filter:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            'e.g. hostname contains "web" AND status = Active — press Enter to search'
        )
        self.search_edit.setToolTip(
            "Type a query and press Enter to search. Or use the filter icon to build visually. "
            "Examples: hostname = \"server01\"; tags contains any [\"production\",\"critical\"]."
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(lambda: self._on_filter_bar_changed(self.search_edit.text()))
        self.search_edit.textChanged.connect(self._on_filter_bar_changed)
        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.search_edit, 1)

        # Inline filter button: same style as device tree expand/collapse (12×12 icon, 18×18 button)
        add_filter_btn = QToolButton()
        add_filter_btn.setAutoRaise(True)
        add_filter_btn.setProperty("iconOnlyInline", "true")
        add_filter_btn.setToolTip("Build filters visually; search bar updates to match")
        _filter_icon_path = os.path.join(os.path.dirname(__file__), "resources", "icons", "filter_list.svg")
        if os.path.isfile(_filter_icon_path):
            add_filter_btn.setIcon(QIcon(_filter_icon_path))
        else:
            add_filter_btn.setIcon(material_icon("filter_list", self))
        add_filter_btn.setIconSize(QSize(12, 12))
        add_filter_btn.setFixedSize(18, 18)
        add_filter_btn.clicked.connect(self.show_advanced_filter_dialog)
        filter_layout.addWidget(add_filter_btn)

        group_filter_label = QLabel("Group:")
        self.group_filter_combo = QComboBox()
        self.group_filter_combo.setMinimumWidth(150)
        self.group_filter_combo.setToolTip("Filter devices by group")
        self.group_filter_combo.currentIndexChanged.connect(self._on_group_filter_combo_changed)
        self.group_filter_combo.addItem("All Devices", None)
        filter_layout.addWidget(group_filter_label)
        filter_layout.addWidget(self.group_filter_combo)
        
        # Connect signals
        self.clicked.connect(self.on_item_clicked)
        self.doubleClicked.connect(self.on_item_double_clicked)
        self.customContextMenuRequested.connect(self.on_context_menu)
        self.selectionModel().selectionChanged.connect(self.on_selection_model_changed)
        
        # Connect to device manager signals for group changes
        self.device_manager.group_added.connect(self._on_group_data_changed)
        self.device_manager.group_removed.connect(self._on_group_data_changed)
        self.device_manager.group_changed.connect(self._on_group_data_changed)
        self.device_manager.selection_changed.connect(self.on_manager_selection_changed)
        self.refresh_group_combo()

        # Apply user interface preferences from config if available
        self._apply_ui_preferences()
        self._restore_table_state()
        
        # Register default context menu actions
        self.register_context_menu_action("Add Device", self._on_action_add_device, 10)
        self.register_context_menu_action("Import Devices...", self._on_action_import_devices, 20)
        self.register_context_menu_action("Edit Properties", self._on_action_edit_properties, 200)
        self.register_context_menu_action("Add to Group", self._on_action_add_to_group, 300)
        self.register_context_menu_action("Create New Group", self._on_action_create_group, 310)
        self.register_context_menu_action("Deduplicate Devices", self.show_deduplicate_dialog, 350)
        self.register_context_menu_action("Select All", self._on_action_select_all, 400)
        self.register_context_menu_action("Deselect All", self._on_action_deselect_all, 410)
        self.register_context_menu_action("Delete", self._on_action_delete, 900)

        app = QApplication.instance()
        config = getattr(app, "config", None)
        if config and hasattr(config, "config_changed"):
            config.config_changed.connect(self._apply_ui_preferences)

    def _apply_ui_preferences(self):
        """Apply UI preferences like row height from configuration."""
        app = QApplication.instance()
        config = getattr(app, "config", None)
        row_height = 22
        if config:
            row_height = config.get("ui.row_height", row_height)
        self.verticalHeader().setDefaultSectionSize(row_height)
        
    def refresh(self):
        """Refresh the device table view and its components"""
        # Refresh the device data in the model
        self.table_model.refresh_devices()
        # Reset selection
        self.clearSelection()
        self._update_header_checkbox_state()
    
    def refresh_group_combo(self):
        """Refresh group-related state for filtering and update the combo box."""
        groups = [
            group for group in self.device_manager.get_groups()
            if group != self.device_manager.root_group
        ]
        self._group_list = groups
        
        # Update the combo box
        current_text = self.group_filter_combo.currentText()
        self.group_filter_combo.blockSignals(True)
        self.group_filter_combo.clear()
        self.group_filter_combo.addItem("All Devices", None)
        for group in groups:
            self.group_filter_combo.addItem(group.name, group)
        self.group_filter_combo.blockSignals(False)
        
        # Restore previous selection if it still exists
        if self._group_filter_name:
            index = self.group_filter_combo.findText(self._group_filter_name)
            if index >= 0:
                self.group_filter_combo.setCurrentIndex(index)
            else:
                # Group was removed, clear filter
                self.set_group_filter(None)
                self.group_filter_combo.setCurrentIndex(0)
        else:
            # No filter active, ensure "All Devices" is selected
            self.group_filter_combo.setCurrentIndex(0)
    
    def _on_filter_bar_changed(self, text):
        """Apply filter from the filter bar. Parses power-user text, field:value, or plain search."""
        all_headers = ["Any Column"] + self.table_model.get_all_headers()
        simple, advanced = parse_filter_syntax(text, all_headers)
        if advanced:
            self._advanced_filter_state = advanced
            self.proxy_model.setFilterFixedString("")
            self.proxy_model.set_advanced_filter(advanced)
        else:
            self._advanced_filter_state = {"logic": "AND", "rules": []}
            self.proxy_model.set_advanced_filter(None)
            self.proxy_model.setFilterFixedString(simple or "")
        self._update_header_checkbox_state()

    def filter_table(self, text):
        """Filter the table based on the text (legacy / programmatic). Prefer _on_filter_bar_changed."""
        self._on_filter_bar_changed(text)
        
    def filter_by_group(self, index):
        """Filter the table by selected group"""
        if isinstance(index, int):
            group = None
            if index > 0 and index - 1 < len(self._group_list):
                group = self._group_list[index - 1]
            self._apply_group_filter(group)
            return
        self._apply_group_filter(index)

    def set_group_filter(self, group):
        """Set the group filter programmatically"""
        self._apply_group_filter(group)

    def _on_group_data_changed(self, *_args):
        """Keep group filter state in sync with group changes."""
        self.refresh_group_combo()

    def _apply_group_filter(self, group):
        """Apply a group filter and persist it."""
        if group is None:
            self.table_model.filter_by_group(None)
            self._group_filter_name = None
        else:
            self.table_model.filter_by_group(group)
            self._group_filter_name = group.name

        # Update combo box selection without triggering signal
        self.group_filter_combo.blockSignals(True)
        if group is None:
            self.group_filter_combo.setCurrentIndex(0)
        else:
            index = self.group_filter_combo.findText(group.name)
            if index >= 0:
                self.group_filter_combo.setCurrentIndex(index)
        self.group_filter_combo.blockSignals(False)

        self._save_group_filter_state(self._group_filter_name)
        self._update_header_checkbox_state()

    def _on_group_filter_combo_changed(self, index):
        """Handle group filter combo box selection change."""
        if index < 0:
            return
        group = self.group_filter_combo.itemData(index)
        self._apply_group_filter(group)

    def _save_group_filter_state(self, group_name):
        settings = self._get_workspace_settings()
        settings.setValue("group_filter", group_name or "")
            
    def show_column_selector(self):
        """Show a dialog to select which columns to display"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Columns")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Get all available columns from the model
        available_standard_columns = self.table_model._all_headers
        available_plugin_columns = [header for header, _, _ in self.table_model._plugin_columns]
        available_custom_columns = self.table_model._custom_prop_headers
        visible_columns = self.table_model.get_visible_headers()
        
        # Create sections for different column types
        if available_standard_columns:
            standard_group = QGroupBox("Standard Columns")
            standard_layout = QVBoxLayout(standard_group)
            
            standard_checkboxes = []
            for column in available_standard_columns:
                checkbox = QCheckBox(column)
                checkbox.setChecked(column in visible_columns)
                standard_checkboxes.append((column, checkbox))
                standard_layout.addWidget(checkbox)
                
            layout.addWidget(standard_group)
        
        if available_plugin_columns:
            plugin_group = QGroupBox("Plugin Columns")
            plugin_layout = QVBoxLayout(plugin_group)
            
            plugin_checkboxes = []
            for column in available_plugin_columns:
                checkbox = QCheckBox(column)
                checkbox.setChecked(column in visible_columns)
                plugin_checkboxes.append((column, checkbox))
                plugin_layout.addWidget(checkbox)
                
            layout.addWidget(plugin_group)
            
        if available_custom_columns:
            custom_group = QGroupBox("Custom Property Columns")
            custom_layout = QVBoxLayout(custom_group)
            
            custom_checkboxes = []
            for column in available_custom_columns:
                checkbox = QCheckBox(column)
                checkbox.setChecked(column in visible_columns)
                custom_checkboxes.append((column, checkbox))
                custom_layout.addWidget(checkbox)
                
            layout.addWidget(custom_group)
        
        # Combine all checkboxes
        all_checkboxes = []
        if 'standard_checkboxes' in locals():
            all_checkboxes.extend(standard_checkboxes)
        if 'plugin_checkboxes' in locals():
            all_checkboxes.extend(plugin_checkboxes)
        if 'custom_checkboxes' in locals():
            all_checkboxes.extend(custom_checkboxes)
            
        # Add buttons
        button_layout = QHBoxLayout()
        
        select_all = QPushButton("Select All")
        select_none = QPushButton("Select None")
        reset = QPushButton("Reset to Default")
        
        button_layout.addWidget(select_all)
        button_layout.addWidget(select_none)
        button_layout.addWidget(reset)
        
        layout.addLayout(button_layout)
        
        # Connect button signals
        def on_select_all():
            for _, checkbox in all_checkboxes:
                checkbox.setChecked(True)
                
        def on_select_none():
            for _, checkbox in all_checkboxes:
                checkbox.setChecked(False)
                
        def on_reset():
            # Default columns
            default_columns = ["Alias", "Hostname", "IP Address", "MAC Address", "Status", "Tags", "Groups"]
            for column, checkbox in all_checkboxes:
                checkbox.setChecked(column in default_columns)
                
        select_all.clicked.connect(on_select_all)
        select_none.clicked.connect(on_select_none)
        reset.clicked.connect(on_reset)
        
        # Add dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        if dialog.exec():
            # Get selected columns
            selected_columns = [column for column, checkbox in all_checkboxes if checkbox.isChecked()]
            
            # Ensure at least one column is visible
            if not selected_columns:
                QMessageBox.warning(self, "Column Selection", "At least one column must be visible.")
                return
                
            # Update model
            self.table_model.set_visible_headers(selected_columns)
            self._save_column_visibility(selected_columns)
            self._update_header_checkbox_state()
            
    def show_deduplicate_dialog(self):
        """Show dialog to deduplicate devices based on a selected column"""
        # Check if there are enough devices to deduplicate
        current_devices = self.table_model._devices
        if len(current_devices) < 2:
            QMessageBox.information(
                self,
                "Deduplication",
                "At least two devices are required for deduplication."
            )
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Deduplicate Devices")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel("Select a column to identify duplicate devices. Devices with the same value in this column will be detected as duplicates.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Column selection
        form_layout = QFormLayout()
        
        # Get column options for deduplication
        column_combo = QComboBox()
        
        # Add standard columns that make sense for deduplication
        dedup_columns = ["MAC Address", "IP Address", "Hostname"]
        
        # Also add any custom columns that might be useful
        all_headers = (
            self.table_model._headers + 
            self.table_model._custom_prop_headers + 
            [header for header, _, _ in self.table_model._plugin_columns]
        )
        
        # Add unique columns to the combo box
        unique_columns = []
        for column in dedup_columns + all_headers:
            if column not in unique_columns:
                unique_columns.append(column)
                column_combo.addItem(column)
        
        # Only allow meaningful columns for deduplication
        if column_combo.count() == 0:
            QMessageBox.warning(
                self,
                "Deduplication",
                "No suitable columns found for deduplication."
            )
            return
            
        form_layout.addRow("Deduplicate by:", column_combo)
        layout.addLayout(form_layout)
        
        # Options for handling duplicates
        options_group = QGroupBox("Duplicate Handling Options")
        options_layout = QVBoxLayout(options_group)
        
        select_radio = QRadioButton("Select duplicates (for manual handling)")
        select_radio.setChecked(True)
        options_layout.addWidget(select_radio)
        
        merge_radio = QRadioButton("Merge duplicates (combine properties and keep one device)")
        options_layout.addWidget(merge_radio)
        
        delete_radio = QRadioButton("Delete duplicates (keep first occurrence, delete others)")
        options_layout.addWidget(delete_radio)
        
        layout.addWidget(options_group)
        
        # Create a preview section
        preview_group = QGroupBox("Preview (click Scan to find duplicates)")
        layout.addWidget(preview_group)
        
        preview_layout = QVBoxLayout(preview_group)
        
        # Table for displaying duplicates
        duplicates_table = QTableWidget()
        duplicates_table.setColumnCount(3)
        duplicates_table.setHorizontalHeaderLabels(["Keep", "Value", "Duplicates"])
        duplicates_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        duplicates_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        duplicates_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        preview_layout.addWidget(duplicates_table)
        
        # Store scan results
        scan_results = {}
        
        # Scan for duplicates
        def scan_for_duplicates():
            selected_column = column_combo.currentText()
            
            # Find the corresponding key for the selected column
            column_idx = self.table_model._headers.index(selected_column) if selected_column in self.table_model._headers else -1
            
            # Default to using the column name as the key
            key = selected_column.lower().replace(" ", "_")
            
            # Try to find an exact match in the column keys
            if column_idx >= 0 and column_idx < len(self.table_model._column_keys):
                key = self.table_model._column_keys[column_idx]
            
            # Group devices by the selected column value
            devices_by_value = {}
            
            # Process each device
            for device in current_devices:
                # Get the value for the selected column
                if key == "groups":
                    # Special handling for groups
                    value = ", ".join(self.table_model._device_groups.get(device.id, []))
                else:
                    # Regular property
                    value = device.get_property(key, "")
                    
                    # Handle tag lists
                    if key == "tags" and isinstance(value, list):
                        value = ", ".join(value)
                
                # Skip empty values
                if not value:
                    continue
                    
                # Add to the group of devices with this value
                if value not in devices_by_value:
                    devices_by_value[value] = []
                devices_by_value[value].append(device)
            
            # Filter to only include values with multiple devices (duplicates)
            duplicate_values = {v: devices for v, devices in devices_by_value.items() if len(devices) > 1}
            
            # Update the duplicates table
            duplicates_table.setRowCount(len(duplicate_values))
            
            # Save the scan results
            scan_results.clear()
            scan_results.update(duplicate_values)
            
            # Populate the table
            for row, (value, devices) in enumerate(duplicate_values.items()):
                # Create a checkbox for keeping the first device
                checkbox = QCheckBox()
                checkbox.setChecked(True)
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                duplicates_table.setCellWidget(row, 0, checkbox_widget)
                
                # Value column
                value_item = QTableWidgetItem(value)
                duplicates_table.setItem(row, 1, value_item)
                
                # Duplicates column - show count and aliases
                device_aliases = [d.get_property("alias", "Unnamed") for d in devices]
                duplicates_item = QTableWidgetItem(f"{len(devices)} devices: {', '.join(device_aliases)}")
                duplicates_table.setItem(row, 2, duplicates_item)
                
                # Store devices in the item for later access
                duplicates_item.setData(Qt.UserRole, devices)
                
            # Update action button state
            action_button.setEnabled(len(duplicate_values) > 0)
            
            # Show results summary
            total_duplicates = sum(len(devices) - 1 for devices in duplicate_values.values())
            results_label.setText(f"Found {len(duplicate_values)} duplicate groups with a total of {total_duplicates} duplicate devices.")
            
        # Button to scan for duplicates
        scan_button = QPushButton("Scan for Duplicates")
        scan_button.clicked.connect(scan_for_duplicates)
        preview_layout.addWidget(scan_button)
        
        # Results label
        results_label = QLabel("Click Scan to find duplicates")
        preview_layout.addWidget(results_label)
        
        # Action button
        action_button = QPushButton("Apply")
        action_button.setEnabled(False)
        
        # Handle the action based on selected option
        def handle_action():
            # Get all rows with checked "Keep" checkbox
            rows_to_process = []
            for row in range(duplicates_table.rowCount()):
                checkbox_widget = duplicates_table.cellWidget(row, 0)
                if checkbox_widget:
                    checkbox = checkbox_widget.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked():
                        rows_to_process.append(row)
            
            if not rows_to_process:
                QMessageBox.information(
                    dialog,
                    "No Action",
                    "No duplicate groups selected for processing."
                )
                return
                
            # Get the selected action
            action = "select"
            if merge_radio.isChecked():
                action = "merge"
            elif delete_radio.isChecked():
                action = "delete"
                
            # Process each row
            if action == "select":
                # Select all duplicate devices
                all_duplicates = []
                for row in rows_to_process:
                    # Get devices from the item data
                    devices_item = duplicates_table.item(row, 2)
                    devices = devices_item.data(Qt.UserRole)
                    
                    # Skip the first device (keep) and select all others (duplicates)
                    for device in devices[1:]:
                        all_duplicates.append(device)
                        
                # Select these devices in the table
                self.device_manager.clear_selection()
                for device in all_duplicates:
                    self.device_manager.select_device(device)
                
                # Close the dialog
                dialog.accept()
                
                # Show message
                QMessageBox.information(
                    self,
                    "Duplicates Selected",
                    f"Selected {len(all_duplicates)} duplicate devices. You can now edit or delete them."
                )
                
            elif action == "merge":
                # Merge duplicate properties into the first device
                groups_processed = 0
                devices_merged = 0
                
                for row in rows_to_process:
                    # Get devices from the item data
                    devices_item = duplicates_table.item(row, 2)
                    devices = devices_item.data(Qt.UserRole)
                    
                    if len(devices) <= 1:
                        continue
                        
                    # Keep the first device, merge data from others
                    keep_device = devices[0]
                    duplicate_devices = devices[1:]
                    
                    # For each duplicate, merge properties and then delete it
                    for dup_device in duplicate_devices:
                        # Merge non-empty properties
                        for key, value in dup_device.get_properties().items():
                            # Skip empty values and ID
                            if key == "id" or not value:
                                continue
                                
                            # Handle special cases
                            if key == "tags":
                                # Merge tags (add any missing)
                                keep_tags = keep_device.get_property("tags", [])
                                if not isinstance(keep_tags, list):
                                    keep_tags = [keep_tags] if keep_tags else []
                                    
                                dup_tags = value if isinstance(value, list) else [value] if value else []
                                
                                # Add new tags
                                for tag in dup_tags:
                                    if tag not in keep_tags:
                                        keep_tags.append(tag)
                                        
                                # Update tags
                                keep_device.set_property("tags", keep_tags)
                            else:
                                # Only copy if keep device doesn't have the property
                                if not keep_device.get_property(key, ""):
                                    keep_device.set_property(key, value)
                        
                        # Now remove the duplicate device
                        self.device_manager.remove_device(dup_device)
                        devices_merged += 1
                        
                    groups_processed += 1
                
                # Close the dialog
                dialog.accept()
                
                # Show message
                QMessageBox.information(
                    self,
                    "Duplicates Merged",
                    f"Merged {devices_merged} duplicate devices across {groups_processed} groups."
                )
                
            elif action == "delete":
                # Keep first device, delete others
                groups_processed = 0
                devices_deleted = 0
                
                for row in rows_to_process:
                    # Get devices from the item data
                    devices_item = duplicates_table.item(row, 2)
                    devices = devices_item.data(Qt.UserRole)
                    
                    if len(devices) <= 1:
                        continue
                        
                    # Keep the first device, delete others
                    duplicate_devices = devices[1:]
                    
                    # Delete duplicates
                    for dup_device in duplicate_devices:
                        self.device_manager.remove_device(dup_device)
                        devices_deleted += 1
                        
                    groups_processed += 1
                
                # Close the dialog
                dialog.accept()
                
                # Show message
                QMessageBox.information(
                    self,
                    "Duplicates Deleted",
                    f"Moved {devices_deleted} duplicate devices to the recycle bin across {groups_processed} groups."
                )
        
        action_button.clicked.connect(handle_action)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(scan_button)
        button_layout.addStretch()
        button_layout.addWidget(action_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Show the dialog
        dialog.exec()
    
    def get_container_widget(self):
        """Get a widget containing the table and filter controls"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        layout.addWidget(self.filter_widget)
        layout.addWidget(self)
        
        return container

    def show_advanced_filter_dialog(self):
        """Show the advanced filtering dialog."""
        presets = self._load_filter_presets()
        fields = ["Any Column"] + self.table_model.get_all_headers()

        if self._advanced_filter_dialog:
            try:
                self._advanced_filter_dialog.close()
            except Exception:
                pass

        dialog = AdvancedFilterDialog(
            fields=fields,
            presets=presets,
            current_state=self._advanced_filter_state,
            on_save_preset=self._save_filter_preset,
            on_delete_preset=self._delete_filter_preset,
            parent=self,
        )
        def on_apply(state):
            self._apply_advanced_filter_state(state)
            syntax = filter_state_to_syntax(state, _default_header_to_short())
            self.search_edit.blockSignals(True)
            try:
                self.search_edit.setText(syntax)
            finally:
                self.search_edit.blockSignals(False)

        dialog.apply_requested.connect(on_apply)
        dialog.open()
        self._advanced_filter_dialog = dialog

    def _apply_advanced_filter_state(self, state, save=True):
        """Apply advanced filter state (tree or legacy) to the proxy model."""
        state = state or {"logic": "AND", "rules": []}
        self._advanced_filter_state = state
        self.proxy_model.set_advanced_filter(state)
        if save:
            self._save_filter_state(state)
        self._update_header_checkbox_state()

    def _on_header_context_menu(self, position):
        """Show a context menu for column header actions."""
        menu = QMenu(self)
        menu.addAction("Edit Columns...", self.show_column_selector)
        menu.exec(self.horizontalHeader().mapToGlobal(position))

    def _on_header_checkbox_toggled(self, state):
        """Select or deselect all visible rows via the header checkbox."""
        if state == Qt.Checked:
            self._on_action_select_all()
        else:
            self._on_action_deselect_all()

    def _update_header_checkbox_state(self):
        """Sync the header checkbox with the current selection state."""
        header = self.horizontalHeader()
        if not isinstance(header, _SelectionHeader):
            return

        row_count = self.proxy_model.rowCount()
        if row_count == 0:
            header.set_check_state(Qt.Unchecked)
            return

        selected_devices = set(self.device_manager.get_selected_devices())
        selected_visible = 0
        for row in range(row_count):
            device = self.proxy_model.index(row, 0).data(Qt.UserRole)
            if device in selected_devices:
                selected_visible += 1

        if selected_visible == 0:
            header.set_check_state(Qt.Unchecked)
        elif selected_visible == row_count:
            header.set_check_state(Qt.Checked)
        else:
            header.set_check_state(Qt.PartiallyChecked)

    def _get_visible_devices(self):
        """Return devices for currently visible rows in the proxy model."""
        devices = []
        for row in range(self.proxy_model.rowCount()):
            device = self.proxy_model.index(row, 0).data(Qt.UserRole)
            if device:
                devices.append(device)
        return devices

    def _get_highlighted_devices(self):
        """Return devices for currently highlighted rows."""
        devices = []
        for index in self.selectionModel().selectedRows():
            device = index.data(Qt.UserRole)
            if device:
                devices.append(device)
        return devices

    def get_selected_devices(self):
        """Return checked devices, or highlighted ones if none are checked."""
        checked_devices = self.device_manager.get_selected_devices()
        if checked_devices:
            return checked_devices.copy()
        return self._get_highlighted_devices()

    def _set_check_state_for_indexes(self, indices, state):
        """Set checkbox state for a list of proxy indexes."""
        for index in indices:
            if not index.isValid():
                continue
            proxy_index = index.sibling(index.row(), 0)
            source_index = self.proxy_model.mapToSource(proxy_index)
            self.table_model.setData(source_index, state, Qt.CheckStateRole)

    def _toggle_checkbox_for_index(self, index):
        """Toggle checkbox state for the row containing the given index."""
        if not index.isValid():
            return

        proxy_index = index.sibling(index.row(), 0)
        source_index = self.proxy_model.mapToSource(proxy_index)
        current_state = source_index.data(Qt.CheckStateRole)
        next_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
        self.table_model.setData(source_index, next_state, Qt.CheckStateRole)

    def keyPressEvent(self, event):
        """Toggle checkbox selection using the spacebar."""
        if event.key() == Qt.Key_Space:
            highlighted = self.selectionModel().selectedRows()
            if highlighted:
                # Toggle all highlighted rows in one action.
                states = [
                    self.proxy_model.mapToSource(index.sibling(index.row(), 0)).data(Qt.CheckStateRole)
                    for index in highlighted
                    if index.isValid()
                ]
                next_state = Qt.Unchecked if states and all(state == Qt.Checked for state in states) else Qt.Checked
                self._set_check_state_for_indexes(highlighted, next_state)
            else:
                current = self.currentIndex()
                if current.isValid():
                    self._toggle_checkbox_for_index(current)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Toggle checkbox selection on click without altering row highlight."""
        if event.button() == Qt.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid() and index.column() == 0:
                self._toggle_checkbox_for_index(index)
                self.setCurrentIndex(index)
                event.accept()
                return
        super().mousePressEvent(event)

    def _get_workspace_settings(self):
        """Get QSettings for the current workspace device table state."""
        workspace_name = self.device_manager.current_workspace
        workspace_dir = os.path.join(self.device_manager.workspaces_dir, workspace_name)
        settings_dir = os.path.join(workspace_dir, "settings")
        os.makedirs(settings_dir, exist_ok=True)
        return QSettings(os.path.join(settings_dir, "device_table.ini"), QSettings.IniFormat)

    def _restore_table_state(self):
        """Restore column visibility and filters for the workspace."""
        settings = self._get_workspace_settings()

        visible_headers = settings.value("visible_headers", None)
        if visible_headers:
            if isinstance(visible_headers, str):
                visible_headers = [visible_headers]
            self.table_model.set_visible_headers(visible_headers)
        else:
            app = QApplication.instance()
            config = getattr(app, "config", None)
            default_keys = []
            applied_defaults = False
            if config:
                default_keys = config.get("ui.device_table.default_columns", []) or []
            if default_keys:
                key_to_header = dict(zip(self.table_model._all_column_keys, self.table_model._all_headers))
                default_headers = [key_to_header.get(key) for key in default_keys]
                default_headers = [header for header in default_headers if header]
                if default_headers:
                    self.table_model.set_visible_headers(default_headers)
                    applied_defaults = True
            if not applied_defaults:
                fallback_headers = ["Alias", "Hostname", "IP Address", "MAC Address", "Status", "Tags", "Groups"]
                self.table_model.set_visible_headers(fallback_headers)

        group_name = settings.value("group_filter", "")
        if group_name:
            group = self.device_manager.get_group(group_name)
            if group:
                self._apply_group_filter(group)

        # Filter bar starts empty on load; do not restore saved filter state
        self._advanced_filter_state = {"logic": "AND", "rules": []}
        self.proxy_model.set_advanced_filter(None)
        self.proxy_model.setFilterFixedString("")
        self.search_edit.blockSignals(True)
        try:
            self.search_edit.clear()
        finally:
            self.search_edit.blockSignals(False)
        self._update_header_checkbox_state()

        sort_column = settings.value("sort_column", None)
        sort_order = settings.value("sort_order", None)
        sort_header = settings.value("sort_header", "")
        if sort_column is not None and sort_order is not None:
            try:
                sort_column = int(sort_column)
                sort_order = Qt.SortOrder(int(sort_order))
                if 0 <= sort_column < self.proxy_model.columnCount():
                    self.sortByColumn(sort_column, sort_order)
            except Exception:
                logger.warning("Failed to restore sort state", exc_info=True)
        elif sort_header:
            column_index = self.table_model.get_column_index(sort_header)
            if column_index >= 0:
                self.sortByColumn(column_index, Qt.AscendingOrder)

    def restore_workspace_state(self):
        """Public wrapper to restore per-workspace table state."""
        self._restore_table_state()

    def _save_column_visibility(self, headers):
        settings = self._get_workspace_settings()
        settings.setValue("visible_headers", headers)

    def _save_sort_state(self, column, order):
        """Persist sort column and order for the workspace."""
        settings = self._get_workspace_settings()
        order_value = int(order.value) if hasattr(order, "value") else int(order)
        settings.setValue("sort_column", int(column))
        settings.setValue("sort_order", order_value)
        header_name = ""
        if column > 0:
            header_name = self.table_model.get_data_headers()[column - 1]
        settings.setValue("sort_header", header_name)

    def _load_filter_state(self):
        settings = self._get_workspace_settings()
        raw_state = settings.value("advanced_filter_state", "")
        if not raw_state:
            return None
        try:
            state = json.loads(raw_state)
            if isinstance(state, dict):
                return state
        except Exception:
            logger.warning("Failed to load advanced filter state", exc_info=True)
        return None

    def _save_filter_state(self, state):
        settings = self._get_workspace_settings()
        settings.setValue("advanced_filter_state", json.dumps(state))

    def _load_filter_presets(self):
        settings = self._get_workspace_settings()
        raw_presets = settings.value("advanced_filter_presets", "")
        if not raw_presets:
            return {}
        try:
            presets = json.loads(raw_presets)
            if isinstance(presets, dict):
                return presets
        except Exception:
            logger.warning("Failed to load filter presets", exc_info=True)
        return {}

    def _save_filter_presets(self, presets):
        settings = self._get_workspace_settings()
        settings.setValue("advanced_filter_presets", json.dumps(presets))

    def _save_filter_preset(self, name, state):
        presets = self._load_filter_presets()
        presets[name] = state
        self._save_filter_presets(presets)

    def _delete_filter_preset(self, name):
        presets = self._load_filter_presets()
        if name in presets:
            del presets[name]
            self._save_filter_presets(presets)
     
    def register_context_menu_action(self, name, callback, priority=500):
        """
        Register a context menu action
        
        Args:
            name: Name of the action (displayed in menu)
            callback: Function to call when action is selected
                     Should accept (device) as argument, or None for table actions
            priority: Priority of the action (lower values appear first)
        
        Returns:
            bool: True if registered successfully
        """
        # Check if action with this name already exists
        for i, (action_name, _, _) in enumerate(self._context_menu_actions):
            if action_name == name:
                # Replace the callback
                self._context_menu_actions[i] = (name, callback, priority)
                return True
        
        # Add new action
        self._context_menu_actions.append((name, callback, priority))
        # Sort by priority
        self._context_menu_actions.sort(key=lambda x: x[2])
        return True
     
    def unregister_context_menu_action(self, name):
        """
        Unregister a context menu action
        
        Args:
            name: Name of the action to remove
        
        Returns:
            bool: True if unregistered successfully
        """
        for i, (action_name, _, _) in enumerate(self._context_menu_actions):
            if action_name == name:
                del self._context_menu_actions[i]
                return True
        return False

    def on_item_clicked(self, index):
        """Handle item clicked"""
        if not index.isValid():
            return
            
        device = index.data(Qt.UserRole)
        if not device:
            return
            
        # Row highlight is navigation only; checkbox state controls actual selection.
        modifiers = QApplication.keyboardModifiers()
        logger.debug(f"Item clicked with modifiers: {modifiers}")
    
    def on_item_double_clicked(self, index):
        """Handle item double clicked"""
        if not index.isValid():
            return

        self._toggle_checkbox_for_index(index)
        device = index.data(Qt.UserRole)
        if device:
            self.double_clicked.emit(device)
    
    def device_properties_dialog(self, device=None):
        """
        Show a dialog for adding or editing device properties
        
        Args:
            device: Device to edit, or None to create a new device
        
        Returns:
            The modified or new device if accepted, None if cancelled
        """
        is_new = device is None
        dialog = QDialog()
        dialog.setWindowTitle(f"{'Add' if is_new else 'Edit'} Device Properties")
        dialog.resize(600, 400)  # Reduce initial height from 500 to 400
        
        layout = QVBoxLayout(dialog)
        
        # Create tab widget for organizing properties
        tab_widget = QTabWidget()
        
        # Function to create a handler for the "Show in Table" button
        def make_show_in_table_handler(property_key):
            def handle_show_in_table():
                # Get current visible headers
                table_view = self
                table_model = table_view.table_model
                visible_headers = table_model.get_visible_headers()
                
                # Add this property's header if not already visible
                header_name = property_key.replace('_', ' ').title()
                if header_name not in visible_headers:
                    new_headers = visible_headers + [header_name]
                    table_model.set_visible_headers(new_headers)
                    self._save_column_visibility(new_headers)
                    QMessageBox.information(
                        dialog,
                        "Column Added",
                        f"'{header_name}' column has been added to the device table."
                    )
                else:
                    QMessageBox.information(
                        dialog,
                        "Column Already Visible",
                        f"'{header_name}' column is already visible in the device table."
                    )
            return handle_show_in_table
        
        # Basic tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_form = QFormLayout()
        
        # Core property fields
        alias_edit = QLineEdit(device.get_property("alias", "") if device else "")
        alias_edit.setPlaceholderText("Device name/alias")
        basic_form.addRow("Alias:", alias_edit)
        
        hostname_edit = QLineEdit(device.get_property("hostname", "") if device else "")
        hostname_edit.setPlaceholderText("Enter hostname or FQDN")
        basic_form.addRow("Hostname:", hostname_edit)
        
        ip_edit = QLineEdit(device.get_property("ip_address", "") if device else "")
        ip_edit.setPlaceholderText("Enter IP address")
        basic_form.addRow("IP Address:", ip_edit)
        
        mac_edit = QLineEdit(device.get_property("mac_address", "") if device else "")
        mac_edit.setPlaceholderText("Enter MAC address")
        basic_form.addRow("MAC Address:", mac_edit)
        
        status_combo = QComboBox()
        status_values = ["unknown", "up", "down", "warning", "error", "maintenance"]
        status_combo.addItems(status_values)
        current_status = device.get_property("status", "unknown") if device else "unknown"
        if current_status in status_values:
            status_combo.setCurrentText(current_status)
        basic_form.addRow("Status:", status_combo)
        
        # Add the form to the basic tab
        basic_layout.addLayout(basic_form)
        tab_widget.addTab(basic_tab, "Basic")
        
        # Notes tab
        notes_tab = QWidget()
        notes_layout = QVBoxLayout(notes_tab)
        notes_edit = QTextEdit(device.get_property("notes", "") if device else "")
        notes_edit.setPlaceholderText("Enter notes about this device")
        notes_layout.addWidget(notes_edit)
        tab_widget.addTab(notes_tab, "Notes")
        
        # Tags tab
        tags_tab = QWidget()
        tags_layout = QVBoxLayout(tags_tab)
        
        # Add a label for the tag list
        tags_layout.addWidget(QLabel("Add these tags to all selected devices:"))

        # Add a filter for tags
        tags_filter_layout = QHBoxLayout()
        tags_filter_label = QLabel("Filter:")
        tags_filter_edit = QLineEdit()
        tags_filter_edit.setPlaceholderText("Type to filter tags...")
        tags_filter_layout.addWidget(tags_filter_label)
        tags_filter_layout.addWidget(tags_filter_edit)
        tags_layout.addLayout(tags_filter_layout)

        # Tag list
        tags_list = QListWidget()
        tags_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Add existing tags if editing a device
        current_tags = device.get_property("tags", []) if device else []
        for tag in current_tags:
            item = QListWidgetItem(tag)
            tags_list.addItem(item)
        
        tags_layout.addWidget(tags_list)

        # Tag controls
        tags_control_layout = QHBoxLayout()
        new_tag = QLineEdit()
        new_tag.setPlaceholderText("New tag")
        add_tag_button = QPushButton("Add")
        remove_tag_button = QPushButton("Remove Selected")
        
        tags_control_layout.addWidget(new_tag)
        tags_control_layout.addWidget(add_tag_button)
        tags_control_layout.addWidget(remove_tag_button)
        
        tags_layout.addLayout(tags_control_layout)
        
        # Add tag function
        def add_tag():
            tag = new_tag.text().strip()
            if tag and not tags_list.findItems(tag, Qt.MatchExactly):
                tags_list.addItem(QListWidgetItem(tag))
                new_tag.clear()
                
        # Remove selected tags
        def remove_selected_tags():
            for item in reversed(tags_list.selectedItems()):
                row = tags_list.row(item)
                tags_list.takeItem(row)
        
        # Add tag filter function
        def filter_tags(text):
            filter_text = text.lower()
            for i in range(tags_list.count()):
                item = tags_list.item(i)
                item.setHidden(filter_text and filter_text not in item.text().lower())
                
        add_tag_button.clicked.connect(add_tag)
        remove_tag_button.clicked.connect(remove_selected_tags)
        tags_filter_edit.textChanged.connect(filter_tags)
        
        # Add enter key press to add tag
        def on_tag_return_pressed():
            if new_tag.text().strip():
                add_tag()
                
        new_tag.returnPressed.connect(on_tag_return_pressed)
        
        # Add tags tab to tab widget
        tab_widget.addTab(tags_tab, "Tags")
        
        # Custom properties tab
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        
        # Form layout for existing custom properties
        custom_props_layout = QFormLayout()
        custom_props = {}
        
        # Create a scroll area for custom properties
        custom_props_scroll = QScrollArea()
        custom_props_scroll.setWidgetResizable(True)
        custom_props_widget = QWidget()
        custom_props_widget.setLayout(custom_props_layout)
        custom_props_scroll.setWidget(custom_props_widget)
        custom_props_scroll.setMaximumHeight(200)  # Limit maximum height
        
        # Add existing custom properties if editing a device
        current_custom_props = []
        core_props = ["id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"]
        
        if device:
            for key, value in device.get_properties().items():
                if key not in core_props:
                    current_custom_props.append(key)
                    prop_layout = QHBoxLayout()
                    
                    # Property value field
                    edit = QLineEdit(str(value))
                    prop_layout.addWidget(edit)
                    custom_props[key] = edit
                    
                    # Add to table button
                    show_in_table_btn = QPushButton("Show in Table")
                    show_in_table_btn.setMaximumWidth(100)
                    show_in_table_btn.setToolTip("Add this property as a column in the device table")
                    prop_key = key  # Create a local copy of the key for the closure
                    
                    show_in_table_btn.clicked.connect(make_show_in_table_handler(prop_key))
                    prop_layout.addWidget(show_in_table_btn)
                    
                    custom_props_layout.addRow(f"{key}:", prop_layout)
        
        custom_layout.addWidget(custom_props_scroll)
        
        # Find common custom properties from other devices
        suggested_props = []
        if self.device_manager:
            # Collect custom properties from all devices
            for other_device in self.device_manager.get_devices():
                # Skip the current device
                if device and other_device.id == device.id:
                    continue
                
                for key, value in other_device.get_properties().items():
                    # Skip core properties and properties already on this device
                    if key not in core_props and key not in current_custom_props:
                        # Skip complex values
                        if not isinstance(value, (list, dict)):
                            suggested_props.append((key, str(value), other_device))
            
            # If we have suggestions, add them to the dialog
            if suggested_props:
                suggestions_group = QGroupBox("Suggested Properties")
                suggestions_layout = QVBoxLayout(suggestions_group)
                
                suggestions_label = QLabel("The following properties are used by other devices:")
                suggestions_label.setWordWrap(True)
                suggestions_layout.addWidget(suggestions_label)
                
                # Create a scroll area for the suggested properties
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setMaximumHeight(200)  # Limit maximum height
                
                # Create a table for suggested properties
                props_table = QTableWidget()
                props_table.setColumnCount(3)  # Checkbox, Property Name, Add Button
                props_table.setHorizontalHeaderLabels(["Use", "Property", "Add"])
                props_table.setRowCount(len(suggested_props))
                props_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
                props_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
                props_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
                props_table.verticalHeader().setVisible(False)
                props_table.setAlternatingRowColors(True)
                props_table.setShowGrid(True)
                props_table.setSelectionMode(QTableWidget.NoSelection)
                props_table.setFocusPolicy(Qt.NoFocus)
                props_table.setEditTriggers(QTableWidget.NoEditTriggers)
                
                # Set compact row height
                props_table.verticalHeader().setDefaultSectionSize(28)
                
                # Add suggested properties to the table
                checkbox_map = {}  # Map to store checkboxes by row
                button_map = {}    # Map to store buttons by row
                
                for row, (prop_key, prop_value, source_device) in enumerate(suggested_props):
                    # Checkbox column
                    checkbox = QCheckBox()
                    checkbox.setToolTip(f"Value from {source_device.get_property('alias', 'Unknown')}: {prop_value}")
                    checkbox_widget = QWidget()
                    checkbox_layout = QHBoxLayout(checkbox_widget)
                    checkbox_layout.addWidget(checkbox)
                    checkbox_layout.setAlignment(Qt.AlignCenter)
                    checkbox_layout.setContentsMargins(0, 0, 0, 0)
                    props_table.setCellWidget(row, 0, checkbox_widget)
                    checkbox_map[row] = checkbox
                    
                    # Property name column
                    name_item = QTableWidgetItem(f"{prop_key} ({source_device.get_property('alias', 'Unknown')})")
                    name_item.setToolTip(f"Value: {prop_value}")
                    name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                    props_table.setItem(row, 1, name_item)
                    
                    # Add button column
                    add_button = QPushButton("+")
                    add_button.setMaximumWidth(30)
                    add_button.setMaximumHeight(25)
                    add_button.setToolTip(f"Add this property with value: {prop_value}")
                    
                    # Store data for the button
                    prop_key_copy = prop_key
                    prop_value_copy = prop_value
                    
                    # Create widget to center the button
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.addWidget(add_button)
                    button_layout.setAlignment(Qt.AlignCenter)
                    button_layout.setContentsMargins(0, 0, 0, 0)
                    props_table.setCellWidget(row, 2, button_widget)
                    button_map[row] = add_button
                    
                    def make_add_handler(key, value, row):
                        def handle_add():
                            # Add the property if not already added
                            if key not in custom_props:
                                prop_layout = QHBoxLayout()
                                
                                # Property value field
                                edit = QLineEdit(value)
                                prop_layout.addWidget(edit)
                                custom_props[key] = edit
                                
                                # Add to table button
                                show_in_table_btn = QPushButton("Show in Table")
                                show_in_table_btn.setMaximumWidth(100)
                                show_in_table_btn.setToolTip("Add this property as a column in the device table")
                                
                                show_in_table_btn.clicked.connect(make_show_in_table_handler(key))
                                prop_layout.addWidget(show_in_table_btn)
                                
                                custom_props_layout.addRow(f"{key}:", prop_layout)
                                
                                # Disable the checkbox and button
                                checkbox_map[row].setEnabled(False)
                                button_map[row].setEnabled(False)
                                name_item = props_table.item(row, 1)
                                old_text = name_item.text()
                                name_item.setText(f"{key} (Added)")
                        return handle_add
                    
                    add_button.clicked.connect(make_add_handler(prop_key_copy, prop_value_copy, row))
                
                # Set the table as the scroll area's widget
                scroll_area.setWidget(props_table)
                suggestions_layout.addWidget(scroll_area)
                
                # Add a button to add all selected properties
                add_selected_button = QPushButton("Add Selected")
                add_selected_button.setToolTip("Add all checked properties at once")
                add_selected_button.setMaximumWidth(120)
                suggestions_layout.addWidget(add_selected_button)
                
                # Handler to add all selected properties
                def add_selected_properties():
                    # Find all checked properties
                    for row in range(props_table.rowCount()):
                        checkbox = checkbox_map.get(row)
                        if checkbox and checkbox.isChecked() and checkbox.isEnabled():
                            # Get the property key from the table
                            name_item = props_table.item(row, 1)
                            if name_item:
                                text = name_item.text()
                                key = text.split(" (")[0]
                                
                                # Find the matching suggested property
                                for prop_key, prop_value, _ in suggested_props:
                                    if prop_key == key:
                                        # Add the property
                                        prop_layout = QHBoxLayout()
                                        
                                        # Property value field
                                        edit = QLineEdit(prop_value)
                                        prop_layout.addWidget(edit)
                                        custom_props[key] = edit
                                        
                                        # Add to table button
                                        show_in_table_btn = QPushButton("Show in Table")
                                        show_in_table_btn.setMaximumWidth(100)
                                        show_in_table_btn.setToolTip("Add this property as a column in the device table")
                                        
                                        show_in_table_btn.clicked.connect(make_show_in_table_handler(key))
                                        prop_layout.addWidget(show_in_table_btn)
                                        
                                        custom_props_layout.addRow(f"{key}:", prop_layout)
                                        
                                        # Disable the checkbox and button
                                        checkbox.setEnabled(False)
                                        if row in button_map:
                                            button_map[row].setEnabled(False)
                                        name_item.setText(f"{key} (Added)")
                                        break
                
                add_selected_button.clicked.connect(add_selected_properties)
                
                # Add the suggestions group to the custom tab
                custom_layout.addWidget(suggestions_group)
        
        # Add custom property controls with a form layout for better alignment
        add_prop_group = QGroupBox("Add New Property")
        add_prop_layout = QHBoxLayout(add_prop_group)
        add_prop_layout.setContentsMargins(10, 15, 10, 10)
        
        new_prop_name = QLineEdit()
        new_prop_name.setPlaceholderText("Property Name")
        new_prop_value = QLineEdit()
        new_prop_value.setPlaceholderText("Property Value")
        add_prop_button = QPushButton("Add")
        add_prop_button.setMaximumWidth(60)
        add_prop_button.setToolTip("Add a new custom property")
        
        add_prop_layout.addWidget(new_prop_name)
        add_prop_layout.addWidget(new_prop_value)
        add_prop_layout.addWidget(add_prop_button)
        
        custom_layout.addWidget(add_prop_group)
        
        # Help text for custom properties
        help_text = QLabel("Custom properties can be used to store additional information about a device.\n"
                          "They can also be displayed as columns in the device table for easy sorting and filtering.")
        help_text.setWordWrap(True)
        custom_layout.addWidget(help_text)
        
        # Add stretch to push controls to the top
        custom_layout.addStretch()
        
        # Add custom tab to tab widget
        tab_widget.addTab(custom_tab, "Custom Properties")
        
        # Add tab widget to main layout
        layout.addWidget(tab_widget)
        
        # Function to add a new property
        def add_property():
            prop_name = new_prop_name.text().strip()
            prop_value = new_prop_value.text().strip()
            
            if not prop_name:
                return
                
            core_props = ["id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"]
            if prop_name in core_props:
                QMessageBox.warning(
                    dialog,
                    "Reserved Property",
                    f"The property name '{prop_name}' is reserved for system use.\nPlease choose a different name."
                )
                return
            
            # Create a new property row with edit field and 'Show in Table' button
            prop_layout = QHBoxLayout()
            
            # Property value field
            edit = QLineEdit(prop_value)
            prop_layout.addWidget(edit)
            custom_props[prop_name] = edit
            
            # Add to table button
            show_in_table_btn = QPushButton("Show in Table")
            show_in_table_btn.setMaximumWidth(100)
            show_in_table_btn.setToolTip("Add this property as a column in the device table")
            
            show_in_table_btn.clicked.connect(make_show_in_table_handler(prop_name))
            prop_layout.addWidget(show_in_table_btn)
            
            custom_props_layout.addRow(f"{prop_name}:", prop_layout)
            
            new_prop_name.clear()
            new_prop_value.clear()
        
        add_prop_button.clicked.connect(add_property)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        if dialog.exec():
            # Get all tags from the list
            tags = [tags_list.item(i).text() for i in range(tags_list.count())]
            
            # Update existing or create new device
            if is_new:
                # Create new device
                new_device = Device(
                    alias=alias_edit.text().strip() or "New Device",
                    hostname=hostname_edit.text().strip(),
                    ip_address=ip_edit.text().strip(),
                    mac_address=mac_edit.text().strip(),
                    status=status_combo.currentText(),
                    notes=notes_edit.toPlainText(),
                    tags=tags
                )
                
                # Add custom properties
                for key, edit in custom_props.items():
                    new_device.set_property(key, edit.text())
                
                return new_device
            else:
                # Update existing device
                device.set_property("alias", alias_edit.text())
                device.set_property("hostname", hostname_edit.text())
                device.set_property("ip_address", ip_edit.text())
                device.set_property("mac_address", mac_edit.text())
                device.set_property("status", status_combo.currentText())
                device.set_property("notes", notes_edit.toPlainText())
                device.set_property("tags", tags)
                
                # Update custom properties
                for key, edit in custom_props.items():
                    device.set_property(key, edit.text())
                
                return device
        
        return None

    def on_context_menu(self, pos):
        """Show context menu"""
        devices = self._get_highlighted_devices()
        if not devices:
            checked_devices = self.device_manager.get_selected_devices()
            devices = checked_devices.copy() if checked_devices else []

        if not devices:
            index = self.indexAt(pos)
            if index.isValid():
                device = index.data(Qt.UserRole)
                if device:
                    devices.append(device)
                
        # Exit if no devices
        if not devices:
            return
            
        # Create context menu
        menu = QMenu()
        
        # SECTION 1: Device Management Actions
        if len(devices) == 1:
            menu.addAction("Edit Properties", lambda: self._handle_action(self._on_action_edit_properties, devices))
        else:
            menu.addAction(f"Edit Selected Devices ({len(devices)})", lambda: self._handle_action(self._on_action_edit_properties, devices))
            
        menu.addAction("Delete", lambda: self._handle_action(self._on_action_delete, devices))
        
        # SECTION 2: Group Management
        menu.addSeparator()
        
        add_to_group_menu = menu.addMenu("Add to Group")
        self._populate_add_to_group_menu(add_to_group_menu, devices)
        
        # Add "Remove from Group" submenu
        remove_from_group_menu = menu.addMenu("Remove from Group")
        self._populate_remove_from_group_menu(remove_from_group_menu, devices)
        
        menu.addAction("Create Group from Selection", lambda: self._handle_action(self._on_action_create_group, devices))
        
        # SECTION 3: Device Creation and Import
        menu.addSeparator()
        menu.addAction("Add Device", lambda: self._handle_action(self._on_action_add_device, None))
        menu.addAction("Import Devices...", lambda: self._handle_action(self._on_action_import_devices, None))
        
        # SECTION 4: Selection Controls
        menu.addSeparator()
        menu.addAction("Select All", self._on_action_select_all)
        menu.addAction("Deselect All", self._on_action_deselect_all)
        
        # SECTION 5: Custom Plugin Actions (not duplicating existing ones)
        # Filter out registered actions we've already added directly
        built_in_actions = {
            "Add Device", "Import Devices...", "Edit Properties", 
            "Add to Group", "Remove from Group", "Create New Group", "Create Group from Selection",
            "Select All", "Deselect All", "Delete"
        }
        
        # Get filtered and sorted actions
        filtered_actions = []
        for name, callback, priority in self._context_menu_actions:
            if name not in built_in_actions:
                filtered_actions.append((name, callback, priority))
                
        if filtered_actions:
            menu.addSeparator()
            # Group by plugin using a dictionary
            plugin_actions = {}
            
            for name, callback, priority in sorted(filtered_actions, key=lambda x: x[2]):
                # Extract plugin name from function module if available
                plugin_name = "Other Actions"
                if hasattr(callback, '__module__'):
                    module_parts = callback.__module__.split('.')
                    if 'plugins' in module_parts:
                        # Try to get plugin name from module path
                        plugin_idx = module_parts.index('plugins')
                        if plugin_idx + 1 < len(module_parts):
                            plugin_name = module_parts[plugin_idx + 1].replace('_', ' ').title()
                
                # Add to plugin group
                if plugin_name not in plugin_actions:
                    plugin_actions[plugin_name] = []
                plugin_actions[plugin_name].append((name, callback, priority))
            
            # Add each plugin group as a submenu or directly if only one action
            for plugin_name, actions in plugin_actions.items():
                if len(actions) == 1:
                    # Just one action, add directly
                    name, callback, _ = actions[0]
                    action = menu.addAction(name)
                    local_callback = callback
                    action.triggered.connect(
                        lambda checked=False, cb=local_callback: self._handle_action(cb, devices)
                    )
                else:
                    # Multiple actions, create submenu
                    plugin_menu = menu.addMenu(plugin_name)
                    for name, callback, _ in sorted(actions, key=lambda x: x[2]):
                        action = plugin_menu.addAction(name)
                        local_callback = callback
                        action.triggered.connect(
                            lambda checked=False, cb=local_callback: self._handle_action(cb, devices)
                        )
        
        # Emit signal for plugins to add to menu
        self.context_menu_requested.emit(devices, menu)
        
        # Show menu
        menu.exec(self.viewport().mapToGlobal(pos))

    def _handle_action(self, callback, devices):
        """Handle a context menu action"""
        # Special handling for actions that don't need device arguments
        if callback in [self._on_action_select_all, self._on_action_deselect_all]:
            callback()
            return
            
        if devices:
            # Determine if the callback function is from a plugin 
            # by checking if it comes from a module with 'plugins' in its path
            is_plugin_callback = False
            if hasattr(callback, '__module__'):
                module_parts = callback.__module__.split('.')
                is_plugin_callback = 'plugins' in module_parts
                
            # Check if devices is a list or a single device
            if isinstance(devices, list):
                if len(devices) == 1 and not is_plugin_callback:
                    # Single device from a list - only for internal actions
                    # Plugin actions should always receive a list even for a single device
                    callback(devices[0])
                else:
                    # Multiple devices or plugin callback
                    callback(devices)
            else:
                # Single device (not in a list)
                if is_plugin_callback:
                    # For plugin callbacks, always convert to a list
                    callback([devices])
                else:
                    # For internal callbacks, pass as is
                    callback(devices)
        else:
            # No device selected
            callback(None)

    def _on_action_edit_properties(self, device_or_devices):
        """Edit device properties"""
        # Check if we have a list of devices for multi-edit
        if isinstance(device_or_devices, list):
            if device_or_devices:
                logger.debug(f"Editing properties for {len(device_or_devices)} devices")
                self._edit_multiple_devices(device_or_devices)
            return
            
        # Single device edit
        device = device_or_devices
        if not device:
            return
            
        logger.debug(f"Editing properties for device: {device}")
        self.device_properties_dialog(device)
    
    def _edit_multiple_devices(self, devices):
        """Edit properties for multiple devices at once"""
        if not devices:
            return
            
        dialog = QDialog()
        dialog.setWindowTitle(f"Edit {len(devices)} Devices")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Create tab widget for organizing properties
        tab_widget = QTabWidget()
        
        # Basic tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_form = QFormLayout()
        
        # Instructions
        info_label = QLabel("Edit properties for multiple devices. Empty fields will keep existing values.")
        basic_layout.addWidget(info_label)
        
        # Core property fields
        alias_edit = QLineEdit()
        alias_edit.setPlaceholderText("Leave empty to keep current values")
        basic_form.addRow("Alias:", alias_edit)
        
        hostname_edit = QLineEdit()
        hostname_edit.setPlaceholderText("Leave empty to keep current values")
        basic_form.addRow("Hostname:", hostname_edit)
        
        ip_edit = QLineEdit()
        ip_edit.setPlaceholderText("Leave empty to keep current values")
        basic_form.addRow("IP Address:", ip_edit)
        
        mac_edit = QLineEdit()
        mac_edit.setPlaceholderText("Leave empty to keep current values")
        basic_form.addRow("MAC Address:", mac_edit)
        
        status_combo = QComboBox()
        status_values = ["--Keep Current--", "unknown", "up", "down", "warning", "error", "maintenance"]
        status_combo.addItems(status_values)
        basic_form.addRow("Status:", status_combo)
        
        # Add the form to the basic tab
        basic_layout.addLayout(basic_form)
        tab_widget.addTab(basic_tab, "Basic")
        
        # Tags tab
        tags_tab = QWidget()
        tags_layout = QVBoxLayout(tags_tab)
        
        # Add a label for the tag list
        tags_layout.addWidget(QLabel("Add these tags to all selected devices:"))

        # Add a filter for tags
        tags_filter_layout = QHBoxLayout()
        tags_filter_label = QLabel("Filter:")
        tags_filter_edit = QLineEdit()
        tags_filter_edit.setPlaceholderText("Type to filter tags...")
        tags_filter_layout.addWidget(tags_filter_label)
        tags_filter_layout.addWidget(tags_filter_edit)
        tags_layout.addLayout(tags_filter_layout)

        # Tag list
        tags_list = QListWidget()
        tags_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
            
        tags_layout.addWidget(tags_list)

        # Tag controls
        tags_control_layout = QHBoxLayout()
        new_tag = QLineEdit()
        new_tag.setPlaceholderText("New tag")
        add_tag_button = QPushButton("Add")
        remove_tag_button = QPushButton("Remove Selected")
        
        tags_control_layout.addWidget(new_tag)
        tags_control_layout.addWidget(add_tag_button)
        tags_control_layout.addWidget(remove_tag_button)
        
        tags_layout.addLayout(tags_control_layout)
        
        # Add tag function
        def add_tag():
            tag = new_tag.text().strip()
            if tag and not tags_list.findItems(tag, Qt.MatchExactly):
                tags_list.addItem(QListWidgetItem(tag))
                new_tag.clear()
                
        # Remove selected tags
        def remove_selected_tags():
            for item in reversed(tags_list.selectedItems()):
                row = tags_list.row(item)
                tags_list.takeItem(row)
        
        # Add tag filter function
        def filter_tags(text):
            filter_text = text.lower()
            for i in range(tags_list.count()):
                item = tags_list.item(i)
                item.setHidden(filter_text and filter_text not in item.text().lower())
                
        add_tag_button.clicked.connect(add_tag)
        remove_tag_button.clicked.connect(remove_selected_tags)
        tags_filter_edit.textChanged.connect(filter_tags)
        
        # Add enter key press to add tag
        def on_tag_return_pressed():
            if new_tag.text().strip():
                add_tag()
                
        new_tag.returnPressed.connect(on_tag_return_pressed)
        
        # Add tags tab to tab widget
        tab_widget.addTab(tags_tab, "Tags")
        
        # Add tab widget to dialog
        layout.addWidget(tab_widget)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        if dialog.exec():
            # Process the changes for all devices
            for device in devices:
                # Only update properties that were actually changed
                if alias_edit.text():
                    device.set_property("alias", alias_edit.text())
                    
                if hostname_edit.text():
                    device.set_property("hostname", hostname_edit.text())
                    
                if ip_edit.text():
                    device.set_property("ip_address", ip_edit.text())
                    
                if mac_edit.text():
                    device.set_property("mac_address", mac_edit.text())
                    
                if status_combo.currentIndex() > 0:  # Not --Keep Current--
                    device.set_property("status", status_combo.currentText())
                
                # Add new tags to the device
                current_tags = device.get_property("tags", [])
                for i in range(tags_list.count()):
                    tag = tags_list.item(i).text()
                    if tag not in current_tags:
                        current_tags.append(tag)
                device.set_property("tags", current_tags)
                
                # Notify of changes
                self.device_manager.device_changed.emit(device)

    def _on_action_delete(self, device_or_devices):
        """Delete the device(s)"""
        if not device_or_devices:
            return
                
        # Handle single device or list of devices
        devices = device_or_devices if isinstance(device_or_devices, list) else [device_or_devices]
        
        if len(devices) == 1:
            # Single device
            device = devices[0]
            result = QMessageBox.question(
                self, 
                "Confirm Deletion",
                f"Are you sure you want to delete device '{device.get_property('alias')}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result == QMessageBox.Yes:
                self.device_manager.remove_device(device)
        else:
            # Multiple devices
            result = QMessageBox.question(
                self, 
                "Confirm Deletion",
                f"Are you sure you want to delete {len(devices)} devices?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result == QMessageBox.Yes:
                for device in devices:
                    self.device_manager.remove_device(device)

    def _on_action_add_to_group(self, data):
        """Add device(s) to a group"""
        # Extract devices and group from data
        if isinstance(data, tuple) and len(data) == 2:
            devices, group = data
        else:
            logger.error(f"Invalid data format for add_to_group: {data}")
            return
            
        # Get list of devices
        if not isinstance(devices, list):
            devices = [devices]
            
        if not devices:
            return
            
        # Ask if user wants to auto-group by type
        auto_group = False
        if len(devices) > 1:
            reply = QMessageBox.question(
                self,
                "Auto-group by Type",
                "Would you like to automatically create subgroups based on device types?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            auto_group = (reply == QMessageBox.Yes)
        
        # Helper function to get the device type
        def get_device_type(device):
            # Use device_type property if it exists
            device_type = device.get_property("device_type", "")
            if not device_type:
                # Try to determine from other properties
                if device.get_property("is_switch", False) or device.get_property("is_router", False):
                    device_type = "network"
                elif device.get_property("is_server", False):
                    device_type = "server"
                elif device.get_property("is_workstation", False):
                    device_type = "workstation"
                elif device.get_property("is_printer", False):
                    device_type = "printer"
                else:
                    # Default fallback
                    device_type = "unknown"
            return device_type
        
        # Process devices
        added_count = 0
        
        if auto_group:
            # Group devices by type
            device_types = {}
            for device in devices:
                device_type = get_device_type(device)
                if device_type not in device_types:
                    device_types[device_type] = []
                device_types[device_type].append(device)
            
            # Process each type
            for device_type, type_devices in device_types.items():
                # Skip if no devices
                if not type_devices:
                    continue
                    
                # Create a subgroup for this type if it doesn't exist
                type_name = device_type.replace("_", " ").title()
                type_group_name = f"{group.name}: {type_name}"
                
                # Check if the subgroup already exists
                type_group = None
                for subgroup in group.subgroups:
                    if subgroup.name == type_group_name:
                        type_group = subgroup
                        break
                        
                # Create the subgroup if it doesn't exist
                if not type_group:
                    type_group = self.device_manager.create_group(
                        type_group_name,
                        f"Devices of type {type_name} in {group.name}",
                        group
                    )
                    
                # Add devices to the type group
                for device in type_devices:
                    if device not in type_group.devices:
                        self.device_manager.add_device_to_group(device, type_group)
                        added_count += 1
        else:
            # Add devices directly to the group
            for device in devices:
                if device not in group.devices:
                    self.device_manager.add_device_to_group(device, group)
                    added_count += 1
        
        # Save changes
        self.device_manager.save_devices()
        
        # Show a message to the user with the result
        if added_count > 0:
            QMessageBox.information(
                self, 
                "Devices Added",
                f"Added {added_count} device{'s' if added_count != 1 else ''} to group '{group.name}'."
            )
        else:
            QMessageBox.information(
                self,
                "No Changes",
                f"The selected device{'s' if len(devices) > 1 else ''} {'were' if len(devices) > 1 else 'was'} already in group '{group.name}'."
            )

    def _on_action_create_group(self, device_or_devices):
        """Create a new group with selected device(s)"""
        if not device_or_devices:
            return
            
        # Get list of devices
        devices = device_or_devices if isinstance(device_or_devices, list) else [device_or_devices]
        if not devices:
            return
            
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Group")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        # Group name
        form = QFormLayout()
        group_name = QLineEdit()
        form.addRow("Group Name:", group_name)
        
        group_desc = QLineEdit()
        form.addRow("Description:", group_desc)
        
        # Parent group selection
        groups = self.device_manager.get_groups()
        parent_combo = QComboBox()
        for group in groups:
            parent_combo.addItem(group.name, group)
        form.addRow("Parent Group:", parent_combo)
        
        # Auto-group by device type
        auto_group_checkbox = QCheckBox("Auto-group by device type")
        auto_group_checkbox.setToolTip("Create subgroups based on device types")
        layout.addLayout(form)
        layout.addWidget(auto_group_checkbox)
        
        # Add dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        # Show dialog
        if dialog.exec():
            # Get dialog values
            name = group_name.text().strip()
            desc = group_desc.text().strip()
            parent = parent_combo.currentData()
            auto_group = auto_group_checkbox.isChecked()
            
            if not name:
                QMessageBox.warning(
                    self,
                    "Invalid Group Name",
                    "Please enter a valid group name."
                )
                return
                
            try:
                # Create new group
                group = self.device_manager.create_group(name, desc, parent)
                
                # Helper function to get the device type
                def get_device_type(device):
                    # Use device_type property if it exists
                    device_type = device.get_property("device_type", "")
                    if not device_type:
                        # Try to determine from other properties
                        if device.get_property("is_switch", False) or device.get_property("is_router", False):
                            device_type = "network"
                        elif device.get_property("is_server", False):
                            device_type = "server"
                        elif device.get_property("is_workstation", False):
                            device_type = "workstation"
                        elif device.get_property("is_printer", False):
                            device_type = "printer"
                        else:
                            # Default fallback
                            device_type = "unknown"
                    return device_type
                
                # Process each device
                added_devices = 0
                if auto_group:
                    # Group devices by type
                    device_types = {}
                    for device in devices:
                        device_type = get_device_type(device)
                        if device_type not in device_types:
                            device_types[device_type] = []
                        device_types[device_type].append(device)
                    
                    # Create subgroups for each type
                    for device_type, type_devices in device_types.items():
                        # Skip if no devices
                        if not type_devices:
                            continue
                            
                        # Create a subgroup for this type
                        type_name = device_type.replace("_", " ").title()
                        type_group_name = f"{name}: {type_name}"
                        type_group = self.device_manager.create_group(type_group_name, f"{desc} - {type_name}", group)
                        
                        # Add devices to this type group
                        for device in type_devices:
                            self.device_manager.add_device_to_group(device, type_group)
                            added_devices += 1
                else:
                    # Add all devices directly to the group
                    for device in devices:
                        self.device_manager.add_device_to_group(device, group)
                        added_devices += 1
                
                # Show result message
                QMessageBox.information(
                    self,
                    "Group Created",
                    f"Created group '{name}' with {added_devices} devices."
                )
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Creating Group",
                    f"An error occurred while creating the group: {str(e)}"
                )
                logger.error(f"Error creating group: {e}")
                # Raise the exception again to see the full stack trace in the console
                raise

    def _on_action_add_device(self, device):
        """Add a new device"""
        new_device = self.device_properties_dialog(None)
        if new_device:
            # Add to device manager
            self.device_manager.add_device(new_device)
            
    def _on_action_import_devices(self, device):
        """Import devices from a file"""
        from .import_wizard import run_device_import_wizard
        
        run_device_import_wizard(self.device_manager, self)

    def _on_action_select_all(self):
        """Select all devices in the current view"""
        logger.debug("Checking all visible devices")
        visible_devices = self._get_visible_devices()
        if not visible_devices:
            return
        checked_devices = self.device_manager.get_selected_devices()
        merged = {device for device in checked_devices}
        merged.update(visible_devices)
        self._sync_selection_to_device_manager(list(merged))
        self.table_model.notify_selection_changed()
        self._update_header_checkbox_state()
            
    def _on_action_deselect_all(self):
        """Deselect all devices"""
        logger.debug("Clearing all checked devices")
        self._sync_selection_to_device_manager([])
        self.table_model.notify_selection_changed()
        self._update_header_checkbox_state()

    def _populate_add_to_group_menu(self, menu, devices):
        """Populate the Add to Group submenu
        
        Args:
            menu: The QMenu to populate
            devices: List of devices to add to a group
        """
        # Get all groups
        groups = self.device_manager.get_groups()
        
        # Skip the root group (All Devices)
        groups = [g for g in groups if g != self.device_manager.root_group]
        
        if not groups:
            action = menu.addAction("No Groups Available")
            action.setEnabled(False)
            return
            
        # Create a copy of the devices list to avoid reference issues in the lambda
        devices_copy = devices.copy() if isinstance(devices, list) else [devices]
            
        # Add actions for each group
        for group in sorted(groups, key=lambda g: g.name):
            # Create a closure that captures the current group
            action = menu.addAction(group.name)
            # When triggered, this will call _on_action_add_to_group with the tuple (devices, group)
            action.triggered.connect(
                lambda checked=False, g=group, d=devices_copy: self._on_action_add_to_group((d, g))
            )

    def _populate_remove_from_group_menu(self, menu, devices):
        """Populate the Remove from Group submenu
        
        Args:
            menu: The QMenu to populate
            devices: List of devices to remove from their current groups
        """
        # Get all groups
        groups = self.device_manager.get_groups()
        
        # Skip the root group (All Devices)
        groups = [g for g in groups if g != self.device_manager.root_group]
        
        if not groups:
            action = menu.addAction("No Groups Available")
            action.setEnabled(False)
            return
            
        # Create a copy of the devices list to avoid reference issues in the lambda
        devices_copy = devices.copy() if isinstance(devices, list) else [devices]
            
        # Add actions for each group
        for group in sorted(groups, key=lambda g: g.name):
            # Create a closure that captures the current group
            action = menu.addAction(group.name)
            # When triggered, this will call _on_action_remove_from_group with the tuple (devices, group)
            action.triggered.connect(
                lambda checked=False, g=group, d=devices_copy: self._on_action_remove_from_group((d, g))
            )

    def _on_action_remove_from_group(self, data):
        """Remove devices from a group"""
        # Check if we got a tuple of (devices, group)
        if isinstance(data, tuple) and len(data) == 2:
            devices, group = data
            device_count = len(devices)
            logger.debug(f"Removing {device_count} devices from group '{group.name}'")
            
            # Remove each device from the group
            removed_count = 0
            for device in devices:
                # Only remove if in the group
                if device in group.devices:
                    self.device_manager.remove_device_from_group(device, group)
                    removed_count += 1
                else:
                    logger.debug(f"Device {device.get_property('alias', 'Unnamed')} not in group {group.name}")
            
            # Save after all devices are removed
            self.device_manager.save_devices()
            
            # Show a message to the user with the result
            from PySide6.QtWidgets import QMessageBox
            if removed_count > 0:
                QMessageBox.information(
                    self, 
                    "Devices Removed",
                    f"Removed {removed_count} device{'s' if removed_count != 1 else ''} from group '{group.name}'."
                )
            else:
                QMessageBox.information(
                    self,
                    "No Changes",
                    f"The selected device{'s' if device_count > 1 else ''} {'were' if device_count > 1 else 'was'} not in group '{group.name}'."
                )
            
            return
            
        # Legacy handling for backward compatibility
        device_or_devices = data
        
        # Multiple devices
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        else:
            # Single device
            devices = [device_or_devices]
            
        # No devices to remove
        if not devices:
            return
            
        # Get all groups
        groups = [g for g in self.device_manager.get_groups() 
                 if g != self.device_manager.root_group]
                 
        if not groups:
            self.device_manager.create_group("New Group")
            groups = [g for g in self.device_manager.get_groups() 
                     if g != self.device_manager.root_group]
                     
        # Show group selection dialog
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Remove from Group")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        # Header with device count
        header = QLabel(f"Select group to remove {len(devices)} device{'s' if len(devices) > 1 else ''} from:")
        layout.addWidget(header)
        
        # Group list
        list_widget = QListWidget()
        for group in sorted(groups, key=lambda g: g.name):
            list_widget.addItem(group.name)
            
        layout.addWidget(list_widget)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            # Get selected group
            selected_item = list_widget.currentItem()
            if selected_item:
                group_name = selected_item.text()
                group = self.device_manager.get_group(group_name)
                
                if group:
                    removed_count = 0
                    for device in devices:
                        # Only remove if in the group
                        if device in group.devices:
                            self.device_manager.remove_device_from_group(device, group)
                            removed_count += 1
                            
                    self.device_manager.save_devices()
                    
                    # Show a message to the user with the result
                    if removed_count > 0:
                        QMessageBox.information(
                            self, 
                            "Devices Removed",
                            f"Removed {removed_count} device{'s' if removed_count != 1 else ''} from group '{group_name}'."
                        )
                    else:
                        QMessageBox.information(
                            self,
                            "No Changes",
                            f"The selected device{'s' if len(devices) > 1 else ''} {'were' if len(devices) > 1 else 'was'} not in group '{group_name}'."
                        )

    def on_selection_model_changed(self, selected, deselected):
        """Handle changes to the selection model
        
        This method synchronizes the Qt selection model with the device_manager selection
        """
        # Only respond to UI-driven selection changes if this was triggered by user interaction
        # not by programmatic selection changes
        if self._ignore_selection_changes:
            return

        # Selection highlight is navigation only; keep checkboxes unchanged.
        selected_count = len(self.selectionModel().selectedRows())
        logger.debug(f"Row highlight changed: {selected_count} rows highlighted")

    @Slot(list)
    def on_manager_selection_changed(self, devices):
        """Sync device manager selection to the table view"""
        if self._ignore_selection_changes:
            return
            
        self._ignore_selection_changes = True
        try:
            # Only update checkbox visuals and header state.
            self.table_model.notify_selection_changed()
            self._update_header_checkbox_state()
        finally:
            self._ignore_selection_changes = False
        
    def _sync_selection_to_device_manager(self, selected_devices):
        """Sync the UI selection to the device manager
        
        This avoids recursive updates by directly setting the device_manager's selection
        """
        # Get currently selected devices in the manager
        currently_selected = self.device_manager.get_selected_devices()
        
        # Update the device manager's selection directly
        self.device_manager.selected_devices = selected_devices.copy()
        
        # Only emit the signal if the selection has actually changed
        if set(selected_devices) != set(currently_selected):
            self.device_manager.selection_changed.emit(selected_devices)
            logger.debug(f"Emitted selection_changed with {len(selected_devices)} devices")
            
            # Log names of selected devices for debugging
            if selected_devices:
                device_names = [str(d.get_property('alias', f'Device {d.id}')) for d in selected_devices]
                logger.debug(f"Selected devices: {', '.join(device_names[:5])}" + 
                           (f" and {len(device_names) - 5} more" if len(device_names) > 5 else ""))