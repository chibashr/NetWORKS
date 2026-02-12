# NetWORKS Release Zip (Windows)

This guide explains the release zip for NetWORKS.

## One-Click Build (Local-Only)

Local helper scripts are kept under `scripts/local/` and are gitignored for release builds.
If you maintain a local copy of `scripts/local/Build_Release.bat`, run it from the repo root.

## Local Run

1. Unzip the release to a folder of your choice.
2. Run `Start_NetWORKS.bat` to start the app.

## Result

The release zip contains the top-level `NetWORKS` folder.

## Notes

- The output folder is safe to copy to another Windows machine.
- Build artifacts are gitignored by default.
- The release zip contains source files and uses `Start_NetWORKS.bat` to manage setup.

## GitHub Actions Release

The workflow `Release Windows Zip` builds and publishes when you push a tag:

1. Create a tag like `v1.0.0` and push it to GitHub.
2. The workflow builds the core zip (`NetWORKS-Repo-<version>.zip`) and plugin zips.
3. Both are attached to the same GitHub Release as separate downloadable assets.

You can also run the workflow manually from the Actions tab to create a release:

- If you provide a version input, that version is used.
- If you leave it blank, the workflow uses `manifest.json` version.

For auto-release on push to stable, see [versioning.md](versioning.md).
