# Core UI Design

This document captures the core UI styling expectations for NetWORKS and
the implementation touchpoints used to keep the UI consistent across
light, dark, and system themes.

See `docs/Design Considerations.md` for broader product design guidance.

## Theme Support

- Theme keys live under `ui.*` in configuration.
- Supported values for `ui.theme`: `light`, `dark`, `system`.
- Global styling is generated in `src/ui/theme.py` and applied in `src/app.py`.
- Accent color is configurable in settings (default Aruba orange).
- The default Aruba orange (`#ff8300`) is the primary accent across selection,
  focus, and emphasis states when no override is set.

## Menu Bar + Toolbar

- Toolbar icons are 24x24, monochrome where possible, using Material Icons.
- Tool buttons show text labels with an associated icon to align with an
  Office-like layout.
- Every toolbar action must define an icon asset.
- When space is tight, labels switch to icon-only before any text truncation;
  icons are the primary visible affordance and tooltips carry the label.
- Spacing stays compact with sharp corners and subtle separators.
- Tool buttons include visible borders so the clickable area is obvious.
- Icons should be monochrome (black in light theme, white in dark theme) with
  minimal detail.
- When space is tight, lower-priority toolbar actions collapse into an overflow
  menu (chevron) instead of shrinking the core actions.

## Buttons + Inputs

- Enabled buttons are white in light mode and light gray in dark mode.
- Selectable controls (buttons, inputs, combo boxes) should contrast with the
  surrounding surface so they do not read as disabled.
- Text labels should render on transparent backgrounds so they blend with the
  surface behind them.
- Checkbox and radio labels should never render with a white highlight; only the
  indicator should read as clickable.
- Section headers (group boxes, collapsible panels, dock titles) should include
  12px of bottom padding so the text does not sit flush against the border.
- Group box titles that include checkboxes must have horizontal padding so the
  border line does not intersect the checkbox indicator.

## Dock Panels

- Dock headers target a 28px height with bold titles.
- Dock widget header text uses the plugin name so the panel is easy to identify.
- Padding uses 4px grid spacing for compact density.
- Controls inherit global theme styling (avoid per-widget color overrides).

## Tables

- Full cell borders with subtle gridlines.
- Alternating rows and 22px row height for compact density.
- Selection uses the configured accent color with high-contrast text.
- IP/MAC/ID-style fields use monospace for scanability.

## Dialogs

- Dialogs inherit the global theme and tab styling.
- Button bars stay right-aligned and use consistent spacing.
- Inline color styling should be avoided unless it communicates status.

## Status Bar

- Compact, information-dense layout with neutral background.
- Labels should read clearly without strong borders or shadows.
