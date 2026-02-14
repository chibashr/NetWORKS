#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Syslog Collector panel layout.

Panel shows logs coming in and a button to open the config dialog.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Qt

from src.ui.plugin_ui_theme import mark_plugin_ui, PLUGIN_UI_SIZES
from src.ui.plugin_widgets import wrap_in_scroll_area

from .widgets.logs_table_widget import LogsTableWidget


def build_syslog_panel(plugin):
    """Build the Syslog dock panel: log table + config button."""
    container = QWidget()
    mark_plugin_ui(container)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(PLUGIN_UI_SIZES["collapsible_stack_spacing"])

    logs_widget = LogsTableWidget(plugin)
    layout.addWidget(wrap_in_scroll_area(logs_widget))

    config_btn = QPushButton("Open Config")
    config_btn.setToolTip("Open Receiver Config dialog")
    config_btn.clicked.connect(plugin._show_receiver_config_dialog)
    layout.addWidget(config_btn)

    container.setMinimumHeight(200)
    container.setMaximumHeight(420)

    return container
