# Syslog Collector Plugin

Collects syslog messages over UDP/TCP for testing and monitoring.

## Features

- **Live receiver**: UDP, TCP, or both (configurable)
- **Parsing**: RFC 3164 (BSD), RFC 5424 (structured), or raw
- **UI**: Ribbon tab + dialogs (Receiver, View Logs, Export) + dock panel
- **Panel**: Log table with Open Config button
- **Export**: CSV or JSON

## Usage

1. Enable the plugin in **Settings → Plugins**
2. Open the **Syslog** ribbon tab
3. Click **Receiver** to configure and start the listener
4. Set bind host, port (default 1514), transport (UDP/TCP/both), and parse mode
5. Click **Start** to begin receiving
6. View logs in the dock panel or via **View Logs**
7. Use **Export** to save logs to CSV or JSON

## Testing

Send test syslog messages with:

```bash
# UDP (default)
logger -n localhost -P 1514 "Test message"

# Or with netcat
echo "<34>Oct 11 22:14:15 mymachine su: test" | nc -u localhost 1514
```
