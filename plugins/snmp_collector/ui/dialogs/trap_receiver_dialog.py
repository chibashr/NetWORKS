#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Trap Receiver dialog for SNMP Collector.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui, apply_plugin_ui_layout

from ..widgets.trap_receiver_widget import TrapReceiverWidget


class TrapReceiverDialog(QDialog):
    """Dialog for trap receiver start/stop and configuration."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("SNMP Trap Receiver")
        layout = QVBoxLayout(self)
        apply_plugin_ui_layout(layout)
        self.widget = TrapReceiverWidget(plugin, self)
        layout.addWidget(self.widget)
