# Command Manager Plugin API

The Command Manager plugin provides an interface for running commands on network devices and managing credentials.

## Plugin Interface

### Initialization

```python
def initialize(self, app, plugin_info)
```
Initializes the plugin with application context and plugin information.

### Start/Stop

```python
def start(self)
```
Starts the plugin and connects signals.

```python
def stop(self)
```
Stops the plugin and disconnects signals.

```python
def cleanup(self)
```
Saves data and cleans up resources before plugin unload.

## Command Sets API

### Command Set Operations

```python
def get_device_types(self)
```
Returns a list of available device types.

```python
def get_firmware_versions(self, device_type)
```
Returns a list of available firmware versions for a specific device type.

```python
def get_command_set(self, device_type, firmware)
```
Returns a `CommandSet` object for the specified device type and firmware.

```python
def add_command_set(self, command_set)
```
Adds or updates a command set in the plugin.

```python
def delete_command_set(self, device_type, firmware)
```
Deletes a command set.

## Credential Management

### Overview

The Command Manager plugin stores credentials **per workspace** for security. Credentials are never shared across workspaces.

1. **Device Credentials**: Stored in device properties (`credentials`), saved/loaded with the workspace.
2. **Group Credentials**: Stored under `config/workspaces/<workspace>/plugins/command_manager/credentials/groups/`.
3. **Subnet Credentials**: Stored under `config/workspaces/<workspace>/plugins/command_manager/credentials/subnets/`.

The plugin uses a fallback mechanism to find credentials:
1. First, it checks device-specific credentials
2. If not found, it checks credentials for any groups the device belongs to (current workspace only)
3. Finally, it checks if the device's IP address falls within any subnets with credentials (current workspace only)

### Credential Storage (per workspace)

- **Device credentials**: In device properties; persisted when the workspace is saved.
- **Group and subnet credentials**: In the current workspace’s `plugins/command_manager/credentials/` directory. When the user switches workspace, the credential store loads that workspace’s group/subnet credentials automatically.

### Credential Methods

| Method | Description |
|--------|-------------|
| `get_device_credentials(device_id, device_ip=None, groups=None)` | Get credentials for a device with fallback to group/subnet |
| `set_device_credentials(device_id, credentials)` | Store credentials for a device in its properties |
| `delete_device_credentials(device_id)` | Remove credentials from a device |
| `set_group_credentials(group_name, credentials)` | Store credentials for a device group |
| `delete_group_credentials(group_name)` | Remove credentials for a device group |
| `set_subnet_credentials(subnet, credentials)` | Store credentials for a subnet |
| `delete_subnet_credentials(subnet)` | Remove credentials for a subnet |
| `get_all_device_credentials()` | Get all device credentials |
| `get_all_group_credentials()` | Get all group credentials |
| `get_all_subnet_credentials()` | Get all subnet credentials |

### Credentials Format

All credentials are stored in a standard dictionary format:

```json
{
  "connection_type": "ssh",
  "username": "admin",
  "password": "<encrypted>",
  "enable_password": "<encrypted>"
}
```

Passwords are encrypted before storage and decrypted when retrieved.

## Command Execution API

```python
def run_command(self, device, command_text, credentials=None)
```
Runs a command on a device. Returns a dictionary with:
- `success`: Boolean indicating if the command succeeded
- `output`: Command output text
- `error`: Error message if command failed

## Command Output Management API

```python
def add_command_output(self, device_id, command_id, output, command_text=None)
```
Adds a command output to the history for a device.

```python
def get_command_outputs(self, device_id, command_id=None)
```
Gets command outputs for a device, optionally filtered by command ID.

```python
def delete_command_output(self, device_id, command_id, timestamp=None)
```
Deletes command output(s) for a device.

## UI Components

The plugin provides the following UI components:

### CommandDialog
Dialog for running commands on devices.

### CredentialManager
Dialog for managing device credentials.

### CommandOutputPanel
Panel for viewing command outputs.

### CommandSetEditor
Dialog for editing command sets.

## Data Model Classes

### CommandSet
Represents a set of commands for a device type and firmware version.

### Command
Represents a single command within a command set.

## Integration

The plugin integrates with the NetWORKS application by:
1. Adding a toolbar action for opening the Command Manager
2. Adding context menu items to device entries
3. Adding a "Command Outputs" tab to device details

## Menu Integration

The Command Manager plugin provides a `find_existing_menu` method that helps plugins integrate with existing menus in the application. This approach prevents the creation of duplicate menus with similar names.

### Usage

```python
# Find the existing Tools menu (case-insensitive)
tools_menu = plugin.find_existing_menu("Tools")

# Create menu actions
return {
    tools_menu: [
        action1,
        action2
    ]
}
```

### Method Documentation

```python
def find_existing_menu(self, menu_name):
    """Find an existing menu by name (case-insensitive)
    
    This method helps plugins integrate with existing menus rather than creating
    duplicate menus. It performs a case-insensitive search for standard menus
    like File, Edit, View, Tools, etc.
    
    Args:
        menu_name (str): The name of the menu to find
        
    Returns:
        str: The exact name of the menu if found, otherwise the original name
    """
    # Implementation details...
```

### Benefits

- Prevents duplicate menus in the application
- Ensures consistent UI
- Allows plugins to integrate with standard application menus
- Case-insensitive matching to handle different capitalization

### Example

When registering plugin menus, use this pattern:

```python
def get_menu_actions(self):
    """Get actions to be added to the menu"""
    # Find the existing Tools menu
    tools_menu = self.find_existing_menu("Tools")
    
    return {
        tools_menu: [
            self.toolbar_action,
            self.credential_manager_action
        ]
    }
```

## Public API

The Command Manager Plugin provides the following API methods:

### Credentials

- `get_device_credentials(device_id, device_ip=None, groups=None)` - Get credentials for a device
- `set_device_credentials(device_id, credentials)` - Set credentials for a device
- `delete_device_credentials(device_id)` - Delete credentials for a device
- `get_group_credentials(group_name)` - Get credentials for a device group
- `set_group_credentials(group_name, credentials)` - Set credentials for a device group
- `delete_group_credentials(group_name)` - Delete credentials for a device group
- `get_subnet_credentials(subnet)` - Get credentials for a subnet
- `set_subnet_credentials(subnet, credentials)` - Set credentials for a subnet
- `delete_subnet_credentials(subnet)` - Delete credentials for a subnet
- `get_all_device_credentials()` - Get all device credentials
- `get_all_group_credentials()` - Get all group credentials
- `get_all_subnet_credentials()` - Get all subnet credentials

### Commands

- `get_device_types()` - Get all available device types
- `get_firmware_versions(device_type)` - Get all available firmware versions for a device type
- `get_commands(device_type, firmware_version)` - Get all commands for a device type and firmware version
- `get_command_set(device_type, firmware_version)` - Get a command set for a device type and firmware version
- `run_command(device, command, credentials=None)` - Run a command on a device

### Command Outputs

- `get_command_outputs(device_id)` - Get all command outputs for a device
- `add_command_output(device_id, command_id, output, command_text=None)` - Add a command output for a device

## Credential Format

Credentials are stored in a dictionary with the following keys:

```json
{
  "connection_type": "ssh|telnet",
  "username": "username",
  "password": "password",
  "enable_password": "enable_password"
}
```

## UI Components

The plugin provides the following UI components:

### Command Dialog

The Command Dialog allows running commands on devices. It has the following features:

- Run commands on individual devices, device groups, or subnets
- Select commands from command sets
- Syntax highlighting for command output
- Export command outputs to files

### Credential Manager

The Credential Manager allows managing credentials for devices, device groups, and subnets.

## Context Menu Integration

The plugin adds the following context menu items to the device table:

- "Run Commands" - Open the Command Dialog for the selected devices
- "Manage Credentials" - Open the Credential Manager for the selected devices

The plugin also adds the following context menu items to the device group and subnet views (if available):

- "Run Commands on Group" - Open the Command Dialog for devices in the selected groups
- "Manage Group Credentials" - Open the Credential Manager for the selected groups
- "Run Commands on Subnet" - Open the Command Dialog for devices in the selected subnets
- "Manage Subnet Credentials" - Open the Credential Manager for the selected subnets

## Device Groups Integration

The Command Manager plugin can now work with device groups in the following ways:

1. **Running Commands on Groups**: You can select a device group and run commands on all devices in that group.

2. **Group Credentials**: You can set credentials at the group level, which will be used for any device in the group that doesn't have its own credentials.

3. **Group-to-Device Fallback**: When running commands, the plugin will check for credentials in the following order:
   - Device-specific credentials
   - Group credentials (for any groups the device belongs to)
   - Subnet credentials (based on the device's IP address)

The plugin uses the device manager's `get_device_groups_for_device()` method to determine which groups a device belongs to.

### Using Device Groups in Your Plugin

To implement similar functionality in your plugin, you can use:

```python
# Get all groups a device belongs to
device_groups = self.device_manager.get_device_groups_for_device(device.id)

# Check if a device is in a specific group
is_in_group = any(group.name == "MyGroup" for group in device_groups)

# Get all devices in a group
group = self.device_manager.get_group("MyGroup")
if group:
    devices = group.get_all_devices()  # Includes devices in subgroups
``` 