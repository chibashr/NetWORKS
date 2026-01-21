# NetWORKS Development Guide

This guide provides essential information for developers extending or modifying NetWORKS.

## Core Principles

NetWORKS is designed with the following principles in mind:

1. **Modularity**: Code is organized into small, focused modules
2. **Extensibility**: Core functionality can be extended through plugins
3. **Accessibility**: Code is well-documented and follows consistent patterns

## Project Structure
```
networks/
├── API.md                  # Main API documentation
├── config/                 # Configuration files
├── logs/                   # Log files
├── plugins/                # External plugins
├── src/                    # Source code
│   ├── core/               # Core functionality
│   │   ├── API.md                # Core API documentation
│   │   ├── device_manager.py      # Device management
│   │   ├── plugin_interface.py    # Plugin interface
│   │   └── plugin_manager.py      # Plugin management
│   ├── ui/                 # UI components
│   │   ├── API.md                # UI API documentation
│   │   ├── device_table.py        # Device table view
│   │   ├── device_tree.py         # Device tree view
│   │   ├── main_window.py         # Main application window
│   │   ├── plugin_manager_dialog.py  # Plugin manager dialog
│   │   └── splash_screen.py       # Splash screen
│   ├── app.py              # Application class
│   └── config.py           # Configuration management
├── networks.py             # Application entry point
├── requirements.txt        # Python dependencies
└── setup.bat               # Setup script for Windows
```

## Adding New Features

When adding new features to NetWORKS, consider whether the feature should be part of the core application or implemented as a plugin:

- **Core Features**: Functionality that is essential to the application and used by multiple plugins
- **Plugin Features**: Specialized functionality that can be added/removed independently

### Adding Core Features

1. Identify the appropriate module for your feature
2. Ensure proper integration with existing systems
3. Update documentation to reflect changes
4. Update API.md documentation to document new public APIs

### Creating a Plugin

See the [Plugin Development Guide](plugins/README.md) for basic plugin creation instructions.

**Plugin API Documentation Requirements:**

All plugins should include an `API.md` file in their root directory that documents (NetWORKS will warn if this file is missing):

1. Public APIs exposed by the plugin
2. Device properties added or modified by the plugin
3. UI components added by the plugin
4. Integration points with other plugins
5. Examples of how to interact with the plugin

Example structure for a plugin API.md:

```markdown
# My Plugin API Documentation

## Overview
Brief description of what the plugin does

## Public API
Document classes, methods, and properties that other plugins can use

## Device Properties
Document device properties added/modified by this plugin

## UI Components
Document UI elements added by this plugin

## Integration Examples
Show code examples of how other plugins can integrate
```

Advanced plugin development:

1. **UI Integration**: Plugins can add:
   - Toolbar actions and menu items
   - Device table columns
   - Device detail panels
   - Dock widgets
   
2. **Device Extensions**: Plugins can:
   - Add new device types
   - Define custom device properties
   - Implement device discovery mechanisms
   - Add device operations

3. **Event Handling**: Plugins can respond to:
   - Device events (added, removed, changed)
   - Selection events
   - Application events

## Device System

The device system is central to NetWORKS. Key concepts:

- **Device**: Represents a managed device with properties
- **DeviceGroup**: A collection of devices
- **DeviceManager**: Manages devices and groups

### Device Properties

Devices have both built-in and custom properties:

- Built-in: id, name, type, status, description, tags
- Custom: Added by plugins or user

To add a custom property to a device:

```python
device.set_property("my_property", "value")
```

To retrieve a property:

```python
value = device.get_property("my_property", default_value)
```

## Plugin System

The plugin system enables extending NetWORKS. Key classes:

- **PluginInterface**: Base class for all plugins
- **PluginManager**: Handles plugin discovery and lifecycle
- **PluginInfo**: Contains metadata about a plugin

### Plugin Lifecycle

1. **Discovery**: Plugins are discovered in plugin directories
2. **Loading**: Plugin modules are imported and instances created
3. **Initialization**: Plugin's `initialize()` method is called
4. **Operation**: Plugin responds to events and user actions
5. **Cleanup**: Plugin's `cleanup()` method is called during unloading

### Plugin Directory Structure

Each plugin must follow this directory structure:

```
plugin_name/
├── API.md              # API documentation (expected)
├── manifest.json       # Plugin metadata (required, preferred)
├── plugin_main.py      # Main plugin file (specified in entry_point)
└── ...                 # Additional plugin files
```

### Plugin Metadata (manifest.json / plugin.json / plugin.yaml)

The plugin manifest must contain the following fields:

```json
{
  "id": "unique_plugin_id",
  "name": "Human Readable Plugin Name",
  "version": "1.0.0",
  "description": "Description of what the plugin does",
  "author": "chibashr",
  "entry_point": "plugin_main.py"
}
```

### Plugin Events

Plugins can respond to various events by implementing the corresponding methods:

- `on_device_added(device)`
- `on_device_removed(device)`
- `on_device_changed(device)`
- `on_device_selected(devices)`
- `on_group_added(group)`
- `on_group_removed(group)`
- `on_plugin_loaded(plugin_info)`
- `on_plugin_unloaded(plugin_info)`

## API Documentation

NetWORKS provides comprehensive API documentation to help plugin developers:

- **Main API.md**: Overview of all APIs
- **Module-specific API.md**: Detailed documentation for each module
- **Plugin API.md**: Required for each plugin to document its public API

When developing:
1. **Follow existing API patterns**: Ensure your APIs are consistent with existing ones
2. **Document all public APIs**: Any method, property, or signal that others may use
3. **Provide examples**: Show how to use your APIs
4. **Update documentation**: When changing existing APIs

## Coding Guidelines

1. Follow PEP 8 for Python code
2. Use docstrings for classes, methods, and modules
3. Keep files focused and under 800 lines
4. Use type hints where appropriate
5. Add logging at appropriate levels
6. Write tests for new functionality

## User Interface Guidelines

1. Use consistent naming and terminology
2. Provide meaningful tooltips
3. Support keyboard navigation
4. Use appropriate icons for actions
5. Provide user feedback for operations
6. Follow platform UI guidelines

## Performance Considerations

1. Use lazy loading for resources
2. Optimize data structures for common operations
3. Use asynchronous operations for I/O or network
4. Profile code for bottlenecks
5. Consider memory usage for large device sets 

