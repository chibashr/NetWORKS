# Device Creation for Plugins

This guide explains how to properly create and manage devices from your NetWORKS plugins.

## Overview

NetWORKS provides a standard API for plugins to create, modify, and manage devices. Using these APIs ensures compatibility with the core application and other plugins.

## Creating Devices

There are two primary methods for creating devices:

### Method 1: Using create_device (Recommended)

The `create_device` method creates a device without adding it to the manager:

```python
def create_new_device(self):
    """Create a new device with specific properties"""
    # Create the device using the device manager's API
    new_device = self.device_manager.create_device(
        device_type="my_type",        # Type identifier for your device
        name="My Custom Device",      # Human-readable name
        ip_address="192.168.1.100",   # Optional IP address
        mac_address="00:11:22:33:44:55", # Optional MAC address
        status="unknown",             # Initial status
        # Add any custom properties you need
        custom_property="value",
        discovered_by="my_plugin"
    )
    
    # Add it to the device manager so it appears in the UI
    self.device_manager.add_device(new_device)
    
    return new_device
```

### Method 2: Using add_new_device (One-step Approach)

The `add_new_device` method creates a device and adds it to the manager in one step:

```python
def create_new_device(self):
    """Create a new device in one step"""
    # Create and add the device in one operation
    new_device = self.device_manager.add_new_device(
        device_type="my_type",
        name="My Custom Device",
        ip_address="192.168.1.100",
        status="unknown",
        custom_property="value"
    )
    
    return new_device
```

## Device Properties

When creating a device, you can set any properties you need:

### Standard Properties

- `name`: Human-readable device name
- `type`: Device type identifier
- `status`: Device status (unknown, up, down, warning, error, etc.)
- `ip_address`: IP address
- `mac_address`: MAC address
- `hostname`: Device hostname
- `notes`: User notes about the device
- `tags`: List of tags for the device

### Custom Properties

You can add any custom properties by including them in the creation call:

```python
new_device = self.device_manager.create_device(
    device_type="router",
    name="Main Router",
    firmware_version="1.2.3",  # Custom property
    last_scanned="2025-05-12", # Custom property
    open_ports=[22, 80, 443]   # Custom property (list)
)
```

## Modifying Devices

After creating a device, you can modify its properties:

```python
# Get a device
device = self.device_manager.get_device("device-id")

# Update a property
device.set_property("status", "up")

# Update multiple properties
device.update_properties({
    "status": "warning",
    "last_check": "2025-05-12 15:30:00",
    "warning_reason": "CPU usage high"
})

# Get a property
status = device.get_property("status")

# Get all properties
all_props = device.get_properties()
```

## Working with Device Groups

You can organize devices into groups:

```python
# Create a group
group = self.device_manager.create_group("My Devices", "Devices created by my plugin")

# Add a device to a group
self.device_manager.add_device_to_group(device, group)

# Get devices in a group
devices = self.device_manager.get_devices_in_group("My Devices")
```

## Device Lifecycle

Managing the device lifecycle is important for plugins:

```python
# Remove a device (moves to recycle bin)
self.device_manager.remove_device(device)

# Permanently delete a device
self.device_manager.permanently_delete_device(device)

# Restore a device from recycle bin
self.device_manager.restore_device(device)
```

## Icon Specifications

Icons used in plugin UI should follow the application icon spec in
`docs/Design Considerations.md`.

**Sizes:**
- Toolbar: 24x24px
- Panel header: 16x16px
- Inline: 16x16px
- Status: 12x12px
- Large (dialogs): 32x32px
- Plugin icon: 48x48px minimum (store under `resources/icons`)

**Style:**
- Material Icons (filled)
- Monochrome using theme text colors (black in light theme, white in dark theme)
- Minimal detail
- 2px stroke width when using outline variants
- SVG preferred

**Behavior:**
- Icon-only actions must include tooltips and aria-labels

## Best Practices

1. **Use Descriptive Names**: Give devices clear, descriptive names
2. **Set The Right Type**: Use a consistent type string for your devices
3. **Include Discovery Data**: Store information about how and when the device was discovered
4. **Handle Duplicates**: Check if a device already exists before creating a new one
5. **Clean Up**: Remove devices created by your plugin when they're no longer needed
6. **Document Properties**: Document any custom properties your plugin adds

## Example: Device Scanner Plugin

Here's an example of a plugin that scans for devices:

```python
def scan_network(self, network="192.168.1.0/24"):
    """Scan a network for devices"""
    # Scan logic here...
    
    for ip_address in discovered_ips:
        # Check if the device already exists
        existing = None
        for device in self.device_manager.get_devices():
            if device.get_property("ip_address") == ip_address:
                existing = device
                break
                
        if existing:
            # Update existing device
            existing.update_properties({
                "last_seen": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "up"
            })
        else:
            # Create new device
            new_device = self.device_manager.create_device(
                device_type="discovered",
                name=f"Device at {ip_address}",
                ip_address=ip_address,
                status="up",
                discovered_by="network_scanner",
                discovery_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # Add to manager and group
            self.device_manager.add_device(new_device)
            
            # Add to a group
            scan_group = self.device_manager.get_group("Scanned Devices")
            if not scan_group:
                scan_group = self.device_manager.create_group("Scanned Devices")
                
            self.device_manager.add_device_to_group(new_device, scan_group)
```

## Troubleshooting

- If created devices don't appear in the UI, verify you called `add_device` after creating them
- Ensure you're not creating duplicate devices with the same ID
- Check that your plugin properly disconnects from device signals during cleanup 