#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Theme tokens and stylesheet generation for NetWORKS.
"""

from dataclasses import dataclass
from PySide6.QtGui import QPalette, QColor


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


def get_theme_tokens(theme_name, font_size=10, row_height=22, accent_override=None):
    theme = (theme_name or "light").strip().lower()
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
            header_height=24,
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
        header_height=24,
        font_size=font_size,
        spacing=4,
        radius=0,
    )
    return _apply_accent_override(tokens, accent_override)


def build_stylesheet(tokens):
    return f"""
    QWidget {{
        background-color: {tokens.background};
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
    QToolButton {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 3px 6px;
        min-width: 64px;
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
    QPushButton {{
        background-color: {tokens.surface_raised};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        padding: 4px 10px;
        min-height: 24px;
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
    QLineEdit, QTextEdit, QPlainTextEdit {{
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
        min-height: 22px;
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
        min-height: 24px;
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
    QDockWidget {{
        border: 1px solid {tokens.border};
    }}
    QDockWidget::title {{
        background-color: {tokens.dock_title_bg};
        color: {tokens.dock_title_text};
        padding: 6px 8px;
        font-weight: bold;
        min-height: 28px;
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
    QGroupBox {{
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
        border-radius: {tokens.radius}px;
        margin-top: 12px;
        padding-top: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 8px;
        margin-bottom: 12px;
        color: {tokens.text_muted};
        background-color: {tokens.surface_alt};
        border: 1px solid {tokens.border};
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
    return tokens
