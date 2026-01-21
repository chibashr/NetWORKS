# Network Scanner Plugin for NetWORKS

## Overview

The Network Scanner plugin allows NetWORKS to discover devices on your network using nmap. It provides a comprehensive set of scanning options and integrates with the device management system to automatically add discovered devices to your inventory.

## Features

- **Interface-Based Scanning**: Select specific network interfaces to scan from
- **Subnet Scanning**: Quickly scan the subnet of your selected interface
- **Device Rescanning**: Rescan specific devices to update their information
- **Multiple Scan Types**: Choose from quick, standard, or comprehensive scan profiles
- **Quick Ping Scan**: Ultra-fast host discovery without nmap for immediate results
- **Granular Permissions**: Configure OS detection, port scanning, and other options
- **Custom Arguments**: Advanced users can provide custom nmap arguments
- **Elevated Permissions**: Optionally use sudo/administrator privileges for more accurate scans
- **Device Discovery**: Automatically add discovered devices to the inventory
- **OS Detection**: Identify operating systems of discovered devices
- **Port Scanning**: Detect open ports and services on network devices
- **Scan Profiles**: Create and manage custom scan profiles through the settings interface

## Requirements

- NetWORKS 0.8.16 or higher
- Python 3.8+
- Qt 6.5+
- Nmap 7.0+
- Python packages:
  - python-nmap>=0.7.1
  - psutil>=5.9.0 (used for interface detection; wheels are available on most platforms)

## Installation

1. Make sure Nmap is installed on your system:
   - Windows: Download and install from [nmap.org](https://nmap.org/download.html)
   - macOS: `brew install nmap`
   - Linux: `sudo apt install nmap` or equivalent

2. The plugin will be automatically installed with NetWORKS.

3. If you need to install the dependencies manually:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Basic Scanning

1. From the NetWORKS main window, open the Network Scanner dock widget or use the Tools menu.
2. Configure your scan settings:
   - Select your desired network interface
   - The network range will be automatically populated, or you can enter a custom range
   - Choose a scan type from the dropdown
   - Adjust OS detection and port scanning options as needed
3. Click "Start Scan" to begin scanning using the current panel settings.
4. For faster discovery without nmap, click "Quick Ping" to perform a basic ping scan.
5. For more advanced options, click "Advanced..." to open the full scan dialog.

### Scanning from the Context Menu

1. Right-click on a device in the device table.
2. Select "Network Scanner" from the context menu.
3. Choose one of the scan options:
   - **Scan Network**: Scan a custom network range
   - **Scan Interface Subnet**: Scan the subnet of your selected interface
   - **Scan Device's Network**: Scan the subnet of the selected device
   - **Rescan Selected Device(s)**: Rescan the selected device(s)

### Scan Types

- **Quick**: Fast ping-only scan to discover hosts (minimal network impact)
- **Standard**: Balanced scan with some port scanning and OS detection
- **Comprehensive**: In-depth scan with extensive port scanning and OS fingerprinting
- **Custom**: Create your own scan profiles with specific settings

### Advanced Options

Access advanced scan options from the "Advanced" tab in the scan dialog (click "Advanced..." button):

- **OS Detection**: Enable/disable OS detection
- **Port Scanning**: Enable/disable port scanning
- **Elevated Permissions**: Use sudo/admin privileges for more accurate results
- **Custom Arguments**: Provide custom nmap arguments for advanced scanning

## Scan Results

Discovered devices are automatically added to the NetWORKS device inventory with:
- IP address
- MAC address (when available)
- Hostname (when available)
- OS information (when detected)
- Open ports and services (when scanned)
- "scanned" tag for easy identification

## Troubleshooting

- **Scan fails to start**: Ensure nmap is properly installed and in your PATH
- **No devices found**: Try using elevated permissions or a more comprehensive scan
- **Slow scanning**: Comprehensive scans can take time; use the quick scan for faster results
- **Missing information**: OS detection and port scanning require appropriate permissions
- **Timeout errors**: If you encounter timeout errors, try using a smaller network range or increase the timeout value in settings

## For Developers

See the [API.md](API.md) file for information on programmatically integrating with the Network Scanner plugin.

## Changelog

### Version 1.2.3 (2025-05-28)
- Fixed critical bug: Only add devices that actually return data during a scan
- Improved filtering to exclude non-responsive hosts from scan results
- Added verification of host status before adding to inventory

### Version 1.2.2 (2025-05-27)
- Fixed stop scan functionality to properly terminate nmap processes
- Added real-time status updates during scanning for better feedback
- Added new Quick Ping scan option that's faster than nmap for simple discovery
- Improved progress feedback with detailed status messages during scans

### Version 1.2.1 (2025-05-26)
- Fixed critical bug causing nmap to time out due to duplicate scan arguments
- Improved argument handling to prevent duplicated command-line options

### Version 1.2.0 (2025-05-25)
- Modified scan button to directly run scan with current panel settings
- Added new 'Advanced...' button to open the full scan dialog
- Fixed nmap timeout issues on new installations by increasing default timeout values
- Added -T4 timing template to scan profiles to improve scan speed
- Improved error handling for scan timeouts with more helpful messages

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