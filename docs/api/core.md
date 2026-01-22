# NetWORKS Core API Documentation

This document provides detailed information about the core components of NetWORKS that plugins can interact with.

## Table of Contents

- [Device Manager](#device-manager)
- [Plugin Manager](#plugin-manager)
- [Plugin Interface](#plugin-interface)

## Device Manager

The `DeviceManager` class is responsible for managing devices and device groups. This is the primary API for plugins to interact with devices.

### Key Features

- Device creation, modification, and deletion
- Device grouping and organization
- Device selection management
- Persistence of device data
- Associated file management
- Workspace management

### Signals

```python
device_added: Signal(object)      # Emitted when a device is added
device_removed: Signal(object)    # Emitted when a device is removed
device_changed: Signal(object)    # Emitted when a device is changed
group_added: Signal(object)       # Emitted when a group is added
group_removed: Signal(object)     # Emitted when a group is removed
selection_changed: Signal(list)   # Emitted when device selection changes
```

### Core Methods

```python
# Device management
def add_device(self, device) -> Device
def remove_device(self, device) -> bool
def get_device(self, device_id) -> Device
def get_devices(self) -> list

# Group management
def create_group(self, name, description="", parent_group=None) -> DeviceGroup
def remove_group(self, group) -> bool
def get_group(self, name) -> DeviceGroup
def get_groups(self) -> list
def add_device_to_group(self, device, group) -> bool
def remove_device_from_group(self, device, group) -> bool

# Selection management
def select_device(self, device, exclusive=False) -> bool
def deselect_device(self, device) -> bool
def clear_selection(self) -> bool
def get_selected_devices(self) -> list

Note: `get_selected_devices()` returns the checkbox-based selection only. If you need menu behavior that uses highlighted rows when nothing is checked, use `DeviceTableView.get_selected_devices()`.

# Persistence
def save_devices(self) -> bool
def load_devices(self) -> bool

# Workspace management
def create_workspace(self, name, description="") -> bool
def delete_workspace(self, name) -> bool
def list_workspaces(self) -> list
def save_workspace(self, name=None) -> bool
def load_workspace(self, name) -> bool

# Refresh
def refresh_devices(self) -> bool
```

### Device Class

The `Device` class represents a network device with properties and associated files.

```python
class Device:
    # Signals
    changed: Signal()                      # Emitted when device properties change
    
    # Properties
    id: str                                # Unique device ID
    
    # Methods
    def get_properties(self) -> dict             # Get all device properties
    def get_property(self, key, default=None) -> Any  # Get a device property
    def set_property(self, key, value) -> None    # Set a device property
    def update_properties(self, properties) -> None  # Update multiple device properties
    
    # Associated file management
    def add_associated_file(self, file_type, file_path, copy=True) -> bool  # Add an associated file
    def get_associated_file(self, file_type) -> str  # Get path to an associated file
    def get_associated_files(self) -> dict  # Get all associated files
    def remove_associated_file(self, file_type) -> bool  # Remove an associated file
    
    # Serialization
    def to_dict(self) -> dict                    # Convert device to dictionary
    @classmethod from_dict(cls, data) -> Device  # Create device from dictionary
```

### DeviceGroup Class

The `DeviceGroup` class organizes devices into hierarchical groups.

```python
class DeviceGroup:
    # Signals
    changed: Signal()                      # Emitted when group changes
    device_added: Signal(object)           # Emitted when device is added to group
    device_removed: Signal(object)         # Emitted when device is removed from group
    
    # Properties
    name: str                              # Group name
    description: str                       # Group description
    devices: list                          # List of devices in the group
    subgroups: list                        # List of subgroups
    parent: DeviceGroup                    # Parent group (or None)
    
    # Methods
    def add_device(self, device)           # Add a device to the group
    def remove_device(self, device)        # Remove a device from the group
    def add_subgroup(self, group)          # Add a subgroup
    def remove_subgroup(self, group)       # Remove a subgroup
    def get_all_devices(self) -> list            # Get all devices in this group and subgroups
    def to_dict(self) -> dict                    # Convert group to dictionary
```

## Plugin Manager

The `PluginManager` class is responsible for plugin discovery, loading, and lifecycle management.

### Key Features

- Plugin discovery and registration
- Plugin loading and unloading
- Plugin enabling and disabling
- Plugin configuration management

### Signals

```python
plugin_loaded: Signal(object)    # Emitted when a plugin is loaded
plugin_unloaded: Signal(object)  # Emitted when a plugin is unloaded
plugin_enabled: Signal(object)   # Emitted when a plugin is enabled
plugin_disabled: Signal(object)  # Emitted when a plugin is disabled
```

### Core Methods

```python
# Plugin discovery
def discover_plugins(self) -> dict

# Plugin access
def get_plugins(self) -> list
def get_plugin(self, plugin_id) -> PluginInfo

# Plugin lifecycle
def load_plugin(self, plugin_id) -> PluginInterface
def unload_plugin(self, plugin_id) -> bool
def enable_plugin(self, plugin_id) -> bool
def disable_plugin(self, plugin_id) -> bool
def reload_plugin(self, plugin_id) -> PluginInterface
def load_all_plugins(self) -> list
def unload_all_plugins(self) -> list
```

### PluginInfo Class

The `PluginInfo` class represents metadata about a plugin.

```python
# Properties
id: str                # Plugin ID
name: str              # Plugin name
version: str           # Plugin version
description: str       # Plugin description
author: str            # Plugin author
entry_point: str       # Plugin entry point
path: str              # Plugin directory path
enabled: bool          # Whether the plugin is enabled
loaded: bool           # Whether the plugin is loaded
instance: PluginInterface  # Plugin instance (if loaded)

# Methods
def to_dict(self) -> dict
@classmethod def from_dict(cls, data) -> PluginInfo
```

## Plugin Interface

The `PluginInterface` class is the base class for all plugins. All plugins must inherit from this class and implement its methods.

### Lifecycle Methods

```python
def initialize(self)   # Called when the plugin is loaded
def start(self) -> bool   # Called when the plugin should start its operation
def stop(self) -> bool    # Called when the plugin should stop its operation
def cleanup(self) -> bool  # Called when the plugin is unloaded
```

### UI Extension Methods

```python
def get_toolbar_actions(self) -> list
def get_menu_actions(self) -> dict
def get_device_panels(self) -> list
def get_device_table_columns(self) -> list
def get_device_context_menu_actions(self) -> list
def get_device_tabs(self) -> list
def get_dock_widgets(self) -> list
    # Returns list of (widget_name, widget, area) tuples
    # IMPORTANT: Panel titles (QDockWidget titles) must use the full plugin name
    # Example: "Network Scanner" not "Scanner", "Command Manager" not "Commands"
def get_settings_pages(self) -> list
```

### Event Handler Methods

```python
def on_device_added(self, device)
def on_device_removed(self, device)
def on_device_changed(self, device)
def on_device_selected(self, devices)
def on_group_added(self, group)
def on_group_removed(self, group)
def on_plugin_loaded(self, plugin_info)
def on_plugin_unloaded(self, plugin_info)
```

### Properties

```python
app: Application          # Application instance
device_manager: DeviceManager  # Device manager
plugin_manager: PluginManager  # Plugin manager
config: Config           # Configuration manager
main_window: MainWindow  # Main window
```

### Signals

```python
plugin_initialized: Signal()  # Emitted when plugin is initialized
plugin_starting: Signal()     # Emitted when plugin is starting
plugin_running: Signal()      # Emitted when plugin is running
plugin_stopping: Signal()     # Emitted when plugin is stopping
plugin_cleaned_up: Signal()   # Emitted when plugin is cleaned up
plugin_error: Signal(str)     # Emitted when plugin encounters an error
``` 