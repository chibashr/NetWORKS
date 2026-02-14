# SNMP Collector UI Refactor Design

**Status**: Implemented  
**Author**: chibashr  
**Date**: 2026-02-13

## Overview

Refactor the SNMP Collector plugin to provide:
1. **Toolbar (ribbon tab "SNMP")** with buttons that open dialogs for each function
2. **Panel (dock)** with an SNMP tab containing the full workflow
3. **Dialogs** for each function: Trap Receiver, SNMP Poll, Collected Traps

## Current State

- Single dock panel with collapsible sections: Trap Receiver, SNMP Poll, Collected Traps
- No toolbar actions
- All functionality in one panel

## Proposed Architecture

### 1. Ribbon Tab: "SNMP"

- Change manifest `name` to `"SNMP"` (or keep "SNMP Collector" and use a display name if the core supports it)
- Add `get_toolbar_actions()` returning 3 QActions:
  - **Trap Receiver** → opens `TrapReceiverDialog`
  - **SNMP Poll** → opens `SnmpPollDialog`
  - **View Traps** → opens `CollectedTrapsDialog` (or focuses the panel)

### 2. Dialogs (one per function)

| Dialog | Purpose | Content (from current panel) |
|--------|---------|------------------------------|
| `TrapReceiverDialog` | Start/stop trap receiver | Bind host, port, Start/Stop, status |
| `SnmpPollDialog` | Run GET/GETNEXT | Host, OID(s), preset OID dropdown, community, GET/GETNEXT buttons, results |
| `CollectedTrapsDialog` | View collected traps | Table, Clear button |

Each dialog:
- Uses `QDialog` with `exec()` for modal use
- Shares plugin instance for state (traps list, receiver, settings)
- Can be opened from toolbar or from panel quick-launch buttons

### 3. Panel (dock)

- Single dock titled **"SNMP"**
- Internal `QTabWidget` with tabs:
  - **SNMP Poll** – poll form + "Trap Receiver" button (opens `TrapReceiverDialog`), same content as `SnmpPollDialog`
  - **Collected Traps** – traps table + Clear

  *(Trap Receiver tab removed; config accessible via button in SNMP Poll tab.)*

- Alternatively: panel shows traps table + toolbar-style buttons that open the dialogs (lighter panel, dialogs do the work)

### 4. Shared Widgets

To avoid duplication, extract reusable content into widgets:

```
ui/
  dialogs/
    trap_receiver_dialog.py   # TrapReceiverDialog
    snmp_poll_dialog.py      # SnmpPollDialog
    collected_traps_dialog.py # CollectedTrapsDialog
  widgets/
    trap_receiver_widget.py  # Shared by dialog and panel
    snmp_poll_widget.py
    traps_table_widget.py
  panel.py                   # Builds panel from widgets
```

The panel can reuse the same widgets as the dialogs, or embed the dialog content widgets directly.

## Implementation Order

1. **Extract widgets** – Split current panel content into reusable widgets (TrapReceiverWidget, SnmpPollWidget, etc.)
2. **Create dialogs** – Wrap each widget in a QDialog
3. **Add toolbar actions** – Add `get_toolbar_actions()` returning actions that open dialogs
4. **Refactor panel** – Use tabbed layout with tabs or embedded widgets
5. **Update manifest** – Set `name` to `"SNMP"` (or keep full name and add ribbon display name if supported)
6. **Version and changelog** – Bump version, add changelog entry

## File Length Considerations

Per workspace rules: keep files under 500 lines, target 200–400. Each dialog/widget should be ~100–200 lines. Splitting by function supports this.

## Dependencies

- No new dependencies
- Core plugin interface unchanged (`get_toolbar_actions`, `get_dock_widgets`)

## Compatibility

- Existing settings remain unchanged
- Trap receiver and poller logic stay in `core/`
- UI-only refactor
