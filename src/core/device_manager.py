#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Device manager for NetWORKS.
"""

from .device_models import Device, DeviceGroup

import os
import json
import shutil
import uuid
import datetime
from pathlib import Path
from loguru import logger
from PySide6.QtCore import QObject, Signal, QTimer, Slot


class DeviceManager(QObject):
    """Manages devices and device groups"""
    
    device_added = Signal(object)
    device_removed = Signal(object)
    device_changed = Signal(object)
    group_added = Signal(object)
    group_removed = Signal(object)
    group_changed = Signal(object)
    selection_changed = Signal(list)
    
    def __init__(self, app):
        """Initialize the device manager"""
        super().__init__()
        logger.debug("Initializing device manager")
        
        self.app = app
        self.devices = {}  # id -> Device
        self.groups = {}   # name -> DeviceGroup
        self.root_group = DeviceGroup("All Devices", "All devices in the system")
        self.groups["All Devices"] = self.root_group
        
        # Device selection (multiple devices can be selected)
        self.selected_devices = []
        
        # Recycle bin for storing deleted devices
        self.recycle_bin = {}  # id -> Device
        
        # Base path for config and workspace data
        self.base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config"
        )
        
        # Current workspace
        self.current_workspace = "default"
        self.workspaces_dir = os.path.join(self.base_dir, "workspaces")
        
    def initialize(self):
        """Initialize the device manager"""
        logger.debug("Initializing device manager")
        
        # Create necessary directories
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.workspaces_dir, exist_ok=True)
        
        # Check for legacy devices and migrate if needed
        legacy_devices_dir = os.path.join(self.base_dir, "devices")
        legacy_devices_file = os.path.join(self.base_dir, "devices.json")
        legacy_groups_file = os.path.join(self.base_dir, "groups.json")
        
        # Create default workspace if it doesn't exist
        default_workspace_dir = os.path.join(self.workspaces_dir, "default")
        if not os.path.exists(default_workspace_dir):
            self.create_workspace("default", "Default workspace")
            
            # If legacy files exist, migrate them to the default workspace
            if os.path.exists(legacy_devices_dir) or os.path.exists(legacy_devices_file):
                logger.info("Migrating legacy devices to workspace structure")
                
                # Create workspace devices directory
                workspace_devices_dir = os.path.join(default_workspace_dir, "devices")
                os.makedirs(workspace_devices_dir, exist_ok=True)
                
                # Migrate individual device directories
                if os.path.exists(legacy_devices_dir):
                    for device_id in os.listdir(legacy_devices_dir):
                        legacy_device_dir = os.path.join(legacy_devices_dir, device_id)
                        if os.path.isdir(legacy_device_dir):
                            # Copy device directory to workspace
                            workspace_device_dir = os.path.join(workspace_devices_dir, device_id)
                            if not os.path.exists(workspace_device_dir):
                                shutil.copytree(legacy_device_dir, workspace_device_dir)
                
                # Copy legacy groups file if it exists
                if os.path.exists(legacy_groups_file):
                    shutil.copy2(legacy_groups_file, os.path.join(default_workspace_dir, "groups.json"))
        
        # Load devices from current workspace
        self.load_workspace(self.current_workspace)
        
        # Set up auto-refresh if enabled
        refresh_interval = self.app.config.get("devices.refresh_interval", 60)
        if refresh_interval > 0:
            self.refresh_timer = QTimer(self)
            self.refresh_timer.timeout.connect(self.refresh_devices)
            self.refresh_timer.start(refresh_interval * 1000)
    
    def create_device(self, device_type="generic", **properties):
        """
        Create a new device with the specified properties
        
        This is the preferred way for plugins to create devices.
        
        Args:
            device_type (str): The type of device to create (default: "generic")
            **properties: Additional properties to set on the device
            
        Returns:
            Device: The newly created device (not yet added to the manager)
        """
        logger.debug(f"Creating new {device_type} device")
        
        # Generate a unique ID if not provided
        if "id" not in properties:
            device_id = str(uuid.uuid4())
            properties["id"] = device_id
        else:
            device_id = properties["id"]
            
        # Set default properties if not specified
        if "type" not in properties:
            properties["type"] = device_type
            
        if "name" not in properties:
            properties["name"] = f"New {device_type.capitalize()} Device"
            
        if "status" not in properties:
            properties["status"] = "unknown"
            
        if "created" not in properties:
            properties["created"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create the device
        device = Device(device_id=device_id, **properties)
        
        logger.debug(f"Created device: {device}")
        return device
        
    def add_new_device(self, device_type="generic", **properties):
        """
        Create a new device and add it to the device manager
        
        This is a convenience method that creates a device and adds it in one step.
        
        Args:
            device_type (str): The type of device to create
            **properties: Additional properties to set on the device
            
        Returns:
            Device: The newly created and added device
        """
        # Create the device
        device = self.create_device(device_type, **properties)
        
        # Add it to the manager
        self.add_device(device)
        
        return device
    
    def add_device(self, device):
        """Add a device to the system"""
        logger.debug(f"Adding device: {device}")
        
        if device.id in self.devices:
            logger.warning(f"Device with ID {device.id} already exists, updating instead")
            self.devices[device.id].update_properties(device.get_properties())
            self.device_changed.emit(self.devices[device.id])
            
            # Save to current workspace
            self.save_workspace()
            
            return self.devices[device.id]
        
        self.devices[device.id] = device
        self.root_group.add_device(device)
        
        # Connect to device signals
        device.changed.connect(lambda: self.device_changed.emit(device))
        
        # Emit signals
        self.device_added.emit(device)
        
        # Save device data directly to workspace
        workspace_dir = os.path.join(self.workspaces_dir, self.current_workspace)
        devices_dir = os.path.join(workspace_dir, "devices")
        os.makedirs(devices_dir, exist_ok=True)
        
        device_dir = os.path.join(devices_dir, device.id)
        os.makedirs(device_dir, exist_ok=True)
        
        device_file = os.path.join(device_dir, "device.json")
        with open(device_file, 'w') as f:
            json.dump(device.to_dict(), f, indent=2)
            
        # Update workspace info file
        info_file = os.path.join(workspace_dir, "workspace.json")
        if os.path.exists(info_file):
            try:
                with open(info_file, 'r') as f:
                    workspace_info = json.load(f)
                    
                if device.id not in workspace_info.get("devices", []):
                    workspace_info["devices"] = workspace_info.get("devices", []) + [device.id]
                    workspace_info["last_saved"] = str(datetime.datetime.now())
                    
                    with open(info_file, 'w') as f:
                        json.dump(workspace_info, f, indent=2)
            except Exception as e:
                logger.error(f"Error updating workspace info: {e}")
        
        return device
    
    def remove_device(self, device):
        """Move a device to the recycle bin"""
        if isinstance(device, str):
            device = self.get_device(device)
            
        if device and device.id in self.devices:
            logger.debug(f"Moving device to recycle bin: {device}")
            
            # Remove from selection
            if device in self.selected_devices:
                self.selected_devices.remove(device)
                self.selection_changed.emit(self.selected_devices)
            
            # Remove from groups but keep track of group membership
            device_groups = []
            for group in self.groups.values():
                if device in group.devices:
                    if group != self.root_group:  # Don't need to track root group
                        device_groups.append(group.name)
                    group.remove_device(device)
            
            # Store group membership in the device for later restoration
            device.set_property("_recycled_groups", device_groups)
            
            # Move to recycle bin
            self.recycle_bin[device.id] = device
            
            # Remove from devices dictionary
            del self.devices[device.id]
            
            # Emit signal
            self.device_removed.emit(device)
            
            # Save changes to workspace
            self.save_workspace()
            
            return True
        
        return False
    
    def get_recycle_bin_devices(self):
        """Get all devices in the recycle bin"""
        return list(self.recycle_bin.values())
    
    def restore_device(self, device):
        """Restore a device from the recycle bin"""
        if isinstance(device, str):
            device = self.recycle_bin.get(device)
            
        if device and device.id in self.recycle_bin:
            logger.debug(f"Restoring device from recycle bin: {device}")
            
            # Move from recycle bin to active devices
            self.devices[device.id] = device
            del self.recycle_bin[device.id]
            
            # Add back to groups
            recycled_groups = device.get_property("_recycled_groups", [])
            for group_name in recycled_groups:
                group = self.get_group(group_name)
                if group:
                    group.add_device(device)
            
            # Remove the _recycled_groups property
            if "_recycled_groups" in device._properties:
                del device._properties["_recycled_groups"]
            
            # Add to root group if not already there
            if device not in self.root_group.devices:
                self.root_group.add_device(device)
                
            # Emit signal
            self.device_added.emit(device)
            
            # Save changes to workspace
            self.save_workspace()
            
            return True
            
        return False
    
    def restore_all_devices(self):
        """Restore all devices from the recycle bin"""
        if not self.recycle_bin:
            return False
            
        devices_to_restore = list(self.recycle_bin.values())
        for device in devices_to_restore:
            self.restore_device(device)
            
        return True
    
    def permanently_delete_device(self, device):
        """Permanently delete a device (from recycle bin or active devices)"""
        if isinstance(device, str):
            device_id = device
            device = self.get_device(device_id) or self.recycle_bin.get(device_id)
        else:
            device_id = device.id
            
        if not device:
            return False
            
        logger.debug(f"Permanently deleting device: {device}")
        
        # If device is active, move it to recycle bin first
        if device_id in self.devices:
            self.remove_device(device)
            
        # Delete from recycle bin if it's there
        if device_id in self.recycle_bin:
            del self.recycle_bin[device_id]
            
            # Delete the device directory from workspace
            workspace_dir = os.path.join(self.workspaces_dir, self.current_workspace)
            device_dir = os.path.join(workspace_dir, "devices", device_id)
            if os.path.exists(device_dir):
                try:
                    shutil.rmtree(device_dir)
                except Exception as e:
                    logger.error(f"Error deleting device directory: {e}")
        
        # Save changes to workspace
        self.save_workspace()
        
        return True
        
    def empty_recycle_bin(self):
        """Permanently delete all devices in the recycle bin"""
        if not self.recycle_bin:
            return False
            
        devices_to_delete = list(self.recycle_bin.keys())
        for device_id in devices_to_delete:
            self.permanently_delete_device(device_id)
            
        # Save changes to workspace
        self.save_workspace()
        
        return True
    
    def get_device(self, device_id):
        """Get a device by ID"""
        return self.devices.get(device_id)
    
    def get_devices(self):
        """Get all devices"""
        return list(self.devices.values())
    
    def create_group(self, name, description="", parent_group=None):
        """Create a device group"""
        # Handle duplicate names by appending a number
        name = self._ensure_unique_group_name(name)
            
        logger.debug(f"Creating device group: {name}")
        group = DeviceGroup(name, description)
        self.groups[name] = group
        
        # Add to parent group
        if parent_group:
            if isinstance(parent_group, str):
                parent_group = self.groups.get(parent_group)
                
            if parent_group:
                parent_group.add_subgroup(group)
            else:
                logger.warning(f"Parent group not found, adding to root group")
                self.root_group.add_subgroup(group)
        else:
            self.root_group.add_subgroup(group)
            
        # Emit signal
        self.group_added.emit(group)
        
        # Save to workspace
        self.save_workspace()
        
        return group

    def _ensure_unique_group_name(self, name):
        """Ensure a group name is unique, appending a suffix if needed"""
        original_name = name.strip() or "New Group"
        name = original_name
        counter = 1
        
        while name in self.groups:
            # If the name already has a number at the end, increment it
            if original_name.rstrip().endswith(")") and " (" in original_name:
                base_name = original_name[:original_name.rindex(" (")]
                name = f"{base_name} ({counter})"
            else:
                name = f"{original_name} ({counter})"
            counter += 1
            
        return name

    def rename_group(self, group, new_name):
        """Rename a group and keep the group registry consistent"""
        if isinstance(group, str):
            group = self.groups.get(group)
            
        if not group or group == self.root_group:
            return False
            
        new_name = new_name.strip()
        if not new_name or new_name == group.name:
            return False
            
        unique_name = self._ensure_unique_group_name(new_name)
        
        # Update registry key
        if group.name in self.groups:
            del self.groups[group.name]
        group.name = unique_name
        self.groups[unique_name] = group
        
        self.group_changed.emit(group)
        self.save_workspace()
        return True

    def move_group(self, group, new_parent):
        """Move a group under a new parent group"""
        if isinstance(group, str):
            group = self.groups.get(group)
        if isinstance(new_parent, str):
            new_parent = self.groups.get(new_parent)
            
        if not group or group == self.root_group:
            return False
            
        if new_parent is None:
            new_parent = self.root_group
            
        if group == new_parent:
            return False
            
        if self._is_descendant(new_parent, group):
            logger.warning("Cannot move a group into one of its descendants")
            return False
            
        # Remove from current parent
        if group.parent:
            group.parent.remove_subgroup(group)
        else:
            # Fallback: find the parent in case the parent reference is missing
            for potential_parent in self.groups.values():
                if group in potential_parent.subgroups:
                    potential_parent.remove_subgroup(group)
                    break
                    
        # Add to new parent
        new_parent.add_subgroup(group)
        
        self.group_changed.emit(group)
        self.save_workspace()
        return True

    def _is_descendant(self, group, potential_ancestor):
        """Return True if group is inside potential_ancestor subtree"""
        parent = group.parent
        while parent:
            if parent == potential_ancestor:
                return True
            parent = parent.parent
        return False
    
    def remove_group(self, group):
        """Remove a device group"""
        if isinstance(group, str):
            group = self.groups.get(group)
            
        if group and group != self.root_group:
            logger.debug(f"Removing device group: {group}")
            
            # Remove from parent group
            for potential_parent in self.groups.values():
                if group in potential_parent.subgroups:
                    potential_parent.remove_subgroup(group)
                    break
                    
            # Remove from groups dictionary
            if group.name in self.groups:
                del self.groups[group.name]
                
            # Emit signal
            self.group_removed.emit(group)
            
            # Save to workspace
            self.save_workspace()
            
            return True
            
        return False
    
    def get_group(self, name):
        """Get a group by name"""
        return self.groups.get(name)
    
    def get_groups(self):
        """Get all groups"""
        return list(self.groups.values())
    
    def get_device_groups_for_device(self, device_id):
        """Get all groups that contain the specified device
        
        Args:
            device_id: The device ID or Device object
            
        Returns:
            list: List of DeviceGroup objects that contain the device
        """
        # Handle different input types
        if isinstance(device_id, Device):
            device = device_id
            device_id = device.id
        else:
            device = self.get_device(device_id)
            
        if not device:
            logger.warning(f"Device not found with ID: {device_id}")
            return []
            
        # Find all groups that contain this device
        device_groups = []
        for group in self.groups.values():
            # Check if device is in this group
            if device in group.devices:
                device_groups.append(group)
            
            # Check if device is in any subgroup
            for subgroup in group.subgroups:
                if self._check_device_in_group(device, subgroup):
                    device_groups.append(subgroup)
                    
        logger.debug(f"Found {len(device_groups)} groups for device: {device_id}")
        return device_groups
        
    def _check_device_in_group(self, device, group):
        """Check if a device is in a group or any of its subgroups
        
        Args:
            device: Device object
            group: DeviceGroup object
            
        Returns:
            bool: True if device is in the group or any subgroup, False otherwise
        """
        # Check if device is directly in this group
        if device in group.devices:
            return True
            
        # Check subgroups recursively
        for subgroup in group.subgroups:
            if self._check_device_in_group(device, subgroup):
                return True
                
        return False
    
    def add_device_to_group(self, device, group):
        """Add a device to a group"""
        if isinstance(device, str):
            device = self.get_device(device)
            
        if isinstance(group, str):
            group = self.get_group(group)
            
        if device and group:
            logger.debug(f"Adding device {device} to group {group}")
            group.add_device(device)
            # Emit the group_changed signal so the tree view can update
            self.group_changed.emit(group)
            return True
            
        return False
    
    def remove_device_from_group(self, device, group):
        """Remove a device from a group"""
        if isinstance(device, str):
            device = self.get_device(device)
            
        if isinstance(group, str):
            group = self.get_group(group)
            
        if device and group:
            logger.debug(f"Removing device {device} from group {group}")
            group.remove_device(device)
            # Emit the group_changed signal so the tree view can update
            self.group_changed.emit(group)
            return True
            
        return False
    
    def select_device(self, device, exclusive=False):
        """Select a device"""
        if isinstance(device, str):
            device = self.get_device(device)
            
        if device:
            if exclusive:
                logger.debug(f"Exclusively selecting device: {device.get_property('alias', 'Unnamed')} ({device.id})")
                self.selected_devices = [device]
            elif device not in self.selected_devices:
                logger.debug(f"Adding device to selection: {device.get_property('alias', 'Unnamed')} ({device.id})")
                self.selected_devices.append(device)
                
            self.selection_changed.emit(self.selected_devices)
            logger.debug(f"Total selected devices: {len(self.selected_devices)}")
            return True
            
        return False
    
    def deselect_device(self, device):
        """Deselect a device"""
        if isinstance(device, str):
            device = self.get_device(device)
            
        if device and device in self.selected_devices:
            logger.debug(f"Removing device from selection: {device.get_property('alias', 'Unnamed')} ({device.id})")
            self.selected_devices.remove(device)
            self.selection_changed.emit(self.selected_devices)
            logger.debug(f"Total selected devices: {len(self.selected_devices)}")
            return True
            
        return False
    
    def clear_selection(self):
        """Clear device selection"""
        if self.selected_devices:
            logger.debug(f"Clearing selection of {len(self.selected_devices)} devices")
            self.selected_devices = []
            self.selection_changed.emit(self.selected_devices)
            return True
            
        return False
    
    def get_selected_devices(self):
        """Get selected devices"""
        return self.selected_devices.copy()
    
    def save_devices(self):
        """Save all devices to the current workspace"""
        logger.debug("Saving all devices to workspace")
        
        # Save to current workspace
        return self.save_workspace(self.current_workspace)
    
    def _save_device(self, device):
        """Save a single device to its JSON file"""
        device_dir = os.path.join(self.devices_dir, device.id)
        os.makedirs(device_dir, exist_ok=True)
        
        device_file = os.path.join(device_dir, "device.json")
        
        try:
            with open(device_file, 'w') as f:
                json.dump(device.to_dict(), f, indent=2)
                
            # Copy associated files if needed
            for file_type, file_path in device.get_associated_files().items():
                if os.path.exists(file_path):
                    dest_path = os.path.join(device_dir, os.path.basename(file_path))
                    if file_path != dest_path:  # Don't copy if it's already in the right place
                        shutil.copy2(file_path, dest_path)
                        device._associated_files[file_type] = dest_path
            
            return True
        except Exception as e:
            logger.error(f"Error saving device {device.id}: {e}")
            return False
    
    def _save_groups(self):
        """Save groups structure to file"""
        groups_file = os.path.join(self.base_dir, "groups.json")
        
        try:
            groups_data = {
                "groups": [group.to_dict() for group in self.groups.values() if group != self.root_group]
            }
            
            with open(groups_file, 'w') as f:
                json.dump(groups_data, f, indent=2)
                
            return True
        except Exception as e:
            logger.error(f"Error saving groups: {e}")
            return False
    
    def _delete_device_file(self, device_id):
        """Delete a device's directory and files"""
        device_dir = os.path.join(self.devices_dir, device_id)
        
        if os.path.exists(device_dir):
            try:
                shutil.rmtree(device_dir)
                return True
            except Exception as e:
                logger.error(f"Error deleting device directory {device_dir}: {e}")
                return False
        return True  # Directory didn't exist, so deletion "succeeded"
    
    def load_devices(self):
        """Load devices from individual files"""
        # Clear existing devices and groups (except root)
        self.devices = {}
        self.groups = {"All Devices": self.root_group}
        self.root_group.devices = []
        self.root_group.subgroups = []
        
        success = True
        
        # Check if devices directory exists
        if not os.path.exists(self.devices_dir):
            os.makedirs(self.devices_dir, exist_ok=True)
            
            # Try loading from legacy file
            if os.path.exists(self.devices_file):
                logger.info("No devices directory, trying to load from legacy file")
                if self._load_legacy_devices():
                    # Save in new format
                    self.save_devices()
                return True
            
            return True  # No devices to load
        
        # Load devices from individual files
        for device_id in os.listdir(self.devices_dir):
            device_dir = os.path.join(self.devices_dir, device_id)
            if os.path.isdir(device_dir):
                device_file = os.path.join(device_dir, "device.json")
                if os.path.exists(device_file):
                    try:
                        with open(device_file, 'r') as f:
                            device_data = json.load(f)
                            
                        device = Device.from_dict(device_data)
                        self.devices[device.id] = device
                        device.changed.connect(lambda d=device: self.device_changed.emit(d))
                    except Exception as e:
                        logger.error(f"Error loading device {device_id}: {e}")
                        success = False
        
        # Load groups
        if not self._load_groups():
            success = False
            
        # Add all devices to root group
        for device in self.devices.values():
            if device not in self.root_group.devices:
                self.root_group.add_device(device)
                
        logger.info(f"Loaded {len(self.devices)} devices and {len(self.groups)-1} groups")
        return success
    
    def _load_legacy_devices(self):
        """Load devices from legacy file"""
        try:
            with open(self.devices_file, 'r') as f:
                data = json.load(f)
                
            # Load devices
            for device_data in data.get("devices", []):
                device = Device.from_dict(device_data)
                self.devices[device.id] = device
                device.changed.connect(lambda d=device: self.device_changed.emit(d))
                
            # Load groups
            for group_data in data.get("groups", []):
                self._load_group(group_data, self.root_group)
                
            # Add all devices to root group
            for device in self.devices.values():
                if device not in self.root_group.devices:
                    self.root_group.add_device(device)
                    
            logger.info(f"Loaded {len(self.devices)} devices and {len(self.groups)-1} groups from legacy file")
            return True
        except Exception as e:
            logger.error(f"Error loading legacy devices: {e}")
            return False
    
    def _load_groups(self):
        """Load groups from file"""
        groups_file = os.path.join(self.base_dir, "groups.json")
        
        if not os.path.exists(groups_file):
            return True  # No groups to load
            
        try:
            with open(groups_file, 'r') as f:
                data = json.load(f)
                
            for group_data in data.get("groups", []):
                self._load_group(group_data, self.root_group)
                
            return True
        except Exception as e:
            logger.error(f"Error loading groups: {e}")
            return False
    
    def _load_group(self, group_data, parent_group):
        """Recursively load a group from data"""
        name = group_data.get("name")
        if not name:
            return None
            
        # Create group
        group = DeviceGroup(name, group_data.get("description", ""))
        self.groups[name] = group
        parent_group.add_subgroup(group)
        
        # Add devices to group
        for device_id in group_data.get("devices", []):
            device = self.devices.get(device_id)
            if device:
                group.add_device(device)
                
        # Load subgroups
        for subgroup_data in group_data.get("subgroups", []):
            self._load_group(subgroup_data, group)
            
        return group
    
    # Workspace management
    
    def create_workspace(self, name, description=""):
        """Create a new workspace"""
        logger.debug(f"Creating workspace: {name}")
        
        workspace_dir = os.path.join(self.workspaces_dir, name)
        if os.path.exists(workspace_dir):
            logger.warning(f"Workspace {name} already exists")
            return False
            
        os.makedirs(workspace_dir, exist_ok=True)
        
        # Create workspace info file
        workspace_info = {
            "name": name,
            "description": description,
            "created": str(datetime.datetime.now()),
            "devices": [],
            "groups": [],
            "enabled_plugins": []
        }
        
        try:
            with open(os.path.join(workspace_dir, "workspace.json"), 'w') as f:
                json.dump(workspace_info, f, indent=2)
                
            logger.info(f"Created workspace: {name}")
            return True
        except Exception as e:
            logger.error(f"Error creating workspace {name}: {e}")
            return False
    
    def delete_workspace(self, name):
        """Delete a workspace"""
        if name == "default":
            logger.warning("Cannot delete default workspace")
            return False
            
        workspace_dir = os.path.join(self.workspaces_dir, name)
        if not os.path.exists(workspace_dir):
            logger.warning(f"Workspace {name} does not exist")
            return False
            
        try:
            shutil.rmtree(workspace_dir)
            logger.info(f"Deleted workspace: {name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting workspace {name}: {e}")
            return False
    
    def list_workspaces(self):
        """List all available workspaces"""
        workspaces = []
        
        if not os.path.exists(self.workspaces_dir):
            return workspaces
            
        for name in os.listdir(self.workspaces_dir):
            workspace_dir = os.path.join(self.workspaces_dir, name)
            if os.path.isdir(workspace_dir):
                info_file = os.path.join(workspace_dir, "workspace.json")
                if os.path.exists(info_file):
                    try:
                        with open(info_file, 'r') as f:
                            info = json.load(f)
                            workspaces.append(info)
                    except Exception:
                        # If can't read info, just add the name
                        workspaces.append({"name": name})
                else:
                    workspaces.append({"name": name})
                    
        return workspaces
    
    def save_workspace(self, name=None):
        """Save current state to a workspace"""
        if name is None:
            name = self.current_workspace
            
        logger.debug(f"Saving workspace: {name}")
        
        return self._save_workspace(name)
    
    def _save_workspace(self, name):
        """Save current state to a workspace"""
        workspace_dir = os.path.join(self.workspaces_dir, name)
        os.makedirs(workspace_dir, exist_ok=True)
        
        # Get current enabled plugins
        enabled_plugins = []
        if hasattr(self.app, 'plugin_manager'):
            enabled_plugins = [
                p.id for p in self.app.plugin_manager.get_plugins() 
                if p.enabled
            ]
        
        # Create workspace info
        workspace_info = {
            "name": name,
            "description": f"Workspace {name}",
            "last_saved": str(datetime.datetime.now()),
            "devices": list(self.devices.keys()),
            "groups": list(self.groups.keys()),
            "enabled_plugins": enabled_plugins,
            "recycle_bin": list(self.recycle_bin.keys())
        }
        
        try:
            # Save workspace info
            with open(os.path.join(workspace_dir, "workspace.json"), 'w') as f:
                json.dump(workspace_info, f, indent=2)
                
            # Save groups to workspace directly
            groups_data = {
                "groups": [group.to_dict() for group in self.groups.values() if group != self.root_group]
            }
            with open(os.path.join(workspace_dir, "groups.json"), 'w') as f:
                json.dump(groups_data, f, indent=2)
                
            # Create devices directory within workspace
            devices_dir = os.path.join(workspace_dir, "devices")
            os.makedirs(devices_dir, exist_ok=True)
            
            # Save full device data to workspace (active devices)
            for device_id, device in self.devices.items():
                device_dir = os.path.join(devices_dir, device_id)
                os.makedirs(device_dir, exist_ok=True)
                
                # Save device data
                with open(os.path.join(device_dir, "device.json"), 'w') as f:
                    json.dump(device.to_dict(), f, indent=2)
                
                # Copy associated files
                for file_type, file_path in device.get_associated_files().items():
                    if os.path.exists(file_path):
                        dest_path = os.path.join(device_dir, os.path.basename(file_path))
                        if file_path != dest_path:  # Don't copy if it's already in the right place
                            shutil.copy2(file_path, dest_path)
                    
            # Save recycle bin devices
            for device_id, device in self.recycle_bin.items():
                device_dir = os.path.join(devices_dir, device_id)
                os.makedirs(device_dir, exist_ok=True)
                
                # Save device data with a flag indicating it's in the recycle bin
                device_data = device.to_dict()
                device_data["_in_recycle_bin"] = True
                
                with open(os.path.join(device_dir, "device.json"), 'w') as f:
                    json.dump(device_data, f, indent=2)
                    
            logger.info(f"Saved workspace: {name}")
            return True
        except Exception as e:
            logger.error(f"Error saving workspace {name}: {e}")
            return False
    
    def load_workspace(self, name):
        """Load a workspace"""
        if name == self.current_workspace and self.devices:
            logger.debug(f"Already in workspace {name}")
            # Even if we're already in this workspace, we should reload it to ensure
            # the UI is properly updated - do not return early
            
        workspace_dir = os.path.join(self.workspaces_dir, name)
        
        # If workspace doesn't exist, create it
        if not os.path.exists(workspace_dir):
            logger.info(f"Workspace {name} doesn't exist, creating it")
            self.create_workspace(name)
            
            # Clear current state since we're switching to a new empty workspace
            self.clear_current_state()
            
            # Set the current workspace
            self.current_workspace = name
            
            # Log the workspace change
            logger.info(f"Loaded workspace: {name} with 0 devices and 0 groups")
            return True
            
        logger.debug(f"Loading workspace: {name}")
        
        # Load workspace info
        info_file = os.path.join(workspace_dir, "workspace.json")
        if not os.path.exists(info_file):
            logger.warning(f"Workspace info file not found for {name}")
            return False
            
        try:
            with open(info_file, 'r') as f:
                workspace_info = json.load(f)
                
            # Clear current state
            self.clear_current_state()
            
            # Restore plugin states if plugin_manager is available
            if hasattr(self.app, 'plugin_manager') and 'enabled_plugins' in workspace_info:
                plugin_manager = self.app.plugin_manager
                # Get the plugin IDs listed as enabled in the workspace
                enabled_plugins = workspace_info.get('enabled_plugins', [])
                logger.debug(f"Workspace {name} has {len(enabled_plugins)} enabled plugins: {', '.join(enabled_plugins)}")
                
                try:
                    # First, discover all available plugins to ensure we have a complete list
                    # Only discover if not already discovering (to avoid duplicate calls during init)
                    if not plugin_manager._discovering:
                        logger.debug("Discovering plugins for workspace...")
                        plugin_manager.discover_plugins()
                    else:
                        logger.debug("Plugin discovery already in progress, skipping duplicate call")
                    
                    # Enable all plugins first, then load them to avoid dependency order issues
                    for plugin_id in enabled_plugins:
                        try:
                            if plugin_id in plugin_manager.plugins:
                                if not plugin_manager.plugins[plugin_id].state.is_enabled:
                                    logger.debug(f"Enabling plugin {plugin_id} from workspace configuration")
                                    plugin_manager.enable_plugin(plugin_id)
                            else:
                                logger.warning(f"Plugin {plugin_id} specified in workspace configuration not found")
                        except Exception as e:
                            logger.error(f"Error enabling plugin {plugin_id}: {e}", exc_info=True)
                            # Continue with other plugins even if one fails
                    
                    for plugin_id in enabled_plugins:
                        try:
                            if plugin_id in plugin_manager.plugins:
                                # Ensure the plugin is loaded if enabled
                                if (not plugin_manager.plugins[plugin_id].state.is_loaded and 
                                    plugin_manager.plugins[plugin_id].state.is_enabled):
                                    logger.debug(f"Loading plugin {plugin_id} from workspace configuration")
                                    plugin_manager.load_plugin(plugin_id)
                            else:
                                logger.warning(f"Plugin {plugin_id} specified in workspace configuration not found")
                        except Exception as e:
                            logger.error(f"Error loading plugin {plugin_id}: {e}", exc_info=True)
                            # Continue with other plugins even if one fails
                except Exception as e:
                    logger.error(f"Error during plugin discovery/loading: {e}", exc_info=True)
                    # Continue with workspace loading even if plugins fail
            
            # Load devices from workspace directory
            workspace_devices_dir = os.path.join(workspace_dir, "devices")
            if os.path.exists(workspace_devices_dir):
                for device_id in os.listdir(workspace_devices_dir):
                    device_dir = os.path.join(workspace_devices_dir, device_id)
                    if os.path.isdir(device_dir):
                        device_file = os.path.join(device_dir, "device.json")
                        if os.path.exists(device_file):
                            try:
                                with open(device_file, 'r') as f:
                                    device_data = json.load(f)
                                
                                # Check if it's a recycle bin device
                                in_recycle_bin = device_data.pop("_in_recycle_bin", False)
                                
                                device = Device.from_dict(device_data)
                                
                                if in_recycle_bin:
                                    # Add to recycle bin
                                    self.recycle_bin[device.id] = device
                                else:
                                    # Add to active devices
                                    self.devices[device.id] = device
                                    device.changed.connect(lambda d=device: self.device_changed.emit(d))
                                    
                                    # Emit signal for each loaded device
                                    self.device_added.emit(device)
                            except Exception as e:
                                logger.error(f"Error loading device {device_id}: {e}")
            
            # Load groups directly from workspace
            groups_file = os.path.join(workspace_dir, "groups.json")
            if os.path.exists(groups_file):
                try:
                    with open(groups_file, 'r') as f:
                        data = json.load(f)
                        
                    for group_data in data.get("groups", []):
                        group = self._load_group(group_data, self.root_group)
                        if group:
                            # Emit signal for each loaded group
                            self.group_added.emit(group)
                except Exception as e:
                    logger.error(f"Error loading groups from workspace: {e}")
            
            # Add all devices to root group
            for device in self.devices.values():
                if device not in self.root_group.devices:
                    self.root_group.add_device(device)
            
            self.current_workspace = name
            
            # Clear any device selection
            self.clear_selection()
            
            logger.info(f"Loaded workspace: {name} with {len(self.devices)} devices and {len(self.groups)-1} groups")
            logger.info(f"Recycle bin contains {len(self.recycle_bin)} devices")
            return True
        except Exception as e:
            logger.error(f"Error loading workspace {name}: {e}")
            return False
    
    def clear_current_state(self):
        """Clear the current device and group state"""
        # Disconnect signals from existing devices
        for device in self.devices.values():
            device.changed.disconnect()
        
        # Clear devices
        self.devices = {}
        
        # Clear recycle bin
        self.recycle_bin = {}
        
        # Clear groups but keep the root group
        self.groups = {"All Devices": self.root_group}
        self.root_group.devices = []
        self.root_group.subgroups = []
        
        # Clear selection
        self.selected_devices = []
    
    @Slot()
    def refresh_devices(self):
        """Refresh device status"""
        logger.debug("Refreshing devices")
        
        # This would typically reach out to devices and update their status
        # For now, we'll just emit signals for all devices to notify listeners
        for device in self.devices.values():
            self.device_changed.emit(device)
            
        return True 