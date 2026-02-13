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

1. Push to `stable` (core changes) — release-core bumps version, creates tag, and triggers this workflow.
2. The workflow builds the core zip (`NetWORKS-Core-<version>.zip`) and attaches it to the GitHub Release.
3. Plugins are published separately via the `plugins` release (see [versioning.md](versioning.md)).

You can also run the workflow manually from the Actions tab:

- **tag**: Set to an existing tag (e.g. `v0.12.9`) to build and publish a release for that tag.
- **version**: Optional; defaults to manifest or derived from tag.

For auto-release on push to stable, see [versioning.md](versioning.md).
