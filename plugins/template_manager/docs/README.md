# Template Manager Plugin

Template Manager creates reusable command templates from device outputs using **Report Generator–style variable binding** (`{{property_name}}`), stores them per workspace, and exports populated commands to file or sends them to Command Manager for execution.

Open Template Manager from the **toolbar** or **Tools** menu; it opens as a dialog (no dock panel).

## Variable binding

- **Syntax**: `{{property_name}}` — same as Report Generator.
- **Standard fields**: `id`, `alias`, `hostname`, `ip_address`, `mac_address`, `status`, `notes`, `tags`.
- **Custom fields**: Any key from `device.get_properties()`.
- **Expression lines**: Optional; e.g. `{{alias}} + " " + {{ip_address}}` — same rules as Report Generator templates.

Use **Insert placeholder** or type `{{property_name}}` in the template body. See Report Generator template docs for full syntax.

## Data sources

When loading into Command Manager or exporting for devices, you choose:

- **All Devices**, **Selected Devices**, **Group**, **Subnet**, **Tag**

plus optional **filters** (property, operator, value) with AND/OR logic. This matches Report Generator’s data-source and filter behavior.

## Dialog layout

- **Left**: Templates list and Template details (name, description) on the same row; Source/Body with **Load from Command Manager…** to use a saved command output as body; **searchable Variables** list; Export actions.
- **Right**: **Preview** — choose a device and see the template body rendered with that device’s properties.

## Workflow

1. Create a template: name, description, and body. Use **Load from Command Manager…** to fill the body from a previously saved command output (device + command), or paste/type and add `{{property_name}}` placeholders.
2. Use the **Variables** search to find and insert `{{field}}` at the cursor. Use the **Preview** device list to check rendered output for a given device.
3. Save templates (stored per workspace under `plugins/template_manager/templates.json`).
4. **Export template file…** — save one or more templates to a JSON file for backup/sharing.
5. **Load into Command Manager…** — pick scope and filters, resolve devices, expand each template per device, and add the resulting command set(s) to Command Manager (or export a Command Manager–format JSON file if Command Manager is not loaded).
6. **Batch export…** — export template(s) with variables applied for selected devices / group / subnet. Choose “One file per device” or “One combined file (sections per device)” and a path.
7. **Export template for…** (device table context menu) — right‑click on the device list and choose “Export template for…” to run batch export for the selected devices (template picker and output options in the batch export dialog).

Template Manager does **not** execute commands; it only produces template text and hands it off to Command Manager. Run the commands from Command Manager as usual.

## Dependencies

- **Command Manager** (>=1.0.0) — required for “Load into Command Manager”.

## File layout

- `manifest.json` — plugin metadata and Command Manager dependency.
- `template_manager.py` — entry point, PluginInterface implementation.
- `core/template_engine.py` — `render_template_text`, placeholders (matches Report Generator).
- `core/template_storage.py` — load/save `templates.json` per workspace.
- `core/device_resolver.py` — resolve devices by source + filters (mirrors Report Generator).
- `ui/template_manager_panel.py` — panel content (templates list, source, variables, export), used inside the dialog.
- `ui/template_manager_dialog.py` — dialog opened from toolbar/Tools menu.
- `ui/export_dialog.py` — scope, filters, “Load into Command Manager” / “Export for Command Manager (file)”.
- `resources/icons/template_manager.svg` — plugin icon (48×48 minimum).
