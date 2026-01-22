# Workspaces

## Introduction

In NetWORKS, workspaces provide a way to organize and manage different sets of devices and their configurations. Each workspace maintains its own collection of devices, groups, and settings, allowing you to switch between different configurations easily.

## UI Layout Persistence

Workspaces now save and restore UI layouts, including:
- Main window size and position
- Dock widget positions and sizes
- Toolbar positions
- Plugin panel layouts

This means that each workspace can have its own custom UI arrangement tailored to specific use cases.

## Workspace Structure

Each workspace is stored in the `config/workspaces` directory with the following structure:

```
config/workspaces/
├── default/                   # Default workspace
│   ├── workspace.json         # Workspace metadata
│   ├── groups.json            # Group structure
│   └── devices/               # Device data per workspace
│       ├── <device-id>/
│       │   └── device.json
│       └── <device-id>/
│           └── device.json
└── production/                # Another workspace
    ├── workspace.json
    ├── groups.json
    └── devices/
```

Device data is stored inside each workspace under `devices/<device-id>/device.json`. This keeps workspaces fully self-contained for portability.

## Workspace File Format

### workspace.json

```json
{
  "name": "production",
  "description": "Production network devices",
  "created": "2023-11-14 10:00:00",
  "last_saved": "2023-11-14 15:30:45",
  "devices": [
    "920a4f34-c1bc-4504-9283-e20738a88203",
    "b5c12e8f-945a-4f2a-9b27-f12d89a24c67"
  ],
  "groups": [
    "All Devices",
    "Core Routers",
    "Edge Switches"
  ],
  "enabled_plugins": [
    "sample",
    "network_scanner",
    "device_backup"
  ]
}
```

## Workspace Operations

### Creating a Workspace

To create a new workspace:

1. Go to "File" → "Workspaces" → "New Workspace"
2. Enter a name and optional description
3. Click "Create"

A new workspace will be created with default settings and an empty device list. The UI layout of your current workspace will be copied to the new workspace as a starting point.

### Switching Workspaces

To switch to a different workspace:

1. Go to "File" → "Workspaces" → "Open Workspace"
2. Browse to a workspace folder in the file browser
3. Click "Open"

When switching workspaces, the UI layout will automatically change to match the saved layout for that workspace.

### Saving Workspace State

```python
device_manager.save_workspace()
```

### Listing Available Workspaces

```python
workspaces = device_manager.list_workspaces()
for workspace in workspaces:
    print(f"{workspace['name']} - {workspace.get('description', '')}")
```

### Deleting a Workspace

```python
workspace_name = "test"
device_manager.delete_workspace(workspace_name)
```

## Default Workspace

The "default" workspace is created automatically when the application starts for the first time. This workspace cannot be deleted.

## Best Practices

1. **Use descriptive names**: Choose workspace names that clearly indicate their purpose.
2. **Save often**: Call `save_workspace()` after making significant changes.
3. **Create workspaces for different environments**: For example, create separate workspaces for development, testing, and production environments.
4. **Document workspaces**: Use the description field to document the purpose and contents of each workspace.
5. **Share workspaces**: Copy workspace directories between installations to share configurations.
6. **Customize layouts per workspace**: Arrange UI elements differently based on the workspace's purpose. 