# Changelog

All notable changes to this project will be documented in this file.

## [0.11.0] - 2026-01-27

### Changed
- Version bump to 0.11.0

## [0.10.6] - 2026-01-27

### Changed
- Version bump to 0.10.6

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