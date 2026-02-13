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

## Automatic Updates

NetWORKS supports automatic updates using Git. This makes keeping your installation up-to-date seamless and easy.

### How It Works

1. **First Update**: When you first check for updates on an extracted zip installation, NetWORKS will automatically initialize a Git repository for your installation. This is a one-time setup that happens in the background.

2. **Future Updates**: Once initialized, updates are performed automatically by pulling the latest changes from the repository. You'll see progress indicators during the update process.

3. **Update Channels**: You can choose which update channel to follow:
   - **Stable**: Recommended for production use (default)
   - **Beta**: Pre-release versions for testing
   - **Alpha**: Early development versions
   - **Development**: Latest from main branch

### Requirements

- **Git**: Git must be installed on your system for automatic updates to work. If Git is not installed, you'll be prompted with instructions.
  - Download Git from: https://git-scm.com/downloads
  - After installing Git, restart NetWORKS

### Checking for Updates

- **Manual Check**: Go to **Help → Check for Updates** to manually check for available updates
- **Automatic Check**: NetWORKS can automatically check for updates on startup (configurable in Settings)

### Update Process

When an update is available:

1. You'll see an update notification dialog with release notes
2. Click **"Update Now"** to start the update
3. The system will:
   - Initialize Git repository (if needed, first time only)
   - Fetch the latest changes from the remote repository
   - Apply the updates
   - Verify the update was successful
4. Restart NetWORKS to apply the changes

### Manual Updates

If you prefer not to use automatic updates or Git is not available:

1. Visit the [GitHub Releases page](https://github.com/chibashr/NetWORKS/releases)
2. Download the latest release zip file
3. Extract and replace the application files
4. Restart NetWORKS

### Configuration

Update settings can be configured in **Tools → Settings → General**:

- **Update Channel**: Choose which branch to update from
- **Auto-initialize Git**: Automatically set up Git repository on first update (recommended)
- **Repository URL**: Custom repository URL (for forks or custom installations)

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