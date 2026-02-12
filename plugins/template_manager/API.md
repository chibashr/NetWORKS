# Template Manager Plugin API

Available from **Plugin Manager → Browse**. For future callers and integration, the Template Manager plugin and its storage support the following concepts. The current UI is the primary interface; these are documented for programmatic use or extensions.

## Template storage

- **Location**: Per-workspace under `workspaces/<workspace>/plugins/template_manager/templates.json`.
- **Schema**: List of objects with `id`, `name`, `description`, `body`, `source_command_ref` (optional), `created_at`, `updated_at`.

## Template engine (core)

- **`render_template_text(template_text, context)`**  
  Replaces `{{property}}` placeholders with values from `context`. Matches Report Generator behavior. Supports expression lines (e.g. `{{alias}} + " " + {{ip_address}}`).
- **`STANDARD_DEVICE_PROPERTIES`**  
  Tuple of standard device field names: `id`, `alias`, `hostname`, `ip_address`, `mac_address`, `status`, `notes`, `tags`.

## Device resolution (core)

- **`resolve_devices(device_manager, data_source, filter_logic="AND", filters=None)`**  
  Returns a list of devices for the given `data_source` dict (`type`, `group`, `subnet`, `tag`) and optional filters. Uses the same semantics as Report Generator (`DATA_SOURCE_MAP`, `FILTER_OPERATORS`, etc.).

## Helpers (core)

- **`device_display_name(device)`** — returns a label for UI: `alias`, `hostname`, `ip_address`, or `"Unknown"`. From `plugins.template_manager.core.device_utils`.

## Future API methods (not yet implemented)

If the plugin exposes a programmatic API later, it could include:

- **`get_templates()`** — Return the current workspace's template list (from storage).
- **`add_template(template_dict)`** — Add or update a template and persist.
- **`expand_template(template_id, device)`** — Return the template body with placeholders replaced by `device.get_properties()`.

## Command Manager hand-off

**Load into Command Manager** (direct, no dialog):

1. The current template's body is split into lines; each non-empty line becomes one command (dict with `command`, `alias`, `description`).
2. The Command Manager plugin's `add_temporary_saved_set("Template: <name>", commands)` is called so the template appears as a **temporary Saved Set** in the Command Manager dialog (under "Commands: Saved Sets:"), not as a new device type.
3. The Command Manager dialog is opened with that temporary saved set selected; the user picks devices and runs the commands from the dialog.

Template Manager does not run commands on devices; the user must load the template into Command Manager and run from there.

**Export for Command Manager (file):** opens a dialog with scope and filters. After resolving devices, the template is expanded per device and a single JSON file is written containing the first template's command set. Repeat the export for other templates if needed.

**Workspace:** Templates are stored per workspace. If the workspace changes while Template Manager is open, reopen the dialog or switch back to refresh the list.
