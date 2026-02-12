# SNMP Collector Plugin API

## Overview

The SNMP Collector plugin provides programmatic access to trap collection, polling, and ingestion for integration with other plugins or automated workflows.

## Public Methods

### Trap Receiver

- `start_trap_receiver() -> bool` — Start listening for SNMP traps. Returns True on success.
- `stop_trap_receiver()` — Stop the trap receiver.
- `get_traps() -> List[dict]` — Return the list of collected traps.
- `clear_traps()` — Clear all collected traps.

### Ingestion

- `ingest_trap_json(json_str: str) -> Optional[str]` — Ingest simulated trap(s) from JSON. Returns None on success, error message on failure.

### Polling

Polling is performed via the UI or by importing the core module:

```python
from plugins.snmp_collector.core.snmp_poller import snmp_get, snmp_getnext

ok, results, err = snmp_get("192.168.1.1", ["1.3.6.1.2.1.1.1.0"], community="public")
ok, results, err = snmp_getnext("192.168.1.1", "1.3.6.1.2.1.1", community="public")
```

## Signals

- `trap_received(dict)` — Emitted when a trap is received. Payload includes parsed varbinds, agent address, etc.

## Trap Data Format

Each trap is a dict with keys such as:

- `transport_address` — Source address
- `version` — SNMP version (1 or 2)
- `varbinds` — List of `{"oid": str, "value": str}`
- `_received_at` — ISO timestamp
- For v1: `enterprise`, `agent_address`, `generic_trap`, `specific_trap`, `uptime`
