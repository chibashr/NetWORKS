# Dock + Tabs UI Tester

Test script for tab elements inside a dockable widget. Use to reproduce and debug the clunky/odd borders appearance when styling QTabWidget inside QDockWidget.

## Run

```bash
python scripts/test_dock_tabs_ui.py
```

## Debug Mode

Enable verbose console output:

```bash
# Windows
set NETWORKS_UI_TEST_DEBUG=1
python scripts/test_dock_tabs_ui.py

# Linux/macOS
NETWORKS_UI_TEST_DEBUG=1 python scripts/test_dock_tabs_ui.py
```

## Hover Debugging

The status bar at the bottom updates in real time as you move the mouse over UI elements. It shows:

- **Hover**: Widget hierarchy from leaf to root (e.g. `QTabBar → QTabWidget#SnmpTabWidget → ...`)
- **Style**: Object name and properties (plugin_ui, plugin_ui_section, etc.)

Use this to identify exactly which element you're hovering for theme/stylesheet targeting.

## Layout

- **Central**: Placeholder text
- **Right dock**: SNMP-style panel with tabs (Trap Receiver, SNMP Poll, Ingestion, Collected Traps)
- **SNMP Poll tab**: Form with Host, OID(s), Version dropdown, Community, GET/GETNEXT buttons, results area
