# Report Generator Plugin

The Report Generator plugin lets you build tabular or template-based reports from devices, apply filters, and export to HTML, JSON, CSV, or TXT. Report definitions are saved per workspace.

## Features

- Table and template report modes.
- Data sources: all devices, selected devices, a group, subnet, or tag filter.
- Property filters with common operators.
- Column editor for existing, computed, and transformed columns in table mode.
- Per-field transformations (upper/lower/title/prefix/suffix/date format/concat).
- Export formats: HTML, JSON, CSV, TXT.

## Entry Points

- **Tools menu**: `Tools > Report Generator`
- **Toolbar**: Report Generator action
- **Device table context menu**: `Generate Report` (prefills Selected Devices)

## Report Builder

### Data Source

Choose where devices come from:

- **All Devices**: all devices in the current workspace.
- **Selected Devices**: current selection from the device table.
- **Group**: all devices in the chosen group (including subgroups).
- **Subnet**: devices whose `ip_address` matches the subnet (CIDR supported).
- **Tag**: devices whose `tags` contain the tag.

### Filters

Add property filters using operators such as `equals`, `contains`, `starts_with`, `regex`, and numeric comparisons.

### Columns (Table Mode)

Use **Add Column** to choose:

- **Existing Column**: pick a device property.
- **Computed Column**: define a column name and parts to concatenate.
- **Transformed Column**: target a column and apply a transform.

Computed column parts can be:

- Property names (e.g., `hostname`)
- Quoted literals (e.g., `" - "`)

Example parts:

```
hostname, " - ", ip_address
```

### Template Mode

Templates use `{{property}}` placeholders and can include `{{index}}` and `{{total}}`.

Example item template:

```
{{alias}} ({{ip_address}})
```

Expression-style concatenation is supported per line:

```
{{device_type}} + " " + {{ip_address}}
```

### Transformations

Transformations are configured when adding a transformed column and target a property name:

- `upper`, `lower`, `title`
- `prefix`, `suffix`
- `date_format` (uses Python `strftime` format strings)
- `concat` (builds a string from parts)

## Storage

Reports are saved per workspace at:

```
config/workspaces/<workspace>/plugins/report_generator/reports.json
```

## Notes

- Exported files are UTF-8 encoded.
- If no columns are listed in table mode, all known device properties are used.
