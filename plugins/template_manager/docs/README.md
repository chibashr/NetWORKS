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

plus optional **filters** (property, operator, value) with AND/OR logic. This applies to **Export for Command Manager (file)** and **Batch export**; **Load into Command Manager** does not use scope/filters (it loads the template body as one command per line).

## Dialog layout

- **Left**: Templates list and Template details (name, description) on the same row; Source/Body with **Load from Command Manager…** to use a saved command output as body; **searchable Variables** list; Export actions (Export template file, Load into Command Manager, Export for Command Manager (file), Batch export).
- **Right**: **Preview** — choose a device and see the template body rendered with that device’s properties.

## Workflow

1. Create a template: name, description, and body. Use **Load from Command Manager…** to fill the body from a previously saved command output (device + command), or paste/type and add `{{property_name}}` placeholders.
2. Use the **Variables** search to find and insert `{{field}}` at the cursor. Use the **Preview** device list to check rendered output for a given device.
3. Save templates (stored per workspace under `plugins/template_manager/templates.json`).
4. **Export template file…** — save one or more templates to a JSON file for backup/sharing.
5. **Load into Command Manager** — loads the current template directly as a command set: each line in the template body becomes one custom command. Command Manager opens with that set selected; pick devices and run. **Export for Command Manager (file)…** opens a dialog with scope and filters, then writes a JSON file containing the first template’s command set (expanded per device); repeat for other templates if needed.
6. **Batch export…** — export template(s) with variables applied for selected devices / group / subnet. Choose “One file per device” or “One combined file (sections per device)” and a path.
7. **Export template for…** (device table context menu) — right‑click on the device list and choose “Export template for…” to run batch export for the selected devices. When opened from the device table context menu, Batch export uses the selected devices and locks the source to “Selected Devices”. Template picker and output options are in the batch export dialog.

Template Manager does **not** execute commands; it only produces template text and hands it off to Command Manager. Run the commands from Command Manager as usual.

Templates are stored **per workspace**. If you switch workspace while Template Manager is open, reopen the dialog or switch back to refresh the list.

## Keyboard

**Escape** closes the Template Manager and export dialogs.

## Dependencies

- **Command Manager** (>=1.0.0) — required for “Load into Command Manager” and “Load from Command Manager…”. Template authoring and batch export to files work without it only if the plugin is still loaded; “Load into Command Manager” and “Load from Command Manager…” are hidden or disabled when Command Manager is unavailable.

## Running tests

From the **project root** (NetWORKS), with the app venv active and `pip install -r requirements.txt` and `pip install -r plugins/template_manager/requirements-dev.txt` done:

- **Run all tests:** `pytest plugins/template_manager/tests/ -v`
- **Run with coverage:** `pytest plugins/template_manager/tests/ -v --cov=plugins.template_manager --cov-report=term-missing --cov-report=html`

Or from the plugin directory: `pytest tests/ -v` (conftest adds project root to `sys.path`).

## File layout

- `manifest.json` — plugin metadata and Command Manager dependency.
- `template_manager.py` — entry point, PluginInterface implementation.
- `core/device_utils.py` — `device_display_name`, `group_names_for_combo` (shared UI helpers).
- `core/template_engine.py` — `render_template_text`, placeholders (matches Report Generator).
- `core/template_storage.py` — load/save `templates.json` per workspace.
- `core/device_resolver.py` — resolve devices by source + filters (mirrors Report Generator).
- `ui/template_manager_panel.py` — panel content (templates list, source, variables, export), used inside the dialog.
- `ui/template_manager_dialog.py` — dialog opened from toolbar/Tools menu.
- `ui/export_dialog.py` — scope, filters, “Export for Command Manager (file)” only (Load into Command Manager is direct from the panel).
- `tests/` — unit tests (see docs/plugins/unit_test_requirements.md).
- `requirements-dev.txt` — pytest, pytest-qt, pytest-cov, pytest-mock.
- `resources/icons/template_manager.svg` — plugin icon (48×48 minimum).
