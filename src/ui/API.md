# NetWORKS UI API Documentation

This document provides detailed information about the UI components of NetWORKS that plugins can interact with.

## Table of Contents

- [Main Window](#main-window)
- [Device Table](#device-table)
- [Device Tree](#device-tree)
- [UI Extension Points](#ui-extension-points)
- [Device Dialogs](#device-dialogs)
- [Workspace Integration](#workspace-integration)

## Main Window

The `MainWindow` class is the primary window of the application. Plugins can access it through `self.main_window`.

```python
class MainWindow:
    # Properties
    app: Application                    # Application instance
    device_manager: DeviceManager       # Device manager instance
    plugin_manager: PluginManager       # Plugin manager instance
    config: Config                      # Configuration manager instance
    
    # UI Components
    toolbar: QToolBar                   # Main toolbar
    menu_bar: QMenuBar                  # Main menu bar
    status_bar: QStatusBar              # Status bar
    device_table: DeviceTableView       # Device table view
    device_tree: DeviceTreeView         # Device tree view
    central_widget: QWidget             # Central widget
    properties_widget: QTabWidget       # Properties panel
    
    # Dock Widgets
    dock_device_tree: QDockWidget       # Device tree dock widget
    dock_properties: QDockWidget        # Properties dock widget
    dock_log: QDockWidget               # Log dock widget
    
    # Methods
    def update_status_bar()             # Update status bar with current counts
    def add_plugin_ui_components(self, plugin_info)  # Add UI components from a plugin
    def remove_plugin_ui_components(self, plugin_info)  # Remove UI components from a plugin
    def findMenu(self, menu_name)       # Find a menu by name
```

## Device Table

The device table lives in the `device_table` package (`src/ui/device_table/`). Import from the package for a stable API:

- `from .device_table import DeviceTableModel, DeviceTableView, QAbstractItemView`
- Submodules: `device_table_filter` (filter syntax, `IPSortFilterProxyModel`), `device_table_dialogs` (`AdvancedFilterDialog`), `device_table_model`, `device_table_view`.

The `DeviceTableModel` and `DeviceTableView` classes provide the device table functionality.

```python
class DeviceTableModel:
    # Methods
    def refresh_devices()               # Refresh the device list
    def add_column(self, header, key, callback=None): bool  # Add a column to the table
    def remove_column(self, header): bool  # Remove a column from the table
```

```python
class DeviceTableView:
    # Signals
    double_clicked: Signal(object)      # Emitted when a device is double-clicked
    
    # Methods
    def device_properties_dialog(self, device=None)  # Show properties dialog for a device or create new
```

## Device Tree

The device tree lives in the `device_tree` package (`src/ui/device_tree/`). Import from the package:

- `from .device_tree import DeviceTreeModel, DeviceTreeView, DeviceTreePanel`
- Submodules: `device_tree_item`, `device_tree_model`, `device_tree_filter`, `device_tree_view`, `device_tree_panel`.

The `DeviceTreeModel` and `DeviceTreeView` classes provide the device tree functionality.

```python
class DeviceTreeView:
    # Signals
    device_double_clicked: Signal(object)  # Emitted when a device is double-clicked
```

## Device Dialogs

Plugins can access device dialogs through methods provided by the `PluginInterface` class. This allows plugins to create, edit and manage devices through the standard UI.

```python
class PluginInterface:
    # Device Dialog Methods
    def show_device_properties_dialog(self, device=None)  # Show properties dialog for a device or create new
    def add_device_dialog()  # Show add device dialog and add the device to the manager
```

Example usage:

```python
def my_plugin_method(self):
    # Edit an existing device
    device = self.device_manager.get_device_by_id("some-id")
    if device:
        self.show_device_properties_dialog(device)
        
    # Add a new device
    new_device = self.add_device_dialog()
    if new_device:
        # The device has already been added to the device manager
        logger.info(f"Added new device: {new_device.get_property('alias')}")
```

## UI Extension Points

Plugins can extend the UI in several ways by implementing methods in the `PluginInterface`:

### Toolbar Actions

```python
def get_toolbar_actions() -> list:
    """
    Get actions to be added to the toolbar
    
    Returns:
        list: List of QAction objects
    """
```

Example:
```python
def get_toolbar_actions(self):
    action = QAction("My Action", self)
    action.triggered.connect(self.on_my_action)
    return [action]
```

### Menu Actions

```python
def get_menu_actions() -> dict:
    """
    Get actions to be added to the menu
    
    Returns:
        dict: Dictionary mapping menu names to lists of QAction objects
              Menu names can be either existing menus (like "File", "Edit", "Tools") 
              or new menu names to be created
    """
```

Example:
```python
def get_menu_actions(self):
    # Create an action for a new plugin-specific menu
    plugin_action = QAction("Plugin Specific Action", self)
    plugin_action.triggered.connect(self.on_plugin_action)
    
    # Create an action for an existing menu (like Tools)
    tools_action = QAction("Plugin Tool Action", self)
    tools_action.triggered.connect(self.on_tool_action)
    
    return {
        "My Plugin Menu": [plugin_action],  # Creates a new menu
        "Tools": [tools_action]  # Adds to existing Tools menu
    }
```

### Device Panels

```python
def get_device_panels() -> list:
    """
    Get panels to be added to the device properties view
    
    Returns:
        list: List of (panel_name, widget) tuples
    """
```

Example:
```python
def get_device_panels(self):
    panel = QWidget()
    # Configure panel...
    return [("My Panel", panel)]
```

### Device Table Columns

```python
def get_device_table_columns() -> list:
    """
    Get columns to be added to the device table
    
    Returns:
        list: List of (column_id, column_name, callback) tuples
              where callback is a function that takes a device and returns the value
    """
```

Example:
```python
def get_device_table_columns(self):
    def get_my_value(device):
        return device.get_property("my_property", "N/A")
    return [("my_column", "My Column", get_my_value)]
```

### Device Context Menu Actions

```python
def get_device_context_menu_actions() -> list:
    """
    Get actions to be added to the device context menu
    
    Returns:
        list: List of QAction objects
    """
```

### Device Tabs

```python
def get_device_tabs() -> list:
    """
    Get tabs to be added to the device details view
    
    Returns:
        list: List of (tab_name, widget) tuples
    """
```

### Dock Widgets

```python
def get_dock_widgets() -> list:
    """
    Get dock widgets to be added to the main window
    
    Returns:
        list: List of (widget_name, widget, area) tuples
              where area is one of Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea,
              Qt.TopDockWidgetArea, or Qt.BottomDockWidgetArea
    """
```

Example:
```python
def get_dock_widgets(self):
    dock_widget = QWidget()
    # Configure dock widget...
    return [("My Dock", dock_widget, Qt.RightDockWidgetArea)]
```

### Settings Pages

```python
def get_settings_pages() -> list:
    """
    Get settings pages to be added to the settings dialog
    
    Returns:
        list: List of (page_name, widget) tuples
    """
```

## Workspace Integration

NetWORKS supports plugin integration with workspaces, including preserving plugin UI layouts.

### Plugin Layout Persistence

When a user switches workspaces or closes and reopens the application, the following plugin UI elements will be preserved:

1. Dock widget positions and sizes
2. Custom panels in the properties view
3. Custom toolbar items
4. Menu items added to existing or custom menus

This happens automatically for any UI components added through the standard plugin extension points.

### Best Practices for Plugin Layout

For best results with workspaces:

1. Always add UI components during plugin initialization
2. Remove UI components during cleanup
3. Use standard extension points rather than direct manipulation
4. Ensure your plugin responds appropriately to workspace changes 