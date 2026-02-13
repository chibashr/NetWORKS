#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SNMP Poll dialog for SNMP Collector.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui, apply_plugin_ui_layout
from src.ui.plugin_widgets import wrap_in_scroll_area

from ..widgets.snmp_poll_widget import SnmpPollWidget


class SnmpPollDialog(QDialog):
    """Dialog for SNMP GET/GETNEXT polling."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("SNMP Poll")
        layout = QVBoxLayout(self)
        apply_plugin_ui_layout(layout)
        self.widget = SnmpPollWidget(plugin, self)
        layout.addWidget(wrap_in_scroll_area(self.widget))
