# Network Scanner Plugin API

Available from **Plugin Manager → Browse**.

## Overview

The Network Scanner plugin provides capabilities to discover devices on a network using nmap and add them to the NetWORKS device inventory. It supports various scanning options and can be integrated with other plugins.

## Features

- Scan networks using nmap's powerful scanning capabilities
- Detect devices, their operating systems, and open ports
- Add discovered devices to the NetWORKS device inventory
- Scan specific IP ranges, subnets, or individual devices
- Select network interfaces for scanning
- Use different scan types with configurable options
- Elevated permission scanning for more accurate results
- Custom nmap arguments for advanced users
- Create and manage custom scan profiles
- Edit scan profiles directly from the scan dialog
- Batch scan selected devices with per-device progress
- Enumerate network interfaces via psutil-only detection

## Public API

### Methods

#### `scan_network(network_range, scan_type="quick")`

Start a network scan of the specified range.

**Parameters:**
- `network_range` (str): The network range to scan (e.g., "192.168.1.0/24", "10.0.0.1-10.0.0.254", or a single IP)
- `scan_type` (str): The type of scan to perform ("quick", "standard", "comprehensive", or a custom profile name)

**Returns:**
- `bool`: True if the scan started successfully, False otherwise

**Example:**
```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Scan a network range
success = scanner_plugin.scan_network("192.168.1.0/24", "standard")
```

#### `stop_scan()`

Stop the currently running scan.

**Returns:**
- `bool`: True if the scan was stopped successfully, False otherwise

**Example:**
```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Stop the current scan
scanner_plugin.stop_scan()
```

#### `is_scanning()`

Check if a scan is currently in progress.

**Returns:**
- `bool`: True if a scan is in progress, False otherwise

**Example:**
```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Check if a scan is in progress
if scanner_plugin.is_scanning():
    print("Scan in progress")
```

#### `get_scan_results()`

Get the results of the most recent scan.

**Returns:**
- `dict`: A dictionary containing scan results

**Example:**
```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Get scan results
results = scanner_plugin.get_scan_results()
print(f"Devices found: {results.get('devices_found', 0)}")
```

#### `get_scan_profiles()`

Get the list of available scan profiles.

**Returns:**
- `dict`: A dictionary containing scan profile configurations

**Example:**
```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Get scan profiles
profiles = scanner_plugin.get_scan_profiles()
print(f"Available profiles: {list(profiles.keys())}")
```

#### `create_scan_profile(name, config)`

Create a new scan profile. Scan behavior (including OS detection and port scanning) is defined only by the profile’s `arguments` and `timeout`; there are no separate "os_detection" or "port_scan" flags.

**Parameters:**
- `name` (str): The profile ID (e.g. used in scan_type choices)
- `config` (dict): Profile data with keys: `name` (display name), `description` (optional), `arguments` (nmap arguments, e.g. `-sn -F` or `-sV -p 22,80,443`), `timeout` (seconds, 30–600)

**Returns:**
- `bool`: True if the profile was created successfully, False otherwise

**Example:**
```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Create a new scan profile (real schema)
profile_config = {
    "name": "Web server scan",
    "description": "Ports 22, 80, 443 with version detection",
    "arguments": "-sV -p 22,80,443",
    "timeout": 120
}
success = scanner_plugin.create_scan_profile("web_server_scan", profile_config)
```

### Signals

#### `scan_started(str network_range)`

Emitted when a scan starts.

**Parameters:**
- `network_range` (str): The network range being scanned

#### `scan_progress(int current, int total)`

Emitted to indicate scan progress.

**Parameters:**
- `current` (int): Current progress
- `total` (int): Total steps

#### `scan_device_found(object device)`

Emitted when a device is found during a scan.

**Parameters:**
- `device` (object): The device that was found

#### `scan_completed(dict results)`

Emitted when a scan completes.

**Parameters:**
- `results` (dict): A dictionary containing scan results

#### `scan_error(str error_message)`

Emitted when an error occurs during a scan.

**Parameters:**
- `error_message` (str): The error message

#### `profile_created(str profile_name)`

Emitted when a new scan profile is created.

**Parameters:**
- `profile_name` (str): The name of the created profile

#### `profile_updated(str profile_name)`

Emitted when a scan profile is updated.

**Parameters:**
- `profile_name` (str): The name of the updated profile

#### `profile_deleted(str profile_name)`

Emitted when a scan profile is deleted.

**Parameters:**
- `profile_name` (str): The name of the deleted profile

## Integration Points

### Context Menu Actions

The plugin adds the following context menu actions to the device table:

- **Scan Network**: Opens a dialog to scan a custom network range
- **Scan Interface Subnet**: Scans the subnet of the selected network interface
- **Scan Device's Network**: Scans the subnet of the selected device
- **Rescan Selected Device(s)**: Rescans the selected device(s)

### Dock Widget

The plugin adds a dock widget to the main window with the following features:

- Network scan controls
- Scan log display
- Scan results display

### Settings

The plugin provides the following settings (configuration keys):

- **scan_type**: Default scan type (e.g. quick, standard, comprehensive, or a custom profile ID)
- **preferred_interface**: Preferred network interface for scanning
- **scan_timeout**: Timeout in seconds for scan operations
- **use_sudo**: Use elevated permissions (sudo/administrator) for scans
- **custom_scan_args**: Additional nmap arguments applied when set
- **auto_tag**: Automatically tag discovered devices
- **batch_scan_threads**: Number of devices to scan in parallel during batch scans (1–8)
- **scan_profiles**: Dict of profile IDs to profile data (`name`, `description`, `arguments`, `timeout`)

## Example Usage

### Basic Scan

```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Scan the local network
scanner_plugin.scan_network("192.168.1.0/24", "quick")
```

### Advanced Scan with Custom Arguments

```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Configure an advanced scan using profiles and custom arguments.
# The selected profile's arguments define the base behavior (including
# OS detection and port scanning); custom arguments further refine it.
scanner_plugin.update_setting("scan_type", "comprehensive")
scanner_plugin.update_setting("custom_scan_args", "-p 22,80,443,3389 -sV")

# Scan a specific IP range
scanner_plugin.scan_network("10.0.0.1-10.0.0.100")
```

### Using Custom Scan Profiles

```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Create a custom profile (schema: name, description, arguments, timeout)
profile_config = {
    "name": "Web servers",
    "description": "Ports 80, 443, 8080 with version detection",
    "arguments": "-sV -p 80,443,8080",
    "timeout": 60
}
scanner_plugin.create_scan_profile("web_servers", profile_config)

# Use the custom profile for scanning
scanner_plugin.scan_network("192.168.1.0/24", "web_servers")
```

### Listening for Scan Results

```python
# Get the network scanner plugin
scanner_plugin = app.plugin_manager.get_plugin("network_scanner")

# Connect to signals
scanner_plugin.scan_device_found.connect(on_device_found)
scanner_plugin.scan_completed.connect(on_scan_completed)

# Define handler functions
def on_device_found(device):
    print(f"Found device: {device.get_property('alias')}")
    
def on_scan_completed(results):
    print(f"Scan completed. Found {results['devices_found']} devices.")

# Start the scan
scanner_plugin.scan_network("192.168.1.0/24")
```

## Changelog

### Version 10.6 (2026-01-27)
- File structure split into core/ui/utils; design compliance (CollapsibleSection, PluginDialogBase, theme-aware styling); documentation updates for profile-only scan behavior and current settings.

### Version 10.4 (2026-01-26)
- Major improvements to nmap detection and integration
- Enhanced nmap detection to check multiple locations including common Windows installation paths
- Improved nmap executable verification to ensure it actually works before reporting availability
- Added support for detecting nmap.exe on Windows systems
- Implemented PATH management to ensure python-nmap can find nmap even when not in system PATH
- Added actual functionality testing to verify python-nmap can execute nmap
- Improved error handling and logging for nmap detection failures
- Updated error messages to be more helpful for users
- ScannerWorker now receives and uses nmap path for better compatibility

### Version 1.2.4 (2026-01-26)
- Improved nmap detection to check multiple locations including common Windows installation paths
- Enhanced nmap executable verification to ensure it actually works before reporting availability
- Added support for detecting nmap.exe on Windows systems
- Improved error handling and logging for nmap detection failures
- Updated error messages to be more helpful for users

### Version 1.1.9 (2025-05-24)
- Fixed import error for QIntValidator in plugin manager dialog
- Corrected Qt module imports to ensure proper functionality

### Version 1.1.8 (2025-05-23)
- Fixed error when opening profile editor from plugin manager dialog
- Implemented custom profile editor in the plugin manager UI
- Improved user experience for managing scan profiles

### Version 1.1.7 (2025-05-22)
- Fixed error when accessing plugin methods from settings dialog
- Added safe method forwarding for plugin settings pages
- Improved dialog handling to prevent missing method errors

### Version 1.1.6 (2025-05-21)
- Fixed JSON settings display in plugin manager dialog
- Added ability to edit scan profiles through plugin manager interface
- Improved scan profile management with dedicated editor dialog

### Version 1.1.5 (2025-05-20)
- Fixed scan profiles not showing up correctly in the plugin settings dialog
- Improved settings page organization to ensure all options are properly displayed
- Added ability to create and manage scan types directly through the settings interface
- Added additional controls for Custom Arguments and Auto Tag settings

### Version 1.1.4 (2025-05-19)
- Fixed scan profiles not showing up properly in plugin settings dialog
- Added dedicated Scan Profiles settings page for better organization and visibility

### Version 1.1.3 (2025-05-18)
- Improved scan profiles management UI with clearer workflow
- Added dedicated 'Add New Profile' option to the profiles list
- Enhanced form layout with better validation and profile creation experience
- Added interface refresh button to update network interfaces dynamically

### Version 1.1.2 (2025-05-17)
- Fixed validator import in scan dialog
- Fixed QIntValidator reference in the timeout field

### Version 1.1.1 (2025-05-16)
- Fixed context menu integration with device table
- Improved handling of device selection in context menu actions

### Version 1.1.0 (2025-05-15)
- Added interface selection for network scanning
- Added more granular scan permissions and options
- Added ability to scan interface subnet directly
- Added ability to rescan selected devices
- Added support for custom nmap arguments
- Added elevated permissions option for more accurate scans

### Version 1.0.0 (2025-05-12)
- Initial release of the Network Scanner plugin
- Automatic discovery of network devices using nmap
- Adds scanned devices to device table with 'scanned' tag
- Supports scanning of IP ranges and CIDR networks
- Context menu integration for on-demand scanning 