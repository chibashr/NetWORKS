# NetWORKS Versioning Guide

## Overview

NetWORKS uses **separate versioning** for the core application and plugins:

- **Core program**: Semver (e.g. `0.12.3`) in `manifest.json`; auto-released when core changes are pushed to `stable`.
- **Plugins**: Independent versions in each plugin's `manifest.json`; auto-released when `plugins/**` changes on `stable`.

## Core Program Versioning

### Automatic Release (Push to Stable)

1. Merge or push changes to the `stable` branch.
2. Ensure changes touch core paths (not only `plugins/**`).
3. GitHub Actions (`release-core.yml`) will:
   - Bump the patch version (e.g. 0.12.3 → 0.12.4)
   - Update `manifest.json` and `CHANGELOG.md`
   - Create and push a version tag
   - Trigger `Release Windows Zip` to build and publish a GitHub Release

### Manual Version Bump

To bump minor or major:

1. Go to **Actions** → **Release Core** → **Run workflow**.
2. Select the `stable` branch.
3. Choose `minor` or `major` in the **bump_type** input.
4. Run workflow.

### Required Updates Before Release

- **CHANGELOG.md**: Add entries under `## [Unreleased]` or create a new version section. The bump script converts `[Unreleased]` to the new version with today's date.
- **manifest.json**: Updated automatically by the workflow.

### Version Fields in manifest.json

| Field | Purpose |
|-------|---------|
| `version` | Main version string (e.g. "0.12.4") |
| `version_string` | Display version (same as version) |
| `version_info` | Parsed major/minor/patch/build |
| `build_date` | Set at release time |
| `release_notes` | Extracted from CHANGELOG or default |

## Plugin Versioning

See [docs/plugins/publishing.md](../plugins/publishing.md) for plugin release flow.

## Release Workflows Summary

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| release-core.yml | Push to stable (core paths) | Bump version, tag, trigger build |
| release-windows.yml | Push tag v* | Build zip, create GitHub Release |
| release-plugins.yml | Push to stable (plugins/**) | Build and publish plugin packages |

## CHANGELOG Conventions

Use `[Unreleased]` for work in progress:

```markdown
## [Unreleased]
### Added
- Your new features here

### Fixed
- Bug fixes

## [0.12.4] - 2026-02-11
...
```

The bump script converts `[Unreleased]` to `[X.Y.Z]` with the release date when creating a new version.
