#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree view for NetWORKS.
"""

from loguru import logger
from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QTimer,
    QSize,
    QSettings,
    QSortFilterProxyModel,
    QItemSelectionModel,
)
from PySide6.QtWidgets import (
    QTreeView, QAbstractItemView, QMenu, QWidget, QDialog, QVBoxLayout,
    QHBoxLayout, QTabWidget, QFileDialog, QLabel, QPushButton, QTextEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QFormLayout, QGroupBox, QCheckBox, QWizard, QWizardPage, QMessageBox,
    QDialogButtonBox, QInputDialog, QApplication, QButtonGroup, QRadioButton,
    QPlainTextEdit, QToolButton, QDockWidget, QSizePolicy, QStyle,
)
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap

from ...core.device_manager import Device
from ..material_icons import material_icon

import os
import json


class DeviceTreeView(QTreeView):
    """Custom tree view for devices"""
    
    device_double_clicked = Signal(object)
    group_selection_changed = Signal(list)
    group_filter_requested = Signal(object)
    
    def __init__(self, device_manager):
        """Initialize the view"""
        super().__init__()
        
        self.device_manager = device_manager
        self._proxy_model = None
        self._source_model = None
        self._ignore_selection_sync = False
        self._filter_table_on_group_select = False
        self._compact_mode = False
        self._pending_state = None
        
        # Configure view
        self.setHeaderHidden(True)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setEditTriggers(QAbstractItemView.EditKeyPressed)
        
        # Connect signals
        self.clicked.connect(self.on_item_clicked)
        self.doubleClicked.connect(self.on_item_double_clicked)
        self.customContextMenuRequested.connect(self.on_context_menu)
        self.device_manager.selection_changed.connect(self.on_manager_selection_changed)
        
        # Expand root item
        self.expandToDepth(0)
        self._configure_columns()

    def setModel(self, model):
        """Track proxy/source models for filtering and selection sync"""
        self._proxy_model = None
        self._source_model = None
        
        if isinstance(model, QSortFilterProxyModel):
            self._proxy_model = model
            self._source_model = model.sourceModel()
        else:
            self._source_model = model
            
        super().setModel(model)
        self._configure_columns()
        
        # Connect model reset signals for state preservation
        if self._source_model:
            self._source_model.modelAboutToBeReset.connect(self._capture_view_state)
            self._source_model.modelReset.connect(self._restore_view_state_from_capture)
            self._source_model.modelReset.connect(self._configure_columns)
        
    def refresh(self):
        """Refresh the device tree view to reflect current data"""
        # Get the model and reset its data
        model = self._source_model or self.model()
        self._capture_view_state()
        if model and hasattr(model, 'setup_model_data'):
            model.setup_model_data()

    def _configure_columns(self):
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(140)

    def set_filter_table_on_group_select(self, enabled):
        """Toggle filtering the device table when selecting a group"""
        self._filter_table_on_group_select = bool(enabled)

    def set_compact_mode(self, enabled):
        """Toggle compact layout for the tree"""
        self._compact_mode = bool(enabled)
        if self._compact_mode:
            self.setIndentation(12)
            self.setIconSize(QSize(10, 10))
            self.setStyleSheet("QTreeView::item { padding: 1px 2px; }")
        else:
            self.setIndentation(20)
            self.setIconSize(QSize(14, 14))
            self.setStyleSheet("")

    def _capture_view_state(self):
        """Capture current expanded and selection state"""
        if not self._source_model:
            return
            
        expanded_groups = []
        selected_groups = []
        selected_devices = []
        
        def walk(item):
            for child in item.child_items:
                if child.group:
                    index = self._index_for_item(child)
                    if index.isValid() and self.isExpanded(index):
                        expanded_groups.append(child.group.name)
                if child.device and self.selectionModel():
                    index = self._index_for_item(child)
                    if index.isValid() and self.selectionModel().isSelected(index):
                        selected_devices.append(child.device.id)
                if child.group:
                    walk(child)
                    
        walk(self._source_model.root_item)
        
        # Capture group selection separately
        if self.selectionModel():
            for index in self.selectionModel().selectedRows():
                item = index.data(Qt.UserRole)
                if hasattr(item, "name"):
                    selected_groups.append(item.name)
        
        self._pending_state = {
            "expanded_groups": expanded_groups,
            "selected_devices": selected_devices,
            "selected_groups": selected_groups,
        }

    def _restore_view_state_from_capture(self):
        """Restore view state after a model reset"""
        if not self._pending_state:
            self.restore_state()
            return
            
        state = self._pending_state
        self._pending_state = None
        self._apply_view_state(state)

    def save_state(self):
        """Persist tree state for the current workspace"""
        state = self._build_view_state()
        settings = self._get_workspace_settings()
        settings.setValue("expanded_groups", state.get("expanded_groups", []))
        settings.setValue("selected_devices", state.get("selected_devices", []))
        settings.setValue("selected_groups", state.get("selected_groups", []))
        settings.setValue("compact_mode", self._compact_mode)
        settings.setValue("filter_table_on_group_select", self._filter_table_on_group_select)

    def restore_state(self):
        """Restore tree state for the current workspace"""
        settings = self._get_workspace_settings()
        expanded_groups = settings.value("expanded_groups", [])
        selected_devices = settings.value("selected_devices", [])
        selected_groups = settings.value("selected_groups", [])
        
        # Handle None values from QSettings (can happen if setting doesn't exist)
        if expanded_groups is None:
            expanded_groups = []
        if selected_devices is None:
            selected_devices = []
        if selected_groups is None:
            selected_groups = []
        
        if isinstance(expanded_groups, str):
            expanded_groups = [expanded_groups]
        if isinstance(selected_devices, str):
            selected_devices = [selected_devices]
        if isinstance(selected_groups, str):
            selected_groups = [selected_groups]
        
        self.set_compact_mode(settings.value("compact_mode", False, type=bool))
        self.set_filter_table_on_group_select(
            settings.value("filter_table_on_group_select", False, type=bool)
        )
        
        self._apply_view_state({
            "expanded_groups": expanded_groups,
            "selected_devices": selected_devices,
            "selected_groups": selected_groups,
        })

    def _build_view_state(self):
        """Build a state snapshot without persisting it"""
        self._capture_view_state()
        state = self._pending_state or {}
        self._pending_state = None
        return state

    def _apply_view_state(self, state):
        """Apply expanded and selected state"""
        if not self._source_model:
            return
        
        # Ensure state is a dictionary
        if not isinstance(state, dict):
            return
            
        self._ignore_selection_sync = True
        try:
            self.clearSelection()
            
            # Restore expansions - handle None values defensively
            expanded_groups = state.get("expanded_groups", []) or []
            for group_name in expanded_groups:
                item = self._source_model.get_group_item(group_name)
                if item:
                    index = self._index_for_item(item)
                    if index.isValid():
                        self.expand(index)
            
            # Restore device selections - handle None values defensively
            selection = self.selectionModel()
            if selection:
                selected_devices = state.get("selected_devices", []) or []
                for device_id in selected_devices:
                    for item in self._source_model.get_device_items(device_id):
                        index = self._index_for_item(item)
                        if index.isValid():
                            selection.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                            
            # Restore group selections if no devices selected - handle None values defensively
            if selection and not selection.selectedRows():
                selected_groups = state.get("selected_groups", []) or []
                for group_name in selected_groups:
                    item = self._source_model.get_group_item(group_name)
                    if item:
                        index = self._index_for_item(item)
                        if index.isValid():
                            selection.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        finally:
            self._ignore_selection_sync = False

    def _index_for_item(self, item):
        """Return the proxy index for a given source item"""
        if not self._source_model or not item:
            return QModelIndex()
            
        source_index = self._source_model.createIndex(item.row(), 0, item)
        if self._proxy_model:
            return self._proxy_model.mapFromSource(source_index)
        return source_index

    def _get_workspace_settings(self):
        """Get QSettings for the current workspace device tree state"""
        workspace_name = self.device_manager.current_workspace
        workspace_dir = os.path.join(self.device_manager.workspaces_dir, workspace_name)
        settings_dir = os.path.join(workspace_dir, "settings")
        os.makedirs(settings_dir, exist_ok=True)
        return QSettings(os.path.join(settings_dir, "device_tree.ini"), QSettings.IniFormat)
        
    def on_item_clicked(self, index):
        """Handle item clicked"""
        if not index.isValid():
            return
            
        # Get selected indexes
        selection = self.selectionModel()
        selected_indexes = selection.selectedIndexes()
        
        # Only process indexes for the first column (to avoid duplicate processing)
        selected_indexes = [idx for idx in selected_indexes if idx.column() == 0]
        
        if not selected_indexes:
            return
            
        # Get selected devices and groups
        selected_devices = []
        selected_groups = []
        for idx in selected_indexes:
            item = idx.data(Qt.UserRole)
            if hasattr(item, 'id'):  # It's a device
                selected_devices.append(item)
            elif hasattr(item, 'name'):  # It's a group
                selected_groups.append(item)
                
        if selected_devices:
            # Update device selection
            modifiers = QApplication.keyboardModifiers()
            exclusive = modifiers != Qt.ControlModifier
            
            self._ignore_selection_sync = True
            try:
                if exclusive:
                    self.device_manager.clear_selection()
                    
                for device in selected_devices:
                    self.device_manager.select_device(device, exclusive=False)
            finally:
                self._ignore_selection_sync = False
                
            self.group_selection_changed.emit([])
        elif selected_groups:
            # Expand selected groups on click
            for idx in selected_indexes:
                item = idx.data(Qt.UserRole)
                if hasattr(item, 'name') and not self.isExpanded(idx):
                    self.expand(idx)
                    
            self._ignore_selection_sync = True
            try:
                self.device_manager.clear_selection()
            finally:
                self._ignore_selection_sync = False
                
            self.group_selection_changed.emit(selected_groups)
            if self._filter_table_on_group_select:
                if len(selected_groups) == 1:
                    self.group_filter_requested.emit(selected_groups[0])
                else:
                    self.group_filter_requested.emit(None)
            
    def on_item_double_clicked(self, index):
        """Handle item double clicked"""
        if not index.isValid():
            return
            
        item = index.data(Qt.UserRole)
        
        if hasattr(item, 'id'):  # It's a device
            self.device_double_clicked.emit(item)
        else:  # It's a group
            self.edit(index)

    @Slot(list)
    def on_manager_selection_changed(self, devices):
        """Sync device manager selection back into the tree view"""
        if self._ignore_selection_sync or not self._source_model:
            return
            
        selection = self.selectionModel()
        if not selection:
            return
            
        self._ignore_selection_sync = True
        try:
            self.clearSelection()
            for device in devices:
                for item in self._source_model.get_device_items(device.id):
                    index = self._index_for_item(item)
                    if index.isValid():
                        selection.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        finally:
            self._ignore_selection_sync = False
            
    def on_context_menu(self, position):
        """Handle context menu request"""
        index = self.indexAt(position)
        
        # Create context menu
        menu = QMenu(self)
        
        if index.isValid():
            item = index.data(Qt.UserRole)
            
            if hasattr(item, 'id'):  # It's a device
                # Device context menu
                action_properties = menu.addAction("Properties")
                menu.addSeparator()
                
                # Add-to-group submenu
                add_to_group_menu = menu.addMenu("Add to Group")
                self._populate_group_menu(add_to_group_menu, item, add_only=True)
                
                # Move-to-group submenu
                move_to_group_menu = menu.addMenu("Move to Group")
                self._populate_group_menu(move_to_group_menu, item, add_only=False, source_index=index)
                
                # Remove from current group
                parent_item = index.parent().data(Qt.UserRole)
                action_remove_from_group = None
                if hasattr(parent_item, "name") and parent_item != self.device_manager.root_group:
                    action_remove_from_group = menu.addAction(f"Remove from '{parent_item.name}'")
                
                menu.addSeparator()
                action_delete = menu.addAction("Delete")
                menu.addSeparator()
                action_import_devices = menu.addAction("Import Devices...")
                
                # Show menu and handle result
                action = menu.exec_(self.viewport().mapToGlobal(position))
                
                if action == action_properties:
                    self.device_double_clicked.emit(item)
                elif action == action_delete:
                    self.device_manager.remove_device(item)
                elif action == action_import_devices:
                    self._show_import_dialog()
                elif action_remove_from_group and action == action_remove_from_group:
                    parent_group = parent_item
                    if parent_group and parent_group != self.device_manager.root_group:
                        self.device_manager.remove_device_from_group(item, parent_group)
                    
            else:  # It's a group
                # Group context menu
                action_rename = menu.addAction("Rename")
                action_manage = menu.addAction("Manage Group...")
                menu.addSeparator()
                action_new_device = menu.addAction("New Device")
                action_new_group = menu.addAction("New Subgroup")
                menu.addSeparator()
                action_import_devices = menu.addAction("Import Devices...")
                menu.addSeparator()
                action_filter_group = menu.addAction("Filter Table by This Group")
                menu.addSeparator()
                action_delete = menu.addAction("Delete Group")
                
                # Show menu and handle result
                action = menu.exec_(self.viewport().mapToGlobal(position))
                
                if action == action_rename:
                    self.edit(index)
                elif action == action_manage:
                    self._show_group_manager_dialog(item)
                elif action == action_new_device:
                    device = Device(name="New Device")
                    self.device_manager.add_device(device)
                    self.device_manager.add_device_to_group(device, item)
                elif action == action_new_group:
                    self.device_manager.create_group("New Group", parent_group=item)
                elif action == action_import_devices:
                    self._show_import_dialog()
                elif action == action_filter_group:
                    self.group_filter_requested.emit(item)
                elif action == action_delete:
                    self.device_manager.remove_group(item)
        else:
            # Root level context menu
            action_new_group = menu.addAction("New Group")
            action_import_devices = menu.addAction("Import Devices...")
            
            # Show menu and handle result
            action = menu.exec_(self.viewport().mapToGlobal(position))
            
            if action == action_new_group:
                self.device_manager.create_group("New Group")
            elif action == action_import_devices:
                self._show_import_dialog()

    def _populate_group_menu(self, menu, device, add_only=True, source_index=None):
        """Populate a group submenu for a device"""
        groups = [g for g in self.device_manager.get_groups() if g != self.device_manager.root_group]
        if not groups:
            action = menu.addAction("No Groups Available")
            action.setEnabled(False)
            return
            
        source_group = None
        if source_index:
            source_group = source_index.parent().data(Qt.UserRole)
            
        for group in groups:
            action = menu.addAction(group.name)
            
            def on_triggered(checked=False, target_group=group):
                if add_only:
                    self.device_manager.add_device_to_group(device, target_group)
                    return
                    
                if source_group and source_group != self.device_manager.root_group and source_group != target_group:
                    self.device_manager.remove_device_from_group(device, source_group)
                self.device_manager.add_device_to_group(device, target_group)
                
            action.triggered.connect(on_triggered)

    def _show_import_dialog(self):
        """Show dialog for importing devices"""
        from .import_wizard import run_device_import_wizard
        
        run_device_import_wizard(self.device_manager, self)

    def _show_group_manager_dialog(self, group):
        """Show dialog for managing a group"""
        if not group:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Group: {group.name}")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Properties tab
        properties_tab = QWidget()
        properties_layout = QVBoxLayout(properties_tab)
        
        # Group properties form
        form_layout = QFormLayout()
        
        # Name field
        name_edit = QLineEdit(group.name)
        form_layout.addRow("Name:", name_edit)
        
        # Description field
        description_edit = QTextEdit(group.description)
        form_layout.addRow("Description:", description_edit)
        
        # Parent group selection
        parent_label = QLabel("Parent Group:")
        parent_combo = QComboBox()
        
        # Get all groups except this one and its descendants
        def add_groups_to_combo(group_list, exclude_group):
            for g in group_list:
                if g != exclude_group:
                    # Check if g is not a descendant of exclude_group
                    is_descendant = False
                    parent = g.parent
                    while parent:
                        if parent == exclude_group:
                            is_descendant = True
                            break
                        parent = parent.parent
                            
                    if not is_descendant:
                        parent_combo.addItem(g.name, g)
        
        add_groups_to_combo(self.device_manager.get_groups(), group)
        
        # Select current parent
        if group.parent:
            index = parent_combo.findText(group.parent.name)
            if index >= 0:
                parent_combo.setCurrentIndex(index)
                
        form_layout.addRow(parent_label, parent_combo)
        
        properties_layout.addLayout(form_layout)
        tab_widget.addTab(properties_tab, "Properties")
        
        # Devices tab
        devices_tab = QWidget()
        devices_tab_layout = QVBoxLayout(devices_tab)
        
        # Create device table
        devices_table = QTableWidget()
        devices_table.setColumnCount(4)
        devices_table.setHorizontalHeaderLabels(["Alias", "Hostname", "IP Address", "Status"])
        devices_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        devices_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        devices_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Add devices to table
        devices_table.setRowCount(len(group.devices))
        for i, device in enumerate(group.devices):
            devices_table.setItem(i, 0, QTableWidgetItem(device.get_property("alias", "")))
            devices_table.setItem(i, 1, QTableWidgetItem(device.get_property("hostname", "")))
            devices_table.setItem(i, 2, QTableWidgetItem(device.get_property("ip_address", "")))
            devices_table.setItem(i, 3, QTableWidgetItem(device.get_property("status", "")))
            
        devices_tab_layout.addWidget(devices_table)
        
        # Device actions
        device_buttons_layout = QHBoxLayout()
        add_device_button = QPushButton("Add Device")
        remove_device_button = QPushButton("Remove Selected")
        
        device_buttons_layout.addWidget(add_device_button)
        device_buttons_layout.addWidget(remove_device_button)
        devices_tab_layout.addLayout(device_buttons_layout)
        
        # Add devices tab
        tab_widget.addTab(devices_tab, f"Devices ({len(group.devices)})")
        
        # Subgroups tab
        subgroups_tab = QWidget()
        subgroups_layout = QVBoxLayout(subgroups_tab)
        
        # Create subgroups table
        subgroups_table = QTableWidget()
        subgroups_table.setColumnCount(2)
        subgroups_table.setHorizontalHeaderLabels(["Name", "Devices"])
        subgroups_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        subgroups_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        subgroups_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        subgroups_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Add subgroups to table
        subgroups_table.setRowCount(len(group.subgroups))
        for i, subgroup in enumerate(group.subgroups):
            subgroups_table.setItem(i, 0, QTableWidgetItem(subgroup.name))
            subgroups_table.setItem(i, 1, QTableWidgetItem(str(len(subgroup.get_all_devices()))))
            
        subgroups_layout.addWidget(subgroups_table)
        
        # Subgroup actions
        subgroup_buttons_layout = QHBoxLayout()
        add_subgroup_button = QPushButton("Add Subgroup")
        remove_subgroup_button = QPushButton("Remove Selected")
        
        subgroup_buttons_layout.addWidget(add_subgroup_button)
        subgroup_buttons_layout.addWidget(remove_subgroup_button)
        subgroups_layout.addLayout(subgroup_buttons_layout)
        
        # Add subgroups tab
        tab_widget.addTab(subgroups_tab, f"Subgroups ({len(group.subgroups)})")
        
        # Add tab widget to dialog
        layout.addWidget(tab_widget)
        
        # Add action buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        # Connect signals
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        # Add device button
        def on_add_device():
            # Show device selector dialog
            device_dialog = QDialog(dialog)
            device_dialog.setWindowTitle("Add Devices to Group")
            device_dialog.resize(500, 400)
            
            device_dialog_layout = QVBoxLayout(device_dialog)
            
            # Get all devices not already in the group
            all_devices = self.device_manager.get_devices()
            available_devices = [d for d in all_devices if d not in group.devices]
            
            if not available_devices:
                QMessageBox.information(
                    dialog,
                    "No Devices Available",
                    "All devices are already in this group."
                )
                return
                
            # Create device list
            device_list = QTableWidget()
            device_list.setColumnCount(4)
            device_list.setHorizontalHeaderLabels(["Alias", "Hostname", "IP Address", "Status"])
            device_list.setSelectionBehavior(QAbstractItemView.SelectRows)
            device_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
            device_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
            device_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            # Add devices to list
            device_list.setRowCount(len(available_devices))
            for i, device in enumerate(available_devices):
                device_list.setItem(i, 0, QTableWidgetItem(device.get_property("alias", "")))
                device_list.setItem(i, 1, QTableWidgetItem(device.get_property("hostname", "")))
                device_list.setItem(i, 2, QTableWidgetItem(device.get_property("ip_address", "")))
                device_list.setItem(i, 3, QTableWidgetItem(device.get_property("status", "")))
                
                # Store device object in item
                device_list.item(i, 0).setData(Qt.UserRole, device)
                
            device_dialog_layout.addWidget(device_list)
            
            # Add buttons
            device_dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            device_dialog_layout.addWidget(device_dialog_buttons)
            
            device_dialog_buttons.accepted.connect(device_dialog.accept)
            device_dialog_buttons.rejected.connect(device_dialog.reject)
            
            if device_dialog.exec():
                # Get selected devices
                selected_rows = device_list.selectionModel().selectedRows()
                selected_devices = []
                
                for index in selected_rows:
                    device = device_list.item(index.row(), 0).data(Qt.UserRole)
                    selected_devices.append(device)
                    
                # Add devices to group
                for device in selected_devices:
                    self.device_manager.add_device_to_group(device, group)
                    
                # Refresh devices table
                devices_table.setRowCount(len(group.devices))
                for i, device in enumerate(group.devices):
                    devices_table.setItem(i, 0, QTableWidgetItem(device.get_property("alias", "")))
                    devices_table.setItem(i, 1, QTableWidgetItem(device.get_property("hostname", "")))
                    devices_table.setItem(i, 2, QTableWidgetItem(device.get_property("ip_address", "")))
                    devices_table.setItem(i, 3, QTableWidgetItem(device.get_property("status", "")))
                    
                # Update tab title
                tab_widget.setTabText(1, f"Devices ({len(group.devices)})")
                
        add_device_button.clicked.connect(on_add_device)
        
        # Remove device button
        def on_remove_device():
            # Get selected devices
            selected_rows = devices_table.selectionModel().selectedRows()
            if not selected_rows:
                return
                
            # Confirm removal
            result = QMessageBox.question(
                dialog,
                "Confirm Removal",
                f"Remove {len(selected_rows)} device(s) from group '{group.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                # Get devices from table
                devices_to_remove = []
                for index in sorted(selected_rows, key=lambda x: x.row(), reverse=True):
                    row = index.row()
                    # Find device by alias
                    alias = devices_table.item(row, 0).text()
                    for device in group.devices:
                        if device.get_property("alias", "") == alias:
                            devices_to_remove.append(device)
                            break
                
                # Remove devices from group
                for device in devices_to_remove:
                    self.device_manager.remove_device_from_group(device, group)
                    
                # Refresh devices table
                devices_table.setRowCount(len(group.devices))
                for i, device in enumerate(group.devices):
                    devices_table.setItem(i, 0, QTableWidgetItem(device.get_property("alias", "")))
                    devices_table.setItem(i, 1, QTableWidgetItem(device.get_property("hostname", "")))
                    devices_table.setItem(i, 2, QTableWidgetItem(device.get_property("ip_address", "")))
                    devices_table.setItem(i, 3, QTableWidgetItem(device.get_property("status", "")))
                    
                # Update tab title
                tab_widget.setTabText(1, f"Devices ({len(group.devices)})")
                
        remove_device_button.clicked.connect(on_remove_device)
        
        # Add subgroup button
        def on_add_subgroup():
            # Show add subgroup dialog
            name, ok = QInputDialog.getText(
                dialog,
                "New Subgroup",
                "Enter name for new subgroup:"
            )
            
            if ok and name:
                # Check if group with this name already exists
                if self.device_manager.get_group(name):
                    QMessageBox.warning(
                        dialog,
                        "Group Already Exists",
                        f"A group named '{name}' already exists."
                    )
                    return
                    
                # Create new group
                new_group = self.device_manager.create_group(name, parent_group=group)
                
                # Refresh subgroups table
                subgroups_table.setRowCount(len(group.subgroups))
                for i, subgroup in enumerate(group.subgroups):
                    subgroups_table.setItem(i, 0, QTableWidgetItem(subgroup.name))
                    subgroups_table.setItem(i, 1, QTableWidgetItem(str(len(subgroup.get_all_devices()))))
                    
                # Update tab title
                tab_widget.setTabText(2, f"Subgroups ({len(group.subgroups)})")
                
        add_subgroup_button.clicked.connect(on_add_subgroup)
        
        # Remove subgroup button
        def on_remove_subgroup():
            # Get selected subgroups
            selected_rows = subgroups_table.selectionModel().selectedRows()
            if not selected_rows:
                return
                
            # Confirm removal
            result = QMessageBox.question(
                dialog,
                "Confirm Removal",
                f"Remove {len(selected_rows)} subgroup(s) from group '{group.name}'?\nThis will also remove all devices in these subgroups.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                # Get subgroups from table
                subgroups_to_remove = []
                for index in sorted(selected_rows, key=lambda x: x.row(), reverse=True):
                    row = index.row()
                    # Find subgroup by name
                    name = subgroups_table.item(row, 0).text()
                    for subgroup in group.subgroups:
                        if subgroup.name == name:
                            subgroups_to_remove.append(subgroup)
                            break
                
                # Remove subgroups
                for subgroup in subgroups_to_remove:
                    self.device_manager.remove_group(subgroup)
                    
                # Refresh subgroups table
                subgroups_table.setRowCount(len(group.subgroups))
                for i, subgroup in enumerate(group.subgroups):
                    subgroups_table.setItem(i, 0, QTableWidgetItem(subgroup.name))
                    subgroups_table.setItem(i, 1, QTableWidgetItem(str(len(subgroup.get_all_devices()))))
                    
                # Update tab title
                tab_widget.setTabText(2, f"Subgroups ({len(group.subgroups)})")
                
        remove_subgroup_button.clicked.connect(on_remove_subgroup)
        
        # Handle OK button
        if dialog.exec():
            # Update group properties
            new_name = name_edit.text().strip()
            new_description = description_edit.toPlainText()
            new_parent = parent_combo.currentData()
            
            # Update group
            if new_name != group.name:
                # Check if name is already used
                if self.device_manager.get_group(new_name):
                    QMessageBox.warning(
                        self,
                        "Group Name Exists",
                        f"A group named '{new_name}' already exists. Changes not saved."
                    )
                    return
                    
                group.name = new_name
                
            group.description = new_description
            
            # Update parent if changed
            if new_parent != group.parent:
                # Remove from current parent
                if group.parent:
                    group.parent.remove_subgroup(group)
                    
                # Add to new parent
                if new_parent:
                    new_parent.add_subgroup(group)
                    
                group.parent = new_parent
                
            # Notify of changes
            self.device_manager.group_changed.emit(group)

