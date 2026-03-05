# Changelog

All notable changes to this project will be documented in this file.

## [0.12.13] - 2026-03-05
### Added
- Core: Initial pytest-based tests for update branch mapping and version comparison logic, and for plugin installer/download flows (including SHA-256 verification and catalog-driven plugin updates).

## [0.12.12] - 2026-02-14
### Changed
- **Network Scanner plugin** (v10.8): Removed splitter from dock; top group renamed to Scan Settings.
- **Network Scanner plugin** (v10.7): Results panel renamed to Logs; reduced margins and smaller text in logs area; removed separator between progress bar and logs.
- **Network Scanner plugin** (v10.6): Scan and Results panels use QGroupBox instead of CollapsibleSection.
- **SNMP Collector plugin** (v1.0.6): Trap Receiver config moved from dedicated tab to button in SNMP Poll tab; opens dialog.
- **SNMP Collector plugin** (v1.0.5): SNMP Poll adds preset OID dropdown (sysDescr, sysUpTime, sysName, etc.); Ingestion tab and dialog removed.
- Arrows: Centralized via get_arrow_color(); all arrows (dropdown, spin box, CollapsibleSection) use text_muted for consistent, theme-aware appearance in light and dark mode.
- QGroupBox: Reduced padding (4px 6px 2px, top bar +4) so groups fit content more tightly.
- QDockWidget (plugin_ui): Tab widget extends to dock edges—removed content padding and panel layout margins (SNMP, Syslog panels).
- QDockWidget: Content area border and padding removed so inner elements can fill the entire space; plugin_ui docks have no outer border.
- QDockWidget: Title bar shows 3-dot grip icon and tooltip "Drag the header to move or reorder this panel" to clarify draggability.
- QSplitter: Handle shows 3 dots in the center only (custom DotSplitterHandle); no border around handle.
- Controls (buttons, line edits, combos, spin boxes): Compact height (font_size+6) and reduced padding (2px vertical) to match tab header density.
- QTabWidget: Tab text centered and bottom-aligned; tabs sized to text (height font_size+4, padding 2px); tab font 1px smaller.
- QGroupBox: Removed checkable/expand-collapse support; use CollapsibleSection for expand/collapse sections.
- Theme tester: Light/Dark toggle now works (unpolish/polish all widgets, pass config to apply_theme). Added "Change Accent Color..." button. QCheckBox: checkmark symbol (stroke) instead of solid fill. QProgressBar/QSlider: themed (accent, surface_alt, border).
- Theme tester: Consolidated into single comprehensive UI (`scripts/test_grouping_panel_ui.py`) with all theme elements (buttons, inputs, groupbox, collapsible, tabs, table, tree, list, labels, progress, splitter, debug). Removed separate Grouping/Panels/Debug tabs and `test_arrows.py`. Each element has clear labels and debug hints.
- Tabs: QTabWidget::pane now has 8px padding so tab content is inset from pane edges; applies to core and plugin tab widgets. Added tab_content_padding to PLUGIN_UI_SIZES and plugin UI design doc.
- Panels: Dock content area now has full border (left, right, bottom) using theme border color; previously only border-top was set, so panels appeared borderless at sides and bottom.
- Panels: Dock header (QDockWidget::title) now has border on all sides so the title bar is fully outlined.
- Groups: CollapsibleSection container now has full border; QGroupBox and CollapsibleSection headers use theme border color for consistent outline.
- Groups: QGroupBox::title uses qlineargradient background for left/right border effect (Qt does not render border-left/right on padded subcontrol); border-top and border-bottom remain explicit.
- Theme: Merged plugin UI stylesheet into core `build_stylesheet()`; single theme file, no redundant append.
- Arrows: Use _draw_arrow_standalone in patched SpinBox/ComboBox—style can be QCommonStyle when stylesheet is active, so no longer rely on NetWORKSStyle._draw_arrow. Set NETWORKS_ARROW_DEBUG=1 for verbose arrow debug.

### Fixed
- QRadioButton: Indicator restored to circular shape (border-radius: 7px).
- QSlider: Top clipping fixed—added min-height 24px and padding 6px 0 so handle is fully visible.
- Spin box and ComboBox arrow buttons: Hover now uses surface_raised (was surface_alt) so buttons visibly highlight on hover; ComboBox::drop-down styled with hover/pressed states for consistent feedback.
- Dark theme: Dynamic switch when triggered from Settings—theme_changed signal, force unpolish/polish/update on all widgets; full palette for dark mode; CollapsibleSection refreshes arrow icons.
- Arrows: Unified geometry via _arrow_polygon_points; 4:3 aspect ratio; scale cap 0.85 for compact arrows; rounded center/points for proper alignment; ComboBox::drop-down full border.
- SpinBox: Remove white line between up/down buttons—margin-top: -1px on down-button overlaps gap; border-bottom/top: none at seam; use subControlRect for arrow placement.
- Spin box arrows: Draw via NetWORKSStyle.drawPrimitive (PE_IndicatorSpinUp/Down) instead of QSS image—base64 data URIs fail on Windows. Use theme tokens (text/text_disabled) for arrow color to ensure visibility on white. Larger arrow size (min 5px). Button width 18px, padding-right 24px to prevent white overlay.
- Spin box up/down buttons: Use full `border: 1px solid` on both buttons so they render with visible borders and clear separation on Windows (was border-left/border-bottom only, causing grey blob appearance).
- Spin box arrows: Patch QSpinBox/QDoubleSpinBox with paintEvent override; manual rect fallback when subControlRect fails; QSS ::up-arrow/::down-arrow image (SVG data URI) as backup. QComboBox::down-arrow uses same triangle style for consistency.

## [0.12.11] - 2026-02-13
### Added
- Quickstart dialog when no plugins are loaded: explains plugins, where to find them (Tools → Plugin Manager), how to configure, where docs are, and program overview (dockable widgets, device table, importing). Dismiss via Skip, "Don't show again" checkbox, or Open Plugin Manager. Setting in File → Settings → General to disable globally.

## [0.12.10] - 2026-02-13
### Changed
- Core release zip renamed to `NetWORKS-Core-<version>.zip` (was NetWORKS-Repo).
- Release Windows Zip: added `tag` input for manual runs on existing tags; explicit checkout ref for correct build source.
- Release-core: added `actions: write` permission so `gh workflow run` can trigger Release Windows Zip (fixes HTTP 403).

## [0.12.8] - 2026-02-13
### Added
- Plugin Manager: Install and Update dialogs now show the actual error message (e.g. HTTP 404, SHA-256 mismatch) instead of a generic "Failed to install" when plugin installation fails.
- Plugin installer: Detailed logging for download URL, HTTP status, SHA verification, extraction, and validation steps to aid troubleshooting.

### Changed
- **Release separation**: Core releases (v* tags) now contain only the core zip; plugin zips are published exclusively to the standalone "plugins" release. Users install plugins via Plugin Manager → Browse.
- Repository URL casing: Fixed netWORKS → NetWORKS in settings defaults, update checker, update manager, issue reporter, and documentation for correct GitHub API/release URLs.
- Docs: Updated versioning guide to clarify core vs. plugins release structure.
- Release: release-core now explicitly triggers release-windows via `gh workflow run` after pushing the tag (GitHub prevents GITHUB_TOKEN tag pushes from auto-triggering workflows).
- Buttons: height derived from font size (text height + 4px); matches QLineEdit/QComboBox when adjacent; apply_compact_button/apply_icon_button use get_control_height().
- Panels: clearer 2px borders on QDockWidget (core and plugin).
- Table headers: thinner—min-height row_height−2, padding 1px; applies to core and plugin themes.
- Buttons: vertically shrunk—min-height row_height+2 (was +6); plugin button_height 24.
- CollapsibleSection, tabs, table headers: much thinner—header derivation 2.4→2.0×font; tab/header padding 5→2px; collapsible header row_height-based; dock title padding reduced.
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