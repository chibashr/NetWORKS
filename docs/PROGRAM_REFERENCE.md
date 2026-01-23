# NetWORKS Program Reference

This reference describes the NetWORKS application end-to-end: what it does, how it is structured, where data lives, and how the major subsystems interact. It is intended to be a durable overview that complements the task-focused guides in this documentation set.

## Scope

This document covers:
- Application entry points and startup flow
- UI layout and major dialogs
- Core systems (device management, workspaces, configuration, logging)
- Data storage layout
- Plugin system architecture and extension points
- Operational scripts and packaging assets

For deep-dive workflows, use:
- `GETTING_STARTED.md`
- `DEVICE_MANAGEMENT.md`
- `MULTI_DEVICE_OPERATIONS.md`
- `workspaces.md`
- `autosave.md`
- `INSTALLATION_TROUBLESHOOTING.md`
- `packaging/windows_exe.md`

## Application Overview

NetWORKS is an extensible device management platform built around a core device model and a plugin architecture. It provides:
- Device and group inventory management
- Multi-device operations and bulk edits
- Workspace separation and UI layout persistence
- A plugin system for discovery, automation, and UI extensions
- An integrated documentation hub

## Entry Points and Startup

- `Start_NetWORKS.bat`: Convenience launcher for Windows.
- `networks.py`: Primary Python entry point that instantiates the application.
- `src/app.py`: Application bootstrap, wiring core services and the UI.

Startup flow (simplified):
1. Configuration is loaded from `config/default.yaml`, `config/plugins.yaml`, and `config/user.yaml`.
2. Core services (device manager, plugin manager, logging) are initialized.
3. Main UI is created and dock widgets are configured.
4. Plugins are discovered and loaded based on registry state in `config/plugins.json`.

## UI Layout and Major Screens

NetWORKS is a Qt application with a dock-based layout. The main window includes:
- **Toolbar**: Primary actions (new device/group, save, refresh, etc.).
- **Device Tree**: Hierarchical view of groups and devices with context actions.
- **Device Table**: Tabular list of devices and key properties.
- **Properties Panel**: Right-side details for the selected device(s).
- **Log Panel**: Application activity and plugin output.
- **Dock Widgets**: Plugin-defined panels (for example, network scanner).

Important dialogs and panels:
- **Plugin Manager**: Enable, disable, reload, configure, and view plugin docs.
- **Settings**: Application configuration (UI, autosave, device behavior).
- **Import Wizard**: Bulk import devices with column mapping.
- **Documentation Hub**: Browse user, API, and plugin documentation.
- **Recycle Bin**: Restore or permanently delete removed devices.

## Core Systems and Data Model

### Device Management

The device system is the foundation of NetWORKS:
- **Device**: Core properties plus plugin-added properties.
- **DeviceGroup**: Hierarchical grouping of devices.
- **DeviceManager**: Central controller for CRUD operations, selection, and persistence.

See `DEVICE_MANAGEMENT.md` for detailed workflows and `MULTI_DEVICE_OPERATIONS.md` for bulk operations.

### Workspaces

Workspaces isolate device collections, enabled plugins, and UI layouts.
- Workspace metadata and layout state are stored under `config/workspaces/`.
- A workspace can be opened, created, or deleted from the UI.

See `workspaces.md` for structure details and usage.

### Autosave and Backups

Autosave protects against data loss and creates optional backups.
- Configurable in the Settings dialog.
- Backups are stored under `data/backups/` by default.

See `autosave.md` for configuration and behavior details.

### Configuration

Configuration is layered:
1. `config/default.yaml` (base defaults)
2. `config/plugins.yaml` (plugin-provided overrides)
3. `config/user.yaml` (user overrides)

The `Config` service exposes `get`, `set`, and plugin-specific configuration accessors for runtime use.

### Logging and Diagnostics

NetWORKS uses structured logging (Loguru) to capture operational events.
- Logs are stored under `logs/`.
- Use `INSTALLATION_TROUBLESHOOTING.md` for diagnostics workflows.

## Data and Storage Layout

Key directories:
- `config/`: Application and plugin configuration.
  - `default.yaml`, `user.yaml`, `plugins.yaml`
  - `plugins.json`: Plugin registry state
  - `workspaces/`: Workspace metadata and UI layout
- `data/`: Runtime data, downloads, screenshots, and backups.
  - `backups/`, `downloads/`, `screenshots/`, `workspaces/`
- `logs/`: Application log files
- `plugins/`: External plugins loaded at runtime
- `src/`: Core application and UI modules
- `scripts/`: Diagnostic and helper scripts

Plugins may store data within their own directories (for example, `plugins/command_manager/data/`).

## Plugin System Architecture

Plugins are the primary extension mechanism. The system supports:
- **Discovery** in internal and external plugin directories
- **Lifecycle**: discover → enable → load → initialize → run → cleanup
- **UI Integration**: menu items, toolbar actions, dock widgets, and device panels
- **Device Extensions**: custom properties, device operations, discovery actions

Key types:
- `PluginManager`: Discovers and controls plugin lifecycle.
- `PluginInterface`: Base class for plugins.
- `PluginInfo`: Metadata and runtime state for each plugin.

Plugin documentation is expected to live inside each plugin directory (`README.md`, `API.md`, and optional additional docs). The documentation hub automatically loads plugin docs when a plugin is loaded.

See `docs/plugins/README.md` and `docs/plugins/manifest.md` for plugin development requirements.

## Scripts and Packaging

Operational scripts:
- `setup.bat`: Environment setup.
- `Start_NetWORKS.bat`: Primary launcher.
- `repair_installation.bat`: Repair and dependency recovery.
- `scripts/`: Helper scripts like dependency checks and plugin tests.

Local-only scripts (gitignored):
- `scripts/local/`: Local build/test helpers for release validation.

Packaging:
- See `packaging/windows_exe.md` for Windows packaging instructions.

## Security Considerations

NetWORKS itself does not store credentials in plaintext. Plugins that handle credentials (for example, Command Manager) encrypt sensitive values before storage and should document their data handling in their own docs.

## Related Documentation

- `GETTING_STARTED.md`
- `DEVICE_MANAGEMENT.md`
- `MULTI_DEVICE_OPERATIONS.md`
- `workspaces.md`
- `autosave.md`
- `INSTALLATION_TROUBLESHOOTING.md`
- `packaging/windows_exe.md`
