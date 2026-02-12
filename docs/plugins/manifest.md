# Plugin Manifest

Each NetWORKS plugin must include a manifest file that describes the plugin and its requirements. The manifest can be provided as `manifest.json`, `plugin.json`, or legacy `plugin.yaml` in the root directory of the plugin.

Plugins with valid manifests are automatically discovered by the build system and included in the [plugin catalog](marketplace.md). Users can install and update plugins from **Plugin Manager → Browse** without updating the core application.

## Required Fields

The following fields are required in every plugin manifest:

- `id`: A unique identifier for the plugin (lowercase letters, numbers, underscores, and hyphens only)
- `name`: The display name of the plugin
- `version`: The plugin version in semantic versioning format (X.Y.Z)
- `entry_point`: The main Python file that contains the plugin class

## Optional Fields

The following fields are optional but recommended:

- `description`: A description of the plugin's functionality
- `icon`: Path to the plugin icon (relative to the plugin root, stored in `resources/icons`)
- `author`: The plugin author (e.g. `chibashr`)
- `min_app_version`: The minimum NetWORKS version required
- `max_app_version`: The maximum NetWORKS version supported
- `dependencies`: A list of plugin dependencies
- `requirements`: Python package and system dependencies needed by the plugin
- `changelog`: A list of changes for each version

## Icon Specifications

Plugins that present UI must follow the application icon spec in
`docs/Design Considerations.md`. Keep icon assets in `resources/icons`.

**Sizes:**
- Toolbar: 24x24px
- Panel header: 16x16px
- Inline: 16x16px
- Status: 12x12px
- Large (dialogs): 32x32px
- Plugin icon: 48x48px minimum

**Style:**
- Material Icons (filled)
- Monochrome using theme text colors (black in light theme, white in dark theme)
- Minimal detail
- 2px stroke width when using outline variants
- SVG preferred

**Behavior:**
- Icon-only actions must include tooltips and aria-labels

## Example Manifest

```json
{
  "id": "sample",
  "name": "Sample Plugin",
  "version": "1.0.0",
  "description": "A sample plugin to demonstrate the plugin system",
  "icon": "resources/icons/sample.svg",
  "author": "chibashr",
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

NetWORKS performs lightweight validation of the manifest and plugin structure (required fields, entry point file, and an API.md warning). The JSON schema in `docs/plugins/manifest_schema.json` is a reference for authors, but it is not enforced at runtime.

## Legacy Support

For backward compatibility, NetWORKS also supports the older `plugin.yaml` format. However, it is recommended to use the JSON format for new plugins.

## Plugin Dependencies

The `dependencies` field specifies other plugins that must be enabled for this plugin to function. Dependencies can be a list of plugin IDs or objects that include:

- `id`: The plugin ID of the dependency
- `version`: The required version range (using npm-style version specifiers)

## Package Requirements

The `requirements` field specifies external dependencies needed by the plugin:

- `python`: A list of Python packages (in pip format) needed by the plugin
- `system`: A list of system/OS dependencies that may need to be manually installed

### Python Requirements

NetWORKS checks for missing Python requirements and warns during validation, but it does not install packages automatically. You can also provide a `requirements.txt` in the plugin directory to list additional packages.

### System Requirements

System requirements are external executables or libraries that must be installed on the operating system (e.g., `nmap`, `git`, `docker`). NetWORKS records these for visibility and warns if they are missing, but installation is handled manually.

## Changelog

The changelog is an array of version entries, each containing:

- `version`: The version string
- `date`: The release date in YYYY-MM-DD format
- `changes`: An array of strings describing the changes in this version

Maintaining a changelog helps users understand what has changed between versions and makes it easier to troubleshoot issues. 