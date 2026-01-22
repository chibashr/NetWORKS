# NetWORKS Plugin Development Guide

This guide provides comprehensive information for developing plugins for the NetWORKS platform. Plugins are the primary way to extend and customize NetWORKS functionality.

## Table of Contents

- [Plugin System Overview](#plugin-system-overview)
- [Plugin Structure](#plugin-structure)
- [Plugin Development Lifecycle](#plugin-development-lifecycle)
- [Creating Your First Plugin](#creating-your-first-plugin)
- [Plugin API Documentation](#plugin-api-documentation)
- [Communication and Integration](#communication-and-integration)
- [Extension Points](#extension-points)
- [Best Practices](#best-practices)
- [Advanced Topics](#advanced-topics)
- [Example Plugins](#example-plugins)
- [Diagnostics and Validation](#diagnostics-and-validation)
- [Troubleshooting](#troubleshooting)
- [Device Properties](#device-properties)
- [Plugin UI Design Guide](ui_design.md)

## Quick Start

For a step-by-step tutorial on creating your first plugin, see the [Getting Started Guide](GETTING_STARTED.md).

## Plugin Quick Checklist

Use this list to mirror what the plugin manager expects during discovery and load:

- `manifest.json` or `plugin.json` (preferred), or `plugin.yaml` (legacy)
- Required manifest fields: `id`, `name`, `version`, `entry_point`
- Entry point file exists and is valid Python
- Plugin class is in the entry point module and implements `initialize(app, plugin_info)`
- `API.md` present (recommended; missing docs trigger a warning)
- Optional: `requirements.txt` for Python package hints

## Documentation Standards

Each plugin should document itself in its own folder:
- `README.md`: Operational overview, usage, and configuration.
- `API.md`: Public API for other plugins and integration points.
- `docs/` (optional): Additional guides and troubleshooting notes.

The documentation hub loads plugin documentation dynamically when a plugin is loaded, so keep these files up to date.

## Icon Specifications

Icons used in plugin UI should follow the application icon spec in
`docs/Design Considerations.md`.

**Sizes:**
- Toolbar: 24x24px
- Panel header: 16x16px
- Inline: 16x16px
- Status: 12x12px
- Large (dialogs): 32x32px
- Plugin icon: 48x48px minimum (store under `resources/icons`)

**Style:**
- Material Icons (filled)
- Monochrome using theme text colors (black in light theme, white in dark theme)
- Minimal detail
- 2px stroke width when using outline variants
- SVG preferred

**Behavior:**
- Icon-only actions must include tooltips and aria-labels

## Plugin System Overview

The NetWORKS plugin system is designed to be:

- **Flexible**: Plugins can extend almost any part of the application
- **Modular**: Plugins can be enabled, disabled, or uninstalled independently
- **Discoverable**: Plugins are discovered from internal/external plugin directories at startup, and workspace plugins are discovered when a workspace loads
- **Transparent**: Plugins run in-process with the application, so only install plugins you trust

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
├── API.md              # API documentation (expected)
├── manifest.json       # Plugin metadata (required, preferred)
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

#### manifest.json / plugin.json / plugin.yaml (legacy)

This file contains plugin metadata. NetWORKS reads `manifest.json` or `plugin.json` first, and falls back to `plugin.yaml` for legacy plugins.

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "A comprehensive description of the plugin's functionality.",
  "author": "chibashr",
  "entry_point": "my_plugin.py",
  "min_app_version": "0.1.0",
  "dependencies": [
    { "id": "other_plugin", "version": ">=1.0.0" }
  ]
}
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

The API.md file is expected for all plugins. NetWORKS will warn if it is missing, and the documentation hub cannot surface plugin docs without it.

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

This is the entry point specified in your manifest file. It should contain a class that inherits from `PluginInterface` and implements `initialize(app, plugin_info)`:

```python
from src.core.plugin_interface import PluginInterface

class MyPlugin(PluginInterface):
    def __init__(self):
        super().__init__()

    def initialize(self, app, plugin_info):
        # Store references provided by the app
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info

        # Plugin initialization code
        self._initialized = True
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

NetWORKS calls `initialize(app, plugin_info)` during load. The optional `start()` and `stop()` hooks are available for plugin-managed workflows, but they are not invoked automatically by the plugin manager.

## Communication and Integration

Use these patterns to keep plugins interoperable and predictable.

### Core References

Plugins receive these references in `initialize(app, plugin_info)`:

- `app`: The application instance
- `device_manager`: Device and group operations + signals
- `main_window`: UI integration surface
- `config`: Application configuration access
- `plugin_info`: Metadata and state for the current plugin

Keep these as attributes so other methods can use them safely.

### Signals to Listen To

Common signals that enable cross-plugin awareness:

- `device_manager.device_added(device)`
- `device_manager.device_removed(device)`
- `device_manager.device_changed(device)`
- `device_manager.selection_changed(devices)`
- `plugin_manager.plugin_loaded(plugin_info)`
- `plugin_manager.plugin_unloaded(plugin_info)`
- `plugin_manager.plugin_enabled(plugin_info)`
- `plugin_manager.plugin_disabled(plugin_info)`
- `plugin_manager.plugin_state_changed(plugin_info)`
- `plugin_manager.plugin_status_changed(plugin_info, status_message)`

Connect during `initialize()` and disconnect during `cleanup()` to avoid leaked connections.

### Signals You Can Emit

`PluginInterface` defines lifecycle signals you can emit to communicate status:

- `plugin_initialized`
- `plugin_starting`
- `plugin_running`
- `plugin_stopping`
- `plugin_cleaned_up`
- `plugin_error(message)`

Emit these when meaningful so other plugins and diagnostics can react.

### Interacting With Other Plugins

Plugins can query other plugins through the plugin manager:

```python
plugin_manager = self.plugin_manager
other_plugin_info = plugin_manager.get_plugin("other_plugin_id")
if other_plugin_info and other_plugin_info.loaded:
    other_plugin = other_plugin_info.instance
    # Use other_plugin public methods documented in its API.md
```

Use this pattern to keep integrations optional and resilient.

### Cross-Plugin Contracts

If your plugin exposes a public API:

- Document methods and expected inputs/outputs in `API.md`
- Avoid relying on private attributes of other plugins
- Prefer stable, versioned methods and clear error behavior

### Plugin Settings Communication

If your plugin exposes settings via `get_settings()`:

- Keep setting IDs stable across releases
- Validate values in `update_setting()` and return `False` on invalid input
- Document each setting in `API.md` so other plugins can read values safely

### Workspace Awareness

Workspace plugins are discovered when a workspace loads. If your plugin stores data:

- Prefer storing within your plugin directory or a workspace-specific subfolder
- Avoid global state that spans workspaces unless intentionally shared
- Recompute workspace-specific caches in `initialize()` or on workspace change hooks

### Plugin Initialization

During initialization, a plugin should:

1. Set up internal data structures
2. Connect to signals
3. Register UI components
4. Register device types or properties

Example:

```python
def initialize(self, app, plugin_info):
    # Set up internal data
    self.devices = {}

    # Store app references
    self.app = app
    self.device_manager = app.device_manager
    self.main_window = app.main_window
    self.config = app.config
    self.plugin_info = plugin_info
    
    # Connect to signals
    self.device_manager.device_added.connect(self.on_device_added)
    self.device_manager.device_removed.connect(self.on_device_removed)
    
    # Register UI components in main_window
    if hasattr(self, 'main_window'):
        self.setup_ui_components()
    
    # Initialize complete
    self._initialized = True
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

Create a `manifest.json` file (recommended) or `plugin.yaml` (legacy):

```json
{
  "id": "my_first_plugin",
  "name": "My First Plugin",
  "version": "0.1.0",
  "description": "A simple demonstration plugin",
  "author": "chibashr",
  "entry_point": "my_first_plugin.py"
}
```

### Step 3: Create the Main Plugin File

Create `my_first_plugin.py`:

```python
from PySide6.QtWidgets import QAction, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

from src.core.plugin_interface import PluginInterface


class MyFirstPlugin(PluginInterface):
    def __init__(self):
        super().__init__()
        self.name = "My First Plugin"
        self.version = "0.1.0"
        self.description = "A simple demonstration plugin"
        
        # Create UI components
        self._create_widgets()
        
    def initialize(self, app, plugin_info):
        """Initialize the plugin"""
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info

        # Connect to signals
        self.device_manager.device_added.connect(self.on_device_added)
        
        # Complete initialization
        self._initialized = True
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
def initialize(self, app, plugin_info):
    # Store app references
    self.app = app
    self.device_manager = app.device_manager
    self.main_window = app.main_window
    self.config = app.config
    self.plugin_info = plugin_info

    # Load settings from config file
    config_file = os.path.join(self.plugin_info.path, "config.json")
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            saved_settings = json.load(f)
            for key, value in saved_settings.items():
                if key in self.settings:
                    self.settings[key]["value"] = value
    
    self._initialized = True
    return True

def update_setting(self, setting_id, value):
    # Update setting value
    if setting_id not in self.settings:
        return False
        
    self.settings[setting_id]["value"] = value
    
    # Save settings to config file
    config_file = os.path.join(self.plugin_info.path, "config.json")
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

### 6. Keep the UI Responsive

Avoid long-running work on the UI thread:
- Move I/O and heavy computation to a worker thread
- Use signals to report progress and update UI safely
- Cancel or stop workers during `cleanup()`

### 7. Track Signal Connections

Maintain a list of signal connections you establish so you can disconnect cleanly:
- Connect in `initialize()`
- Disconnect in `cleanup()` even if initialization was partial
- Guard disconnects to avoid exceptions

### 8. Use Stable Public APIs

If other plugins might call you:
- Keep your public methods small and documented
- Validate inputs and return consistent shapes
- Log useful errors instead of raising unhandled exceptions

### 9. Declare Dependencies Explicitly

Use the manifest `dependencies` field when you rely on other plugins:
- Check for dependency availability at runtime
- Degrade gracefully if the dependency is missing or disabled

### 10. Store Data Predictably

Keep plugin data in clear, documented locations:
- Prefer a `data/` folder inside your plugin directory
- Separate workspace-specific data if it should not be shared
- Document file formats and retention in your `README.md`

### 11. Log With Context

Use structured logging and include your plugin ID in messages:
- Prefer `logger.info(f"[{self.plugin_info.id}] ...")`
- Log configuration changes and external integrations
- Avoid logging sensitive values

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
- **Dependency awareness**: Reports missing Python/system requirements so you can install them before enabling features

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
def get_dock_widgets(self):
    """Get plugin dock widgets"""
    # IMPORTANT: Panel titles should use the full plugin name for easy identification
    # Example: "Network Scanner" not "Scanner", "Command Manager" not "Commands"
    dock = QDockWidget("Network Scanner")  # Use full plugin name
    dock.setWidget(self.main_widget)
    dock.setObjectName("NetworkScannerDock")
    dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
    
    # Return a list of tuples: (widget_name, widget, area)
    return [("Network Scanner", dock, Qt.RightDockWidgetArea)]
```

**Panel Title Requirements:**
- Panel titles (QDockWidget titles) must use the full plugin name
- This makes it easy to identify which plugin a panel belongs to
- Example: "Network Scanner" not "Scanner", "Command Manager" not "Commands"
- The widget_name in the return tuple should also match the plugin name

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

## Diagnostics and Validation

These checks make plugins easier to support and integrate.

### Startup Validation Checklist

- Confirm required manifest fields are present and correct
- Confirm the entry point file exists and is importable
- Confirm your plugin class implements `initialize(app, plugin_info)`
- Warn clearly if optional dependencies are missing
- Log a concise startup summary (version, key config, feature flags)

### Dependency Probes

If you depend on optional libraries or executables:

- Check availability during `initialize()`
- Disable only the feature that needs the dependency
- Log a single warning with remediation steps

### Self-Test Hooks

Provide a lightweight self-test path to validate core behavior:

- Expose a menu or toolbar action that runs a quick smoke test
- Log pass/fail with actionable errors
- Keep tests fast and non-destructive

### Failure Modes

When failing to initialize:

- Return `False` from `initialize()` and log the root cause
- Avoid raising uncaught exceptions
- Leave the UI in a safe, unchanged state

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

Where `your_plugin_id` must match your plugin's ID exactly as defined in your manifest file.

Properties that don't follow this convention will appear in the "Custom Properties" section instead.

### Documenting Properties

Document all properties your plugin adds to devices in your plugin's API.md file:

```markdown
### Device Properties

| Property | Type | Description |
|----------|------|-------------|
| your_plugin_id:property_name | string | Description of the property |
``` 