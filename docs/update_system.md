# Update System

NetWORKS uses a GitHub-based updater that supports both automatic (git) updates and manual download via the **View on GitHub** / **Open in Browser** actions.

## Behavior

- **Stable channel**: Update check uses the [GitHub Releases API](https://docs.github.com/en/rest/releases) (`/repos/{owner}/{repo}/releases/latest`) to get the latest published release. Version and release notes come from the API; if the tag is not version-like, the manifest is fetched from that tag.
- **Beta / Alpha / Development**: Update check fetches `manifest.json` from the branch (`/raw/{branch}/manifest.json`).
- **Applying updates**: When the user clicks **Update Now**, the app uses Git (fetch + reset to `origin/{branch}`). If the install is not a git repo, the user is prompted to initialize it; backups are created before any overwrite.

## Configuration

| Key | Purpose |
|-----|---------|
| `general.check_for_updates` | Whether to check for updates on startup (default: true). |
| `general.update_channel` | `Stable`, `Beta`, `Alpha`, or `Development`. |
| `general.repository_url` | GitHub repo URL (e.g. `https://github.com/owner/repo`). |
| `update.git_remote_url` | Alternative Git remote URL; falls back to `general.repository_url` if unset. |
| `general.skipped_version` | Version string that was skipped via **Skip This Version** (no prompt for that version). |

## Interactive behavior

- **Update Available** dialog: **Update Now**, **View on GitHub**, **Remind Me Later**, **Skip This Version**.
- **View on GitHub** opens the repo’s releases page (Stable) or branch tree (other channels) in the default browser.
- **Manual update** (e.g. when Git is not used): **Manual Update Required** and **Update Error** / **Update Failed** dialogs offer **Open in Browser** to go to the same URL.

## Components

- `src/core/update_checker.py`: Checks for updates (Releases API for Stable, branch manifest for others); emits `update_available` and `check_complete`.
- `src/core/update_manager.py`: Git-based apply (init, fetch, reset, backup).
- `src/ui/update_dialog.py`: Update-available dialog and progress/error handling with **View on GitHub** / **Open in Browser**.
