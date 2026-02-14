#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin UI theme helpers for NetWORKS.
"""

from PySide6.QtWidgets import QLayout, QWidget, QAbstractButton

from .theme import get_control_height


PLUGIN_UI_PROPERTY = "plugin_ui"

PLUGIN_UI_SIZES = {
    "grid": 4,
    "section_padding": 8,
    "tab_content_padding": 8,
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


