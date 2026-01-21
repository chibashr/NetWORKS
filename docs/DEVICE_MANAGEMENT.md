# Device Management in NetWORKS

This document provides information about managing devices in NetWORKS, including creating groups and importing devices.

## Table of Contents

- [Creating Device Groups](#creating-device-groups)
- [Importing Devices](#importing-devices)
  - [Importing from Files](#importing-from-files)
  - [Importing from Pasted Text](#importing-from-pasted-text)
  - [Column Mapping](#column-mapping)
  - [Custom Properties](#custom-properties)

## Creating Device Groups

NetWORKS allows you to organize your devices into groups for better management. Groups can be nested to create a hierarchical structure.

### Creating Groups

To create a new group:

1. Right-click in an empty area of the device tree or on an existing group
2. Select "New Group"
3. The group will be created with a default name "New Group"

If a group with the name "New Group" already exists, NetWORKS will automatically append a number to make the name unique (e.g., "New Group (1)", "New Group (2)", etc.).

### Managing Groups

You can perform the following operations on groups:

- **Rename a group**: Select a group and press F2 or use "Rename"
- **Add devices to a group**: Drag devices onto a group or use "Add to Group"
- **Create a subgroup**: Right-click on a group and select "New Subgroup"
- **Move a group**: Drag a group onto another group to change its parent
- **Delete a group**: Right-click on a group and select "Delete Group"

## Importing Devices

NetWORKS provides a powerful device import feature that allows you to bulk import devices from various sources. The import wizard guides you through the process of importing devices and mapping data columns to device properties.

To access the import feature:
- Right-click in an empty area of the device tree and select "Import Devices..."
- Right-click in an empty area of the device table and select "Import Devices..."

### Importing from Files

You can import devices from CSV or text files:

1. In the import wizard, select the "Import from File" tab
2. Click "Browse..." to select a file
3. Configure the delimiter and header options
4. Click "Next" to proceed to column mapping

Supported delimiters include:
- Comma (,)
- Tab
- Semicolon (;)
- Pipe (|)
- Space

### Importing from Pasted Text

You can also paste data directly from your clipboard:

1. In the import wizard, select the "Paste from Clipboard" tab
2. Paste your data into the text area
3. Configure the delimiter and header options
4. Click "Next" to proceed to column mapping

### Column Mapping

The column mapping page allows you to specify how each column in your data maps to device properties:

1. Review the data preview at the top of the page
2. For each column, select the corresponding device property from the dropdown
3. Columns mapped to "None" will be ignored during import
4. Click "Next" to proceed to the final import page

The import wizard will attempt to automatically map columns based on their headers. For example:
- Columns with "name" or "alias" in the header will map to the "alias" property
- Columns with "host" will map to the "hostname" property
- Columns with "ip" will map to the "ip_address" property

### Custom Properties

You can also map columns to custom properties that don't exist in the standard set of device properties:

1. In the column mapping page, enter a name for your custom property
2. Click "Add"
3. The custom property will now be available in the mapping dropdown for any column
4. Map a column to your custom property
5. During import, the custom property will be created for each device

### Selecting a Target Group

On the final import page, you can select which group the imported devices should be added to:

1. Select a group from the dropdown (defaults to "Root Group")
2. Click "Finish" to complete the import process

All imported devices will be added to the selected group and will be visible in both the device tree and the device table. 