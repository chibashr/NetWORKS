#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device tree model for NetWORKS.
"""

from .device_tree_item import DeviceTreeItem

from loguru import logger
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex, Slot, QMimeData
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QStyle

import json

from ..material_icons import material_icon


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
        
        if parent_item is None or parent_item == self.root_item:
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

