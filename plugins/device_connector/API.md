# Device Connector Plugin — API Documentation

## Overview

The Device Connector plugin adds a **Connect** submenu to the **device table** context menu (right-click on device(s)). It opens protocol URLs (ssh://, telnet://, vnc://, rdp://, http://, https://, ftp://) so the system decides how to open them (like FTP). No executable paths; only default ports are configurable.

## Integration

- **Context menu:** Device table only. The plugin connects to `device_table.context_menu_requested` and adds a "Connect" submenu with SSH, Telnet, VNC, RDP, HTTP, HTTPS, and FTP actions. The device tree has no plugin context menu hook; this plugin does not appear there.
- **Selection:** Uses the same selection as the device table (checked devices, or highlighted rows if none checked). Actions operate on one or more selected devices; one URL is opened per device.

## Public API

### Module `connection_runner`

- `resolve_host(device)` — Returns `(host, None)` with `host` = `device.get_property("ip_address")` or `device.get_property("hostname")`; `(None, None)` if both empty.
- `launch_ssh(devices, default_port, plugin_id)` — Opens `ssh://host:port` for each device. Returns `(success_count, error_message)`.
- `launch_telnet(devices, default_port, plugin_id)` — Opens `telnet://host:port`. Returns `(success_count, error_message)`.
- `launch_vnc(devices, default_port, plugin_id)` — Opens `vnc://host:port`. Returns `(success_count, error_message)`.
- `launch_rdp(devices, default_port, plugin_id)` — Opens `rdp://host[:port]`. Returns `(success_count, error_message)`.
- `launch_http(devices, plugin_id)` — Opens `http://host`. Returns `(success_count, error_message)`.
- `launch_https(devices, plugin_id)` — Opens `https://host`. Returns `(success_count, error_message)`.
- `launch_ftp(devices, plugin_id)` — Opens `ftp://host`. Returns `(success_count, error_message)`.

Connection type constants: `CONNECTION_SSH`, `CONNECTION_TELNET`, `CONNECTION_VNC`, `CONNECTION_RDP`, `CONNECTION_HTTP`, `CONNECTION_HTTPS`, `CONNECTION_FTP`.

## Settings

Only default ports are configurable (no executable paths).

| Setting ID            | Type | Description        | Default |
|-----------------------|------|--------------------|---------|
| `default_ssh_port`    | int  | Default SSH port   | 22      |
| `default_telnet_port` | int  | Default Telnet port| 23      |
| `default_vnc_port`    | int  | Default VNC port   | 5900    |
| `default_rdp_port`   | int  | Default RDP port   | 3389    |

Settings are persisted in `config.json` in the plugin directory.

## Logging

The plugin logs with the prefix `[device_connector]` for diagnostics (see NetWORKS README “Log With Context”).

## Changelog

- **1.2.0** — Removed Web (use HTTP/HTTPS). All connection types open as links (ssh://, telnet://, etc.); system decides handler. Removed executable path settings; only default ports.
- **1.1.0** — Added RDP, HTTP, HTTPS, FTP; plugin list icon; link-based behavior.
- **1.0.0** — Initial release: Connect submenu (SSH, Telnet, VNC, Web), configurable paths and ports.
