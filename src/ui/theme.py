#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Theme tokens and stylesheet generation for NetWORKS.
"""

import base64
from dataclasses import dataclass
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (
    QProxyStyle,
    QStyleFactory,
    QStyle,
    QStyleOptionGroupBox,
    QGroupBox,
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
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}"><path fill="{color}" d="{path}"/></svg>'
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


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
    """Derive header height from font size for dynamic text fitting."""
    return max(20, int(round(font_size * 2.4)))


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
    button_height = tokens.row_height + 6
    control_height = tokens.row_height + 2
    dock_header_height = tokens.header_height + 4
    group_header_font_size = _group_header_font_size(tokens.font_size)
    group_header_bar_height = group_header_font_size + 4

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
        padding: 2px;
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 8px;
        border-radius: {tokens.radius}px;
        margin: 1px;
    }}
    QMenuBar::item:selected {{
        background-color: {tokens.surface_alt};
    }}
    QMenuBar::item:pressed {{
        background-color: {tokens.accent};
        color: {tokens.selection_text};
    }}
    QMenu {{
        background-color: {tokens.surface};
        border: 1px solid {tokens.border};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 4px 24px 4px 20px;
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
        spacing: 4px;
        padding: 2px;
        border-bottom: 1px solid {tokens.separator};
    }}
    QToolBar::separator {{
        background-color: {tokens.separator};
        width: 1px;
        margin: 0 4px;
    }}
    QWidget#RibbonContainer,
    QWidget#RibbonContent {{
        background-color: {tokens.toolbar_bg};
    }}
    QToolBar#RibbonToolbar {{
        background-color: {tokens.toolbar_bg};
        border-bottom: 1px solid {tokens.separator};
        padding: 0 4px;
    }}
    QTabBar#RibbonTabBar {{
        background-color: {tokens.toolbar_bg};
        border: none;
    }}
    QTabBar#RibbonTabBar::tab {{
        min-height: 24px;
        padding: 0 8px;
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-radius: 0px;
        margin-right: 2px;
        font-weight: 500;
    }}
    QTabBar#RibbonTabBar::tab:selected {{
        background-color: {tokens.surface};
        border-bottom: 3px solid {tokens.accent};
    }}
    QTabBar#RibbonTabBar::tab:hover {{
        background-color: {tokens.surface_raised};
    }}
    QToolButton {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 3px 6px;
        min-width: 64px;
        min-height: {button_height}px;
    }}
    QToolButton:hover {{
        background-color: {tokens.surface_alt};
        border-color: {tokens.border};
    }}
    QToolButton:pressed {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.accent};
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
        padding: 4px 10px;
        min-height: {button_height}px;
    }}
    QPushButton:hover {{
        background-color: {tokens.surface_alt};
        border-color: {tokens.accent_hover};
    }}
    QPushButton:pressed {{
        background-color: {tokens.accent_soft};
        border-color: {tokens.accent};
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
        padding: 4px;
        min-height: {control_height}px;
    }}
    QTextEdit, QPlainTextEdit {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 4px;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {tokens.focus};
    }}
    QComboBox {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 3px 18px 3px 6px;
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
        background-color: {tokens.accent};
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
        background-color: {tokens.accent};
        border: 1px solid {tokens.accent};
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
    QSpinBox, QDoubleSpinBox {{
        background-color: {tokens.surface_raised};
        color: {tokens.text};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 4px;
        padding-right: {control_height + 4}px;
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
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-top-right-radius: {tokens.radius}px;
        width: {control_height}px;
        subcontrol-origin: border;
        subcontrol-position: top right;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-bottom-right-radius: {tokens.radius}px;
        width: {control_height}px;
        subcontrol-origin: border;
        subcontrol-position: bottom right;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {tokens.surface_alt};
    }}
    QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
    QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
        background-color: {tokens.accent_soft};
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 6px solid {tokens.text};
        margin: 0 auto;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid {tokens.text};
        margin: 0 auto;
    }}
    QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
    QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
        border-top-color: {tokens.text_disabled};
        border-bottom-color: {tokens.text_disabled};
    }}
    QTabWidget::pane {{
        border: 1px solid {tokens.border};
        background-color: {tokens.surface};
    }}
    QTabBar::tab {{
        background-color: {tokens.surface_alt};
        color: {tokens.text};
        padding: 5px 10px;
        border: 1px solid {tokens.border};
        border-bottom: none;
        border-top-left-radius: {tokens.radius}px;
        border-top-right-radius: {tokens.radius}px;
        min-height: {tokens.header_height}px;
    }}
    QTabBar::tab:selected {{
        background-color: {tokens.surface};
        border-bottom: 1px solid {tokens.surface};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {tokens.surface_raised};
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
        padding: 2px 6px;
        border-right: 1px solid {tokens.border};
        border-bottom: 1px solid {tokens.border};
        height: {tokens.row_height}px;
    }}
    QTreeView::item:selected, QTableView::item:selected {{
        background-color: {tokens.accent};
        color: {tokens.selection_text};
    }}
    QHeaderView::section {{
        background-color: {tokens.header_bg};
        color: {tokens.header_text};
        padding: 4px 6px;
        border: 1px solid {tokens.border};
        min-height: {tokens.header_height}px;
    }}
    QListWidget, QListView {{
        background-color: {tokens.surface_raised};
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
        color: {tokens.dock_title_text};
        padding: 6px 8px;
        font-weight: bold;
        min-height: {dock_header_height}px;
    }}
    QDockWidget > QWidget {{
        border-top: 1px solid {tokens.border};
        padding-top: 12px;
    }}
    QStatusBar {{
        background-color: {tokens.status_bg};
        color: {tokens.text_muted};
        padding: 2px 6px;
    }}
    QStatusBar::item {{
        border-left: 1px solid {tokens.separator};
        padding: 0 6px;
    }}
    QSplitter::handle {{
        background-color: {tokens.separator};
    }}
    QSplitter::handle:horizontal {{
        width: 3px;
    }}
    QSplitter::handle:vertical {{
        height: 3px;
    }}
    /* Integrated header: full-width bar, centered text. Qt cannot set width on ::title;
       large padding expands title bar; parent clips. See stackoverflow.com/questions/14049290 */
    QGroupBox {{
        background-color: {tokens.surface};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        margin-top: 6px;
        padding: 12px;
        padding-top: {group_header_bar_height + 8}px;
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
        padding: 3px 10000px;
        color: {tokens.text};
        font-weight: 600;
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        min-height: {group_header_font_size}px;
        text-align: center;
    }}
    QGroupBox:checkable QGroupBox::title {{
        padding-left: 10022px;
    }}
    QGroupBox::indicator {{
        width: 10px;
        height: 10px;
        subcontrol-position: top left;
        subcontrol-origin: border;
        top: 2px;
        left: 6px;
    }}
    QGroupBox::indicator:unchecked {{
        image: url(data:image/svg+xml;base64,{_arrow_svg_data_uri("right", tokens.text_muted)});
    }}
    QGroupBox::indicator:unchecked:hover {{
        image: url(data:image/svg+xml;base64,{_arrow_svg_data_uri("right", tokens.text)});
    }}
    QGroupBox::indicator:checked {{
        image: url(data:image/svg+xml;base64,{_arrow_svg_data_uri("down", tokens.text_muted)});
    }}
    QGroupBox::indicator:checked:hover {{
        image: url(data:image/svg+xml;base64,{_arrow_svg_data_uri("down", tokens.text)});
    }}
    QLabel#PluginStatusBar {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        padding: 4px 6px;
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
        border-radius: 6px;
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
        border-radius: 6px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
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
    # Ensure primitive controls (like spin box arrows) respect theme colors.
    # These often ignore QSS and use the palette's ButtonText role instead.
    palette = app.palette()
    button_text_color = tokens.text_muted if tokens.name == "light" else tokens.text
    palette.setColor(QPalette.ButtonText, QColor(button_text_color))
    app.setPalette(palette)
    return tokens
