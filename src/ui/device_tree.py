#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree model and view for NetWORKS
"""

from loguru import logger
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex, Signal, Slot, QSortFilterProxyModel, QTimer, QSize, QMimeData, QSettings, QItemSelectionModel
from PySide6.QtWidgets import (QTreeView, QAbstractItemView, QMenu, QWidget,
                              QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                              QFileDialog, QLabel, QPushButton, QTextEdit,
                              QComboBox, QTableWidget, QTableWidgetItem, 
                              QHeaderView, QLineEdit, QFormLayout, QGroupBox,
                              QCheckBox, QWizard, QWizardPage, QMessageBox,
                              QDialogButtonBox, QInputDialog, QApplication,
                              QButtonGroup, QRadioButton, QPlainTextEdit,
                              QToolButton, QDockWidget, QSizePolicy, QStyle)
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap
from ..core.device_manager import Device
from .material_icons import material_icon
import os
import json


class DeviceTreeItem:
    """Item in the device tree"""
    
    def __init__(self, data, parent=None, device=None, group=None):
        """Initialize the tree item"""
        self.item_data = data
        self.parent_item = parent
        self.child_items = []
        self.device = device
        self.group = group
        self.device_ip = ""
        self.group_device_count = 0
        
    def appendChild(self, item):
        """Add a child to this item"""
        self.child_items.append(item)
        
    def child(self, row):
        """Get a child item"""
        if row < 0 or row >= len(self.child_items):
            return None
        return self.child_items[row]
        
    def childCount(self):
        """Get the number of children"""
        return len(self.child_items)
        
    def columnCount(self):
        """Get the number of columns"""
        return len(self.item_data)
        
    def data(self, column):
        """Get data for a column"""
        if column < 0 or column >= len(self.item_data):
            return None
        return self.item_data[column]
        
    def parent(self):
        """Get parent item"""
        return self.parent_item
        
    def row(self):
        """Get row number"""
        if self.parent_item:
            try:
                return self.parent_item.child_items.index(self)
            except ValueError:
                # Item not found in parent's child list
                logger.debug(f"DeviceTreeItem not found in parent's child list: {self.item_data[0]}")
                return 0
        return 0
        
    def removeChild(self, row):
        """Remove a child item"""
        if row < 0 or row >= len(self.child_items):
            return False
        self.child_items.pop(row)
        return True
        
    def removeAllChildren(self):
        """Remove all child items"""
        self.child_items = []
        
    def findChild(self, device=None, group=None):
        """Find a child item by device or group"""
        if device:
            for child in self.child_items:
                if child.device and child.device.id == device.id:
                    return child
        elif group:
            for child in self.child_items:
                if child.group and child.group.name == group.name:
                    return child
        return None


class DeviceTreeModel(QAbstractItemModel):
    """Model for device tree"""
    
    def __init__(self, device_manager):
        """Initialize the model"""
        super().__init__()
        
        self.device_manager = device_manager
        self._device_items = {}
        self._group_items = {}
        self._status_icon_cache = {}
        self._device_icon_cache = {}
        self._is_shutting_down = False
        
        # Create root item
        self.root_item = DeviceTreeItem(["Name", "IP Address"])
        
        # Connect to device manager signals
        self.device_manager.device_added.connect(self.on_device_added)
        self.device_manager.device_removed.connect(self.on_device_removed)
        self.device_manager.device_changed.connect(self.on_device_changed)
        self.device_manager.group_added.connect(self.on_group_added)
        self.device_manager.group_removed.connect(self.on_group_removed)
        self.device_manager.group_changed.connect(self.on_group_changed)
        
        # Initialize tree
        self.setup_model_data()
        
    def setup_model_data(self):
        """Set up the model data"""
        # Signal the model is about to be reset
        self.beginResetModel()
        
        # Reset the model data
        self._reset_model_data()
        
        # Signal the model has been reset
        self.endResetModel()
        
    def _reset_model_data(self):
        """Reset the model data without reset signals"""
        # Clear existing structure
        self.root_item.removeAllChildren()
        self._device_items = {}
        self._group_items = {}
        
        # Add root group (All Devices)
        root_group = self.device_manager.root_group
        self.add_group(root_group, self.root_item)
        
    def add_group(self, group, parent_item):
        """Add a group to the tree"""
        group_item = DeviceTreeItem([group.name, ""], parent_item, group=group)
        group_item.group_device_count = self._get_unique_device_count(group)
        parent_item.appendChild(group_item)
        self._group_items[group.name] = group_item
        
        # Add devices in this group
        for device in group.devices:
            self.add_device(device, group_item)
            
        # Add subgroups recursively
        for subgroup in group.subgroups:
            self.add_group(subgroup, group_item)
            
        return group_item
        
    def add_device(self, device, parent_item):
        """Add a device to the tree"""
        # Display alias/hostname in the name column, with IP address in a separate column
        display_name = (
            device.get_property("alias", "")
            or device.get_property("hostname", "")
            or device.get_property("ip_address", "")
            or "Unnamed Device"
        )
        ip_address = device.get_property("ip_address", "")
        device_item = DeviceTreeItem(
            [display_name, ip_address],
            parent_item,
            device=device
        )
        device_item.device_ip = ip_address
        parent_item.appendChild(device_item)
        self._device_items.setdefault(device.id, []).append(device_item)
        return device_item

    def _get_unique_device_count(self, group):
        """Get a unique device count for a group including subgroups"""
        device_ids = set()
        for device in group.get_all_devices():
            device_ids.add(device.id)
        return len(device_ids)

    def _status_icon(self, status):
        """Return a cached status icon for the given status"""
        if status in self._status_icon_cache:
            return self._status_icon_cache[status]
            
        color_map = {
            "online": QColor(46, 204, 113),
            "up": QColor(46, 204, 113),
            "active": QColor(46, 204, 113),
            "offline": QColor(231, 76, 60),
            "down": QColor(231, 76, 60),
            "error": QColor(231, 76, 60),
            "warning": QColor(241, 196, 15),
            "degraded": QColor(241, 196, 15),
            "unknown": QColor(149, 165, 166),
        }
        
        color = color_map.get(status, QColor(149, 165, 166))
        size = 10
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        
        icon = QIcon(pixmap)
        self._status_icon_cache[status] = icon
        return icon

    def _device_type_icon(self, device):
        """Return a cached device icon based on mac_vendor/vendor attributes."""
        # Get vendor property, handling cases where it might be a float or other non-string type
        mac_vendor = device.get_property("mac_vendor", "")
        vendor_prop = device.get_property("vendor", "")
        
        # Convert to string and get the first non-empty value
        vendor = ""
        for prop_value in [mac_vendor, vendor_prop]:
            if prop_value:
                vendor = str(prop_value).strip()
                if vendor:
                    break
        
        if not vendor:
            return None

        vendor_key = vendor.lower()
        if vendor_key in self._device_icon_cache:
            return self._device_icon_cache[vendor_key]

        icon = self._material_icon_for_vendor(vendor_key)
        if icon is None or icon.isNull():
            icon = self._fallback_icon_for_vendor(vendor_key)

        self._device_icon_cache[vendor_key] = icon
        return icon

    def _material_icon_for_vendor(self, vendor_key):
        vendor_map = [
            (["apple"], "laptop_mac"),
            (["raspberry", "raspberry pi"], "developer_board"),
            (["samsung", "lg", "huawei", "xiaomi", "oneplus", "google"], "smartphone"),
            (["cisco", "juniper", "ubiquiti", "mikrotik", "tp-link", "netgear", "d-link", "aruba"], "router"),
            (["brother", "canon", "epson", "xerox", "lexmark", "hp"], "print"),
            (["dell", "lenovo", "acer", "asus", "microsoft", "intel"], "desktop_windows"),
            (["vmware", "virtual", "qemu", "parallels"], "dns"),
            (["hikvision", "dahua", "axis", "sony", "panasonic"], "videocam"),
        ]
        for keywords, icon_name in vendor_map:
            if any(keyword in vendor_key for keyword in keywords):
                return material_icon(icon_name, self)
        return material_icon("devices", self)

    def _fallback_icon_for_vendor(self, vendor_key):
        style = QApplication.style()
        if any(keyword in vendor_key for keyword in ["cisco", "juniper", "ubiquiti", "mikrotik", "tp-link", "netgear", "d-link", "aruba"]):
            return style.standardIcon(QStyle.SP_DriveNetIcon)
        if any(keyword in vendor_key for keyword in ["brother", "canon", "epson", "xerox", "lexmark", "hp"]):
            return style.standardIcon(QStyle.SP_PrinterIcon)
        if any(keyword in vendor_key for keyword in ["vmware", "virtual", "qemu", "parallels"]):
            return style.standardIcon(QStyle.SP_DriveHDIcon)
        return style.standardIcon(QStyle.SP_ComputerIcon)
        
    def index(self, row, column, parent=QModelIndex()):
        """Create an index for an item"""
        # Guard against accessing model during shutdown
        if self._is_shutting_down:
            return QModelIndex()
        
        try:
            if not self.hasIndex(row, column, parent):
                return QModelIndex()
                
            parent_item = self.get_item(parent)
            if parent_item is None:
                return QModelIndex()
                
            child_item = parent_item.child(row)
            
            if child_item:
                return self.createIndex(row, column, child_item)
            return QModelIndex()
        except (RuntimeError, AttributeError):
            # Qt objects may be deleted during shutdown
            return QModelIndex()
        
    def parent(self, index):
        """Get parent index for an item"""
        if not index.isValid():
            return QModelIndex()
            
        child_item = self.get_item(index)
        parent_item = child_item.parent()
        
        if parent_item == self.root_item:
            return QModelIndex()
            
        try:
            return self.createIndex(parent_item.row(), 0, parent_item)
        except ValueError as e:
            # Log the error and return an invalid index
            logger.error(f"Error creating parent index: {e}")
            return QModelIndex()
            
    def rowCount(self, parent=QModelIndex()):
        """Get row count for a parent index"""
        # Guard against accessing model during shutdown
        if self._is_shutting_down:
            return 0
        
        try:
            parent_item = self.get_item(parent)
            if parent_item is None:
                return 0
            return parent_item.childCount()
        except (RuntimeError, AttributeError):
            # Qt objects may be deleted during shutdown
            return 0
        
    def columnCount(self, parent=QModelIndex()):
        """Get column count for a parent index"""
        return self.root_item.columnCount()
        
    def data(self, index, role):
        """Get data for an index"""
        if not index.isValid():
            return None
            
        item = self.get_item(index)
        
        if role == Qt.DisplayRole:
            if item.group and index.column() == 0:
                count = item.group_device_count or self._get_unique_device_count(item.group)
                return f"{item.group.name} ({count})"
            return item.data(index.column())
        elif role == Qt.UserRole:
            # Return the device or group object
            return item.device or item.group
        elif role == Qt.FontRole and item.group:
            # Make group names bold
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.DecorationRole and item.device and index.column() == 0:
            device_icon = self._device_type_icon(item.device)
            if device_icon is not None:
                return device_icon
            status = (item.device.get_property("status", "unknown") or "unknown").lower()
            return self._status_icon(status)
        elif role == Qt.ToolTipRole:
            if item.group:
                return item.group.description or f"Group: {item.group.name}"
            if item.device:
                alias = item.device.get_property("alias", "Unnamed Device")
                ip_address = item.device.get_property("ip_address", "")
                status = item.device.get_property("status", "unknown")
                details = [alias]
                if ip_address:
                    details.append(f"IP: {ip_address}")
                if status:
                    details.append(f"Status: {status}")
                return " | ".join(details)
                
        return None
        
    def headerData(self, section, orientation, role):
        """Get header data"""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.root_item.data(section)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        """Update data for inline edits"""
        if role != Qt.EditRole or not index.isValid():
            return False
            
        item = self.get_item(index)
        if item.group and index.column() == 0:
            new_name = str(value).strip()
            if not new_name:
                return False
                
            old_name = item.group.name
            if self.device_manager.rename_group(item.group, new_name):
                # Update group item mapping
                if old_name in self._group_items:
                    del self._group_items[old_name]
                self._group_items[item.group.name] = item
                item.item_data[0] = item.group.name
                self.dataChanged.emit(index, index)
                return True
        return False
        
    def flags(self, index):
        """Get flags for an index"""
        if not index.isValid():
            return Qt.NoItemFlags
            
        item = self.get_item(index)
        if item.group:
            return (
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsEditable
                | Qt.ItemIsDropEnabled
            )
            
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

    def mimeTypes(self):
        """Supported MIME types for drag and drop"""
        return ["application/x-networks-tree-item"]

    def mimeData(self, indexes):
        """Create MIME data for dragged items"""
        mime_data = QMimeData()
        items = []
        
        for index in indexes:
            if not index.isValid() or index.column() != 0:
                continue
            item = self.get_item(index)
            if item.device:
                source_group = item.parent_item.group if item.parent_item else None
                items.append({
                    "type": "device",
                    "id": item.device.id,
                    "source_group": source_group.name if source_group else None
                })
            elif item.group and item.group != self.device_manager.root_group:
                items.append({
                    "type": "group",
                    "name": item.group.name
                })
        
        if items:
            payload = json.dumps(items)
            mime_data.setData("application/x-networks-tree-item", payload.encode("utf-8"))
        
        return mime_data

    def supportedDropActions(self):
        """Supported drop actions"""
        return Qt.MoveAction | Qt.CopyAction

    def canDropMimeData(self, data, action, row, column, parent):
        """Validate drop targets"""
        if not data.hasFormat("application/x-networks-tree-item"):
            return False
            
        if not parent.isValid():
            # Allow dropping on the root to move groups to root
            return True
            
        parent_item = self.get_item(parent)
        if parent_item.group:
            return True
            
        return False

    def dropMimeData(self, data, action, row, column, parent):
        """Handle dropped items to move devices or groups"""
        if not data.hasFormat("application/x-networks-tree-item"):
            return False
            
        payload = data.data("application/x-networks-tree-item").data().decode("utf-8")
        try:
            items = json.loads(payload)
        except json.JSONDecodeError:
            return False
            
        target_group = None
        if parent.isValid():
            parent_item = self.get_item(parent)
            target_group = parent_item.group
        else:
            target_group = self.device_manager.root_group
            
        changed = False
        
        for item in items:
            if item.get("type") == "device":
                device = self.device_manager.get_device(item.get("id"))
                if not device or not target_group:
                    continue
                    
                source_group_name = item.get("source_group")
                source_group = self.device_manager.get_group(source_group_name) if source_group_name else None
                
                if source_group and source_group != self.device_manager.root_group and source_group != target_group:
                    self.device_manager.remove_device_from_group(device, source_group)
                    
                if target_group != self.device_manager.root_group:
                    self.device_manager.add_device_to_group(device, target_group)
                    changed = True
            elif item.get("type") == "group":
                group = self.device_manager.get_group(item.get("name"))
                if group and target_group and group != target_group:
                    if self.device_manager.move_group(group, target_group):
                        changed = True
        
        return changed
        
    def get_item(self, index):
        """Get item for an index"""
        # Guard against accessing model during shutdown
        if self._is_shutting_down:
            return self.root_item if hasattr(self, 'root_item') and self.root_item else None
        
        try:
            if index.isValid():
                item = index.internalPointer()
                if item:
                    return item
                    
            return self.root_item if hasattr(self, 'root_item') and self.root_item else None
        except (RuntimeError, AttributeError):
            # Qt objects may be deleted during shutdown
            return self.root_item if hasattr(self, 'root_item') and self.root_item else None

    def get_group_item(self, group_name):
        """Get the tree item for a group name"""
        return self._group_items.get(group_name)

    def get_device_items(self, device_id):
        """Get all tree items for a device ID"""
        return self._device_items.get(device_id, [])
        
    @Slot(object)
    def on_device_added(self, device):
        """Handle device added signal"""
        # Rebuild the model with proper reset signals
        self.beginResetModel()
        self._reset_model_data()
        self.endResetModel()
        
    @Slot(object)
    def on_device_removed(self, device):
        """Handle device removed signal"""
        # Rebuild the model with proper reset signals
        self.beginResetModel()
        self._reset_model_data()
        self.endResetModel()
        
    @Slot(object)
    def on_device_changed(self, device):
        """Handle device changed signal"""
        # Find the device in the tree and update just that item
        # instead of rebuilding the entire tree
        self._update_device_display(device)

    def _update_device_display(self, device):
        """Update a device's display in the tree without resetting the model"""
        # This method updates a device's display name without resetting the model
        
        # Find all instances of the device in the tree (it could be in multiple groups)
        self._update_device_in_item(self.root_item, device)

    def _update_device_in_item(self, item, device):
        """Update a device within a tree item and its children recursively"""
        # Check all children of this item
        for child in item.child_items:
            # If this child is the device we're looking for
            if child.device and child.device.id == device.id:
                # Update the display name in the data array
                display_name = device.get_property("alias", "") or device.get_property("hostname", "") or device.get_property("ip_address", "") or "Unnamed Device"
                ip_address = device.get_property("ip_address", "")
                if ip_address and display_name != ip_address:
                    display_name = f"{display_name} [{ip_address}]"
                child.item_data[0] = display_name
                child.device_ip = ip_address
                
                # Get the model index for this item
                row = child.row()
                if row >= 0:
                    parent_index = self.createIndex(item.row(), 0, item) if item != self.root_item else QModelIndex()
                    index = self.index(row, 0, parent_index)
                    # Emit dataChanged signal to update the view
                    self.dataChanged.emit(index, index)
                
            # Recursively check this child's children if it's a group
            if child.group:
                self._update_device_in_item(child, device)
        
    @Slot(object)
    def on_group_added(self, group):
        """Handle group added signal"""
        # Rebuild the model with proper reset signals
        self.beginResetModel()
        self._reset_model_data()
        self.endResetModel()
        
    @Slot(object)
    def on_group_removed(self, group):
        """Handle group removed signal"""
        # Rebuild the model with proper reset signals
        self.beginResetModel()
        self._reset_model_data()
        self.endResetModel()

    @Slot(object)
    def on_group_changed(self, group):
        """Handle group changed signal - rebuild for now as group membership may have changed"""
        # Rebuild the model with proper reset signals
        self.beginResetModel()
        self._reset_model_data()
        self.endResetModel()


class DeviceTreeFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy for the device tree"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(0)
        
    def set_filter_text(self, text):
        self._filter_text = (text or "").strip()
        self.invalidateFilter()
        
    def filterAcceptsRow(self, source_row, source_parent):
        if not self._filter_text:
            return True
            
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
            
        if self._row_matches(index):
            return True
            
        # Keep parents if any child matches
        child_count = model.rowCount(index)
        for row in range(child_count):
            if self.filterAcceptsRow(row, index):
                return True
                
        return False
        
    def _row_matches(self, index):
        text = index.data(Qt.DisplayRole) or ""
        if self._filter_text.lower() in str(text).lower():
            return True
            
        item = index.data(Qt.UserRole)
        if hasattr(item, "name"):
            return self._filter_text.lower() in item.name.lower()
        if hasattr(item, "get_property"):
            alias = item.get_property("alias", "")
            hostname = item.get_property("hostname", "")
            ip_address = item.get_property("ip_address", "")
            haystack = " ".join([alias, hostname, ip_address]).lower()
            return self._filter_text.lower() in haystack
            
        return False


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


class DeviceTreePanel(QWidget):
    """Panel combining tree controls and the device tree view"""
    
    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.setMinimumWidth(240)
        
        self.model = DeviceTreeModel(self.device_manager)
        self.proxy_model = DeviceTreeFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        
        self.view = DeviceTreeView(self.device_manager)
        self.view.setModel(self.proxy_model)
        
        self._create_ui()
        self.restore_state()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Search row
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search groups or devices...")
        clear_button = QToolButton()
        clear_button.setAutoRaise(True)
        clear_button.setIcon(material_icon("close", self, QStyle.SP_DialogResetButton))
        clear_button.setToolTip("Clear search text")
        clear_button.clicked.connect(self._clear_search)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 1)
        search_layout.addWidget(clear_button)
        
        # Toolbar row
        toolbar_layout = QHBoxLayout()
        self.compact_toggle = QCheckBox("Compact")
        self.filter_toggle = QCheckBox("Filter Table")
        expand_button = QToolButton()
        expand_button.setAutoRaise(True)
        expand_button.setIcon(material_icon("expand_more", self, QStyle.SP_ArrowDown))
        expand_button.setToolTip("Expand all groups")
        collapse_button = QToolButton()
        collapse_button.setAutoRaise(True)
        collapse_button.setIcon(material_icon("expand_less", self, QStyle.SP_ArrowUp))
        collapse_button.setToolTip("Collapse all groups")
        
        width_button = QToolButton()
        width_button.setAutoRaise(True)
        width_button.setIcon(material_icon("width_full", self, QStyle.SP_TitleBarMaxButton))
        width_button.setToolTip("Set a width preset for the device tree")
        width_button.setPopupMode(QToolButton.InstantPopup)
        width_menu = QMenu(self)
        width_menu.addAction("Narrow", lambda: self._apply_width_preset(260))
        width_menu.addAction("Medium", lambda: self._apply_width_preset(320))
        width_menu.addAction("Wide", lambda: self._apply_width_preset(420))
        width_button.setMenu(width_menu)
        
        toolbar_layout.addWidget(self.compact_toggle)
        toolbar_layout.addWidget(self.filter_toggle)
        toolbar_layout.addWidget(expand_button)
        toolbar_layout.addWidget(collapse_button)
        toolbar_layout.addWidget(width_button)
        toolbar_layout.addStretch(1)
        
        layout.addLayout(search_layout)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.view, 1)
        
        # Wire up actions
        self.search_edit.textChanged.connect(self.proxy_model.set_filter_text)
        self.compact_toggle.toggled.connect(self.view.set_compact_mode)
        self.filter_toggle.toggled.connect(self.view.set_filter_table_on_group_select)
        expand_button.clicked.connect(self.view.expandAll)
        collapse_button.clicked.connect(self.view.collapseAll)
        
    def _clear_search(self):
        self.search_edit.clear()
        
    def _apply_width_preset(self, width):
        dock = self._find_dock_widget()
        if dock:
            dock.setMinimumWidth(width)
            dock.resize(width, dock.height())
            self._save_width_preset(width)
        
    def _find_dock_widget(self):
        parent = self.parentWidget()
        while parent:
            if isinstance(parent, QDockWidget):
                return parent
            parent = parent.parentWidget()
        return None
        
    def _save_width_preset(self, width):
        settings = self.view._get_workspace_settings()
        settings.setValue("width_preset", width)
        
    def restore_state(self):
        """Restore UI state from workspace settings"""
        self.view.restore_state()
        self.compact_toggle.setChecked(self.view._compact_mode)
        self.filter_toggle.setChecked(self.view._filter_table_on_group_select)
        settings = self.view._get_workspace_settings()
        preset = settings.value("width_preset", None)
        if preset:
            try:
                self._apply_width_preset(int(preset))
            except (TypeError, ValueError):
                pass
        
    def save_state(self):
        """Persist UI state to workspace settings"""
        self.view.save_state()