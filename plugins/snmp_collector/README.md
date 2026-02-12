# SNMP Collector Plugin

Collects SNMP traps and supports SNMP polling (GET, GETNEXT) for testing and monitoring.

## Features

- **Trap Receiver**: Listens for SNMP traps on a configurable UDP port (default 1162 for non-root use; use 162 for standard trap port with elevated privileges)
- **SNMP Polling**: Perform GET and GETNEXT operations to test device connectivity and retrieve OID values
- **Ingestion**: Paste JSON trap data to simulate traps for testing workflows

## Requirements

- **Python**: pysnmp>=6.2.0,<7.0.0
- **System**: Python 3.8+, Qt 6.5+

Install dependencies:

```bash
pip install -r plugins/snmp_collector/requirements.txt
```

## Usage

### Trap Receiver

1. Set the bind host (default `0.0.0.0`) and port (default `1162`).
2. Click **Start** to begin listening.
3. Received traps appear in the Collected Traps table.
4. For production use on port 162, run NetWORKS with administrator privileges.

### SNMP Poll

1. Enter the target host IP or hostname.
2. Enter one or more OIDs (comma-separated for GET).
3. Click **GET** or **GETNEXT** to poll.

Common OIDs:

- `1.3.6.1.2.1.1.1.0` - sysDescr
- `1.3.6.1.2.1.1.5.0` - sysName
- `1.3.6.1.2.1.1.3.0` - sysUpTime

### Ingestion (Testing)

Paste JSON in the format:

```json
{
  "agent_address": "192.168.1.1",
  "varbinds": [
    {"oid": "1.3.6.1.6.3.1.1.5.1", "value": "linkDown"}
  ]
}
```

Or an array of trap objects. Click **Ingest** to add them as simulated traps.

## Author

chibashr
