# Arrow, Dropdown, and Spinner Audit

Audit of how arrows, dropdowns, and spinners are drawn across the NetWORKS UI. These should look consistent relative to their function.

**Audit date:** 2025-02-13  
**Author:** chibashr

---

## Executive Summary

| Component | Implementation | Consistency Issue |
|-----------|----------------|-------------------|
| **ComboBox dropdown** | SVG via `_arrow_svg_data_uri("down")` | ✓ Themed |
| **SpinBox up/down** | Painted QPolygon (Windows) / SVG (stylesheet) | ⚠ Two code paths; painted triangles differ from SVG |
| **QGroupBox expand** | SVG right/down arrows | ✓ Themed |
| **CollapsibleSection** | `QToolButton.setArrowType()` (Qt native) | ❌ Platform-dependent, not themed |
| **Table sort indicator** | Qt style (no override) | ⚠ Platform-dependent |
| **Loading spinner** | Design spec only | N/A (no implementation found) |

---

## 1. Arrow Implementations

### 1.1 Shared SVG Arrows (`theme.py`)

```196:210:src/ui/theme.py
def _arrow_svg_data_uri(direction, color):
    """Create base64 data URI for arrow (up/down/right triangle)."""
    if direction == "up":
        path = "M4 0l4 6H0z"
        vb = "0 0 8 6"
    elif direction == "down":
        path = "M0 0h8L4 6z"
        vb = "0 0 8 6"
    else:  # right (for collapsible panels)
        path = "M0 0l6 4-6 4z"
        vb = "0 0 6 8"
```

- **Up/down**: viewBox `0 0 8 6` → aspect ratio 4:3
- **Right**: viewBox `0 0 6 8` → aspect ratio 3:4
- All use `tokens.text` / `tokens.text_muted` for theme colors

### 1.2 ComboBox Dropdown Arrow

- **Source:** `QComboBox::down-arrow` stylesheet
- **Image:** `_arrow_svg_data_uri("down", tokens.text)`
- **Size:** 10×8 px
- **Design spec:** 12×12 px (Design Considerations §6)
- **Status:** Themed, but size differs from spec

### 1.3 SpinBox Up/Down Arrows

**Two rendering paths:**

1. **Stylesheet** (lines 680–688): SVG `up_arrow_uri` / `down_arrow_uri`, 10×8 px
2. **Paint override** (`_SpinBoxWithArrows`, `_DoubleSpinBoxWithArrows`): `_draw_spinbox_arrow()` draws QPolygon triangles in `paintEvent`

On Windows, the paint override runs after the base paint and draws on top. The style’s `drawPrimitive` skips `PE_IndicatorSpinUp` / `PE_IndicatorSpinDown`, so the platform style does not draw arrows. The painted triangles use:

```python
h = max(5, min(rect.width(), rect.height()) // 2 - 1)
# Triangle: (cx, cy±h), (cx±h, cy∓h), (cx±h, cy∓h)
```

- **Geometry:** Different from SVG (filled triangle, size from rect)
- **Color:** Uses `tokens.text` / `tokens.text_disabled` via `get_current_theme_tokens`
- **Issue:** Spinbox arrows are drawn with QPainter, not the shared SVG, so they can look different from ComboBox and GroupBox

### 1.4 QGroupBox Expand/Collapse

- **Source:** `QGroupBox::indicator` (unchecked = right, checked = down) + NetWORKSStyle.drawPrimitive override
- **Rendering:** NetWORKSStyle draws arrow via `_arrow_polygon_points` when PE_IndicatorCheckBox and widget is QGroupBox (Fusion ignores stylesheet image on Windows)
- **Size:** 10×10 px (indicator width/height)
- **Status:** Themed, consistent with shared geometry

### 1.5 CollapsibleSection Toggle

- **Source:** `plugin_widgets.py` – `QToolButton.setArrowType(Qt.DownArrow | Qt.RightArrow)`
- **Rendering:** Qt style draws the arrow (platform-dependent)
- **Issue:** Does not use `_arrow_svg_data_uri`. CollapsibleSection and QGroupBox both represent expand/collapse but use different arrow implementations.

### 1.6 Table Header Sort Indicator

- **Source:** `QHeaderView` via `setSortIndicator()` – Qt style draws it
- **Design spec:** 8×8 px (Design Considerations §6)
- **Status:** No custom styling; appearance is platform-dependent

### 1.7 Device Tree Expand/Collapse

- **Source:** `device_tree_panel.py` – `material_icon("expand_more"|"expand_less")` with `QStyle.SP_ArrowDown` / `SP_ArrowUp` fallback
- **Status:** Uses Material Icons (or Qt standard icons), not the shared triangle arrows

---

## 2. Dropdowns

### 2.1 QComboBox

- Arrow: SVG down arrow, 10×8 px (see §1.2)
- Popup: `QComboBox QAbstractItemView` – themed surface, border, accent selection
- **Status:** Themed and consistent

### 2.2 Overflow Menu (ScalableToolbar)

- Uses `material_icon("more_horiz")` – horizontal dots, not an arrow
- **Status:** Intentionally different (overflow affordance)

---

## 3. Spinners

### 3.1 Design Spec

- **Design Considerations §Loading States:** 16×16 px (inline), 32×32 px (centered), orange, 1 s rotation
- **Progress dialog:** 32×32 px, accent color

### 3.2 Implementation

- No dedicated spinner widget found in the audit
- Progress dialogs may use `QProgressDialog` or similar; spinner styling not overridden in theme

---

## 4. Recommendations

### 4.1 ~~High Priority: CollapsibleSection Arrows~~ ✅ Implemented

**Problem:** CollapsibleSection uses `setArrowType()`, which yields platform-native arrows instead of themed SVG.

**Fix (implemented):** Replaced `setArrowType()` with `setIcon()` using `arrow_icon("down"|"right", color)` from `theme.py`. CollapsibleSection now uses themed icons matching QGroupBox geometry.

### 4.2 ~~High Priority: SpinBox Arrow Consistency~~ ✅ Implemented

**Problem:** Spinbox arrows were drawn with QPolygon in `paintEvent`, using different geometry than the shared SVG.

**Fix (implemented):** Added `_arrow_polygon_points(direction, rect)` with geometry matching SVG viewBox (8×6 up/down, 6×8 right). `_draw_spinbox_arrow` now uses this shared geometry.

### 4.3 Medium Priority: Arrow Sizing

- **Design spec:** Dropdown 12×12 px, table sort 8×8 px
- **Current:** ComboBox/SpinBox 10×8 px, GroupBox 10×10 px
- Consider aligning sizes with the design spec or documenting the chosen sizes in `core_ui_design.md`.

### 4.4 Low Priority: Table Sort Indicator

- Add stylesheet or style override for `QHeaderView::down-arrow` / `QHeaderView::up-arrow` if Qt supports it, or document that sort indicators follow platform style.

---

## 5. File Reference

| File | Relevant Sections |
|------|-------------------|
| `src/ui/theme.py` | `_arrow_svg_data_uri`, `_draw_spinbox_arrow`, `build_stylesheet` (ComboBox, SpinBox, GroupBox) |
| `src/ui/plugin_widgets.py` | `CollapsibleSection` – `setArrowType` |
| `src/ui/device_tree/device_tree_panel.py` | Expand/collapse buttons – Material icons |
| `docs/Design Considerations.md` | §6 (dropdown 12×12, table sort 8×8), Loading States |
