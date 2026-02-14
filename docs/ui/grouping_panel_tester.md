# Theme Element Tester

Use `scripts/test_grouping_panel_ui.py` to iterate on theme styling before applying changes to the core. Single comprehensive UI with all theme-defined elements.

## Run

```bash
python scripts/test_grouping_panel_ui.py
```

## Debug Mode

Enable verbose console output:

```bash
# Windows
set NETWORKS_UI_TEST_DEBUG=1
python scripts/test_grouping_panel_ui.py

# Linux/macOS
NETWORKS_UI_TEST_DEBUG=1 python scripts/test_grouping_panel_ui.py
```

## Elements Tested

All elements are in one scrollable panel with clear labels and debug hints:

| # | Element | Debug hint |
|---|---------|------------|
| 1 | QPushButton (enabled, disabled, primary) | surface_raised, border, hover, pressed |
| 2 | QLineEdit | surface_raised, border, focus |
| 3 | QTextEdit, QPlainTextEdit | surface_raised, border, focus |
| 4 | QComboBox | dropdown arrow, popup selection |
| 5 | QSpinBox, QDoubleSpinBox | arrows, surface_raised, selection |
| 6 | QCheckBox, QRadioButton | transparent bg, accent indicator |
| 7 | QGroupBox (regular, static) | centered title bar |
| 8 | CollapsibleSection (expanded, collapsed) | sharp blocks, arrow far right |
| 9 | QTabWidget (plugin_ui) | tab surface_alt, selected accent border |
| 10 | QTableWidget | alternating rows, header_bg, accent selection |
| 11 | QTreeWidget | surface_alt, accent selection |
| 12 | QListWidget | surface_raised, accent selection |
| 13 | Plugin labels (normal, muted, warning) | plugin_ui_muted, plugin_ui_warning |
| 14 | QProgressBar, QSlider | theme palette |
| 15 | QSplitter | separator handle |
| 16 | Debug panel | ThemeTokens + PLUGIN_UI_SIZES |

## Dock

QDockWidget with `plugin_ui="true"` on the right side for dock title bar styling (dock_title_bg, dock_title_text).

## Theme Controls

- **Toggle Light/Dark Theme**: Switches between light and dark themes. Debug panel auto-refreshes.
- **Change Accent Color...**: Opens a color dialog to change the accent color; all themed elements update.
