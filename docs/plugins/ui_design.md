# Plugin UI Design Guide

This guide describes the plugin-scoped UI theme and helper widgets available in NetWORKS. Use these helpers to keep plugin panels, dialogs, and sections consistent with the application styling while staying scoped to plugin surfaces only.

## Visual Assets

Draw as little as possible; favor stock assets. Use SVG icons, Material Icons, or
shared themed assets from the core theme over custom QPainter drawing. Prefer
existing assets (e.g. `arrow_icon`, checkmark SVG) rather than hand-drawn
primitives. This reduces maintenance and keeps plugin UIs consistent with the
core.

## Design Tokens

- **Accent**: Configurable accent color (default muted Aruba orange `#E87722`)
- **Grid**: 4px spacing
- **Section padding**: 8px
- **Dialog padding**: 16px
- **Dock header height**: compact, targeting ~28px at default scaling
- **Section header height**: compact, targeting ~24px at default scaling
- **Tab height**: compact tab row, targeting ~32px at default scaling
- **Tab content padding**: 8px inset from pane edges (applied via stylesheet to `QTabWidget::pane`)
- **Button height**: compact single-line height, targeting ~28px at default scaling
- **Button bar height**: compact bottom bar, targeting ~40px at default scaling

These values are **visual targets** based on a compact desktop density. In code, derive actual sizes from Qt font metrics and layouts using the 4px grid, rather than hardcoding these pixel values, so plugin UIs stay compact but respond correctly to DPI, font, and accessibility settings.

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
- QGroupBox is for static labeled containers only; use CollapsibleSection for
  expand/collapse sections.
- Plugin toolbar actions must define an icon asset and label.
- When toolbars are narrow, labels switch to icon-only before truncating text;
  icons remain visible and tooltips provide the full label.
- Icons should be monochrome (black in light theme, white in dark theme) with
  minimal detail and sourced from Material Icons.
- Plugin toolbar actions may set `toolbar_priority` (int) to influence overflow
  order; higher values stay visible longer when space is tight.

All plugin buttons (text-only, icon-only, text+icon) should use the **same 28px visual height** so mixed button rows feel consistent; icon-only buttons are square at that height, while text and text+icon buttons expand only horizontally.

### Button content variants (icons vs text)

- **Text-only buttons**:
  - Label is centered horizontally; height remains **28px**.
  - Use standard horizontal padding; do not reserve empty space for a missing icon.
- **Icon-only buttons**:
  - Use a **square button** with side length equal to the standard button height (28px), with the 24×24px icon centered inside.
  - Icon is centered; no visible text label, but tooltips and accessible names are required.
- **Text + icon buttons**:
  - In standard layouts, place the icon to the left of the text with a small (4–6px) gap.
  - In ribbon-style toolbars, stack the icon above the label as shown in the main design spec.
  - When toolbar space is constrained, hide the text label and treat the control as icon-only, keeping the tooltip as the primary label.

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

## Tab Content Spacing

Tab content is automatically inset 8px from the pane edges via the application stylesheet (`QTabWidget::pane` padding). This applies to both core and plugin tab widgets.

**For plugins:** Use `create_plugin_tab_widget()` when building tabbed UIs in docks or panels:

```python
from src.ui.plugin_widgets import create_plugin_tab_widget, wrap_in_scroll_area

tab_widget = create_plugin_tab_widget()
tab_widget.addTab(wrap_in_scroll_area(content), "Tab Name")
```

This ensures the tab widget receives plugin styling and pane padding. Tab content does not need extra layout margins—the pane padding provides consistent 8px spacing from the tab edges. If you need to override spacing, use `PLUGIN_UI_SIZES["tab_content_padding"]`.

## Overflow and Scrollable Sections

When tab content, form sections, or panels can overflow (e.g. many fields, conditional v3 options), wrap the content in a scroll area so users can access all controls without clipping:

```python
from src.ui.plugin_widgets import wrap_in_scroll_area

content = MyFormWidget()
scroll = wrap_in_scroll_area(content)
tab_widget.addTab(scroll, "Tab Name")
```

Use `wrap_in_scroll_area` for:
- Tab content that may exceed the available height
- Form sections with variable or many fields
- Dialogs with conditional sections (e.g. v3 options that expand)

The helper applies: `setWidgetResizable(True)`, `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`, and `setFrameShape(QFrame.NoFrame)` for a clean appearance.

## Collapsible Sections

Use `CollapsibleSection` for expand/collapse sections—sharp full-width blocks with
centered headers and arrow far right. Do not use checkable QGroupBox; QGroupBox
is for static labeled containers only.

```python
from src.ui.plugin_widgets import CollapsibleSection
from src.ui.plugin_ui_theme import PLUGIN_UI_SIZES

section = CollapsibleSection("Scan Controls")
section.content_layout.addLayout(controls_layout)
layout.addWidget(section)
```

**Stacking multiple sections:** Use `layout.setSpacing(PLUGIN_UI_SIZES["collapsible_stack_spacing"])` (0) and `layout.addStretch()` at the end so sections sit flush and anchor to the top.

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
