# Context Menu Integration for Plugins

This guide explains how to properly integrate with NetWORKS context menus from your plugins.

## Overview

NetWORKS provides a standard way for plugins to add actions to context menus without creating separate menus. This approach ensures a consistent user experience and prevents UI clutter.

## Device Table Context Menu

To add actions to the device table context menu:

```python
def initialize(self, app, plugin_info):
    # Store references to app components
    self.app = app
    self.device_manager = app.device_manager
    self.main_window = app.main_window
    
    # Get reference to the device table
    if hasattr(self.main_window, 'device_table'):
        device_table = self.main_window.device_table
        
        # Register actions
        device_table.register_context_menu_action(
            "My Custom Action",      # Action name shown to user
            self._on_custom_action,  # Callback function
            priority=300             # Lower values appear higher in the menu
        )
```

### Handling Device Actions

Your callback should accept a device_or_devices parameter that can be:
- A single Device object
- A list of Device objects
- None (if called from elsewhere)

Example implementation:

```python
def _on_custom_action(self, device_or_devices):
    """Handle custom action for devices"""
    # Standardize to always work with a list
    devices = []
    
    if isinstance(device_or_devices, list):
        devices = device_or_devices
    elif device_or_devices is not None:
        devices = [device_or_devices]
    else:
        # No device provided, prefer checked devices and fall back to highlights
        device_table = self.main_window.device_table if hasattr(self.main_window, 'device_table') else None
        if device_table and hasattr(device_table, 'get_selected_devices'):
            devices = device_table.get_selected_devices()
        else:
            devices = self.device_manager.get_selected_devices()
        
    if not devices:
        # Handle no devices case
        return
        
    # Process devices
    for device in devices:
        if device is None:
            continue
            
        # Your action logic here
        device.set_property("my_property", "value")
```

## Group Tree Context Menu

Similar to the device table, you can add actions to the group tree context menu:

```python
def initialize(self, app, plugin_info):
    # Get reference to the group tree
    if hasattr(self.main_window, 'group_tree'):
        group_tree = self.main_window.group_tree
        
        # Register actions
        group_tree.register_context_menu_action(
            "Group Action",              # Action name shown to user
            self._on_group_action,       # Callback function
            priority=200                 # Lower values appear higher in the menu
        )
```

### Handling Group Actions

Group context menu callback typically receives a group name or tree item:

```python
def _on_group_action(self, group_name_or_item=None):
    """Handle action for groups"""
    # Get the group name
    group_name = None
    
    if isinstance(group_name_or_item, str):
        # If a string is passed, use it as the group name
        group_name = group_name_or_item
    elif hasattr(group_name_or_item, 'text') and callable(group_name_or_item.text):
        # If a QTreeWidgetItem is passed, get its text
        group_name = group_name_or_item.text(0)
    else:
        # Try to get selected group from UI
        if hasattr(self.main_window, 'group_tree'):
            selected_items = self.main_window.group_tree.selectedItems()
            if selected_items:
                group_name = selected_items[0].text(0)
    
    if not group_name:
        # Handle no group case
        return
        
    # Get devices in group
    devices = self.device_manager.get_devices_in_group(group_name)
    
    # Your group action logic here
```

## Icon Specifications

Icons used by context menu actions should follow the application icon spec in
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

**Context Menus:**
- Icon size: 16x16px aligned 8px from the left edge
- Icon-only actions must include tooltips and aria-labels

## Best Practices

1. **Use Safe Handlers**: Wrap your action handlers with error handling to prevent crashes
2. **Check for None**: Always verify devices aren't None before operating on them
3. **Provide User Feedback**: Log actions and display status messages
4. **Unregister on Cleanup**: If the context menu supports it, unregister your actions in cleanup()
5. **Respect Multiple Selection**: Properly handle both single and multiple device selection
6. **Limit Priority Range**: Use 100-900 for priority values to leave room for system actions

## Examples

For a complete implementation example, see the Sample Plugin included with NetWORKS.

## Troubleshooting

- If your actions don't appear, verify the table/tree has the `register_context_menu_action` method
- Ensure your handlers safely handle all parameter types
- Verify your cleanup method doesn't cause disconnection errors 