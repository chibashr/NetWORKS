#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template Manager dialog. Opened from toolbar or Tools menu.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox

from src.ui.plugin_ui_theme import mark_plugin_ui
from plugins.template_manager.ui.template_manager_panel import TemplateManagerPanel


class TemplateManagerDialog(QDialog):
    """Dialog that wraps the Template Manager panel."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Template Manager")
        self.setMinimumSize(1100, 620)
        self.resize(1200, 650)

        layout = QVBoxLayout(self)
        self.panel = TemplateManagerPanel(plugin, self)
        layout.addWidget(self.panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
