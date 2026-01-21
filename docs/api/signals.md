# NetWORKS Signals Documentation

This document provides a comprehensive guide to the signals and events system in NetWORKS. Signals are a critical part of the application's architecture, enabling communication between different components and plugins.

## Table of Contents

- [Overview](#overview)
- [Core Signals](#core-signals)
- [UI Signals](#ui-signals)
- [Plugin Signals](#plugin-signals)
- [Working with Signals](#working-with-signals)
- [Multi-Device Selection Signals](#multi-device-selection-signals)
- [Best Practices](#best-practices)
- [Complete Signal Registry](#complete-signal-registry)
- [Plugin Registration Points](#plugin-registration-points)

## Overview

NetWORKS uses Qt's signal and slot mechanism to enable event-driven programming. Signals are emitted when certain events occur, and slots (callback functions) are executed in response to these signals.

Signals enable:
- Loose coupling between components
- Event-driven architecture
- Plugin extensibility
- Reactive UI updates

## Core Signals

### Device Manager Signals

```python
# Device-related signals
device_added: Signal(object)         # Emitted when a device is added
device_removed: Signal(object)       # Emitted when a device is removed
device_changed: Signal(object)       # Emitted when a device is changed
selection_changed: Signal(list)      # Emitted when device selection changes

# Group-related signals
group_added: Signal(object)          # Emitted when a group is added
group_removed: Signal(object)        # Emitted when a group is removed
group_changed: Signal(object)        # Emitted when a group is changed
```

Example usage:
```python
def initialize(self):
    # Connect to device signals
    self.device_manager.device_added.connect(self.on_device_added)
    self.device_manager.device_removed.connect(self.on_device_removed)
    self.device_manager.device_changed.connect(self.on_device_changed)
    self.device_manager.selection_changed.connect(self.on_selection_changed)
    
    # Connect to group signals
    self.device_manager.group_added.connect(self.on_group_added)
    self.device_manager.group_removed.connect(self.on_group_removed)
    self.device_manager.group_changed.connect(self.on_group_changed)
    
    return True

def on_device_added(self, device):
    logger.debug(f"Device added: {device.get_property('alias')}")
    
def on_device_removed(self, device):
    logger.debug(f"Device removed: {device.get_property('alias')}")
    
def on_device_changed(self, device):
    logger.debug(f"Device changed: {device.get_property('alias')}")
    
def on_selection_changed(self, devices):
    logger.debug(f"Selection changed: {len(devices)} devices selected")
```

### Device Group Signals

```python
changed: Signal()                    # Emitted when group changes
device_added: Signal(object)         # Emitted when device is added to group
device_removed: Signal(object)       # Emitted when device is removed from group
```

### Plugin Manager Signals

```python
plugin_loaded: Signal(object)        # Emitted when a plugin is loaded
plugin_unloaded: Signal(object)      # Emitted when a plugin is unloaded
plugin_enabled: Signal(object)       # Emitted when a plugin is enabled
plugin_disabled: Signal(object)      # Emitted when a plugin is disabled
```

Example usage:
```python
def initialize(self):
    # Connect to plugin manager signals
    self.plugin_manager.plugin_loaded.connect(self.on_plugin_loaded)
    self.plugin_manager.plugin_unloaded.connect(self.on_plugin_unloaded)
    
    return True

def on_plugin_loaded(self, plugin_info):
    logger.debug(f"Plugin loaded: {plugin_info.name}")
    
    # Check if it's a specific plugin we want to interact with
    if plugin_info.id == "network_scanner":
        # Get the plugin instance
        scanner_plugin = plugin_info.instance
        if scanner_plugin:
            # Connect to its signals
            scanner_plugin.scan_completed.connect(self.on_scan_completed)
            scanner_plugin.scan_device_found.connect(self.on_device_found)
            # Connect to profile management signals
            scanner_plugin.profile_created.connect(self.on_profile_created)
            scanner_plugin.profile_updated.connect(self.on_profile_updated)
            scanner_plugin.profile_deleted.connect(self.on_profile_deleted)
    
def on_plugin_unloaded(self, plugin_info):
    logger.debug(f"Plugin unloaded: {plugin_info.name}")

# Signal handler examples
def on_scan_completed(self, results):
    logger.info(f"Scan completed with {results.get('devices_found', 0)} devices")

def on_device_found(self, device):
    logger.info(f"Found device: {device.get_property('ip_address')}")

def on_profile_created(self, profile_name):
    logger.info(f"Scan profile created: {profile_name}")

def on_profile_updated(self, profile_name):
    logger.info(f"Scan profile updated: {profile_name}")

def on_profile_deleted(self, profile_name):
    logger.info(f"Scan profile deleted: {profile_name}")
```

## UI Signals

### Main Window Signals

```python
initialized: Signal()                # Emitted when main window is initialized
closing: Signal()                    # Emitted when main window is closing
```

### Device Table View Signals

```python
double_clicked: Signal(object)              # Emitted when a device is double-clicked
context_menu_requested: Signal(list, object) # Emitted when context menu is requested
                                            # Arguments: devices, menu
```

Example usage:
```python
def initialize(self):
    # Connect to device table signals
    device_table = self.app.main_window.device_table
    device_table.double_clicked.connect(self.on_device_double_clicked)
    device_table.context_menu_requested.connect(self.on_context_menu_requested)
    
    return True

def on_device_double_clicked(self, device):
    logger.debug(f"Device double-clicked: {device.get_property('alias')}")
    
def on_context_menu_requested(self, devices, menu):
    logger.debug(f"Context menu requested for {len(devices)} devices")
    
    # Add custom menu items
    if devices:
        menu.addAction("My Custom Action", lambda: self.on_custom_action(devices))
```

### Device Tree View Signals

```python
device_double_clicked: Signal(object)     # Emitted when a device is double-clicked
group_selection_changed: Signal(list)     # Emitted when group selection changes
group_filter_requested: Signal(object)    # Emitted when a group filter is requested
```

## Plugin Signals

Plugin interfaces provide several signals:

```python
plugin_initialized: Signal()         # Emitted when plugin is initialized
plugin_starting: Signal()            # Emitted when plugin is starting
plugin_running: Signal()             # Emitted when plugin is running
plugin_stopping: Signal()            # Emitted when plugin is stopping
plugin_cleaned_up: Signal()          # Emitted when plugin is cleaned up
plugin_error: Signal(str)            # Emitted when plugin encounters an error
```

Plugins can also define and emit their own custom signals:

```python
from PySide6.QtCore import QObject, Signal

class MyPlugin(PluginInterface):
    # Define custom signals
    device_scanned = Signal(object, dict)   # Emitted when device scan completes
    scan_started = Signal(object)           # Emitted when scan starts
    
    def scan_device(self, device):
        """Scan a device for information"""
        # Emit signal that scan has started
        self.scan_started.emit(device)
        
        # Perform the scan
        results = self._perform_scan(device)
        
        # Emit signal with results
        self.device_scanned.emit(device, results)
        
        return results
```

Other plugins can connect to these signals:

```python
def initialize(self):
    # Find the plugin we want to connect to
    scanner_plugin_info = self.plugin_manager.get_plugin("scanner_plugin")
    if scanner_plugin_info and scanner_plugin_info.loaded:
        scanner_plugin = scanner_plugin_info.instance
        
        # Connect to its signals
        scanner_plugin.device_scanned.connect(self.on_device_scanned)
        scanner_plugin.scan_started.connect(self.on_scan_started)
    
    return True

def on_device_scanned(self, device, results):
    logger.info(f"Device {device.get_property('alias')} scanned with {len(results)} results")
    
def on_scan_started(self, device):
    logger.info(f"Scan started for device {device.get_property('alias')}")
```

## Working with Signals

### Connecting to Signals

Connect a signal to a slot (callback function):

```python
# Connect to a signal
signal.connect(slot)

# Example
self.device_manager.device_added.connect(self.on_device_added)
```

### Disconnecting from Signals

Always disconnect from signals in the `cleanup` method to prevent memory leaks:

```python
def cleanup(self):
    # Disconnect from signals
    self.device_manager.device_added.disconnect(self.on_device_added)
    self.device_manager.device_removed.disconnect(self.on_device_removed)
    
    return super().cleanup()
```

### Emitting Signals

Emit a signal to notify listeners:

```python
# Emit a signal
self.my_signal.emit(arg1, arg2)

# Example
self.scan_completed.emit(device, results)
```

### Signal Parameters

Signals can have multiple parameters:

```python
# Define a signal with multiple parameters
my_signal = Signal(object, str, int)

# Emit the signal with all parameters
self.my_signal.emit(device, "status", 42)

# Connect to the signal with a matching slot
self.my_signal.connect(self.on_my_signal)

def on_my_signal(self, device, status, code):
    logger.debug(f"Received signal: {device}, {status}, {code}")
```

## Multi-Device Selection Signals

Starting from version 0.5.4, NetWORKS supports multi-device selection. This affects how you handle signals, particularly the `selection_changed` signal:

```python
def on_selection_changed(self, devices):
    """Handle selection change
    
    Args:
        devices: List of selected devices
    """
    # Clear current display
    self.panel.clear()
    
    if not devices:
        # No devices selected
        self.show_empty_state()
        return
        
    if len(devices) == 1:
        # Single device selected
        device = devices[0]
        self.show_single_device_view(device)
    else:
        # Multiple devices selected
        self.show_multi_device_view(devices)
```

### Context Menu with Multiple Selection

The `context_menu_requested` signal now provides a list of selected devices:

```python
def on_context_menu_requested(self, devices, menu):
    """Handle context menu request
    
    Args:
        devices: List of selected devices
        menu: QMenu instance
    """
    if not devices:
        return
        
    # Create action based on selection count
    if len(devices) == 1:
        # Single device action
        device = devices[0]
        action = menu.addAction(f"Scan {device.get_property('alias')}")
        action.triggered.connect(lambda: self.scan_device(device))
    else:
        # Multi-device action
        action = menu.addAction(f"Scan {len(devices)} devices")
        action.triggered.connect(lambda: self.scan_devices(devices))
```

## Best Practices

### 1. Always Disconnect Signals

Always disconnect signals in the `cleanup` method to prevent memory leaks and unexpected behavior:

```python
def cleanup(self):
    # Disconnect from all signals
    self.device_manager.device_added.disconnect(self.on_device_added)
    
    return super().cleanup()
```

### 2. Type Hints for Signals

Use type hints to document the expected parameters for signals:

```python
from PySide6.QtCore import Signal
from typing import Dict, List

class MyPlugin(PluginInterface):
    # Signal with type hints in comments
    device_scanned = Signal(object, dict)  # (Device, Dict[str, str])
```

### 3. Signal Documentation

Document your signals in your plugin's API.md file:

```markdown
## Signals

### device_scanned

Emitted when a device scan is completed.

**Arguments:**
- `device` (Device): The scanned device
- `results` (dict): Dictionary of scan results

**Example:**
```python
plugin.device_scanned.connect(on_device_scanned)

def on_device_scanned(device, results):
    print(f"Scan completed for {device.get_property('alias')}")
```
```

### 4. Handle Multiple Devices

Always design your signal handlers to work with both single devices and multiple devices:

```python
def on_context_menu_action(self, devices):
    """Handle context menu action for one or more devices"""
    if isinstance(devices, list):
        # Multiple devices
        for device in devices:
            self.process_device(device)
    else:
        # Single device
        self.process_device(devices)
```

### 5. Be Mindful of Performance

Consider performance implications when emitting signals with large data:

```python
def process_large_dataset(self, devices):
    # Process in batches to avoid excessive UI updates
    batch_size = 10
    for i in range(0, len(devices), batch_size):
        batch = devices[i:i+batch_size]
        # Process batch
        results = self._process_batch(batch)
        
        # Emit batch completion signal with summarized data
        self.batch_completed.emit(len(batch), len(results))
```

### 6. Connect to Signals Conditionally

Connect to signals only when needed and check if objects are valid:

```python
def initialize(self):
    # Only connect if the component exists
    if hasattr(self.app.main_window, 'device_table'):
        self.app.main_window.device_table.double_clicked.connect(
            self.on_device_double_clicked
        )
    
    return True
```

## Complete Signal Registry

Below is a comprehensive registry of all signals available in the NetWORKS application. Plugins can connect to these signals or emit their own signals. This registry serves as the authoritative reference for all signal-based interactions.

### Core Application Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| initialized | Application | None | Emitted when the application has been fully initialized |
| shutting_down | Application | None | Emitted when the application is about to shut down |
| config_changed | Application | None | Emitted when application configuration changes |

### Device Manager Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| device_added | DeviceManager | Device | Emitted when a device is added to the system |
| device_removed | DeviceManager | Device | Emitted when a device is removed from the system |
| device_changed | DeviceManager | Device | Emitted when a device's properties are changed |
| selection_changed | DeviceManager | List[Device] | Emitted when the selected devices change |
| group_added | DeviceManager | DeviceGroup | Emitted when a device group is added |
| group_removed | DeviceManager | DeviceGroup | Emitted when a device group is removed |
| group_changed | DeviceManager | DeviceGroup | Emitted when a device group is modified |

### Device Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| changed | Device | None | Emitted when the device's properties change |
| status_changed | Device | str | Emitted when the device's status changes |
| connection_changed | Device | bool | Emitted when the device's connection state changes |

### Device Group Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| changed | DeviceGroup | None | Emitted when the group changes |
| device_added | DeviceGroup | Device | Emitted when a device is added to the group |
| device_removed | DeviceGroup | Device | Emitted when a device is removed from the group |

### Plugin Manager Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| plugin_loaded | PluginManager | PluginInfo | Emitted when a plugin is loaded |
| plugin_unloaded | PluginManager | PluginInfo | Emitted when a plugin is unloaded |
| plugin_enabled | PluginManager | PluginInfo | Emitted when a plugin is enabled |
| plugin_disabled | PluginManager | PluginInfo | Emitted when a plugin is disabled |
| plugin_state_changed | PluginManager | PluginInfo | Emitted when a plugin's state changes |

### Plugin Interface Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| plugin_initialized | PluginInterface | None | Emitted when a plugin is initialized |
| plugin_starting | PluginInterface | None | Emitted when a plugin is starting |
| plugin_running | PluginInterface | None | Emitted when a plugin is running |
| plugin_stopping | PluginInterface | None | Emitted when a plugin is stopping |
| plugin_cleaned_up | PluginInterface | None | Emitted when a plugin is cleaned up |
| plugin_error | PluginInterface | str | Emitted when a plugin encounters an error |

### UI Signals

| Signal Name | Source | Parameters | Description |
|-------------|--------|------------|-------------|
| initialized | MainWindow | None | Emitted when the main window is initialized |
| closing | MainWindow | None | Emitted when the main window is closing |
| double_clicked | DeviceTableView | Device | Emitted when a device is double-clicked in the table |
| context_menu_requested | DeviceTableView | List[Device], QMenu | Emitted when a context menu is requested for devices |
| device_double_clicked | DeviceTreeView | Device | Emitted when a device is double-clicked in the tree |
| settings_changed | SettingsDialog | None | Emitted when settings are changed |

## Plugin Registration Points

Plugins can register with the application in various ways to extend functionality. Here are all the registration points available:

### UI Registration Points

| Registration Method | Source | Description |
|---------------------|--------|-------------|
| get_toolbar_actions() | PluginInterface | Register actions for the main toolbar |
| get_menu_actions() | PluginInterface | Register actions for the application menu |
| get_device_panels() | PluginInterface | Register panels for the device property view |
| get_device_table_columns() | PluginInterface | Register columns for the device table |
| get_device_context_menu_actions() | PluginInterface | Register actions for the device context menu |
| get_device_tabs() | PluginInterface | Register tabs for the device details view |
| get_dock_widgets() | PluginInterface | Register dock widgets for the main window |
| get_settings_pages() | PluginInterface | Register pages for the settings dialog |

### Data Registration Points

| Registration Method | Source | Description |
|---------------------|--------|-------------|
| register_device_type() | DeviceManager | Register a new device type |
| register_property_editor() | DeviceManager | Register a custom property editor for device properties |
| register_device_operation() | DeviceManager | Register a device operation |
| register_discovery_method() | DeviceManager | Register a device discovery method |

### Event Registration Points

Plugins can register to handle events by connecting to signals. Here are the key methods:

```python
# Connect to signals
def initialize(self, app, plugin_info):
    # Store app reference
    self.app = app
    self.device_manager = app.device_manager
    
    # Connect to device manager signals
    self.device_manager.device_added.connect(self.on_device_added)
    self.device_manager.device_removed.connect(self.on_device_removed)
    self.device_manager.device_changed.connect(self.on_device_changed)
    self.device_manager.selection_changed.connect(self.on_device_selected)
    
    # Connect to plugin manager signals
    app.plugin_manager.plugin_loaded.connect(self.on_plugin_loaded)
    app.plugin_manager.plugin_unloaded.connect(self.on_plugin_unloaded)
    
    # Register for UI events
    if hasattr(app, 'main_window') and app.main_window:
        app.main_window.initialized.connect(self.on_main_window_initialized)
    
    return True
```

### Settings Registration

Plugins can register configurable settings:

```python
def get_settings(self):
    """Get plugin settings"""
    return {
        "setting_id": {
            "name": "Human-readable name",
            "description": "Setting description",
            "type": "string|int|float|bool|choice",
            "default": default_value,
            "value": current_value,
            "choices": ["choice1", "choice2"]  # Only for type "choice"
        },
        # ... more settings ...
    }
``` 