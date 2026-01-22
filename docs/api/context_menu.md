# Device Table Context Menu API

NetWORKS provides an extensible context menu system for the device table. This allows plugins to add custom actions to the context menu that appears when a user right-clicks on a device in the table.

## Overview

The context menu system consists of:

1. A registration mechanism for adding actions to the context menu
2. A signal system for notifying plugins when the context menu is requested
3. A priority system for ordering actions in the menu
4. Support for multiple device selection

Selection source:
- Checked devices (checkbox column) are the primary selection for menus.
- If no devices are checked, the currently highlighted rows are used.

## Registering Context Menu Actions

Plugins can register context menu actions using the `register_context_menu_action` method of the `DeviceTableView` class:

```python
def register_action(self):
    # Get the device table view
    device_table = self.app.main_window.device_table
    
    # Register an action with name, callback, and priority
    device_table.register_context_menu_action(
        "My Plugin Action",
        self.on_my_action,
        priority=500  # Default priority is 500
    )
```

The callback function should accept a single argument, which will be:
- A single device instance when one device is selected
- A list of device instances when multiple devices are selected
- `None` if the user right-clicked on an empty area

```python
def on_my_action(self, device_or_devices):
    # Handle multiple selected devices
    if isinstance(device_or_devices, list):
        devices = device_or_devices
        logger.info(f"Action performed on {len(devices)} devices")
        # Process multiple devices
        for device in devices:
            # Do something with each device
            logger.debug(f"Processing device: {device.get_property('alias')}")
    
    # Handle single device
    elif device_or_devices:
        device = device_or_devices
        logger.info(f"Action performed on device: {device.get_property('alias')}")
        # Process single device
    
    # Handle no device selected
    else:
        logger.info("Action performed on empty area")
```

## Context Menu Priorities

The context menu system uses priorities to order actions in the menu. Lower priority values appear higher in the menu. The default priorities for built-in actions are:

- Add Device: 10
- Import Devices: 20
- Edit Properties: 200
- Add to Group: 300
- Create New Group: 310
- Select All: 400
- Deselect All: 410
- Delete: 900

Plugins should use priorities between 500 and 800 to appear between the built-in actions.

## Handling Context Menu Signals

Plugins can also respond to context menu requests by connecting to the `context_menu_requested` signal. This signal provides both the selected devices and the menu object:

```python
def initialize(self):
    """Initialize the plugin"""
    # Connect to the context menu requested signal
    self.app.main_window.device_table.context_menu_requested.connect(
        self.on_context_menu_requested
    )

def on_context_menu_requested(self, devices, menu):
    """Handle context menu requested signal
    
    Args:
        devices: List of selected devices
        menu: QMenu instance being shown
    """
    if not devices:
        return
        
    # Create a submenu for your plugin
    submenu = menu.addMenu("My Plugin")
    
    # Add custom actions for the selected devices
    if len(devices) == 1:
        # Single device selected
        device = devices[0]
        submenu.addAction(f"Action for {device.get_property('alias')}", 
                          lambda: self.action_for_device(device))
    else:
        # Multiple devices selected
        submenu.addAction(f"Action for {len(devices)} devices", 
                          lambda: self.action_for_devices(devices))
```

## Multi-Device Selection Support

NetWORKS supports selecting multiple devices at once, and the context menu system provides full support for operating on multiple devices at once. When implementing context menu actions, always handle both single-device and multi-device cases:

```python
def my_plugin_action(self, device_or_devices):
    """Example action that handles both single and multiple devices
    
    Args:
        device_or_devices: Either a single Device object or a list of Devices
    """
    devices = []
    
    # Normalize input to a list of devices
    if isinstance(device_or_devices, list):
        devices = device_or_devices
    elif device_or_devices:
        devices = [device_or_devices]
    else:
        # No devices selected
        return
    
    # Process each device
    processed_count = 0
    for device in devices:
        # Do something with each device
        success = self.process_device(device)
        if success:
            processed_count += 1
    
    # Show result to user
    if processed_count > 0:
        QMessageBox.information(
            self.app.main_window,
            "Operation Complete",
            f"Successfully processed {processed_count} device(s)."
        )
    else:
        QMessageBox.warning(
            self.app.main_window,
            "Operation Failed",
            "No devices were processed successfully."
        )
```

## Complete Plugin Example

Here's a complete example of a plugin that integrates with the context menu system:

```python
class ContextMenuPlugin(PluginInterface):
    def initialize(self):
        """Initialize the plugin"""
        super().initialize()
        logger.info("Initializing Context Menu Plugin")
        
        # Get device table
        self.device_table = self.app.main_window.device_table
        
        # Register direct context menu actions
        self.device_table.register_context_menu_action(
            "Ping Device",
            self.on_ping_device,
            priority=550
        )
        
        # Connect to context menu signal for dynamic menu customization
        self.device_table.context_menu_requested.connect(
            self.on_context_menu_requested
        )
        
        return True
    
    def cleanup(self):
        """Clean up the plugin"""
        # Unregister the context menu action
        self.device_table.unregister_context_menu_action("Ping Device")
        
        # Disconnect from signals
        self.device_table.context_menu_requested.disconnect(self.on_context_menu_requested)
        
        return super().cleanup()
    
    def on_ping_device(self, device_or_devices):
        """Handle the Ping Device action"""
        # Handle multiple devices
        if isinstance(device_or_devices, list):
            devices = device_or_devices
            logger.info(f"Pinging {len(devices)} devices")
            
            success_count = 0
            for device in devices:
                if self._ping_single_device(device):
                    success_count += 1
            
            # Show result to user
            QMessageBox.information(
                self.app.main_window,
                "Ping Results",
                f"Successfully pinged {success_count} out of {len(devices)} devices."
            )
            
        # Handle single device
        elif device_or_devices:
            device = device_or_devices
            logger.info(f"Pinging device: {device.get_property('alias')}")
            
            if self._ping_single_device(device):
                QMessageBox.information(
                    self.app.main_window,
                    "Ping Success",
                    f"Device {device.get_property('alias')} responded to ping."
                )
            else:
                QMessageBox.warning(
                    self.app.main_window,
                    "Ping Failed",
                    f"Device {device.get_property('alias')} did not respond."
                )
    
    def _ping_single_device(self, device):
        """Ping a single device
        
        Args:
            device: Device to ping
            
        Returns:
            bool: True if ping succeeded, False otherwise
        """
        # Implement actual ping functionality here
        ip = device.get_property('ip_address', '')
        if not ip:
            return False
            
        logger.debug(f"Pinging IP: {ip}")
        
        # Simulated ping result
        return True
        
    def on_context_menu_requested(self, devices, menu):
        """Handle context menu requested signal"""
        if not devices:
            return
            
        # Add a submenu for network tools
        network_submenu = menu.addMenu("Network Tools")
        
        if len(devices) == 1:
            # Single device - add specific tools
            device = devices[0]
            
            # Add ping action
            ping_action = network_submenu.addAction("Ping")
            ping_action.triggered.connect(lambda: self.on_ping_device(device))
            
            # Add traceroute action
            traceroute_action = network_submenu.addAction("Trace Route")
            traceroute_action.triggered.connect(lambda: self.on_trace_route(device))
            
            # Only add port scan if device has an IP
            if device.get_property('ip_address'):
                scan_action = network_submenu.addAction("Port Scan")
                scan_action.triggered.connect(lambda: self.on_port_scan(device))
        else:
            # Multiple devices - add bulk operations
            ping_all_action = network_submenu.addAction(f"Ping All ({len(devices)})")
            ping_all_action.triggered.connect(lambda: self.on_ping_device(devices))
            
            # Group scan action
            scan_action = network_submenu.addAction(f"Scan All ({len(devices)})")
            scan_action.triggered.connect(lambda: self.on_scan_devices(devices))
    
    def on_trace_route(self, device):
        """Handle the Trace Route action"""
        logger.info(f"Tracing route to device: {device.get_property('alias')}")
        # Implement trace route functionality here
        
    def on_port_scan(self, device):
        """Handle the Port Scan action"""
        logger.info(f"Scanning ports on device: {device.get_property('alias')}")
        # Implement port scan functionality here
        
    def on_scan_devices(self, devices):
        """Handle scanning multiple devices"""
        logger.info(f"Scanning {len(devices)} devices")
        # Implement bulk scan functionality here
```

## Best Practices

1. **Use descriptive action names**: Make sure the action name clearly indicates what the action will do.
2. **Handle both device and non-device cases**: Your callback should check if a device was provided and handle both cases appropriately.
3. **Clean up during plugin deactivation**: Always unregister your actions when your plugin is disabled or unloaded.
4. **Use appropriate priorities**: Choose priorities that make sense for your actions' importance.
5. **Group related actions in submenus**: If your plugin adds multiple related actions, consider using a submenu to group them. 