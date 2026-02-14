#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Receiver Config dialog for Syslog Collector.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from src.ui.plugin_ui_theme import mark_plugin_ui, apply_plugin_ui_layout
from src.ui.plugin_widgets import wrap_in_scroll_area

from ..widgets.receiver_config_widget import ReceiverConfigWidget


class ReceiverConfigDialog(QDialog):
    """Dialog for syslog receiver configuration and start/stop."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        mark_plugin_ui(self)
        self.setWindowTitle("Syslog Receiver Config")
        layout = QVBoxLayout(self)
        apply_plugin_ui_layout(layout)
        self.widget = ReceiverConfigWidget(plugin, self)
        layout.addWidget(wrap_in_scroll_area(self.widget))
