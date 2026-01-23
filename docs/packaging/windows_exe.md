# NetWORKS Portable EXE (Windows)

This guide explains the one-click portable build for NetWORKS.

## One-Click Build (Local-Only)

Local helper scripts are kept under `scripts/local/` and are gitignored for release builds.
If you maintain a local copy of `scripts/local/Build_Release.bat`, run it from the repo root.

## Manual Build

1. `python -m venv .venv_build`
2. `.\.venv_build\Scripts\activate`
3. `python -m pip install --upgrade pip`
4. `python -m pip install -r requirements.txt --no-cache-dir`
5. `python -m pip install "pyinstaller>=6.10.0" --no-cache-dir`
6. Run:
   ```
   pyinstaller ^
     --noconfirm ^
     --clean ^
     --onefile ^
     --name NetWORKS ^
     --noconsole ^
     --add-data "manifest.json;." ^
     --add-data "config;config" ^
     --add-data "plugins;plugins" ^
     --collect-all PySide6 ^
     --collect-all qtpy ^
     --collect-all qtawesome ^
     networks.py
   ```
7. `deactivate` and remove `.venv_build` when done

## Result

After a successful build, launch the app from:

`dist/NetWORKS.exe`

## Installer (Optional)

An installer is produced in CI using Inno Setup and allows users to choose an install location.
The installer places `NetWORKS.exe`, `config/`, `plugins/`, and `manifest.json` under the selected folder and creates shortcuts.

CI output:
- `dist/NetWORKS-Setup-<version>.exe`

## Notes

- The output folder is safe to copy to another Windows machine.
- Build artifacts are gitignored by default.

## GitHub Actions Release

The workflow `Release Windows EXE` builds and publishes a Windows zip when you push a tag:

1. Create a tag like `v1.0.0` and push it to GitHub.
2. The workflow builds `dist/NetWORKS-windows.zip`.
3. The zip is attached to the GitHub Release for that tag.

You can also run the workflow manually from the Actions tab to create a release:

- If you provide a version input, that version is used.
- If you leave it blank, the workflow uses `manifest.json` version.
