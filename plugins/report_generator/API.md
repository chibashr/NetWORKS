# Report Generator API Documentation

## Overview

The Report Generator plugin adds a report builder UI to create tabular or template-based reports from devices. Reports can be exported to HTML, JSON, CSV, and TXT and are stored per workspace.

## Public API

This plugin does not expose callable APIs for other plugins at this time.

## Device Properties

This plugin does not add or modify device properties.

## Signals

No custom signals are emitted beyond the base `PluginInterface` lifecycle signals.

## UI Components

- Tools menu action: **Report Generator**
- Toolbar action: **Report Generator**
- Device context menu action: **Generate Report**
- Modal dialog: Report Generator builder

## Report Definition Schema

Each report definition is stored as JSON in `reports.json`.

```json
{
  "id": "uuid",
  "name": "My Report",
  "mode": "table",
  "data_source": {
    "type": "all",
    "group": "",
    "subnet": "",
    "tag": ""
  },
  "filters": [
    { "property": "status", "operator": "equals", "value": "up" }
  ],
  "columns": ["alias", "ip_address"],
  "computed_columns": [
    { "name": "Alias + IP", "parts": "alias, \" - \", ip_address" }
  ],
  "transformations": [
    { "target": "alias", "transform": "upper", "value": "" }
  ],
  "sort": { "column": "alias", "direction": "asc" },
  "sorts": [
    { "column": "alias", "direction": "asc" },
    { "column": "ip_address", "direction": "asc" }
  ],
  "template": {
    "header": "Device Report",
    "item": "{{alias}} ({{ip_address}})",
    "footer": "Total: {{total}}"
  },
  "output": { "format": "HTML" }
}
```

## Template Syntax

- `{{property}}` placeholders map to device properties.
- `{{index}}` and `{{total}}` are available in template mode.
- Per-line concatenation supports the pattern:

```
{{device_type}} + " " + {{ip_address}}
```

## Settings

No plugin-specific settings are currently defined.

## Changelog

### 1.0.0 (2026-01-21)

- Initial release of the Report Generator plugin.
