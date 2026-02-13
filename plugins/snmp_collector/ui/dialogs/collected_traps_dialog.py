#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Collected Traps dialog for SNMP Collector.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui, apply_plugin_ui_layout

from ..widgets.traps_table_widget import TrapsTableWidget


class CollectedTrapsDialog(QDialog):
    """Dialog for viewing collected SNMP traps."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("Collected Traps")
        layout = QVBoxLayout(self)
        apply_plugin_ui_layout(layout)
        self.widget = TrapsTableWidget(plugin, self)
        layout.addWidget(self.widget)
