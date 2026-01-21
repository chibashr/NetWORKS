# NetWORKS - Getting Started

Welcome to NetWORKS, an extensible device management platform. This guide will help you get started with the application.

## First Launch

When you first launch NetWORKS, you'll see the main application window with the following components:

1. **Toolbar**: Quick access to common actions
2. **Device Tree** (left panel): Hierarchical view of devices and groups with search and quick actions
3. **Device Table** (center): List of devices with their properties
4. **Properties Panel** (right panel): Details of selected devices
5. **Log Panel** (bottom panel): Activity log

## Basic Operations

### Managing Devices

- **Create a Device**: Click "New Device" in the toolbar or File menu
- **Delete Devices**: Select devices and press Delete or use the context menu
- **Select Devices**: Click on a device in the table or tree
- **Multiple Selection**: Control+Click to select multiple devices
- **View Properties**: Select a device to view its properties in the right panel

### Managing Groups

- **Create a Group**: Click "New Group" in the toolbar or File menu
- **Rename a Group**: Select the group and press F2 or use "Rename" from the context menu
- **Add Devices to Group**: Drag devices to a group in the tree, or use the context menu
- **Remove from Group**: Use the context menu on a device in a group

### Navigating the Device Tree

- **Search**: Use the search box to filter devices and groups
- **Expand/Collapse**: Use the expand/collapse buttons for quick navigation
- **Compact Mode**: Toggle compact mode to fit more items in the list

### Saving and Loading

- **Save**: Click "Save" in the toolbar or File menu to save your device configuration
- **Auto-save**: Your configuration is automatically saved when you exit the application

## Plugins

NetWORKS functionality can be extended through plugins.

### Managing Plugins

1. Open the Plugin Manager from the Tools menu
2. Enable/disable plugins using the checkboxes
3. Click "Reload" to reload a plugin after making changes
4. Click "Refresh" to discover new plugins

### Installing Plugins

Installing new plugins is simple:

1. Place plugin folders into the `plugins` directory in the application root
2. Restart NetWORKS or use the "Refresh" button in the Plugin Manager
3. Enable the plugin using the checkbox in the Plugin Manager

### Sample Plugin

The Sample Plugin is included to demonstrate plugin capabilities:

- Adds a "Sample" column to the device table
- Adds a "Sample" tab to the device properties
- Adds a "Sample Plugin" panel at the bottom
- Adds a "Sample" menu with custom actions

### Developing Plugins

If you're interested in developing plugins for NetWORKS:

1. See the `README.md` file for basic plugin creation instructions
2. Check `DEVELOPMENT.md` for detailed plugin development guidelines
3. Explore the API documentation in `API.md` and module-specific API.md files
4. Use the Sample Plugin as a reference

## Next Steps

- Explore the different panels and views
- Create some device groups to organize your devices
- Check out the included plugins
- Read the documentation for more advanced features

## Troubleshooting

If you encounter issues:

- Check the log file in the `logs` directory
- Make sure you have the required Python version (3.8+)
- Verify that all dependencies are installed
- Try disabling plugins if the application is unstable

## Getting Help

Refer to the following resources for more information:

- README.md: General information about the application
- DEVELOPMENT.md: Information for developers and extending the application
- API.md: API documentation for plugin developers 