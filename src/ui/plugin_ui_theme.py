#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin UI theme helpers for NetWORKS.
"""

from PySide6.QtWidgets import QLayout, QWidget, QAbstractButton

from .theme import get_theme_tokens


PLUGIN_UI_PROPERTY = "plugin_ui"

PLUGIN_UI_SIZES = {
    "grid": 4,
    "section_padding": 8,
    "dialog_padding": 16,
    "button_height": 28,
    "button_bar_height": 40,
    "section_header_height": 24,
    "dock_header_height": 28,
    "tab_height": 32,
    "icon_button_size": 24,
}


def mark_plugin_ui(widget: QWidget) -> None:
    """Mark a widget as plugin UI for scoped stylesheet selectors."""
    if widget is None:
        return
    widget.setProperty(PLUGIN_UI_PROPERTY, "true")
    # Force a style refresh so the property selector is applied immediately.
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def apply_plugin_ui_layout(layout: QLayout, padding: int = None) -> None:
    """Apply standard plugin UI padding and grid spacing."""
    if layout is None:
        return
    grid = PLUGIN_UI_SIZES["grid"]
    padding_value = PLUGIN_UI_SIZES["dialog_padding"] if padding is None else padding
    layout.setSpacing(grid)
    layout.setContentsMargins(padding_value, padding_value, padding_value, padding_value)


def apply_compact_button(button: QAbstractButton) -> None:
    """Apply compact sizing to buttons in plugin UI."""
    if button is None:
        return
    button.setMinimumHeight(PLUGIN_UI_SIZES["button_height"])


def apply_icon_button(button: QAbstractButton) -> None:
    """Apply square icon button sizing (same aspect ratio as icon per design)."""
    if button is None:
        return
    size = PLUGIN_UI_SIZES["icon_button_size"]
    button.setMinimumSize(size, size)
    button.setMaximumSize(size, size)


def plugin_ui_stylesheet(tokens=None) -> str:
    """Return plugin-scoped QSS to style plugin surfaces only."""
    theme = tokens or get_theme_tokens("light")
    return f"""
    QDockWidget[plugin_ui="true"] {{
        border: 1px solid {theme.border};
        background-color: {theme.surface};
    }}
    QWidget#PluginDockHeader {{
        background-color: {theme.surface_alt};
        border-bottom: 1px solid {theme.border};
    }}
    QLabel#PluginDockTitle {{
        color: {theme.text};
        font-weight: 600;
    }}
    QFrame[plugin_ui_section="true"] {{
        border: 1px solid {theme.border};
        background-color: {theme.surface};
    }}
    QToolButton[plugin_ui_section="true"] {{
        min-height: {PLUGIN_UI_SIZES["section_header_height"]}px;
        padding: 2px 8px 4px 8px;
        margin-bottom: 12px;
        text-align: left;
        color: {theme.text};
        background-color: {theme.surface_alt};
        border: 1px solid {theme.border};
    }}
    QToolButton[plugin_ui_section="true"]:hover {{
        background-color: {theme.surface_raised};
    }}
    QToolButton[plugin_ui_section="true"]:checked {{
        background-color: {theme.surface};
        border-bottom: none;
    }}
    QDialog[plugin_ui="true"] {{
        background-color: {theme.surface};
    }}
    QDockWidget[plugin_ui="true"] QPushButton {{
        min-height: {PLUGIN_UI_SIZES["button_height"]}px;
        border-radius: 0px;
    }}
    QDialog[plugin_ui="true"] QPushButton {{
        min-height: {PLUGIN_UI_SIZES["button_height"]}px;
        border-radius: 0px;
    }}
    QDialog[plugin_ui="true"] QWidget#PluginDialogButtonBar {{
        min-height: {PLUGIN_UI_SIZES["button_bar_height"]}px;
    }}
    QTabWidget[plugin_ui="true"]::pane {{
        border: 1px solid {theme.border};
        background-color: {theme.surface};
    }}
    QTabBar[plugin_ui="true"]::tab {{
        min-height: {PLUGIN_UI_SIZES["tab_height"]}px;
        padding: 0 12px;
        background-color: {theme.surface_alt};
        border: 1px solid {theme.border};
        border-bottom: none;
        border-radius: 0px;
    }}
    QTabBar[plugin_ui="true"]::tab:selected {{
        background-color: {theme.surface};
        border-bottom: 2px solid {theme.accent};
    }}
    QDockWidget[plugin_ui="true"] QTableView,
    QDockWidget[plugin_ui="true"] QTableWidget,
    QDialog[plugin_ui="true"] QTableView,
    QDialog[plugin_ui="true"] QTableWidget {{
        border: 1px solid {theme.border};
        gridline-color: {theme.border};
        alternate-background-color: {theme.table_alt};
    }}
    QDockWidget[plugin_ui="true"] QHeaderView::section,
    QDialog[plugin_ui="true"] QHeaderView::section {{
        background-color: {theme.header_bg};
        color: {theme.header_text};
        border: 1px solid {theme.border};
    }}
    """
