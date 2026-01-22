# NetWORKS API Documentation

This document provides an overview of the NetWORKS API for plugin developers. It describes the interfaces and classes that plugins can interact with.

## Table of Contents

- [Application](#application)
- [Device Manager](#device-manager)
- [Plugin Manager](#plugin-manager)
- [Configuration Manager](#configuration-manager)
- [UI Components](#ui-components)
- [Plugin Interface](#plugin-interface)

## Application

The `Application` class is the main entry point for the application. Plugins receive a reference to this class in their constructor.

```python
class Application:
    def __init__(self, argv)
    @property device_manager: DeviceManager  # Access to the device manager
    @property plugin_manager: PluginManager  # Access to the plugin manager
    @property config: Config                 # Access to the configuration manager
    @property main_window: MainWindow        # Access to the main window (only available after initialization)
```

## Device Manager

The `DeviceManager` class manages devices and device groups.

```python
class DeviceManager:
    # Signals
    device_added: Signal(object)            # Emitted when a device is added
    device_removed: Signal(object)          # Emitted when a device is removed
    device_changed: Signal(object)          # Emitted when a device is changed
    group_added: Signal(object)             # Emitted when a group is added
    group_removed: Signal(object)           # Emitted when a group is removed
    group_changed: Signal(object)           # Emitted when a group is changed (devices added/removed)
    selection_changed: Signal(list)         # Emitted when device selection changes
    
    # Methods
    def add_device(self, device): Device    # Add a device to the system
    def remove_device(self, device): bool   # Remove a device from the system
    def get_device(self, device_id): Device # Get a device by ID
    def get_devices(): list                 # Get all devices
    def create_group(self, name, description="", parent_group=None): DeviceGroup  # Create a device group
    def remove_group(self, group): bool     # Remove a device group
    def get_group(self, name): DeviceGroup  # Get a group by name
    def get_groups(): list                  # Get all groups
    def add_device_to_group(self, device, group): bool  # Add a device to a group
    def remove_device_from_group(self, device, group): bool  # Remove a device from a group
    def select_device(self, device, exclusive=False): bool  # Select a device
    def deselect_device(self, device): bool  # Deselect a device
    def clear_selection(): bool             # Clear device selection
    def get_selected_devices(): list        # Get checkbox-selected devices
    def save_devices(): bool                # Save devices to file
    def load_devices(): bool                # Load devices from file
    def refresh_devices(): bool             # Refresh device status
```

### Device Class

```python
class Device:
    # Signals
    changed: Signal()                      # Emitted when device properties change
    
    # Properties
    id: str                                # Unique device ID
    
    # Methods
    def get_properties(): dict             # Get all device properties
    def get_property(self, key, default=None)  # Get a device property
    def set_property(self, key, value)     # Set a device property
    def update_properties(self, properties)  # Update multiple device properties
    def to_dict(): dict                    # Convert device to dictionary
    @classmethod from_dict(cls, data): Device  # Create device from dictionary
```

### DeviceGroup Class

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
    def get_all_devices(): list            # Get all devices in this group and subgroups
    def to_dict(): dict                    # Convert group to dictionary
```

## Plugin Manager

The `PluginManager` class manages plugin discovery, loading, and lifecycle.

```python
class PluginManager:
    # Signals
    plugin_loaded: Signal(object)          # Emitted when a plugin is loaded
    plugin_unloaded: Signal(object)        # Emitted when a plugin is unloaded
    plugin_enabled: Signal(object)         # Emitted when a plugin is enabled
    plugin_disabled: Signal(object)        # Emitted when a plugin is disabled
    
    # Methods
    def discover_plugins(): dict           # Discover available plugins
    def get_plugins(): list                # Get all plugins
    def get_plugin(self, plugin_id): PluginInfo  # Get a plugin by ID
    def load_plugin(self, plugin_id): PluginInterface  # Load a plugin by ID
    def unload_plugin(self, plugin_id): bool  # Unload a plugin by ID
    def enable_plugin(self, plugin_id): bool  # Enable a plugin by ID
    def disable_plugin(self, plugin_id): bool  # Disable a plugin by ID
    def reload_plugin(self, plugin_id): PluginInterface  # Reload a plugin by ID
    def load_all_plugins(): list           # Load all enabled plugins
    def unload_all_plugins(): list         # Unload all loaded plugins
```

### PluginInfo Class

```python
class PluginInfo:
    # Properties
    id: str                               # Plugin ID
    name: str                             # Plugin name
    version: str                          # Plugin version
    description: str                      # Plugin description
    author: str                           # Plugin author
    entry_point: str                      # Plugin entry point
    path: str                             # Plugin directory path
    enabled: bool                         # Whether the plugin is enabled
    loaded: bool                          # Whether the plugin is loaded
    instance: PluginInterface             # Plugin instance (if loaded)
    
    # Methods
    def to_dict(): dict                   # Convert to dictionary
    @classmethod from_dict(cls, data): PluginInfo  # Create from dictionary
```

## Configuration Manager

The `Config` class manages application and plugin configuration.

```python
class Config:
    # Signals
    config_changed: Signal()              # Emitted when configuration changes
    
    # Methods
    def load()                            # Load configuration from files
    def save()                            # Save user configuration to file
    def get(self, key, default=None)      # Get a configuration value by key
    def set(self, key, value)             # Set a configuration value by key
    def update_plugin_config(self, plugin_id, config)  # Update configuration for a plugin
    def get_plugin_config(self, plugin_id): dict  # Get configuration for a plugin
```

## UI Components

### MainWindow Class

See [src/ui/API.md](src/ui/API.md) for detailed documentation of UI components.

Note: Menu actions should prefer `DeviceTableView.get_selected_devices()` when available because it falls back to highlighted rows when no checkboxes are selected.

## Plugin Interface

The `PluginInterface` class is the base class for all plugins.

```python
class PluginInterface:
    # Signals
    plugin_initialized: Signal()          # Emitted when plugin is initialized
    plugin_starting: Signal()             # Emitted when plugin is starting
    plugin_running: Signal()              # Emitted when plugin is running
    plugin_stopping: Signal()             # Emitted when plugin is stopping
    plugin_cleaned_up: Signal()           # Emitted when plugin is cleaned up
    plugin_error: Signal(str)             # Emitted when plugin encounters an error
    
    # Properties
    app: Application                      # Application instance
    device_manager: DeviceManager         # Device manager instance
    plugin_manager: PluginManager         # Plugin manager instance
    config: Config                        # Configuration manager instance
    main_window: MainWindow               # Main window instance
    
    # Methods (to implement)
    def initialize()                      # Initialize the plugin
    def start(): bool                     # Start the plugin
    def stop(): bool                      # Stop the plugin
    def cleanup(): bool                   # Clean up the plugin
    
    # UI extension methods (to implement)
    def get_toolbar_actions(): list       # Get actions for toolbar
    def get_menu_actions(): dict          # Get actions for menus
    def get_device_panels(): list         # Get panels for device view
    def get_device_table_columns(): list  # Get columns for device table
    def get_device_context_menu_actions(): list  # Get actions for device context menu
    def get_device_tabs(): list           # Get tabs for device details view
    def get_dock_widgets(): list          # Get dock widgets for main window
    def get_settings_pages(): list        # Get pages for settings dialog
    
    # Event handler methods (to implement)
    def on_device_added(self, device)     # Called when a device is added
    def on_device_removed(self, device)   # Called when a device is removed
    def on_device_changed(self, device)   # Called when a device is changed
    def on_device_selected(self, devices) # Called when devices are selected
    def on_group_added(self, group)       # Called when a group is added
    def on_group_removed(self, group)     # Called when a group is removed
    def on_plugin_loaded(self, plugin_info)  # Called when a plugin is loaded
    def on_plugin_unloaded(self, plugin_info)  # Called when a plugin is unloaded
```

For more detailed information about specific components, refer to the API documentation in the respective module directories.

# Device Properties

## Core Properties

NetWORKS devices have the following core properties that are managed by the application:

- `id`: Unique identifier for the device
- `alias`: Human-readable name for the device
- `hostname`: Network hostname
- `ip_address`: IP address
- `mac_address`: MAC address
- `status`: Current status (up, down, unknown, etc.)
- `notes`: User notes
- `tags`: List of tags for categorizing devices

Core properties are always displayed at the top of the properties panel.

## Plugin Properties

Plugins should use a naming convention for their properties to ensure they appear in the "Plugin Properties" section:

```python
# Set a plugin property
device.set_property("plugin_id:property_name", "value")

# Examples
device.set_property("scanner:last_scan", "2023-05-15")
device.set_property("monitor.alarm_threshold", 95)
device.set_property("backup_tool_backup_path", "/backups/device1")
```

Plugin properties can use any of these prefixes:
- `plugin_id:property_name` (colon separator)
- `plugin_id.property_name` (dot separator)
- `plugin_id_property_name` (underscore separator)

Where `plugin_id` matches the plugin's ID exactly.

## Custom Properties

Any properties not matching core or plugin naming patterns are considered custom properties and appear in the "Custom Properties" section.

```python
# Set a custom property
device.set_property("location", "Server Room 3")
```

# Device API

// ... rest of the existing documentation 