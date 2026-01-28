#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Template Manager dialog. Opened from toolbar or Tools menu.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox

from src.ui.plugin_ui_theme import mark_plugin_ui
from plugins.template_manager.ui.template_manager_panel import TemplateManagerPanel


class TemplateManagerDialog(QDialog):
    """Dialog that wraps the Template Manager panel."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent or plugin.main_window)
        mark_plugin_ui(self)
        self.setWindowTitle("Template Manager")
        # Allow the dialog to be more compact vertically so there is less
        # empty space between the bottom controls and the window border.
        self.setMinimumSize(1100, 520)
        self.resize(1200, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.panel = TemplateManagerPanel(plugin, self)
        layout.addWidget(self.panel)

        # Bottom row: export actions on the left, status in the middle, Close on the right.
        bottom = QHBoxLayout()
        bottom.addWidget(self.panel.export_file_btn)
        bottom.addWidget(self.panel.send_cm_btn)
        bottom.addWidget(self.panel.batch_export_btn)
        bottom.addStretch()
        bottom.addWidget(self.panel.status_label)
        bottom.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)
