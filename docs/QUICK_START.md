# NetWORKS - Quick Start

Get NetWORKS running and add your first devices in a few minutes.

## Install and Run

### Windows

1. Run `Start_NetWORKS.bat` from the application directory.
2. On first run, the script may create a virtual environment and install dependencies; wait for it to finish, then the application will start.

### Other platforms (manual setup)

1. Create a virtual environment: `python -m venv venv`
2. Activate it:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the application: `python networks.py`

## Quickstart (When No Plugins Loaded)

If you open a workspace with no plugins loaded, a quickstart dialog appears explaining the program, where to find plugins, how to configure them, and where documentation lives. You can dismiss it with **Skip**, check **Don't show again** to disable it, or click **Open Plugin Manager** to open the Plugin Manager. To disable the quickstart globally, go to **File → Settings → General** and uncheck **Show quickstart when no plugins are loaded**.

## Main Window

When NetWORKS starts, you'll see:

1. **Toolbar**: Quick access to common actions
2. **Device Tree** (left panel): Hierarchical view of devices and groups with search and quick actions
3. **Device Table** (center): List of devices with their properties
4. **Properties Panel** (right panel): Details of selected devices
5. **Log Panel** (bottom panel): Activity log

## First Steps

1. **Create a device** — Click "New Device" in the toolbar or use **File → New Device**. Enter a name and any properties you need.

2. **Optional: Create a group** — Use **File → New Group** or the toolbar, then drag the device into the group in the device tree to organize it.

3. **Alternative: Import many devices** — Use **File → Import Devices…** or the Import toolbar button. Choose a CSV or text file (or paste data), configure the delimiter and header, map columns to device properties, then finish. See [Device Management](DEVICE_MANAGEMENT.md) for details.

4. **Save** — Click Save in the toolbar or **File → Save**. Your workspace is also autosaved when you exit.

## Next

- [Getting Started](GETTING_STARTED.md) — Full guide: devices, groups, updates, plugins
- [Device Management](DEVICE_MANAGEMENT.md) — Groups and importing
- [Documentation Index](index.md) — All documentation
