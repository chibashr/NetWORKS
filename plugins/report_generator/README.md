# Report Generator Plugin

## Installation

Available from **Plugin Manager → Browse** (Tools → Plugin Manager → Browse). Install or update without updating the core application.

## Overview

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

### Table Editor vs Template Editor

- **Table mode**: only the **Table Editor** (Columns / Filters / Sorting) is shown.
- **Template mode**: only the **Template Settings** panel is shown. They are never both visible.

### Report Generator Wizard (Table Mode)

The Table Editor is a single wizard with three tabs:

#### 1. Columns

- **Available Fields** (left): searchable list of device properties, grouped as *Standard* (id, alias, hostname, ip_address, mac_address, status, notes, tags) or *Custom*. Fields not yet selected are listed.
- **Selected Columns** (right): drag to reorder. Per column you can toggle **Visible**, set a **Custom header**, or remove; Visible/Header apply to the first selected column. **Add All** / **Remove All** and **Add Column…** (existing/computed/transformed) are available.

#### 2. Filters

- **Combine with**: AND or OR.
- Each filter: **[Property]** **[Operator]** **[Value]**.
- Operators: `equals`, `not_equals`, `contains`, `starts_with`, `ends_with`, `regex`, `>`, `>=`, `<`, `<=`.
- Use **+ Add Filter** and **Remove Selected** to manage rows.

#### 3. Sorting

- Sort rules: **[#]** **[Column]** **[Direction]** with numbered priority (1, 2, 3…).
- Use **+ Add Sort Level**, **Remove Selected**, **Move Up** / **Move Down** to change order.

### Template Editor (Template Mode)

- Header / Item / Footer text with `{{property}}` placeholders.
- **Available properties**: listed as *Standard* and *Custom* (from device properties). Use `{{name}}` in templates.

### Dialog

The Report Generator uses a **3-panel layout**:

- **Left panel**: Quick Start, Report Details (name, mode), Data Source (source, group/subnet/tag). Scrollable.
- **Middle panel** (largest): **Table Info** group containing Columns / Filters / Sorting (table mode) or Template Settings (template mode). Scrollable.
- **Right panel**: Output (format, filename template, path, Save / Generate Preview / Export), Preview of the report output.

The dialog opens at a size that shows all three panels; minimum size is enforced and splitters are adjustable.

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

## Running tests

Unit tests follow `docs/plugins/unit_test_requirements.md`. From the project root, with project dependencies and plugin dev deps installed:

```bash
pip install -r requirements.txt
pip install -r plugins/report_generator/requirements-dev.txt
python -m pytest plugins/report_generator/tests/ -v --tb=short
```

With coverage:

```bash
python -m pytest plugins/report_generator/tests/ --cov=plugins/report_generator --cov-report=term-missing --cov-report=html -q
```

## Storage

Reports are saved per workspace at:

```
config/workspaces/<workspace>/plugins/report_generator/reports.json
```

## Notes

- Exported files are UTF-8 encoded.
- If no columns are listed in table mode, all known device properties are used.
