#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device and DeviceGroup models for NetWORKS.

Extracted from device_manager to keep core models separate from manager logic.
"""

import os
import uuid
from loguru import logger
from PySide6.QtCore import QObject, Signal


class Device(QObject):
    """Base device class"""

    changed = Signal()

    def __init__(self, device_id=None, **properties):
        """Initialize a device with properties"""
        super().__init__()

        # Generate a UUID if none is provided
        self.id = device_id or str(uuid.uuid4())

        # Basic properties that all devices have
        self._properties = {
            "id": self.id,
            "alias": properties.get("alias", "Unnamed Device"),
            "hostname": properties.get("hostname", ""),
            "ip_address": properties.get("ip_address", ""),
            "mac_address": properties.get("mac_address", ""),
            "status": properties.get("status", "unknown"),
            "notes": properties.get("notes", ""),
            "tags": properties.get("tags", []),
        }

        # Update with any additional custom properties
        for key, value in properties.items():
            if key not in self._properties and key != "id":
                self._properties[key] = value

        # Store associated files
        self._associated_files = {}

    def get_properties(self):
        """Get all device properties"""
        return self._properties.copy()

    def get_property(self, key, default=None):
        """Get a device property"""
        return self._properties.get(key, default)

    def set_property(self, key, value):
        """Set a device property"""
        self._properties[key] = value
        self.changed.emit()

    def update_properties(self, properties):
        """Update multiple device properties"""
        self._properties.update(properties)
        self.changed.emit()

    def add_associated_file(self, file_type, file_path, copy=True):
        """
        Add an associated file to the device

        Args:
            file_type: Type of file (e.g., 'config', 'log', 'image')
            file_path: Path to the file
            copy: Whether to copy the file to the device directory

        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"Associated file not found: {file_path}")
            return False

        self._associated_files[file_type] = file_path
        return True

    def get_associated_file(self, file_type):
        """Get the path to an associated file"""
        return self._associated_files.get(file_type)

    def get_associated_files(self):
        """Get all associated files"""
        return self._associated_files.copy()

    def remove_associated_file(self, file_type):
        """Remove an associated file"""
        if file_type in self._associated_files:
            del self._associated_files[file_type]
            return True
        return False

    def to_dict(self):
        """Convert device to dictionary for serialization"""
        data = self.get_properties()
        data["associated_files"] = self._associated_files
        return data

    @classmethod
    def from_dict(cls, data):
        """Create a device from a dictionary"""
        device_id = data.pop("id", None)
        associated_files = data.pop("associated_files", {})
        device = cls(device_id=device_id, **data)
        device._associated_files = associated_files
        return device

    def __str__(self):
        """String representation of device"""
        return f"{self._properties.get('alias', 'Unknown')} ({self.id})"


class DeviceGroup(QObject):
    """Group of devices"""

    changed = Signal()
    device_added = Signal(object)
    device_removed = Signal(object)

    def __init__(self, name, description="", parent=None):
        """Initialize a device group"""
        super().__init__()
        self.name = name
        self.description = description
        self.devices = []
        self.parent = parent
        self.subgroups = []

    def add_device(self, device):
        """Add a device to the group"""
        if device not in self.devices:
            self.devices.append(device)
            device.changed.connect(self.changed)
            self.device_added.emit(device)
            self.changed.emit()

    def remove_device(self, device):
        """Remove a device from the group"""
        if device in self.devices:
            self.devices.remove(device)
            device.changed.disconnect(self.changed)
            self.device_removed.emit(device)
            self.changed.emit()

    def add_subgroup(self, group):
        """Add a subgroup to this group"""
        if group not in self.subgroups:
            self.subgroups.append(group)
            group.parent = self
            group.changed.connect(self.changed)
            self.changed.emit()

    def remove_subgroup(self, group):
        """Remove a subgroup from this group"""
        if group in self.subgroups:
            self.subgroups.remove(group)
            if group.parent == self:
                group.parent = None
            group.changed.disconnect(self.changed)
            self.changed.emit()

    def get_all_devices(self):
        """Get all devices in this group and subgroups"""
        all_devices = self.devices.copy()
        for subgroup in self.subgroups:
            all_devices.extend(subgroup.get_all_devices())
        return all_devices

    def to_dict(self):
        """Convert group to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "devices": [device.id for device in self.devices],
            "subgroups": [subgroup.to_dict() for subgroup in self.subgroups],
        }

    def __str__(self):
        """String representation of group"""
        return f"{self.name} ({len(self.devices)} devices, {len(self.subgroups)} subgroups)"
