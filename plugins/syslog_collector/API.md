# Syslog Collector API Documentation

Collects syslog messages over UDP/TCP for testing and monitoring.

## Features

- **Live receiver**: UDP, TCP, or both (configurable)
- **Parsing modes**: RFC 3164 (BSD), RFC 5424 (structured), or raw
- **Ribbon + dialogs**: Receiver, View Logs, Export
- **Panel**: Log table with Open Config button
- **Export**: CSV or JSON

## Integration

Standalone plugin. Other plugins can:

1. Check if `syslog_collector` is loaded via `plugin_manager.get_plugin("syslog_collector")`
2. Access `get_logs()` for collected entries (if exposed)

## Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| port | int | 1514 | UDP/TCP port (non-privileged) |
| host | string | 0.0.0.0 | Bind address |
| transport | string | udp | udp, tcp, or both |
| parse_mode | string | rfc3164 | rfc3164, rfc5424, or raw |
| max_logs | int | 500 | Max in-memory entries |

## Parsed Log Structure

Each log entry includes:

- `raw`: Original message
- `parse_mode`: rfc3164, rfc5424, or raw
- `facility`, `severity`: Numeric (0–23, 0–7)
- `facility_name`, `severity_name`: Text
- `timestamp`, `host`, `message`: Parsed fields
- `_received_at`: ISO timestamp when received
- `_source_addr`: Source IP address
