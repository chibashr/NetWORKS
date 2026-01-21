# Plugin Manifest

Each NetWORKS plugin must include a manifest file that describes the plugin and its requirements. The manifest can be provided as either a `manifest.json` or a `plugin.json` file in the root directory of the plugin.

## Required Fields

The following fields are required in every plugin manifest:

- `id`: A unique identifier for the plugin (lowercase letters, numbers, underscores, and hyphens only)
- `name`: The display name of the plugin
- `version`: The plugin version in semantic versioning format (X.Y.Z)
- `entry_point`: The main Python file that contains the plugin class

## Optional Fields

The following fields are optional but recommended:

- `description`: A description of the plugin's functionality
- `author`: The plugin author or organization
- `min_app_version`: The minimum NetWORKS version required
- `max_app_version`: The maximum NetWORKS version supported
- `dependencies`: A list of plugin dependencies
- `requirements`: Python package and system dependencies needed by the plugin
- `changelog`: A list of changes for each version

## Example Manifest

```json
{
  "id": "sample",
  "name": "Sample Plugin",
  "version": "1.0.0",
  "description": "A sample plugin to demonstrate the plugin system",
  "author": "NetWORKS Team",
  "entry_point": "sample_plugin.py",
  "min_app_version": "0.2.0",
  "dependencies": [
    {
      "id": "core",
      "version": ">=1.0.0"
    }
  ],
  "requirements": {
    "python": [
      "requests>=2.28.0",
      "beautifulsoup4>=4.11.0"
    ],
    "system": [
      "nmap (for network scanning functionality)"
    ]
  },
  "changelog": [
    {
      "version": "1.0.0",
      "date": "2023-11-14",
      "changes": [
        "Initial release"
      ]
    }
  ]
}
```

## Validation

NetWORKS validates plugin manifests against a JSON schema to ensure they contain all required fields and follow the correct format. The schema is available at `docs/plugins/manifest_schema.json`.

## Legacy Support

For backward compatibility, NetWORKS also supports the older `plugin.yaml` format. However, it is recommended to use the JSON format for new plugins.

## Plugin Dependencies

The `dependencies` field specifies other plugins that must be enabled for this plugin to function. Each dependency includes:

- `id`: The plugin ID of the dependency
- `version`: The required version range (using npm-style version specifiers)

## Package Requirements

The `requirements` field specifies external dependencies needed by the plugin:

- `python`: A list of Python packages (in pip format) that will be automatically installed
- `system`: A list of system/OS dependencies that may need to be manually installed

### Python Requirements

NetWORKS will automatically install Python package requirements when the plugin is enabled and remove them when the plugin is uninstalled, ensuring clean system management.

### System Requirements

System requirements are external executables or libraries that must be installed on the operating system (e.g., `nmap`, `git`, `docker`). NetWORKS provides an **automatic installation assistant** for system dependencies:

#### Automatic System Dependency Installation

When you enable a plugin that requires system dependencies, NetWORKS will:

1. **Check Availability**: Automatically check if the required system dependencies are installed and available in your system PATH
2. **Offer Installation**: If dependencies are missing, show a dialog with platform-specific installation options:
   - **Windows**: Opens download page for installers (e.g., nmap.org for nmap)
   - **macOS**: Offers to install via Homebrew (e.g., `brew install nmap`)
   - **Linux**: Detects your package manager and offers installation (apt, yum, dnf, pacman, zypper)
3. **Verify Installation**: After installation, automatically re-checks to verify the dependency is now available
4. **Graceful Degradation**: The plugin will still enable even if dependencies are missing, but features requiring those dependencies will be disabled with helpful messages

#### Supported System Dependencies

Currently, the following system dependencies are automatically detected and can be installed:

- **nmap**: Network scanning tool (used by Network Scanner plugin)
  - Windows: Opens nmap.org download page
  - macOS: Runs `brew install nmap`
  - Linux: Runs appropriate package manager command

Additional system dependencies can be added to the core installer as needed. The system is extensible and can be enhanced to support more dependencies in the future.

#### Example: Network Scanner Plugin

The Network Scanner plugin requires `nmap` as a system dependency. When you enable it:

1. NetWORKS checks if `nmap` is installed
2. If missing, shows an installation dialog with platform-specific options
3. After installation, verifies `nmap` is available
4. Plugin enables successfully with full functionality

#### Manual Installation

You can always install system dependencies manually if you prefer:

- **Windows**: Download and install from the official website
- **macOS**: Use Homebrew: `brew install <package>`
- **Linux**: Use your distribution's package manager: `sudo apt install <package>` (or equivalent)

After manual installation, restart NetWORKS for the changes to take effect.

## Changelog

The changelog is an array of version entries, each containing:

- `version`: The version string
- `date`: The release date in YYYY-MM-DD format
- `changes`: An array of strings describing the changes in this version

Maintaining a changelog helps users understand what has changed between versions and makes it easier to troubleshoot issues. 