# Sample Plugin API Documentation

Available from **Plugin Manager → Browse** (also included with NetWORKS by default).

## Overview

The Sample Plugin demonstrates how to extend NetWORKS functionality while providing comprehensive testing capabilities for the application. It serves as both a reference implementation for plugin developers and a testing utility for core application features.

Key features include:
- UI extensions (toolbar actions, menu items, device panels, dock widgets)
- Device property extensions
- Device table column extensions
- Comprehensive signal monitoring and testing
- Core application feature testing dashboard
- Plugin lifecycle management examples
- Robust error handling and fault tolerance

## Public API

### Methods

```python
def test_core_features(self):
    """
    Run a comprehensive test of core application features
    
    Returns:
        dict: Dictionary containing test results with success/failure status
    """

def test_signal(self, signal_name):
    """
    Test a specific application signal
    
    Args:
        signal_name (str): Name of the signal to test
        
    Returns:
        bool: True if signal test was successful, False otherwise
    """
    
def monitor_signal(self, signal_name, enable=True):
    """
    Enable or disable monitoring for a specific signal
    
    Args:
        signal_name (str): Name of the signal to monitor
        enable (bool): True to enable monitoring, False to disable
        
    Returns:
        bool: True if the operation was successful
    """
    
def update_device_details(self, device):
    """
    Update device details in the panel
    
    Args:
        device: Device to update details for
    """
    
def log_message(self, message):
    """
    Add a message to the plugin's log widget
    
    Args:
        message (str): Message to log
    """
```

### Device Dialog Usage

The plugin demonstrates how to use the device dialog methods provided by the PluginInterface:

```python
def show_properties_dialog(self, device):
    """
    Show properties dialog for an existing device
    
    Args:
        device: Device to edit
        
    Returns:
        Device or None: Updated device if successful, None if cancelled
    """
    updated_device = self.show_device_properties_dialog(device)
    return updated_device
    
def create_new_device(self):
    """
    Create a new device using the add device dialog
    
    Returns:
        Device or None: New device if created, None if cancelled
    """
    new_device = self.add_device_dialog()
    return new_device
```

### Device Properties

The plugin adds and manages the following device properties:

| Property | Type   | Description                           |
|----------|--------|---------------------------------------|
| sample   | string | A sample property for demonstration   |
| test_result | string | Last test result for this device   |
| test_timestamp | string | Timestamp of the last test      |

Example usage:
```python
# Set sample property
device.set_property("sample", "My Sample Value")

# Get sample property (with default value if not found)
value = device.get_property("sample", "Default")

# Check if property exists
has_property = device.get_property("sample", None) is not None

# Get test results
test_result = device.get_property("test_result", "Not tested")
```

### Testing API

The plugin provides a comprehensive testing API for the application:

```python
# Get the sample plugin instance
sample_plugin = plugin_manager.get_plugin("sample").instance

# Run comprehensive tests
test_results = sample_plugin.test_core_features()
for feature, result in test_results.items():
    print(f"{feature}: {'SUCCESS' if result['success'] else 'FAILED'}")
    
# Test a specific signal
signal_test_result = sample_plugin.test_signal("device_added")
print(f"Signal test result: {signal_test_result}")

# Enable signal monitoring
sample_plugin.monitor_signal("plugin_loaded", True)
```

### Resilient Testing

The sample plugin implements resilient testing strategies to handle different application structures:

#### Device Manager Test

```python
# The device manager test will attempt to:
# 1. Verify the device manager API is accessible
# 2. Check if basic methods are available
# 3. Try to add/remove test devices (but won't fail if this part doesn't work)
# 4. Report success if basic access was possible

result, message = sample_plugin._test_device_manager()
```

#### Device Table Test

```python
# The device table test tries multiple methods to access the table:
# 1. Look for device_table_model in main_window
# 2. Look for device_table in main_window
# 3. Try to get the model from device_table if found
# 4. Search for QTableView and QTableWidget instances in the main window
# 5. Succeed if any method finds the table

result, message = sample_plugin._test_device_table()
```

#### Configuration Test

```python
# The configuration test uses multiple approaches:
# 1. Try various common configuration key names
# 2. Explore available config keys if possible
# 3. Attempt to set and get a test value
# 4. Succeed if any method can verify config access

result, message = sample_plugin._test_configuration()
```

## Error Handling

The Sample Plugin implements comprehensive error handling to ensure stability and fault tolerance:

### Device Property Access

Property access is always performed with safe defaults and type checking:

```python
# Safe property access with default value
device_name = device.get_property("name", "N/A")

# Type checking to prevent format errors
device_name_str = str(device_name) if device_name is not None else "N/A"
```

### Signal Event Logging

Signal events are logged with robust parameter handling:

```python
# Safe parameter formatting
if isinstance(parameters, list) or isinstance(parameters, tuple):
    # Handle case where list might contain None values
    safe_params = ["<None>" if p is None else str(p) for p in parameters]
    params_text = ", ".join(safe_params)
else:
    params_text = str(parameters)
```

### Device Testing Exception Handling

Device testing includes comprehensive exception handling:

```python
try:
    # Perform device tests
    # ...
except Exception as e:
    # Handle any exceptions that occur during testing
    error_msg = f"Error testing device {device_name}: {str(e)}"
    logger.error(error_msg)
    self.log_message(error_msg)
    
    # Update device with error information
    device.set_property("test_result", "ERROR")
    device.set_property("test_summary", f"Test failed with error: {str(e)}")
```

## Signals

### Emitted Signals

The plugin emits the following signals:

| Signal | Parameters | Description |
|--------|------------|-------------|
| test_started | (str) | Emitted when a test begins, with test name |
| test_completed | (str, bool) | Emitted when a test completes, with test name and result |
| test_all_completed | (dict) | Emitted with complete test results dictionary |

### Monitored Signals

The plugin can monitor and log the following application signals:

- `device_manager.device_added`
- `device_manager.device_removed`
- `device_manager.device_changed`
- `device_manager.selection_changed`
- `device_manager.group_added`
- `device_manager.group_removed`
- `plugin_manager.plugin_loaded`
- `plugin_manager.plugin_unloaded`
- `plugin_manager.plugin_enabled`
- `plugin_manager.plugin_disabled`

## Plugin Settings

The plugin demonstrates how to implement configurable settings:

| Setting ID | Type | Description | Default |
|------------|------|-------------|---------|
| log_level | choice | The log level for plugin messages | INFO |
| auto_sample | bool | Automatically add sample property to devices | true |
| default_value | string | Default value for the sample property | Sample Value |
| testing_mode | choice | Testing mode (manual, automatic, or disabled) | manual |
| test_signal_timeout | int | Timeout in seconds for signal tests | 10 |
| signal_monitoring | bool | Enable signal monitoring by default | false |

## UI Components

The plugin provides the following UI components:

- Toolbar actions:
  - "Sample Action": Add sample property to selected devices
  - "Test Application": Launch application testing dashboard

- Menu items (under "Sample" menu):
  - "Sample Menu Action"
  - "Add New Device"
  - "Edit Selected Device"
  - "Run Tests"
  - "Signal Monitor"

- Device panels:
  - "Sample" tab: Shows device details and test results

- Dock widgets:
  - "Sample Plugin Log": Shows plugin operation log
  - "Test Dashboard": Shows test results and monitoring data

### Context Menus

The plugin demonstrates how to implement robust context menus for both device table and group tree:

#### Device Context Menu

The device context menu appears when right-clicking:
- On selected devices: Shows actions that apply to the selection
- On unselected devices: Automatically selects the device and shows the menu
- On empty space: Falls back to the default application menu (if available)

```python
def _setup_device_context_menu(self):
    """Set up context menu for device table items"""
    # Create context menu specific to our plugin
    self.device_context_menu = QMenu("Sample Plugin")
    self.device_context_menu.addAction(self.device_context_actions["mark_important"])
    self.device_context_menu.addAction(self.device_context_actions["set_sample_value"])
    # ... add more actions ...
    
    # Set the custom context menu policy for the device table
    self.device_table.setContextMenuPolicy(Qt.CustomContextMenu)
    self.device_table.customContextMenuRequested.connect(self._on_device_context_menu)
```

To ensure that context menus work correctly, the sample plugin provides comprehensive testing:

```python
def _test_context_menu_setup(self):
    """Verify that the context menu setup is correct"""
    try:
        # Check if device table is accessible
        if not hasattr(self, 'device_table'):
            logger.error("Device table reference not stored")
            return False
            
        # Check if context menu is accessible
        if not hasattr(self, 'device_context_menu'):
            logger.error("Device context menu not created")
            return False
            
        # Check context menu policy
        if self.device_table.contextMenuPolicy() != Qt.CustomContextMenu:
            logger.error("Device table has wrong context menu policy")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error testing context menu setup: {e}")
        return False
```

#### Device Details Testing

The plugin includes comprehensive testing of device detail functionality:

```python
def _test_device_details(self):
    """Test the device details functionality"""
    try:
        # Get devices
        devices = self.device_manager.get_devices()
        if not devices:
            return True, "No devices available to test"
            
        # Test updating device details with a sample device
        sample_device = devices[0]
        
        # Safely test property access
        name = sample_device.get_property('name', 'Unnamed')
        device_type = sample_device.get_property('type', 'Unknown')
        
        # Try updating the device details panel
        self.update_device_details(sample_device)
        
        # Test setting a property
        test_value = f"test-{int(time.time())}"
        sample_device.set_property("sample_test", test_value)
        read_value = sample_device.get_property("sample_test", None)
        
        if read_value == test_value:
            return True, "Device details test successful"
        else:
            return False, "Property value mismatch"
    except Exception as e:
        return False, f"Error in device details test: {e}"
```

#### Signal Connection Tracking

For proper signal disconnection during plugin unloading, the plugin tracks signal connections:

```python
# When connecting a signal
self.device_table.customContextMenuRequested.connect(self._on_device_context_menu)
self._device_table_custom_context_connected = True

# When disconnecting during cleanup
if hasattr(self, 'device_table') and hasattr(self, '_device_table_custom_context_connected'):
    if self._device_table_custom_context_connected:
        try:
            self.device_table.customContextMenuRequested.disconnect(self._on_device_context_menu)
            self._device_table_custom_context_connected = False
        except Exception as e:
            logger.debug(f"Error disconnecting signal: {e}")
```

## Integration Examples

Other plugins can integrate with the Sample Plugin as follows:

```python
def initialize(self, app, plugin_info):
    # Get the sample plugin instance
    sample_plugin_info = app.plugin_manager.get_plugin("sample")
    
    if sample_plugin_info and sample_plugin_info.loaded:
        sample_plugin = sample_plugin_info.instance
        
        # Connect to test signals
        sample_plugin.test_completed.connect(self.on_test_completed)
        
        # Add to log
        sample_plugin.log_message("Integration from my plugin")
        
        # Use the testing API
        test_results = sample_plugin.test_core_features()
        
    return True
    
def on_test_completed(self, test_name, success):
    logger.info(f"Test {test_name} completed: {'SUCCESS' if success else 'FAILED'}")
```

## Changelog

### Version 1.0.5 (2025-05-12)
- Added comprehensive context menu and device details testing
- Improved context menu signal handling and connection tracking
- Added proper disconnection for context menu signals during cleanup
- Added detailed logging and diagnostics for context menu operations
- Fixed signal connection tracking to prevent disconnection warnings

### Version 1.0.4 (2025-05-12)
- Fixed crash when checking device properties with has_property method
- Updated code to use get_property method with proper null checks
- Improved property access throughout the plugin for better compatibility

### Version 1.0.3 (2025-05-12)
- Fixed device context menu to properly appear when right-clicking on selected devices
- Completely redesigned context menu handling for both device table and group tree
- Added proper item selection when right-clicking on unselected devices
- Improved menu action enabling/disabling based on selection properties

### Version 1.0.2 (2025-05-12)
- Improved device manager test to gracefully handle initialization issues
- Enhanced device table test with multiple detection methods
- Fixed configuration system test to work with various config formats
- Made all tests more resilient to variations in application structure

### Version 1.0.1 (2025-05-12)
- Fixed device selection handling to safely handle None property values
- Added robust error handling in signal event logging
- Improved device testing with better exception handling
- Enhanced device details display with proper NULL value handling

### Version 1.0.0 (2025-05-19)
- Added comprehensive application testing capabilities
- Updated to comply with new documentation standards
- Enhanced UI with testing dashboard
- Added signal testing and monitoring functionality

### Version 0.9.1 (2025-04-15)
- Added context menu support for device table
- Implemented device and group action capabilities
- Added more plugin settings for demonstration
- Improved test functionality

### Version 0.1.0 (2023-11-14)
- Initial sample plugin
- Demonstrates basic plugin functionality
- Shows how to register with the application 