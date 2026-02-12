# Plugin Marketplace

The NetWORKS Plugin Manager includes a **Browse** tab that lets you discover, install, and update plugins from the plugin catalog without updating the core application.

## Browsing Plugins

1. Open **Tools → Plugin Manager** (or via the main menu).
2. Click the **Browse** tab.
3. The catalog lists available plugins with their status:
   - **Not installed** – Plugin is available for installation
   - **Installed** – Plugin is already installed
   - **Update available** – A newer version is available

4. Use the filter field to search by plugin name or ID.
5. Click **Refresh Catalog** to fetch the latest catalog from the server.

## Installing a Plugin

1. In the **Browse** tab, select a plugin with status **Not installed**.
2. Click **Install**.
3. Wait for the download and extraction to complete.
4. The plugin appears in the **Installed** tab. Load it from there if needed.

## Updating a Plugin

1. In the **Browse** tab, select a plugin with status **Update available**.
2. Click **Update**.
3. The plugin is overwritten with the new version. If it was loaded, it is reloaded automatically.

## Removing a Plugin

1. In the **Browse** tab, select a plugin with status **Installed** or **Update available**.
2. Click **Remove**.
3. Confirm the removal. The plugin files are deleted from disk.

## Configuration

- **Catalog URL**: Set `plugins.catalog_url` in config to use a custom catalog (e.g. a fork or alternate branch).
- **Cache TTL**: `plugins.catalog_cache_ttl_minutes` (default 60) controls how long the catalog is cached locally.
- **Startup check**: `plugins.check_for_updates_on_startup` (default true) checks for plugin updates when the app starts.

## Catalog Source

The catalog is loaded in this order:

1. **Remote URL** – Fetched from the configured catalog URL (default: raw GitHub from `general.repository_url`).
2. **Cache** – If the remote fetch fails, the last successfully loaded catalog is used (stored in `config/plugin_catalog_cache.json`).
3. **Local file** – If the remote fails and there is no cache, loads `plugin_catalog.json` from the project root (next to `manifest.json`). This supports local development and runs before the catalog has been pushed to GitHub.

## Troubleshooting

- **Catalog fails to load**: Check your network connection. The catalog URL may be blocked or the server may be unavailable. If the remote is not yet available (e.g. before first push), the catalog falls back to a local `plugin_catalog.json` in the project root. Run `python scripts/build_plugin_package.py --generate-catalog` to create it.
- **Install fails**: Ensure you have write permission to the plugins directory. Check logs for details.
- **Update not showing**: Click **Refresh Catalog** to force a fresh fetch.
