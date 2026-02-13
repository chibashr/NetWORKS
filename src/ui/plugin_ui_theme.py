#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin UI theme helpers for NetWORKS.
"""

from PySide6.QtWidgets import QLayout, QWidget, QAbstractButton

from .theme import get_theme_tokens, _derive_control_height, get_control_height


PLUGIN_UI_PROPERTY = "plugin_ui"

PLUGIN_UI_SIZES = {
    "grid": 4,
    "section_padding": 8,
    "collapsible_content_padding": 2,
    "dialog_padding": 16,
    # button_height: use get_control_height() for dynamic sizing
    "button_bar_height": 40,
    "section_header_height": 22,
    "dock_header_height": 24,
    "tab_height": 24,
    "icon_button_size": 24,
    # Use 0 when stacking CollapsibleSections so they sit flush and anchor to top.
    "collapsible_stack_spacing": 0,
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
    """Apply compact sizing to buttons; height matches line edits, combos."""
    if button is None:
        return
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    button.setMinimumHeight(get_control_height(app))


def apply_icon_button(button: QAbstractButton) -> None:
    """Apply square icon button sizing; height matches line edits, combos."""
    if button is None:
        return
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    height = get_control_height(app)
    button.setMinimumSize(height, height)
    button.setMaximumSize(height, height)


def plugin_ui_stylesheet(tokens=None) -> str:
    """Return plugin-scoped QSS to style plugin surfaces only."""
    theme = tokens or get_theme_tokens("light")

    # Derive compact control sizes from theme tokens so plugin UI follows
    # configured row/header heights instead of hardcoded pixels.
    # Button height = control height so buttons align with line edits, combos.
    control_height = _derive_control_height(theme.font_size)
    button_height = control_height
    table_header_height = theme.row_height - 2
    section_header_height = theme.row_height
    dock_header_height = theme.header_height + 2
    tab_height = theme.header_height + 2
    button_bar_height = button_height + 12

    return f"""
    QDockWidget[plugin_ui="true"] {{
        border: 2px solid {theme.border};
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
    /* CollapsibleSection: sharp full-width blocks, arrow far right, text centered */
    QWidget#CollapsibleSection {{
        min-width: 100%;
    }}
    QFrame#CollapsibleSectionHeader {{
        min-height: {section_header_height}px;
        padding: 2px 6px;
        background-color: {theme.surface_alt};
        border: 1px solid {theme.border};
        border-bottom: none;
        border-radius: 0;
    }}
    QFrame#CollapsibleSectionHeader:hover {{
        background-color: {theme.surface_raised};
    }}
    QWidget#CollapsibleSection[collapsed="true"] QFrame#CollapsibleSectionHeader,
    QFrame#CollapsibleSectionHeader[collapsed="true"] {{
        border-bottom: 1px solid {theme.border};
        border-radius: 0;
    }}
    QWidget#CollapsibleSection QFrame#CollapsibleSectionContent {{
        border: 1px solid {theme.border};
        border-top: none;
        border-radius: 0;
        background-color: {theme.surface};
    }}
    QLabel#CollapsibleSectionTitle {{
        color: {theme.text};
        font-weight: 600;
        text-align: center;
    }}
    QWidget#CollapsibleSection QToolButton[plugin_ui_section="true"] {{
        min-width: {section_header_height}px;
        min-height: {section_header_height}px;
        max-width: {section_header_height}px;
        max-height: {section_header_height}px;
        padding: 0;
        margin: 0;
        color: {theme.text};
        background-color: transparent;
        border: none;
    }}
    QWidget#CollapsibleSection QToolButton[plugin_ui_section="true"]:hover {{
        background-color: {theme.surface_alt};
        border-radius: 0;
    }}
    QDialog[plugin_ui="true"] {{
        background-color: {theme.surface};
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
        min-height: {button_bar_height}px;
    }}
    QTabWidget[plugin_ui="true"]::pane {{
        border: 1px solid {theme.border};
        background-color: {theme.surface};
    }}
    QTabBar[plugin_ui="true"]::tab {{
        min-height: {tab_height}px;
        padding: 0 8px;
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
        padding: 1px 4px;
        border: 1px solid {theme.border};
        min-height: {table_header_height}px;
    }}
    QDialog[plugin_ui="true"] QLabel[plugin_ui_muted="true"],
    QWidget[plugin_ui="true"] QLabel[plugin_ui_muted="true"] {{
        color: {theme.text_muted};
    }}
    QDialog[plugin_ui="true"] QLabel[plugin_ui_warning="true"],
    QWidget[plugin_ui="true"] QLabel[plugin_ui_warning="true"] {{
        color: #F59E0B;
    }}
    """
