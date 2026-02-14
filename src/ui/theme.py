#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Theme tokens and stylesheet generation for NetWORKS.
"""

import base64
import os

ARROW_DEBUG = os.environ.get("NETWORKS_ARROW_DEBUG", "").lower() in ("1", "true", "yes")
from dataclasses import dataclass
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QIcon, QPalette, QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QRadioButton,
    QProxyStyle,
    QStyleFactory,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionGroupBox,
    QStyleOptionSpinBox,
    QStyleOptionTab,
    QGroupBox,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QSplitterHandle,
)


class _GroupBoxUppercaseTitle(QGroupBox):
    """QGroupBox that displays titles in uppercase."""

    def __init__(self, title=""):
        super().__init__(title.upper() if isinstance(title, str) else title)

    def setTitle(self, title):
        super().setTitle(title.upper() if isinstance(title, str) else title)


def _patch_groupbox_uppercase():
    """Patch QGroupBox so all group box titles render in uppercase."""
    import PySide6.QtWidgets as _qt
    _qt.QGroupBox = _GroupBoxUppercaseTitle


# Apply patch when theme loads (before other UI imports QGroupBox)
_patch_groupbox_uppercase()


CHECKMARK_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" d="M5 12l5 5 9-13"/>
</svg>'''

RADIO_DOT_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="6" fill="{color}"/>
</svg>'''

ARROW_SVG = {
    "up": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 6"><path fill="{color}" d="M4 0l4 6H0z"/></svg>',
    "down": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 6"><path fill="{color}" d="M0 0h8L4 6z"/></svg>',
    "right": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 6 8"><path fill="{color}" d="M0 0l6 4-6 4z"/></svg>',
}


def _render_svg(svg_str, size):
    """Render SVG string to QPixmap. Returns None on failure."""
    try:
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QImage, QPixmap
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        if not renderer.isValid():
            return None
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return QPixmap.fromImage(image)
    except ImportError:
        return None


def _draw_checkbox_symbol(painter, rect):
    """Draw checkmark SVG icon in accent color when checked."""
    app = QApplication.instance()
    tokens = get_current_theme_tokens(app) if app else None
    if not tokens:
        return
    pixmap = _render_svg(CHECKMARK_SVG.format(color=tokens.accent), min(rect.width(), rect.height()))
    if pixmap:
        size = pixmap.width()
        x = rect.x() + (rect.width() - size) // 2
        y = rect.y() + (rect.height() - size) // 2
        painter.drawPixmap(x, y, pixmap)


def _draw_radio_symbol(painter, rect):
    """Draw dot SVG icon in accent color when checked."""
    app = QApplication.instance()
    tokens = get_current_theme_tokens(app) if app else None
    if not tokens:
        return
    size = min(rect.width(), rect.height())
    pixmap = _render_svg(RADIO_DOT_SVG.format(color=tokens.accent), size)
    if pixmap:
        x = rect.x() + (rect.width() - size) // 2
        y = rect.y() + (rect.height() - size) // 2
        painter.drawPixmap(x, y, pixmap)


class _CheckBoxWithSymbol(QCheckBox):
    """Draws checkmark symbol when checked (no solid fill)."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked() and self.isEnabled():
            opt = QStyleOptionButton()
            self.initStyleOption(opt)
            ind = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, self)
            if ind.isValid():
                _draw_checkbox_symbol(QPainter(self), ind)


class _RadioButtonWithSymbol(QRadioButton):
    """Draws filled dot when checked (no solid fill)."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked() and self.isEnabled():
            opt = QStyleOptionButton()
            self.initStyleOption(opt)
            ind = self.style().subElementRect(QStyle.SubElement.SE_RadioButtonIndicator, opt, self)
            if ind.isValid():
                _draw_radio_symbol(QPainter(self), ind)


def _patch_checkbox_radio():
    import PySide6.QtWidgets as _qt
    _qt.QCheckBox = _CheckBoxWithSymbol
    _qt.QRadioButton = _RadioButtonWithSymbol


_patch_checkbox_radio()


def _spinbox_button_rects(opt, widget):
    """Compute up/down button rects for spinbox. Fallback when subControlRect fails."""
    r = opt.rect if opt else (widget.rect() if widget else QRect())
    if not r.isValid() or r.width() < 20 or r.height() < 10:
        return None, None
    btn_w = 18
    x = r.x() + max(0, r.width() - btn_w - 2)
    half = max(4, r.height() // 2)
    up_rect = QRect(x, r.y() + 2, btn_w, half - 2)
    down_rect = QRect(x, r.y() + half, btn_w, r.height() - half - 2)
    return up_rect, down_rect


def _combobox_arrow_rect(opt, widget):
    """Compute ComboBox dropdown arrow rect. Fallback when subControlRect fails."""
    r = opt.rect if opt else (widget.rect() if widget else QRect())
    if not r.isValid() or r.width() < 24 or r.height() < 8:
        return None
    arrow_w = 18
    arrow_h = max(8, r.height() - 4)
    x = r.x() + max(0, r.width() - arrow_w - 2)
    y = r.y() + (r.height() - arrow_h) // 2
    return QRect(x, y, arrow_w, arrow_h)


def _spinbox_button_rects_widget(widget):
    """Button rects for SpinBox (widget coords)."""
    r = widget.rect()
    if not r.isValid() or r.width() < 20:
        return None, None
    btn_w = 18
    x = max(0, r.width() - btn_w - 2)
    half = max(4, r.height() // 2)
    return QRect(x, 2, btn_w, half - 2), QRect(x, half, btn_w, r.height() - half - 2)


def _combobox_arrow_rect_widget(widget):
    """Arrow rect for ComboBox (widget coords)."""
    r = widget.rect()
    if not r.isValid() or r.width() < 24:
        return None
    return QRect(r.width() - 20, 2, 18, r.height() - 4)


ARROW_SCALE = 0.4  # Arrow icon uses 40% of available rect


def _draw_arrow_standalone(painter, rect, direction, enabled=True):
    """Draw arrow SVG. Standalone—does not require NetWORKSStyle."""
    if not rect.isValid() or direction not in ARROW_SVG:
        return
    app = QApplication.instance()
    color = "#6B7280"  # fallback: medium gray, works on light and dark
    if app:
        try:
            tokens = get_current_theme_tokens(app)
            color = tokens.text_disabled if not enabled else get_arrow_color(app)
        except Exception:
            pass
    rect_size = min(rect.width(), rect.height())
    size = max(4, int(rect_size * ARROW_SCALE))
    pixmap = _render_svg(ARROW_SVG[direction].format(color=color), size)
    if pixmap:
        x = rect.x() + (rect.width() - size) // 2
        y = rect.y() + (rect.height() - size) // 2
        painter.drawPixmap(x, y, pixmap)


class _SpinBoxWithArrows(QSpinBox):
    """QSpinBox that draws arrows in paintEvent. No overlay—no blocking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if ARROW_DEBUG:
            print("[ARROW] _SpinBoxWithArrows created")

    def paintEvent(self, event):
        super().paintEvent(event)
        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        style = self.style()
        up = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxUp, self
        )
        down = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxDown, self
        )
        if not up.isValid() or not down.isValid():
            up, down = _spinbox_button_rects_widget(self)
            up = up or QRect()
            down = down or QRect()
        if ARROW_DEBUG:
            print(f"[ARROW] SpinBox rects: up={up.getRect() if up.isValid() else None}, down={down.getRect() if down.isValid() else None}")
        if up.isValid() and down.isValid():
            painter = QPainter(self)
            _draw_arrow_standalone(painter, up, "up", self.isEnabled())
            _draw_arrow_standalone(painter, down, "down", self.isEnabled())
            painter.end()


class _DoubleSpinBoxWithArrows(QDoubleSpinBox):
    """QDoubleSpinBox that draws arrows in paintEvent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if ARROW_DEBUG:
            print("[ARROW] _DoubleSpinBoxWithArrows created")

    def paintEvent(self, event):
        super().paintEvent(event)
        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        style = self.style()
        up = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxUp, self
        )
        down = style.subControlRect(
            QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxDown, self
        )
        if not up.isValid() or not down.isValid():
            up, down = _spinbox_button_rects_widget(self)
            up = up or QRect()
            down = down or QRect()
        if up.isValid() and down.isValid():
            painter = QPainter(self)
            _draw_arrow_standalone(painter, up, "up", self.isEnabled())
            _draw_arrow_standalone(painter, down, "down", self.isEnabled())
            painter.end()


class _ComboBoxWithArrow(QComboBox):
    """QComboBox that draws dropdown arrow in paintEvent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if ARROW_DEBUG:
            print("[ARROW] _ComboBoxWithArrow created")

    def paintEvent(self, event):
        super().paintEvent(event)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        style = self.style()
        r = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opt, QStyle.SubControl.SC_ComboBoxArrow, self
        )
        if not r.isValid():
            r = _combobox_arrow_rect_widget(self)
        if ARROW_DEBUG:
            print(f"[ARROW] ComboBox rect: {r.getRect() if r and r.isValid() else None}")
        if r is not None and r.isValid():
            painter = QPainter(self)
            _draw_arrow_standalone(painter, r, "down", self.isEnabled())
            painter.end()


def _patch_arrow_widgets():
    import PySide6.QtWidgets as _qt
    _qt.QSpinBox = _SpinBoxWithArrows
    _qt.QDoubleSpinBox = _DoubleSpinBoxWithArrows
    _qt.QComboBox = _ComboBoxWithArrow
    if ARROW_DEBUG:
        print("[ARROW] Patched QSpinBox, QDoubleSpinBox, QComboBox")


_patch_arrow_widgets()


def _splitter_dots_color():
    """Color for splitter handle dots; darker than separator."""
    tokens = get_current_theme_tokens(QApplication.instance())
    return _shade_hex(tokens.separator, 0.7)


class _DotSplitterHandle(QSplitterHandle):
    """Splitter handle that draws dots in the center only."""

    def paintEvent(self, event):
        r = self.rect()
        if not r.isValid():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(_splitter_dots_color())
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        dot_r = 1.5
        gap = 4
        # orientation(): Horizontal = splitter divides left/right, handle is vertical bar
        # Vertical = splitter divides top/bottom, handle is horizontal bar
        if self.orientation() == Qt.Orientation.Horizontal:
            # Vertical bar: 3 dots stacked
            cx = r.center().x()
            for dy in (-gap, 0, gap):
                painter.drawEllipse(int(cx - dot_r), int(r.center().y() + dy - dot_r), int(dot_r * 2), int(dot_r * 2))
        else:
            # Horizontal bar: 3 dots in a row
            cy = r.center().y()
            for dx in (-gap, 0, gap):
                painter.drawEllipse(int(r.center().x() + dx - dot_r), int(cy - dot_r), int(dot_r * 2), int(dot_r * 2))
        painter.end()


class _DotSplitter(QSplitter):
    """QSplitter that uses dot-style handles."""

    def createHandle(self):
        return _DotSplitterHandle(self.orientation(), self)


def _patch_splitter():
    import PySide6.QtWidgets as _qt
    _qt.QSplitter = _DotSplitter


_patch_splitter()


class NetWORKSStyle(QProxyStyle):
    """Fusion-based style for consistent cross-platform appearance."""

    def __init__(self):
        base = QStyleFactory.create("Fusion") if QStyleFactory else None
        super().__init__(base)

    def subControlRect(
        self,
        control,
        option,
        sub_control,
        widget=None,
    ):
        rect = super().subControlRect(control, option, sub_control, widget)
        if control == QStyle.ComplexControl.CC_GroupBox and sub_control == QStyle.SubControl.SC_GroupBoxLabel:
            opt = option
            if isinstance(opt, QStyleOptionGroupBox):
                r = opt.rect
                if widget is not None:
                    r = widget.rect()
                header_height = rect.height() if rect.isValid() else max(20, opt.fontMetrics.height() + 4)
                return QRect(r.left(), r.top(), r.width(), header_height)
        return rect

    def _draw_arrow(self, painter, rect, direction, enabled=True):
        """Draw arrow SVG (delegates to _draw_arrow_standalone)."""
        _draw_arrow_standalone(painter, rect, direction, enabled)

    def drawControl(self, element, option, painter, widget=None):
        """Tab bar tab label: center and bottom-align text."""
        if element == QStyle.ControlElement.CE_TabBarTabLabel:
            opt = option
            if isinstance(opt, QStyleOptionTab) and opt.rect.isValid():
                rect = opt.rect
                text = opt.text or ""
                has_icon = opt.icon is not None and not opt.icon.isNull()
                if text or has_icon:
                    painter.save()
                    if not (opt.state & QStyle.StateFlag.State_Enabled):
                        painter.setOpacity(0.5)
                    if has_icon:
                        icon_rect = QRect(rect.x(), rect.y(), opt.iconSize.width(), opt.iconSize.height())
                        icon_rect.moveCenter(QRect(rect.x(), rect.y(), rect.width(), rect.height() // 2).center())
                        opt.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
                    if text:
                        text_rect = rect
                        if has_icon:
                            text_rect = QRect(rect.x(), rect.y() + opt.iconSize.height() + 2, rect.width(), rect.height() - opt.iconSize.height() - 2)
                        painter.drawText(
                            text_rect,
                            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                            text,
                        )
                    painter.restore()
                return
        super().drawControl(element, option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        """Skip spinbox arrows. Suppress checkable QGroupBox indicator (use CollapsibleSection instead)."""
        if element in (QStyle.PE_IndicatorSpinUp, QStyle.PE_IndicatorSpinPlus,
                      QStyle.PE_IndicatorSpinDown, QStyle.PE_IndicatorSpinMinus):
            return
        if element == QStyle.PE_IndicatorCheckBox and widget is not None and isinstance(widget, QGroupBox):
            return  # No expand/collapse on QGroupBox; use CollapsibleSection
        super().drawPrimitive(element, option, painter, widget)


def _hex_to_rgb(hex_color):
    """Convert #RRGGBB to rgb(r,g,b) for SVG (avoids # in data URI)."""
    c = QColor(hex_color)
    return f"rgb({c.red()},{c.green()},{c.blue()})"


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
    fill = _hex_to_rgb(color) if str(color).startswith("#") else color
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"><path fill="{fill}" d="{path}"/></svg>'
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _grip_svg_data_uri(color):
    """Create base64 data URI for 3-dot vertical grip (drag affordance)."""
    fill = _hex_to_rgb(color) if str(color).startswith("#") else color
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 14">'
        f'<circle cx="4" cy="2" r="1.2" fill="{fill}"/>'
        f'<circle cx="4" cy="7" r="1.2" fill="{fill}"/>'
        f'<circle cx="4" cy="12" r="1.2" fill="{fill}"/>'
        "</svg>"
    )
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def arrow_icon(direction, color, size=10):
    """Create QIcon for arrow (up/down/right) from SVG."""
    if direction not in ARROW_SVG:
        return QIcon()
    hex_color = color.name() if hasattr(color, "name") else str(color)
    pixmap = _render_svg(ARROW_SVG[direction].format(color=hex_color), size)
    if not pixmap:
        return QIcon()
    icon = QIcon()
    icon.addPixmap(pixmap)
    return icon


@dataclass(frozen=True)
class ThemeTokens:
    name: str
    accent: str
    accent_soft: str
    accent_hover: str
    accent_pressed: str
    background: str
    surface: str
    surface_alt: str
    surface_raised: str
    border: str
    text: str
    text_muted: str
    text_disabled: str
    selection_text: str
    menu_bg: str
    toolbar_bg: str
    status_bg: str
    dock_title_bg: str
    dock_title_text: str
    separator: str
    table_alt: str
    header_bg: str
    header_text: str
    focus: str
    row_height: int
    header_height: int
    font_size: int
    spacing: int
    radius: int


def resolve_theme_name(theme_name, app=None):
    normalized = (theme_name or "light").strip().lower()
    if normalized != "system":
        return normalized
    if app is None:
        return "light"
    palette = app.palette()
    window_color = palette.color(QPalette.Window)
    return "dark" if window_color.lightness() < 128 else "light"


def _normalize_hex(color_value):
    if not color_value:
        return None
    if isinstance(color_value, QColor):
        return color_value.name()
    value = str(color_value).strip()
    if not value:
        return None
    if not value.startswith("#"):
        value = f"#{value}"
    if len(value) != 7:
        return None
    return value.lower()


def _shade_hex(hex_color, factor):
    color = QColor(hex_color)
    return QColor(
        max(0, min(255, int(color.red() * factor))),
        max(0, min(255, int(color.green() * factor))),
        max(0, min(255, int(color.blue() * factor))),
    ).name()


def _blend_hex(base_hex, overlay_hex, overlay_ratio):
    base = QColor(base_hex)
    overlay = QColor(overlay_hex)
    ratio = max(0.0, min(1.0, overlay_ratio))
    return QColor(
        int(base.red() * (1 - ratio) + overlay.red() * ratio),
        int(base.green() * (1 - ratio) + overlay.green() * ratio),
        int(base.blue() * (1 - ratio) + overlay.blue() * ratio),
    ).name()


def _apply_accent_override(tokens, accent_override):
    accent = _normalize_hex(accent_override)
    if not accent:
        return tokens
    return tokens.__class__(
        **{
            **tokens.__dict__,
            "accent": accent,
            "accent_hover": _shade_hex(accent, 0.9),
            "accent_pressed": _shade_hex(accent, 0.85),
            "accent_soft": _blend_hex(tokens.background, accent, 0.15),
            "focus": accent,
        }
    )


def _derive_header_height(font_size):
    """Derive header height from font size for compact text fitting."""
    return max(18, int(round(font_size * 2.0)))


def _derive_control_height(font_size):
    """Derive control/button height from font size; compact like tab headers."""
    return max(16, font_size + 6)


def get_control_height(app=None):
    """Return control/button height for current theme (matches line edits, combos)."""
    tokens = get_current_theme_tokens(app)
    return _derive_control_height(tokens.font_size)


def get_arrow_color(app=None):
    """Return arrow color for dropdown, spin box, CollapsibleSection. Consistent across light/dark themes."""
    tokens = get_current_theme_tokens(app)
    return tokens.text_muted


def get_theme_tokens(theme_name, font_size=10, row_height=22, accent_override=None):
    theme = (theme_name or "light").strip().lower()
    header_height = _derive_header_height(font_size)
    if theme == "dark":
        tokens = ThemeTokens(
            name="dark",
            accent="#E87722",
            accent_soft="#3d2a12",
            accent_hover="#D66A1F",
            accent_pressed="#C35E1C",
            background="#1E1E1E",
            surface="#2D2D2D",
            surface_alt="#26282b",
            surface_raised="#3a3d43",
            border="#3E3E3E",
            text="#E5E7EB",
            text_muted="#9CA3AF",
            text_disabled="#6B7280",
            selection_text="#1b1b1b",
            menu_bg="#2D2D2D",
            toolbar_bg="#26282b",
            status_bg="#2a2c30",
            dock_title_bg="#2f3136",
            dock_title_text="#E5E7EB",
            separator="#41454c",
            table_alt="#26292e",
            header_bg="#31343a",
            header_text="#E5E7EB",
            focus="#E87722",
            row_height=row_height,
            header_height=header_height,
            font_size=font_size,
            spacing=4,
            radius=0,
        )
        return _apply_accent_override(tokens, accent_override)
    tokens = ThemeTokens(
        name="light",
        accent="#E87722",
        accent_soft="#fbe5d6",
        accent_hover="#D66A1F",
        accent_pressed="#C35E1C",
        background="#FFFFFF",
        surface="#F8F9FA",
        surface_alt="#f2f2f4",
        surface_raised="#FFFFFF",
        border="#D1D5DB",
        text="#1F2937",
        text_muted="#6B7280",
        text_disabled="#9CA3AF",
        selection_text="#ffffff",
        menu_bg="#F8F9FA",
        toolbar_bg="#F2F2F4",
        status_bg="#F2F2F4",
        dock_title_bg="#F2F2F4",
        dock_title_text="#1F2937",
        separator="#D1D5DB",
        table_alt="#fafafa",
        header_bg="#E9EAEC",
        header_text="#1F2937",
        focus="#E87722",
        row_height=row_height,
        header_height=header_height,
        font_size=font_size,
        spacing=4,
        radius=0,
    )
    return _apply_accent_override(tokens, accent_override)


def get_current_theme_tokens(app=None):
    """Get theme tokens for the current application configuration."""
    if app is None:
        return get_theme_tokens("light")
    config = getattr(app, "config", None)
    if not config:
        return get_theme_tokens("light")
    theme_name = config.get("ui.theme", "light") if config else "light"
    font_size = config.get("ui.font_size", 10) if config else 10
    row_height = config.get("ui.row_height", 22) if config else 22
    accent_color = config.get("ui.accent_color", "") if config else ""
    resolved = resolve_theme_name(theme_name, app)
    return get_theme_tokens(
        resolved,
        font_size=font_size,
        row_height=row_height,
        accent_override=accent_color,
    )


def _group_header_font_size(font_size):
    """Group header font size: 4pt smaller than base, minimum 6."""
    return max(6, font_size - 4)


def build_stylesheet(tokens):
    # Derive compact control sizes from theme tokens so sizing follows
    # configured row height / header height instead of hardcoded pixels.
    # Control/button height from font size so buttons align with line edits, combos.
    control_height = _derive_control_height(tokens.font_size)
    button_height = control_height
    table_header_height = tokens.row_height - 2
    dock_header_height = tokens.header_height + 2
    group_header_font_size = _group_header_font_size(tokens.font_size)
    group_header_bar_height = group_header_font_size + 4
    tab_bar_height = max(16, tokens.font_size + 4)
    up_arrow_uri = _arrow_svg_data_uri("up", tokens.text_muted)
    down_arrow_uri = _arrow_svg_data_uri("down", tokens.text_muted)
    grip_uri = _grip_svg_data_uri(tokens.dock_title_text)
    return f"""
    QWidget {{
        background-color: transparent;
        color: {tokens.text};
        font-size: {tokens.font_size}px;
    }}
    QMainWindow, QDialog {{
        background-color: {tokens.background};
    }}
    QMenuBar {{
        background-color: {tokens.menu_bg};
        padding: {tokens.spacing}px;
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: {tokens.spacing}px 8px;
        border-radius: {tokens.radius}px;
        margin: 1px;
    }}
    QMenuBar::item:selected {{
        background-color: {tokens.surface_alt};
    }}
    QMenuBar::item:pressed {{
        background-color: {tokens.accent_soft};
        color: {tokens.selection_text};
    }}
    QMenu {{
        background-color: {tokens.surface};
        border: 1px solid {tokens.border};
        padding: {tokens.spacing}px;
    }}
    QMenu::item {{
        padding: {tokens.spacing}px 24px {tokens.spacing}px 20px;
        border-radius: {tokens.radius}px;
    }}
    QMenu::item:selected {{
        background-color: {tokens.accent};
        color: {tokens.selection_text};
    }}
    QMenu::item:disabled {{
        color: {tokens.text_disabled};
    }}
    QToolBar {{
        background-color: {tokens.toolbar_bg};
        spacing: {tokens.spacing}px;
        padding: {tokens.spacing}px;
        border-bottom: 1px solid {tokens.separator};
    }}
    QToolBar::separator {{
        background-color: {tokens.separator};
        width: 1px;
        margin: 0 {tokens.spacing}px;
    }}
    QWidget#RibbonContainer,
    QWidget#RibbonContent {{
        background-color: {tokens.toolbar_bg};
    }}
    QToolBar#RibbonToolbar {{
        background-color: {tokens.toolbar_bg};
        border-bottom: 1px solid {tokens.separator};
        padding: 0 {tokens.spacing}px;
    }}
    QTabBar#RibbonTabBar {{
        background-color: {tokens.toolbar_bg};
        border: none;
    }}
    QTabBar#RibbonTabBar::tab {{
        min-height: {dock_header_height}px;
        padding: {tokens.spacing}px 8px;
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-radius: 0px;
        margin-right: 2px;
        font-weight: 500;
    }}
    QTabBar#RibbonTabBar::tab:selected {{
        background-color: {tokens.surface};
        border-bottom: 2px solid {tokens.accent};
    }}
    QTabBar#RibbonTabBar::tab:hover {{
        background-color: {tokens.accent_soft};
    }}
    QToolButton {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 2px 6px;
        min-width: 64px;
        min-height: {button_height}px;
    }}
    QToolButton:hover {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.border};
    }}
    QToolButton:pressed {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.accent};
    }}
    QToolButton:focus {{
        border-color: {tokens.focus};
    }}
    QToolButton:checked {{
        background-color: {tokens.accent};
        color: {tokens.selection_text};
    }}
    /* Icon-only tool buttons: square chrome so they share height with text buttons. */
    QToolButton[iconOnly="true"] {{
        min-width: {button_height}px;
        max-width: {button_height}px;
        min-height: {button_height}px;
        max-height: {button_height}px;
    }}
    QToolButton[iconOnlyInline="true"] {{
        min-width: {button_height}px;
        max-width: {button_height}px;
        min-height: {button_height}px;
        max-height: {button_height}px;
    }}
    QPushButton {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 2px 10px;
        min-height: {button_height}px;
    }}
    QPushButton:hover {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.accent_hover};
    }}
    QPushButton:pressed {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.accent};
    }}
    QPushButton:focus {{
        border-color: {tokens.focus};
    }}
    QPushButton:disabled {{
        color: {tokens.text_disabled};
        border-color: {tokens.border};
        background-color: {tokens.surface_alt};
    }}
    QLineEdit {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 2px 6px;
        min-height: {control_height}px;
    }}
    QTextEdit, QPlainTextEdit {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 2px 6px;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {tokens.focus};
    }}
    QComboBox {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 2px 18px 2px 6px;
        min-height: {control_height}px;
    }}
    QCheckBox, QRadioButton {{
        color: {tokens.text};
        background-color: transparent;
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
    }}
    QCheckBox::indicator:checked {{
        background-color: transparent;
        border: 1px solid {tokens.accent};
    }}
    QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 7px;
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
    }}
    QRadioButton::indicator:checked {{
        background-color: transparent;
        border: 1px solid {tokens.accent};
        border-radius: 7px;
    }}
    QLabel {{
        background-color: transparent;
    }}
    QComboBox:hover {{
        border-color: {tokens.accent_hover};
    }}
    QComboBox:focus {{
        border-color: {tokens.focus};
    }}
    QComboBox QAbstractItemView {{
        background-color: {tokens.surface};
        border: 1px solid {tokens.border};
        selection-background-color: {tokens.accent};
        selection-color: {tokens.selection_text};
    }}
    QComboBox::drop-down {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-top-right-radius: {tokens.radius}px;
        border-bottom-right-radius: {tokens.radius}px;
        width: 18px;
        subcontrol-origin: border;
        subcontrol-position: top right;
    }}
    QComboBox::drop-down:hover {{
        background-color: {tokens.accent_soft};
    }}
    QComboBox::drop-down:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QComboBox::down-arrow {{
        image: url(data:image/svg+xml;base64,{down_arrow_uri});
        width: 10px;
        height: 8px;
    }}
    QSpinBox, QDoubleSpinBox {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: 0;
        padding: 2px 6px;
        padding-right: 24px;
        min-height: {control_height}px;
        selection-background-color: {tokens.accent};
        selection-color: {tokens.selection_text};
    }}
    QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {tokens.accent_hover};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {tokens.focus};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-top-right-radius: 0;
        width: 18px;
        subcontrol-origin: border;
        subcontrol-position: top right;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-top: none;
        border-bottom-right-radius: 0;
        width: 18px;
        margin-top: -1px;
        subcontrol-origin: border;
        subcontrol-position: bottom right;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {tokens.accent_soft};
    }}
    QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
    QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url(data:image/svg+xml;base64,{up_arrow_uri});
        width: 10px;
        height: 8px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url(data:image/svg+xml;base64,{down_arrow_uri});
        width: 10px;
        height: 8px;
    }}
    QTabWidget::pane {{
        border: 1px solid {tokens.border};
        background-color: {tokens.surface};
        padding: {tokens.spacing * 2}px;
    }}
    QTabBar::tab {{
        background-color: {tokens.surface_alt};
        color: {tokens.text};
        padding: 2px 8px 2px 8px;
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-top-left-radius: {tokens.radius}px;
        border-top-right-radius: {tokens.radius}px;
        min-height: {tab_bar_height}px;
        font-size: {max(8, tokens.font_size - 1)}px;
        text-align: center;
    }}
    QTabBar::tab:selected {{
        background-color: {tokens.surface};
        border-bottom: 2px solid {tokens.accent};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {tokens.accent_soft};
    }}
    QTreeView, QTableView {{
        background-color: {tokens.surface};
        alternate-background-color: {tokens.table_alt};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        gridline-color: {tokens.border};
        selection-background-color: {tokens.accent};
        selection-color: {tokens.selection_text};
    }}
    QTreeView::item, QTableView::item {{
        padding: 2px {tokens.spacing + 2}px;
        border-right: 1px solid {tokens.border};
        border-bottom: 1px solid {tokens.border};
        height: {tokens.row_height}px;
    }}
    QTreeView::item:selected, QTableView::item:selected {{
        background-color: {tokens.accent};
        color: {tokens.selection_text};
    }}
    QTreeView::item:hover:!selected, QTableView::item:hover:!selected {{
        background-color: {tokens.accent_soft};
    }}
    QTreeView::item:focus:!selected, QTableView::item:focus:!selected {{
        background-color: {tokens.accent_soft};
    }}
    QHeaderView::section {{
        background-color: {tokens.header_bg};
        color: {tokens.header_text};
        padding: 1px 4px;
        border: 1px solid {tokens.border};
        min-height: {table_header_height}px;
    }}
    QHeaderView::section:hover {{
        background-color: {tokens.accent_soft};
    }}
    QHeaderView::section:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QListWidget, QListView {{
        background-color: {tokens.surface};
        alternate-background-color: {tokens.table_alt};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        selection-background-color: {tokens.accent};
        selection-color: {tokens.selection_text};
    }}
    QDockWidget {{
        border: 1px solid {tokens.border};
    }}
    QDockWidget::title {{
        background-color: {tokens.dock_title_bg};
        background-image: url(data:image/svg+xml;base64,{grip_uri});
        background-repeat: no-repeat;
        background-position: 6px center;
        color: {tokens.dock_title_text};
        padding: {tokens.spacing}px 8px;
        padding-left: 20px;
        font-weight: bold;
        min-height: {dock_header_height}px;
        border: 1px solid {tokens.border};
        text-align: center;
    }}
    QDockWidget > QWidget {{
        border: none;
        padding: 0;
    }}
    QStatusBar {{
        background-color: {tokens.status_bg};
        color: {tokens.text_muted};
        padding: {tokens.spacing}px 6px;
    }}
    QStatusBar::item {{
        border-left: 1px solid {tokens.separator};
        padding: 0 6px;
    }}
    QSplitter::handle {{
        background-color: transparent;
        border: none;
    }}
    QSplitter::handle:horizontal {{
        width: 9px;
        margin: 0 6px;
    }}
    QSplitter::handle:vertical {{
        height: 9px;
        margin: 6px 0;
    }}
    /* Integrated header: full-width bar, centered text. Qt cannot set width on ::title;
       large padding expands title bar; parent clips. See stackoverflow.com/questions/14049290 */
    QGroupBox {{
        background-color: {tokens.surface};
        border: 1px solid {tokens.border};
        border-width: 1px;
        border-style: solid;
        border-color: {tokens.border};
        border-radius: {tokens.radius}px;
        margin-top: 6px;
        padding: 4px 6px 2px 6px;
        padding-top: {group_header_bar_height + 4}px;
        font-size: {group_header_font_size}px;
    }}
    QGroupBox QWidget {{
        font-size: {tokens.font_size}px;
    }}
    QGroupBox > QListWidget, QGroupBox > QTreeView, QGroupBox > QTableView,
    QGroupBox > QTextEdit, QGroupBox > QPlainTextEdit, QGroupBox > QScrollArea {{
        margin-top: 4px;
    }}
    QGroupBox + QGroupBox {{
        margin-top: 4px;
    }}
    QGroupBox::title {{
        subcontrol-origin: border;
        subcontrol-position: top center;
        top: 0;
        padding: 2px 10000px;
        color: {tokens.text};
        font-weight: 600;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {tokens.border},
            stop:0.003 {tokens.border},
            stop:0.003 {tokens.surface_alt},
            stop:0.997 {tokens.surface_alt},
            stop:0.997 {tokens.border},
            stop:1 {tokens.border});
        border-top: 1px solid {tokens.border};
        border-bottom: 1px solid {tokens.border};
        min-height: {group_header_font_size}px;
        text-align: center;
    }}
    QLabel#PluginStatusBar {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        padding: {tokens.spacing}px 6px;
    }}
    QLabel#PluginStatusLabel {{
        color: {tokens.text_muted};
        font-weight: bold;
    }}
    QTextBrowser#PluginDocumentationView {{
        font-family: monospace;
    }}
    QPushButton[importance="primary"] {{
        font-weight: bold;
    }}
    QScrollBar:vertical {{
        background-color: {tokens.surface_alt};
        width: 12px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {tokens.border};
        min-height: 20px;
        border-radius: 0;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {tokens.accent_soft};
    }}
    QScrollBar::handle:vertical:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {tokens.surface_alt};
        height: 12px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {tokens.border};
        min-width: 20px;
        border-radius: 0;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {tokens.accent_soft};
    }}
    QScrollBar::handle:horizontal:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QProgressBar {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {tokens.accent};
        border-radius: {tokens.radius}px;
    }}
    QSlider {{
        min-height: 24px;
        padding: 6px 0;
    }}
    QSlider::groove:horizontal {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        height: 6px;
        border-radius: 0;
    }}
    QSlider::handle:horizontal {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        width: 14px;
        margin: -5px 0;
        border-radius: 0;
    }}
    QSlider::handle:horizontal:hover {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.accent_hover};
    }}
    QSlider::handle:horizontal:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QSlider::sub-page:horizontal {{
        background-color: {tokens.accent};
        border-radius: 0;
    }}
    /* Plugin-scoped overrides */
    QDockWidget[plugin_ui="true"] {{
        border: none;
        background-color: {tokens.surface};
    }}
    QDockWidget[plugin_ui="true"] > QWidget {{
        padding: 0;
        border: none;
    }}
    QWidget#PluginDockHeader {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
    }}
    QLabel#PluginDockTitle {{
        color: {tokens.text};
        font-weight: 600;
        text-align: center;
    }}
    /* CollapsibleSection: sharp full-width blocks, arrow far right, text centered */
    QWidget#CollapsibleSection {{
        min-width: 100%;
        border-width: 1px;
        border-style: solid;
        border-color: {tokens.border};
    }}
    QFrame#CollapsibleSectionHeader {{
        min-height: {tokens.row_height}px;
        min-width: 100%;
        padding: {tokens.spacing}px 6px;
        margin: 0;
        background-color: {tokens.surface_alt};
        border-width: 1px;
        border-style: solid;
        border-color: {tokens.border};
        border-bottom: none;
        border-radius: 0;
    }}
    QFrame#CollapsibleSectionHeader:hover {{
        background-color: {tokens.accent_soft};
    }}
    QWidget#CollapsibleSection[collapsed="true"] QFrame#CollapsibleSectionHeader,
    QFrame#CollapsibleSectionHeader[collapsed="true"] {{
        border-bottom: 1px solid {tokens.border};
        border-radius: 0;
    }}
    QWidget#CollapsibleSection QFrame#CollapsibleSectionContent {{
        border-width: 1px;
        border-style: solid;
        border-color: {tokens.border};
        border-top: none;
        border-radius: 0;
        background-color: {tokens.surface};
    }}
    QLabel#CollapsibleSectionTitle {{
        color: {tokens.text};
        font-weight: 600;
        text-align: center;
    }}
    QWidget#CollapsibleSection QToolButton[plugin_ui_section="true"] {{
        min-width: {tokens.row_height}px;
        min-height: {tokens.row_height}px;
        max-width: {tokens.row_height}px;
        max-height: {tokens.row_height}px;
        padding: 0;
        margin: 0;
        color: {tokens.text};
        background-color: transparent;
        border: none;
    }}
    QWidget#CollapsibleSection QToolButton[plugin_ui_section="true"]:hover {{
        background-color: {tokens.accent_soft};
        border-radius: 0;
    }}
    QDialog[plugin_ui="true"] {{
        background-color: {tokens.surface};
    }}
    /* Scroll area: match dialog background to prevent white overlay on scrollable content */
    QDialog[plugin_ui="true"] QScrollArea, QDockWidget[plugin_ui="true"] QScrollArea,
    QWidget[plugin_ui="true"] QScrollArea {{
        background-color: {tokens.surface};
        border: none;
    }}
    QDockWidget[plugin_ui="true"] QPushButton {{
        min-height: {button_height}px;
        border-radius: 0px;
    }}
    QDialog[plugin_ui="true"] QPushButton {{
        min-height: {button_height}px;
        border-radius: 0px;
    }}
    QDialog[plugin_ui="true"] QWidget#PluginDialogButtonBar {{
        min-height: {button_height + 12}px;
    }}
    QTabWidget[plugin_ui="true"]::pane {{
        border: 1px solid {tokens.border};
        background-color: {tokens.surface};
        padding: {tokens.spacing * 2}px;
    }}
    QTabBar[plugin_ui="true"]::tab {{
        min-height: {tab_bar_height}px;
        padding: 2px 8px 2px 8px;
        font-size: {max(8, tokens.font_size - 1)}px;
        text-align: center;
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-radius: 0px;
    }}
    QTabBar[plugin_ui="true"]::tab:selected {{
        background-color: {tokens.surface};
        border-bottom: 2px solid {tokens.accent};
    }}
    QDockWidget[plugin_ui="true"] QTableView,
    QDockWidget[plugin_ui="true"] QTableWidget,
    QDialog[plugin_ui="true"] QTableView,
    QDialog[plugin_ui="true"] QTableWidget {{
        border: 1px solid {tokens.border};
        gridline-color: {tokens.border};
        alternate-background-color: {tokens.table_alt};
    }}
    QDockWidget[plugin_ui="true"] QHeaderView::section,
    QDialog[plugin_ui="true"] QHeaderView::section {{
        background-color: {tokens.header_bg};
        color: {tokens.header_text};
        padding: 2px {tokens.spacing}px;
        border: 1px solid {tokens.border};
        min-height: {table_header_height}px;
    }}
    QDialog[plugin_ui="true"] QLabel[plugin_ui_muted="true"],
    QWidget[plugin_ui="true"] QLabel[plugin_ui_muted="true"] {{
        color: {tokens.text_muted};
    }}
    QDialog[plugin_ui="true"] QLabel[plugin_ui_warning="true"],
    QWidget[plugin_ui="true"] QLabel[plugin_ui_warning="true"] {{
        color: {tokens.accent};
    }}
    /* Spin box: arrows via NetWORKSStyle, narrow buttons to avoid input overlay */
    QDockWidget[plugin_ui="true"] QSpinBox, QDockWidget[plugin_ui="true"] QDoubleSpinBox,
    QDialog[plugin_ui="true"] QSpinBox, QDialog[plugin_ui="true"] QDoubleSpinBox,
    QWidget[plugin_ui="true"] QSpinBox, QWidget[plugin_ui="true"] QDoubleSpinBox {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: 0;
        padding: 2px 6px;
        padding-right: 24px;
        min-height: {control_height}px;
        min-width: 60px;
        selection-background-color: {tokens.accent};
        selection-color: {tokens.selection_text};
    }}
    QDockWidget[plugin_ui="true"] QSpinBox::up-button, QDockWidget[plugin_ui="true"] QDoubleSpinBox::up-button,
    QDialog[plugin_ui="true"] QSpinBox::up-button, QDialog[plugin_ui="true"] QDoubleSpinBox::up-button,
    QWidget[plugin_ui="true"] QSpinBox::up-button, QWidget[plugin_ui="true"] QDoubleSpinBox::up-button {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-top-right-radius: 0;
        width: 18px;
        subcontrol-origin: border;
        subcontrol-position: top right;
    }}
    QDockWidget[plugin_ui="true"] QSpinBox::down-button, QDockWidget[plugin_ui="true"] QDoubleSpinBox::down-button,
    QDialog[plugin_ui="true"] QSpinBox::down-button, QDialog[plugin_ui="true"] QDoubleSpinBox::down-button,
    QWidget[plugin_ui="true"] QSpinBox::down-button, QWidget[plugin_ui="true"] QDoubleSpinBox::down-button {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-top: none;
        border-bottom-right-radius: 0;
        width: 18px;
        margin-top: -1px;
        subcontrol-origin: border;
        subcontrol-position: bottom right;
    }}
    QDockWidget[plugin_ui="true"] QSpinBox::up-arrow, QDockWidget[plugin_ui="true"] QDoubleSpinBox::up-arrow,
    QDialog[plugin_ui="true"] QSpinBox::up-arrow, QDialog[plugin_ui="true"] QDoubleSpinBox::up-arrow,
    QWidget[plugin_ui="true"] QSpinBox::up-arrow, QWidget[plugin_ui="true"] QDoubleSpinBox::up-arrow {{
        image: url(data:image/svg+xml;base64,{up_arrow_uri});
        width: 10px;
        height: 8px;
    }}
    QDockWidget[plugin_ui="true"] QSpinBox::down-arrow, QDockWidget[plugin_ui="true"] QDoubleSpinBox::down-arrow,
    QDialog[plugin_ui="true"] QSpinBox::down-arrow, QDialog[plugin_ui="true"] QDoubleSpinBox::down-arrow,
    QWidget[plugin_ui="true"] QSpinBox::down-arrow, QWidget[plugin_ui="true"] QDoubleSpinBox::down-arrow {{
        image: url(data:image/svg+xml;base64,{down_arrow_uri});
        width: 10px;
        height: 8px;
    }}
    QDockWidget[plugin_ui="true"] QComboBox::down-arrow, QDialog[plugin_ui="true"] QComboBox::down-arrow,
    QWidget[plugin_ui="true"] QComboBox::down-arrow {{
        image: url(data:image/svg+xml;base64,{down_arrow_uri});
        width: 10px;
        height: 8px;
    }}
    QDockWidget[plugin_ui="true"] QSpinBox:hover, QDockWidget[plugin_ui="true"] QDoubleSpinBox:hover,
    QDialog[plugin_ui="true"] QSpinBox:hover, QDialog[plugin_ui="true"] QDoubleSpinBox:hover,
    QWidget[plugin_ui="true"] QSpinBox:hover, QWidget[plugin_ui="true"] QDoubleSpinBox:hover {{
        border-color: {tokens.accent_hover};
    }}
    QDockWidget[plugin_ui="true"] QSpinBox:focus, QDockWidget[plugin_ui="true"] QDoubleSpinBox:focus,
    QDialog[plugin_ui="true"] QSpinBox:focus, QDialog[plugin_ui="true"] QDoubleSpinBox:focus,
    QWidget[plugin_ui="true"] QSpinBox:focus, QWidget[plugin_ui="true"] QDoubleSpinBox:focus {{
        border-color: {tokens.focus};
    }}
    QDockWidget[plugin_ui="true"] QSpinBox::up-button:hover, QDockWidget[plugin_ui="true"] QDoubleSpinBox::up-button:hover,
    QDialog[plugin_ui="true"] QSpinBox::up-button:hover, QDialog[plugin_ui="true"] QDoubleSpinBox::up-button:hover,
    QWidget[plugin_ui="true"] QSpinBox::up-button:hover, QWidget[plugin_ui="true"] QDoubleSpinBox::up-button:hover,
    QDockWidget[plugin_ui="true"] QSpinBox::down-button:hover, QDockWidget[plugin_ui="true"] QDoubleSpinBox::down-button:hover,
    QDialog[plugin_ui="true"] QSpinBox::down-button:hover, QDialog[plugin_ui="true"] QDoubleSpinBox::down-button:hover,
    QWidget[plugin_ui="true"] QSpinBox::down-button:hover, QWidget[plugin_ui="true"] QDoubleSpinBox::down-button:hover {{
        background-color: {tokens.accent_soft};
    }}
    QDockWidget[plugin_ui="true"] QSpinBox::up-button:pressed, QDockWidget[plugin_ui="true"] QDoubleSpinBox::up-button:pressed,
    QDialog[plugin_ui="true"] QSpinBox::up-button:pressed, QDialog[plugin_ui="true"] QDoubleSpinBox::up-button:pressed,
    QWidget[plugin_ui="true"] QSpinBox::up-button:pressed, QWidget[plugin_ui="true"] QDoubleSpinBox::up-button:pressed,
    QDockWidget[plugin_ui="true"] QSpinBox::down-button:pressed, QDockWidget[plugin_ui="true"] QDoubleSpinBox::down-button:pressed,
    QDialog[plugin_ui="true"] QSpinBox::down-button:pressed, QDialog[plugin_ui="true"] QDoubleSpinBox::down-button:pressed,
    QWidget[plugin_ui="true"] QSpinBox::down-button:pressed, QWidget[plugin_ui="true"] QDoubleSpinBox::down-button:pressed {{
        background-color: {tokens.accent_soft};
    }}
    """


def apply_theme(
    app,
    theme_name,
    font_size=10,
    row_height=22,
    accent_override=None,
    extra_stylesheet="",
):
    resolved = resolve_theme_name(theme_name, app)
    tokens = get_theme_tokens(
        resolved,
        font_size=font_size,
        row_height=row_height,
        accent_override=accent_override,
    )
    combined = build_stylesheet(tokens) + (extra_stylesheet or "")
    app.setStyleSheet(combined)
    # Set palette so primitive controls and palette-using widgets respect theme.
    palette = app.palette()
    button_text_color = tokens.text_muted if tokens.name == "light" else tokens.text
    palette.setColor(QPalette.ButtonText, QColor(button_text_color))
    if tokens.name == "dark":
        palette.setColor(QPalette.Window, QColor(tokens.background))
        palette.setColor(QPalette.WindowText, QColor(tokens.text))
        palette.setColor(QPalette.Base, QColor(tokens.surface))
        palette.setColor(QPalette.Text, QColor(tokens.text))
        palette.setColor(QPalette.Button, QColor(tokens.surface_alt))
        palette.setColor(QPalette.Highlight, QColor(tokens.accent))
        palette.setColor(QPalette.HighlightedText, QColor(tokens.selection_text))
    app.setPalette(palette)
    return tokens
