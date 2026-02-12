# Publishing Plugins to the Catalog

This guide explains how to publish your plugin to the NetWORKS plugin catalog.

## Prerequisites

- Your plugin is in the `plugins/` directory of the NetWORKS repository (or a fork).
- The plugin has a valid `manifest.json` (or `plugin.json`/`plugin.yaml`) with required fields: `id`, `name`, `version`, `entry_point`.

## Automatic Publishing

The catalog is **fully automatic**. No manual steps are required.

1. Add your plugin directory under `plugins/{plugin_id}/`.
2. Ensure `manifest.json` exists with at least: `id`, `name`, `version`, `entry_point`, `description`, `author`.
3. Push to the `stable` branch (or the branch configured for the workflow).

When you push changes under `plugins/**`, the `release-plugins` GitHub workflow:

1. Scans `plugins/` for all plugin directories
2. Builds each plugin into a ZIP (`dist/plugins/{id}-{version}.zip`)
3. Creates/updates the `plugins` release with all ZIPs
4. Generates `plugin_catalog.json` with one entry per plugin
5. Commits the catalog to the repository

## Manifest Requirements

Your manifest must include:

- `id`: Unique plugin identifier (lowercase, alphanumeric, underscores)
- `name`: Display name
- `version`: Version string (e.g. `1.0.0` or `10.5`)
- `entry_point`: Python file that contains the plugin class
- `description`: Short description
- `author`: Author name

Optional but recommended:

- `min_app_version`: Minimum NetWORKS version required
- `changelog`: Array of `{version, date, changes}` entries
- `icon`: Path to plugin icon (e.g. `resources/icons/plugin_id.svg`)

## Packaging Exclusions

The build script excludes from the ZIP:

- `__pycache__`, `*.pyc`, `*.pyo`
- `.git`, `.gitignore`
- `.coveragerc`, `pytest.ini`, `requirements-dev.txt`
- `*.md` except `API.md`

## Adding a New Plugin

1. Create `plugins/my_plugin/` with your plugin files.
2. Add `manifest.json` with required fields.
3. Push to `stable`.
4. The workflow runs automatically. Within a few minutes, your plugin appears in the catalog.
5. Users can then install it via **Plugin Manager → Browse**.

## Version Updates

To publish an update:

1. Edit your plugin as needed.
2. Bump `version` in `manifest.json`.
3. Push to `stable`.
4. The workflow rebuilds and updates the catalog. Users see **Update available** when they refresh the catalog.

## Local Development

For local development or before the catalog exists on GitHub, the Browse tab falls back to `plugin_catalog.json` in the project root. Generate it with:

```bash
python scripts/build_plugin_package.py --generate-catalog
```

This creates or updates `plugin_catalog.json` from the current `plugins/` directory. The Plugin Manager will use it when the remote catalog is unavailable (e.g. 404).
