# NetWORKS Documentation Hub

Welcome to the NetWORKS documentation hub. This directory contains the authoritative documentation for the platform and serves as the source for the in-app documentation browser.

## Documentation Structure

The documentation is organized into:
- **User guides**: Getting started, device management, workspaces, autosave.
- **Program reference**: Architecture, data layout, and core systems.
- **API reference**: Core, UI, and signals for plugin developers.
- **Plugin development**: Manifest, extension points, and best practices.

Use `index.md` as the master entry point.

## Documentation Index

Start with the [Documentation Index](index.md) for a complete overview of all available documentation.

## Quick Links

- [Core API Documentation](api/core.md)
- [UI API Documentation](api/ui.md)
- [Plugin Development Guide](plugins/README.md)
- [Program Reference](PROGRAM_REFERENCE.md)
- [Getting Started](GETTING_STARTED.md)
- [Development Guide](DEVELOPMENT.md)

## Plugin Documentation in the Hub

Plugin documentation is stored in each plugin folder (for example, `plugins/network_scanner/README.md`). The in-app documentation hub loads plugin docs dynamically when a plugin is loaded, so the hub always reflects the active plugin set.

## Contributing to Documentation

Documentation is a critical part of the NetWORKS platform. If you find areas that need improvement, please consider contributing updates.

### Documentation Guidelines

1. Use Markdown format for all documentation
2. Follow the established structure and naming conventions
3. Include examples where appropriate
4. Keep documentation up-to-date with code changes
5. Follow the [API Documentation Guidelines](api/README.md) for API documentation

## Other Resources

- [Sample Plugin](../plugins/sample/API.md): Example of a well-documented plugin
- [Main Project README](../README.md): Overview of the project