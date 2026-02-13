#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Ingestion dialog for SNMP Collector (testing with pasted JSON).
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui, apply_plugin_ui_layout
from src.ui.plugin_widgets import wrap_in_scroll_area

from ..widgets.ingestion_widget import IngestionWidget


class IngestionDialog(QDialog):
    """Dialog for pasting JSON trap data to simulate traps."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("SNMP Ingestion (Testing)")
        layout = QVBoxLayout(self)
        apply_plugin_ui_layout(layout)
        self.widget = IngestionWidget(plugin, self)
        layout.addWidget(wrap_in_scroll_area(self.widget))
