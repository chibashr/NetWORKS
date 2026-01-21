# NetWORKS Plugin Development Guide

This guide provides comprehensive information for developing plugins for the NetWORKS platform. Plugins are the primary way to extend and customize NetWORKS functionality.

## Table of Contents

- [Plugin System Overview](#plugin-system-overview)
- [Plugin Structure](#plugin-structure)
- [Plugin Development Lifecycle](#plugin-development-lifecycle)
- [Creating Your First Plugin](#creating-your-first-plugin)
- [Plugin API Documentation](#plugin-api-documentation)
- [Extension Points](#extension-points)
- [Best Practices](#best-practices)
- [Advanced Topics](#advanced-topics)
- [Troubleshooting](#troubleshooting)
- [Example Plugins](#example-plugins)

## Quick Start

For a step-by-step tutorial on creating your first plugin, see the [Getting Started Guide](GETTING_STARTED.md).

## Plugin System Overview

The NetWORKS plugin system is designed to be:

- **Flexible**: Plugins can extend almost any part of the application
- **Modular**: Plugins can be enabled, disabled, or uninstalled independently
- **Discoverable**: Plugins are automatically discovered on application startup
- **Safe**: Plugins run in a controlled environment to prevent system damage

Plugins can extend NetWORKS by:

1. Adding UI components (toolbar actions, menu items, panels, dock widgets)
2. Extending device capabilities (properties, operations)
3. Adding device discovery methods
4. Integrating with external systems and services
5. Implementing custom data visualization
6. Adding support for specific device types or protocols

## Plugin Structure

A NetWORKS plugin is a directory containing the following components:

```
my_plugin/
├── API.md              # API documentation (required)
├── plugin.yaml         # Plugin metadata (required)
├── my_plugin.py        # Main plugin file (specified in entry_point)
├── resources/          # Resources directory (optional)
│   ├── icons/          # Plugin icons
│   └── ui/             # UI definition files
├── lib/                # Library directory for plugin-specific modules (optional)
│   └── ...             # Additional Python modules
└── docs/               # Additional documentation (optional)
    └── ...             # Documentation files
```

### Required Files

#### plugin.yaml

This file contains plugin metadata:

```yaml
id: my_plugin               # Unique identifier for the plugin
name: My Plugin             # Human-readable name
version: 1.0.0              # Plugin version (semantic versioning recommended)
description: >              # Description of what the plugin does
  A comprehensive description of the plugin's functionality.
  Can span multiple lines.
author: Your Name           # Author name or organization
entry_point: my_plugin.py   # Main plugin file
min_app_version: 0.1.0      # Minimum compatible application version (optional)
dependencies:               # Other plugins this plugin depends on (optional)
  - other_plugin: ">=1.0.0"
```

#### API.md

This file documents the public API your plugin exposes to other plugins. It should include:

1. Overview of plugin functionality
2. Public classes, methods, and properties
3. Device properties added or modified
4. Signals emitted or handled
5. UI components added
6. Integration examples
7. Available settings and configuration options

The API.md file is **required** for all plugins. Without this file, the plugin will not be properly documented, and users will not know how to use your plugin's features.

Here's a recommended structure for your API.md file:

```markdown
# Plugin Name API Documentation

## Overview

Brief description of what the plugin does and its key features.

## Public API

### Methods

List of public methods that other plugins can call, with descriptions, parameters, and return values.

```python
def method_name(param1, param2):
    """Method description
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
    """
```

### Device Properties

| Property | Type | Description |
|----------|------|-------------|
| property_name | string | Description of the property |

### Signals

| Signal | Parameters | Description |
|--------|------------|-------------|
| signal_name | (param1_type, param2_type) | Description of when the signal is emitted |

### UI Components

Description of UI components added by the plugin (toolbars, menus, panels, etc.)

## Integration Examples

Examples of how other plugins can integrate with your plugin.

## Settings

| Setting ID | Type | Description | Default |
|------------|------|-------------|---------|
| setting_id | string | Description | Default value |

## Changelog

Version history and changes.
```

#### Main Plugin File

This is the entry point specified in `plugin.yaml`. It must contain a class that inherits from `PluginInterface`:

```python
from src.core.plugin_interface import PluginInterface

class MyPlugin(PluginInterface):
    def initialize(self):
        # Plugin initialization code
        super().initialize()
        return True
        
    def cleanup(self):
        # Plugin cleanup code
        return super().cleanup()
```

### Optional Components

- **resources/**: Contains static resources like icons, images, and UI files
- **lib/**: Contains additional Python modules specific to the plugin
- **docs/**: Contains additional documentation

## Plugin Development Lifecycle

The lifecycle of a plugin includes the following stages:

1. **Discovery**: The application finds the plugin in the plugins directory
2. **Registration**: The plugin metadata is read and registered
3. **Loading**: The plugin code is imported
4. **Initialization**: The plugin's `initialize()` method is called
5. **Operation**: The plugin runs and responds to events
6. **Cleanup**: When unloading, the plugin's `cleanup()` method is called

### Plugin Initialization

During initialization, a plugin should:

1. Set up internal data structures
2. Connect to signals
3. Register UI components
4. Register device types or properties

Example:

```python
def initialize(self):
    # Set up internal data
    self.devices = {}
    
    # Connect to signals
    self.device_manager.device_added.connect(self.on_device_added)
    self.device_manager.device_removed.connect(self.on_device_removed)
    
    # Register UI components in main_window
    if hasattr(self, 'main_window'):
        self.setup_ui_components()
    
    # Initialize complete
    super().initialize()
    return True
```

### Plugin Cleanup

During cleanup, a plugin should:

1. Release resources
2. Disconnect from signals
3. Remove UI components
4. Save state if necessary

Example:

```python
def cleanup(self):
    # Disconnect signals
    self.device_manager.device_added.disconnect(self.on_device_added)
    self.device_manager.device_removed.disconnect(self.on_device_removed)
    
    # Clean up any resources
    
    # Cleanup complete
    return super().cleanup()
```

## Creating Your First Plugin

### Step 1: Create the Plugin Directory

Create a new directory in the `plugins` folder with your plugin name:

```
plugins/my_first_plugin/
```

### Step 2: Create the Plugin Metadata

Create a `plugin.yaml` file:

```yaml
id: my_first_plugin
name: My First Plugin
version: 0.1.0
description: A simple demonstration plugin
author: Your Name
entry_point: my_first_plugin.py
```

### Step 3: Create the Main Plugin File

Create `my_first_plugin.py`:

```python
from PySide6.QtWidgets import QAction, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from src.core.plugin_interface import PluginInterface


class MyFirstPlugin(PluginInterface):
    def __init__(self, app):
        super().__init__(app)
        self.name = "My First Plugin"
        self.version = "0.1.0"
        self.description = "A simple demonstration plugin"
        
        # Create UI components
        self._create_widgets()
        
    def initialize(self):
        """Initialize the plugin"""
        # Connect to signals
        self.device_manager.device_added.connect(self.on_device_added)
        
        # Complete initialization
        super().initialize()
        return True
        
    def cleanup(self):
        """Clean up the plugin"""
        # Disconnect signals
        self.device_manager.device_added.disconnect(self.on_device_added)
        
        # Complete cleanup
        return super().cleanup()
        
    def _create_widgets(self):
        """Create widgets for the plugin"""
        # Create a panel widget
        self.panel_widget = QWidget()
        layout = QVBoxLayout(self.panel_widget)
        layout.addWidget(QLabel("My First Plugin"))
        
    def get_device_panels(self):
        """Get panels to be added to the device view"""
        return [("My Panel", self.panel_widget)]
        
    def on_device_added(self, device):
        """Handle device added event"""
        print(f"MyFirstPlugin: Device added - {device}")
```

### Step 4: Create the API Documentation

Create `API.md`:

```markdown
# My First Plugin API Documentation

This plugin demonstrates basic plugin functionality. It adds a simple panel to the device properties view.
```

### Step 5: Test Your Plugin

Start the NetWORKS application and verify that your plugin is loaded correctly.

## Plugin API Documentation

Plugins have access to various APIs provided by the NetWORKS application. Here are the key APIs:

### Device Manager API

The Device Manager provides methods for working with devices:

```python
# Access through the plugin interface
device_manager = self.device_manager

# Create and manage devices
new_device = device_manager.add_device(Device())
device_manager.remove_device(device)
device_list = device_manager.get_devices()

# Create and manage groups
group = device_manager.create_group("My Group")
device_manager.add_device_to_group(device, group)

# Handle selection
device_manager.select_device(device)
selected_devices = device_manager.get_selected_devices()
```

Signals:
- `device_added(device)`: Emitted when a device is added
- `device_removed(device)`: Emitted when a device is removed
- `device_changed(device)`: Emitted when a device is changed
- `selection_changed(devices)`: Emitted when selection changes

### Device Dialog API

Plugins can access standard device dialogs for creating and editing devices:

```python
# Show properties dialog for an existing device
device = self.device_manager.get_device("device-id")
updated_device = self.show_device_properties_dialog(device)
if updated_device:
    # Device was modified by the user
    pass

# Create a new device
new_device = self.add_device_dialog()
if new_device:
    # A new device was created and added to the device manager
    print(f"Created new device: {new_device.get_property('alias')}")
```

### Plugin Manager API

The Plugin Manager provides methods for working with other plugins:

```python
# Access through the plugin interface
plugin_manager = self.plugin_manager

# Get plugin information
all_plugins = plugin_manager.get_plugins()
other_plugin_info = plugin_manager.get_plugin("other_plugin_id")

# Access another plugin's instance
if other_plugin_info and other_plugin_info.loaded:
    other_plugin = other_plugin_info.instance
    # Now you can use the other plugin's public API
```

Signals:
- `plugin_loaded(plugin_info)`: Emitted when a plugin is loaded
- `plugin_unloaded(plugin_info)`: Emitted when a plugin is unloaded

### UI API

The UI API provides access to the application's user interface:

```python
# Access through the plugin interface
main_window = self.main_window
if main_window:
    # Access UI components
    status_bar = main_window.status_bar
    status_bar.showMessage("Plugin message", 3000)
```

## Extension Points

Plugins can extend the application in several ways through extension points. Here are the main extension points:

### 1. Toolbar Actions

Add actions to the main toolbar:

```python
def get_toolbar_actions(self):
    action = QAction("My Action", self)
    action.triggered.connect(self.on_my_action)
    return [action]
```

### 2. Menu Actions

Add actions to the menu:

```python
def get_menu_actions(self):
    action = QAction("My Menu Action", self)
    action.triggered.connect(self.on_my_menu_action)
    return {"My Menu": [action]}
```

### 3. Device Panels

Add panels to the device properties view:

```python
def get_device_panels(self):
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.addWidget(QLabel("My Device Panel"))
    return [("My Panel", panel)]
```

### 4. Device Table Columns

Add columns to the device table:

```python
def get_device_table_columns(self):
    def get_my_value(device):
        return device.get_property("my_property", "N/A")
    return [("my_column", "My Column", get_my_value)]
```

### 5. Device Context Menu Actions

Add actions to the device context menu:

```python
def get_device_context_menu_actions(self):
    action = QAction("My Device Action", self)
    action.triggered.connect(self.on_my_device_action)
    return [action]
```

### 6. Dock Widgets

Add dock widgets to the main window:

```python
def get_dock_widgets(self):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("My Dock Widget"))
    return [("My Dock", widget, Qt.RightDockWidgetArea)]
```

### UI Extensions

Plugins can add various UI components:

- **Toolbar Actions**: Add buttons to the main toolbar
- **Menu Actions**: Add items to the application menu
- **Device Panels**: Add panels to the device view
- **Dock Widgets**: Add dockable widgets to the main window
- **Settings Pages**: Add pages to the settings dialog

### Device Extensions

Plugins can extend device functionality:

- **Device Properties**: Add custom properties to devices
- **Device Operations**: Add operations that can be performed on devices
- **Device Discovery**: Add methods to discover devices on the network

### Plugin Configuration

Plugins can provide user-configurable settings through the Plugin Manager dialog:

#### Registering Settings

Implement the `get_settings()` method to register configurable settings:

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
        }
    }
```

The supported setting types are:
- `string`: Text input
- `int`: Integer input
- `float`: Floating-point number input
- `bool`: Boolean checkbox
- `choice`: Dropdown list of options

#### Handling Setting Updates

Implement the `update_setting()` method to handle setting changes:

```python
def update_setting(self, setting_id, value):
    """Update a plugin setting"""
    if setting_id not in self.settings:
        return False
        
    # Update the setting value
    self.settings[setting_id]["value"] = value
    
    # Apply the changes as needed
    if setting_id == "log_level":
        # Update log level
        pass
        
    return True
```

This method should return `True` if the setting was updated successfully, or `False` otherwise.

#### Accessing Settings

Access the current setting values within your plugin:

```python
# Get a setting value with a default fallback
log_level = self.settings["log_level"]["value"]

# Use the setting in your plugin
if log_level == "DEBUG":
    # Enable detailed logging
    pass
```

#### Persistent Settings

To make settings persistent across application restarts, you can:

1. Store settings in a configuration file
2. Load settings during plugin initialization
3. Update settings file when settings change

Example implementation:

```python
def initialize(self):
    # Load settings from config file
    config_file = os.path.join(self.get_plugin_dir(), "config.json")
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            saved_settings = json.load(f)
            for key, value in saved_settings.items():
                if key in self.settings:
                    self.settings[key]["value"] = value
    
    super().initialize()
    return True

def update_setting(self, setting_id, value):
    # Update setting value
    if setting_id not in self.settings:
        return False
        
    self.settings[setting_id]["value"] = value
    
    # Save settings to config file
    config_file = os.path.join(self.get_plugin_dir(), "config.json")
    settings_dict = {k: v["value"] for k, v in self.settings.items()}
    with open(config_file, "w") as f:
        json.dump(settings_dict, f, indent=4)
        
    return True
```

## Best Practices

### 1. Follow Coding Standards

Maintain consistency with the NetWORKS codebase:
- Use PEP 8 style guidelines
- Add docstrings to classes and methods
- Use meaningful variable and function names

### 2. Handle Exceptions

Catch and handle exceptions to prevent plugin failures from affecting the application:

```python
try:
    # Code that might fail
except Exception as e:
    logger.error(f"Error in my plugin: {e}")
    # Fallback behavior
```

### 3. Clean Up Resources

Always clean up resources in the `cleanup()` method:

```python
def cleanup(self):
    # Disconnect signals
    self.device_manager.device_added.disconnect(self.on_device_added)
    
    # Close open files
    if hasattr(self, 'log_file') and self.log_file:
        self.log_file.close()
    
    # Complete cleanup
    return super().cleanup()
```

### 4. Provide Comprehensive Documentation

Document your plugin's functionality and API:
- Include usage examples
- Document any device properties added
- Explain integration points with other plugins

### 5. Version Your Plugin

Use semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Incompatible API changes
- MINOR: Added functionality in a backward-compatible manner
- PATCH: Backward-compatible bug fixes

## Advanced Topics

### Creating Custom Device Types

Plugins can define custom device types with specific properties and behavior:

```python
class CustomDevice(Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Set default properties
        self.set_property("type", "custom")
        self.set_property("custom_property", "")
    
    def special_method(self):
        # Custom functionality
        pass
```

### Interacting with Other Plugins

Plugins can interact with other plugins through the plugin manager:

```python
def use_other_plugin(self, other_plugin_id):
    other_plugin_info = self.plugin_manager.get_plugin(other_plugin_id)
    if other_plugin_info and other_plugin_info.loaded:
        other_plugin = other_plugin_info.instance
        # Use the other plugin's public API
    else:
        # Handle the case where the other plugin is not available
```

### Background Processing

For long-running tasks, use a separate thread:

```python
from PySide6.QtCore import QThread, Signal

class WorkerThread(QThread):
    task_completed = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def run(self):
        # Perform long-running task
        result = self.perform_task()
        self.task_completed.emit(result)
        
    def perform_task(self):
        # Implementation
        return result
```

Usage:
```python
def start_background_task(self):
    self.worker = WorkerThread(self)
    self.worker.task_completed.connect(self.on_task_completed)
    self.worker.start()

def on_task_completed(self, result):
    # Handle the result
    pass
```

## Example Plugins

### Network Scanner Plugin

The Network Scanner plugin provides an excellent example of a well-structured plugin that extends NetWORKS with network discovery capabilities.

#### Features

- Scans networks using nmap to discover devices
- Adds discovered devices to the NetWORKS device inventory
- Offers multiple scan types (quick, standard, comprehensive)
- Supports custom scan profiles with configurable options
- Provides UI integration through context menu actions
- Incorporates a dedicated settings page for configuration
- **Automatic system dependency installation**: When enabled, automatically detects and offers to install `nmap` if missing
- **Automatic system dependency installation**: When enabled, automatically detects and offers to install `nmap` if missing

#### Code Organization

The Network Scanner plugin demonstrates proper organization with:

- Clear separation of UI and business logic
- Well-documented API in API.md
- Comprehensive README with installation and usage instructions
- Proper signal management for async operations
- Complete settings integration

#### Settings Management

The plugin shows how to implement complex settings:

```python
self.settings = {
    "default_scan_type": {
        "name": "Default Scan Type",
        "description": "The default scan type to use",
        "type": "choice",
        "default": "quick",
        "value": "quick",
        "choices": ["quick", "standard", "comprehensive"]
    },
    "scan_profiles": {
        "name": "Scan Profiles",
        "description": "Custom scan profiles",
        "type": "json",
        "default": {},
        "value": {}
    }
}
```

#### UI Integration

The plugin demonstrates proper UI integration through:

1. Context menu actions:
```python
def setup_context_menu(self):
    # Add scanner actions to the context menu
    self.device_table.context_menu_requested.connect(self.on_context_menu_requested)
    
def on_context_menu_requested(self, devices, menu):
    # Create a submenu for network scanner options
    scanner_menu = menu.addMenu("Network Scanner")
    scanner_menu.addAction("Scan Network...", self.show_scan_dialog)
    scanner_menu.addAction("Scan Interface Subnet", self.scan_interface_subnet)
    
    # Only enable these options if devices are selected
    if devices:
        scanner_menu.addAction("Scan Device's Network", 
                               lambda: self.scan_device_network(devices[0]))
        scanner_menu.addAction("Rescan Selected Device(s)", 
                               lambda: self.rescan_devices(devices))
```

2. Dock widget registration:
```python
def setup_dock_widget(self):
    # Create the dock widget
    self.dock_widget = QDockWidget("Network Scanner", self.main_window)
    self.dock_widget.setObjectName("network_scanner_dock")
    self.dock_widget.setWidget(self.dock_content)
    
    # Add the dock widget to the main window
    self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
```

#### Signal Management

The plugin defines and emits appropriate signals:

```python
# Define signals
scan_started = Signal(str)          # network range being scanned
scan_progress = Signal(int, int)    # current, total progress
scan_device_found = Signal(object)  # device found
scan_completed = Signal(dict)       # results dictionary
scan_error = Signal(str)            # error message
profile_created = Signal(str)       # profile name
profile_updated = Signal(str)       # profile name
profile_deleted = Signal(str)       # profile name
```

For more details, see the [Network Scanner Plugin API documentation](../plugins/network_scanner/API.md).

## Troubleshooting

### Plugin Not Loading

1. Check the log for error messages
2. Verify plugin directory structure
3. Check for import errors in your code
4. Ensure plugin metadata is correct

### UI Components Not Appearing

1. Check if your plugin is properly initialized
2. Verify that UI extension methods are implemented correctly
3. Check if the main window is available before accessing it

### Conflicts with Other Plugins

1. Use unique identifiers for your plugin's resources
2. Check if other plugins are modifying the same resources
3. Use plugin dependencies to ensure proper loading order

## Device Properties

### Property Naming Convention

When adding properties to devices from your plugin, use one of the following naming conventions to have them appear in the "Plugin Properties" section of the device properties panel:

```python
# Use any of these formats:
device.set_property("your_plugin_id:property_name", value)
device.set_property("your_plugin_id.property_name", value)
device.set_property("your_plugin_id_property_name", value)

# Examples for a plugin with id "backup":
device.set_property("backup:last_backup", "2023-05-15")
device.set_property("backup.next_scheduled", "2023-05-22")
device.set_property("backup_error_count", 0)
```

Where `your_plugin_id` must match your plugin's ID exactly as defined in your plugin.yaml file.

Properties that don't follow this convention will appear in the "Custom Properties" section instead.

### Documenting Properties

Document all properties your plugin adds to devices in your plugin's API.md file:

```markdown
### Device Properties

| Property | Type | Description |
|----------|------|-------------|
| your_plugin_id:property_name | string | Description of the property |
``` 