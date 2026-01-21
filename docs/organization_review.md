# NetWORKS Organization Review

This document records stability-focused findings and how the project is organized.

## Purpose

NetWORKS is an extensible device management application with workspaces, device storage, and a plugin system that adds UI panels, menu actions, and device operations.

## Plugin Behavior Summary

- Plugins are discovered from internal (`src/plugins`) and external (`plugins`) directories.
- Each plugin uses a manifest (`manifest.json`, `plugin.json`, or `plugin.yaml`) with an entry point.
- The plugin lifecycle is: discover → enable → load → initialize → run → cleanup.
- Plugins can register UI components (toolbars, menus, panels, dock widgets) and add device properties or operations.

## Stability Notes

- Startup requires a full dependency install; a one-click smoke test now validates this.
- Automated scripts avoid interactive prompts to prevent startup hangs.
- Configuration defaults use portable paths to avoid machine-specific breakage.
