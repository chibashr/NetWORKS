# NetWORKS Core API Documentation

This document provides detailed information about the core components of NetWORKS that plugins can interact with.

## Module layout (file-length refactor)

Models and helpers live in separate modules; public API is preserved via re-exports:

- **device_models.py**: `Device`, `DeviceGroup` (import from `device_manager` or `device_models`).
- **plugin_types.py**: `PluginState`, `PluginInfo` (import from `plugin_manager` or `plugin_types`).
- **plugin/**: `plugin_registry`, `plugin_discovery`; used by `PluginManager`. Import plugin API from `plugin_manager` only.
- **importer_utils.py**: optional deps (pandas, openpyxl, xlrd, docx, chardet) and `_try_import_pandas`, `get_pandas`, `get_openpyxl`, etc. Used by `importer`.

## Table of Contents

- [Device Manager](#device-manager)
- [Device Importer](#device-importer)
- [Plugin Manager](#plugin-manager)
- [Plugin Interface](#plugin-interface)
- [Logging Manager](#logging-manager)

## Device Manager

The `DeviceManager` class is responsible for managing devices and device groups. This is the primary API for plugins to interact with devices.

### Key Features

- Device creation, modification, and deletion
- Device grouping and organization
- Device selection management
- Persistence of device data

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
def get_device_groups_for_device(self, device_id) -> list  # Returns all groups that contain a device

# Selection management
def select_device(self, device, exclusive=False) -> bool
def deselect_device(self, device) -> bool
def clear_selection(self) -> bool
def get_selected_devices(self) -> list

# Persistence
def save_devices(self) -> bool
def load_devices(self) -> bool

# Refresh
def refresh_devices(self) -> bool
```

### Device Class

The `Device` class represents a managed device with properties.

```python
# Signals
changed: Signal()  # Emitted when properties change

# Methods
def get_properties(self) -> dict
def get_property(self, key, default=None)
def set_property(self, key, value)
def update_properties(self, properties)
def to_dict(self) -> dict
@classmethod def from_dict(cls, data) -> Device
```

### DeviceGroup Class

The `DeviceGroup` class represents a group of devices.

```python
# Signals
changed: Signal()
device_added: Signal(object)
device_removed: Signal(object)

# Methods
def add_device(self, device)
def remove_device(self, device)
def add_subgroup(self, group)
def remove_subgroup(self, group)
def get_all_devices(self) -> list
def to_dict(self) -> dict
```

## Device Importer

The `DeviceImporter` class provides functionality for importing devices from various file formats and data sources. It is separate from the device tree to allow for better modularity.

### Key Features

- Import devices from CSV, Excel, and Word documents
- Import devices from pasted text
- Auto-detect field mappings
- Duplicate detection and handling
- Format-specific data extraction

### Core Methods

```python
def __init__(self, device_manager)
    # Initialize the device importer with a device manager instance
    
def import_from_file(self, file_path, options=None) -> tuple
    # Import devices from a file
    # file_path: Path to the file
    # options: Dictionary of import options:
    #   - delimiter: CSV delimiter character
    #   - has_header: Whether the file has a header row
    #   - encoding: File encoding (or 'auto' to detect)
    #   - target_group: Group to add devices to
    #   - field_mapping: Dictionary mapping columns to device properties
    #   - skip_duplicates: Whether to skip duplicate devices
    #   - mark_imported: Whether to tag devices as 'imported'
    # Returns: (success, stats) where success is a boolean and stats is a dict with:
    #   - imported_count: Number of devices imported
    #   - skipped_count: Number of devices skipped
    #   - error_count: Number of devices with errors
    
def import_from_text(self, text, options=None) -> tuple
    # Import devices from pasted text
    # text: Text containing device data (CSV, line-by-line IP list, etc.)
    # options: Dictionary of import options (see import_from_file)
    # Returns: (success, stats) same format as import_from_file
```

### Supported File Formats

The importer supports the following file formats:
- CSV files (*.csv)
- Tab-separated text files (*.txt)
- Excel files (*.xlsx, *.xls) - requires pandas or xlrd
- Word documents (*.docx) - requires python-docx

### Usage Examples

```python
# Import from a CSV file
importer = DeviceImporter(device_manager)
options = {
    'delimiter': ',',
    'has_header': True,
    'skip_duplicates': True,
    'mark_imported': True,
    'target_group': device_manager.get_group('Imported Devices')
}
success, stats = importer.import_from_file('devices.csv', options)
if success:
    print(f"Imported {stats['imported_count']} devices")
else:
    print(f"Import had issues. Imported: {stats['imported_count']}, "
          f"Skipped: {stats['skipped_count']}, Errors: {stats['error_count']}")

# Import from pasted text (IP addresses, one per line)
text = """
192.168.1.1
192.168.1.2
192.168.1.3
"""
success, stats = importer.import_from_text(text, {'delimiter': 'Auto-detect'})
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
def get_settings_pages(self) -> list
```

### Device Dialog Methods

```python
def show_device_properties_dialog(self, device=None) -> Device
    # Show the device properties dialog for an existing device or to create a new one
    # Returns the modified or new device if accepted, None if cancelled
    
def add_device_dialog(self) -> Device
    # Show a dialog to add a new device
    # The device is automatically added to the device manager if accepted
    # Returns the new device if added, None if cancelled
```

Example:
```python
def my_plugin_method(self):
    # Edit an existing device
    device = self.device_manager.get_device("device-id")
    if device:
        updated_device = self.show_device_properties_dialog(device)
        if updated_device:
            # Device was updated
            pass
            
    # Add a new device
    new_device = self.add_device_dialog()
    if new_device:
        # Device was added to the device manager
        pass
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

## Logging Manager

The `LoggingManager` class provides centralized logging capabilities for the application and plugins.

### Key Features

- Comprehensive session-based logging
- Detailed system information logging
- Advanced error tracking and diagnostics
- Configurable log levels and retention
- Recent logs file for quick issue diagnosis

### Core Methods

```python
def __init__(self, app_version=None)
    # Initialize the logging manager with the application version
    
def get_logger(self)
    # Get the configured logger instance
    # Returns the loguru logger with all sinks configured
    
def set_level(self, level)
    # Set the global logging level
    # level: str - DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Usage in Plugins

Plugins should use the application's logger instance for consistent logging:

```python
# In your plugin:
def initialize(self):
    self.logger = self.app.logger
    self.logger.info(f"Initializing {self.name} plugin")
    
def my_method(self):
    try:
        # Your code here
        self.logger.debug("Operation completed successfully")
    except Exception as e:
        self.logger.exception(f"Error in {self.name} plugin: {e}")
```

### Log Levels

The following log levels are available (in order of severity):

- `TRACE`: Detailed information, typically useful only when diagnosing problems
- `DEBUG`: Information useful for debugging
- `INFO`: Confirmation that things are working as expected
- `SUCCESS`: Successful operations
- `WARNING`: Indication that something unexpected happened, or may happen in the near future
- `ERROR`: Due to a more serious problem, the software has not been able to perform some function
- `CRITICAL`: A serious error, indicating that the program itself may be unable to continue running

### Log Format

Session-specific logs include:
- Timestamp
- Log level
- Module, function, and line number
- Session ID
- Application version
- System information
- Log message

The format of log entries is:
```
YYYY-MM-DD HH:mm:ss.SSS | LEVEL    | module:function:line | session:1698765432 | v0.3.3 | Windows 10 | Message
``` 