# Sample Plugin

This plugin serves as a comprehensive example of how to create plugins for NetWORKS, demonstrating best practices and core integration patterns.

## Features

- Demonstrates proper plugin lifecycle management
- Shows how to integrate with device management
- Implements context menu integration with the main application
- Provides examples of creating and managing dock widgets and panels
- Includes examples of toolbar and main menu integration
- Shows signal handling and event monitoring
- Demonstrates device property management
- Includes comprehensive testing capabilities

## Context Menu Integration

The sample plugin demonstrates the proper way to integrate with the application's context menu system. Instead of creating separate context menus, plugins should register actions with the existing context menus:

```python
# Register actions with the device table's context menu
device_table.register_context_menu_action(
    "Sample Action", 
    self._on_sample_action_context, 
    priority=100  # Lower priority = higher in the menu
)

# Register actions with the group tree's context menu
group_tree.register_context_menu_action(
    "Sample Action on Group",
    self._on_sample_action_group,
    priority=100
)
```

## Device Creation

The plugin demonstrates proper device creation using the device manager API:

```python
# Create a device using the device manager API
new_device = self.device_manager.create_device(
    device_type="sample",
    name="Sample Device",
    description="Device created by Sample Plugin",
    sample="Sample Value"
)

# Add it to the device manager
self.device_manager.add_device(new_device)
```

## Signal Handling

The plugin shows how to safely connect to and disconnect from signals:

```python
# Connect to a signal with tracking
self._connect_to_signal(
    self.device_manager.device_added, 
    self.on_device_added, 
    "device_added"
)

# Safe disconnection during cleanup
safe_disconnect(
    self.device_manager, 
    "device_added", 
    self.on_device_added, 
    "DeviceManager"
)
```

## Action Handlers

All action handlers are wrapped with a safety decorator to prevent crashes:

```python
@safe_action_wrapper
def _on_sample_action_context(self, device_or_devices):
    """Handle Sample Action from context menu for devices"""
    # Implementation with safe error handling
```

## Installation

Available from **Plugin Manager → Browse** (Tools → Plugin Manager → Browse). Also included with NetWORKS by default. To study its code, look at:

- `sample_plugin.py`: Main plugin implementation
- `manifest.json`: Plugin metadata and version information

## Usage

This plugin is primarily meant as a reference, but it also provides useful testing capabilities:

1. **Test Core Features**: Test core application functionality
2. **Signal Monitoring**: Monitor application signals for debugging
3. **Device Testing**: Test device properties and operations
4. **Sample Properties**: Demonstrate custom device property management 

## Settings and Configuration

The Sample plugin exposes settings in the Plugin Manager dialog to demonstrate:
- Log level changes
- Automatic sample property creation
- Testing mode configuration
- Signal monitoring defaults

Use these settings to explore how plugin configuration is presented and applied.

## Documentation and References

- `API.md` documents the plugin's public API, signals, and UI components.
- The plugin source is intended as a reference for building new plugins and testing extension points.