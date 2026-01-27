# Template Manager Plugin API

For future callers and integration, the Template Manager plugin and its storage support the following concepts. The current UI is the primary interface; these are documented for programmatic use or extensions.

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

## Future API methods (not yet implemented)

If the plugin exposes a programmatic API later, it could include:

- **`get_templates()`** — Return the current workspace’s template list (from storage).
- **`add_template(template_dict)`** — Add or update a template and persist.
- **`expand_template(template_id, device)`** — Return the template body with placeholders replaced by `device.get_properties()`.

## Command Manager hand-off

When “Load into Command Manager” is used:

1. Devices are resolved via `resolve_devices(device_manager, data_source, filter_logic, filters)`.
2. For each template, for each device, `render_template_text(body, device.get_properties())` is called.
3. A `CommandSet(device_type="Template: <name>", firmware_version="1.0")` is built with one `Command(expanded_text, alias, description)` per device.
4. The Command Manager plugin’s `add_command_set(command_set)` is called for each set.

Template Manager does not execute commands; it only produces command text and passes it to Command Manager.
