#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Collected Logs dialog for Syslog Collector.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui, apply_plugin_ui_layout
from src.ui.plugin_widgets import wrap_in_scroll_area

from ..widgets.logs_table_widget import LogsTableWidget


class CollectedLogsDialog(QDialog):
    """Dialog for viewing collected syslog messages."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("Collected Logs")
        layout = QVBoxLayout(self)
        apply_plugin_ui_layout(layout)
        self.widget = LogsTableWidget(plugin, self)
        layout.addWidget(wrap_in_scroll_area(self.widget))
