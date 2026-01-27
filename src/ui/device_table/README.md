# Device Table

Model, view, filter bar, and query engine for the device table.

## Filter bar (spec-style)

- **Filter** – Text input. Type a query and press **Enter** to search. Updates to match the visual builder when you apply from the Add filter dialog.
- **Add filter** – Icon-only, small button that opens the visual query builder; applied filters are reflected in the search bar as spec-style text.
- **Group** – Filter by device group (separate from text/advanced filter).

The search bar accepts:

1. **Plain text** – Search all columns (e.g. `router`).
2. **Legacy `field:value`** – e.g. `ip:192.168`, `status:online`. Short names: `ip`, `host`, `alias`, `mac`, `status`, `tags`, `groups`. Multiple terms are AND.
3. **Power-user text** (Section 7) – Spec-style expressions:
   - `hostname = "server01"`, `status = "Active"`
   - `hostname contains "web" AND status = "Active"`
   - `(location = "NYC" OR location = "BOS") AND status != "Retired"`
   - `tags contains any ["production","critical"]`
   - `ip in subnet "192.168.1.0/24"`

When filters are applied from the dialog, the search bar shows this spec-style text (strings quoted, list operators as `["a","b"]`, symbolic `=`, `!=`, `>`, `<` where applicable).

## Filter state format

- **Tree**: `{"operator": "AND"|"OR", "conditions": [rule | group, ...]}`  
  Rule: `{"field": str, "operator": str, "value": str}`  
  Group: nested `{"operator", "conditions"}`.
- **Legacy**: `{"logic": "AND"|"OR", "rules": [rule, ...]}` – normalized to tree when applied.

The Advanced Filter dialog supports nested groups (“Add Group”), field-type operators, and presets. The search bar shows the text form of the current filter (power-user syntax when tree, legacy shorthand when flat).

## Modules

- `device_table_model` – Table model and column metadata.
- `device_table_filter` – `parse_filter_syntax`, `filter_state_to_syntax`, `IPSortFilterProxyModel`.
- `device_table_query` – Field types, operators, `parse_text_query`, `tree_to_syntax`, `ensure_tree`.
- `device_table_dialogs` – `AdvancedFilterDialog` (visual query builder).
- `device_table_view` – `DeviceTableView` and filter bar UI.
