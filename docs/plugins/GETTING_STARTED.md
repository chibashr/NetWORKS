# Getting Started with NetWORKS Plugin Development

This guide will walk you through creating your first NetWORKS plugin from scratch.

## Prerequisites

- Basic knowledge of Python programming
- Familiarity with PySide6 (Qt for Python) is helpful but not required
- A working installation of NetWORKS

## 1. Setting Up Your Development Environment

### Plugin Directory Structure

Create a new directory for your plugin inside the NetWORKS `plugins` directory:

```
plugins/
└── my_first_plugin/         # Your plugin directory
    ├── __init__.py          # Plugin entry point (set in entry_point)
    ├── manifest.json        # Plugin metadata
    ├── API.md               # API documentation
    └── resources/           # Optional resources directory
        └── icons/           # Optional icons
```

## 2. Creating the Manifest File

Create a file called `manifest.json` in your plugin directory with the following content:

```json
{
  "id": "my_first_plugin",
  "name": "My First Plugin",
  "version": "0.1.0",
  "description": "A simple plugin for NetWORKS",
  "author": "chibashr",
  "entry_point": "__init__.py",
  "min_app_version": "0.5.0",
  "dependencies": []
}
```

## 3. Implementing the Plugin

Create a file called `__init__.py` in your plugin directory:

```python
from PySide6.QtWidgets import QAction, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Slot
from loguru import logger

from src.core.plugin_interface import PluginInterface


class MyFirstPlugin(PluginInterface):
    def __init__(self):
        """Initialize the plugin"""
        super().__init__()
        logger.info("My First Plugin constructed")
        
    def initialize(self, app, plugin_info):
        """Initialize the plugin
        
        Called when the plugin is loaded and ready to be initialized.
        Connect to signals and set up UI components here.
        """
        logger.info("Initializing My First Plugin")
        
        # Store app references
        self.app = app
        self.device_manager = app.device_manager
        self.main_window = app.main_window
        self.config = app.config
        self.plugin_info = plugin_info

        # Connect to device manager signals
        self.device_manager.device_added.connect(self.on_device_added)
        self.device_manager.device_removed.connect(self.on_device_removed)
        self.device_manager.selection_changed.connect(self.on_selection_changed)
        
        # Complete initialization
        self._initialized = True
        return True
        
    def cleanup(self):
        """Clean up the plugin
        
        Called when the plugin is being unloaded or the application is closing.
        Disconnect signals and clean up resources here.
        """
        logger.info("Cleaning up My First Plugin")
        
        # Disconnect from signals
        self.device_manager.device_added.disconnect(self.on_device_added)
        self.device_manager.device_removed.disconnect(self.on_device_removed)
        self.device_manager.selection_changed.disconnect(self.on_selection_changed)
        
        # Complete cleanup
        return super().cleanup()
    
    # Event handlers
    
    @Slot(object)
    def on_device_added(self, device):
        """Handle device added event
        
        Args:
            device: The added device
        """
        logger.info(f"Device added: {device.get_property('alias')}")
    
    @Slot(object)
    def on_device_removed(self, device):
        """Handle device removed event
        
        Args:
            device: The removed device
        """
        logger.info(f"Device removed: {device.get_property('alias')}")
    
    @Slot(list)
    def on_selection_changed(self, devices):
        """Handle selection changed event
        
        Args:
            devices: List of selected devices
        """
        if not devices:
            logger.info("No devices selected")
        elif len(devices) == 1:
            logger.info(f"Selected device: {devices[0].get_property('alias')}")
        else:
            logger.info(f"Selected {len(devices)} devices")
    
    # UI Extension methods
    
    def get_toolbar_actions(self):
        """Get toolbar actions
        
        Returns:
            list: List of QActions to add to the toolbar
        """
        action = QAction("My Plugin Action", self)
        action.triggered.connect(self.on_toolbar_action)
        return [action]
    
    def get_device_panels(self):
        """Get device panels
        
        Returns:
            list: List of tuples (name, widget) to add to the device properties view
        """
        # Create a panel widget
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("My First Plugin Panel"))
        
        return [("My Panel", panel)]
    
    def get_device_context_menu_actions(self):
        """Get device context menu actions
        
        Returns:
            list: List of QActions to add to the device context menu
        """
        action = QAction("My Plugin Context Action", self)
        action.triggered.connect(self.on_context_action)
        return [action]
    
    # Action handlers
    
    def on_toolbar_action(self):
        """Handle toolbar action"""
        logger.info("Toolbar action triggered")
        
        # Get selected devices
        devices = self.device_manager.get_selected_devices()
        
        if not devices:
            logger.info("No devices selected")
        elif len(devices) == 1:
            device = devices[0]
            logger.info(f"Processing device: {device.get_property('alias')}")
        else:
            logger.info(f"Processing {len(devices)} devices")
    
    def on_context_action(self, device_or_devices):
        """Handle context menu action
        
        Args:
            device_or_devices: Single device or list of devices
        """
        # Normalize to a list
        devices = []
        
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices:
            devices = [device_or_devices]
            
        logger.info(f"Context action for {len(devices)} devices")
```

## 4. Creating Documentation

Create a file called `API.md` in your plugin directory:

```markdown
# My First Plugin API Documentation

This plugin demonstrates the basic structure and capabilities of a NetWORKS plugin.

## Features

- Logs device additions and removals
- Adds a toolbar action
- Provides a device properties panel
- Adds a context menu action

## Integration

Other plugins can integrate with this plugin by:

1. Checking if it's loaded
2. Accessing its public methods

```

## 5. Testing Your Plugin

1. Start NetWORKS
2. Go to **Settings → Plugins**
3. Your plugin should appear in the list
4. Enable the plugin
5. The plugin will be loaded and initialized

## Next Steps

Now that you've created a basic plugin, you can extend it with more functionality:

1. **Add custom device properties**:
   ```python
   def on_device_added(self, device):
       # Add a custom property
       device.set_property("my_plugin_status", "initialized")
   ```

2. **Add a custom device tab**:
   ```python
   def get_device_tabs(self):
       tab = QWidget()
       layout = QVBoxLayout(tab)
       layout.addWidget(QLabel("My Custom Tab"))
       return [("My Tab", tab)]
   ```

3. **Add a settings page**:
   ```python
   def get_settings_pages(self):
       page = QWidget()
       layout = QVBoxLayout(page)
       layout.addWidget(QLabel("My Plugin Settings"))
       return [("My Plugin", page)]
   ```

4. **Connect to other plugins**:
   ```python
   def connect_to_other_plugin(self):
       other_plugin_info = self.plugin_manager.get_plugin("other_plugin_id")
       if other_plugin_info and other_plugin_info.loaded:
           other_plugin = other_plugin_info.instance
           # Now use other_plugin's API
   ```

## Resources

- [Plugin Development Guide](README.md): Complete plugin development documentation
- [API Documentation](../API.md): Core API reference
- [Signals Documentation](../api/signals.md): Working with signals and events
- [Context Menu API](../api/context_menu.md): Customizing context menus
- [Multi-Device Operations](../MULTI_DEVICE_OPERATIONS.md): Working with multiple devices 