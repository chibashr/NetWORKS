# NetWORKS UI API Documentation

This document provides detailed information about the UI components of NetWORKS that plugins can interact with.

## Table of Contents

- [Main Window](#main-window)
- [Device Table](#device-table)
- [Device Tree](#device-tree)
- [Log Panel](#log-panel)
- [UI Extension Points](#ui-extension-points)

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
```

### Layout Persistence

`MainWindow` persists its dock layout and geometry in two places:

- Per-workspace layout is saved to `workspaces/<workspace>/settings/window_layout.ini` when closing or switching workspaces, and restored first when the workspace loads.
- Application-wide layout is used as a fallback when no workspace-specific layout exists.

This keeps dock positions, visibility, and sizes consistent within each workspace.

### Properties Panel – Toolbar

The Details tab toolbar keeps the “Filter properties…” search bar and the Export button on a single horizontal row at all times; they do not stack when the panel is narrow.

### Properties Panel – Details Table

The Details tab shows a two-column table (Property, Value). Right-clicking a value cell opens a context menu with copy actions and, when one or more devices are selected, **Edit Value...** (single) or **Batch Edit Value...** (multiple). Choosing Edit Value opens a dialog to change that property; the new value is applied to the selected device(s). When multiple devices are selected, batch edit applies the same value to all of them, similar to the table’s “Edit Properties” multi-device flow. List properties (e.g. tags) are edited as comma-separated text; long text (e.g. notes) uses a multiline editor. The `id` property cannot be edited.

## Device Table

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
    def get_selected_devices() -> list  # Checked devices, or highlighted rows if none checked
```

The device table view uses uniform row heights, when supported by the Qt binding, to improve resize performance on large datasets.

The device table filter controls are wrapped in a responsive container. When the main window is narrow, the filter and action buttons stack vertically instead of overlapping.

### Filter bar syntax

The device table filter bar supports both plain search and structured `field:value` filters (similar to search bars in Jira/Gmail):

- **Plain text** – Searches all columns. Example: `router` matches any cell containing "router".
- **field:value** – Restricts to a column. Example: `ip:192.168`, `alias:gateway`, `status:online`.
- **Short names** – `ip`, `host`/`hostname`, `alias`/`name`, `mac`, `status`, `tags`, `groups`. Full column names (e.g. "IP Address") also work.
- **Multiple terms** – Combined with AND. Example: `ip:192.168 status:online`.

The **Add filter** button uses the same inline button style as the device tree (12×12 icon, 18×18 button, icon-only). It opens a graphical filter builder; rules you apply there are reflected in the filter bar as syntax, so you can edit them by hand or learn the syntax from the builder.

The properties panel uses checked devices for selection. If no devices are checked, the currently highlighted rows are used to populate the Details tab.

## Device Tree

The device tree uses `DeviceTreeModel`, `DeviceTreeView`, and `DeviceTreePanel`.
`DeviceTreePanel` wraps the view with search, compact mode, and filter controls.
Device rows show the device alias/hostname in the first column and the IP address in the second column.
The device name column stretches to fill available space, while the IP column sizes to content.
Device rows show a vendor-based icon when `mac_vendor` is available (falls back to status icon).

```python
class DeviceTreeView:
    # Signals
    device_double_clicked: Signal(object)     # Emitted when a device is double-clicked
    group_selection_changed: Signal(list)    # Emitted when group selection changes
    group_filter_requested: Signal(object)   # Emitted when table filter is requested
```

## Log Panel

The log panel control row uses a responsive container to keep filters and buttons readable on narrow windows. When width is constrained, the control groups stack vertically to avoid overlapping the log content.

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
    """
```

Example:
```python
def get_menu_actions(self):
    action = QAction("My Menu Action", self)
    action.triggered.connect(self.on_my_menu_action)
    return {"My Menu": [action]}
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