# Plugin UI Design Guide

This guide describes the plugin-scoped UI theme and helper widgets available in NetWORKS. Use these helpers to keep plugin panels, dialogs, and sections consistent with the application styling while staying scoped to plugin surfaces only.

## Design Tokens

- **Accent**: Configurable accent color (default muted Aruba orange `#E87722`)
- **Grid**: 4px spacing
- **Section padding**: 8px
- **Dialog padding**: 16px
- **Dock header height**: 28px
- **Section header height**: 24px
- **Tab height**: 32px
- **Button height**: 28px
- **Button bar height**: 40px

## Plugin Scope

Plugin styling is scoped using a widget property:

- `plugin_ui="true"`

The application sets this property automatically for plugin dock widgets and plugin panels. For custom dialogs or custom widgets, apply the property yourself:

```python
from src.ui.plugin_ui_theme import mark_plugin_ui

mark_plugin_ui(my_widget)
```

## Dock Panels

Plugin dock widgets should use the default dock title bar so they match core
dock headers:

```python
dock = QDockWidget("My Plugin")
dock.setWidget(self.main_widget)
```

The dock widget title must be the plugin name so the panel is easy to identify.
Dock headers include 12px of bottom padding so the title text does not sit
flush against the content.

## Buttons & Toolbars

- Buttons use visible borders to make clickable areas obvious.
- Toolbar buttons use bordered states consistent with standard buttons.
- Enabled buttons are white in light mode and light gray in dark mode.
- Selectable controls should contrast with the surrounding surface so they do not
  read as disabled.
- Text labels should render on transparent backgrounds.
- Checkbox and radio labels should not render with a white highlight; only the
  indicator should read as clickable.
- Group box titles with checkboxes need horizontal padding so the section border
  does not intersect the checkbox indicator.
- Plugin toolbar actions must define an icon asset and label.
- When toolbars are narrow, labels switch to icon-only before truncating text;
  icons remain visible and tooltips provide the full label.
- Icons should be monochrome (black in light theme, white in dark theme) with
  minimal detail and sourced from Material Icons.
- Plugin toolbar actions may set `toolbar_priority` (int) to influence overflow
  order; higher values stay visible longer when space is tight.

## Icon Specifications

Follow the application icon spec in `docs/Design Considerations.md`.

**Aspect ratio:** Buttons that display icons use the same aspect ratio as the icon; icons are almost always square, so icon buttons are square (e.g. 24×24, 32×32).

**Sizes:**
- Toolbar: 24x24px
- Panel header: 16x16px
- Inline: 16x16px
- Status: 12x12px
- Large (dialogs): 32x32px
- Plugin icon: 48x48px minimum (store under `resources/icons`)

**Style:**
- Material Icons (filled)
- Monochrome using theme text colors (black in light theme, white in dark theme)
- Minimal detail
- 2px stroke width when using outline variants
- SVG preferred

**Behavior:**
- Icon-only actions must include tooltips and aria-labels

## Collapsible Sections

Use `CollapsibleSection` instead of a standard group box when you want compact headers and consistent padding:

```python
from src.ui.plugin_widgets import CollapsibleSection

section = CollapsibleSection("Scan Controls")
section.content_layout.addLayout(controls_layout)
panel_layout.addWidget(section)
```

Sections use 24px headers and 8px content padding.
Section headers should include 12px of bottom padding so the text does not sit
flush against the section border.
Group box titles should include 12px of bottom padding so the text does not sit
flush against the border.

## Plugin Dialogs

Use `PluginDialogBase` for settings/results/progress dialogs:

```python
from src.ui.plugin_widgets import PluginDialogBase

dialog = PluginDialogBase("Plugin Settings", parent)
dialog.add_tab(settings_widget, "General")
dialog.add_action_button("Close", dialog.reject)
dialog.exec()
```

Dialogs use 32px tabs, 16px content padding, sharp 28px buttons, and a 40px button bar.

## Tables

Tables inside plugin docks or dialogs are styled with full cell borders and alternating rows. Enable alternating rows in your table widget:

```python
table.setAlternatingRowColors(True)
```
