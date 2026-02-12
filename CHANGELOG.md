# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- CollapsibleSection: sharp full-width blocks, centered headers, arrow far right; extends to vertical panel limits; use `PLUGIN_UI_SIZES["collapsible_stack_spacing"]` and `addStretch()` when stacking sections.

### Changed
- QGroupBox: integrated header layout (Option E)—full-width header bar, no left notch, symmetric padding; header height derived from font_size for dynamic text fitting.
- QGroupBox titles: full-width bar, centered text, 4pt smaller font (min 6pt), uppercase; extra padding-top prevents content overlap; compact bar height derived from font size.
- Section headers now scale with configured font size; `_derive_header_height(font_size)` in theme.py.

### Fixed
- QGroupBox full-width titles: large padding workaround (Qt cannot set ::title width); titles centered, uppercase. Reverted StyledGroupBox custom widget due to layout/setLayout compatibility issues with QVBoxLayout(group) pattern.
- Theme consistency: QSplitter handles and QGroupBox titles now use theme border colors; workspace selector and panels have complete side borders.
- CollapsibleSection: bottom border now correctly appears when collapsed (header repolish on toggle).
- Dark/light mode: replaced hardcoded colors in device details panel, splash screen, plugin manager, and documentation dialog with theme tokens for consistent appearance.
- Spin box styling: QSpinBox/QDoubleSpinBox input field now uses theme background (surface_raised) instead of black; arrow buttons use theme colors with proper contrast; arrows visible in both light and dark modes.
- QGroupBox styling modernized: full-width header bars, continuous vertical stacking with collapsed borders, optional expand/collapse indicator for checkable group boxes.
- Tab controls for stacked/tabbed dock panels now appear at the top instead of the bottom.
- Version references now dynamic from manifest: splash screen, plugin catalog client fallback, and update dialog test block no longer hardcode version strings.
- **SNMP Collector plugin**: Trap receiver now compatible with both etingof pysnmp (camelCase API) and pysnmp-lextudio (snake_case API); fixes `'UdpAsyncioTransport' object has no attribute 'open_server_mode'` when using etingof pysnmp.

## [0.12.5] - 2026-02-12

### Changed
- Version bump to 0.12.5


## [0.12.4] - 2026-02-11

### Added
- **SNMP Collector plugin**: Collects SNMP traps, supports SNMP polling (GET/GETNEXT), and ingestion for testing. Trap receiver on configurable port (default 1162), SNMP poll for device testing, and JSON ingestion to simulate traps.

## [0.12.3] - 2026-02-12

### Added
- **Plugin Marketplace**: Browse tab in Plugin Manager to discover, install, and update plugins from the catalog without core app updates.
- Build script `scripts/build_plugin_package.py` for dynamic plugin packaging and catalog generation.
- GitHub workflow `release-plugins.yml` for automated plugin releases on push to `plugins/**`.
- Config keys: `plugins.catalog_url`, `plugins.catalog_cache_ttl_minutes`, `plugins.check_for_updates_on_startup`.
- Documentation: `docs/plugins/marketplace.md`, `docs/plugins/publishing.md`, `docs/plugins/catalog_schema.json`.

### Changed
- Version bump to 0.12.3

## [0.12.2] - 2026-02-10

### Changed
- Version bump to 0.12.2

## [0.12.1] - 2026-02-10

### Changed
- Version bump to 0.12.1

## [0.12.0] - 2026-01-29

### Changed
- Version bump to 0.12.0

## [0.11.5] - 2026-01-28

### Fixed
- Plugin persistence: loaded plugins for a workspace are now correctly saved on application close and restored when opening the same workspace in a later session. Previously, the workspace was saved again during plugin unload, overwriting `loaded_plugins` with an empty list; shutdown now persists the loaded plugin list once before unloading and skips further workspace saves during close.

### Changed
- Version bump to 0.11.5

## [0.11.4] - 2026-01-28

### Added
- Command Manager: `run_command_set(devices, command_set=..., show_progress=True)` API to run a command set on devices without opening the dialog; used by Template Manager to apply templates.
- Template Manager: **Run template on selected devices** (panel) runs the current template on device-table selection via Command Manager.
- Template Manager: **Send to Command Manager and run** in Export dialog runs the first template on scope/filter-resolved devices.
- Template Manager: **Run in Command Manager** in Batch export dialog runs the first template on batch-resolved devices.

### Changed
- Command Manager and Template Manager integrate via `run_command_set` only; both plugins remain independent.
- Command Manager API.md documents `run_command_set` and `add_command_set(..., temporary=True)`.
- Template Manager API.md documents Run template on selected devices, Send to Command Manager and run, and Run in Command Manager flows.

## [0.11.3] - 2026-01-28

### Changed
- Version bump to 0.11.3
- Settings menu: moved from Tools to File; fixed duplicate Settings entry on same line

## [11.2] - 2026-01-27

### Changed
- Version bump to 11.2

## [0.11.1] - 2026-01-27

### Added
- Properties panel: right-click context menu **Edit Value...** when exactly one device is selected; opens a dialog to edit that property (strings, numbers, bools, lists as comma-separated, long text via multiline editor).

### Changed
- Version bump to 0.11.1

## [0.11.0] - 2026-01-27

### Changed
- Version bump to 0.11.0

## [0.10.6] - 2026-01-27

### Changed
- Version bump to 0.10.6
- Updater: Stable channel now uses GitHub Releases API for latest release; Beta/Alpha/Development use branch manifest
- Updater: Update dialog adds **View on GitHub**; error and manual-update dialogs add **Open in Browser**
- Updater: Completion handling uses thread signal only to avoid duplicate dialogs
- Config key for startup update check aligned to `general.check_for_updates` (was `general.check_updates` in code)

### Fixed
- Updater: Correct config key so “Check for updates on startup” is respected in Settings and at startup
- Updater: Clearer handling when Releases API returns 404 (fallback to stable branch manifest)

## [0.10.5] - 2026-01-26

### Changed
- Update system now always creates a backup of local files before overwriting them
- Local files are automatically backed up to `backups/` directory with timestamp before any update
- Git initialization and updates now always overwrite local files after backing them up
- Removed stashing behavior - updates now use hard reset to always match remote

### Fixed
- Fixed shutdown errors: improved signal disconnection handling, added guards for Qt object access during shutdown, and fixed recursive errors in device tree model

## [0.10.4] - 2026-01-26

### Fixed
- Fixed RuntimeWarning errors when disconnecting plugin signals during shutdown
- Fixed recursive errors in device tree model when accessing Qt objects during shutdown
- Fixed errors in scalable toolbar when accessing deleted Qt objects during shutdown
- Improved signal disconnection by checking if signals are connected before disconnecting
- Added shutdown guards to prevent accessing invalid Qt objects

## [0.10.3] - 2026-01-26

### Changed
- Redesigned device table filter UI with simplified single-line layout
- Search bar and group selector now on the same line (search on left, group selector on right)
- Removed advanced filter and deduplication buttons from filter toolbar (still available via context menu)

### Fixed
- Improved filter UI consistency and usability

## [0.10.0] - 2026-01-22

### Added
- Report Generator plugin with table and template report modes.
- Report exports in HTML, JSON, CSV, and TXT formats.
- Per-workspace report storage for generated report definitions.

## [0.9.0] - 2025-05-29

### Added
- Enhanced property panel with separate sections for core, plugin, and custom properties
- Added property naming convention for plugins (using plugin_id: prefix)
- Updated documentation with property naming guidelines for plugin developers

### Changed
- Improved property value display formatting for complex data types
- Updated core UI components to use the latest PySide6 features

### Fixed
- Fixed issue with device property filter not working with complex property values

## [0.8.54] - 2025-05-15

### Added
- Enhanced property details viewer with multiple view modes
- Added tabular data representation for structured data
- New JSON syntax highlighting in property details 