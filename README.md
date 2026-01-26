# NetWORKS

An extensible device management application.

Current Release: 0.10.2

## Features

- Device inventory with groups, tags, and custom properties
- Workspace isolation with per-workspace UI layout persistence
- Plugin system for UI extensions and device automation
- Multi-device selection and bulk operations
- Import wizard for CSV/text device onboarding
- Autosave with configurable backups and rotation
- Centralized settings for UI, autosave, devices, and logging
- Integrated documentation hub with dynamically loaded plugin docs
- Windows launcher for quick setup and execution

## Installation

### Windows

1. Clone the repository or download the source code
2. Run `Start_NetWORKS.bat` to automatically set up the environment and launch the application

### Manual Setup

1. Clone the repository or download the source code
2. Create a Python virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the application: `python networks.py`

## Workspaces

NetWORKS supports multiple workspaces for managing different device configurations. Each workspace maintains its own set of devices, groups, and enabled plugins.

### Creating a New Workspace

1. Go to **File → Workspaces → New Workspace**
2. Enter a name and optional description for the workspace
3. Choose whether to switch to the new workspace immediately

### Switching Workspaces

1. Go to **File → Workspaces → Open Workspace**
2. Select a workspace from the list

### Managing Workspaces

1. Go to **File → Workspaces → Manage Workspaces**
2. From here you can:
   - Switch to a different workspace
   - Delete workspaces (except the default workspace)

## Autosave and Backups

NetWORKS includes a comprehensive autosave system to prevent data loss:

- **Automated Saving**: Configure automatic workspace saving at specified intervals
- **Smart Detection**: Option to only save when changes are detected
- **Backup System**: Automatic creation of backup files during autosaves
- **Backup Rotation**: Configurable limit on the number of backup files to keep

See the [Autosave Documentation](docs/autosave.md) for detailed information on configuring and using this feature.

## Application Settings

Access the settings dialog via **Tools → Settings** to configure various aspects of the application:

- **General**: Theme, plugin loading, update settings
- **User Interface**: Font size, toolbar position, table appearance
- **Autosave**: Configure autosave behavior and backups
- **Devices**: Device discovery and connection settings
- **Logging**: Log level, retention, and diagnostics
- **Advanced**: Performance, networking, and security settings

## Device Storage

Devices are stored in individual directories under the `config/devices` directory. Each device has its own directory named with its UUID, containing:

- `device.json` - Device properties and metadata
- Associated files - Configuration files, logs, or other files associated with the device

## Plugins

NetWORKS can be extended with plugins. Plugins are stored in the `plugins` directory.

### Plugin Manifest

Each plugin must include a `manifest.json` file that provides information about the plugin. See the [Plugin Manifest](docs/plugins/manifest.md) documentation for details.

### Sample Plugin

A sample plugin is included in the `plugins/sample` directory to demonstrate the plugin architecture.

## Development

### Project Structure

```
NetWORKS/
├── config/              # Configuration files
│   ├── devices/         # Device storage
│   └── workspaces/      # Workspace configurations
├── docs/                # Documentation
│   ├── api/             # API documentation
│   └── plugins/         # Plugin development guides
├── logs/                # Application logs
├── plugins/             # Plugin directory
│   └── sample/          # Sample plugin
├── src/                 # Source code
│   ├── core/            # Core functionality
│   ├── plugins/         # Internal plugins
│   └── ui/              # User interface
├── manifest.json        # Application manifest
├── networks.py          # Main entry point
├── README.md            # This file
├── requirements.txt     # Python dependencies
├── setup.bat            # Setup script for Windows
└── Start_NetWORKS.bat   # Launcher for Windows
```

### Adding a New Device Type

To add a new device type, you can either:

1. Extend the base `Device` class in a plugin
2. Register a custom device factory with the `DeviceManager`

### Creating a Plugin

See the [Plugin Development Guide](docs/plugins/README.md) for details on creating plugins.

## Documentation

NetWORKS includes comprehensive documentation to help you get started and extend the platform:

- [Documentation Index](docs/index.md): Master entry point for all docs
- [Program Reference](docs/PROGRAM_REFERENCE.md): Architecture, data layout, and core systems
- [Getting Started Guide](docs/GETTING_STARTED.md): First steps with NetWORKS
- [Device Management Guide](docs/DEVICE_MANAGEMENT.md): Managing devices and groups
- [Workspaces](docs/workspaces.md): Workspace structure and layout persistence
- [Autosave Documentation](docs/autosave.md): Autosave and backups
- [Development Guide](docs/DEVELOPMENT.md): Core development and plugin lifecycle
- [API Documentation](docs/API.md): API overview for plugins
- [Plugin Development Guide](docs/plugins/README.md): Extending NetWORKS

Plugin documentation lives inside each plugin folder (for example, `plugins/network_scanner/README.md`). The in-app documentation hub loads plugin docs dynamically when plugins are loaded.

## Architecture

NetWORKS is built around three layers:
- **Core**: Device management, workspace persistence, configuration, and logging
- **UI**: Dock-based main window, device tree/table, and dialogs
- **Plugins**: Feature extensions, discovery, and UI integrations

Core services include:
- **Device Manager**: Device/group CRUD, selection, and persistence
- **Plugin Manager**: Discovery, enable/disable, load/unload, lifecycle
- **Configuration Manager**: Layered config (`default.yaml`, `plugins.yaml`, `user.yaml`)

Plugins can extend the application by:
- Adding toolbar actions and menu items
- Registering device properties and operations
- Adding device table columns and detail panels
- Adding dock widgets and settings pages
- Subscribing to and emitting application signals

## License

This project is licensed under the MIT License.