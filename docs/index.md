# NetWORKS Documentation

Welcome to the NetWORKS documentation. This index provides a complete map of the guides, references, and plugin documentation that describe the platform.

## Table of Contents

### User Documentation

- [Quick Start](QUICK_START.md) - Short path for first-time users
- [Getting Started](GETTING_STARTED.md) - First steps with NetWORKS
- [Device Management](DEVICE_MANAGEMENT.md) - Devices, groups, and importing
- [Multi-Device Operations](MULTI_DEVICE_OPERATIONS.md) - Bulk selection workflows
- [Workspaces](workspaces.md) - Workspace structure and layout persistence
- [Autosave and Backups](autosave.md) - Autosave configuration and backups
- [Installation and Troubleshooting](INSTALLATION_TROUBLESHOOTING.md)

### Program Reference

- [Program Reference](PROGRAM_REFERENCE.md) - End-to-end architecture and data layout
- [Development Guide](DEVELOPMENT.md) - Development practices and plugin lifecycle

### API Documentation

- [API Overview](API.md)
- [Core API](api/core.md)
- [UI API](api/ui.md)
- [Signals](api/signals.md)
- [API Documentation Guidelines](api/README.md)

### Plugin Documentation

- [Plugin Development Guide](plugins/README.md)
- [Plugin Manifest Schema](plugins/manifest.md)
- [Plugin Context Menu Integration](plugins/context_menu_integration.md)
- [Plugin Device Creation](plugins/device_creation.md)

Plugin-specific documentation is stored inside each plugin directory (for example, `plugins/network_scanner/README.md` and `plugins/network_scanner/API.md`). The documentation hub loads these dynamically when the plugin is loaded.

## Documentation Structure

The NetWORKS documentation is organized into several key areas:

```
NetWORKS/
├── docs/                   # Documentation hub
│   ├── index.md            # Documentation index
│   ├── PROGRAM_REFERENCE.md
│   ├── GETTING_STARTED.md
│   ├── DEVICE_MANAGEMENT.md
│   ├── MULTI_DEVICE_OPERATIONS.md
│   ├── workspaces.md
│   ├── autosave.md
│   ├── INSTALLATION_TROUBLESHOOTING.md
│   ├── api/                # API documentation
│   └── plugins/            # Plugin development docs
│
├── plugins/                # External plugins with their docs
│   ├── network_scanner/
│   │   ├── README.md
│   │   └── API.md
│   └── command_manager/
│       ├── README.md
│       └── API.md
│
└── src/                    # Source code
    ├── core/
    ├── ui/
    └── ...
```

## Using This Documentation

- **New users**: Start with `GETTING_STARTED.md`
- **Operators**: Use `DEVICE_MANAGEMENT.md`, `MULTI_DEVICE_OPERATIONS.md`, and `workspaces.md`
- **Plugin developers**: Use `plugins/README.md` and plugin-specific docs
- **Core developers**: Use `PROGRAM_REFERENCE.md` and `DEVELOPMENT.md`
- **API users**: Use `API.md`, `api/core.md`, and `api/ui.md`

## Contributing to Documentation

Documentation improvements are always welcome. If you find areas that need clarification or expansion:

1. Update the relevant documentation file within `docs/` or the plugin folder.
2. Follow the [API Documentation Guidelines](api/README.md).
3. Keep examples aligned with current APIs and UI behavior.